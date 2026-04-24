import React, { useEffect, useRef, useState, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { Play, Pause, Loader2 } from 'lucide-react';

interface WaveformPlayerProps {
  audioUrl: string | null;
  height?: number;
  waveColor?: string;
  progressColor?: string;
  interact?: boolean;
}

const WaveformPlayer: React.FC<WaveformPlayerProps> = ({
  audioUrl,
  height = 80,
  waveColor = '#4f46e5', // indigo-600
  progressColor = '#ec4899', // pink-500
  interact = true,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isReady, setIsReady] = useState(false);

  const initWaveSurfer = useCallback(() => {
    if (!containerRef.current || !audioUrl) return;

    if (wavesurferRef.current) {
      wavesurferRef.current.destroy();
    }

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: waveColor,
      progressColor: progressColor,
      cursorColor: 'rgba(255,255,255,0.5)',
      barWidth: 2,
      barGap: 3,
      barRadius: 3,
      height: height,
      normalize: true,
      interact: interact,
      url: audioUrl, // Load directly via URL option in v7
    });

    ws.on('ready', () => {
      setIsReady(true);
    });

    ws.on('play', () => setIsPlaying(true));
    ws.on('pause', () => setIsPlaying(false));
    ws.on('finish', () => setIsPlaying(false));

    wavesurferRef.current = ws;

    return () => {
      ws.destroy();
    };
  }, [audioUrl, height, waveColor, progressColor, interact]);

  useEffect(() => {
    const cleanup = initWaveSurfer();
    return () => {
      cleanup?.();
    };
  }, [initWaveSurfer]);

  const togglePlay = () => {
    if (wavesurferRef.current) {
      wavesurferRef.current.playPause();
    }
  };

  if (!audioUrl) return null;

  return (
    <div className="w-full bg-surface/50 rounded-xl p-4 border border-slate-700/50 backdrop-blur-sm">
      <div className="flex items-center gap-4">
        <button
          onClick={togglePlay}
          disabled={!isReady}
          className={`flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-full transition-all duration-200 ${
            isReady 
              ? 'bg-primary hover:bg-primary/90 text-white shadow-lg shadow-primary/25' 
              : 'bg-slate-700 text-slate-500 cursor-not-allowed'
          }`}
        >
          {!isReady ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : isPlaying ? (
            <Pause className="w-5 h-5 fill-current" />
          ) : (
            <Play className="w-5 h-5 fill-current ml-1" />
          )}
        </button>

        <div className="flex-grow relative h-[80px]" ref={containerRef}>
          {!isReady && (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-slate-400">
              Loading waveform...
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default WaveformPlayer;