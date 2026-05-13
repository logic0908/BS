import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'

import './App.css'
import { compareStyleEvidence } from './api/styleAnalysis'
import AudioComparePanel from './components/AudioComparePanel'
import FileUpload from './components/FileUpload'
import KeyMetricsComparePanel from './components/KeyMetricsComparePanel'
import {
  AppStatus,
  STYLE_PROMPT_CHIPS,
  type AudioFile,
  type ConvertResponse,
  type ProcessingResult,
  type ResultMetadata,
  type SovitsCheckResponse,
  type StyleEvidenceCompareResponse,
  type SystemHealthResponse,
  type TaskResponse,
  type UploadResponse,
} from './types'

type StyleEvidenceRequest = {
  inputPath: string
  outputPath: string
  promptText: string
  modelPresetId: string
}

type TaskUpdate = {
  status: string
  stage: string
  progress: number
  message: string
}

const FILE_SIZE_LIMIT = 10 * 1024 * 1024
const DEFAULT_PRESET_ID = 'final_primary'
const DEFAULT_SPEAKER = 'lain'

function App() {
  const [systemHealth, setSystemHealth] = useState<SystemHealthResponse | null>(null)
  const [sovitsCheck, setSovitsCheck] = useState<SovitsCheckResponse | null>(null)

  const [status, setStatus] = useState<AppStatus>(AppStatus.IDLE)
  const [inputAudio, setInputAudio] = useState<AudioFile | null>(null)
  const [uploadInfo, setUploadInfo] = useState<UploadResponse | null>(null)
  const [vocalsId, setVocalsId] = useState<string | null>(null)

  const [promptText, setPromptText] = useState('')

  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskStatus, setTaskStatus] = useState<string>('idle')
  const [taskStage, setTaskStage] = useState<string>('')
  const [taskProgress, setTaskProgress] = useState<number>(0)
  const [statusMessage, setStatusMessage] = useState<string>('等待上传音频。')

  const [result, setResult] = useState<ProcessingResult | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [errorDetails, setErrorDetails] = useState<string | null>(null)

  const [styleEvidenceRequest, setStyleEvidenceRequest] = useState<StyleEvidenceRequest | null>(null)
  const [styleEvidence, setStyleEvidence] = useState<StyleEvidenceCompareResponse | null>(null)
  const [styleEvidenceWarning, setStyleEvidenceWarning] = useState<string | null>(null)

  const isUploading = status === AppStatus.UPLOADING
  const isConverting = status === AppStatus.CONVERTING

  const modelPresetId = useMemo(() => {
    const fromHealth = systemHealth?.svc_model_presets?.active_preset_id?.trim()
    if (fromHealth) return fromHealth
    const fromCheck = sovitsCheck?.svc_model_presets?.active_preset_id?.trim()
    if (fromCheck) return fromCheck
    return DEFAULT_PRESET_ID
  }, [sovitsCheck?.svc_model_presets?.active_preset_id, systemHealth?.svc_model_presets?.active_preset_id])

  const speaker = useMemo(() => {
    const presets = systemHealth?.svc_model_presets?.presets ?? sovitsCheck?.svc_model_presets?.presets ?? []
    const current = presets.find((item) => item.preset_id === modelPresetId)
    return current?.speaker || DEFAULT_SPEAKER
  }, [modelPresetId, sovitsCheck?.svc_model_presets?.presets, systemHealth?.svc_model_presets?.presets])

  const metadataSpeaker = result?.metadata?.speaker ?? null
  const effectiveSpeaker = metadataSpeaker || speaker || DEFAULT_SPEAKER

  const conditionMode = useMemo(() => {
    return systemHealth?.sovits?.condition_mode ?? sovitsCheck?.sovits?.condition_mode ?? 'internal_film'
  }, [sovitsCheck?.sovits?.condition_mode, systemHealth?.sovits?.condition_mode])

  const filmStrength = useMemo(() => {
    return (
      systemHealth?.text_conditioning?.film_strength ??
      systemHealth?.sovits?.film_strength ??
      sovitsCheck?.sovits?.film_strength ??
      null
    )
  }, [sovitsCheck?.sovits?.film_strength, systemHealth?.sovits?.film_strength, systemHealth?.text_conditioning?.film_strength])

  const isRealSvc = useMemo(() => {
    if (typeof systemHealth?.mock_mode === 'boolean') {
      return !systemHealth.mock_mode
    }
    if (typeof sovitsCheck?.SOVITS_MOCK === 'boolean') {
      return !sovitsCheck.SOVITS_MOCK
    }
    return null
  }, [sovitsCheck?.SOVITS_MOCK, systemHealth?.mock_mode])

  const gpuReady = useMemo(() => {
    if (typeof sovitsCheck?.torch_cuda_available === 'boolean') {
      return sovitsCheck.torch_cuda_available
    }
    if (typeof sovitsCheck?.torch_device_count === 'number') {
      return sovitsCheck.torch_device_count > 0
    }
    return null
  }, [sovitsCheck?.torch_cuda_available, sovitsCheck?.torch_device_count])

  const modelReady = useMemo(() => {
    const runtime = systemHealth?.sovits ?? sovitsCheck?.sovits
    if (typeof runtime?.model_exists === 'boolean' && typeof runtime?.config_exists === 'boolean') {
      return runtime.model_exists && runtime.config_exists
    }
    return null
  }, [sovitsCheck?.sovits, systemHealth?.sovits])

  const inputQuality = uploadInfo?.input_quality_summary ?? null

  const canUpload = Boolean(inputAudio) && !isUploading && !isConverting
  const canConvert = Boolean(vocalsId) && promptText.trim().length > 0 && !isUploading && !isConverting

  useEffect(() => {
    let cancelled = false

    const loadStatus = async () => {
      try {
        const [healthResponse, checkResponse] = await Promise.all([
          axios.get<SystemHealthResponse>('/api/v1/system/health'),
          axios.get<SovitsCheckResponse>('/api/v1/system/sovits-check'),
        ])
        if (cancelled) return
        setSystemHealth(healthResponse.data ?? null)
        setSovitsCheck(checkResponse.data ?? null)
      } catch {
        if (cancelled) return
        setSystemHealth(null)
        setSovitsCheck(null)
      }
    }

    void loadStatus()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!styleEvidenceRequest || status !== AppStatus.SUCCEEDED) {
      return
    }

    let cancelled = false
    setStyleEvidenceWarning(null)

    void compareStyleEvidence({
      input_path: styleEvidenceRequest.inputPath,
      output_path: styleEvidenceRequest.outputPath,
      prompt_text: styleEvidenceRequest.promptText,
      model_preset_id: styleEvidenceRequest.modelPresetId,
    })
      .then((data) => {
        if (cancelled) return
        if (!data?.ok) {
          setStyleEvidence(null)
          setStyleEvidenceWarning('风格分析未返回有效数据（不影响主结果）。')
          return
        }
        setStyleEvidence(data)
      })
      .catch(() => {
        if (cancelled) return
        setStyleEvidence(null)
        setStyleEvidenceWarning('风格分析失败（不影响播放和下载）。')
      })

    return () => {
      cancelled = true
    }
  }, [status, styleEvidenceRequest])

  useEffect(() => {
    return () => {
      if (inputAudio?.url) {
        window.URL.revokeObjectURL(inputAudio.url)
      }
      if (result?.outputAudioUrl) {
        window.URL.revokeObjectURL(result.outputAudioUrl)
      }
    }
  }, [inputAudio?.url, result?.outputAudioUrl])

  const clearStyleEvidenceState = () => {
    setStyleEvidence(null)
    setStyleEvidenceRequest(null)
    setStyleEvidenceWarning(null)
  }

  const clearResultState = () => {
    if (result?.outputAudioUrl) {
      window.URL.revokeObjectURL(result.outputAudioUrl)
    }
    setResult(null)
    setTaskId(null)
    setTaskStatus('idle')
    setTaskStage('')
    setTaskProgress(0)
    setErrorMessage(null)
    setErrorDetails(null)
    clearStyleEvidenceState()
  }

  const handlePromptChange = (value: string) => {
    setPromptText(value)
    clearStyleEvidenceState()
  }

  const handleFileSelect = async (file: File) => {
    if (file.size > FILE_SIZE_LIMIT) {
      setStatus(AppStatus.FAILED)
      setErrorMessage('上传音频文件大小不能超过 10MB。')
      return
    }

    if (inputAudio?.url) {
      window.URL.revokeObjectURL(inputAudio.url)
    }

    clearResultState()
    setUploadInfo(null)
    setVocalsId(null)

    const objectUrl = window.URL.createObjectURL(file)
    const nextAudio: AudioFile = {
      file,
      url: objectUrl,
      name: file.name,
      size: file.size,
      mimeType: file.type,
      durationSeconds: null,
    }

    setInputAudio(nextAudio)
    setStatus(AppStatus.FILE_SELECTED)
    setStatusMessage('已选择新音频，旧结果已清空。')

    const durationSeconds = await getAudioDuration(objectUrl)
    setInputAudio((current) => {
      if (!current || current.url !== objectUrl) {
        return current
      }
      return {
        ...current,
        durationSeconds,
      }
    })
  }

  const handleUpload = async () => {
    if (!inputAudio) {
      return
    }

    setStatus(AppStatus.UPLOADING)
    setStatusMessage('正在上传音频并进行输入检查...')
    setErrorMessage(null)
    setErrorDetails(null)

    try {
      const formData = new FormData()
      formData.append('audio', inputAudio.file)
      const response = await axios.post<UploadResponse>('/api/v1/upload', formData)
      const data = response.data ?? {}
      if (!data.vocals_id) {
        throw new Error('后端未返回 vocals_id。')
      }
      setUploadInfo(data)
      setVocalsId(data.vocals_id)
      setStatus(AppStatus.UPLOADED)
      setStatusMessage('上传成功，已可开始风格转换。')
    } catch (error) {
      setStatus(AppStatus.FAILED)
      setErrorMessage(readAxiosMessage(error, '上传失败，请检查后端服务。'))
    }
  }

  const handleConvert = async () => {
    if (!vocalsId) {
      setStatus(AppStatus.FAILED)
      setErrorMessage('请先完成上传。')
      return
    }

    if (!promptText.trim()) {
      setStatus(AppStatus.FAILED)
      setErrorMessage('请输入风格提示词。')
      return
    }

    clearResultState()
    setStatus(AppStatus.CONVERTING)
    setStatusMessage('正在创建转换任务...')

    try {
      const response = await axios.post<ConvertResponse>('/api/v1/convert', {
        vocals_id: vocalsId,
        prompt_text: promptText,
        style_prompt: promptText,
        model_preset_id: modelPresetId,
        engine: 'sovits',
      })

      const createdTaskId = response.data?.task_id
      if (!createdTaskId) {
        throw new Error('后端未返回 task_id。')
      }

      setTaskId(createdTaskId)
      setTaskStatus('queued')
      setTaskStage('queued')
      setStatusMessage(`任务 ${createdTaskId} 已创建，正在排队...`)

      const completed = await pollTask(createdTaskId, (update) => {
        setTaskStatus(update.status)
        setTaskStage(update.stage)
        setTaskProgress(update.progress)
        if (update.message) {
          setStatusMessage(update.message)
        }
      })

      const mergedMetadata = normalizeResultMetadata(completed)
      const resultUrl = completed.result_url || `/api/v1/tasks/${createdTaskId}/result`

      const downloadResponse = await axios.get(`/api/v1/tasks/${createdTaskId}/result`, { responseType: 'blob' })
      const outputAudioUrl = window.URL.createObjectURL(downloadResponse.data as Blob)

      const nextResult: ProcessingResult = {
        taskId: createdTaskId,
        inputAudioUrl: inputAudio?.url ?? null,
        outputAudioUrl,
        resultUrl,
        downloadUrl: outputAudioUrl,
        metadata: {
          ...mergedMetadata,
          task_id: mergedMetadata.task_id ?? createdTaskId,
          result_url: mergedMetadata.result_url ?? resultUrl,
          style_prompt: mergedMetadata.style_prompt ?? promptText,
        },
      }

      setResult(nextResult)
      setStatus(AppStatus.SUCCEEDED)
      setTaskStatus('succeeded')
      setTaskStage('completed')
      setTaskProgress(100)
      setStatusMessage('转换成功，结果已生成。')

      const styleRequest = buildStyleEvidenceRequest(nextResult.metadata, promptText, modelPresetId)
      setStyleEvidenceRequest(styleRequest)
    } catch (error) {
      setStatus(AppStatus.FAILED)
      setTaskStatus('failed')
      setTaskStage('failed')
      setTaskProgress(100)
      if (error instanceof TaskFailureError) {
        setErrorMessage(error.message)
        setErrorDetails(error.detailText)
      } else {
        setErrorMessage(readAxiosMessage(error, '转换失败。'))
      }
    }
  }

  const progressPercent = Math.max(0, Math.min(100, taskProgress))
  const metadata = result?.metadata ?? null
  const convertButtonLabel = getConvertButtonLabel({ inputAudio, vocalsId, promptText, isConverting })
  const resultFileName = basenamePath(metadata?.final_output_path ?? `${result?.taskId || 'result'}.wav`)
  const malePromptMismatchWarning =
    promptText.includes('男声') && effectiveSpeaker === 'lain'
      ? '当前提示词包含男声方向，但实际目标 speaker 仍为 lain。文本提示词会影响风格调制，但不会自动切换为男声模型；若需男声输出，需要接入男声 preset/speaker。'
      : null

  return (
    <div className="page-shell" translate="no">
      <main className="page-container" data-testid="main-container">
        <header className="hero-compact">
          <div className="hero-main">
            <h1>基于文本提示词控制的歌声风格转换系统</h1>
            <p>上传干声音频，输入风格提示词，执行 So-VITS-SVC + internal_film 转换并展示结果对比。</p>
          </div>
          <section className="hero-status" aria-label="系统状态">
            <StatusRow label="Real SVC" value={statusLabel(isRealSvc, '未检测')} tone={toneFromBoolean(isRealSvc)} />
            <StatusRow
              label="Internal FiLM"
              value={conditionMode === 'internal_film' ? '已启用' : conditionMode || '未检测'}
              tone={conditionMode === 'internal_film' ? 'success' : 'warning'}
            />
            <StatusRow
              label="Trained Adapter"
              value={valueOrFallback(metadata?.text_style_adapter_loaded, '未检测')}
              tone={metadata?.text_style_adapter_loaded === true ? 'success' : 'neutral'}
            />
            <StatusRow
              label="GPU/Model Ready"
              value={gpuModelReadyLabel(gpuReady, modelReady)}
              tone={gpuReady && modelReady ? 'success' : gpuReady === null && modelReady === null ? 'neutral' : 'warning'}
            />
          </section>
        </header>

        <section className="workspace-grid" data-testid="workspace-grid">
          <section className="input-column" data-testid="input-column">
            <article className="card">
              <div className="card-header compact-header">
                <h2>上传音频</h2>
                <span className="badge badge-neutral">/api/v1/upload</span>
              </div>
              <FileUpload
                onFileSelect={handleFileSelect}
                onError={(message) => {
                  setStatus(AppStatus.FAILED)
                  setErrorMessage(message)
                }}
                disabled={isUploading || isConverting}
              />

              {inputAudio ? (
                <div className="meta-grid single-column">
                  <MetaItem label="文件名" value={inputAudio.name} />
                  <MetaItem label="大小" value={formatBytes(inputAudio.size)} />
                  <MetaItem label="时长" value={formatDuration(inputAudio.durationSeconds)} />
                  <MetaItem label="格式" value={formatMimeType(inputAudio.mimeType, inputAudio.name)} />
                  <MetaItem label="上传状态" value={uploadStatusLabel(status)} />
                  <MetaItem label="vocals_id" value={valueOrFallback(uploadInfo?.vocals_id, '未返回')} />
                </div>
              ) : null}

              <button type="button" className="secondary-button" onClick={handleUpload} disabled={!canUpload || status === AppStatus.UPLOADED}>
                {isUploading ? '上传中...' : status === AppStatus.UPLOADED ? '已完成上传' : '上传音频'}
              </button>
            </article>

            <article className="card">
              <div className="card-header compact-header">
                <h2>Prompt 与参数</h2>
                <span className="badge badge-neutral">{modelPresetId} / {speaker}</span>
              </div>

              <label htmlFor="style-prompt" className="field-label">文本风格提示词</label>
              <textarea
                id="style-prompt"
                className="styled-textarea"
                placeholder="例如：温柔、明亮、流行感更强的女声风格"
                value={promptText}
                onChange={(event) => handlePromptChange(event.target.value)}
                disabled={isConverting}
              />
              <div className="char-count">字数：{promptText.length}</div>

              <div className="chip-row">
                {STYLE_PROMPT_CHIPS.map((chip) => (
                  <button key={chip} type="button" className="chip-button" onClick={() => handlePromptChange(chip)} disabled={isConverting}>
                    {chip}
                  </button>
                ))}
              </div>

              <div className="meta-grid two-column">
                <MetaItem label="condition_mode" value={valueOrFallback(conditionMode, '未返回')} />
                <MetaItem label="film_strength" value={formatFilmStrength(filmStrength)} />
                <MetaItem label="model_preset_id" value={modelPresetId} />
                <MetaItem label="speaker" value={speaker} />
              </div>

              <button type="button" className="primary-button" onClick={handleConvert} disabled={!canConvert}>
                {convertButtonLabel}
              </button>
            </article>
          </section>

          <section className="result-column" data-testid="result-column">
            <article className="card" role="status" aria-live="polite">
              <div className="card-header compact-header">
                <h2>转换状态</h2>
                <span className={`badge ${taskStatusBadgeClass(status, taskStatus)}`}>{taskStatusText(status, taskStatus)}</span>
              </div>
              <div className="meta-grid two-column">
                <MetaItem label="task_id" value={valueOrFallback(taskId, '未创建')} />
                <MetaItem label="status" value={valueOrFallback(taskStatus, status)} />
                <MetaItem label="stage" value={valueOrFallback(taskStage, '等待中')} />
                <MetaItem label="progress" value={`${progressPercent}%`} />
              </div>
              <div className="task-message">{statusMessage}</div>

              <div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progressPercent}>
                <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
              </div>

              {isConverting ? <StageSteps currentStage={taskStage} /> : null}
            </article>

            <article className="card">
              <div className="card-header compact-header">
                <h2>转换结果</h2>
                <span className="badge badge-neutral">结果</span>
              </div>

              {(status === AppStatus.IDLE || status === AppStatus.FILE_SELECTED || status === AppStatus.UPLOADING || status === AppStatus.UPLOADED) && (
                <div className="empty-state">转换结果将在这里显示</div>
              )}
              {status === AppStatus.CONVERTING && <div className="empty-state">任务进行中，请等待后端返回结果。</div>}

              {status === AppStatus.FAILED && (
                <div className="error-box" role="alert">
                  <strong>转换失败</strong>
                  <div>{valueOrFallback(errorMessage, '未返回错误信息')}</div>
                  {errorDetails ? <div className="muted-text">{errorDetails}</div> : null}
                </div>
              )}

              {status === AppStatus.SUCCEEDED && result && (
                <div className="success-box">
                  <strong>转换成功</strong>
                  <audio controls src={result.outputAudioUrl} className="result-audio" />
                  <a href={result.downloadUrl} download={`converted_${result.taskId}.wav`} className="download-button">下载结果</a>

                  <div className="meta-grid two-column">
                    <PathMetaItem label="result_url" value={valueOrFallback(result.resultUrl, '未返回')} />
                    <PathMetaItem label="输出文件" value={resultFileName} />
                    <PathMetaItem label="输出路径" value={valueOrFallback(metadata?.final_output_path, '未返回')} />
                    <MetaItem label="duration_seconds" value={valueOrFallback(metadata?.duration_seconds, '未返回')} />
                    <MetaItem label="sample_rate" value={valueOrFallback(metadata?.sample_rate, '未返回')} />
                  </div>
                </div>
              )}
            </article>

            {status === AppStatus.SUCCEEDED && result && (
              <AudioComparePanel
                originalUrl={result.inputAudioUrl}
                convertedUrl={result.outputAudioUrl}
                originalLabel={result.inputAudioUrl ? '输入音频' : '输入音频不可预览'}
                convertedLabel="输出音频"
                originalDuration={inputAudio?.durationSeconds ?? inputQuality?.duration ?? null}
                convertedDuration={typeof metadata?.duration_seconds === 'number' ? metadata.duration_seconds : null}
                originalSampleRate={inputQuality?.sample_rate ?? null}
                convertedSampleRate={typeof metadata?.sample_rate === 'number' ? metadata.sample_rate : null}
              />
            )}
          </section>

          <section className="metrics-column" data-testid="metrics-column">
            <KeyMetricsComparePanel analysis={styleEvidence} resultMetadata={metadata} inputQuality={inputQuality} />

            {styleEvidenceWarning ? <div className="inline-warning" role="status">{styleEvidenceWarning}</div> : null}

            <article className="card compact-card" aria-label="技术链路">
              <div className="card-header compact-header">
                <h2>技术链路</h2>
                <span className="badge badge-neutral">真实链路</span>
              </div>

              <div className="meta-grid two-column">
                <MetaItem label="condition_mode" value={valueOrFallback(metadata?.condition_mode ?? conditionMode, '未返回')} />
                <MetaItem label="film_strength" value={valueOrFallback(metadata?.film_strength ?? filmStrength, '未返回')} />
                <BoolMetaItem label="executed_internal_film" value={metadata?.executed_internal_film ?? null} />
                <BoolMetaItem label="text_style_adapter_loaded" value={metadata?.text_style_adapter_loaded ?? null} />
                <MetaItem label="adapter_mode" value={valueOrFallback(metadata?.adapter_mode, '未返回')} />
                <MetaItem label="adapter_type" value={valueOrFallback(metadata?.adapter_type, '未返回')} />
                <PathMetaItem label="adapter_checkpoint" value={compactCheckpoint(metadata?.adapter_checkpoint ?? metadata?.adapter_checkpoint_path)} />
                <MetaItem
                  label="model_preset"
                  value={valueOrFallback(metadata?.effective_model_preset_id ?? metadata?.model_preset_id ?? modelPresetId, '未返回')}
                />
                <MetaItem label="speaker" value={effectiveSpeaker} />
              </div>

              <div className="inline-note">当前目标 speaker：{effectiveSpeaker}</div>

              {malePromptMismatchWarning ? <div className="inline-warning" role="alert">{malePromptMismatchWarning}</div> : null}
            </article>
          </section>
        </section>
      </main>
    </div>
  )
}

function StageSteps({ currentStage }: { currentStage: string }) {
  const steps = ['uploaded', 'text_encoded', 'adapter_applied', 'inference_running', 'completed']
  const labels: Record<string, string> = {
    uploaded: '上传完成',
    text_encoded: '文本编码',
    adapter_applied: 'Adapter',
    inference_running: 'Internal FiLM',
    completed: '输出生成',
  }

  const currentIndex = stepIndex(currentStage)

  return (
    <ol className="stage-list">
      {steps.map((step, index) => {
        const done = currentIndex >= index
        return (
          <li key={step} className={done ? 'stage-item stage-done' : 'stage-item'}>
            <span className="stage-dot" aria-hidden="true" />
            <span>{labels[step]}</span>
          </li>
        )
      })}
    </ol>
  )
}

function StatusRow({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone: 'success' | 'warning' | 'error' | 'neutral'
}) {
  return (
    <div className="status-row">
      <span>{label}</span>
      <span className={`badge badge-${tone}`}>{value}</span>
    </div>
  )
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="meta-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function PathMetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="meta-item">
      <span>{label}</span>
      <strong className="path-ellipsis" title={value}>{value}</strong>
    </div>
  )
}

function BoolMetaItem({ label, value }: { label: string; value: boolean | null }) {
  const text = value === true ? 'true' : value === false ? 'false' : '未返回'
  const badgeClass = value === true ? 'badge badge-success' : value === false ? 'badge badge-warning' : 'badge badge-neutral'
  return (
    <div className="meta-item">
      <span>{label}</span>
      <strong><span className={badgeClass}>{text}</span></strong>
    </div>
  )
}

class TaskFailureError extends Error {
  detailText: string

  constructor(message: string, detailText: string) {
    super(message)
    this.name = 'TaskFailureError'
    this.detailText = detailText
  }
}

async function pollTask(taskId: string, onUpdate: (update: TaskUpdate) => void): Promise<TaskResponse> {
  for (let attempt = 0; attempt < 180; attempt += 1) {
    const response = await axios.get<TaskResponse>(`/api/v1/tasks/${taskId}`)
    const data = response.data ?? {}
    onUpdate({
      status: typeof data.status === 'string' ? data.status : 'running',
      stage: typeof data.stage === 'string' ? data.stage : '',
      progress: typeof data.progress === 'number' ? Math.max(0, Math.min(100, data.progress)) : 0,
      message: typeof data.message === 'string' ? data.message : '',
    })

    if (data.status === 'failed') {
      const parsed = parseTaskError(data)
      throw new TaskFailureError(parsed.message, parsed.details)
    }

    if (data.status === 'succeeded') {
      if (!data.result_url) {
        throw new TaskFailureError('任务状态为 succeeded，但 result_url 缺失。', JSON.stringify(data.error ?? {}, null, 2))
      }
      return data
    }

    await new Promise((resolve) => setTimeout(resolve, 1000))
  }

  throw new TaskFailureError('任务超时，请重试。', '轮询超时：超过 180 秒未完成。')
}

function parseTaskError(task: TaskResponse): { message: string; details: string } {
  const error = task.error
  if (typeof error === 'string') {
    return { message: error, details: error }
  }
  if (error && typeof error === 'object') {
    const maybeCode = typeof error.code === 'string' ? error.code : null
    const maybeMessage = typeof error.message === 'string' ? error.message : null
    const maybeDetails = error.details && typeof error.details === 'object' ? JSON.stringify(error.details) : '未返回 details'
    return {
      message: maybeMessage || maybeCode || task.message || '转换失败',
      details: maybeDetails,
    }
  }
  return {
    message: task.message || '转换失败',
    details: '后端未返回错误详情。',
  }
}

function normalizeResultMetadata(taskData: TaskResponse): ResultMetadata {
  const raw = (taskData.result_metadata ?? taskData.engine_details ?? {}) as Record<string, unknown>
  return {
    task_id: readString(raw.task_id ?? taskData.task_id),
    status: readString(raw.status ?? taskData.status),
    result_url: readString(raw.result_url ?? taskData.result_url),
    download_url: readString(raw.download_url ?? taskData.download_url),
    input_url: readString(raw.input_url ?? taskData.input_url),
    output_url: readString(raw.output_url ?? taskData.output_url),
    warning: readString(raw.warning ?? taskData.warning),
    condition_mode: readString(raw.condition_mode),
    film_strength: readNumber(raw.film_strength),
    executed_internal_film: readBoolean(raw.executed_internal_film),
    text_style_adapter_loaded: readBoolean(raw.text_style_adapter_loaded ?? raw.adapter_enabled),
    adapter_mode: readString(raw.adapter_mode),
    adapter_type: readString(raw.adapter_type),
    adapter_checkpoint: readString(raw.adapter_checkpoint),
    adapter_checkpoint_path: readString(raw.adapter_checkpoint_path),
    style_prompt: readString(raw.style_prompt),
    sample_rate: readNumber(raw.sample_rate),
    duration_seconds: readNumber(raw.duration_seconds),
    has_nan_or_inf: readBoolean(raw.has_nan_or_inf),
    objective_metrics_summary: readRecord(raw.objective_metrics_summary),
    model_preset_id: readString(raw.model_preset_id),
    requested_model_preset_id: readString(raw.requested_model_preset_id),
    effective_model_preset_id: readString(raw.effective_model_preset_id),
    speaker: readString(raw.speaker),
    input_audio_path: readString(raw.input_audio_path),
    input_vocals_path: readString(raw.input_vocals_path),
    final_output_path: readString(raw.final_output_path),
    audio_quality_summary: readRecord(raw.audio_quality_summary) as ResultMetadata['audio_quality_summary'],
    ...raw,
  }
}

function buildStyleEvidenceRequest(metadata: ResultMetadata, promptText: string, modelPresetId: string): StyleEvidenceRequest | null {
  const normalizedPrompt = promptText.trim()
  const inputPath = metadata.input_vocals_path ?? metadata.input_audio_path
  const outputPath = metadata.final_output_path

  if (!normalizedPrompt || !inputPath || !outputPath) {
    return null
  }

  return {
    inputPath,
    outputPath,
    promptText: normalizedPrompt,
    modelPresetId: metadata.effective_model_preset_id ?? metadata.model_preset_id ?? modelPresetId,
  }
}

function getConvertButtonLabel(args: {
  inputAudio: AudioFile | null
  vocalsId: string | null
  promptText: string
  isConverting: boolean
}) {
  if (args.isConverting) return '转换中...'
  if (!args.inputAudio || !args.vocalsId) return '请先上传音频'
  if (!args.promptText.trim()) return '请输入风格提示词'
  return '开始风格转换'
}

function taskStatusText(status: AppStatus, taskStatus: string): string {
  if (status === AppStatus.IDLE) return 'idle'
  if (status === AppStatus.FILE_SELECTED) return 'file_selected'
  if (status === AppStatus.UPLOADING) return 'uploading'
  if (status === AppStatus.UPLOADED) return 'uploaded'
  if (status === AppStatus.CONVERTING) return taskStatus || 'converting'
  if (status === AppStatus.SUCCEEDED) return 'succeeded'
  return 'failed'
}

function taskStatusBadgeClass(status: AppStatus, taskStatus: string): string {
  if (status === AppStatus.SUCCEEDED || taskStatus === 'succeeded') return 'badge-success'
  if (status === AppStatus.FAILED || taskStatus === 'failed') return 'badge-error'
  if (status === AppStatus.CONVERTING || taskStatus === 'running' || taskStatus === 'queued') return 'badge-running'
  if (status === AppStatus.UPLOADING) return 'badge-running'
  return 'badge-neutral'
}

function uploadStatusLabel(status: AppStatus): string {
  if (status === AppStatus.UPLOADING) return '上传中'
  if (status === AppStatus.UPLOADED || status === AppStatus.CONVERTING || status === AppStatus.SUCCEEDED) return '上传完成'
  if (status === AppStatus.FILE_SELECTED) return '待上传'
  if (status === AppStatus.FAILED) return '失败'
  return '等待文件'
}

function stepIndex(stage: string): number {
  const normalized = stage.toLowerCase()
  if (normalized.includes('uploaded') || normalized.includes('separated')) return 0
  if (normalized.includes('text')) return 1
  if (normalized.includes('adapter')) return 2
  if (normalized.includes('inference') || normalized.includes('running')) return 3
  if (normalized.includes('completed') || normalized.includes('quality')) return 4
  return -1
}

function toneFromBoolean(value: boolean | null): 'success' | 'warning' | 'error' | 'neutral' {
  if (value === true) return 'success'
  if (value === false) return 'warning'
  return 'neutral'
}

function statusLabel(value: boolean | null, fallback: string): string {
  if (value === true) return '已就绪'
  if (value === false) return '未就绪'
  return fallback
}

function gpuModelReadyLabel(gpuReady: boolean | null, modelReady: boolean | null): string {
  if (gpuReady === null && modelReady === null) return '未检测'
  if (gpuReady && modelReady) return '已就绪'
  const gpuText = gpuReady === null ? 'GPU未知' : gpuReady ? 'GPU就绪' : 'GPU未就绪'
  const modelText = modelReady === null ? '模型未知' : modelReady ? '模型就绪' : '模型未就绪'
  return `${gpuText} / ${modelText}`
}

function valueOrFallback(value: unknown, fallback: string): string {
  if (typeof value === 'string') return value.trim() ? value : fallback
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : fallback
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return fallback
}

function readAxiosMessage(error: unknown, fallback: string): string {
  const responseDetail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof responseDetail === 'string' && responseDetail.trim()) return responseDetail
  const message = (error as { message?: unknown })?.message
  if (typeof message === 'string' && message.trim()) return message
  return fallback
}

function readString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

function readNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function readBoolean(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null
}

function readRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null
}

async function getAudioDuration(url: string): Promise<number | null> {
  return new Promise((resolve) => {
    const audio = document.createElement('audio')
    audio.preload = 'metadata'
    audio.src = url
    audio.onloadedmetadata = () => {
      if (!Number.isFinite(audio.duration)) {
        resolve(null)
        return
      }
      resolve(audio.duration)
    }
    audio.onerror = () => resolve(null)
  })
}

function formatDuration(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '未检测'
  return `${value.toFixed(2)} s`
}

function formatFilmStrength(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '未返回'
  return value.toFixed(2)
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes)) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let current = bytes
  let index = 0
  while (current >= 1024 && index < units.length - 1) {
    current /= 1024
    index += 1
  }
  return `${current.toFixed(index === 0 ? 0 : 2)} ${units[index]}`
}

function formatMimeType(mimeType: string, filename: string): string {
  if (mimeType) return mimeType
  const lower = filename.toLowerCase()
  if (lower.endsWith('.wav')) return 'audio/wav'
  if (lower.endsWith('.mp3')) return 'audio/mpeg'
  if (lower.endsWith('.flac')) return 'audio/flac'
  if (lower.endsWith('.m4a')) return 'audio/mp4'
  return '未知'
}

function basenamePath(path: string): string {
  const normalized = path.replace(/\\/g, '/')
  const parts = normalized.split('/').filter(Boolean)
  return parts[parts.length - 1] ?? path
}

function compactCheckpoint(value: string | null | undefined): string {
  if (!value) return '未返回'
  const normalized = value.replace(/\\/g, '/')
  const runtimeIndex = normalized.indexOf('runtime/')
  if (runtimeIndex >= 0) {
    return normalized.slice(runtimeIndex)
  }
  return basenamePath(normalized)
}

export default App
