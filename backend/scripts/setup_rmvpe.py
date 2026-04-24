import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlretrieve


BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = BASE_DIR / "backend"
THIRD_PARTY_DIR = BACKEND_DIR / "third_party"
RMVPE_DIR = THIRD_PARTY_DIR / "RMVPE"
RMVPE_MODEL_DIR = BACKEND_DIR / "models" / "rmvpe"
RMVPE_MODEL_PATH = RMVPE_MODEL_DIR / "rmvpe.pt"

RMVPE_REPO_URL = "https://github.com/xavriley/RMVPE.git"
RMVPE_PINNED_COMMIT = "37a4b6254c4fa6eb73898177aa4e70749eb665f3"
RMVPE_ZIP_URL = f"https://github.com/xavriley/RMVPE/archive/{RMVPE_PINNED_COMMIT}.zip"
RMVPE_MODEL_URL = "https://huggingface.co/xavriley/source_separation_mirror/resolve/main/rmvpe.pt"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=True,
    )


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _git_available() -> bool:
    return shutil.which("git") is not None


def _repo_looks_valid(repo_dir: Path) -> bool:
    return (repo_dir / "pyproject.toml").exists() and (repo_dir / "rmvpe" / "__init__.py").exists()


def _download_zip_fallback(repo_dir: Path) -> str:
    THIRD_PARTY_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rmvpe_zip_") as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        zip_path = tmp_dir_path / "rmvpe.zip"
        urlretrieve(RMVPE_ZIP_URL, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir_path)

        extracted_root = next(tmp_dir_path.glob("RMVPE-*"), None)
        if extracted_root is None:
            raise RuntimeError("RMVPE zip download succeeded but extracted directory was not found")

        if repo_dir.exists():
            shutil.rmtree(repo_dir)
        shutil.move(str(extracted_root), str(repo_dir))
    return "zip"


def ensure_vendored_repo(repo_dir: Path = RMVPE_DIR) -> str:
    THIRD_PARTY_DIR.mkdir(parents=True, exist_ok=True)

    if _repo_looks_valid(repo_dir):
        if (repo_dir / ".git").exists():
            try:
                _run(["git", "-C", str(repo_dir), "fetch", "--depth", "1", "origin", RMVPE_PINNED_COMMIT])
                _run(["git", "-C", str(repo_dir), "checkout", RMVPE_PINNED_COMMIT])
                return "git"
            except Exception:
                # Existing clone is still usable; continue with current checkout.
                return "git"
        return "vendored"

    if repo_dir.exists():
        shutil.rmtree(repo_dir)

    if _git_available():
        try:
            _run(["git", "clone", RMVPE_REPO_URL, str(repo_dir)])
            _run(["git", "-C", str(repo_dir), "checkout", RMVPE_PINNED_COMMIT])
            return "git"
        except Exception as exc:
            if repo_dir.exists():
                shutil.rmtree(repo_dir)
            git_error = exc
        else:
            git_error = None
    else:
        git_error = RuntimeError("git executable is not available")

    try:
        return _download_zip_fallback(repo_dir)
    except Exception as zip_exc:
        raise RuntimeError(f"RMVPE source download failed: git={git_error}; zip={zip_exc}") from zip_exc


def install_editable(repo_dir: Path = RMVPE_DIR) -> str:
    _run([sys.executable, "-m", "pip", "install", "-e", str(repo_dir)])
    return "editable"


def ensure_importable(repo_dir: Path = RMVPE_DIR) -> tuple[bool, str, str]:
    if str(repo_dir) not in sys.path:
        sys.path.insert(0, str(repo_dir))
    importlib.invalidate_caches()
    module = importlib.import_module("rmvpe")
    module_path = os.path.abspath(getattr(module, "__file__", ""))
    source = "vendored" if str(repo_dir.resolve()) in module_path else "site_packages"
    return True, source, module_path


def download_model(model_path: Path = RMVPE_MODEL_PATH) -> str:
    _ensure_parent(model_path)
    if model_path.exists() and os.access(model_path, os.R_OK):
        return str(model_path)
    urlretrieve(RMVPE_MODEL_URL, model_path)
    if not model_path.exists():
        raise RuntimeError(f"RMVPE model download failed: {model_path}")
    return str(model_path)


def validate_runtime(model_path: str) -> dict:
    from rmvpe import RMVPE

    model = RMVPE(model_path=model_path, is_half=False, device="cpu")
    return {
        "class_name": model.__class__.__name__,
        "load_ok": True,
    }


def setup_rmvpe() -> dict:
    result = {
        "repo_url": RMVPE_REPO_URL,
        "repo_commit": RMVPE_PINNED_COMMIT,
        "repo_dir": str(RMVPE_DIR),
        "rmvpe_module_ready": False,
        "rmvpe_model_ready": False,
        "rmvpe_model_path": str(RMVPE_MODEL_PATH),
        "rmvpe_module_source": "missing",
        "rmvpe_module_path": "",
        "install_mode": "unknown",
        "download_mode": "unknown",
        "runtime_validated": False,
    }

    download_mode = ensure_vendored_repo(RMVPE_DIR)
    result["download_mode"] = download_mode

    install_error = None
    try:
        result["install_mode"] = install_editable(RMVPE_DIR)
    except Exception as exc:
        install_error = exc
        result["install_mode"] = "vendored_path"

    ready, source, module_path = ensure_importable(RMVPE_DIR)
    result["rmvpe_module_ready"] = ready
    result["rmvpe_module_source"] = source
    result["rmvpe_module_path"] = module_path

    if not ready:
        raise RuntimeError(f"RMVPE import failed after setup. install_error={install_error}")

    result["rmvpe_model_path"] = download_model(RMVPE_MODEL_PATH)
    result["rmvpe_model_ready"] = True

    runtime = validate_runtime(result["rmvpe_model_path"])
    result["runtime_validated"] = runtime["load_ok"]
    return result


def main() -> int:
    try:
        result = setup_rmvpe()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"rmvpe_module_ready={str(result['rmvpe_module_ready']).lower()}")
        print(f"rmvpe_model_ready={str(result['rmvpe_model_ready']).lower()}")
        print(f"rmvpe_model_path={result['rmvpe_model_path']}")
        return 0
    except Exception as exc:
        error = {
            "rmvpe_module_ready": False,
            "rmvpe_model_ready": False,
            "error": str(exc),
        }
        print(json.dumps(error, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
