
import sys
import torch
import torchaudio

def check_env():
    print(f"Python Version: {sys.version}")
    print(f"PyTorch Version: {torch.__version__}")
    print(f"TorchAudio Version: {torchaudio.__version__}")
    
    cuda_available = torch.cuda.is_available()
    print(f"CUDA Available: {cuda_available}")
    
    if cuda_available:
        print(f"CUDA Device Count: {torch.cuda.device_count()}")
        print(f"Current Device Name: {torch.cuda.get_device_name(0)}")
    else:
        print("WARNING: CUDA is not available. Training/Inference will be very slow on CPU.")

if __name__ == "__main__":
    check_env()
