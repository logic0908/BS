
export const AppStatus = {
  IDLE: 'IDLE',
  UPLOADING: 'UPLOADING',
  READY_TO_CONVERT: 'READY_TO_CONVERT',
  CONVERTING: 'CONVERTING',
  COMPLETED: 'COMPLETED',
  ERROR: 'ERROR'
} as const;

export type AppStatus = typeof AppStatus[keyof typeof AppStatus];

export interface AudioFile {
  file: File;
  url: string | null;
  name: string;
  duration: number;
}

export interface ConversionConfig {
  prompt: string;
  intensity: number; // 0.0 to 1.0
}

export interface ProcessingResult {
  originalUrl: string;
  convertedUrl: string;
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
  "流行", 
  "抒情", 
  "古风", 
  "摇滚", 
  "R&B", 
  "治愈", 
  "清澈少年音"
];
