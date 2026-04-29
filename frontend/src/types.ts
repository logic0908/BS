
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
  metadata?: {
    inference_mode?: string | null;
    mock_enabled?: boolean | null;
    model_path?: string | null;
    config_path?: string | null;
    speaker?: string | null;
    device?: string | null;
    selected_output?: string | null;
    final_output_path?: string | null;
    return_code?: number | null;
    elapsed_seconds?: number | null;
    sovits_command_debug_path?: string | null;
    called_inference_main?: boolean | null;
  };
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
  "温柔",
  "气声",
  "清亮",
  "摇滚",
  "厚重",
  "少年感",
  "治愈",
  "女声",
  "男声"
];
