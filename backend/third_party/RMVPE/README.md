# RMVPE

> [!WARNING]
> This repo is a vibe coded wrapper to allow easy pip installs. I haven't done any checks beyond basic functionality and this code should not be relied upon in public projects until a proper review and publication strategy have taken place. For the same reason, I haven't attempted to merge this upstream yet.

A pip-installable Python package for vocal pitch estimation in polyphonic music using the RMVPE (Robust Model for Vocal Pitch Estimation) deep learning model.

This is the PyTorch implementation of ["RMVPE: A Robust Model for Vocal Pitch Estimation in Polyphonic Music"](https://arxiv.org/abs/2306.15412v2).

## Features

- 🎵 Accurate pitch estimation for vocals in polyphonic music
- 🚀 Easy to use Python API
- 📦 Automatic model downloading from HuggingFace
- 🎯 Command-line interface for batch processing
- ⚡ GPU acceleration support
- 🔧 Half precision (FP16) support for faster inference

## Installation

### From source (for development)

```bash
# Clone the repository
git clone https://github.com/xavriley/RMVPE.git
cd RMVPE

# Install in editable mode
pip install -e .
```

### Dependencies

The package requires:
- Python >= 3.7
- PyTorch >= 1.7.0
- NumPy 1.26.4
- librosa
- tqdm >= 4.50.0

## Usage

### Python API

```python
import librosa
from rmvpe import RMVPE

# Initialize the model (automatically downloads on first use)
model = RMVPE()

# Load audio file (must be 16kHz sample rate)
audio, sr = librosa.load("audio.wav", sr=16000)

# Estimate pitch
f0 = model.infer_from_audio(audio, thred=0.03)

# f0 is a numpy array of F0 values in Hz
# Zero values indicate unvoiced frames
# Hop length is 160 samples (10ms at 16kHz)

print(f"Estimated {len(f0)} pitch frames")
```

### Advanced Usage

```python
from rmvpe import RMVPE

# Use custom model path
model = RMVPE(model_path="/path/to/custom/model.pt")

# Use GPU with half precision for faster inference
model = RMVPE(device="cuda", is_half=True)

# Adjust sensitivity threshold (lower = more sensitive)
f0 = model.infer_from_audio(audio, thred=0.01)
```

### Command-Line Interface

Process all audio files in a folder:

```bash
# Basic usage
rmvpe input_folder/ output_folder/

# Use custom model
rmvpe input_folder/ output_folder/ --model_path /path/to/model.pt

# Use GPU with half precision
rmvpe input_folder/ output_folder/ --device cuda --is_half

# Adjust sensitivity threshold
rmvpe input_folder/ output_folder/ --thred 0.05
```

The CLI will:
- Process all audio files (`.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a`) in the input folder
- Save pitch estimates as CSV files (time, frequency) in the output folder
- Skip files that have already been processed
- Show a progress bar during processing

### Output Format

The output is a NumPy array (or CSV file for CLI) containing F0 values:
- **F0 values**: Fundamental frequency in Hz
- **Zero values**: Indicate unvoiced/silent frames
- **Temporal resolution**: 10ms per frame (hop length = 160 samples at 16kHz)

Example CSV output:
```csv
time,frequency
0.000,0.0
0.010,0.0
0.020,220.5
0.030,221.2
...
```

## Model Details

- **Input**: Audio waveform at 16kHz
- **Output**: F0 contour with 10ms resolution
- **Architecture**: Deep U-Net with BiGRU
- **Model size**: ~85MB
- **Cache location**: `~/.cache/rmvpe/rmvpe.pt`

The model is automatically downloaded from HuggingFace on first use and cached locally.

## API Reference

### RMVPE Class

```python
class RMVPE(model_path=None, is_half=False, device=None)
```

**Parameters:**
- `model_path` (str, optional): Path to model weights. If None, downloads automatically.
- `is_half` (bool): Use FP16 precision. Default: False.
- `device` (str, optional): Device to use ('cuda' or 'cpu'). Default: auto-detect.

**Methods:**

#### `infer_from_audio(audio, thred=0.03)`

Estimate pitch from audio.

**Parameters:**
- `audio` (np.ndarray): Audio array at 16kHz, shape (samples,)
- `thred` (float): Threshold for voiced/unvoiced detection. Default: 0.03. Lower values are more sensitive.

**Returns:**
- `np.ndarray`: F0 array in Hz. Zero values indicate unvoiced frames.

## Training (Research Use)

This package focuses on inference only. For training code, please refer to the original research repository. The training scripts (`train.py`, `evaluate.py`) are included in the repository but not installed with the package.

## Citation

If you use RMVPE in your research, please cite:

```bibtex
@article{rmvpe2023,
  title={RMVPE: A Robust Model for Vocal Pitch Estimation in Polyphonic Music},
  author={},
  journal={arXiv preprint arXiv:2306.15412},
  year={2023}
}
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Original RMVPE paper and research
- HuggingFace for hosting the pre-trained model
- PyTorch and librosa communities
