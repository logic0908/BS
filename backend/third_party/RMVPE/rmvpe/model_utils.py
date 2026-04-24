"""Utilities for downloading and managing RMVPE models."""
import os
from pathlib import Path
from urllib.request import urlretrieve


def get_model_path(model_path=None):
    """
    Get the path to the RMVPE model, downloading it if necessary.
    
    Args:
        model_path: Optional path to a local model file. If None, will use cached model.
        
    Returns:
        Path to the model file.
    """
    if model_path is not None:
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}")
        return model_path
    
    # Use cached model
    cache_dir = Path.home() / ".cache" / "rmvpe"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_model_path = cache_dir / "rmvpe.pt"
    
    if not cached_model_path.exists():
        print("Downloading RMVPE model from HuggingFace...")
        # model_url = "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/rmvpe.pt"
        model_url = "https://huggingface.co/xavriley/source_separation_mirror/resolve/main/rmvpe.pt"
        
        def _progress_hook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, downloaded * 100 / total_size)
                print(f"\rDownloading: {percent:.1f}% ({downloaded}/{total_size} bytes)", end='')
        
        urlretrieve(model_url, cached_model_path, reporthook=_progress_hook)
        print("\nModel downloaded successfully!")
    
    return str(cached_model_path)

