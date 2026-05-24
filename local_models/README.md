# Local Models

This directory is intentionally excluded from Git.

Keep local model weights, text-encoder caches, and preset-specific asset files here, for example:

- `local_models/sovits-final/final_primary/`
- `local_models/sovits-final/final_male_powerful/`
- `local_models/sovits-final/final_male_youth/`
- `local_models/text-encoders/`

Do not commit:

- `*.pth`
- `*.pt`
- `*.ckpt`
- `*.onnx`
- `*.safetensors`
- downloaded Hugging Face cache blobs
- local install reports that are specific to one machine unless explicitly needed as text evidence elsewhere in `docs/`

After cloning the repository on a new server, recreate the expected local directory layout and place the required model files here before running real inference.
