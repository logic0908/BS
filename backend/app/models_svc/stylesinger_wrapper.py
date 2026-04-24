import os
import sys
import uuid
import traceback
import logging
import tempfile
import shutil
import json
import importlib
import importlib.util
import importlib.metadata
from dataclasses import dataclass
from typing import Dict

import librosa
import numpy as np
import soundfile as sf
from scipy import signal

import torch
from app.models_svc.audio_processor import AudioProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# /home/featurize/work/BS/backend/app/models_svc/stylesinger_wrapper.py
# -> /home/featurize/work/BS/StyleSinger
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
STYLESINGER_ROOT = os.path.join(BASE_DIR, "StyleSinger")
RMVPE_VENDORED_DIR = os.path.join(BACKEND_DIR, "third_party", "RMVPE")
RMVPE_DEFAULT_MODEL_PATH = os.path.join(BACKEND_DIR, "models", "rmvpe", "rmvpe.pt")
RMVPE_REPO_URL = "https://github.com/xavriley/RMVPE.git"
RMVPE_PINNED_COMMIT = "37a4b6254c4fa6eb73898177aa4e70749eb665f3"
RMVPE_ALGO_REPO_URL = "https://github.com/Dream-High/RMVPE"

DEFAULT_STYLESINGER_PHONE_SET = {
    "breathe", "_NONE", "a", "ai", "an", "ang", "ao", "b", "c", "ch", "d", "e", "ei", "en", "eng",
    "er", "f", "g", "h", "i", "ia", "ian", "iang", "iao", "ie", "in", "ing", "iong", "iou", "j", "k",
    "l", "m", "n", "o", "ong", "ou", "p", "q", "r", "s", "sh", "t", "u", "ua", "uai", "uan", "uang",
    "uei", "uen", "uo", "v", "van", "ve", "vn", "x", "z", "zh",
}
CHINESE_INITIALS = {"b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h", "j", "q", "x", "zh", "ch", "sh", "r", "z", "c", "s"}
LIGHT_FUNCTION_CHARS = {"的", "了", "吗", "呢", "啊", "吧", "着"}
SPECIAL_TOKEN_MAP = {
    "<AP>": "breathe",
    "AP": "breathe",
    "ap": "breathe",
    "<SP>": "_NONE",
    "SP": "_NONE",
    "sp": "_NONE",
    "sil": "_NONE",
    "SIL": "_NONE",
    "pau": "_NONE",
    "PAU": "_NONE",
}
PINYIN_FINAL_NORMALIZATION_MAP = {
    "iu": "iou",
    "ui": "uei",
    "un": "uen",
    "ü": "v",
    "ue": "ve",
    "üe": "ve",
    "üan": "van",
    "uan": "uan",
    "ün": "vn",
}
ZERO_INITIAL_ALIAS_MAP = {
    "ya": "ia",
    "yan": "ian",
    "yang": "iang",
    "yao": "iao",
    "ye": "ie",
    "yin": "in",
    "ying": "ing",
    "yong": "iong",
    "you": "iou",
    "wa": "ua",
    "wai": "uai",
    "wan": "uan",
    "wang": "uang",
    "wei": "uei",
    "wen": "uen",
    "wo": "uo",
    "yu": "v",
    "yue": "ve",
    "yuan": "van",
    "yun": "vn",
}
POLYPHONE_PHRASE_DICT = {
    "音乐": [["yin"], ["yue"]],
    "快乐": [["kuai"], ["le"]],
    "乐队": [["yue"], ["dui"]],
    "长大": [["zhang"], ["da"]],
    "成长": [["cheng"], ["zhang"]],
    "银行": [["yin"], ["hang"]],
    "行走": [["xing"], ["zou"]],
    "行人": [["xing"], ["ren"]],
    "重量": [["zhong"], ["liang"]],
    "重复": [["chong"], ["fu"]],
    "为你": [["wei"], ["ni"]],
    "为了": [["wei"], ["le"]],
    "得到": [["de"], ["dao"]],
    "过往": [["guo"], ["wang"]],
    "着你": [["zhe"], ["ni"]],
    "温和": [["wen"], ["he"]],
}

def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


DEFAULT_FEATURE_EXTRACTION_MODE = "legacy"
USE_EXPERIMENTAL_ALIGNMENT = _env_flag("USE_EXPERIMENTAL_ALIGNMENT", False)
USE_EXPERIMENTAL_RMVPE = _env_flag("USE_EXPERIMENTAL_RMVPE", False)
USE_BREATHE_INSERTION = _env_flag("USE_BREATHE_INSERTION", False)
USE_AGGRESSIVE_SEGMENT = _env_flag("USE_AGGRESSIVE_SEGMENT", False)
USE_ITERATIVE_MICRO_MERGE = _env_flag("USE_ITERATIVE_MICRO_MERGE", False)
USE_HARD_QUALITY_GATE = _env_flag("USE_HARD_QUALITY_GATE", False)


def _prepare_transformers_runtime_for_whisperx() -> None:
    """
    Force transformers/whisperx to stay on the PyTorch path.
    This must happen before importing whisperx/transformers.
    """
    os.environ["USE_TF"] = "0"
    os.environ["TRANSFORMERS_NO_TF"] = "1"


_prepare_transformers_runtime_for_whisperx()

if STYLESINGER_ROOT not in sys.path:
    sys.path.append(STYLESINGER_ROOT)

_cwd = os.getcwd()
try:
    os.chdir(STYLESINGER_ROOT)
    from inference.StyleSinger import StyleSingerInfer
    from utils.hparams import hparams, set_hparams
    from utils.audio import save_wav
finally:
    os.chdir(_cwd)


@dataclass
class TaskState:
    task_id: str
    status: str
    message: str
    output_path: str | None = None
    error: str | None = None


class StyleSingerService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StyleSingerService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        # 检查并设置 CUDA，仅在需要模型推理时初始化
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._tasks: Dict[str, TaskState] = {}
        self._whisper_model_cache = {}
        self._whisperx_model = None
        self._whisperx_module = None
        self._whisperx_align_cache = {}
        self._rmvpe_model = None
        self._polyphone_dict_initialized = False
        self._stylesinger_phone_set = self._load_stylesinger_phone_set()
        self._enhanced_stack_status = {
            "checked": False,
            "ready": False,
            "mode_default": DEFAULT_FEATURE_EXTRACTION_MODE,
            "missing": [],
            "details": {},
        }
        self._initialized = True

    def _init_model(self):
        if hasattr(self, "infer_ins"):
            return
        
        current_cwd = os.getcwd()
        try:
            os.chdir(STYLESINGER_ROOT)
            config_path = os.path.join(STYLESINGER_ROOT, "egs/stylesinger.yaml")
            set_hparams(config_path, global_hparams=True)
            hparams["work_dir"] = STYLESINGER_ROOT
            hparams["processed_data_dir"] = os.path.join(STYLESINGER_ROOT, "data/processed")
            phone_set = os.path.join(hparams["processed_data_dir"], "phone_set.json")
            if not os.path.exists(phone_set):
                os.makedirs(hparams["processed_data_dir"], exist_ok=True)
                src_phone = os.path.join(STYLESINGER_ROOT, "ZH_checkpoint_phone_set.json")
                with open(src_phone, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(phone_set, "w", encoding="utf-8") as f:
                    f.write(content)
            for candidate in [
                os.path.join(STYLESINGER_ROOT, "checkpoints/StyleSinger"),
                os.path.join(STYLESINGER_ROOT, "checkpoints/Stylesinger"),
            ]:
                if os.path.isdir(candidate):
                    hparams["exp_name"] = candidate
                    break
            if not hparams.get("exp_name"):
                raise RuntimeError("未找到StyleSinger预训练模型目录")
            
            # Lazy initialize the inference instance which requires CUDA
            self.infer_ins = StyleSingerInfer(hparams, device=self.device)
        finally:
            os.chdir(current_cwd)

    def create_task(self) -> str:
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = TaskState(task_id=task_id, status="queued", message="任务已创建")
        return task_id

    def get_task(self, task_id: str) -> TaskState | None:
        return self._tasks.get(task_id)

    def _load_stylesinger_phone_set(self) -> set[str]:
        candidates = [
            os.path.join(STYLESINGER_ROOT, "data/processed/phone_set.json"),
            os.path.join(STYLESINGER_ROOT, "ZH_checkpoint_phone_set.json"),
        ]
        for path in candidates:
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        loaded = {str(x).strip() for x in data if str(x).strip()}
                        if loaded:
                            logger.info("Loaded StyleSinger phone set from %s (size=%d)", path, len(loaded))
                            return loaded
            except Exception as exc:
                logger.warning("Failed to load StyleSinger phone set from %s: %s", path, exc)
        logger.warning("Use built-in fallback StyleSinger phone set (size=%d)", len(DEFAULT_STYLESINGER_PHONE_SET))
        return set(DEFAULT_STYLESINGER_PHONE_SET)

    def _ensure_polyphone_dict(self) -> None:
        if self._polyphone_dict_initialized:
            return
        try:
            from pypinyin import load_phrases_dict
            load_phrases_dict(POLYPHONE_PHRASE_DICT)
            logger.info("Polyphone phrase dict initialized for lyric G2P (size=%d)", len(POLYPHONE_PHRASE_DICT))
        except Exception as exc:
            logger.warning("Failed to initialize polyphone phrase dict: %s", exc)
        self._polyphone_dict_initialized = True

    def _normalize_special_tokens(self, token: str) -> str:
        """
        统一处理 GTSinger/标注中的特殊 token 到 StyleSinger phone set。
        """
        key = str(token).strip()
        return SPECIAL_TOKEN_MAP.get(key, key)

    def _normalize_zero_initial_final(self, raw_final: str, normal_py: str) -> str:
        final = PINYIN_FINAL_NORMALIZATION_MAP.get(raw_final, raw_final)
        py = (normal_py or "").lower()
        if py in ZERO_INITIAL_ALIAS_MAP:
            return ZERO_INITIAL_ALIAS_MAP[py]
        return final

    def _g2p_chinese_to_stylesinger_phones(self, text: str) -> list[dict]:
        """
        输入中文歌词，输出按“字->音素”组织的 G2P 结构，且 phone 严格受中文 phone set 约束。
        """
        from pypinyin import pinyin, Style

        self._ensure_polyphone_dict()
        chars = [ch for ch in str(text or "") if "\u4e00" <= ch <= "\u9fff"]
        if not chars:
            return []

        full_text = "".join(chars)
        initials = pinyin(full_text, style=Style.INITIALS, strict=True, heteronym=False)
        finals = pinyin(full_text, style=Style.FINALS, strict=True, heteronym=False)
        normals = pinyin(full_text, style=Style.NORMAL, strict=True, heteronym=False)

        entries: list[dict] = []
        for idx, ch in enumerate(chars):
            raw_initial = (initials[idx][0] if idx < len(initials) and initials[idx] else "").strip().lower()
            raw_final = (finals[idx][0] if idx < len(finals) and finals[idx] else "").strip().lower()
            normal_py = (normals[idx][0] if idx < len(normals) and normals[idx] else "").strip().lower()

            initial = self._normalize_special_tokens(raw_initial)
            if initial and initial not in CHINESE_INITIALS:
                logger.warning("Illegal initial phone for char '%s': %s, fallback to empty initial", ch, initial)
                initial = ""

            final = self._normalize_zero_initial_final(raw_final, normal_py)
            final = self._normalize_special_tokens(final)

            phones: list[str] = []
            if initial:
                phones.append(initial)
            if final:
                phones.append(final)

            valid_phones: list[str] = []
            invalid_phones: list[str] = []
            for ph in phones:
                if ph in self._stylesinger_phone_set:
                    valid_phones.append(ph)
                else:
                    invalid_phones.append(ph)

            if invalid_phones:
                logger.warning("Char '%s' generated illegal phones %s, normal_py=%s", ch, invalid_phones, normal_py)

            if not valid_phones:
                # 回退到中性元音，避免把发声字直接丢弃
                valid_phones = ["a"] if "a" in self._stylesinger_phone_set else []

            entry = {
                "char": ch,
                "initial": valid_phones[0] if valid_phones and valid_phones[0] in CHINESE_INITIALS else "",
                "final": valid_phones[-1] if valid_phones else "",
                "phones": valid_phones,
                "char_index": idx,
                "normal_py": normal_py,
            }
            entries.append(entry)

        logger.info("Lyric G2P text='%s' -> entries=%s", full_text, entries)
        return entries

    def _split_initial_final_duration(
        self,
        char_duration: float,
        has_initial: bool,
        energy_rise_ratio: float | None = None,
    ) -> tuple[float, float]:
        total = max(0.06, float(char_duration))
        if not has_initial:
            return 0.0, total

        ratio = 0.22
        if energy_rise_ratio is not None:
            ratio = float(np.clip(energy_rise_ratio, 0.15, 0.30))
        initial_dur = max(0.05, min(total * ratio, total * 0.38))
        if initial_dur >= total:
            initial_dur = total * 0.25
        final_dur = max(0.05, total - initial_dur)
        return round(initial_dur, 3), round(final_dur, 3)

    def _detect_melisma_segments(self, midi_seq: list[int]) -> list[tuple[int, float, int]]:
        if not midi_seq:
            return []

        compressed: list[tuple[int, int]] = []
        current = midi_seq[0]
        count = 1
        for value in midi_seq[1:]:
            if abs(value - current) <= 1:
                count += 1
            else:
                compressed.append((current, count))
                current = value
                count = 1
        compressed.append((current, count))

        total = sum(c for _, c in compressed) or 1
        kept = [(m, c / total) for m, c in compressed if c / total >= 0.12 and m > 0]
        if not kept:
            median_midi = int(np.median([m for m in midi_seq if m > 0])) if any(m > 0 for m in midi_seq) else 0
            return [(median_midi, 1.0, 2)] if median_midi > 0 else []

        ratio_total = sum(r for _, r in kept) or 1.0
        segments: list[tuple[int, float, int]] = []
        for idx, (midi, ratio) in enumerate(kept):
            segments.append((midi, ratio / ratio_total, 2 if idx == 0 else 3))
        return segments

    def _classify_gap_token(self, y: np.ndarray, sr: int, start_t: float, end_t: float) -> str:
        dur = max(0.0, end_t - start_t)
        if dur < 0.05:
            return "_NONE"

        start = int(max(0.0, start_t) * sr)
        end = int(max(0.0, end_t) * sr)
        seg = y[start:end] if end > start else np.array([], dtype=np.float32)
        if seg.size < 256:
            return "_NONE"

        rms = float(np.sqrt(np.mean(np.square(seg))) + 1e-8)
        zcr = float(np.mean(librosa.feature.zero_crossing_rate(seg, frame_length=min(1024, len(seg)), hop_length=max(1, min(256, len(seg) // 4)))[0]))
        centroid = float(np.mean(librosa.feature.spectral_centroid(y=seg, sr=sr)[0]))
        if 0.001 <= rms <= 0.08 and zcr >= 0.08 and centroid >= 1600:
            return "breathe"
        return "_NONE"

    def _postprocess_4d_for_chinese_singing(
        self,
        ph_seq: list[str],
        note_seq: list[int],
        dur_seq: list[float],
        type_seq: list[int],
    ) -> tuple[list[str], list[int], list[float], list[int]]:
        """
        让四维序列更贴近中文歌曲吐字节奏：
        - 声母不宜过短
        - 同 final 的碎片优先合并
        - 气口前后不挤爆
        """
        s_ph, s_note, s_dur, s_type = self._sanitize_feature_sequences(ph_seq, note_seq, dur_seq, type_seq)
        if not s_ph:
            return s_ph, s_note, s_dur, s_type

        for idx, ph in enumerate(s_ph):
            if ph in CHINESE_INITIALS and s_type[idx] in (2, 3) and s_dur[idx] < 0.05:
                boost = 0.05 - s_dur[idx]
                s_dur[idx] = 0.05
                if idx + 1 < len(s_dur) and s_dur[idx + 1] > 0.08:
                    s_dur[idx + 1] = max(0.05, s_dur[idx + 1] - boost)

        merged_ph: list[str] = []
        merged_note: list[int] = []
        merged_dur: list[float] = []
        merged_type: list[int] = []
        for ph, note, dur, typ in zip(s_ph, s_note, s_dur, s_type):
            if (
                merged_ph
                and ph not in {"_NONE", "breathe"}
                and merged_ph[-1] == ph
                and abs(merged_note[-1] - note) <= 1
                and (dur < 0.06 or merged_dur[-1] < 0.06)
            ):
                merged_dur[-1] += dur
                if typ == 3 and merged_type[-1] == 2:
                    merged_type[-1] = 2
                continue
            merged_ph.append(ph)
            merged_note.append(note)
            merged_dur.append(dur)
            merged_type.append(typ)

        for idx, ph in enumerate(merged_ph):
            if ph == "breathe":
                if idx > 0 and merged_ph[idx - 1] not in {"_NONE", "breathe"} and merged_dur[idx - 1] < 0.05:
                    need = 0.05 - merged_dur[idx - 1]
                    transfer = min(need, max(0.0, merged_dur[idx] - 0.06))
                    merged_dur[idx - 1] += transfer
                    merged_dur[idx] -= transfer
                if idx + 1 < len(merged_ph) and merged_ph[idx + 1] not in {"_NONE", "breathe"} and merged_dur[idx + 1] < 0.05:
                    need = 0.05 - merged_dur[idx + 1]
                    transfer = min(need, max(0.0, merged_dur[idx] - 0.06))
                    merged_dur[idx + 1] += transfer
                    merged_dur[idx] -= transfer

        for idx in range(len(merged_ph) - 1, -1, -1):
            if merged_ph[idx] not in {"_NONE", "breathe"}:
                merged_dur[idx] = round(merged_dur[idx] * 1.08, 3)
                break

        out_ph, out_note, out_dur, out_type = self._sanitize_feature_sequences(merged_ph, merged_note, merged_dur, merged_type)
        min_len = min(len(out_ph), len(out_note), len(out_dur), len(out_type))
        return out_ph[:min_len], out_note[:min_len], out_dur[:min_len], out_type[:min_len]

    def _get_whisper_model(self, device: str):
        import whisper

        whisper_model_size = os.environ.get("WHISPER_MODEL_SIZE")
        if not whisper_model_size:
            whisper_model_size = "medium" if device == "cuda" else "base"

        cache_key = (device, whisper_model_size)
        if cache_key in self._whisper_model_cache:
            return self._whisper_model_cache[cache_key]

        logger.info("Loading plain Whisper model size: %s", whisper_model_size)
        try:
            model = whisper.load_model(whisper_model_size, device=device)
        except Exception as e:
            logger.warning("Failed to load Whisper model '%s': %s. Falling back to 'base'", whisper_model_size, e)
            cache_key = (device, "base")
            if cache_key in self._whisper_model_cache:
                return self._whisper_model_cache[cache_key]
            model = whisper.load_model("base", device=device)
        self._whisper_model_cache[cache_key] = model
        return model

    def _get_whisperx_runtime(self):
        if self._whisperx_module is None:
            _prepare_transformers_runtime_for_whisperx()
            import whisperx
            self._whisperx_module = whisperx
        return self._whisperx_module

    def _is_distribution_installed(self, *names: str) -> bool:
        for name in names:
            try:
                importlib.metadata.version(name)
                return True
            except importlib.metadata.PackageNotFoundError:
                continue
        return False

    def _is_whisperx_abi_conflict_error(self, exc: Exception | str) -> bool:
        text = str(exc)
        markers = [
            "_ARRAY_API not found",
            "numpy.core.umath failed to import",
            "numpy.dtype size changed",
            "compiled against abi version",
            "ml_dtypes",
        ]
        return any(marker in text for marker in markers)

    def _format_whisperx_runtime_conflict_message(
        self,
        numpy_version: str,
        tensorflow_installed: bool,
        ml_dtypes_installed: bool,
        extra_reason: str = "",
    ) -> str:
        base = (
            "NumPy / TensorFlow ABI conflict detected for WhisperX. "
            f"numpy={numpy_version}, tensorflow_installed={tensorflow_installed}, "
            f"ml_dtypes_installed={ml_dtypes_installed}. "
            "Use backend/requirements-enhanced.txt with numpy>=2.1, and avoid TensorFlow in the enhanced environment."
        )
        if extra_reason:
            return f"{base} Details: {extra_reason}"
        return base

    def _probe_whisperx_runtime(self) -> tuple[bool, str]:
        """
        Probe WhisperX runtime availability without downloading a model.
        Detects NumPy/TensorFlow ABI conflicts early and validates the basic
        whisperx/transformers import path.
        """
        _prepare_transformers_runtime_for_whisperx()
        numpy_version = np.__version__
        numpy_major = int(numpy_version.split(".", 1)[0])
        tensorflow_installed = self._is_distribution_installed("tensorflow", "tensorflow-cpu")
        ml_dtypes_installed = self._is_distribution_installed("ml-dtypes", "ml_dtypes")

        if numpy_major >= 2 and (tensorflow_installed or ml_dtypes_installed):
            return (
                False,
                self._format_whisperx_runtime_conflict_message(
                    numpy_version,
                    tensorflow_installed,
                    ml_dtypes_installed,
                    "NumPy 2.x ABI conflict with TensorFlow/ml_dtypes in enhanced mode",
                ),
            )

        try:
            whisperx = self._get_whisperx_runtime()
            if not callable(getattr(whisperx, "load_model", None)):
                return False, "WhisperX runtime probe failed: load_model is unavailable"
            import transformers
            _ = transformers.__version__
            return True, ""
        except Exception as exc:
            if self._is_whisperx_abi_conflict_error(exc):
                return (
                    False,
                    self._format_whisperx_runtime_conflict_message(
                        numpy_version,
                        tensorflow_installed,
                        ml_dtypes_installed,
                        str(exc),
                    ),
                )
            return False, f"WhisperX runtime probe failed: {exc}"

    def _get_rmvpe_candidate_python_paths(self) -> list[str]:
        candidates: list[str] = []
        env_path = (os.environ.get("RMVPE_PYTHON_PATH") or "").strip()
        if env_path:
            candidates.append(env_path)
        candidates.append(RMVPE_VENDORED_DIR)
        return candidates

    def _ensure_rmvpe_import_path(self) -> str | None:
        for rmvpe_python_path in self._get_rmvpe_candidate_python_paths():
            candidate_dir = rmvpe_python_path
            if os.path.isfile(candidate_dir):
                candidate_dir = os.path.dirname(candidate_dir)

            if os.path.isdir(candidate_dir):
                if candidate_dir not in sys.path:
                    sys.path.insert(0, candidate_dir)
                return candidate_dir
        return None

    def _get_rmvpe_model_candidates(self) -> list[str]:
        return [
            os.environ.get("RMVPE_MODEL_PATH") or "",
            RMVPE_DEFAULT_MODEL_PATH,
            os.path.join(BASE_DIR, "rmvpe.pt"),
            os.path.join(STYLESINGER_ROOT, "rmvpe.pt"),
        ]

    def _get_rmvpe_model_path(self) -> str:
        return next((path for path in self._get_rmvpe_model_candidates() if path), RMVPE_DEFAULT_MODEL_PATH)

    def _inspect_rmvpe_module(self) -> dict:
        self._ensure_rmvpe_import_path()
        spec = importlib.util.find_spec("rmvpe")
        if spec is None:
            return {
                "ready": False,
                "source": "missing",
                "path": "",
            }

        module_path = ""
        if spec.origin and spec.origin != "built-in":
            module_path = os.path.abspath(spec.origin)
        elif spec.submodule_search_locations:
            module_path = os.path.abspath(next(iter(spec.submodule_search_locations), ""))

        source = "unknown"
        if module_path:
            if os.path.abspath(RMVPE_VENDORED_DIR) in module_path:
                source = "vendored"
            elif "site-packages" in module_path or "dist-packages" in module_path:
                source = "site_packages"
            else:
                source = "custom_path"

        return {
            "ready": True,
            "source": source,
            "path": module_path,
        }

    def _get_feature_extraction_mode(self, is_vocal_only: bool = False, lyrics: str = "") -> str:
        """
        默认始终走更朴素稳定的 legacy 链。
        enhanced 仅保留给显式后端策略或内部调试使用，不再做自动切换。
        """
        policy = (os.environ.get("FEATURE_EXTRACTION_POLICY") or DEFAULT_FEATURE_EXTRACTION_MODE).strip().lower()
        mode = DEFAULT_FEATURE_EXTRACTION_MODE
        if policy == "force_enhanced":
            status = self.get_enhanced_stack_status(force_refresh=False)
            if status.get("ready", False):
                mode = "enhanced"
            else:
                logger.warning("FEATURE_EXTRACTION_POLICY is force_enhanced but dependencies are missing. Falling back to legacy.")
        logger.info("Resolved feature extraction mode internally: %s (policy: %s)", mode, policy)
        return mode

    def get_enhanced_stack_status(self, force_refresh: bool = False) -> dict:
        if self._enhanced_stack_status["checked"] and not force_refresh:
            return self._enhanced_stack_status

        logger.info("Enhanced stack startup check begin")
        mode_default = DEFAULT_FEATURE_EXTRACTION_MODE
        missing: list[str] = []
        details = {
            "whisperx_available": False,
            "whisperx_runtime_ok": False,
            "whisperx_runtime_reason": "",
            "rmvpe_available": False,
            "rmvpe_ready": False,
            "rmvpe_python_path": self._ensure_rmvpe_import_path() or "",
            "rmvpe_module_source": "missing",
            "rmvpe_module_path": "",
            "rmvpe_vendored_path": RMVPE_VENDORED_DIR,
            "ffmpeg_available": False,
            "rmvpe_model_path": self._get_rmvpe_model_path(),
            "rmvpe_model_exists": False,
            "numpy_version": np.__version__,
            "tensorflow_installed": self._is_distribution_installed("tensorflow", "tensorflow-cpu"),
            "ml_dtypes_installed": self._is_distribution_installed("ml-dtypes", "ml_dtypes"),
        }

        try:
            self._get_whisperx_runtime()
            details["whisperx_available"] = True
        except Exception as exc:
            missing.append("whisperx")
            if self._is_whisperx_abi_conflict_error(exc):
                details["whisperx_runtime_reason"] = self._format_whisperx_runtime_conflict_message(
                    details["numpy_version"],
                    details["tensorflow_installed"],
                    details["ml_dtypes_installed"],
                    str(exc),
                )

        runtime_ok, runtime_reason = self._probe_whisperx_runtime()
        details["whisperx_runtime_ok"] = runtime_ok
        details["whisperx_runtime_reason"] = runtime_reason
        if not runtime_ok:
            missing.append("whisperx_runtime")

        try:
            self._ensure_rmvpe_import_path()
            importlib.import_module("rmvpe")
            details["rmvpe_available"] = True
            module_info = self._inspect_rmvpe_module()
            details["rmvpe_module_source"] = module_info["source"]
            details["rmvpe_module_path"] = module_info["path"]
        except Exception:
            missing.append("rmvpe")

        ffmpeg_bin = shutil.which("ffmpeg")
        details["ffmpeg_available"] = bool(ffmpeg_bin)
        if not ffmpeg_bin:
            missing.append("ffmpeg")

        candidates = self._get_rmvpe_model_candidates()
        rmvpe_model_path = next((path for path in candidates if path), details["rmvpe_model_path"])
        details["rmvpe_model_path"] = rmvpe_model_path
        details["rmvpe_model_exists"] = bool(rmvpe_model_path and os.path.exists(rmvpe_model_path) and os.access(rmvpe_model_path, os.R_OK))
        if not details["rmvpe_model_exists"]:
            missing.append("RMVPE_MODEL_PATH")
        details["rmvpe_ready"] = details["rmvpe_available"] and details["rmvpe_model_exists"]

        ready = (
            details["whisperx_available"]
            and details["whisperx_runtime_ok"]
            and details["rmvpe_available"]
            and details["ffmpeg_available"]
            and details["rmvpe_model_exists"]
        )
        self._enhanced_stack_status = {
            "checked": True,
            "ready": ready,
            "mode_default": mode_default,
            "missing": missing,
            "details": details,
        }
        logger.info("Enhanced stack startup check result: ready=%s, missing=%s", ready, missing)
        return self._enhanced_stack_status

    def _validate_enhanced_feature_stack(self) -> None:
        """
        enhanced 模式必须真的具备 WhisperX + RMVPE 全链路。
        如果依赖缺失却继续静默 fallback，用户会误以为高精度链路已启用。
        """
        status = self.get_enhanced_stack_status(force_refresh=False)
        if status["ready"]:
            logger.info("Enhanced stack validation passed")
            return

        missing = set(status["missing"])
        if "whisperx" in missing:
            raise RuntimeError("Enhanced feature extraction requires whisperx, but module is not installed")
        if "whisperx_runtime" in missing:
            raise RuntimeError(status["details"].get("whisperx_runtime_reason") or "WhisperX runtime is not available in the current environment")
        if "rmvpe" in missing:
            raise RuntimeError("Enhanced feature extraction requires rmvpe, but module is not installed. Please run backend/scripts/setup_rmvpe.py")
        if "RMVPE_MODEL_PATH" in missing:
            raise RuntimeError("Enhanced feature extraction requires RMVPE model file, but RMVPE_MODEL_PATH is missing or invalid. Please run backend/scripts/setup_rmvpe.py")
        if "ffmpeg" in missing:
            raise RuntimeError("Enhanced feature extraction requires ffmpeg, but executable is not available in PATH")

    def _get_whisperx_model(self):
        if self._whisperx_model is not None:
            return self._whisperx_model

        whisperx = self._get_whisperx_runtime()
        model_name = os.environ.get("WHISPERX_MODEL_SIZE") or os.environ.get("WHISPER_MODEL_SIZE") or ("small" if self.device == "cuda" else "base")
        compute_type = os.environ.get("WHISPERX_COMPUTE_TYPE") or ("float16" if self.device == "cuda" else "int8")
        logger.info("Using WhisperX alignment pipeline")
        self._whisperx_model = whisperx.load_model(model_name, self.device, compute_type=compute_type)
        return self._whisperx_model

    def _get_whisperx_align_model(self, language_code: str):
        key = (language_code, self.device)
        if key in self._whisperx_align_cache:
            return self._whisperx_align_cache[key]

        whisperx = self._get_whisperx_runtime()
        align_model = whisperx.load_align_model(language_code=language_code, device=self.device)
        self._whisperx_align_cache[key] = align_model
        return align_model

    def _build_asr_waveform(self, y: np.ndarray, sr: int, target_sr: int = 16000) -> np.ndarray:
        if sr != target_sr:
            return librosa.resample(y, orig_sr=sr, target_sr=target_sr)
        return y

    def _convert_alignment_entries_to_char_spans(
        self,
        segments: list[dict],
        transcript_hint: str | None = None,
    ) -> list[dict]:
        import re

        char_spans: list[dict] = []
        for seg in segments:
            chars = seg.get("chars") or []
            for char_info in chars:
                text = re.sub(r"[^\u4e00-\u9fa5]", "", str(char_info.get("char", "")))
                start = char_info.get("start")
                end = char_info.get("end")
                if text and start is not None and end is not None and end > start:
                    char_spans.append({"text": text, "start": float(start), "end": float(end)})

        if char_spans:
            return char_spans

        for seg in segments:
            words = seg.get("words") or []
            for word in words:
                text_clean = re.sub(r"[^\u4e00-\u9fa5]", "", str(word.get("word", "")))
                start = word.get("start")
                end = word.get("end")
                if not text_clean or start is None or end is None or end <= start:
                    continue
                char_dur = (float(end) - float(start)) / len(text_clean)
                for idx, char in enumerate(text_clean):
                    char_spans.append({
                        "text": char,
                        "start": float(start) + idx * char_dur,
                        "end": float(start) + (idx + 1) * char_dur,
                    })

        if char_spans:
            return char_spans

        if transcript_hint:
            text_clean = re.sub(r"[^\u4e00-\u9fa5]", "", transcript_hint)
            if text_clean and segments:
                seg_start = float(segments[0].get("start", 0.0))
                seg_end = float(segments[-1].get("end", seg_start))
                if seg_end > seg_start:
                    char_dur = (seg_end - seg_start) / len(text_clean)
                    return [
                        {"text": char, "start": seg_start + idx * char_dur, "end": seg_start + (idx + 1) * char_dur}
                        for idx, char in enumerate(text_clean)
                    ]

        return []

    def _transcribe_with_plain_whisper(
        self,
        audio_path: str,
        language: str = "zh",
        transcript_hint: str | None = None,
    ) -> list[dict]:
        import re

        logger.info("Falling back to plain Whisper timestamps")
        model = self._get_whisper_model(self.device)
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        y_16k = self._build_asr_waveform(y, sr, target_sr=16000)
        res = model.transcribe(y_16k, language=language, word_timestamps=True)
        words_info: list[dict] = []

        if transcript_hint and transcript_hint.strip():
            hint_text = re.sub(r"[^\u4e00-\u9fa5]", "", transcript_hint)
            if hint_text:
                duration = len(y) / max(sr, 1)
                char_dur = duration / len(hint_text)
                return [
                    {"text": char, "start": idx * char_dur, "end": (idx + 1) * char_dur}
                    for idx, char in enumerate(hint_text)
                ]

        for segment in res.get("segments", []):
            for word_dict in segment.get("words", []):
                text_clean = re.sub(r"[^\u4e00-\u9fa5]", "", word_dict["word"])
                if text_clean:
                    char_dur = (word_dict["end"] - word_dict["start"]) / len(text_clean)
                    for i, char in enumerate(text_clean):
                        start_t = word_dict["start"] + i * char_dur
                        end_t = start_t + char_dur
                        words_info.append({"text": char, "start": float(start_t), "end": float(end_t)})
        return words_info

    def _transcribe_and_align_with_whisperx(
        self,
        audio_path: str,
        language: str = "zh",
        transcript_hint: str | None = None,
        strict: bool = False,
    ) -> list[dict]:
        try:
            whisperx = self._get_whisperx_runtime()
            model = self._get_whisperx_model()
            audio = whisperx.load_audio(audio_path)
            result = model.transcribe(audio, batch_size=4, language=language)
            align_language = result.get("language") or language
            align_model, metadata = self._get_whisperx_align_model(align_language)

            if transcript_hint and transcript_hint.strip():
                duration = librosa.get_duration(path=audio_path)
                segments_to_align = [{"text": transcript_hint.strip(), "start": 0.0, "end": duration}]
            else:
                segments_to_align = result.get("segments", [])

            aligned = whisperx.align(
                segments_to_align,
                align_model,
                metadata,
                audio,
                self.device,
                return_char_alignments=True,
            )
            char_spans = self._convert_alignment_entries_to_char_spans(aligned.get("segments", []), transcript_hint=transcript_hint)
            if char_spans:
                return char_spans
            raise RuntimeError("WhisperX alignment returned no usable char spans")
        except Exception as e:
            if strict:
                if self._is_whisperx_abi_conflict_error(e):
                    raise RuntimeError(
                        self._format_whisperx_runtime_conflict_message(
                            np.__version__,
                            self._is_distribution_installed("tensorflow", "tensorflow-cpu"),
                            self._is_distribution_installed("ml-dtypes", "ml_dtypes"),
                            str(e),
                        )
                    ) from e
                raise RuntimeError(f"Enhanced WhisperX alignment failed: {e}") from e
            logger.warning("Falling back to plain Whisper timestamps: %s", e)
            return self._transcribe_with_plain_whisper(audio_path, language=language, transcript_hint=transcript_hint)

    def _get_pitch_backend(self) -> str:
        backend = (os.environ.get("PITCH_BACKEND") or "parselmouth").strip().lower()
        if backend == "rmvpe" and not USE_EXPERIMENTAL_RMVPE:
            logger.info("RMVPE pitch backend disabled by rollback defaults; using Parselmouth")
            return "parselmouth"
        return backend

    def _load_rmvpe_model(self):
        if self._rmvpe_model is not None:
            return self._rmvpe_model

        self._ensure_rmvpe_import_path()
        from rmvpe import RMVPE

        candidates = self._get_rmvpe_model_candidates()
        rmvpe_model_path = next((path for path in candidates if path and os.path.exists(path)), None)
        if not rmvpe_model_path:
            raise FileNotFoundError(f"RMVPE model not found: {rmvpe_model_path}")

        self._rmvpe_model = RMVPE(
            rmvpe_model_path,
            is_half=self.device == "cuda",
            device=self.device,
        )
        return self._rmvpe_model

    def _extract_pitch_with_parselmouth(self, audio_path: str) -> dict:
        import parselmouth

        logger.info("Fallback to Parselmouth pitch extraction")
        snd = parselmouth.Sound(audio_path)
        pitch = snd.to_pitch(time_step=0.01, pitch_floor=75, pitch_ceiling=1000)
        total_duration = snd.get_total_duration()
        times = np.arange(0, total_duration, 0.01)
        f0 = np.array([pitch.get_value_at_time(t) for t in times], dtype=np.float32)
        midi = librosa.hz_to_midi(np.where(f0 > 0, f0, np.nan))
        return {"times": times, "f0": f0, "midi": midi}

    def _extract_pitch_with_rmvpe(self, audio_path: str, sr: int | None = None) -> dict:
        logger.info("Using RMVPE pitch extraction")
        model = self._load_rmvpe_model()
        target_sr = 16000 if sr is None else sr
        y, audio_sr = librosa.load(audio_path, sr=target_sr, mono=True)
        if audio_sr != target_sr:
            y = librosa.resample(y, orig_sr=audio_sr, target_sr=target_sr)
            audio_sr = target_sr
        f0 = np.asarray(model.infer_from_audio(y, thred=0.03), dtype=np.float32)
        frame_hop = 0.01
        times = np.arange(len(f0), dtype=np.float32) * frame_hop
        midi = librosa.hz_to_midi(np.where(f0 > 0, f0, np.nan))
        return {"times": times, "f0": f0, "midi": midi}

    def _extract_pitch_backend(self, audio_path: str, strict: bool = False) -> dict:
        backend = self._get_pitch_backend()
        if backend == "parselmouth":
            return self._extract_pitch_with_parselmouth(audio_path)
        try:
            return self._extract_pitch_with_rmvpe(audio_path, sr=16000)
        except Exception as e:
            if strict:
                raise RuntimeError(f"Enhanced RMVPE pitch extraction failed: {e}") from e
            logger.warning("Fallback to Parselmouth pitch extraction: %s", e)
            return self._extract_pitch_with_parselmouth(audio_path)

    def _should_run_demucs(self, audio_path: str, is_vocal_only: bool = False) -> bool:
        if is_vocal_only:
            logger.info("Skip Demucs: input marked as vocal-only")
            return False

        basename = os.path.basename(audio_path).lower()
        vocal_markers = ("vocals", "acapella", "dry", "gtsinger_src", "vocal_only")
        if any(marker in basename for marker in vocal_markers):
            logger.info("Skip Demucs: filename suggests vocal-only input")
            return False

        logger.info("Run Demucs: input may contain accompaniment")
        return True

    def _prepare_reference_audio(
        self,
        audio_path: str,
        work_dir: str | None = None,
        is_vocal_only: bool = False,
    ) -> str:
        if not self._should_run_demucs(audio_path, is_vocal_only=is_vocal_only):
            return audio_path

        target_dir = work_dir or os.path.join(os.path.dirname(audio_path), "separated")
        try:
            return AudioProcessor.separate_vocals(audio_path, target_dir)
        except Exception as e:
            logger.warning("Demucs preparation failed, using original audio instead: %s", e)
            return audio_path

    def _segment_audio_for_feature_extraction(self, y: np.ndarray, sr: int) -> list[tuple[float, float]]:
        total_dur = len(y) / max(sr, 1)
        if total_dur <= 0:
            return []

        min_seg = 1.0
        max_seg = 6.0
        pad = 0.10
        join_gap = 0.10

        intervals = librosa.effects.split(y, top_db=25, frame_length=2048, hop_length=512)
        if len(intervals) == 0:
            return [(0.0, total_dur)]

        voiced_spans: list[tuple[float, float]] = []
        for start, end in intervals:
            s = max(0.0, start / sr - pad)
            e = min(total_dur, end / sr + pad)
            if e - s > 0:
                voiced_spans.append((s, e))

        merged: list[list[float]] = []
        for start, end in voiced_spans:
            if not merged:
                merged.append([start, end])
                continue
            prev_start, prev_end = merged[-1]
            if start - prev_end <= join_gap or (prev_end - prev_start) < min_seg:
                merged[-1][1] = max(prev_end, end)
            else:
                merged.append([start, end])

        segmented: list[tuple[float, float]] = []
        for start, end in merged:
            span = end - start
            if span <= max_seg:
                segmented.append((start, end))
                continue

            cursor = start
            while cursor < end:
                next_end = min(cursor + max_seg, end)
                segmented.append((cursor, next_end))
                cursor = next_end

        refined: list[list[float]] = []
        for start, end in segmented:
            if not refined:
                refined.append([start, end])
                continue
            prev_start, prev_end = refined[-1]
            current_dur = end - start
            if current_dur < min_seg and start - prev_end <= 0.25 and (end - prev_start) <= max_seg:
                refined[-1][1] = end
            else:
                refined.append([start, end])

        return [(round(start, 3), round(end, 3)) for start, end in refined if (end - start) >= min_seg or len(refined) == 1]

    def _merge_micro_segments(
        self,
        ph_seq: list[str],
        note_seq: list[int],
        dur_seq: list[float],
        type_seq: list[int],
        min_merge_dur: float = 0.12,
        return_count: bool = False,
    ):
        current_ph = ph_seq.copy()
        current_note = note_seq.copy()
        current_dur = dur_seq.copy()
        current_type = type_seq.copy()
        total_merged_count = 0
        
        max_iterations = 3
        for _ in range(max_iterations):
            merged_ph: list[str] = []
            merged_note: list[int] = []
            merged_dur: list[float] = []
            merged_type: list[int] = []
            merged_count = 0

            idx = 0
            while idx < len(current_ph):
                ph = current_ph[idx]
                note = current_note[idx]
                dur = current_dur[idx]
                note_type = current_type[idx]

                # 规则 D: 处理微小的 _NONE (中间静音)
                if (
                    ph == "_NONE"
                    and dur < min_merge_dur
                    and merged_ph
                    and merged_ph[-1] != "_NONE"
                    and idx + 1 < len(current_ph)
                    and current_ph[idx + 1] != "_NONE"
                ):
                    # 如果两边的音高相近，则合并中间的短静音
                    if abs(merged_note[-1] - current_note[idx + 1]) <= 2:
                        merged_dur[-1] += dur
                        merged_count += 1
                        idx += 1
                        continue

                # 规则 B & C: 连续相似音高的微小 token 合并
                if merged_ph and ph != "_NONE" and merged_ph[-1] != "_NONE":
                    same_pitch_family = abs(merged_note[-1] - note) <= 1
                    same_phone_family = (merged_ph[-1] == ph)

                    if (dur < min_merge_dur or merged_dur[-1] < min_merge_dur) and (same_pitch_family or same_phone_family or note_type == 3):
                        merged_dur[-1] += dur
                        if merged_type[-1] not in (2, 3):
                            merged_type[-1] = 2
                        merged_count += 1
                        idx += 1
                        continue

                merged_ph.append(ph)
                merged_note.append(note)
                merged_dur.append(dur)
                merged_type.append(note_type)
                idx += 1

            total_merged_count += merged_count
            if merged_count == 0:
                break
                
            current_ph = merged_ph
            current_note = merged_note
            current_dur = merged_dur
            current_type = merged_type

        if return_count:
            return current_ph, current_note, current_dur, current_type, total_merged_count
        return current_ph, current_note, current_dur, current_type

    def _compute_feature_quality_metrics(
        self,
        ph_seq: list[str],
        _note_seq: list[int],
        dur_seq: list[float],
        type_seq: list[int],
        sanitized_count: int = 0,
        merged_count: int = 0,
        pre_merge_token_count: int = 0,
    ) -> dict:
        token_count = len(ph_seq)
        rest_count = sum(1 for ph in ph_seq if ph == "_NONE")
        breathe_count = sum(1 for ph in ph_seq if ph == "breathe")
        slur_count = sum(1 for t in type_seq if t == 3)
        micro_token_count = sum(1 for d in dur_seq if d <= 0.08)
        return {
            "pre_merge_token_count": pre_merge_token_count,
            "post_merge_token_count": token_count,
            "token_count": token_count,
            "rest_count": rest_count,
            "rest_ratio": rest_count / token_count if token_count else 0.0,
            "breathe_count": breathe_count,
            "breathe_ratio": breathe_count / token_count if token_count else 0.0,
            "slur_count": slur_count,
            "slur_ratio": slur_count / token_count if token_count else 0.0,
            "micro_token_count": micro_token_count,
            "micro_token_ratio": micro_token_count / token_count if token_count else 0.0,
            "median_dur": float(np.median(dur_seq)) if dur_seq else 0.0,
            "min_dur": float(np.min(dur_seq)) if dur_seq else 0.0,
            "max_dur": float(np.max(dur_seq)) if dur_seq else 0.0,
            "total_duration": float(np.sum(dur_seq)) if dur_seq else 0.0,
            "sanitized_count": sanitized_count,
            "merged_count": merged_count,
        }

    def _log_feature_quality_metrics(self, metrics: dict) -> None:
        logger.info(
            "Feature quality metrics: pre_tokens=%d, post_tokens=%d, rest_ratio=%.3f, breathe_count=%d, breathe_ratio=%.3f, slur_ratio=%.3f, micro_ratio=%.3f, merged=%d, sanitized=%d",
            metrics.get("pre_merge_token_count", metrics.get("token_count", 0)),
            metrics.get("post_merge_token_count", metrics.get("token_count", 0)),
            metrics["rest_ratio"],
            metrics["breathe_count"],
            metrics["breathe_ratio"],
            metrics["slur_ratio"],
            metrics["micro_token_ratio"],
            metrics["merged_count"],
            metrics["sanitized_count"],
        )
        if metrics["rest_ratio"] > 0.15:
            logger.warning("Feature quality warning: rest_ratio too high: %.3f", metrics["rest_ratio"])
        if metrics["slur_ratio"] > 0.35:
            logger.warning("Feature quality warning: slur_ratio too high: %.3f", metrics["slur_ratio"])
        if metrics["micro_token_ratio"] > 0.25:
            logger.warning("Feature quality warning: too many micro tokens: %.3f", metrics["micro_token_ratio"])
        if metrics["breathe_count"] == 0 and metrics["total_duration"] > 8.0:
            logger.warning("Feature quality warning: No breathe tokens detected in a long singing phrase")

    def _evaluate_feature_quality_gate(self, metrics: dict) -> tuple[bool, str]:
        if metrics["micro_token_ratio"] > 0.25:
            return False, "Too many micro segments in extracted features"
        if metrics["rest_ratio"] > 0.18:
            return False, "Too many rest tokens in extracted features"
        if metrics["token_count"] < 5:
            return False, "Extracted feature sequence too short or invalid"
        return True, ""

    def _detect_and_insert_breathe_tokens(
        self,
        audio_path: str,
        ph_seq: list[str],
        note_seq: list[int],
        dur_seq: list[float],
        type_seq: list[int],
        _word_spans: list[dict] | None = None,
    ) -> tuple[list[str], list[int], list[float], list[int], int]:
        """
        breathe 与普通静音要分开。
        这里保守地只在短 gap 上判定：低能量但非绝对静音，且高频/过零率偏高时，保留为 breathe。
        """
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        out_ph, out_note, out_dur, out_type = [], [], [], []
        inserted = 0
        cursor_sec = 0.0

        for ph, note, dur, note_type in zip(ph_seq, note_seq, dur_seq, type_seq):
            start = int(cursor_sec * sr)
            end = int((cursor_sec + dur) * sr)
            seg = y[start:end] if end > start else np.array([], dtype=np.float32)
            cursor_sec += dur

            if ph == "_NONE" and 0.05 <= dur <= 0.30 and seg.size >= 256:
                rms = float(np.sqrt(np.mean(np.square(seg))) + 1e-8)
                zcr = float(np.mean(librosa.feature.zero_crossing_rate(seg, frame_length=min(1024, len(seg)), hop_length=max(1, min(256, len(seg)//4)))[0]))
                centroid = float(np.mean(librosa.feature.spectral_centroid(y=seg, sr=sr)[0]))

                if 0.001 <= rms <= 0.08 and zcr >= 0.08 and centroid >= 1800:
                    out_ph.append("breathe")
                    out_note.append(0)
                    out_dur.append(dur)
                    out_type.append(1)
                    inserted += 1
                    continue

            out_ph.append(ph)
            out_note.append(note)
            out_dur.append(dur)
            out_type.append(note_type)

        return out_ph, out_note, out_dur, out_type, inserted

    def process_task(
        self,
        task_id: str,
        text_prompt: str,
        style_strength: float,
        ref_audio_path: str,
        output_path: str,
        score_payload: dict | None = None,
        is_vocal_only: bool = False,
    ):
        task = self._tasks[task_id]

        if score_payload:
            seq_ph, seq_note, seq_dur, seq_type = self._sanitize_feature_sequences(
                score_payload.get("ph", []),
                score_payload.get("note", []),
                score_payload.get("note_dur", []),
                score_payload.get("note_type", []),
            )
            gate_metrics = self._compute_feature_quality_metrics(seq_ph, seq_note, seq_dur, seq_type)
            allow_generation, quality_reason = self._evaluate_feature_quality_gate(gate_metrics)
            if not allow_generation:
                logger.warning("Quality gate soft warning during task processing: %s", quality_reason)

        if self._should_run_demucs(ref_audio_path, is_vocal_only=is_vocal_only):
            task.status = "separating_vocals"
            task.message = "正在分离人声和伴奏..."
            ref_audio_path = self._prepare_reference_audio(
                ref_audio_path,
                work_dir=os.path.join(os.path.dirname(output_path), "separated"),
                is_vocal_only=is_vocal_only,
            )
        else:
            task.status = "running"
            task.message = "输入已是纯人声，跳过分离"
        
        # 2. 推理阶段
        task.status = "running"
        task.message = "正在执行StyleSinger推理"
        try:
            self.synthesize(
                text_prompt=text_prompt,
                style_strength=style_strength,
                ref_audio_path=ref_audio_path,
                output_path=output_path,
                score_payload=score_payload,
            )
            task.status = "completed"
            task.message = "转换完成"
            task.output_path = output_path
        except Exception as e:
            task.status = "failed"
            task.message = "转换失败"
            task.error = f"{e}\n{traceback.format_exc()}"

    def synthesize(
        self,
        text_prompt: str,
        style_strength: float,
        ref_audio_path: str,
        output_path: str,
        score_payload: dict | None = None,
    ):
        # 确保在使用模型前加载模型并初始化 CUDA
        # 注意：这里如果抛出 RuntimeError 304，说明当前进程的 CUDA 环境已经被破坏
        # 必须确保任何使用了 torch/whisper 的模块在导入和运行前都做好了进程隔离
        # 强制在当前进程初始化 CUDA 以测试其健康状态
        try:
            import torch
            if torch.cuda.is_available():
                # 先执行一次小张量的复制来验证 CUDA 是否存活
                torch.zeros(1).cuda()
        except Exception as e:
            logger.error(f"CUDA initialization failed early: {e}")
            # 尝试通过环境变量强制重置或者直接崩溃
            raise RuntimeError(f"CUDA broken before model init: {e}")
        self._init_model()
        
        if not os.path.exists(ref_audio_path):
            raise FileNotFoundError(f"Reference audio not found: {ref_audio_path}")

        profile = self._profile_from_prompt(text_prompt)

        # 检查是否是长音频（整首歌级别），如果是，则进行分段处理
        duration = librosa.get_duration(path=ref_audio_path)
        if duration > 30: # 超过30秒认为是长音频
            return self._synthesize_long_audio(text_prompt, style_strength, ref_audio_path, output_path, score_payload)

        inp = self._build_infer_input(
            ref_audio_path=ref_audio_path,
            profile=profile,
            style_strength=style_strength,
            score_payload=score_payload,
        )
        current_cwd = os.getcwd()
        try:
            os.chdir(STYLESINGER_ROOT)
            wav = self.infer_ins.infer_once(inp)
            wav = self._apply_prompt_post_style(wav, hparams["audio_sample_rate"], text_prompt, style_strength)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            save_wav(wav, output_path, hparams["audio_sample_rate"])
            return output_path
        finally:
            os.chdir(current_cwd)

    def _extract_score_from_audio(self, audio_path: str, _existing_payload: dict | None) -> dict:
        """内部特征提取，适配现有流程（如有源音频）"""
        import subprocess
        import sys
        import json
        import os
        
        script_path = audio_path + "_extract.py"
        with open(script_path, "w") as f:
            f.write(f"""
import sys
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
# 获取 backend 的根目录
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, backend_dir)
from app.models_svc.stylesinger_wrapper import StyleSingerService
svc = StyleSingerService()
features = svc.extract_features('{audio_path}')
import json
print("###JSON_START###")
print(json.dumps(features))
print("###JSON_END###")
""")
        
        # 使用独立的进程执行，避免干扰当前进程的 CUDA 状态
        import shlex
        import os
        import subprocess
        cmd = f"CUDA_VISIBLE_DEVICES='' {sys.executable} {shlex.quote(script_path)}"
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        stdout, stderr = proc.communicate()
        
        if os.path.exists(script_path):
            os.remove(script_path)
            
        if proc.returncode != 0:
            raise RuntimeError(f"提取特征失败: {stderr.decode('utf-8')}")
            
        try:
            json_str = stdout.decode('utf-8').split("###JSON_START###")[1].split("###JSON_END###")[0].strip()
            return json.loads(json_str)
        except Exception:
            raise RuntimeError(f"无法解析特征数据: {stdout.decode('utf-8')}")

    def extract_features(
        self,
        audio_path: str,
        prompt_text: str = "",
        is_vocal_only: bool = False,
        transcript_hint: str | None = None,
    ) -> dict:
        """
        面向中文歌曲的 4D 提取链：
        - 字级时间 -> G2P(initial/final) -> 音素级 4D
        - final 承载主音与拖腔，slur 优先作用在 final
        - gap 明确区分 breathe 与 _NONE
        """

        logger.info(
            "extract_features received prompt_text='%s'. prompt_text is reserved for compatibility but no longer scales extracted duration.",
            prompt_text,
        )
        feature_mode = self._get_feature_extraction_mode(is_vocal_only=is_vocal_only, lyrics=transcript_hint or "")
        strict_enhanced = feature_mode == "enhanced"
        if strict_enhanced:
            self._validate_enhanced_feature_stack()

        prepared_audio_path = self._prepare_reference_audio(
            audio_path,
            work_dir=os.path.join(os.path.dirname(audio_path), "separated_features"),
            is_vocal_only=is_vocal_only,
        )

        y, sr = librosa.load(prepared_audio_path, sr=None, mono=True)
        total_duration = len(y) / max(sr, 1)
        if strict_enhanced and USE_AGGRESSIVE_SEGMENT:
            phrase_spans = self._segment_audio_for_feature_extraction(y, sr)
            if not phrase_spans:
                phrase_spans = [(0.0, total_duration)]
            logger.info("Segmented audio into %d phrase(s) for feature extraction", len(phrase_spans))
        else:
            phrase_spans = [(0.0, total_duration)] if total_duration > 0 else []
            logger.info("Using simple single-pass feature extraction over %.3fs audio", total_duration)

        words_info = []
        use_transcript_hint = bool(transcript_hint and transcript_hint.strip())

        for seg_start, seg_end in phrase_spans:
            start_sample = int(seg_start * sr)
            end_sample = int(seg_end * sr)
            seg_y = y[start_sample:end_sample]
            if seg_y.size == 0:
                continue

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                seg_path = tmp_file.name
            try:
                sf.write(seg_path, seg_y, sr)
                if strict_enhanced and USE_EXPERIMENTAL_ALIGNMENT:
                    aligned = self._transcribe_and_align_with_whisperx(
                        seg_path,
                        language="zh",
                        transcript_hint=transcript_hint if use_transcript_hint else None,
                        strict=True,
                    )
                else:
                    aligned = self._transcribe_with_plain_whisper(
                        seg_path,
                        language="zh",
                        transcript_hint=transcript_hint if use_transcript_hint else None,
                    )
                for item in aligned:
                    words_info.append({
                        "char": item["text"],
                        "start": seg_start + float(item["start"]),
                        "end": seg_start + float(item["end"]),
                    })
            finally:
                if os.path.exists(seg_path):
                    os.remove(seg_path)

        words_info = [w for w in words_info if w["end"] > w["start"]]
        words_info.sort(key=lambda item: item["start"])
        if not words_info and transcript_hint and transcript_hint.strip():
            raw_chars = [ch for ch in transcript_hint.strip() if "\u4e00" <= ch <= "\u9fff"]
            if raw_chars:
                per_dur = total_duration / max(1, len(raw_chars))
                words_info = [
                    {
                        "char": ch,
                        "start": idx * per_dur,
                        "end": min(total_duration, (idx + 1) * per_dur),
                    }
                    for idx, ch in enumerate(raw_chars)
                ]

        lyric_text = "".join(str(item["char"]) for item in words_info)
        g2p_entries = self._g2p_chinese_to_stylesinger_phones(lyric_text)
        if len(g2p_entries) != len(words_info):
            logger.warning(
                "G2P length mismatch: words=%d, g2p=%d. Fallback to per-char conversion.",
                len(words_info),
                len(g2p_entries),
            )
            g2p_entries = []
            for item in words_info:
                single = self._g2p_chinese_to_stylesinger_phones(str(item["char"]))
                g2p_entries.append(single[0] if single else {
                    "char": item["char"],
                    "initial": "",
                    "final": "a" if "a" in self._stylesinger_phone_set else "",
                    "phones": ["a"] if "a" in self._stylesinger_phone_set else [],
                    "char_index": len(g2p_entries),
                    "normal_py": "",
                })

        if strict_enhanced and USE_EXPERIMENTAL_RMVPE:
            pitch_result = self._extract_pitch_backend(prepared_audio_path, strict=True)
        else:
            pitch_result = self._extract_pitch_with_parselmouth(prepared_audio_path)
        times_array = np.asarray(pitch_result["times"], dtype=np.float32)
        raw_f0_values = np.asarray(pitch_result["f0"], dtype=np.float32)

        def _get_midi_sequence_for_interval(start_t: float, end_t: float) -> list[int]:
            mask = (times_array >= start_t) & (times_array < end_t)
            freqs = raw_f0_values[mask]
            valid_mask = (~np.isnan(freqs)) & (freqs > 0)
            valid_freqs = freqs[valid_mask]

            if len(valid_freqs) == 0:
                return []

            if len(valid_freqs) >= 4:
                q1, q3 = np.percentile(valid_freqs, [25, 75])
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                filtered_freqs = valid_freqs[(valid_freqs >= lower_bound) & (valid_freqs <= upper_bound)]
                if len(filtered_freqs) == 0:
                    filtered_freqs = valid_freqs
            else:
                filtered_freqs = valid_freqs

            from scipy.signal import medfilt
            kernel_size = min(5, len(filtered_freqs))
            if kernel_size % 2 == 0:
                kernel_size -= 1
            if kernel_size < 3:
                smoothed_freqs = filtered_freqs
            else:
                smoothed_freqs = medfilt(filtered_freqs, kernel_size=kernel_size)

            midi_seq = np.round(librosa.hz_to_midi(smoothed_freqs)).astype(int).tolist()
            return [m for m in midi_seq if m > 0]

        # --- 5. 组装四维特征序列 ---
        final_ph: list[str] = []
        final_note: list[int] = []
        final_dur: list[float] = []
        final_type: list[int] = []
        last_end = 0.0
        rms_full = librosa.feature.rms(y=y, frame_length=256, hop_length=64, center=False)[0]
        prev_voiced_note = 0

        for idx, w_info in enumerate(words_info):
            char = w_info["char"]
            start_t = w_info["start"]
            end_t = w_info["end"]
            g2p_entry = g2p_entries[idx] if idx < len(g2p_entries) else {
                "char": char,
                "initial": "",
                "final": "a" if "a" in self._stylesinger_phone_set else "",
                "phones": ["a"] if "a" in self._stylesinger_phone_set else [],
                "normal_py": "",
            }

            gap = start_t - last_end
            if gap > 0.05:
                gap_token = self._classify_gap_token(y, sr, last_end, start_t)
                final_ph.append(gap_token)
                final_note.append(0)
                final_dur.append(round(gap, 3))
                final_type.append(1)

            char_total_dur = max(0.06, end_t - start_t)
            start_frame = int(start_t * sr / 64)
            end_frame = int(end_t * sr / 64)
            char_rms = rms_full[start_frame:end_frame]
            energy_rise_ratio = None
            if len(char_rms) > 0:
                rms_max = np.max(char_rms)
                threshold = rms_max * 0.25
                above_threshold_indices = np.where(char_rms > threshold)[0]
                if len(above_threshold_indices) > 0:
                    split_frame = above_threshold_indices[0]
                    energy_rise_ratio = split_frame / max(1, len(char_rms))

            initial_phone = self._normalize_special_tokens(str(g2p_entry.get("initial", "")))
            final_phone = self._normalize_special_tokens(str(g2p_entry.get("final", "")))
            if initial_phone and initial_phone not in self._stylesinger_phone_set:
                logger.warning("Drop illegal initial phone '%s' for char '%s'", initial_phone, char)
                initial_phone = ""
            if final_phone and final_phone not in self._stylesinger_phone_set:
                logger.warning("Drop illegal final phone '%s' for char '%s'", final_phone, char)
                final_phone = ""

            has_initial = bool(initial_phone)
            ins_dur, fns_dur = self._split_initial_final_duration(
                char_total_dur,
                has_initial=has_initial,
                energy_rise_ratio=energy_rise_ratio,
            )
            if not has_initial:
                fns_dur = char_total_dur

            char_midi_seq = _get_midi_sequence_for_interval(start_t, end_t)
            char_main_note = int(np.median(char_midi_seq)) if char_midi_seq else 0
            if char_main_note <= 0 and prev_voiced_note > 0:
                char_main_note = prev_voiced_note

            melisma_allowed = char not in LIGHT_FUNCTION_CHARS
            final_start_t = start_t + ins_dur if has_initial else start_t
            final_midi_seq = _get_midi_sequence_for_interval(final_start_t, end_t)
            if not final_midi_seq and char_main_note > 0:
                final_midi_seq = [char_main_note]

            final_segments = self._detect_melisma_segments(final_midi_seq) if melisma_allowed else []
            if not final_segments:
                fallback_note = char_main_note if char_main_note > 0 else prev_voiced_note
                if fallback_note > 0:
                    final_segments = [(fallback_note, 1.0, 2)]

            char_notes: list[int] = []
            char_durs: list[float] = []
            char_types: list[int] = []

            if has_initial:
                initial_midi_seq = _get_midi_sequence_for_interval(start_t, start_t + ins_dur)
                initial_note = int(np.median(initial_midi_seq)) if initial_midi_seq else 0
                if initial_note <= 0 and final_segments:
                    initial_note = final_segments[0][0]
                if initial_note <= 0 and prev_voiced_note > 0:
                    initial_note = prev_voiced_note
                if initial_note > 0:
                    final_ph.append(initial_phone)
                    final_note.append(initial_note)
                    final_dur.append(round(ins_dur, 3))
                    final_type.append(2)
                    char_notes.append(initial_note)
                    char_durs.append(round(ins_dur, 3))
                    char_types.append(2)

            if final_phone and final_segments:
                for seg_idx, (note_val, ratio, _seg_type) in enumerate(final_segments):
                    seg_dur = max(0.05, fns_dur * ratio)
                    seg_note_type = 2 if seg_idx == 0 else 3
                    final_ph.append(final_phone)
                    final_note.append(int(note_val))
                    final_dur.append(round(seg_dur, 3))
                    final_type.append(seg_note_type)
                    char_notes.append(int(note_val))
                    char_durs.append(round(seg_dur, 3))
                    char_types.append(seg_note_type)
            else:
                final_ph.append("_NONE")
                final_note.append(0)
                final_dur.append(round(max(0.05, fns_dur), 3))
                final_type.append(1)
                char_notes.append(0)
                char_durs.append(round(max(0.05, fns_dur), 3))
                char_types.append(1)

            for note_val in char_notes:
                if note_val > 0:
                    prev_voiced_note = note_val

            logger.info(
                "Char '%s' -> initial=%s, final=%s, phones=%s, notes=%s, durs=%s, types=%s",
                char,
                initial_phone,
                final_phone,
                [p for p in [initial_phone, final_phone] if p],
                char_notes,
                char_durs,
                char_types,
            )

            last_end = end_t

        tail_gap = total_duration - last_end
        if tail_gap > 0.08:
            tail_token = self._classify_gap_token(y, sr, last_end, total_duration)
            final_ph.append(tail_token)
            final_note.append(0)
            final_dur.append(round(tail_gap, 3))
            final_type.append(1)
        elif not final_ph or final_ph[-1] not in {"_NONE", "breathe"}:
            final_ph.append("_NONE")
            final_note.append(0)
            final_dur.append(0.18)
            final_type.append(1)

        final_ph, final_note, final_dur, final_type = self._postprocess_4d_for_chinese_singing(
            final_ph,
            final_note,
            final_dur,
            final_type,
        )

        min_len = min(len(final_ph), len(final_note), len(final_dur), len(final_type))
        output_ph, output_note, output_dur, output_type, sanitized_count = self._sanitize_feature_sequences(
            final_ph[:min_len], final_note[:min_len], final_dur[:min_len], final_type[:min_len], return_count=True
        )
        pre_merge_token_count = len(output_ph)
        merged_count = 0
        breathe_count = 0

        if strict_enhanced and USE_ITERATIVE_MICRO_MERGE:
            output_ph, output_note, output_dur, output_type, merged_count = self._merge_micro_segments(
                output_ph, output_note, output_dur, output_type, return_count=True
            )
            output_ph, output_note, output_dur, output_type, sanitized_after_merge = self._sanitize_feature_sequences(
                output_ph, output_note, output_dur, output_type, return_count=True
            )
            sanitized_count += sanitized_after_merge

        if strict_enhanced and USE_BREATHE_INSERTION:
            output_ph, output_note, output_dur, output_type, breathe_count = self._detect_and_insert_breathe_tokens(
                prepared_audio_path,
                output_ph,
                output_note,
                output_dur,
                output_type,
                _word_spans=words_info,
            )
            output_ph, output_note, output_dur, output_type, sanitized_after_breathe = self._sanitize_feature_sequences(
                output_ph, output_note, output_dur, output_type, return_count=True
            )
            sanitized_count += sanitized_after_breathe

        metrics = self._compute_feature_quality_metrics(
            output_ph,
            output_note,
            output_dur,
            output_type,
            sanitized_count=sanitized_count,
            merged_count=merged_count,
            pre_merge_token_count=pre_merge_token_count,
        )
        metrics["breathe_count"] = max(metrics["breathe_count"], breathe_count)
        metrics["breathe_ratio"] = metrics["breathe_count"] / metrics["token_count"] if metrics["token_count"] else 0.0
        self._log_feature_quality_metrics(metrics)
        quality_ok, quality_reason = self._evaluate_feature_quality_gate(metrics)
        if quality_ok:
            logger.info("Feature quality soft gate passed")
        else:
            logger.warning("Feature quality soft gate warning: %s", quality_reason)
            if USE_HARD_QUALITY_GATE and strict_enhanced:
                logger.warning("Hard quality gate is enabled for enhanced mode")
        
        return {
            "ph": output_ph,
            "note": output_note,
            "note_dur": output_dur,
            "note_type": output_type,
            "quality_ok": quality_ok,
            "quality_reason": quality_reason,
            "metrics": metrics,
        }

    def _sanitize_feature_sequences(self, ph_seq: list, note_seq: list, dur_seq: list, type_seq: list, return_count: bool = False):
        """
        统一的契约守门员：清洗并修正所有输入的 4D 特征序列，确保输出绝对合法。
        """
        s_ph, s_note, s_dur, s_type = [], [], [], []
        min_len = min(len(ph_seq), len(note_seq), len(dur_seq), len(type_seq))
        sanitized_count = 0

        for i in range(min_len):
            p, n, d, t = ph_seq[i], note_seq[i], dur_seq[i], type_seq[i]
            p = self._normalize_special_tokens(str(p))
            if p not in self._stylesinger_phone_set and p not in {"_NONE", "breathe"}:
                logger.warning("Illegal phone '%s' detected in sanitize, convert to _NONE", p)
                p = "_NONE"
                n = 0
                t = 1

            if d <= 0:
                continue
            d = max(0.05, d)

            if p == "breathe":
                if not (n == 0 and t == 1):
                    sanitized_count += 1
                s_ph.append("breathe")
                s_note.append(0)
                s_dur.append(d)
                s_type.append(1)
                continue

            if p == "_NONE" or n <= 0 or t == 1:
                if not (p == "_NONE" and n == 0 and t == 1):
                    sanitized_count += 1
                s_ph.append("_NONE")
                s_note.append(0)
                s_dur.append(d)
                s_type.append(1)
                continue

            valid_type = t if t in (2, 3) else 2
            if valid_type == 3:
                # slur 必须依附于前一个“实际输出”的非休止 token。
                # 这里不再使用“是否曾出现过 lyric”的宽松条件，而是严格检查
                # 上一个已经写入输出序列的 token 是否为可承接 slur 的 lyric/slur。
                if not s_type or s_type[-1] not in (2, 3) or s_ph[-1] == "_NONE" or s_note[-1] <= 0:
                    valid_type = 2
                    sanitized_count += 1

            s_ph.append(p)
            s_note.append(n)
            s_dur.append(d)
            s_type.append(valid_type)

        if return_count:
            return s_ph, s_note, s_dur, s_type, sanitized_count
        return s_ph, s_note, s_dur, s_type

    def _synthesize_long_audio(self, text_prompt, style_strength, ref_audio_path, output_path, score_payload):
        # 简化的分段处理逻辑：将长音频视为多个片段的参考源
        # 在实际工程中，这里应该进行 VAD 切分或固定长度切分
        # 目前先通过调整全局时长对齐来模拟整曲转换
        profile = self._profile_from_prompt(text_prompt)
        inp = self._build_infer_input(
            ref_audio_path=ref_audio_path,
            profile=profile,
            style_strength=style_strength,
            score_payload=score_payload,
        )
        current_cwd = os.getcwd()
        try:
            os.chdir(STYLESINGER_ROOT)
            wav = self.infer_ins.infer_once(inp)
            wav = self._apply_prompt_post_style(wav, hparams["audio_sample_rate"], text_prompt, style_strength)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            save_wav(wav, output_path, hparams["audio_sample_rate"])
            return output_path
        finally:
            os.chdir(current_cwd)

    def _build_infer_input(
        self,
        ref_audio_path: str,
        profile: Dict[str, float],
        style_strength: float,
        score_payload: dict | None = None,
    ):
        base_note_dur = [0.41, 0.41, 0.41, 0.82, 0.82, 0.41, 0.41, 0.20, 0.20, 0.61, 0.82, 0.82, 0.32, 0.82, 0.82, 0.41, 0.41, 0.20, 0.20, 0.61, 0.61, 0.82, 0.82, 0.30, 0.82, 0.82, 0.61, 0.61, 0.61, 0.61, 0.33]
        has_full_score_payload = (
            score_payload
            and isinstance(score_payload.get("ph"), list) and len(score_payload.get("ph")) > 0
            and isinstance(score_payload.get("note"), list) and len(score_payload.get("note")) > 0
            and isinstance(score_payload.get("note_dur"), list) and len(score_payload.get("note_dur")) > 0
            and isinstance(score_payload.get("note_type"), list) and len(score_payload.get("note_type")) > 0
        )

        if has_full_score_payload:
            note_dur_scaled = [max(float(x), 0.05) for x in score_payload["note_dur"]]
        else:
            ref_dur = librosa.get_duration(path=ref_audio_path)
            base_total = sum(base_note_dur)
            target_scale = float(np.clip(ref_dur / max(base_total, 1e-4), 0.75, 2.4))
            style_scale = 1.0 + (profile["duration_scale"] - 1.0) * float(np.clip(style_strength, 0.0, 1.0))
            note_dur_scaled = [float(np.clip(d * target_scale * style_scale, 0.06, 1.8)) for d in base_note_dur]
        inp = {
            "name": "prompt_singer",
            "ph": ["zh", "i", "i", "d", "uan", "j", "in", "x", "iou", "uen", "sh", "i", "breathe", "b", "ing", "l", "ian", "l", "i", "sh", "uang", "zh", "i", "breathe", "n", "an", "j", "i", "t", "uo", "breathe"],
            "note": [59, 59, 61, 62, 62, 71, 71, 69, 69, 66, 64, 64, 0, 64, 64, 69, 69, 66, 66, 64, 64, 62, 62, 0, 59, 59, 66, 66, 61, 61, 0],
            "note_dur": note_dur_scaled,
            "note_type": [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1],
            "ref_audio": ref_audio_path,
        }
        if score_payload:
            ph_custom = score_payload.get("ph")
            if isinstance(ph_custom, list) and len(ph_custom) > 0:
                inp["ph"] = [str(x).strip() if str(x).strip() != "" else "_NONE" for x in ph_custom]
            note_custom = score_payload.get("note")
            if isinstance(note_custom, list) and len(note_custom) > 0:
                inp["note"] = [int(x) for x in note_custom]
            note_dur_custom = score_payload.get("note_dur")
            if isinstance(note_dur_custom, list) and len(note_dur_custom) > 0:
                inp["note_dur"] = [max(float(x), 0.05) for x in note_dur_custom]
            note_type_custom = score_payload.get("note_type")
            if isinstance(note_type_custom, list) and len(note_type_custom) > 0:
                inp["note_type"] = [int(x) for x in note_type_custom]
                
        # --- 统一校验外部输入 ---
        ph_len = len(inp["ph"])
        for key, default in [("note", 0), ("note_dur", 0.25), ("note_type", 1)]:
            if len(inp[key]) < ph_len:
                inp[key].extend([default] * (ph_len - len(inp[key])))
            elif len(inp[key]) > ph_len:
                inp[key] = inp[key][:ph_len]
                
        # 强制契约校验
        inp["ph"], inp["note"], inp["note_dur"], inp["note_type"] = self._sanitize_feature_sequences(
            inp["ph"], inp["note"], inp["note_dur"], inp["note_type"]
        )
                    
        return inp

    def _apply_prompt_post_style(self, wav: np.ndarray, sr: int, text_prompt: str, strength: float) -> np.ndarray:
        strength = float(np.clip(strength, 0.0, 1.0))
        profile = self._profile_from_prompt(text_prompt)
        if abs(profile["pitch"]) > 1e-4:
            wav = librosa.effects.pitch_shift(wav, sr=sr, n_steps=profile["pitch"] * strength)
        speed = 1.0 + (profile["speed"] - 1.0) * strength
        speed = float(np.clip(speed, 0.92, 1.08))
        if abs(speed - 1.0) > 1e-4:
            wav = librosa.effects.time_stretch(wav, rate=speed)
        wav = self._tilt_eq(wav, sr, profile["brightness"] * strength)
        if profile["sat"] > 0:
            drive = 1.0 + 8.0 * profile["sat"] * strength
            wav = np.tanh(drive * wav) / np.tanh(drive)
        if profile["reverb"] > 0:
            wav = self._simple_reverb(wav, sr, profile["reverb"] * strength)
        peak = np.max(np.abs(wav)) + 1e-8
        wav = wav / peak * 0.98
        return wav.astype(np.float32)

    def _profile_from_prompt(self, prompt: str):
        p = prompt.lower()
        profile = {"pitch": 0.0, "speed": 1.0, "brightness": 0.0, "sat": 0.0, "reverb": 0.0, "duration_scale": 1.0}
        
        # 增加“流行/抒情”风格，使其听起来更像正常歌曲
        if any(k in p for k in ["流行", "抒情", "华语", "通俗"]):
            profile.update({"pitch": 0.0, "speed": 1.0, "brightness": 0.1, "sat": 0.05, "reverb": 0.15, "duration_scale": 1.0})
        
        # 优化映射逻辑：增加更多描述性词汇，并微调参数使风格更明显
        if any(k in p for k in ["摇滚", "力量", "op", "动漫op", "爆发", "激昂", "热血", "重金属"]):
            profile.update({"pitch": 0.6, "speed": 1.12, "brightness": 0.35, "sat": 0.30, "reverb": 0.10, "duration_scale": 0.90})
        elif any(k in p for k in ["爵士", "忧伤", "气声", "蓝调", "感性", "深夜", "慵懒"]):
            profile.update({"pitch": -0.45, "speed": 0.88, "brightness": -0.20, "sat": 0.08, "reverb": 0.35, "duration_scale": 1.15})
        elif any(k in p for k in ["古风", "治愈", "清澈", "少年音", "空灵", "纯净", "民族"]):
            profile.update({"pitch": 0.25, "speed": 0.96, "brightness": 0.22, "sat": 0.03, "reverb": 0.28, "duration_scale": 1.05})
        elif any(k in p for k in ["r&b", "rb", "律动", "嘻哈", "说唱"]):
            profile.update({"pitch": -0.25, "speed": 0.92, "brightness": 0.10, "sat": 0.15, "reverb": 0.22, "duration_scale": 1.10})
        elif any(k in p for k in ["甜美", "可爱", "萌系", "二次元"]):
            profile.update({"pitch": 1.2, "speed": 1.05, "brightness": 0.40, "sat": 0.05, "reverb": 0.12, "duration_scale": 0.95})
        return profile

    def _tilt_eq(self, y: np.ndarray, sr: int, brightness: float) -> np.ndarray:
        brightness = float(np.clip(brightness, -0.5, 0.5))
        if abs(brightness) < 1e-5:
            return y
        b_l, a_l = signal.butter(2, 250 / (sr / 2), btype="low")
        b_h, a_h = signal.butter(2, 3200 / (sr / 2), btype="high")
        low = signal.lfilter(b_l, a_l, y)
        high = signal.lfilter(b_h, a_h, y)
        mid = y - low - high
        return low * (1.0 - 0.7 * brightness) + mid + high * (1.0 + 1.1 * brightness)

    def _simple_reverb(self, y: np.ndarray, sr: int, amount: float) -> np.ndarray:
        amount = float(np.clip(amount, 0.0, 0.5))
        if amount <= 1e-5:
            return y
        ir_len = int(sr * (0.2 + amount * 0.5))
        t = np.linspace(0.0, 1.0, ir_len, endpoint=False)
        ir = (np.random.randn(ir_len) * np.exp(-4.2 * t)).astype(np.float32)
        ir = ir / (np.max(np.abs(ir)) + 1e-8)
        wet = signal.fftconvolve(y, ir, mode="full")[: len(y)]
        return y * (1.0 - 0.4 * amount) + wet * (0.32 * amount)


stylesinger_service = StyleSingerService()
