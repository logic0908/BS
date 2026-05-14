export const AppStatus = {
  IDLE: 'idle',
  FILE_SELECTED: 'file_selected',
  UPLOADING: 'uploading',
  UPLOADED: 'uploaded',
  CONVERTING: 'converting',
  SUCCEEDED: 'succeeded',
  FAILED: 'failed',
} as const

export type AppStatus = (typeof AppStatus)[keyof typeof AppStatus]

export type QualityLevel = 'good' | 'warn' | 'bad'

export interface AudioFile {
  file: File
  url: string
  name: string
  size: number
  mimeType: string
  durationSeconds: number | null
}

export interface InputQualitySummary {
  duration: number | null
  sample_rate: number | null
  channels: number | null
  rms: number | null
  peak: number | null
  low_energy_ratio: number | null
  clipping_ratio: number | null
  silence_ratio: number | null
  is_too_short: boolean
  is_probably_silent: boolean
  quality_level: QualityLevel
  warnings: string[]
}

export interface AudioQualitySummary {
  duration_consistency?: number | null
  low_energy_ratio?: number | null
  possible_dropouts?: boolean | null
}

export interface UploadResponse {
  vocals_id?: string
  status?: string
  is_vocal_only?: boolean
  input_url?: string | null
  vocals_url?: string | null
  file_url?: string | null
  input_audio_path?: string | null
  input_vocals_path?: string | null
  input_quality_summary?: InputQualitySummary | null
  warning?: string | null
}

export interface ConvertResponse {
  task_id?: string
  status?: string
}

export interface TaskError {
  code?: string | null
  message?: string | null
  details?: Record<string, unknown> | null
}

export interface ResultMetadata {
  task_id?: string | null
  status?: string | null
  result_url?: string | null
  download_url?: string | null
  input_url?: string | null
  output_url?: string | null
  warning?: string | null
  condition_mode?: string | null
  film_strength?: number | null
  executed_internal_film?: boolean | null
  text_style_adapter_loaded?: boolean | null
  adapter_mode?: string | null
  adapter_type?: string | null
  adapter_checkpoint?: string | null
  adapter_checkpoint_path?: string | null
  style_prompt?: string | null
  sample_rate?: number | null
  duration_seconds?: number | null
  has_nan_or_inf?: boolean | null
  objective_metrics_summary?: Record<string, unknown> | null
  model_preset_id?: string | null
  requested_model_preset_id?: string | null
  effective_model_preset_id?: string | null
  speaker?: string | null
  input_audio_path?: string | null
  input_vocals_path?: string | null
  final_output_path?: string | null
  audio_quality_summary?: AudioQualitySummary | null
  [key: string]: unknown
}

export interface TaskResponse {
  task_id?: string
  status?: string
  progress?: number
  stage?: string
  message?: string
  result_url?: string | null
  download_url?: string | null
  input_url?: string | null
  output_url?: string | null
  warning?: string | null
  error?: TaskError | string | null
  result_metadata?: Record<string, unknown> | null
  engine_details?: Record<string, unknown> | null
  [key: string]: unknown
}

export interface ProcessingResult {
  taskId: string
  inputAudioUrl: string | null
  outputAudioUrl: string
  resultUrl: string
  downloadUrl: string
  metadata: ResultMetadata
}

export interface ModelPresetStatus {
  preset_id: string
  display_name: string
  ready: boolean
  speaker: string
}

export interface ModelPresetCollection {
  active_preset_id?: string
  fallback_preset_id?: string
  presets?: ModelPresetStatus[]
}

export interface SovitsRuntimeStatus {
  mock?: boolean
  condition_mode?: string | null
  film_strength?: number | null
  model_exists?: boolean
  config_exists?: boolean
}

export interface TextConditioningStatus {
  enabled?: boolean
  film_strength?: number | null
}

export interface SystemHealthResponse {
  ok?: boolean
  app_status?: string
  task_backend_mode?: string
  mock_mode?: boolean
  svc_model_presets?: ModelPresetCollection
  sovits?: SovitsRuntimeStatus
  text_conditioning?: TextConditioningStatus
}

export interface SovitsCheckResponse {
  SOVITS_MOCK?: boolean
  torch_cuda_available?: boolean
  torch_device_count?: number
  svc_model_presets?: ModelPresetCollection
  sovits?: SovitsRuntimeStatus
}

export interface AudioStyleFeatures {
  ok: boolean
  path?: string | null
  duration_seconds?: number | null
  sample_rate?: number | null
  brightness_score?: number | null
  energy_score?: number | null
  softness_score?: number | null
  thickness_score?: number | null
  pitch_height_score?: number | null
  spectral_centroid_mean?: number | null
  spectral_bandwidth_mean?: number | null
  spectral_rolloff_mean?: number | null
  zero_crossing_rate_mean?: number | null
  f0_median?: number | null
  voiced_ratio?: number | null
  low_energy_ratio?: number | null
  mid_energy_ratio?: number | null
  high_energy_ratio?: number | null
  warnings?: string[]
  [key: string]: unknown
}

export interface PromptStyleTargets {
  prompt_text: string
  target_dimensions: Record<string, string>
  matched_keywords: string[]
  human_readable_targets: string[]
}

export interface StyleEvidenceComparison {
  key: string
  label: string
  input_value: number | null
  output_value: number | null
  delta: number | null
  direction: string
  expected_direction: string | null
  matches_prompt: boolean
  evidence_level: string
  explanation: string
}

export interface StyleEvidenceSummary {
  matched_count: number
  total_count: number
  score: number
  level: 'strong' | 'partial' | 'weak' | 'unknown'
  text: string
}

export interface StyleEvidenceRadar {
  dimensions: string[]
  input: number[]
  output: number[]
  target: number[]
}

export interface StyleEvidenceCompareResponse {
  ok: boolean
  prompt_text: string
  model_preset_id?: string | null
  input: AudioStyleFeatures
  output: AudioStyleFeatures
  prompt_targets: PromptStyleTargets
  comparisons: StyleEvidenceComparison[]
  radar: StyleEvidenceRadar
  summary: StyleEvidenceSummary
  warnings: string[]
}

export const STYLE_PROMPT_CHIPS = [
  '温柔明亮流行女声',
  '清亮少年感流行男声',
  '低沉磁性叙事感',
  '激昂有力量摇滚感',
  '甜美轻柔治愈感',
]

export const STYLE_PRESETS = STYLE_PROMPT_CHIPS
