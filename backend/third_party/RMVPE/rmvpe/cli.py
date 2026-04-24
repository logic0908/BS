"""Command-line interface for RMVPE pitch estimation."""
import argparse
import os
from pathlib import Path

import librosa
import numpy as np
from tqdm import tqdm

from .inference import RMVPE


def process_audio_file(audio_path, rmvpe_model, thred=0.03):
    """Process a single audio file and return pitch predictions."""
    # Load and preprocess audio
    audio, sampling_rate = librosa.load(audio_path, sr=16000)
    if len(audio.shape) > 1:
        audio = librosa.to_mono(audio.transpose(1, 0))
    
    # Get predictions using RMVPE
    f0 = rmvpe_model.infer_from_audio(audio, thred=thred)
    
    # Create time array (hop_length=160 for 16kHz audio)
    times = np.arange(len(f0)) * 160 / 16000  # Convert to seconds
    
    return times, f0


def process_single_file(input_path, output_path, rmvpe, thred=0.03):
    """Process a single file."""
    # Skip if output already exists
    if os.path.exists(output_path):
        return "skipped"
        
    try:
        # Process audio
        times, freqs = process_audio_file(input_path, rmvpe, thred=thred)
        
        # Save results
        np.savetxt(output_path, np.column_stack((times, freqs)), 
                  delimiter=',', header='time,frequency', comments='', fmt='%.8f')
        return "success"
    except Exception as e:
        print(f"\nError processing {os.path.basename(input_path)}: {str(e)}")
        return "failed"


def process_folder(input_folder, output_folder, model_path=None, device=None, 
                   is_half=False, thred=0.03):
    """Process all audio files in a folder and save results."""
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Initialize RMVPE model
    print("Initializing RMVPE model...")
    rmvpe = RMVPE(model_path=model_path, is_half=is_half, device=device)
    
    # Get all audio files
    audio_extensions = ('.wav', '.mp3', '.flac', '.ogg', '.m4a')
    audio_files = [f for f in os.listdir(input_folder) 
                   if f.lower().endswith(audio_extensions)]
    
    if not audio_files:
        print(f"No audio files found in {input_folder}")
        return
    
    print(f"Found {len(audio_files)} audio files to process.")
    
    # Process files
    successful = 0
    failed = 0
    skipped = 0
    
    for audio_file in tqdm(audio_files, desc="Processing audio files"):
        input_path = os.path.join(input_folder, audio_file)
        output_path = os.path.join(output_folder, 
                                   os.path.splitext(audio_file)[0] + '.csv')
        result = process_single_file(input_path, output_path, rmvpe, thred)
        
        if result == "success":
            successful += 1
        elif result == "failed":
            failed += 1
        elif result == "skipped":
            skipped += 1
    
    print(f"\nProcessing complete!")
    print(f"  Successfully processed: {successful} files")
    print(f"  Skipped (already exists): {skipped} files")
    print(f"  Failed: {failed} files")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='RMVPE: Vocal Pitch Estimation for audio files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all audio files in a folder
  rmvpe input_folder/ output_folder/
  
  # Use custom model path
  rmvpe input_folder/ output_folder/ --model_path /path/to/model.pt
  
  # Use GPU with half precision
  rmvpe input_folder/ output_folder/ --device cuda --is_half
  
  # Adjust sensitivity threshold
  rmvpe input_folder/ output_folder/ --thred 0.05
        """
    )
    
    parser.add_argument('input_folder', type=str, 
                       help='Input folder containing audio files')
    parser.add_argument('output_folder', type=str, 
                       help='Output folder for pitch estimation CSV files')
    parser.add_argument('--model_path', type=str, default=None,
                       help='Path to RMVPE model file (default: auto-download)')
    parser.add_argument('--device', type=str, default=None,
                       help='Device to use: cuda or cpu (default: auto-detect)')
    parser.add_argument('--is_half', action='store_true',
                       help='Use half precision (FP16) for inference')
    parser.add_argument('--thred', type=float, default=0.03,
                       help='Threshold for pitch detection (default: 0.03, lower = more sensitive)')
    
    args = parser.parse_args()
    
    # Validate input folder
    if not os.path.isdir(args.input_folder):
        print(f"Error: Input folder '{args.input_folder}' does not exist.")
        return 1
    
    # Process folder
    process_folder(
        args.input_folder,
        args.output_folder,
        model_path=args.model_path,
        device=args.device,
        is_half=args.is_half,
        thred=args.thred
    )
    
    return 0


if __name__ == "__main__":
    exit(main())

