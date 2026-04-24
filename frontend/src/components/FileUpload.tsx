import React, { useCallback } from 'react';
import { UploadCloud, FileAudio } from 'lucide-react';

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
}

const FileUpload: React.FC<FileUploadProps> = ({ onFileSelect, disabled = false }) => {
  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      if (disabled) return;
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        validateAndPass(e.dataTransfer.files[0]);
      }
    },
    [disabled, onFileSelect]
  );

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndPass(e.target.files[0]);
    }
  };

  const validateAndPass = (file: File) => {
    // Basic validation for audio types
    if (file.type.startsWith('audio/') || file.name.endsWith('.wav') || file.name.endsWith('.mp3')) {
      onFileSelect(file);
    } else {
      alert('Please upload a valid audio file (.mp3, .wav)');
    }
  };

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      className={`relative group border-2 border-dashed rounded-2xl p-10 text-center transition-all duration-300 ${
        disabled
          ? 'border-slate-700 bg-slate-800/30 cursor-not-allowed opacity-50'
          : 'border-slate-600 bg-slate-800/50 hover:border-primary hover:bg-slate-800 cursor-pointer'
      }`}
    >
      <input
        type="file"
        accept=".mp3,.wav"
        onChange={handleInputChange}
        disabled={disabled}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
      />
      
      <div className="flex flex-col items-center gap-4 pointer-events-none">
        <div className={`p-4 rounded-full transition-transform duration-300 group-hover:scale-110 ${
          disabled ? 'bg-slate-700' : 'bg-slate-700/50 group-hover:bg-primary/20'
        }`}>
          {disabled ? (
             <FileAudio className="w-8 h-8 text-slate-500" />
          ) : (
             <UploadCloud className="w-8 h-8 text-primary" />
          )}
        </div>
        
        <div className="space-y-1">
          <h3 className="text-lg font-medium text-slate-200">
            {disabled ? 'File Uploaded' : 'Click or Drag & Drop'}
          </h3>
          <p className="text-sm text-slate-400">
            Supports .wav, .mp3 (Max 10MB)
          </p>
        </div>
      </div>
    </div>
  );
};

export default FileUpload;