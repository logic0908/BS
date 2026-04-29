#!/usr/bin/env python3
from __future__ import annotations

import site
import subprocess
import sys
import traceback
from pathlib import Path

CONFIG_REPLACEMENTS = [
    ("common: CommonConfig = CommonConfig()", "common: CommonConfig = field(default_factory=CommonConfig)"),
    ("common_eval: CommonEvalConfig = CommonEvalConfig()", "common_eval: CommonEvalConfig = field(default_factory=CommonEvalConfig)"),
    (
        "distributed_training: DistributedTrainingConfig = DistributedTrainingConfig()",
        "distributed_training: DistributedTrainingConfig = field(default_factory=DistributedTrainingConfig)",
    ),
    ("dataset: DatasetConfig = DatasetConfig()", "dataset: DatasetConfig = field(default_factory=DatasetConfig)"),
    ("optimization: OptimizationConfig = OptimizationConfig()", "optimization: OptimizationConfig = field(default_factory=OptimizationConfig)"),
    ("checkpoint: CheckpointConfig = CheckpointConfig()", "checkpoint: CheckpointConfig = field(default_factory=CheckpointConfig)"),
    ("bmuf: FairseqBMUFConfig = FairseqBMUFConfig()", "bmuf: FairseqBMUFConfig = field(default_factory=FairseqBMUFConfig)"),
    ("generation: GenerationConfig = GenerationConfig()", "generation: GenerationConfig = field(default_factory=GenerationConfig)"),
    ("eval_lm: EvalLMConfig = EvalLMConfig()", "eval_lm: EvalLMConfig = field(default_factory=EvalLMConfig)"),
    ("interactive: InteractiveConfig = InteractiveConfig()", "interactive: InteractiveConfig = field(default_factory=InteractiveConfig)"),
    ("ema: EMAConfig = EMAConfig()", "ema: EMAConfig = field(default_factory=EMAConfig)"),
]
TRANSFORMER_CONFIG_REPLACEMENTS = [
    ("encoder: EncDecBaseConfig = EncDecBaseConfig()", "encoder: EncDecBaseConfig = field(default_factory=EncDecBaseConfig)"),
    ("decoder: DecoderConfig = DecoderConfig()", "decoder: DecoderConfig = field(default_factory=DecoderConfig)"),
    ("quant_noise: QuantNoiseConfig = QuantNoiseConfig()", "quant_noise: QuantNoiseConfig = field(default_factory=QuantNoiseConfig)"),
]
FAIRSEQ_INIT_PATCH = """# Python 3.11 So-VITS inference compatibility patch:
# skip hydra_init() and heavy top-level fairseq imports. ContentVec inference only needs
# fairseq.checkpoint_utils; other fairseq submodules can still be imported on demand.
# from fairseq.dataclass.initialize import hydra_init
# hydra_init()
"""
FAIRSEQ_MODELS_PATCH = """# automatically import any Python files in the models/ directory
models_dir = os.path.dirname(__file__)
# Python 3.11 So-VITS inference compatibility patch: skipped full model auto-registration.
# Full import_models(models_dir, "fairseq.models") is intentionally disabled here because
# So-VITS-SVC ContentVec inference only needs wav2vec/hubert model families.
for _sovits_model_module in [
    "fairseq.models.wav2vec.wav2vec2",
    "fairseq.models.wav2vec.wav2vec2_asr",
    "fairseq.models.hubert.hubert",
    "fairseq.models.hubert.hubert_asr",
]:
    importlib.import_module(_sovits_model_module)
"""
CHECKPOINT_UTILS_PATCH = """        # Python 3.11 / PyTorch 2.6+ So-VITS inference compatibility patch:
        # ContentVec legacy checkpoint needs full pickle loading. Only use this for trusted checkpoints.
        state = torch.load(f, map_location=torch.device("cpu"), weights_only=False)
"""


def site_roots() -> list[Path]:
    roots: list[Path] = []
    for root in list(site.getsitepackages()) + [site.getusersitepackages(), *sys.path]:
        if root:
            roots.append(Path(root))
    return roots


def locate_fairseq_file(relative_path: str) -> Path:
    seen: set[str] = set()
    for root in site_roots():
        candidate = root / "fairseq" / relative_path
        candidate_key = str(candidate)
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not locate fairseq/{relative_path} in current Python environment.")


def ensure_backup(path: Path) -> Path:
    backup_path = path.with_name(path.name + ".bak")
    if not backup_path.exists():
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


def py_compile_file(path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"py_compile failed for {path}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def apply_simple_replacements(text: str, replacements: list[tuple[str, str]]) -> tuple[str, list[str], list[str]]:
    updated = text
    patched: list[str] = []
    missing: list[str] = []
    for old, new in replacements:
        field_name = old.split(":", 1)[0].strip()
        if old in updated:
            updated = updated.replace(old, new)
            patched.append(field_name)
        elif new in updated:
            patched.append(field_name)
        else:
            missing.append(old)
    return updated, patched, missing


def replace_tail_from_marker(text: str, marker: str, replacement: str) -> tuple[str, bool]:
    if replacement in text:
        return text, True
    if marker not in text:
        return text, False
    index = text.index(marker)
    return text[:index] + replacement, True


def patch_checkpoint_utils(text: str) -> tuple[str, bool]:
    if 'state = torch.load(f, map_location=torch.device("cpu"), weights_only=False)' in text:
        return text, True
    old_line = '        state = torch.load(f, map_location=torch.device("cpu"))\n'
    if old_line in text:
        return text.replace(old_line, CHECKPOINT_UTILS_PATCH), True
    return text, False


def patch_file(path: Path, updated_text: str) -> bool:
    original_text = path.read_text(encoding="utf-8")
    ensure_backup(path)
    if updated_text != original_text:
        path.write_text(updated_text, encoding="utf-8")
    py_compile_file(path)
    return updated_text != original_text


def validate_imports() -> int:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import fairseq; from fairseq import checkpoint_utils; print('fairseq import ok')",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(result.stdout.strip())
        return 0

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if "mutable default" in result.stderr and "use default_factory" in result.stderr:
        print("Fairseq 仍存在 dataclass mutable default 兼容问题，请继续检查 configs.py 或 transformer_config.py。", file=sys.stderr)
    if "hydra_init" in result.stderr or "OmegaConf.structured" in result.stderr or "_MISSING_TYPE" in result.stderr:
        print("Fairseq 仍可能卡在 Hydra/OmegaConf 初始化阶段，请检查 fairseq/__init__.py 是否已跳过 hydra_init()。", file=sys.stderr)
    return result.returncode


def main() -> int:
    try:
        configs_path = locate_fairseq_file("dataclass/configs.py")
        init_path = locate_fairseq_file("__init__.py")
        models_init_path = locate_fairseq_file("models/__init__.py")
        checkpoint_utils_path = locate_fairseq_file("checkpoint_utils.py")
        transformer_config_path = locate_fairseq_file("models/transformer/transformer_config.py")
    except Exception:
        traceback.print_exc()
        return 1

    print(f"Detected fairseq configs.py: {configs_path}")
    print(f"Detected fairseq __init__.py: {init_path}")
    print(f"Detected fairseq models/__init__.py: {models_init_path}")
    print(f"Detected fairseq checkpoint_utils.py: {checkpoint_utils_path}")
    print(f"Detected fairseq transformer_config.py: {transformer_config_path}")

    try:
        configs_text = configs_path.read_text(encoding="utf-8")
        configs_updated, config_fields, config_missing = apply_simple_replacements(configs_text, CONFIG_REPLACEMENTS)
        patch_file(configs_path, configs_updated)

        init_text = init_path.read_text(encoding="utf-8")
        init_updated, init_found = replace_tail_from_marker(init_text, "# initialize hydra\n", FAIRSEQ_INIT_PATCH)
        patch_file(init_path, init_updated)

        models_init_text = models_init_path.read_text(encoding="utf-8")
        models_updated, models_found = replace_tail_from_marker(
            models_init_text,
            "# automatically import any Python files in the models/ directory\n",
            FAIRSEQ_MODELS_PATCH,
        )
        patch_file(models_init_path, models_updated)

        checkpoint_text = checkpoint_utils_path.read_text(encoding="utf-8")
        checkpoint_updated, checkpoint_found = patch_checkpoint_utils(checkpoint_text)
        patch_file(checkpoint_utils_path, checkpoint_updated)

        transformer_text = transformer_config_path.read_text(encoding="utf-8")
        transformer_updated, transformer_fields, transformer_missing = apply_simple_replacements(
            transformer_text,
            TRANSFORMER_CONFIG_REPLACEMENTS,
        )
        patch_file(transformer_config_path, transformer_updated)

        if config_missing:
            print("Warning: some configs.py patterns were not found exactly as expected:", file=sys.stderr)
            for pattern in config_missing:
                print(f"  - {pattern}", file=sys.stderr)
        if transformer_missing:
            print("Warning: some transformer_config.py patterns were not found exactly as expected:", file=sys.stderr)
            for pattern in transformer_missing:
                print(f"  - {pattern}", file=sys.stderr)
        if not init_found:
            print("Warning: could not find the expected hydra_init marker in fairseq/__init__.py", file=sys.stderr)
        if not models_found:
            print("Warning: could not find the expected import_models marker in fairseq/models/__init__.py", file=sys.stderr)
        if not checkpoint_found:
            print("Warning: could not find the expected torch.load checkpoint marker in fairseq/checkpoint_utils.py", file=sys.stderr)

        print("Patched configs.py fields:")
        for field_name in config_fields:
            print(f"  - {field_name}")
        print("Patched transformer_config.py fields:")
        for field_name in transformer_fields:
            print(f"  - {field_name}")
        print("Other applied patches:")
        print("  - fairseq/__init__.py: skipped hydra_init and heavy imports")
        print("  - fairseq/models/__init__.py: skipped full import_models and kept targeted wav2vec/hubert registration")
        print("  - fairseq/checkpoint_utils.py: torch.load(..., weights_only=False)")

        return validate_imports()
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
