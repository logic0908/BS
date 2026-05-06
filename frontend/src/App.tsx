import { Component, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import axios from 'axios'
import { ChevronDown, Cpu, ShieldAlert, Sparkles, Wand2 } from 'lucide-react'

import './App.css'
import AudioComparePanel from './components/AudioComparePanel'
import FileUpload from './components/FileUpload'
import {
  AppStatus,
  STYLE_PRESETS,
  type AudioFile,
  type InputQualitySummary,
  type ModelPresetCollection,
  type ModelPresetStatus,
  type ProcessingResult,
  type ResultMetadata,
  type StyleSelection,
  type SovitsCheckResponse,
  type SystemHealthResponse,
  type TaskResponse,
  type UploadResponse,
} from './types'

type ResultFetchPayload = {
  blob: Blob
  taskData: TaskResponse
}

type DebugArtifacts = {
  extracted_features?: string
  quality_report?: string
}

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app-shell" translate="no">
          <div className="page-frame">
            <section className="surface-card error-card">
              <h2>页面渲染出错了</h2>
              <pre>{this.state.error?.message}</pre>
              <button type="button" className="primary-button" onClick={() => window.location.reload()}>
                刷新页面
              </button>
            </section>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function App() {
  const [systemHealth, setSystemHealth] = useState<SystemHealthResponse | null>(null)
  const [sovitsCheck, setSovitsCheck] = useState<SovitsCheckResponse | null>(null)
  const [promptText, setPromptText] = useState('')
  const [styleStrength, setStyleStrength] = useState(0.65)
  const [transpose, setTranspose] = useState(0)
  const [f0Method, setF0Method] = useState('rmvpe')
  const [autoPredictF0, setAutoPredictF0] = useState(false)
  const [sliceDb, setSliceDb] = useState(-40)
  const [clipSeconds, setClipSeconds] = useState(0)
  const [padSeconds, setPadSeconds] = useState(0.5)
  const [allowPresetFallback, setAllowPresetFallback] = useState(false)
  const [modelPresetId, setModelPresetId] = useState('final_primary')
  const [isVocalOnly, setIsVocalOnly] = useState(false)
  const [uploadedVocalOnly, setUploadedVocalOnly] = useState<boolean | null>(null)
  const [advancedParamsOpen, setAdvancedParamsOpen] = useState(false)
  const [techDetailsOpen, setTechDetailsOpen] = useState(false)
  const [styleSingerOpen, setStyleSingerOpen] = useState(false)
  const [phSeq, setPhSeq] = useState('')
  const [noteSeq, setNoteSeq] = useState('')
  const [noteDurSeq, setNoteDurSeq] = useState('')
  const [noteTypeSeq, setNoteTypeSeq] = useState('')
  const [featureSource, setFeatureSource] = useState<string | null>(null)
  const [featureDebugArtifacts, setFeatureDebugArtifacts] = useState<DebugArtifacts | null>(null)
  const [featureQualityMessage, setFeatureQualityMessage] = useState<string | null>(null)

  const [status, setStatus] = useState<typeof AppStatus[keyof typeof AppStatus]>(AppStatus.IDLE)
  const [inputAudio, setInputAudio] = useState<AudioFile | null>(null)
  const [vocalsId, setVocalsId] = useState<string | null>(null)
  const [taskStatusMsg, setTaskStatusMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [result, setResult] = useState<ProcessingResult | null>(null)
  const [selectedStyle, setSelectedStyle] = useState<StyleSelection | null>(null)
  const [taskSnapshot, setTaskSnapshot] = useState<TaskResponse | null>(null)
  const [inputQuality, setInputQuality] = useState<InputQualitySummary | null>(null)

  const isUploading = status === AppStatus.UPLOADING
  const isConverting = status === AppStatus.CONVERTING
  const promptError = !promptText.trim() ? '请先输入目标风格描述。' : null
  const mockMode = typeof sovitsCheck?.SOVITS_MOCK === 'boolean' ? Boolean(sovitsCheck.SOVITS_MOCK) : Boolean(systemHealth?.mock_mode)
  const gpuStatus = getGpuStatus(sovitsCheck)
  const canStartConversion = Boolean(vocalsId) && Boolean(promptText.trim()) && !isUploading && !isConverting
  const taskProgress = Math.max(0, Math.min(100, Number(taskSnapshot?.progress ?? 0)))
  const promptConflict = useMemo(() => detectPromptConflict(promptText), [promptText])
  const currentResultMetadata = useMemo(
    () => result?.metadata ?? normalizeResultMetadata(taskSnapshot),
    [result?.metadata, taskSnapshot],
  )
  const effectiveTaskBackendMode =
    currentResultMetadata?.task_backend_mode ?? taskSnapshot?.task_backend_mode ?? systemHealth?.task_backend_mode ?? 'celery'
  const modelPresets = useMemo(
    () => pickPresets(systemHealth?.svc_model_presets ?? sovitsCheck?.svc_model_presets ?? null),
    [sovitsCheck?.svc_model_presets, systemHealth?.svc_model_presets],
  )
  const activePreset = useMemo(
    () => modelPresets.find((item) => item.preset_id === modelPresetId) ?? modelPresets[0] ?? null,
    [modelPresetId, modelPresets],
  )
  const activePresetConfigured = activePreset?.ready ?? false
  const effectiveF0Method = currentResultMetadata?.f0_method ?? sovitsCheck?.f0_method ?? f0Method
  const effectiveAutoPredictF0 = currentResultMetadata?.auto_predict_f0 ?? sovitsCheck?.auto_predict_f0 ?? autoPredictF0
  const selectedStyleNeedsDedicatedPreset = Boolean(selectedStyle?.current_style_has_dedicated_model)
  const selectedStylePresetReady = Boolean(selectedStyle?.model_preset_ready)
  const requestedModelPresetId =
    currentResultMetadata?.requested_model_preset_id ?? selectedStyle?.model_preset_id ?? modelPresetId
  const effectiveModelPresetId =
    currentResultMetadata?.effective_model_preset_id ?? currentResultMetadata?.model_preset_id ?? modelPresetId
  const presetFallbackUsed = Boolean(currentResultMetadata?.preset_fallback_used)
  const activePresetStatusLabel = activePreset?.ready ? '已配置' : '未绑定模型'
  const unconfiguredPresetNotice = !activePresetConfigured
    ? allowPresetFallback
      ? '当前选中的目标模型 preset 尚未真正配置完成；开启 fallback 后会回退到 final_primary/lain，并把请求 preset 与实际使用 preset 分开记录。'
      : '当前选中的目标模型 preset 尚未真正配置完成；严格模式下该 preset 不能推理，也不会伪装成该风格。'
    : null

  useEffect(() => {
    let cancelled = false

    const loadSystemStatus = async () => {
      try {
        const [healthResponse, checkResponse] = await Promise.all([
          axios.get<SystemHealthResponse>('/api/v1/system/health'),
          axios.get<SovitsCheckResponse>('/api/v1/system/sovits-check'),
        ])
        if (cancelled) {
          return
        }
        setSystemHealth(healthResponse.data ?? null)
        setSovitsCheck(checkResponse.data ?? null)
      } catch {
        if (!cancelled) {
          setSystemHealth(null)
          setSovitsCheck(null)
        }
      }
    }

    void loadSystemStatus()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const activePresetId = systemHealth?.svc_model_presets?.active_preset_id
    if (typeof activePresetId === 'string' && activePresetId.trim()) {
      setModelPresetId(activePresetId)
    }
  }, [systemHealth?.svc_model_presets?.active_preset_id])

  useEffect(() => {
    if (typeof sovitsCheck?.f0_method === 'string' && sovitsCheck.f0_method.trim()) {
      setF0Method(sovitsCheck.f0_method)
    }
    if (typeof sovitsCheck?.auto_predict_f0 === 'boolean') {
      setAutoPredictF0(sovitsCheck.auto_predict_f0)
    }
    if (typeof sovitsCheck?.slice_db === 'number') {
      setSliceDb(sovitsCheck.slice_db)
    }
    if (typeof sovitsCheck?.clip_seconds === 'number') {
      setClipSeconds(sovitsCheck.clip_seconds)
    }
    if (typeof sovitsCheck?.pad_seconds === 'number') {
      setPadSeconds(sovitsCheck.pad_seconds)
    }
  }, [sovitsCheck?.auto_predict_f0, sovitsCheck?.clip_seconds, sovitsCheck?.f0_method, sovitsCheck?.pad_seconds, sovitsCheck?.slice_db])

  const handleFileSelect = async (file: File) => {
    if (file.size > 10 * 1024 * 1024) {
      setErrorMsg('上传音频文件大小不能超过 10MB。')
      setStatus(AppStatus.ERROR)
      return
    }

    const fileUrl = window.URL.createObjectURL(file)
    setInputAudio({
      file,
      url: fileUrl,
      name: file.name,
      duration: 0,
    })
    setResult(null)
    setVocalsId(null)
    setUploadedVocalOnly(null)
    setTaskSnapshot(null)
    setSelectedStyle(null)
    setFeatureDebugArtifacts(null)
    setFeatureQualityMessage(null)
    setInputQuality(null)
    setErrorMsg(null)
    setStatus(AppStatus.UPLOADING)
    setTaskStatusMsg(isVocalOnly ? '正在标准化干声并生成输入质量报告…' : '正在分离/标准化人声并生成输入质量报告…')

    try {
      const formData = new FormData()
      formData.append('audio', file)
      formData.append('is_vocal_only', String(isVocalOnly))
      const response = await axios.post<UploadResponse>('/api/v1/upload', formData)
      setVocalsId(response.data?.vocals_id ?? null)
      setUploadedVocalOnly(Boolean(response.data?.is_vocal_only))
      setInputQuality(response.data?.input_quality_summary ?? null)
      setTaskStatusMsg('音频上传完成，可以开始默认 So-VITS-SVC 转换。')
      setStatus(AppStatus.READY_TO_CONVERT)
    } catch (err: unknown) {
      setStatus(AppStatus.ERROR)
      setTaskStatusMsg(null)
      setErrorMsg(readAxiosMessage(err, '上传或预处理失败，请检查后端服务。'))
    }
  }

  const pollTask = async (taskId: string): Promise<ResultFetchPayload> => {
    for (let i = 0; i < 180; i += 1) {
      const statusResponse = await axios.get<TaskResponse>(`/api/v1/tasks/${taskId}`)
      const data = (statusResponse.data ?? {}) as TaskResponse
      setTaskSnapshot(data)
      setTaskStatusMsg(typeof data.message === 'string' ? data.message : '正在处理…')
      setSelectedStyle(data.selected_style ?? null)
      if (data.status === 'succeeded') {
        const resultResponse = await axios.get(`/api/v1/tasks/${taskId}/result`, { responseType: 'blob' })
        return {
          blob: resultResponse.data as Blob,
          taskData: data,
        }
      }
      if (data.status === 'failed') {
        throw new Error(
          typeof data.error === 'string'
            ? data.error
            : typeof (data.error as { message?: string } | null)?.message === 'string'
              ? String((data.error as { message?: string }).message)
              : data.message || '转换失败',
        )
      }
      await new Promise((resolve) => setTimeout(resolve, 1000))
    }
    throw new Error('任务超时，请重试。')
  }

  const completeWithBlob = (payload: ResultFetchPayload) => {
    const originalUrl = inputAudio?.url
    if (!originalUrl) {
      throw new Error('原始音频缺失。')
    }
    const convertedUrl = window.URL.createObjectURL(payload.blob)
    setResult({
      originalUrl,
      convertedUrl,
      metadata: normalizeResultMetadata(payload.taskData),
    })
    setStatus(AppStatus.COMPLETED)
    setTaskStatusMsg('转换完成，可以在下方进行 A/B 对比。')
  }

  const handleSvcConvert = async () => {
    if (!vocalsId) {
      setStatus(AppStatus.ERROR)
      setErrorMsg('请先上传音频并完成预处理。')
      return
    }
    if (!promptText.trim()) {
      setStatus(AppStatus.ERROR)
      setErrorMsg('请先输入目标风格描述。')
      return
    }

    setStatus(AppStatus.CONVERTING)
    setTaskStatusMsg('正在创建 So-VITS-SVC 任务…')
    setTaskSnapshot(null)
    setErrorMsg(null)

    try {
      const response = await axios.post('/api/v1/convert', {
        vocals_id: vocalsId,
        prompt_text: promptText,
        style_strength: styleStrength,
        model_preset_id: modelPresetId,
        transpose,
        f0_method: f0Method,
        auto_predict_f0: autoPredictF0,
        slice_db: sliceDb,
        clip_seconds: clipSeconds,
        pad_seconds: padSeconds,
        allow_preset_fallback: allowPresetFallback,
        engine: 'sovits',
      })
      const taskId = response.data?.task_id as string | undefined
      if (!taskId) {
        throw new Error('后端未返回 task_id。')
      }
      const payload = await pollTask(taskId)
      completeWithBlob(payload)
    } catch (err: unknown) {
      setStatus(AppStatus.ERROR)
      setErrorMsg(readAxiosMessage(err, 'SVC 转换失败。'))
    }
  }

  const handleExtractFeatures = async () => {
    if (!inputAudio?.file) {
      setStatus(AppStatus.ERROR)
      setErrorMsg('请先上传音频。')
      return
    }

    setTaskStatusMsg('正在提取 StyleSinger 四维特征…')
    setErrorMsg(null)

    try {
      const formData = new FormData()
      formData.append('audio', inputAudio.file)
      formData.append('prompt_text', promptText)
      formData.append('style_prompt', promptText)
      formData.append('is_vocal_only', String(isVocalOnly))

      const response = await axios.post('/api/v1/extract_features', formData)
      const data = response.data ?? {}
      setPhSeq(data.ph ?? '')
      setNoteSeq(data.note ?? '')
      setNoteDurSeq(data.note_dur ?? '')
      setNoteTypeSeq(data.note_type ?? '')
      setFeatureSource(data.source ?? data.features?.source ?? 'auto')
      setFeatureDebugArtifacts((data.debug_artifacts as DebugArtifacts | undefined) ?? null)
      setFeatureQualityMessage(typeof data.quality_reason === 'string' ? data.quality_reason : null)
      setTaskStatusMsg('StyleSinger 实验特征已回填。')
    } catch (err: unknown) {
      setStatus(AppStatus.ERROR)
      setErrorMsg(readAxiosMessage(err, '四维特征提取失败。'))
    }
  }

  const handleStyleSingerConvert = async () => {
    if (!inputAudio?.file) {
      setStatus(AppStatus.ERROR)
      setErrorMsg('请先上传音频。')
      return
    }
    if (!promptText.trim()) {
      setStatus(AppStatus.ERROR)
      setErrorMsg('高级模式也需要风格描述。')
      return
    }

    setStatus(AppStatus.CONVERTING)
    setTaskStatusMsg('正在创建 StyleSinger 高级实验任务…')
    setTaskSnapshot(null)
    setErrorMsg(null)

    try {
      const formData = new FormData()
      formData.append('text', promptText)
      formData.append('prompt_text', promptText)
      formData.append('style_prompt', promptText)
      formData.append('style_strength', styleStrength.toString())
      formData.append('ph_seq', phSeq)
      formData.append('note_seq', noteSeq)
      formData.append('note_dur_seq', noteDurSeq)
      formData.append('note_type_seq', noteTypeSeq)
      formData.append('is_vocal_only', String(isVocalOnly))
      formData.append('ref_audio', inputAudio.file)

      const response = await axios.post('/api/v1/tasks', formData)
      const taskId = response.data?.task_id as string | undefined
      if (!taskId) {
        throw new Error('后端未返回 task_id。')
      }
      const payload = await pollTask(taskId)
      completeWithBlob(payload)
    } catch (err: unknown) {
      setStatus(AppStatus.ERROR)
      setErrorMsg(readAxiosMessage(err, 'StyleSinger 高级模式转换失败。'))
    }
  }

  const appendPromptTag = (tag: string) => {
    setPromptText((current) => {
      const trimmed = current.trim()
      if (!trimmed) {
        return tag
      }
      const parts = trimmed.split('、').map((item) => item.trim())
      if (parts.includes(tag)) {
        return current
      }
      return `${trimmed}、${tag}`
    })
  }

  const resetApp = () => {
    if (inputAudio?.url) {
      window.URL.revokeObjectURL(inputAudio.url)
    }
    if (result?.convertedUrl) {
      window.URL.revokeObjectURL(result.convertedUrl)
    }
    setPromptText('')
    setStyleStrength(0.65)
    setTranspose(0)
    setF0Method(sovitsCheck?.f0_method || 'rmvpe')
    setAutoPredictF0(Boolean(sovitsCheck?.auto_predict_f0))
    setSliceDb(typeof sovitsCheck?.slice_db === 'number' ? sovitsCheck.slice_db : -40)
    setClipSeconds(typeof sovitsCheck?.clip_seconds === 'number' ? sovitsCheck.clip_seconds : 0)
    setPadSeconds(typeof sovitsCheck?.pad_seconds === 'number' ? sovitsCheck.pad_seconds : 0.5)
    setAllowPresetFallback(false)
    setModelPresetId(systemHealth?.svc_model_presets?.active_preset_id || 'final_primary')
    setIsVocalOnly(false)
    setUploadedVocalOnly(null)
    setAdvancedParamsOpen(false)
    setTechDetailsOpen(false)
    setStyleSingerOpen(false)
    setPhSeq('')
    setNoteSeq('')
    setNoteDurSeq('')
    setNoteTypeSeq('')
    setFeatureSource(null)
    setFeatureDebugArtifacts(null)
    setFeatureQualityMessage(null)
    setStatus(AppStatus.IDLE)
    setInputAudio(null)
    setVocalsId(null)
    setTaskStatusMsg(null)
    setErrorMsg(null)
    setResult(null)
    setSelectedStyle(null)
    setTaskSnapshot(null)
    setInputQuality(null)
  }

  return (
    <ErrorBoundary>
      <div className="app-shell" translate="no">
        <main className="page-frame">
          <section className="hero-panel">
            <div className="hero-copy">
              <div className="hero-kicker">v1.1 真实多风格 preset 接入工作台</div>
              <h1>基于文本提示词控制的歌声风格转换系统</h1>
              <p>
                默认主链路为 So-VITS-SVC。当前默认模型为 <strong>final_primary / lain</strong>，Redis/Celery
                负责真实异步任务，StyleSinger 仅保留为高级实验模式，不是默认内容保持型 SVC。
              </p>
            </div>
            <div className="hero-badges">
              <StatusBadge label={mockMode ? 'Mock SVC' : '真实 SVC'} tone={mockMode ? 'warning' : 'success'} />
              <StatusBadge
                label={effectiveTaskBackendMode === 'celery' ? 'Celery / Redis' : '本地任务'}
                tone={effectiveTaskBackendMode === 'celery' ? 'success' : 'neutral'}
              />
              <StatusBadge
                label={
                  gpuStatus === 'visible'
                    ? 'GPU 可见'
                    : gpuStatus === 'missing'
                      ? 'GPU 不可见'
                      : 'GPU 未检测'
                }
                tone={gpuStatus === 'visible' ? 'success' : gpuStatus === 'missing' ? 'warning' : 'neutral'}
              />
              <StatusBadge
                label={currentResultMetadata?.adapter_mode === 'trained' ? 'Adapter trained' : 'Adapter trained 已接入'}
                tone={currentResultMetadata?.adapter_mode === 'trained' ? 'success' : 'primary'}
              />
            </div>
          </section>

          <section className="surface-card">
            <div className="section-header">
              <div>
                <div className="section-kicker">Demo Workspace</div>
                <h2>正式演示工作台</h2>
                <p>左侧准备输入与风格提示，右侧查看任务状态并启动默认 SVC 转换。</p>
              </div>
              {(inputAudio || result) && (
                <button type="button" className="secondary-button" onClick={resetApp} disabled={isUploading || isConverting}>
                  重置演示
                </button>
              )}
            </div>

            <div className="workspace-grid">
              <div className="workspace-left">
                <article className="subcard">
                  <div className="subcard-header">
                    <h3>上传音频</h3>
                    <span className="subcard-tag">/api/v1/upload</span>
                  </div>
                  {!inputAudio ? (
                    <FileUpload onFileSelect={handleFileSelect} disabled={isUploading || isConverting} />
                  ) : (
                    <div className="uploaded-summary">
                      <div className="uploaded-title-row">
                        <div>
                          <div className="uploaded-title">{inputAudio.name}</div>
                          <div className="muted-text">{formatBytes(inputAudio.file.size)}</div>
                        </div>
                        <StatusBadge label={vocalsId ? '已就绪' : '处理中'} tone={vocalsId ? 'success' : 'neutral'} />
                      </div>
                      <label className="toggle-row">
                        <input
                          type="checkbox"
                          checked={isVocalOnly}
                          onChange={(event) => setIsVocalOnly(event.target.checked)}
                        />
                        <span>输入已是纯人声/干声，跳过人声分离</span>
                      </label>
                      {vocalsId && uploadedVocalOnly !== null && uploadedVocalOnly !== isVocalOnly && (
                        <div className="inline-text warning-text">更改该选项将在重新上传后生效。</div>
                      )}
                      {isVocalOnly && (
                        <Notice tone="warning">
                          如果当前上传的是完整歌曲而不是干声，跳过人声分离会把伴奏一并送入 SVC，明显增加跑调、杂音和风格失真风险。
                        </Notice>
                      )}
                    </div>
                  )}

                  {inputQuality && (
                    <div className={`quality-panel quality-${inputQuality.quality_level}`}>
                      <div className="quality-header">
                        <div>
                          <div className="field-label">输入质量</div>
                          <div className="quality-title">{formatQualityLabel(inputQuality.quality_level)}</div>
                        </div>
                        <StatusBadge label={qualityChipLabel(inputQuality.quality_level)} tone={qualityTone(inputQuality.quality_level)} />
                      </div>
                      <div className="metric-grid compact">
                        <MetricItem label="时长" value={formatNullableNumber(inputQuality.duration, 's')} />
                        <MetricItem label="采样率" value={formatNullableNumber(inputQuality.sample_rate, 'Hz', 0)} />
                        <MetricItem label="声道" value={formatNullableNumber(inputQuality.channels, '', 0)} />
                        <MetricItem label="静音比例" value={formatNullableNumber(inputQuality.silence_ratio)} />
                      </div>
                      {inputQuality.warnings.length > 0 ? (
                        <div className="warning-list">
                          {inputQuality.warnings.map((warning) => (
                            <div key={warning} className="warning-item">
                              <ShieldAlert className="mini-icon" />
                              <span>{warning}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="muted-text">当前输入质量没有检测到明显风险。</div>
                      )}
                      {inputQuality.quality_level === 'bad' && (
                        <Notice tone="warning">输入质量较差，但不会阻止转换；建议在答辩演示前优先换用更干净的人声片段。</Notice>
                      )}
                    </div>
                  )}
                </article>

                <article className="subcard">
                  <div className="subcard-header">
                    <h3>文本提示词</h3>
                    <span className="subcard-tag">TextStyleEncoder + Adapter</span>
                  </div>
                  <label className="field-label" htmlFor="prompt-textarea">
                    目标风格描述
                  </label>
                  <textarea
                    id="prompt-textarea"
                    aria-label="style-prompt"
                    className="styled-textarea"
                    value={promptText}
                    onChange={(event) => setPromptText(event.target.value)}
                    disabled={isConverting}
                    placeholder="例如：清亮、少年感、带一点气声"
                  />
                  <div className="tag-row">
                    {STYLE_PRESETS.map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        className="tag-button"
                        onClick={() => appendPromptTag(preset)}
                        disabled={isConverting}
                      >
                        {preset}
                      </button>
                    ))}
                  </div>
                  {promptConflict && <Notice tone="warning">{promptConflict}</Notice>}
                  {promptError && <div className="inline-text warning-text">{promptError}</div>}

                  <details
                    className="inline-details"
                    open={advancedParamsOpen}
                    onToggle={(event) => setAdvancedParamsOpen((event.currentTarget as HTMLDetailsElement).open)}
                  >
                    <summary>
                      <span>高级转换参数</span>
                      <ChevronDown className={`summary-icon ${advancedParamsOpen ? 'open' : ''}`} />
                    </summary>
                    <div className="advanced-params-grid">
                      <label className="form-field">
                        <span className="field-label">style_strength</span>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={styleStrength}
                          onChange={(event) => setStyleStrength(Number.parseFloat(event.target.value))}
                          disabled={isConverting}
                        />
                        <span className="field-help">当前值：{styleStrength.toFixed(2)}</span>
                      </label>

                      <label className="form-field">
                        <span className="field-label">transpose</span>
                        <input
                          type="number"
                          min={-24}
                          max={24}
                          value={transpose}
                          onChange={(event) => setTranspose(Number.parseInt(event.target.value || '0', 10))}
                          disabled={isConverting}
                          className="text-input"
                        />
                        <span className="field-help">单位：半音，后端继续使用现有安全校验。</span>
                      </label>

                      <label className="form-field">
                        <span className="field-label">model_preset_id</span>
                        <select
                          value={modelPresetId}
                          onChange={(event) => setModelPresetId(event.target.value)}
                          disabled={isConverting}
                          className="text-input"
                        >
                          {modelPresets.map((preset) => (
                            <option key={preset.preset_id} value={preset.preset_id}>
                              {formatPresetOptionLabel(preset)}
                            </option>
                          ))}
                        </select>
                        <span className="field-help">
                          默认保持 `final_primary`；`tech_villager` 仅作为技术 fallback，不会被默认选中。
                        </span>
                        {activePreset && (
                          <div className="preset-meta-card">
                            <strong>{activePreset.display_name}</strong>
                            <span>{`状态：${activePresetStatusLabel}`}</span>
                            <span>{`speaker：${activePreset.speaker || 'n/a'}`}</span>
                            <span>{`source_repo：${activePreset.source_repo || 'n/a'}`}</span>
                            <span>{`license：${activePreset.license || 'license_unknown'}`}</span>
                          </div>
                        )}
                      </label>

                      <label className="form-field">
                        <span className="field-label">f0_method</span>
                        <select value={f0Method} onChange={(event) => setF0Method(event.target.value)} disabled={isConverting} className="text-input">
                          <option value="rmvpe">rmvpe</option>
                          <option value="system_default">system_default</option>
                          <option value="harvest">harvest</option>
                          <option value="dio">dio</option>
                        </select>
                        <span className="field-help">若当前环境不支持 rmvpe，系统会记录 fallback_reason，并回退到当前集成默认值。</span>
                      </label>

                      <label className="form-field">
                        <span className="field-label">auto_predict_f0</span>
                        <input type="checkbox" checked={autoPredictF0} onChange={(event) => setAutoPredictF0(event.target.checked)} disabled={isConverting} />
                        <span className="field-help">默认 false。若当前 CLI 不支持，该参数会记录到 debug 产物但不强行透传。</span>
                      </label>

                      <label className="form-field">
                        <span className="field-label">slice_db</span>
                        <input
                          type="number"
                          min={-80}
                          max={0}
                          step="1"
                          value={sliceDb}
                          onChange={(event) => setSliceDb(Number.parseFloat(event.target.value || '-40'))}
                          disabled={isConverting}
                          className="text-input"
                        />
                      </label>

                      <label className="form-field">
                        <span className="field-label">clip_seconds</span>
                        <input
                          type="number"
                          min={0}
                          max={30}
                          step="0.5"
                          value={clipSeconds}
                          onChange={(event) => setClipSeconds(Number.parseFloat(event.target.value || '0'))}
                          disabled={isConverting}
                          className="text-input"
                        />
                      </label>

                      <label className="form-field">
                        <span className="field-label">pad_seconds</span>
                        <input
                          type="number"
                          min={0}
                          max={5}
                          step="0.1"
                          value={padSeconds}
                          onChange={(event) => setPadSeconds(Number.parseFloat(event.target.value || '0.5'))}
                          disabled={isConverting}
                          className="text-input"
                        />
                      </label>

                      <label className="form-field">
                        <span className="field-label">allow_preset_fallback</span>
                        <input
                          type="checkbox"
                          checked={allowPresetFallback}
                          onChange={(event) => setAllowPresetFallback(event.target.checked)}
                          disabled={isConverting}
                        />
                        <span className="field-help">默认关闭。开启后仅用于演示续跑，会明确标记请求 preset 与实际使用 preset。</span>
                      </label>
                    </div>
                  </details>
                </article>
              </div>

              <div className="workspace-right">
                <article className="subcard task-card">
                  <div className="subcard-header">
                    <h3>任务状态</h3>
                    <StatusBadge label={formatTaskStatusLabel(taskSnapshot?.status ?? status)} tone={badgeToneForStatus(taskSnapshot?.status ?? status)} />
                  </div>

                  <div className="metric-grid">
                    <MetricItem label="任务阶段" value={getStageLabel(taskSnapshot?.stage)} />
                    <MetricItem label="当前进度" value={`${taskProgress}%`} />
                    <MetricItem label="任务后端" value={formatTaskBackendMode(effectiveTaskBackendMode)} />
                    <MetricItem label="默认模型" value={`${activePreset?.preset_id ?? 'final_primary'} / ${activePreset?.speaker ?? 'lain'}`} />
                    <MetricItem label="preset 已配置" value={formatBool(currentResultMetadata?.model_preset_ready ?? activePresetConfigured)} />
                    <MetricItem label="请求风格 preset" value={String(requestedModelPresetId ?? 'n/a')} />
                    <MetricItem label="实际使用 preset" value={String(effectiveModelPresetId ?? 'n/a')} />
                    <MetricItem label="发生 fallback" value={formatBool(presetFallbackUsed)} />
                    <MetricItem label="f0_method" value={String(effectiveF0Method ?? 'system_default')} />
                    <MetricItem label="auto_predict_f0" value={formatBool(effectiveAutoPredictF0)} />
                    <MetricItem label="adapter_mode" value={formatAdapterMode(currentResultMetadata?.adapter_mode)} />
                  </div>

                  <div className="config-summary">
                    <SummaryPill label="style_strength" value={styleStrength.toFixed(2)} />
                    <SummaryPill label="transpose" value={String(transpose)} />
                    <SummaryPill label="model_preset_id" value={modelPresetId} />
                    <SummaryPill label="f0_method" value={f0Method} />
                    <SummaryPill label="allow_fallback" value={allowPresetFallback ? 'true' : 'false'} />
                  </div>

                  {mockMode ? (
                    <Notice tone="warning">当前处于 Mock SVC，只适合流程演示；要展示真实效果，请确保后端返回真实 SVC 模式。</Notice>
                  ) : (
                    <Notice tone="success">当前目标为真实本地 So-VITS-SVC 推理，默认模型为 final_primary/lain。</Notice>
                  )}

                  {unconfiguredPresetNotice && <Notice tone="warning">{unconfiguredPresetNotice}</Notice>}

                  {presetFallbackUsed && (
                    <Notice tone="warning">
                      {currentResultMetadata?.preset_fallback_reason ||
                        '当前提示词匹配专用风格 preset，但该 preset 尚未绑定可用 SVC 模型；本次已回退到 final_primary/lain，结果不代表该专用风格真实效果。'}
                    </Notice>
                  )}

                  {selectedStyleNeedsDedicatedPreset && !selectedStylePresetReady && (
                    <Notice tone="warning">
                      当前提示词匹配“{selectedStyle?.style_label ?? selectedStyle?.description ?? '目标风格'}”风格，但该风格尚未绑定可用 SVC 目标模型；当前不会伪装为该风格转换。
                    </Notice>
                  )}

                  {selectedStyleNeedsDedicatedPreset && selectedStylePresetReady && (
                    <Notice tone="success">当前提示词已命中专用目标模型，可针对该风格进行更有针对性的 SVC 转换。</Notice>
                  )}

                  <Notice tone="info">
                    当前转换效果主要受目标模型、输入音频质量、F0 提取质量以及人声分离质量影响。
                  </Notice>

                  <Notice tone="info">提升建议：使用更匹配的目标模型、纯净干声、合适的 F0 方法与转调参数。</Notice>

                  <div className="progress-track" aria-hidden="true">
                    <div className="progress-fill" style={{ width: `${taskProgress}%` }} />
                  </div>

                  <div className="task-message">{taskSnapshot?.message || taskStatusMsg || '等待上传音频并输入提示词。'}</div>

                  {errorMsg && <div className="error-banner">{errorMsg}</div>}

                  <button type="button" className="primary-button" onClick={handleSvcConvert} disabled={!canStartConversion}>
                    {isConverting ? '转换中…' : status === AppStatus.COMPLETED ? '再次转换' : '开始转换'}
                  </button>
                </article>
              </div>
            </div>
          </section>

          <section className="surface-card">
            <div className="section-header">
              <div>
                <div className="section-kicker">Audio Compare</div>
                <h2>A/B 波形对比</h2>
                <p>上传成功后显示原始音频波形，转换成功后自动补齐转换波形，并提供统一播放控制。</p>
              </div>
            </div>
            <AudioComparePanel
              originalUrl={result?.originalUrl || inputAudio?.url || null}
              convertedUrl={result?.convertedUrl || null}
              originalLabel={inputAudio?.name ? `原始音频 · ${inputAudio.name}` : '原始音频'}
              convertedLabel={
                result?.convertedUrl
                  ? `转换结果 · ${currentResultMetadata?.model_preset_id ?? modelPresetId}`
                  : '转换音频'
              }
              downloadUrl={result?.convertedUrl || null}
              downloadFilename={`converted_${basenamePath(inputAudio?.name || 'result.wav')}`}
            />
          </section>

          <details
            className="surface-card details-shell"
            open={techDetailsOpen}
            onToggle={(event) => setTechDetailsOpen((event.currentTarget as HTMLDetailsElement).open)}
          >
            <summary className="details-summary">
              <div>
                <div className="section-kicker">Advanced Details</div>
                <h2>查看技术详情</h2>
                <p>这里集中放 Adapter、audio_quality、GPU telemetry 和高级实验入口，不干扰主演示流程。</p>
              </div>
              <ChevronDown className={`summary-icon ${techDetailsOpen ? 'open' : ''}`} />
            </summary>

            <div className="details-grid">
              <article className="detail-card">
                <div className="detail-card-header">
                  <Sparkles className="detail-icon" />
                  <h3>Adapter 与模型说明</h3>
                </div>
                <p className="muted-text">
                  当前 TextStyleAdapter 是训练型参数级控制，不是 So-VITS-SVC 网络内部 Bias/Scale 注入。
                </p>
                <div className="metric-grid compact">
                  <MetricItem label="adapter_mode" value={formatAdapterMode(currentResultMetadata?.adapter_mode)} />
                  <MetricItem label="adapter_version" value={String(currentResultMetadata?.adapter_version ?? '待任务结果')} />
                  <MetricItem label="text encoding" value={formatTextEncodingStatus(currentResultMetadata)} />
                  <MetricItem label="effective strength" value={formatNullableNumber(currentResultMetadata?.effective_style_strength ?? styleStrength)} />
                  <MetricItem label="f0_method" value={String(effectiveF0Method ?? 'system_default')} />
                  <MetricItem label="auto_predict_f0" value={formatBool(effectiveAutoPredictF0)} />
                </div>
                {selectedStyle ? (
                  <div className="selected-style-card">
                    <div className="field-label">selected_style</div>
                    <div className="style-reason">{String(selectedStyle.reason ?? '暂无风格匹配说明。')}</div>
                    <div className="config-summary">
                      <SummaryPill label="style_id" value={String(selectedStyle.style_id ?? 'n/a')} />
                      <SummaryPill label="preset" value={String(selectedStyle.model_preset_id ?? currentResultMetadata?.model_preset_id ?? 'n/a')} />
                      <SummaryPill label="transpose" value={String(selectedStyle.transpose ?? transpose)} />
                      <SummaryPill
                        label="dedicated_model"
                        value={selectedStyle.current_style_has_dedicated_model ? (selectedStyle.model_preset_ready ? 'ready' : 'missing') : 'baseline'}
                      />
                    </div>
                    <div className="muted-text">{selectedStyle.model_preset_notice ?? '当前风格匹配信息待任务结果更新。'}</div>
                  </div>
                ) : (
                  <div className="muted-text">完成一次任务后，会在这里显示 selected_style 与 Adapter 解释信息。</div>
                )}
              </article>

              <article className="detail-card">
                <div className="detail-card-header">
                  <Wand2 className="detail-icon" />
                  <h3>audio_quality</h3>
                </div>
                <div className="detail-section">
                  <div className="field-label">上传输入质量</div>
                  <div className="metric-grid compact">
                    <MetricItem label="quality_level" value={formatQualityLabel(inputQuality?.quality_level ?? null)} />
                    <MetricItem label="rms" value={formatNullableNumber(inputQuality?.rms)} />
                    <MetricItem label="peak" value={formatNullableNumber(inputQuality?.peak)} />
                    <MetricItem label="low_energy_ratio" value={formatNullableNumber(inputQuality?.low_energy_ratio)} />
                  </div>
                </div>
                <div className="detail-section">
                  <div className="field-label">输出摘要</div>
                  <div className="metric-grid compact">
                    <MetricItem
                      label="duration_consistency"
                      value={formatNullableNumber(currentResultMetadata?.audio_quality_summary?.duration_consistency)}
                    />
                    <MetricItem
                      label="low_energy_ratio"
                      value={formatNullableNumber(currentResultMetadata?.audio_quality_summary?.low_energy_ratio)}
                    />
                    <MetricItem
                      label="possible_dropouts"
                      value={formatBool(currentResultMetadata?.audio_quality_summary?.possible_dropouts)}
                    />
                    <MetricItem
                      label="report_path"
                      value={String(currentResultMetadata?.audio_quality_report_path ?? '待生成')}
                    />
                  </div>
                </div>
              </article>

              <article className="detail-card">
                <div className="detail-card-header">
                  <Cpu className="detail-icon" />
                  <h3>GPU telemetry</h3>
                </div>
                <div className="metric-grid compact">
                  <MetricItem label="device" value={String(currentResultMetadata?.device ?? sovitsCheck?.SOVITS_DEVICE ?? '未检测')} />
                  <MetricItem label="torch cuda" value={formatBool(sovitsCheck?.torch_cuda_available)} />
                  <MetricItem label="backend" value={formatTaskBackendMode(effectiveTaskBackendMode)} />
                  <MetricItem label="model display" value={String(currentResultMetadata?.model_display_name ?? activePreset?.display_name ?? '待任务结果')} />
                </div>
                <div className="path-box">{currentResultMetadata?.gpu_telemetry_debug_path ?? '任务完成后将在这里显示 GPU telemetry 路径。'}</div>
                <div className="muted-text">GPU 证据请以 `gpu_telemetry.txt` 与 `sovits_command.txt` 为准，不直接把调试 JSON 暴露到主演示区。</div>
              </article>
            </div>

            <details
              className="nested-details"
              open={styleSingerOpen}
              onToggle={(event) => setStyleSingerOpen((event.currentTarget as HTMLDetailsElement).open)}
            >
              <summary>
                <div>
                  <h3>StyleSinger 高级实验模式</h3>
                  <p>非默认内容保持型 SVC，仅用于 metadata / 四维特征实验，不替代当前 So-VITS-SVC 主链路。</p>
                </div>
                <ChevronDown className={`summary-icon ${styleSingerOpen ? 'open' : ''}`} />
              </summary>
              <div className="nested-content">
                <div className="button-row">
                  <button type="button" className="secondary-button" onClick={handleExtractFeatures} disabled={!inputAudio || isConverting || isUploading}>
                    extract_features
                  </button>
                  <button type="button" className="secondary-button" onClick={handleStyleSingerConvert} disabled={!inputAudio || isConverting || isUploading}>
                    使用 StyleSinger 高级模式转换
                  </button>
                </div>
                {featureSource && <Notice tone="info">特征来源：{featureSource}</Notice>}
                {featureQualityMessage && <Notice tone="warning">{featureQualityMessage}</Notice>}
                <div className="feature-grid">
                  <FeatureField label="ph" value={phSeq} />
                  <FeatureField label="note" value={noteSeq} />
                  <FeatureField label="note_dur" value={noteDurSeq} />
                  <FeatureField label="note_type" value={noteTypeSeq} />
                </div>
                {featureDebugArtifacts && (
                  <div className="link-row">
                    {featureDebugArtifacts.extracted_features ? (
                      <a href={featureDebugArtifacts.extracted_features} target="_blank" rel="noreferrer">
                        下载 extracted_features.json
                      </a>
                    ) : null}
                    {featureDebugArtifacts.quality_report ? (
                      <a href={featureDebugArtifacts.quality_report} target="_blank" rel="noreferrer">
                        下载 quality_report.json
                      </a>
                    ) : null}
                  </div>
                )}
              </div>
            </details>
          </details>
        </main>
      </div>
    </ErrorBoundary>
  )
}

function StatusBadge({
  label,
  tone,
}: {
  label: string
  tone: 'primary' | 'success' | 'warning' | 'neutral' | 'danger'
}) {
  return <span className={`status-badge status-badge-${tone}`}>{label}</span>
}

function Notice({
  tone,
  children,
}: {
  tone: 'success' | 'warning' | 'error' | 'info'
  children: ReactNode
}) {
  return <div className={`notice notice-${tone}`}>{children}</div>
}

function MetricItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function SummaryPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="summary-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function FeatureField({ label, value }: { label: string; value: string }) {
  return (
    <label className="feature-field">
      <span className="field-label">{label}</span>
      <textarea readOnly value={value} className="feature-textarea" />
    </label>
  )
}

function normalizeResultMetadata(taskData?: TaskResponse | null): ResultMetadata {
  const taskMeta = (taskData?.result_metadata ?? taskData?.engine_details ?? {}) as Record<string, unknown>
  return {
    inference_mode: stringOrNull(taskMeta.inference_mode ?? taskData?.inference_mode),
    mock_enabled: coerceBoolean(taskMeta.mock_enabled ?? taskData?.mock_enabled),
    model_path: stringOrNull(taskMeta.model_path ?? taskData?.model_path),
    config_path: stringOrNull(taskMeta.config_path ?? taskData?.config_path),
    model_preset_id: stringOrNull(taskMeta.model_preset_id ?? taskData?.model_preset_id),
    requested_model_preset_id: stringOrNull(taskMeta.requested_model_preset_id ?? taskData?.requested_model_preset_id),
    effective_model_preset_id: stringOrNull(taskMeta.effective_model_preset_id ?? taskData?.effective_model_preset_id),
    preset_fallback_used: coerceBoolean(taskMeta.preset_fallback_used ?? taskData?.preset_fallback_used),
    preset_fallback_reason: stringOrNull(taskMeta.preset_fallback_reason ?? taskData?.preset_fallback_reason),
    model_display_name: stringOrNull(taskMeta.model_display_name ?? taskData?.model_display_name),
    source_repo: stringOrNull(taskMeta.source_repo ?? taskData?.source_repo),
    source_url: stringOrNull(taskMeta.source_url ?? taskData?.source_url),
    license: stringOrNull(taskMeta.license ?? taskData?.license),
    install_report_path: stringOrNull(taskMeta.install_report_path ?? taskData?.install_report_path),
    notes: stringOrNull(taskMeta.notes ?? taskData?.notes),
    model_path_basename: stringOrNull(taskMeta.model_path_basename ?? taskData?.model_path_basename),
    config_path_basename: stringOrNull(taskMeta.config_path_basename ?? taskData?.config_path_basename),
    is_demo_quality: coerceBoolean(taskMeta.is_demo_quality ?? taskData?.is_demo_quality),
    is_technical_validation_only: coerceBoolean(taskMeta.is_technical_validation_only ?? taskData?.is_technical_validation_only),
    speaker: stringOrNull(taskMeta.speaker ?? taskData?.speaker),
    device: stringOrNull(taskMeta.device ?? taskData?.device),
    selected_output: stringOrNull(taskMeta.selected_output ?? taskData?.selected_output),
    final_output_path: stringOrNull(taskMeta.final_output_path ?? taskData?.final_output_path),
    return_code: numberOrNull(taskMeta.return_code ?? taskData?.return_code),
    elapsed_seconds: numberOrNull(taskMeta.elapsed_seconds ?? taskData?.elapsed_seconds),
    sovits_command_debug_path: stringOrNull(taskMeta.sovits_command_debug_path ?? taskData?.sovits_command_debug_path),
    gpu_telemetry_debug_path: stringOrNull(taskMeta.gpu_telemetry_debug_path ?? taskData?.gpu_telemetry_debug_path),
    task_backend_mode: stringOrNull(taskMeta.task_backend_mode ?? taskData?.task_backend_mode),
    encoder_model_name: stringOrNull(taskMeta.encoder_model_name ?? taskData?.encoder_model_name),
    embedding_dim: numberOrNull(taskMeta.embedding_dim ?? taskData?.embedding_dim),
    embedding_norm: numberOrNull(taskMeta.embedding_norm ?? taskData?.embedding_norm),
    top_keywords: arrayOfString(taskMeta.top_keywords ?? taskData?.top_keywords),
    text_encoding_status: stringOrNull(taskMeta.text_encoding_status ?? taskData?.text_encoding_status),
    text_encoding_enabled: coerceBoolean(taskMeta.text_encoding_enabled ?? taskData?.text_encoding_enabled),
    adapter_enabled: coerceBoolean(taskMeta.adapter_enabled ?? taskData?.adapter_enabled),
    adapter_mode: stringOrNull(taskMeta.adapter_mode ?? taskData?.adapter_mode),
    adapter_version: stringOrNull(taskMeta.adapter_version ?? taskData?.adapter_version),
    adapter_type: stringOrNull(taskMeta.adapter_type ?? taskData?.adapter_type),
    adapter_checkpoint_path: stringOrNull(taskMeta.adapter_checkpoint_path ?? taskData?.adapter_checkpoint_path),
    control_params_summary: objectOrNull(taskMeta.control_params_summary ?? taskData?.control_params_summary),
    adapter_override_reason: stringOrNull(taskMeta.adapter_override_reason ?? taskData?.adapter_override_reason),
    adapter_fallback_reason: stringOrNull(taskMeta.adapter_fallback_reason ?? taskData?.adapter_fallback_reason),
    audio_quality_summary: objectOrNull(taskMeta.audio_quality_summary ?? taskData?.audio_quality_summary) as ResultMetadata['audio_quality_summary'],
    audio_quality_report_path: stringOrNull(taskMeta.audio_quality_report_path ?? taskData?.audio_quality_report_path),
    text_style_adapter_notice: stringOrNull(taskMeta.text_style_adapter_notice ?? taskData?.text_style_adapter_notice),
    called_inference_main: coerceBoolean(taskMeta.called_inference_main),
    input_quality_summary: objectOrNull(taskMeta.input_quality_summary ?? taskData?.input_quality_summary) as InputQualitySummary | null,
    input_quality_report_path: stringOrNull(taskMeta.input_quality_report_path ?? taskData?.input_quality_report_path),
    effective_style_strength: numberOrNull(taskMeta.effective_style_strength),
    f0_method: stringOrNull(taskMeta.f0_method ?? taskData?.f0_method),
    f0_fallback_reason: stringOrNull(taskMeta.f0_fallback_reason ?? taskData?.f0_fallback_reason),
    auto_predict_f0: coerceBoolean(taskMeta.auto_predict_f0 ?? taskData?.auto_predict_f0),
    slice_db: numberOrNull(taskMeta.slice_db ?? taskData?.slice_db),
    clip_seconds: numberOrNull(taskMeta.clip_seconds ?? taskData?.clip_seconds),
    pad_seconds: numberOrNull(taskMeta.pad_seconds ?? taskData?.pad_seconds),
    conversion_params_path: stringOrNull(taskMeta.conversion_params_path ?? taskData?.conversion_params_path),
    conversion_params_summary: objectOrNull(taskMeta.conversion_params_summary ?? taskData?.conversion_params_summary),
    model_preset_ready: coerceBoolean(taskMeta.model_preset_ready ?? taskData?.model_preset_ready),
    model_preset_configured: coerceBoolean(taskMeta.model_preset_configured ?? taskData?.model_preset_configured),
    smoke_test_passed: coerceBoolean(taskMeta.smoke_test_passed ?? taskData?.smoke_test_passed),
  }
}

function pickPresets(collection: ModelPresetCollection | null): ModelPresetStatus[] {
  const configured = (collection?.presets ?? []).filter((item): item is ModelPresetStatus => Boolean(item?.preset_id))
  if (configured.length > 0) {
    return configured
  }
  return [
    {
      preset_id: 'final_primary',
      display_name: '当前可用默认 So-VITS-SVC 模型',
      ready: true,
      speaker: 'lain',
      style_tags: ['baseline', 'demo'],
      source_repo: 'SuCicada/Lain-so-vits-svc-4.1',
      source_url: 'https://huggingface.co/SuCicada/Lain-so-vits-svc-4.1',
      license: 'gpl',
      is_configured: true,
      is_demo_quality: true,
      smoke_test_passed: true,
      is_technical_validation_only: false,
    },
    {
      preset_id: 'final_male_youth',
      display_name: '少年感男声目标模型',
      ready: false,
      speaker: '',
      style_tags: ['male', 'youth', 'bright'],
      source_repo: '',
      source_url: '',
      license: '',
      is_configured: false,
      is_demo_quality: false,
      smoke_test_passed: false,
      is_technical_validation_only: false,
    },
    {
      preset_id: 'final_male_powerful',
      display_name: '力量感男声目标模型',
      ready: false,
      speaker: '',
      style_tags: ['male', 'powerful', 'thick'],
      source_repo: '',
      source_url: '',
      license: '',
      is_configured: false,
      is_demo_quality: false,
      smoke_test_passed: false,
      is_technical_validation_only: false,
    },
    {
      preset_id: 'final_female_soft',
      display_name: '温柔女声目标模型',
      ready: false,
      speaker: '',
      style_tags: ['female', 'soft', 'breathy'],
      source_repo: '',
      source_url: '',
      license: '',
      is_configured: false,
      is_demo_quality: false,
      smoke_test_passed: false,
      is_technical_validation_only: false,
    },
    {
      preset_id: 'final_female_clear',
      display_name: '清亮女声目标模型',
      ready: false,
      speaker: '',
      style_tags: ['female', 'clear', 'bright'],
      source_repo: '',
      source_url: '',
      license: '',
      is_configured: false,
      is_demo_quality: false,
      smoke_test_passed: false,
      is_technical_validation_only: false,
    },
    {
      preset_id: 'tech_villager',
      display_name: '技术验收模型：Minecraft Villager',
      ready: true,
      speaker: 'villager',
      style_tags: ['technical', 'validation', 'fallback'],
      source_repo: 'Sucial/so-vits-svc4.1-Minecraft_villager',
      source_url: 'https://huggingface.co/Sucial/so-vits-svc4.1-Minecraft_villager',
      license: 'cc-by-nc-sa-4.0',
      is_configured: true,
      is_demo_quality: false,
      smoke_test_passed: true,
      is_technical_validation_only: true,
    },
  ]
}

function getGpuStatus(sovitsCheck: SovitsCheckResponse | null) {
  if (!sovitsCheck) {
    return 'unknown'
  }
  if (sovitsCheck.torch_cuda_available || Number(sovitsCheck.torch_device_count ?? 0) > 0) {
    return 'visible'
  }
  return 'missing'
}

function formatPresetOptionLabel(preset: ModelPresetStatus) {
  const suffix = preset.ready ? '已配置' : '未绑定模型'
  return preset.preset_id === 'tech_villager' ? `tech_villager fallback / ${suffix}` : `${preset.preset_id} / ${suffix}`
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes)) {
    return '0 B'
  }
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function formatQualityLabel(level: string | null | undefined) {
  if (level === 'good') {
    return '良好'
  }
  if (level === 'warn') {
    return '一般'
  }
  if (level === 'bad') {
    return '较差'
  }
  return '待检测'
}

function qualityChipLabel(level: string) {
  if (level === 'good') {
    return '可直接演示'
  }
  if (level === 'warn') {
    return '建议留意'
  }
  return '高风险'
}

function qualityTone(level: string): 'success' | 'warning' | 'danger' | 'neutral' {
  if (level === 'good') {
    return 'success'
  }
  if (level === 'warn') {
    return 'warning'
  }
  if (level === 'bad') {
    return 'danger'
  }
  return 'neutral'
}

function formatTaskStatusLabel(status: string | null | undefined) {
  switch ((status ?? '').toUpperCase()) {
    case AppStatus.IDLE:
      return '待开始'
    case AppStatus.UPLOADING:
      return '上传中'
    case AppStatus.READY_TO_CONVERT:
      return '可转换'
    case AppStatus.CONVERTING:
      return '转换中'
    case AppStatus.COMPLETED:
      return '已完成'
    case AppStatus.ERROR:
      return '出错'
    case 'QUEUED':
      return '排队中'
    case 'RUNNING':
      return '运行中'
    case 'SUCCEEDED':
      return '已完成'
    case 'FAILED':
      return '失败'
    default:
      return status || '待开始'
  }
}

function badgeToneForStatus(status: string | null | undefined): 'primary' | 'success' | 'warning' | 'neutral' | 'danger' {
  const normalized = (status ?? '').toUpperCase()
  if (normalized === AppStatus.COMPLETED || normalized === 'SUCCEEDED') {
    return 'success'
  }
  if (normalized === AppStatus.ERROR || normalized === 'FAILED') {
    return 'danger'
  }
  if (normalized === AppStatus.CONVERTING || normalized === 'RUNNING') {
    return 'primary'
  }
  if (normalized === AppStatus.UPLOADING || normalized === 'QUEUED') {
    return 'warning'
  }
  return 'neutral'
}

function getStageLabel(stage: string | null | undefined) {
  switch (stage) {
    case 'uploaded':
      return '输入已准备'
    case 'separated':
      return '人声已就绪'
    case 'style_selected':
      return '风格已匹配'
    case 'text_encoded':
      return '文本已编码'
    case 'adapter_applied':
      return 'Adapter 已应用'
    case 'inference_running':
      return 'SVC 推理中'
    case 'quality_evaluated':
      return '质量评估中'
    case 'completed':
      return '转换完成'
    case 'failed':
      return '转换失败'
    default:
      return stage || '等待开始'
  }
}

function formatTaskBackendMode(mode: string | null | undefined) {
  if (mode === 'celery') {
    return 'Celery / Redis'
  }
  if (mode === 'local') {
    return 'BackgroundTasks / 本地'
  }
  return mode || '未检测'
}

function formatAdapterMode(mode: string | null | undefined) {
  if (mode === 'trained') {
    return 'trained'
  }
  if (mode === 'rule_based') {
    return 'rule_based'
  }
  return mode || '待任务结果'
}

function formatTextEncodingStatus(metadata: ResultMetadata | null | undefined) {
  if (metadata?.text_encoding_enabled && metadata?.text_encoding_status) {
    return metadata.text_encoding_status
  }
  if (metadata?.text_encoding_status) {
    return metadata.text_encoding_status
  }
  return '待任务结果'
}

function formatNullableNumber(value: number | null | undefined, unit = '', digits = 4) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 'n/a'
  }
  const formatted = digits === 0 ? value.toFixed(0) : value.toFixed(digits)
  return unit ? `${formatted}${unit}` : formatted
}

function formatBool(value: boolean | null | undefined) {
  if (value === true) {
    return '是'
  }
  if (value === false) {
    return '否'
  }
  return 'n/a'
}

function detectPromptConflict(prompt: string) {
  const normalized = prompt.trim()
  if (!normalized) {
    return null
  }
  if (normalized.includes('男声') && normalized.includes('女声')) {
    return '提示词同时包含“男声”和“女声”，可能让风格匹配变得不稳定。'
  }
  return null
}

function basenamePath(path: string) {
  const normalized = path.replace(/\\/g, '/')
  const parts = normalized.split('/')
  return parts[parts.length - 1] || path
}

function readAxiosMessage(error: unknown, fallback: string) {
  const responseMessage = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  if (typeof responseMessage === 'string' && responseMessage.trim()) {
    return responseMessage
  }
  const message = (error as { message?: string })?.message
  if (typeof message === 'string' && message.trim()) {
    return message
  }
  return fallback
}

function coerceBoolean(value: unknown) {
  return typeof value === 'boolean' ? value : null
}

function stringOrNull(value: unknown) {
  return typeof value === 'string' && value.trim() ? value : null
}

function numberOrNull(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function arrayOfString(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : null
}

function objectOrNull(value: unknown) {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null
}

export default App
