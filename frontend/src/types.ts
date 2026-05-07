export const AppStatus = {
  IDLE: 'IDLE',
  UPLOADING: 'UPLOADING',
  READY_TO_CONVERT: 'READY_TO_CONVERT',
  CONVERTING: 'CONVERTING',
  COMPLETED: 'COMPLETED',
  ERROR: 'ERROR',
} as const

export type AppStatus = (typeof AppStatus)[keyof typeof AppStatus]

export type QualityLevel = 'good' | 'warn' | 'bad'

export interface AudioFile {
  file: File
  url: string | null
  name: string
  duration: number
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

export interface AudioStyleFeatures {
  ok: boolean
  path?: string | null
  duration_seconds?: number | null
  sample_rate?: number | null
  frames?: number | null
  channels?: number | null
  rms_mean?: number | null
  rms_std?: number | null
  dynamic_range?: number | null
  spectral_centroid_mean?: number | null
  spectral_bandwidth_mean?: number | null
  spectral_rolloff_mean?: number | null
  zero_crossing_rate_mean?: number | null
  f0_available?: boolean | null
  f0_mean?: number | null
  f0_median?: number | null
  f0_std?: number | null
  f0_min?: number | null
  f0_max?: number | null
  voiced_ratio?: number | null
  low_energy_ratio?: number | null
  mid_energy_ratio?: number | null
  high_energy_ratio?: number | null
  brightness_score?: number | null
  energy_score?: number | null
  softness_score?: number | null
  thickness_score?: number | null
  pitch_height_score?: number | null
  warnings?: string[]
  code?: string | null
  message?: string | null
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

export interface StyleSelection {
  style_id?: string | null
  style_label?: string | null
  description?: string | null
  model_preset_id?: string | null
  requested_model_preset_id?: string | null
  effective_model_preset_id?: string | null
  preset_fallback_used?: boolean | null
  preset_fallback_reason?: string | null
  model_display_name?: string | null
  model_preset_ready?: boolean | null
  model_preset_configured?: boolean | null
  current_style_has_dedicated_model?: boolean | null
  model_preset_notice?: string | null
  transpose?: number | null
  match_score?: number | null
  matched_keywords?: string[] | null
  reason?: string | null
  adapter_override_reason?: string | null
}

export interface ResultMetadata {
  inference_mode?: string | null
  mock_enabled?: boolean | null
  model_path?: string | null
  config_path?: string | null
  model_preset_id?: string | null
  requested_model_preset_id?: string | null
  effective_model_preset_id?: string | null
  preset_fallback_used?: boolean | null
  preset_fallback_reason?: string | null
  model_display_name?: string | null
  source_repo?: string | null
  source_url?: string | null
  license?: string | null
  install_report_path?: string | null
  notes?: string | null
  model_path_basename?: string | null
  config_path_basename?: string | null
  model_preset_ready?: boolean | null
  model_preset_configured?: boolean | null
  is_demo_quality?: boolean | null
  smoke_test_passed?: boolean | null
  is_technical_validation_only?: boolean | null
  speaker?: string | null
  device?: string | null
  selected_output?: string | null
  final_output_path?: string | null
  return_code?: number | null
  elapsed_seconds?: number | null
  sovits_command_debug_path?: string | null
  gpu_telemetry_debug_path?: string | null
  task_backend_mode?: string | null
  encoder_model_name?: string | null
  embedding_dim?: number | null
  embedding_norm?: number | null
  top_keywords?: string[] | null
  text_encoding_status?: string | null
  text_encoding_enabled?: boolean | null
  adapter_enabled?: boolean | null
  adapter_mode?: string | null
  adapter_version?: string | null
  adapter_type?: string | null
  adapter_checkpoint_path?: string | null
  control_params_summary?: Record<string, unknown> | null
  adapter_override_reason?: string | null
  adapter_fallback_reason?: string | null
  audio_quality_summary?: AudioQualitySummary | null
  audio_quality_report_path?: string | null
  input_audio_path?: string | null
  input_vocals_path?: string | null
  text_style_adapter_notice?: string | null
  called_inference_main?: boolean | null
  input_quality_summary?: InputQualitySummary | null
  input_quality_report_path?: string | null
  effective_style_strength?: number | null
  f0_method?: string | null
  f0_fallback_reason?: string | null
  auto_predict_f0?: boolean | null
  slice_db?: number | null
  clip_seconds?: number | null
  pad_seconds?: number | null
  conversion_params_path?: string | null
  conversion_params_summary?: Record<string, unknown> | null
}

export interface ProcessingResult {
  originalUrl: string
  convertedUrl: string
  metadata?: ResultMetadata
}

export interface TaskResponse {
  task_id?: string
  engine?: string
  status?: string
  progress?: number
  stage?: string
  message?: string
  selected_style?: StyleSelection | null
  result_url?: string | null
  error?: unknown
  inference_mode?: string | null
  engine_details?: Record<string, unknown> | null
  result_metadata?: Record<string, unknown> | null
  task_backend_mode?: string | null
  text_encoding?: Record<string, unknown> | null
  adapter_result?: Record<string, unknown> | null
  audio_quality?: Record<string, unknown> | null
  mock_enabled?: boolean | null
  model_path?: string | null
  config_path?: string | null
  speaker?: string | null
  device?: string | null
  selected_output?: string | null
  final_output_path?: string | null
  return_code?: number | null
  elapsed_seconds?: number | null
  sovits_command_debug_path?: string | null
  gpu_telemetry_debug_path?: string | null
  encoder_model_name?: string | null
  embedding_dim?: number | null
  embedding_norm?: number | null
  top_keywords?: string[] | null
  text_encoding_status?: string | null
  text_encoding_enabled?: boolean | null
  adapter_enabled?: boolean | null
  adapter_mode?: string | null
  adapter_version?: string | null
  adapter_type?: string | null
  adapter_checkpoint_path?: string | null
  control_params_summary?: Record<string, unknown> | null
  adapter_override_reason?: string | null
  adapter_fallback_reason?: string | null
  audio_quality_summary?: AudioQualitySummary | null
  audio_quality_report_path?: string | null
  input_audio_path?: string | null
  input_vocals_path?: string | null
  text_style_adapter_notice?: string | null
  model_preset_id?: string | null
  requested_model_preset_id?: string | null
  effective_model_preset_id?: string | null
  preset_fallback_used?: boolean | null
  preset_fallback_reason?: string | null
  model_display_name?: string | null
  source_repo?: string | null
  source_url?: string | null
  license?: string | null
  install_report_path?: string | null
  notes?: string | null
  model_path_basename?: string | null
  config_path_basename?: string | null
  model_preset_ready?: boolean | null
  model_preset_configured?: boolean | null
  is_demo_quality?: boolean | null
  smoke_test_passed?: boolean | null
  is_technical_validation_only?: boolean | null
  input_quality_summary?: InputQualitySummary | null
  input_quality_report_path?: string | null
  f0_method?: string | null
  f0_fallback_reason?: string | null
  auto_predict_f0?: boolean | null
  slice_db?: number | null
  clip_seconds?: number | null
  pad_seconds?: number | null
  conversion_params_path?: string | null
  conversion_params_summary?: Record<string, unknown> | null
}

export interface UploadResponse {
  vocals_id?: string
  status?: string
  is_vocal_only?: boolean
  input_quality_summary?: InputQualitySummary | null
}

export interface ModelPresetStatus {
  preset_id: string
  display_name: string
  ready: boolean
  speaker: string
  style_tags?: string[]
  source_repo?: string
  source_url?: string
  license?: string
  install_report_path?: string
  notes?: string
  is_configured?: boolean
  is_demo_quality?: boolean
  smoke_test_passed?: boolean
  is_technical_validation_only?: boolean
  model_exists?: boolean
  config_exists?: boolean
}

export interface ModelPresetCollection {
  active_preset_id?: string
  fallback_preset_id?: string
  active_preset_ready?: boolean
  presets?: ModelPresetStatus[]
}

export interface SystemHealthResponse {
  ok?: boolean
  app_status?: string
  mock_mode?: boolean
  task_backend_mode?: string
  svc_model_presets?: ModelPresetCollection
  timestamp?: string
}

export interface SovitsCheckResponse {
  SOVITS_MOCK?: boolean
  SOVITS_DEVICE?: string
  torch_cuda_available?: boolean
  torch_device_count?: number
  f0_method?: string | null
  f0_fallback_reason?: string | null
  auto_predict_f0?: boolean | null
  slice_db?: number | null
  clip_seconds?: number | null
  pad_seconds?: number | null
  model_preset_id?: string
  model_display_name?: string
  svc_model_presets?: ModelPresetCollection
}

export const STYLE_PRESETS = [
  '流行',
  '温柔',
  '气声',
  '清亮',
  '摇滚',
  '厚重',
  '少年感',
  '治愈',
  '女声',
  '男声',
]
