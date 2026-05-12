from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(name: str, relative_path: str):
    script_path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_conversion_ablation_accepts_all_adapter_modes(monkeypatch, tmp_path):
    module = _load_script_module("run_conversion_ablation", "scripts/run_conversion_ablation.py")
    captured: list[tuple[str, str]] = []

    monkeypatch.setattr(module, "build_environment_check", lambda: {"torch": {"torch_cuda_is_available": False}})

    def fake_run_single_experiment(
        *,
        input_path: str,
        prompt: str,
        style_strength: float,
        case,
        task_backend_mode: str,
        timeout_seconds: float,
        poll_seconds: float,
    ):
        captured.append((case.adapter_mode, case.f0_method))
        return {
            "label": case.label,
            "task_id": f"{case.adapter_mode}-{case.f0_method}",
            "prompt": prompt,
            "requested_model_preset_id": case.model_preset_id,
            "effective_model_preset_id": case.model_preset_id,
            "speaker": "lain",
            "adapter_mode": case.adapter_mode,
            "f0_method": case.f0_method,
            "duration_consistency": None,
            "low_energy_ratio": None,
            "possible_dropouts": None,
            "output_path": None,
        }

    monkeypatch.setattr(module, "run_single_experiment", fake_run_single_experiment)
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            input="demo.wav",
            prompt="清亮、少年感、男声",
            style_strength=0.65,
            model_preset_id="final_primary",
            adapter_modes=["no_adapter", "rule_based", "trained"],
            f0_methods=["rmvpe"],
            cases=None,
            task_backend_mode="local",
            poll_seconds=0.1,
            timeout_seconds=1.0,
            output=str(tmp_path / "ablation.json"),
        ),
    )

    result = module.main()

    assert result == 0
    assert captured == [
        ("no_adapter", "rmvpe"),
        ("rule_based_adapter", "rmvpe"),
        ("trained_adapter", "rmvpe"),
    ]


def test_evaluate_audio_quality_template_writer(monkeypatch, tmp_path):
    module = _load_script_module("evaluate_audio_quality", "scripts/evaluate_audio_quality.py")
    template_path = tmp_path / "eval_cases.example.json"
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(cases=None, output=tmp_path / "objective_metrics.json", init_template=template_path),
    )
    assert module.main() == 0
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    assert payload["cases"][0]["sample_id"] == "case_001"


def test_run_film_strength_ablation_dry_run_writes_report(monkeypatch, tmp_path):
    module = _load_script_module("run_film_strength_ablation", "scripts/run_film_strength_ablation.py")
    output_path = tmp_path / "film_strength_ablation.json"
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            input="/missing/demo.wav",
            prompt="温柔、明亮、流行感更强的女声风格",
            strengths=["0", "0.05", "0.10", "0.15"],
            preset="final_primary",
            output=output_path,
            dry_run=True,
            max_cases=0,
            skip_existing=False,
        ),
    )
    assert module.main() == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "dry_run"
    assert len(payload["results"]) == 4


def test_run_condition_mode_ablation_dry_run_writes_report(monkeypatch, tmp_path):
    module = _load_script_module("run_condition_mode_ablation", "scripts/run_condition_mode_ablation.py")
    output_path = tmp_path / "condition_mode_ablation.json"
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            input="/missing/demo.wav",
            prompt="温柔、明亮、流行感更强的女声风格",
            preset="final_primary",
            output=output_path,
            film_strength=0.10,
            dry_run=True,
            include_combo=False,
        ),
    )
    assert module.main() == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "dry_run"
    assert [row["label"] for row in payload["results"]] == ["none", "external_preset", "internal_film"]


def test_train_text_style_adapter_dry_run_report(monkeypatch, tmp_path):
    module = _load_script_module("train_text_style_adapter", "scripts/train_text_style_adapter.py")
    metadata_path = tmp_path / "metadata.jsonl"
    metadata_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "sample_001",
                        "input_audio_path": "runtime/eval_samples/input.wav",
                        "target_audio_path": "runtime/eval_samples/output.wav",
                        "style_prompt": "清亮、少年感、流行男声",
                        "style_label": "bright,youth,male",
                        "speaker": "lain",
                        "split": "train",
                        "notes": "test",
                    },
                    ensure_ascii=False,
                )
            ]
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "text_style_adapter_dry_run.json"
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            metadata=metadata_path,
            output=tmp_path / "text_style_adapter_v1.pt",
            epochs=2,
            batch_size=1,
            style_dim=16,
            device="cpu",
            dry_run=True,
            report_output=report_path,
            minimum_train_samples=8,
        ),
    )
    assert module.main() == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "dry_run_ready"
    assert payload["rows_usable"] == 1


def test_summarize_subjective_eval_pending_state(monkeypatch, tmp_path):
    module = _load_script_module("summarize_subjective_eval", "scripts/summarize_subjective_eval.py")
    input_path = tmp_path / "subjective_eval_scores.csv"
    input_path.write_text(
        "listener_id,sample_id,prompt,condition,naturalness_score,clarity_score,content_preservation_score,prompt_match_score,style_change_score,overall_preference,comments\n",
        encoding="utf-8",
    )
    output_json = tmp_path / "subjective_eval_summary.json"
    output_md = tmp_path / "subjective_eval_summary.md"
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: module.argparse.Namespace(
            input=input_path,
            pairwise_input=tmp_path / "missing_pairwise.csv",
            output_json=output_json,
            output_md=output_md,
        ),
    )
    assert module.main() == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["status"] == "pending_human_scores"
