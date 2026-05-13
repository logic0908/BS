export const FIELD_LABELS: Record<string, string> = {
  task_id: '任务编号',
  status: '任务状态',
  stage: '当前阶段',
  progress: '处理进度',
  result_url: '结果接口',
  output_url: '输出音频地址',
  output_path: '输出路径',
  output_file: '输出文件',
  input_url: '输入音频地址',
  vocals_id: '人声编号',
  duration_seconds: '音频时长',
  sample_rate: '采样率',
  has_nan_or_inf: '异常数值检查',
  condition_mode: '条件控制模式',
  film_strength: '注入强度',
  executed_internal_film: '已执行内部注入',
  text_style_adapter_loaded: '已加载训练适配器',
  adapter_mode: '适配器模式',
  adapter_type: '适配器类型',
  adapter_checkpoint: '适配器权重',
  model_preset: '模型预设',
  model_preset_id: '模型预设',
  effective_model_preset_id: '实际模型预设',
  speaker: '目标音色',
  style_prompt: '风格提示词',
  brightness_score: '亮度',
  energy_score: '能量',
  softness_score: '柔和度',
  thickness_score: '厚度',
  f0_median: '基频中位数',
  spectral_centroid_mean: '频谱中心均值',
  voiced_ratio: '有声帧比例',
}

export const VALUE_LABELS: Record<string, string> = {
  internal_film: '内部 FiLM 注入',
  none: '不启用内部注入',
  trained: '训练适配器',
  trained_mlp: '训练得到的 MLP 适配器',
  no_adapter: '未启用适配器',
  rule_based: '规则适配器',
  final_primary: '主模型预设',
  lain: '当前目标音色 lain',
  true: '是',
  false: '否',
  succeeded: '已完成',
  failed: '失败',
  running: '处理中',
  pending: '等待中',
  completed: '已完成',
  queued: '等待中',
  uploading: '上传中',
  uploaded: '上传完成',
  converting: '处理中',
  idle: '待开始',
  file_selected: '已选择文件',
  text_encoded: '文本编码',
  adapter_applied: '适配器处理',
  inference_running: '内部注入与推理',
}

export function labelOf(key: string): string {
  return FIELD_LABELS[key] ?? key
}

export function valueLabelOf(value: unknown): string {
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (value == null || value === '') return '未返回'
  const text = String(value)
  return VALUE_LABELS[text] ?? text
}

export function formatSeconds(value: unknown): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return '未返回'
  return `${n.toFixed(2)} 秒`
}

export function formatSampleRate(value: unknown): string {
  const n = Number(value)
  if (!Number.isFinite(n)) return '未返回'
  return `${Math.round(n)} Hz`
}
