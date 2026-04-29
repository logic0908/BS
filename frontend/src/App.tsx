import { Component, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import axios from 'axios'
import { ChevronDown, Download, ShieldCheck } from 'lucide-react'

import './App.css'
import { AppStatus } from './types'
import type { AudioFile, ProcessingResult } from './types'
import FileUpload from './components/FileUpload'
import StyleControls from './components/StyleControls'
import WaveformPlayer from './components/WaveformPlayer'

type TaskResponse = {
  task_id?: string
  engine?: string
  status?: string
  progress?: number
  stage?: string
  message?: string
  selected_style?: Record<string, unknown> | null
  result_url?: string | null
  error?: unknown
  inference_mode?: string | null
  engine_details?: Record<string, unknown> | null
  result_metadata?: Record<string, unknown> | null
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
  model_preset_id?: string | null
  model_display_name?: string | null
  source_repo?: string | null
  license?: string | null
  model_path_basename?: string | null
  config_path_basename?: string | null
  is_demo_quality?: boolean | null
  is_technical_validation_only?: boolean | null
}

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
        <div className="app-shell error-shell" translate="no">
          <div className="card error-card">
            <h2>页面渲染出错了</h2>
            <pre>{this.state.error?.message}</pre>
            <button type="button" className="primary-button" onClick={() => window.location.reload()}>
              刷新页面
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function App() {
  const [systemHealth, setSystemHealth] = useState<Record<string, unknown> | null>(null)
  const [sovitsCheck, setSovitsCheck] = useState<Record<string, unknown> | null>(null)
  const [promptText, setPromptText] = useState('')
  const [styleStrength, setStyleStrength] = useState(0.65)
  const [isVocalOnly, setIsVocalOnly] = useState(false)
  const [uploadedVocalOnly, setUploadedVocalOnly] = useState<boolean | null>(null)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [systemPanelOpen, setSystemPanelOpen] = useState(false)
  const [debugPanelOpen, setDebugPanelOpen] = useState(false)
  const [phSeq, setPhSeq] = useState('')
  const [noteSeq, setNoteSeq] = useState('')
  const [noteDurSeq, setNoteDurSeq] = useState('')
  const [noteTypeSeq, setNoteTypeSeq] = useState('')
  const [featureSource, setFeatureSource] = useState<string | null>(null)
  const [featureDebugArtifacts, setFeatureDebugArtifacts] = useState<DebugArtifacts | null>(null)
  const [featureQualityMessage, setFeatureQualityMessage] = useState<string | null>(null)

  const [status, setStatus] = useState<AppStatus>(AppStatus.IDLE)
  const [inputAudio, setInputAudio] = useState<AudioFile | null>(null)
  const [vocalsId, setVocalsId] = useState<string | null>(null)
  const [vocalsPreviewUrl, setVocalsPreviewUrl] = useState<string | null>(null)
  const [taskStatusMsg, setTaskStatusMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [result, setResult] = useState<ProcessingResult | null>(null)
  const [selectedStyle, setSelectedStyle] = useState<Record<string, unknown> | null>(null)
  const [taskSnapshot, setTaskSnapshot] = useState<TaskResponse | null>(null)

  const isUploading = status === AppStatus.UPLOADING
  const isConverting = status === AppStatus.CONVERTING
  const promptError = !promptText.trim() ? '请先输入目标风格描述' : null
  const mockMode = typeof sovitsCheck?.SOVITS_MOCK === 'boolean' ? Boolean(sovitsCheck.SOVITS_MOCK) : null
  const gpuStatus = getGpuStatus(sovitsCheck)
  const canStartConversion = Boolean(vocalsId) && Boolean(promptText.trim()) && !isUploading && !isConverting
  const convertActionLabel =
    status === AppStatus.ERROR ? '重新转换' : status === AppStatus.COMPLETED ? '再次转换' : '开始转换'
  const taskErrorInfo = useMemo(() => normalizeTaskError(taskSnapshot?.error), [taskSnapshot?.error])
  const taskProgress = Math.max(0, Math.min(100, Number(taskSnapshot?.progress ?? 0)))
  const promptConflict = useMemo(() => detectPromptConflict(promptText), [promptText])
  const currentResultMetadata = useMemo(
    () => result?.metadata ?? normalizeResultMetadata(taskSnapshot),
    [result?.metadata, taskSnapshot],
  )

  useEffect(() => {
    let cancelled = false

    const loadSystemStatus = async () => {
      try {
        const [healthResponse, checkResponse] = await Promise.all([
          axios.get('/api/v1/system/health'),
          axios.get('/api/v1/system/sovits-check'),
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

  const handleFileSelect = async (file: File) => {
    if (file.size > 10 * 1024 * 1024) {
      setErrorMsg('上传音频文件大小不能超过 10MB')
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
    setVocalsPreviewUrl(null)
    setTaskSnapshot(null)
    setSelectedStyle(null)
    setFeatureDebugArtifacts(null)
    setFeatureQualityMessage(null)
    setErrorMsg(null)
    setStatus(AppStatus.UPLOADING)
    setTaskStatusMsg(isVocalOnly ? '正在标准化干声...' : '正在分离/标准化人声...')

    try {
      const formData = new FormData()
      formData.append('audio', file)
      formData.append('is_vocal_only', String(isVocalOnly))
      const response = await axios.post('/api/v1/upload', formData)
      setVocalsId(response.data?.vocals_id ?? null)
      setUploadedVocalOnly(Boolean(response.data?.is_vocal_only))
      setVocalsPreviewUrl(typeof response.data?.vocals_url === 'string' ? response.data.vocals_url : null)
      setTaskStatusMsg('音频上传完成，可以开始 SVC 转换。')
      setStatus(AppStatus.READY_TO_CONVERT)
    } catch (err: unknown) {
      setStatus(AppStatus.ERROR)
      setTaskStatusMsg(null)
      setErrorMsg(readAxiosMessage(err, '上传或预处理失败，请检查后端服务'))
    }
  }

  const pollTask = async (taskId: string): Promise<ResultFetchPayload> => {
    for (let i = 0; i < 180; i += 1) {
      const statusResponse = await axios.get(`/api/v1/tasks/${taskId}`)
      const data = (statusResponse.data ?? {}) as TaskResponse
      setTaskSnapshot(data)
      setTaskStatusMsg(typeof data.message === 'string' ? data.message : '正在处理...')
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
    throw new Error('任务超时，请重试')
  }

  const completeWithBlob = (payload: ResultFetchPayload) => {
    const originalUrl = inputAudio?.url
    if (!originalUrl) {
      throw new Error('原始音频缺失')
    }
    const convertedUrl = window.URL.createObjectURL(payload.blob)
    setResult({
      originalUrl,
      convertedUrl,
      metadata: normalizeResultMetadata(payload.taskData),
    })
    setStatus(AppStatus.COMPLETED)
    setTaskStatusMsg('转换完成')
  }

  const handleSvcConvert = async () => {
    if (!vocalsId) {
      setStatus(AppStatus.ERROR)
      setErrorMsg('请先上传音频并完成预处理')
      return
    }
    if (!promptText.trim()) {
      setStatus(AppStatus.ERROR)
      setErrorMsg('请先输入目标风格描述')
      return
    }

    setStatus(AppStatus.CONVERTING)
    setTaskStatusMsg('正在创建 SVC 任务...')
    setTaskSnapshot(null)
    setErrorMsg(null)

    try {
      const response = await axios.post('/api/v1/convert', {
        vocals_id: vocalsId,
        prompt_text: promptText,
        style_strength: styleStrength,
        engine: 'sovits',
      })
      const taskId = response.data?.task_id as string | undefined
      if (!taskId) {
        throw new Error('后端未返回 task_id')
      }
      const payload = await pollTask(taskId)
      completeWithBlob(payload)
    } catch (err: unknown) {
      setStatus(AppStatus.ERROR)
      setErrorMsg(readAxiosMessage(err, 'SVC 转换失败'))
    }
  }

  const handleExtractFeatures = async () => {
    if (!inputAudio?.file) {
      setStatus(AppStatus.ERROR)
      setErrorMsg('请先上传音频')
      return
    }

    setTaskStatusMsg('正在提取 StyleSinger 四维特征...')
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
      setTaskStatusMsg('StyleSinger 四维特征已回填')
    } catch (err: unknown) {
      setStatus(AppStatus.ERROR)
      setErrorMsg(readAxiosMessage(err, '四维特征提取失败'))
    }
  }

  const handleStyleSingerConvert = async () => {
    if (!inputAudio?.file) {
      setStatus(AppStatus.ERROR)
      setErrorMsg('请先上传音频')
      return
    }
    if (!promptText.trim()) {
      setStatus(AppStatus.ERROR)
      setErrorMsg('高级模式也需要风格描述')
      return
    }

    setStatus(AppStatus.CONVERTING)
    setTaskStatusMsg('正在创建 StyleSinger 高级任务...')
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
        throw new Error('后端未返回 task_id')
      }
      const payload = await pollTask(taskId)
      completeWithBlob(payload)
    } catch (err: unknown) {
      setStatus(AppStatus.ERROR)
      setErrorMsg(readAxiosMessage(err, 'StyleSinger 高级模式转换失败'))
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
    setPromptText('')
    setStyleStrength(0.65)
    setIsVocalOnly(false)
    setAdvancedOpen(false)
    setSystemPanelOpen(false)
    setDebugPanelOpen(false)
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
    setUploadedVocalOnly(null)
    setVocalsPreviewUrl(null)
    setTaskStatusMsg(null)
    setErrorMsg(null)
    setResult(null)
    setSelectedStyle(null)
    setTaskSnapshot(null)
  }

  return (
    <ErrorBoundary>
      <div className="app-shell" translate="no">
        <main className="app-container">
          <section className="hero-card">
            <div className="hero-copy">
              <h1>基于文本提示词控制的歌声风格转换系统</h1>
              <p>
                上传一段人声或歌曲片段，输入目标风格描述，系统将尽量保留原唱内容与旋律，并转换音色与演唱风格。
              </p>
            </div>
            <div className="hero-badges">
              <StatusBadge label="SVC 主链路" tone="primary" />
              <StatusBadge
                label={mockMode === null ? '模式未检测' : mockMode ? 'Mock SVC' : '真实 SVC'}
                tone={mockMode === null ? 'neutral' : mockMode ? 'warning' : 'success'}
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
            </div>
          </section>

          <section className="card workspace-card">
            <div className="section-heading">
              <div>
                <h2>Demo Workspace</h2>
                <p>左侧完成输入控制，右侧查看任务进度与音频工作台 A/B 对比。</p>
              </div>
              {(inputAudio || result) && (
                <button type="button" className="secondary-button" onClick={resetApp} disabled={isUploading || isConverting}>
                  重置演示
                </button>
              )}
            </div>

            <div className="demo-grid">
              <section className="input-panel">
                <article className="step-card">
                  <StepHeader index="1" title="上传音频" description="上传后将调用 /api/v1/upload，得到 vocals_id 并准备主链路输入。" />
                  {!inputAudio ? (
                    <div className="upload-card-shell">
                      <FileUpload onFileSelect={handleFileSelect} disabled={isUploading || isConverting} />
                    </div>
                  ) : (
                    <div className="uploaded-file-card">
                      <div className="file-meta-row">
                        <div>
                          <div className="file-title">{inputAudio.name}</div>
                          <div className="file-subtitle">
                            {formatBytes(inputAudio.file.size)}
                            {inputAudio.duration ? ` · ${inputAudio.duration.toFixed(1)}s` : ''}
                          </div>
                        </div>
                        <span className="mini-status">{vocalsId ? '已上传' : '处理中'}</span>
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
                        <div className="inline-hint warning-text">更改该选项将在重新上传或重新预处理后生效。</div>
                      )}
                      <AudioWorkbenchCard
                        title="原始音频"
                        subtitle={vocalsId ? `vocals_id: ${vocalsId}` : '等待预处理完成'}
                        audioUrl={inputAudio.url}
                        filename={inputAudio.name}
                      />
                      {vocalsPreviewUrl && (
                        <AudioWorkbenchCard
                          title="预处理人声"
                          subtitle="后端返回的 vocals 预处理结果"
                          audioUrl={vocalsPreviewUrl}
                          filename="vocals.wav"
                        />
                      )}
                    </div>
                  )}
                </article>

                <article className="step-card">
                  <StepHeader index="2" title="描述目标风格" description="输入目标风格关键词，系统会根据提示词匹配风格 preset。" />
                  {promptConflict && <Notice tone="warning">存在风格冲突，可能影响匹配。</Notice>}
                  <StyleControls
                    prompt={promptText}
                    setPrompt={setPromptText}
                    intensity={styleStrength}
                    setIntensity={setStyleStrength}
                    onConvert={handleSvcConvert}
                    isLoading={isConverting}
                    disabled={!vocalsId || isUploading || isConverting}
                    onAppendPreset={appendPromptTag}
                    promptError={promptError}
                    actionLabel={convertActionLabel}
                  />
                </article>

                <article className="step-card">
                  <StepHeader index="3" title="开始转换" description="点击后调用 /api/v1/convert，并轮询 /api/v1/tasks/{task_id}。" />
                  <div className="step-note">
                    {canStartConversion
                      ? '已满足转换条件，可以开始 SVC 转换。'
                      : !vocalsId
                        ? '请先上传音频并等待预处理完成。'
                        : '请先输入目标风格描述。'}
                  </div>
                </article>
              </section>

              <section className="result-panel">
                <article className="task-progress-card">
                  <div className="panel-title-row">
                    <div>
                      <h3>任务进度</h3>
                      <p>使用结构化状态展示转换流程，而不是直接显示 JSON。</p>
                    </div>
                    <StatusBadge label={String(taskSnapshot?.status ?? 'idle')} tone={badgeToneForStatus(taskSnapshot?.status)} />
                  </div>

                  {currentResultMetadata?.inference_mode === 'mock' || (currentResultMetadata?.inference_mode == null && mockMode === true) ? (
                    <Notice tone="warning">当前为 Mock SVC，仅验证流程，不代表真实风格转换效果。</Notice>
                  ) : null}
                  {currentResultMetadata?.inference_mode === 'real' || (currentResultMetadata?.inference_mode == null && mockMode === false) ? (
                    <Notice tone="success">当前为真实 So-VITS-SVC 推理模式，将调用 So-VITS-SVC CLI。</Notice>
                  ) : null}
                  {mockMode === false && gpuStatus === 'missing' && (
                    <Notice tone="warning">
                      当前 GPU 对容器不可见，真实推理可能失败；可切回 Mock 模式或检查平台 GPU/驱动/容器挂载。
                    </Notice>
                  )}

                  <div className="task-progress-meta">
                    <div className="progress-meta-item">
                      <span>当前状态</span>
                      <strong>{String(taskSnapshot?.status ?? 'queued')}</strong>
                    </div>
                    <div className="progress-meta-item">
                      <span>当前阶段</span>
                      <strong>{getStageLabel(taskSnapshot?.stage)}</strong>
                    </div>
                    <div className="progress-meta-item">
                      <span>当前进度</span>
                      <strong>{taskProgress}%</strong>
                    </div>
                  </div>

                  {currentResultMetadata?.inference_mode && (
                    <div className="selected-style-grid result-meta-grid">
                      <MetaItem
                        label="当前模型 preset"
                        value={String(currentResultMetadata.model_preset_id ?? 'n/a')}
                      />
                      <MetaItem
                        label="模型显示名"
                        value={String(currentResultMetadata.model_display_name ?? 'n/a')}
                      />
                      <MetaItem
                        label="推理模式"
                        value={currentResultMetadata.inference_mode === 'real' ? '真实 So-VITS-SVC' : 'Mock SVC'}
                      />
                      <MetaItem label="目标 speaker" value={String(currentResultMetadata.speaker ?? 'n/a')} />
                      <MetaItem
                        label="模型 basename"
                        value={String(currentResultMetadata.model_path_basename ?? basenamePath(String(currentResultMetadata.model_path ?? 'n/a')))}
                      />
                      <MetaItem label="source repo" value={String(currentResultMetadata.source_repo ?? 'n/a')} />
                      <MetaItem label="license" value={String(currentResultMetadata.license ?? 'n/a')} />
                      <MetaItem label="demo quality" value={formatBool(currentResultMetadata.is_demo_quality)} />
                      <MetaItem
                        label="真实调用 inference_main.py"
                        value={currentResultMetadata.called_inference_main ? '是' : '否'}
                      />
                    </div>
                  )}
                  {currentResultMetadata?.model_preset_id === 'final_primary' && (
                    <Notice tone="success">当前使用最终演示 SVC 模型。</Notice>
                  )}
                  {currentResultMetadata?.model_preset_id === 'tech_villager' && (
                    <Notice tone="warning">当前使用技术验收模型。</Notice>
                  )}

                  <div className="progress-bar-track">
                    <div className="progress-bar-fill" style={{ width: `${taskProgress}%` }} />
                  </div>

                  <div className="task-message">{taskSnapshot?.message || taskStatusMsg || '等待开始转换'}</div>

                  {taskSnapshot?.status === 'failed' && (
                    <div className="status-message error-state">
                      <div>error.code: {taskErrorInfo.code || 'unknown'}</div>
                      <div>error.message: {taskErrorInfo.message || errorMsg || '转换失败'}</div>
                    </div>
                  )}
                  {errorMsg && taskSnapshot?.status !== 'failed' && <div className="status-message error-state">{errorMsg}</div>}
                </article>

                <article className="card">
                  <div className="panel-title-row">
                    <div>
                      <h3>音频工作台 A/B 对比</h3>
                      <p>对比原始音频与转换结果，适合答辩现场直接试听。</p>
                    </div>
                  </div>

                  <div className="audio-compare-grid">
                    <AudioWorkbenchCard
                      title="原始音频"
                      subtitle={inputAudio?.name || '未上传音频'}
                      audioUrl={result?.originalUrl || inputAudio?.url || null}
                      filename={inputAudio?.name}
                    />
                    <AudioWorkbenchCard
                      title="转换结果"
                      subtitle={result?.convertedUrl ? formatResultSubtitle(currentResultMetadata) : '转换完成后将在这里显示结果音频'}
                      audioUrl={result?.convertedUrl || null}
                      filename={basenamePath(String(currentResultMetadata?.final_output_path ?? 'converted.wav'))}
                      action={
                        result?.convertedUrl ? (
                          <a
                            href={result.convertedUrl}
                            download={`converted_${inputAudio?.name ?? 'result.wav'}`}
                            className="download-button"
                          >
                            <Download className="download-button-icon" />
                            下载 converted.wav
                          </a>
                        ) : undefined
                      }
                    />
                  </div>
                </article>

                <article className="card">
                  <div className="panel-title-row">
                    <div>
                      <h3>风格匹配信息</h3>
                      <p>展示 selected_style 返回结果，便于解释系统为什么选择该风格。</p>
                    </div>
                  </div>

                  {selectedStyle ? (
                    <div className="selected-style-grid">
                      {Number(selectedStyle.match_score ?? 0) === 0 && (
                        <div className="status-message warning-state style-warning-full">
                          提示词未命中风格库，当前使用默认 preset，文本风格未真正生效。
                        </div>
                      )}
                      <MetaItem label="style_id" value={String(selectedStyle.style_id ?? 'n/a')} />
                      <MetaItem label="model_preset_id" value={String(selectedStyle.model_preset_id ?? 'n/a')} />
                      <MetaItem label="model_display_name" value={String(selectedStyle.model_display_name ?? 'n/a')} />
                      <MetaItem label="description" value={String(selectedStyle.description ?? 'n/a')} />
                      <MetaItem label="match_score" value={String(selectedStyle.match_score ?? 'n/a')} />
                      <MetaItem label="matched_keywords" value={formatMatchedKeywords(selectedStyle.matched_keywords)} />
                      <MetaItem label="reason" value={String(selectedStyle.reason ?? 'n/a')} wide />
                    </div>
                  ) : (
                    <div className="placeholder-card">转换完成后将在这里显示 style_id、description、reason 等信息。</div>
                  )}
                </article>
              </section>
            </div>
          </section>

          <details
            className="advanced-panel"
            open={advancedOpen}
            onToggle={(event) => setAdvancedOpen((event.currentTarget as HTMLDetailsElement).open)}
          >
            <summary className="panel-summary">
              <div>
                <h3>高级模式：StyleSinger 乐谱/metadata 分支</h3>
                <p>该分支适用于已知 metadata 或人工四维特征的实验场景；默认 SVC 主链路不依赖 ph/note/note_dur/note_type。</p>
              </div>
              <ChevronDown className={`summary-icon ${advancedOpen ? 'open' : ''}`} />
            </summary>
            <div className="advanced-content">
              <div className="advanced-actions">
                <button type="button" className="secondary-button" onClick={handleExtractFeatures} disabled={!inputAudio || isConverting || isUploading}>
                  extract_features
                </button>
                <button type="button" className="accent-button" onClick={handleStyleSingerConvert} disabled={!inputAudio || isConverting || isUploading}>
                  使用 StyleSinger 高级模式转换
                </button>
              </div>
              <p className="advanced-description">
                可用于 quality report、hard gate fail 排查，以及 metadata/manual features 实验入口。
              </p>
              {featureSource && <div className="status-message info-state">特征来源：{featureSource}</div>}
              {featureQualityMessage && <div className="status-message warning-state">quality report: {featureQualityMessage}</div>}
              <div className="feature-grid">
                <FeatureField label="ph" value={phSeq} />
                <FeatureField label="note" value={noteSeq} />
                <FeatureField label="note_dur" value={noteDurSeq} />
                <FeatureField label="note_type" value={noteTypeSeq} />
              </div>
              {featureDebugArtifacts && (
                <div className="debug-links">
                  {featureDebugArtifacts.extracted_features && (
                    <a href={featureDebugArtifacts.extracted_features} target="_blank" rel="noreferrer">
                      下载 extracted_features.json
                    </a>
                  )}
                  {featureDebugArtifacts.quality_report && (
                    <a href={featureDebugArtifacts.quality_report} target="_blank" rel="noreferrer">
                      下载 quality_report.json
                    </a>
                  )}
                </div>
              )}
            </div>
          </details>

          <details
            className="health-panel"
            open={systemPanelOpen}
            onToggle={(event) => setSystemPanelOpen((event.currentTarget as HTMLDetailsElement).open)}
          >
            <summary className="panel-summary">
              <div className="summary-with-icon">
                <ShieldCheck className="summary-badge-icon" />
                <div>
                  <h3>系统状态与环境诊断</h3>
                  <p>调用 /api/v1/system/health 和 /api/v1/system/sovits-check 展示环境状态。</p>
                </div>
              </div>
              <ChevronDown className={`summary-icon ${systemPanelOpen ? 'open' : ''}`} />
            </summary>
            <div className="health-grid">
              <div className="health-meta-grid">
                <MetaItem label="Python executable" value={String(systemHealth?.python_executable ?? '未检测')} />
                <MetaItem label="SOVITS_MOCK" value={formatMockMode(mockMode)} />
                <MetaItem label="SOVITS_DEVICE" value={String(sovitsCheck?.SOVITS_DEVICE ?? '未检测')} />
                <MetaItem label="repo / model / config" value={formatTripleStatus(sovitsCheck)} />
                <MetaItem label="torch cuda available" value={formatBool(sovitsCheck?.torch_cuda_available)} />
                <MetaItem label="nvidia-smi" value={formatNvidiaSmi(sovitsCheck?.nvidia_smi)} />
              </div>
              <div className="health-import-card">
                <h4>import_status</h4>
                <div className="import-status-grid">{renderImportStatuses(sovitsCheck?.import_status)}</div>
              </div>
            </div>
            {gpuStatus === 'missing' && (
              <Notice tone="warning">当前 GPU 对容器不可见，真实推理可能失败；但系统仍可用于 Mock 演示与 CLI 链路验证。</Notice>
            )}
          </details>

          <details
            className="advanced-panel"
            open={debugPanelOpen}
            onToggle={(event) => setDebugPanelOpen((event.currentTarget as HTMLDetailsElement).open)}
          >
            <summary className="panel-summary">
              <div>
                <h3>Debug artifacts 说明</h3>
                <p>不干扰主演示流程，仅用于说明工程闭环与可追踪性。</p>
              </div>
              <ChevronDown className={`summary-icon ${debugPanelOpen ? 'open' : ''}`} />
            </summary>
            <div className="advanced-content">
              <p className="advanced-description">
                调试文件保存在后端 `runtime/debug/{'{task_id}'}/`，通常包括 `prompt.json`、`selected_style.json`、
                `sovits_command.txt`、`error.json`、`extracted_features.sanitized.json`、`quality_report.json`。
              </p>
              <div className="status-message info-state">
                这些文件用于证明系统在 Mock/真实模式下都具备结构化错误、过程留痕和调试回放能力。
              </div>
            </div>
          </details>
        </main>
      </div>
    </ErrorBoundary>
  )
}

function StepHeader({ index, title, description }: { index: string; title: string; description: string }) {
  return (
    <div className="step-header">
      <div className="step-index">{index}</div>
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
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

function AudioWorkbenchCard({
  title,
  subtitle,
  audioUrl,
  filename,
  action,
}: {
  title: string
  subtitle: string
  audioUrl: string | null
  filename?: string
  action?: ReactNode
}) {
  return (
    <div className="audio-card">
      <div className="audio-card-header">
        <div>
          <h4>{title}</h4>
          <p>{subtitle}</p>
        </div>
        {action}
      </div>
      {audioUrl ? (
        <>
          <audio controls className="audio-player" src={audioUrl} />
          <div className="waveform-shell">
            <WaveformPlayer audioUrl={audioUrl} waveColor="#4f46e5" progressColor="#2563eb" />
          </div>
          {filename && <div className="audio-meta">{filename}</div>}
        </>
      ) : (
        <div className="placeholder-card">音频就绪后将在这里显示播放器。</div>
      )}
    </div>
  )
}

function formatResultSubtitle(metadata: ProcessingResult['metadata'] | undefined) {
  if (!metadata) {
    return 'converted.wav 已生成'
  }
  if (metadata.inference_mode === 'real') {
    return `真实 So-VITS-SVC 输出已生成 · ${basenamePath(String(metadata.selected_output ?? 'selected output'))}`
  }
  if (metadata.inference_mode === 'mock') {
    return 'Mock SVC 输出已生成'
  }
  return 'converted.wav 已生成'
}

function FeatureField({ label, value }: { label: string; value: string }) {
  return (
    <div className="feature-field">
      <div className="feature-label">{label}</div>
      <textarea value={value} readOnly className="feature-textarea" />
    </div>
  )
}

function MetaItem({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={`meta-item ${wide ? 'meta-item-wide' : ''}`}>
      <div className="meta-label">{label}</div>
      <div className="meta-value">{value}</div>
    </div>
  )
}

function Notice({ tone, children }: { tone: 'success' | 'warning' | 'error'; children: ReactNode }) {
  return <div className={`notice notice-${tone}`}>{children}</div>
}

function normalizeResultMetadata(taskData?: TaskResponse | null): ProcessingResult['metadata'] {
  const taskMeta = (taskData?.result_metadata ?? taskData?.engine_details ?? {}) as Record<string, unknown>
  const inferenceModeRaw = taskMeta.inference_mode ?? taskData?.inference_mode
  const inferenceMode = typeof inferenceModeRaw === 'string' && inferenceModeRaw.trim() ? inferenceModeRaw : null
  return {
    inference_mode: inferenceMode,
    mock_enabled: coerceBoolean(taskMeta.mock_enabled ?? taskData?.mock_enabled),
    model_path: stringOrNull(taskMeta.model_path ?? taskData?.model_path),
    config_path: stringOrNull(taskMeta.config_path ?? taskData?.config_path),
    model_preset_id: stringOrNull(taskMeta.model_preset_id ?? taskData?.model_preset_id),
    model_display_name: stringOrNull(taskMeta.model_display_name ?? taskData?.model_display_name),
    source_repo: stringOrNull(taskMeta.source_repo ?? taskData?.source_repo),
    license: stringOrNull(taskMeta.license ?? taskData?.license),
    model_path_basename: stringOrNull(taskMeta.model_path_basename ?? taskData?.model_path_basename),
    config_path_basename: stringOrNull(taskMeta.config_path_basename ?? taskData?.config_path_basename),
    is_demo_quality: coerceBoolean(taskMeta.is_demo_quality ?? taskData?.is_demo_quality),
    is_technical_validation_only: coerceBoolean(
      taskMeta.is_technical_validation_only ?? taskData?.is_technical_validation_only,
    ),
    speaker: stringOrNull(taskMeta.speaker ?? taskData?.speaker),
    device: stringOrNull(taskMeta.device ?? taskData?.device),
    selected_output: stringOrNull(taskMeta.selected_output ?? taskData?.selected_output),
    final_output_path: stringOrNull(taskMeta.final_output_path ?? taskData?.final_output_path),
    return_code: coerceNumber(taskMeta.return_code ?? taskData?.return_code),
    elapsed_seconds: coerceNumber(taskMeta.elapsed_seconds ?? taskData?.elapsed_seconds),
    sovits_command_debug_path: stringOrNull(taskMeta.sovits_command_debug_path ?? taskData?.sovits_command_debug_path),
    called_inference_main:
      inferenceMode === 'real' ? true : inferenceMode === 'mock' ? false : coerceBoolean(taskMeta.called_inference_main),
  }
}

function stringOrNull(value: unknown): string | null {
  if (typeof value !== 'string' || !value.trim()) {
    return null
  }
  return value
}

function coerceBoolean(value: unknown): boolean | null {
  if (typeof value === 'boolean') {
    return value
  }
  if (typeof value === 'string') {
    if (value === 'true') return true
    if (value === 'false') return false
  }
  return null
}

function coerceNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return null
}

function basenamePath(value: string) {
  if (!value || value === 'n/a') {
    return value
  }
  const parts = value.split(/[\\/]/)
  return parts[parts.length - 1] || value
}

function detectPromptConflict(prompt: string) {
  const normalized = prompt.trim()
  if (!normalized) {
    return false
  }
  const clearTerms = ['清亮', '明亮', '清澈']
  const thickTerms = ['厚重', 'powerful', 'thick', 'deep']
  return clearTerms.some((term) => normalized.includes(term)) && thickTerms.some((term) => normalized.includes(term))
}

function renderImportStatuses(importStatus: unknown) {
  if (!importStatus || typeof importStatus !== 'object') {
    return <div className="import-status-row">未获取到依赖检查结果</div>
  }
  return Object.entries(importStatus as Record<string, unknown>).map(([name, value]) => {
    const payload = typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {}
    const ok = Boolean(payload.ok)
    return (
      <div key={name} className="import-status-row">
        <span>{name}</span>
        <strong className={ok ? 'ok-text' : 'error-text'}>{ok ? 'ok' : 'failed'}</strong>
      </div>
    )
  })
}

function getStageLabel(stage: unknown) {
  const map: Record<string, string> = {
    uploaded: '音频已上传',
    separated: '人声预处理完成',
    style_selected: '已匹配目标风格',
    inference_running: '正在进行 SVC 转换',
    completed: '转换完成',
    failed: '转换失败',
  }
  const key = typeof stage === 'string' ? stage : ''
  return map[key] || key || '未开始'
}

function getGpuStatus(sovitsCheck: Record<string, unknown> | null) {
  if (!sovitsCheck) {
    return 'unknown'
  }
  if (Boolean(sovitsCheck.torch_cuda_available)) {
    return 'visible'
  }
  const devices = Array.isArray(sovitsCheck.dev_nvidia_devices) ? sovitsCheck.dev_nvidia_devices : []
  if (devices.length > 0) {
    return 'visible'
  }
  if (sovitsCheck.nvidia_smi) {
    return 'missing'
  }
  return 'unknown'
}

function normalizeTaskError(error: unknown) {
  if (!error || typeof error !== 'object') {
    return { code: '', message: typeof error === 'string' ? error : '' }
  }
  const payload = error as Record<string, unknown>
  return {
    code: typeof payload.code === 'string' ? payload.code : '',
    message: typeof payload.message === 'string' ? payload.message : '',
  }
}

function badgeToneForStatus(status: unknown) {
  if (status === 'succeeded') {
    return 'success' as const
  }
  if (status === 'failed') {
    return 'danger' as const
  }
  if (status === 'running') {
    return 'primary' as const
  }
  if (status === 'queued') {
    return 'neutral' as const
  }
  return 'neutral' as const
}

function formatMatchedKeywords(value: unknown) {
  if (!Array.isArray(value) || value.length === 0) {
    return 'n/a'
  }
  return value.map((item) => String(item)).join('、')
}

function formatBool(value: unknown) {
  return value ? 'true' : 'false'
}

function formatMockMode(value: boolean | null) {
  if (value === null) {
    return '未检测'
  }
  return value ? 'true' : 'false'
}

function formatNvidiaSmi(value: unknown) {
  if (!value || typeof value !== 'object') {
    return '未检测'
  }
  const payload = value as Record<string, unknown>
  return `return_code=${String(payload.return_code ?? 'unknown')}`
}

function formatTripleStatus(sovitsCheck: Record<string, unknown> | null) {
  if (!sovitsCheck) {
    return '未检测'
  }
  return `repo=${formatBool(sovitsCheck.SOVITS_REPO_DIR_exists)} model=${formatBool(sovitsCheck.SOVITS_MODEL_PATH_exists)} config=${formatBool(sovitsCheck.SOVITS_CONFIG_PATH_exists)}`
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
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

function readAxiosMessage(err: unknown, fallback: string) {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') {
      return detail
    }
    if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') {
      return detail.message
    }
  }
  if (err instanceof Error) {
    return err.message
  }
  return fallback
}

export default App
