import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Loader2 } from 'lucide-react';

interface AudioRecorderProps {
  onRecordingComplete: (file: File) => void;
  disabled?: boolean;
}

const AudioRecorder: React.FC<AudioRecorderProps> = ({ onRecordingComplete, disabled = false }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (mediaRecorderRef.current && isRecording) {
        mediaRecorderRef.current.stop();
      }
    };
  }, [isRecording]);

  const startRecording = async () => {
    if (disabled) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        // Create a file with a timestamp name
        const ext = mimeType.includes('mp4') ? 'mp4' : 'webm';
        const blob = new Blob(chunksRef.current, { type: mimeType });
        const file = new File([blob], `recording-${new Date().toISOString()}.${ext}`, { type: mimeType });
        
        onRecordingComplete(file);
        
        // Stop all tracks to release microphone
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setDuration(0);
      
      const startTime = Date.now();
      timerRef.current = window.setInterval(() => {
        setDuration(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);

    } catch (err) {
      console.error("Error accessing microphone:", err);
      alert("Could not access microphone. Please ensure permissions are granted.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className={`
      relative border-2 border-dashed rounded-2xl p-6 flex flex-col items-center justify-center transition-all duration-300
      ${isRecording 
        ? 'border-red-500/50 bg-red-500/10' 
        : disabled 
          ? 'border-slate-700 bg-slate-800/30 cursor-not-allowed opacity-50'
          : 'border-slate-700 bg-slate-800/30 hover:border-slate-600 hover:bg-slate-800/50'
      }
    `}>
      {!isRecording ? (
        <button 
          onClick={startRecording}
          disabled={disabled}
          className="flex flex-row items-center gap-4 w-full justify-center group"
        >
          <div className={`p-3 rounded-full transition-all duration-300 ${
             disabled ? 'bg-slate-700 text-slate-500' : 'bg-slate-700 group-hover:bg-primary/20 group-hover:text-primary text-slate-400'
          }`}>
            <Mic className="w-6 h-6" />
          </div>
          <div className="text-left">
            <h3 className={`text-base font-medium ${disabled ? 'text-slate-500' : 'text-slate-300 group-hover:text-slate-200'}`}>
              Record Microphone
            </h3>
            <p className="text-xs text-slate-500">Click to start recording</p>
          </div>
        </button>
      ) : (
        <div className="flex items-center justify-between w-full px-4">
          <div className="flex items-center gap-3">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
            </span>
            <span className="font-mono text-red-400 text-lg font-medium tracking-wider">
              {formatDuration(duration)}
            </span>
          </div>
          
          <button 
            onClick={stopRecording}
            className="flex items-center gap-2 bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-lg font-bold text-sm transition-all shadow-lg shadow-red-500/20"
          >
            <Square className="w-4 h-4 fill-current" /> 
            Stop
          </button>
        </div>
      )}
    </div>
  );
};

export default AudioRecorder;