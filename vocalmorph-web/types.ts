
export enum AppStatus {
  IDLE = 'IDLE',
  UPLOADING = 'UPLOADING',
  SEPARATING = 'SEPARATING', // Demucs phase
  READY_TO_CONVERT = 'READY_TO_CONVERT',
  CONVERTING = 'CONVERTING', // So-VITS-SVC phase
  COMPLETED = 'COMPLETED',
  ERROR = 'ERROR'
}

export interface AudioFile {
  file: File | null;
  url: string | null;
  duration: number;
  name: string;
}

export interface ConversionConfig {
  prompt: string;
  intensity: number; // 0.0 to 1.0
}

export interface ProcessingResult {
  originalUrl: string; // The separated vocals
  convertedUrl: string; // The final result
}

export interface ProcessingParams {
  pitchShift: number; // Semitones
  speed: number;      // Playback rate
  distortion: number; // 0-1
  reverb: number;     // 0-1
  lowPass: number;    // Hz
  highPass: number;   // Hz
  formantShift: number; // Simulated via pitch
}

export const STYLE_PRESETS = [
  "Gentle ancient style female voice",
  "Lazy jazz male voice",
  "Powerful anime OP style",
  "Whispery R&B soul",
  "Clear youthful pop",
  "Deep resonant opera baritone"
];
