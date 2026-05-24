import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'

import './App.css'
import { compareStyleEvidence } from './api/styleAnalysis'
import AudioSpectrumComparePanel from './components/AudioSpectrumComparePanel'
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
import { formatSampleRate, formatSeconds, labelOf, valueLabelOf } from './utils/displayLabels'

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

type AudioRuntimeMetadata = {
  durationSeconds?: number
  sampleRate?: number
}

type FetchableAudioUrlReason = 'ok' | 'empty' | 'filesystem_path'
type ModelSelectionMode = 'auto' | 'manual'

const FILE_SIZE_LIMIT = 10 * 1024 * 1024
const DEFAULT_PRESET_ID = 'final_primary'
const DEFAULT_MANUAL_PRESET_ID = 'final_male_powerful'
const DEFAULT_SPEAKER = 'lain'
const DEFAULT_FILM_STRENGTH = 0.1
const FILM_STRENGTH_PRESETS = [0.05, 0.1, 0.15, 0.2]

function App() {
  const [systemHealth, setSystemHealth] = useState<SystemHealthResponse | null>(null)
  const [sovitsCheck, setSovitsCheck] = useState<SovitsCheckResponse | null>(null)

  const [status, setStatus] = useState<AppStatus>(AppStatus.IDLE)
  const [inputAudio, setInputAudio] = useState<AudioFile | null>(null)
  const [selectedFilePreviewUrl, setSelectedFilePreviewUrl] = useState<string | null>(null)
  const [uploadInfo, setUploadInfo] = useState<UploadResponse | null>(null)
  const [vocalsId, setVocalsId] = useState<string | null>(null)
  const [filmStrength, setFilmStrength] = useState<number>(DEFAULT_FILM_STRENGTH)

  const [promptText, setPromptText] = useState('')
  const [modelSelectionMode, setModelSelectionMode] = useState<ModelSelectionMode>('auto')
  const [manualModelPresetId, setManualModelPresetId] = useState(DEFAULT_MANUAL_PRESET_ID)

  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskStatus, setTaskStatus] = useState<string>('idle')
  const [taskStage, setTaskStage] = useState<string>('')
  const [taskProgress, setTaskProgress] = useState<number>(0)
  const [statusMessage, setStatusMessage] = useState<string>('等待上传音频。')

  const [result, setResult] = useState<ProcessingResult | null>(null)
  const [outputAudioMetadata, setOutputAudioMetadata] = useState<AudioRuntimeMetadata>({})
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [errorDetails, setErrorDetails] = useState<string | null>(null)

  const [styleEvidenceRequest, setStyleEvidenceRequest] = useState<StyleEvidenceRequest | null>(null)
  const [styleEvidence, setStyleEvidence] = useState<StyleEvidenceCompareResponse | null>(null)
  const [styleEvidenceWarning, setStyleEvidenceWarning] = useState<string | null>(null)
  const selectedPreviewRef = useRef<string | null>(null)
  const outputPreviewRef = useRef<string | null>(null)

  const isUploading = status === AppStatus.UPLOADING
  const isConverting = status === AppStatus.CONVERTING

  const activeModelPresetId = useMemo(() => {
    const fromHealth = systemHealth?.svc_model_presets?.active_preset_id?.trim()
    if (fromHealth) return fromHealth
    const fromCheck = sovitsCheck?.svc_model_presets?.active_preset_id?.trim()
    if (fromCheck) return fromCheck
    return DEFAULT_PRESET_ID
  }, [sovitsCheck?.svc_model_presets?.active_preset_id, systemHealth?.svc_model_presets?.active_preset_id])

  const availableModelPresets = useMemo(() => {
    return systemHealth?.svc_model_presets?.presets ?? sovitsCheck?.svc_model_presets?.presets ?? []
  }, [sovitsCheck?.svc_model_presets?.presets, systemHealth?.svc_model_presets?.presets])

  const recommendedManualPresetId = useMemo(() => {
    return resolveRecommendedManualPresetId(availableModelPresets, activeModelPresetId)
  }, [activeModelPresetId, availableModelPresets])

  const selectedManualPresetId = useMemo(() => {
    if (availableModelPresets.some((item) => item.preset_id === manualModelPresetId)) {
      return manualModelPresetId
    }
    return recommendedManualPresetId
  }, [availableModelPresets, manualModelPresetId, recommendedManualPresetId])

  const requestedModelPresetId = modelSelectionMode === 'manual' ? selectedManualPresetId : null

  const selectedPreset = useMemo(() => {
    const currentId = requestedModelPresetId ?? activeModelPresetId
    return availableModelPresets.find((item) => item.preset_id === currentId) ?? null
  }, [activeModelPresetId, availableModelPresets, requestedModelPresetId])

  const speaker = useMemo(() => {
    if (modelSelectionMode === 'auto') return null
    return selectedPreset?.speaker || DEFAULT_SPEAKER
  }, [modelSelectionMode, selectedPreset])

  const metadataSpeaker = result?.metadata?.speaker ?? null
  const effectiveSpeaker = metadataSpeaker || speaker || DEFAULT_SPEAKER

  const conditionMode = useMemo(() => {
    return systemHealth?.sovits?.condition_mode ?? sovitsCheck?.sovits?.condition_mode ?? 'internal_film'
  }, [sovitsCheck?.sovits?.condition_mode, systemHealth?.sovits?.condition_mode])

  const isRealSvc = useMemo(() => {
    if (typeof systemHealth?.mock_mode === 'boolean') return !systemHealth.mock_mode
    if (typeof sovitsCheck?.SOVITS_MOCK === 'boolean') return !sovitsCheck.SOVITS_MOCK
    return null
  }, [sovitsCheck?.SOVITS_MOCK, systemHealth?.mock_mode])

  const gpuReady = useMemo(() => {
    if (typeof sovitsCheck?.torch_cuda_available === 'boolean') return sovitsCheck.torch_cuda_available
    if (typeof sovitsCheck?.torch_device_count === 'number') return sovitsCheck.torch_device_count > 0
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
          setStyleEvidenceWarning('关键指标分析未返回有效数据（不影响主结果）。')
          return
        }
        setStyleEvidence(data)
      })
      .catch(() => {
        if (cancelled) return
        setStyleEvidence(null)
        setStyleEvidenceWarning('关键指标分析失败（不影响主结果）。')
      })

    return () => {
      cancelled = true
    }
  }, [status, styleEvidenceRequest])

  useEffect(() => {
    selectedPreviewRef.current = selectedFilePreviewUrl
  }, [selectedFilePreviewUrl])

  useEffect(() => {
    outputPreviewRef.current = result?.outputAudioUrl ?? null
  }, [result?.outputAudioUrl])

  useEffect(() => {
    return () => {
      if (selectedPreviewRef.current) {
        window.URL.revokeObjectURL(selectedPreviewRef.current)
      }
      if (outputPreviewRef.current) {
        window.URL.revokeObjectURL(outputPreviewRef.current)
      }
    }
  }, [])

  const clearStyleEvidenceState = () => {
    setStyleEvidence(null)
    setStyleEvidenceRequest(null)
    setStyleEvidenceWarning(null)
  }

  const clearResultState = () => {
    if (result?.outputAudioUrl) {
      window.URL.revokeObjectURL(result.outputAudioUrl)
      outputPreviewRef.current = null
    }
    setResult(null)
    setTaskId(null)
    setTaskStatus('idle')
    setTaskStage('')
    setTaskProgress(0)
    setOutputAudioMetadata({})
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

    if (selectedPreviewRef.current) {
      window.URL.revokeObjectURL(selectedPreviewRef.current)
      selectedPreviewRef.current = null
    }

    clearResultState()
    setUploadInfo(null)
    setVocalsId(null)

    const objectUrl = window.URL.createObjectURL(file)
    setSelectedFilePreviewUrl(objectUrl)
    selectedPreviewRef.current = objectUrl
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
    if (!inputAudio) return

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
        condition_mode: conditionMode,
        film_strength: filmStrength,
        model_preset_id: requestedModelPresetId ?? undefined,
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
        if (update.message) setStatusMessage(update.message)
      })

      const mergedMetadata = normalizeResultMetadata(completed)
      const resultUrl = completed.result_url || `/api/v1/tasks/${createdTaskId}/result`

      const downloadResponse = await axios.get(`/api/v1/tasks/${createdTaskId}/result`, { responseType: 'blob' })
      const outputAudioBlob = normalizeAudioBlob(downloadResponse.data, 'audio/wav')
      if (outputAudioBlob.size <= 0) {
        throw new TaskFailureError('后端结果文件为空。', `task_id=${createdTaskId}`)
      }
      const outputAudioUrl = window.URL.createObjectURL(outputAudioBlob)

      const nextResult: ProcessingResult = {
        taskId: createdTaskId,
        inputAudioUrl: inputAudio?.url ?? null,
        outputAudioUrl,
        resultUrl,
        downloadUrl: outputAudioUrl,
        duration_seconds: mergedMetadata.duration_seconds ?? null,
        sample_rate: mergedMetadata.sample_rate ?? null,
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

      const styleRequest = buildStyleEvidenceRequest(nextResult.metadata, promptText, selectedPreset?.preset_id ?? activeModelPresetId)
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
  const inputSpectrumUrl = pickBrowserAudioUrl(
    selectedFilePreviewUrl,
    uploadInfo?.input_url,
    uploadInfo?.vocals_url,
    uploadInfo?.file_url,
    result?.inputAudioUrl,
    metadata?.input_url,
  )
  const outputSpectrumUrl = pickBrowserAudioUrl(
    result?.outputAudioUrl,
    result?.downloadUrl,
    metadata?.output_url,
    result?.resultUrl,
  )
  const outputAudioSourceUrl = pickBrowserAudioUrl(
    result?.outputAudioUrl,
    result?.downloadUrl,
    result?.resultUrl,
  )
  const displayDurationSeconds = pickPositiveNumber(
    metadata?.duration_seconds,
    result?.duration_seconds,
    outputAudioMetadata.durationSeconds,
  )
  const displaySampleRate = pickPositiveNumber(
    metadata?.sample_rate,
    result?.sample_rate,
    outputAudioMetadata.sampleRate,
  )
  const handleSpectrumMetadata = useCallback((runtimeMetadata: {
    label: 'input' | 'output'
    durationSeconds?: number
    sampleRate?: number
  }) => {
    if (runtimeMetadata.label !== 'output') return
    setOutputAudioMetadata((current) => ({
      durationSeconds: pickPositiveNumber(current.durationSeconds, runtimeMetadata.durationSeconds) ?? current.durationSeconds,
      sampleRate: pickPositiveNumber(current.sampleRate, runtimeMetadata.sampleRate) ?? current.sampleRate,
    }))
  }, [])
  const convertButtonLabel = getConvertButtonLabel({ inputAudio, vocalsId, promptText, isConverting })
  const resultFileName = basenamePath(metadata?.final_output_path ?? `${result?.taskId || 'result'}.wav`)
  const internalTestPresetWarning =
    selectedPreset?.internal_test_only
      ? selectedPreset.temporary_demo_reason || '当前模型仅用于本地测试，不用于公开发布。'
      : null

  const resultInternalTestWarning =
    metadata?.internal_test_only
      ? metadata.temporary_demo_reason || '本次结果使用了内部测试模型，仅用于本地测试，不用于公开发布。'
      : null

  const malePromptMismatchWarning =
    promptText.includes('男声') && metadata?.speaker === 'lain'
      ? `当前提示词包含“男声”方向，但当前目标音色仍为“${metadata?.speaker}”。文本提示词只影响风格调制，不会自动切换目标音色；若需真正男声输出，需要接入男声模型预设或男声目标音色。`
      : null

  return (
    <div className="page-shell" translate="no">
      <main className="page-container" data-testid="main-container">
        <header className="hero-section">
          <div className="hero-main">
            <h1>基于文本提示词控制的歌声风格转换系统</h1>
            <p>上传干声音频，输入风格提示词，执行 So-VITS-SVC 与内部 FiLM 注入转换并展示结果。</p>
          </div>
          <section className="hero-status" aria-label="系统状态">
            <StatusRow label="真实 SVC" value={statusLabel(isRealSvc, '未检测')} tone={toneFromBoolean(isRealSvc)} />
            <StatusRow
              label="内部注入"
              value={valueLabelOf(conditionMode)}
              tone={conditionMode === 'internal_film' ? 'success' : 'warning'}
            />
            <StatusRow
              label="训练适配器"
              value={valueLabelOf(metadata?.text_style_adapter_loaded)}
              tone={metadata?.text_style_adapter_loaded === true ? 'success' : 'neutral'}
            />
            <StatusRow
              label="GPU/模型状态"
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
                <span className="badge badge-neutral">上传接口</span>
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
                <div className="compact-meta-grid">
                  <MiniMeta label="文件名" value={inputAudio.name} />
                  <MiniMeta label="文件大小" value={formatBytes(inputAudio.size)} />
                  <MiniMeta label="音频时长" value={formatDuration(inputAudio.durationSeconds)} />
                  <MiniMeta label="音频格式" value={formatMimeType(inputAudio.mimeType, inputAudio.name)} />
                  <MiniMeta label="上传状态" value={uploadStatusLabel(status)} />
                  <MiniMeta label="人声编号" value={valueOrFallback(uploadInfo?.vocals_id, '未返回')} />
                </div>
              ) : null}

              <button type="button" className="secondary-button" onClick={handleUpload} disabled={!canUpload || status === AppStatus.UPLOADED}>
                {isUploading ? '上传中...' : status === AppStatus.UPLOADED ? '已完成上传' : '上传音频'}
              </button>
            </article>

            <article className="card">
              <div className="card-header compact-header">
                <h2>提示词与参数</h2>
                <span className="badge badge-neutral">参数区</span>
              </div>

              <label htmlFor="style-prompt" className="field-label">风格提示词</label>
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

              <div className="field-label">模型选择</div>
              <div className="chip-row" role="radiogroup" aria-label="模型选择模式">
                <button
                  type="button"
                  className="chip-button"
                  aria-pressed={modelSelectionMode === 'auto'}
                  onClick={() => setModelSelectionMode('auto')}
                  disabled={isConverting}
                >
                  自动按提示词选择模型
                </button>
                <button
                  type="button"
                  className="chip-button"
                  aria-pressed={modelSelectionMode === 'manual'}
                  onClick={() => setModelSelectionMode('manual')}
                  disabled={isConverting}
                >
                  手动选择模型
                </button>
              </div>
              <div className="char-count">
                {modelSelectionMode === 'auto'
                  ? '自动模式不会强制传固定 baseline preset，后端会根据提示词命中 male_powerful / male_youth 等风格。'
                  : '手动模式会显式传 model_preset_id；演示对比时优先预置 final_male_powerful。'}
              </div>

              {modelSelectionMode === 'manual' ? (
                <>
                  <label htmlFor="manual-model-preset" className="field-label">手动模型预设</label>
                  <select
                    id="manual-model-preset"
                    className="styled-textarea"
                    value={selectedManualPresetId}
                    onChange={(event) => setManualModelPresetId(event.target.value)}
                    disabled={isConverting}
                  >
                    {availableModelPresets.map((preset) => (
                      <option key={preset.preset_id} value={preset.preset_id}>
                        {buildPresetOptionLabel(preset)}
                      </option>
                    ))}
                  </select>
                </>
              ) : null}

              {internalTestPresetWarning ? <div className="inline-warning" role="alert">{internalTestPresetWarning}</div> : null}

              <label htmlFor="film-strength-slider" className="field-label">
                注入强度（{filmStrength.toFixed(2)}）
              </label>
              <input
                id="film-strength-slider"
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={filmStrength}
                onChange={(event) => setFilmStrength(Number(event.target.value))}
                disabled={isConverting}
              />
              <div className="chip-row" aria-label="注入强度快捷值">
                {FILM_STRENGTH_PRESETS.map((value) => (
                  <button
                    key={value}
                    type="button"
                    className="chip-button"
                    onClick={() => setFilmStrength(value)}
                    disabled={isConverting}
                  >
                    {value.toFixed(2)}
                  </button>
                ))}
              </div>
              <div className="char-count">建议范围：0.05-0.20；过高可能影响音质稳定性。</div>

              <div className="compact-meta-grid" data-testid="task-main-fields">
                <MiniMeta label={labelOf('condition_mode')} value={valueLabelOf(conditionMode)} />
                <MiniMeta label={labelOf('film_strength')} value={formatFilmStrength(filmStrength)} />
                <MiniMeta label={labelOf('model_preset_id')} value={valueLabelOf(requestedModelPresetId ?? '自动按提示词选择')} />
                <MiniMeta label={labelOf('speaker')} value={valueLabelOf(speaker ?? '按命中结果决定')} />
              </div>

              <button type="button" className="primary-button" onClick={handleConvert} disabled={!canConvert}>
                {convertButtonLabel}
              </button>
            </article>
          </section>

          <section className="result-column" data-testid="result-column" data-testid-main-ui="true">
            <article className="card" role="status" aria-live="polite">
              <div className="card-header compact-header">
                <h2>转换状态</h2>
                <span className={`badge ${taskStatusBadgeClass(status, taskStatus)}`}>{valueLabelOf(taskStatusText(status, taskStatus))}</span>
              </div>
              <div className="compact-meta-grid">
                <MiniMeta label={labelOf('task_id')} value={valueOrFallback(taskId, '未创建')} />
                <MiniMeta label={labelOf('status')} value={valueLabelOf(taskStatusText(status, taskStatus))} />
                <MiniMeta label={labelOf('stage')} value={valueLabelOf(taskStage || 'pending')} />
                <MiniMeta label={labelOf('progress')} value={`${progressPercent}%`} />
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
                  {resultInternalTestWarning ? <div className="inline-warning" role="alert">{resultInternalTestWarning}</div> : null}
                  <audio
                    controls
                    src={outputAudioSourceUrl ?? undefined}
                    className="result-audio"
                    onLoadedMetadata={(event) => {
                      const duration = event.currentTarget.duration
                      if (Number.isFinite(duration) && duration > 0) {
                        setOutputAudioMetadata((current) => ({
                          ...current,
                          durationSeconds: duration,
                        }))
                      }
                    }}
                  />
                  <a href={outputAudioSourceUrl ?? result.resultUrl} download={`converted_${result.taskId}.wav`} className="download-button">下载结果</a>

                  <div className="compact-meta-grid" data-testid="result-main-fields">
                    <PathMiniMeta label={labelOf('result_url')} value={valueOrFallback(result.resultUrl, '未返回')} />
                    <PathMiniMeta label={labelOf('output_file')} value={resultFileName} />
                    <PathMiniMeta label={labelOf('output_path')} value={valueOrFallback(metadata?.final_output_path, '未返回')} />
                    <MiniMeta label={labelOf('duration_seconds')} value={formatSeconds(displayDurationSeconds)} />
                    <MiniMeta label={labelOf('sample_rate')} value={formatSampleRate(displaySampleRate)} />
                  </div>

                  <AudioSpectrumComparePanel
                    inputUrl={inputSpectrumUrl}
                    outputUrl={outputSpectrumUrl}
                    inputLabel="上传音频"
                    outputLabel="转换后音频"
                    onMetadata={handleSpectrumMetadata}
                  />
                </div>
              )}
            </article>
          </section>

          <section className="metrics-column" data-testid="metrics-column">
            <KeyMetricsComparePanel analysis={styleEvidence} resultMetadata={metadata} inputQuality={inputQuality} />
            {styleEvidenceWarning ? <div className="inline-warning" role="status">{styleEvidenceWarning}</div> : null}

            <article className="card compact-card" aria-label="技术链路">
              <div className="card-header compact-header">
                <h2>技术链路</h2>
                <span className="badge badge-neutral">真实链路</span>
              </div>

              <div className="compact-meta-grid" data-testid="tech-main-fields">
                <MiniMeta label={labelOf('condition_mode')} value={valueLabelOf(metadata?.condition_mode ?? conditionMode)} />
                <MiniMeta label={labelOf('film_strength')} value={formatFilmStrength(pickFiniteNumber(metadata?.film_strength, filmStrength))} />
                <MiniMeta label={labelOf('executed_internal_film')} value={valueLabelOf(metadata?.executed_internal_film)} />
                <MiniMeta label={labelOf('text_style_adapter_loaded')} value={valueLabelOf(metadata?.text_style_adapter_loaded)} />
                <MiniMeta label={labelOf('adapter_mode')} value={valueLabelOf(metadata?.adapter_mode)} />
                <MiniMeta label={labelOf('adapter_type')} value={valueLabelOf(metadata?.adapter_type)} />
                <PathMiniMeta
                  label={labelOf('adapter_checkpoint')}
                  value={compactCheckpoint(metadata?.adapter_checkpoint ?? metadata?.adapter_checkpoint_path)}
                />
                <MiniMeta
                  label={labelOf('model_preset')}
                  value={valueLabelOf(metadata?.effective_model_preset_id ?? metadata?.model_preset_id ?? requestedModelPresetId ?? activeModelPresetId)}
                />
                <MiniMeta label={labelOf('speaker')} value={valueLabelOf(effectiveSpeaker)} />
              </div>

              {malePromptMismatchWarning ? <div className="inline-warning" role="alert">{malePromptMismatchWarning}</div> : null}

              <details className="terms-details" data-testid="terms-details">
                <summary>字段说明</summary>
                <div className="terms-content">
                  <p><strong>模型预设（model_preset）</strong> 当前系统选择的模型配置方案，决定使用哪组模型权重和默认目标音色。</p>
                  <p><strong>目标音色（speaker）</strong> 目标音色决定输出主音色。提示词中的“男声”不会自动切换目标音色。</p>
                  <p><strong>音频时长（duration_seconds）</strong> 音频持续时间，单位为秒。</p>
                  <p><strong>采样率（sample_rate）</strong> 音频每秒采样点数量，单位为 Hz。</p>
                  <p><strong>结果接口（result_url）</strong> 后端返回转换结果信息的接口地址。</p>
                  <p><strong>输出路径（output_path）</strong> 后端生成音频文件在服务器上的保存路径，用于调试和追踪。</p>
                  <p><strong>条件控制模式（condition_mode）</strong> 当前采用的文本条件控制方式。</p>
                  <p><strong>内部 FiLM 注入（internal_film）</strong> 将文本风格向量转换为内部条件量并注入 So-VITS-SVC 内部特征。</p>
                  <p><strong>注入强度（film_strength）</strong> 文本风格条件影响内部特征的强度。</p>
                  <p><strong>已执行内部注入（executed_internal_film）</strong> 表示本次推理是否真实执行内部 FiLM 注入。</p>
                  <p><strong>已加载训练适配器（text_style_adapter_loaded）</strong> 表示是否加载训练后的 TextStyleAdapter。</p>
                  <p><strong>适配器模式（adapter_mode）</strong> 适配器当前工作方式。</p>
                  <p><strong>适配器类型（adapter_type）</strong> 当前适配器结构类型。</p>
                  <p><strong>适配器权重（adapter_checkpoint）</strong> 当前加载的 TextStyleAdapter 权重文件。</p>
                </div>
              </details>
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
    adapter_applied: '适配器处理',
    inference_running: '内部注入与推理',
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

function MiniMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="mini-meta-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function PathMiniMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="mini-meta-item">
      <span>{label}</span>
      <strong className="path-ellipsis" title={value}>{value}</strong>
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
  if (typeof error === 'string') return { message: error, details: error }
  if (error && typeof error === 'object') {
    const maybeCode = typeof error.code === 'string' ? error.code : null
    const maybeMessage = typeof error.message === 'string' ? error.message : null
    const maybeDetails = error.details && typeof error.details === 'object' ? JSON.stringify(error.details) : '未返回 details'
    return { message: maybeMessage || maybeCode || task.message || '转换失败', details: maybeDetails }
  }
  return { message: task.message || '转换失败', details: '后端未返回错误详情。' }
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
    model_display_name: readString(raw.model_display_name),
    source_url: readString(raw.source_url),
    license: readString(raw.license),
    is_demo_quality: readBoolean(raw.is_demo_quality),
    internal_test_only: readBoolean(raw.internal_test_only),
    temporary_demo_reason: readString(raw.temporary_demo_reason),
    speaker: readString(raw.speaker),
    input_audio_path: readString(raw.input_audio_path),
    input_vocals_path: readString(raw.input_vocals_path),
    final_output_path: readString(raw.final_output_path),
    audio_quality_summary: readRecord(raw.audio_quality_summary) as ResultMetadata['audio_quality_summary'],
    ...raw,
  }
}

function normalizeAudioBlob(payload: unknown, fallbackMimeType: string): Blob {
  if (payload instanceof Blob) {
    if (payload.type) return payload
    return new Blob([payload], { type: fallbackMimeType })
  }
  if (payload instanceof ArrayBuffer) {
    return new Blob([payload], { type: fallbackMimeType })
  }
  if (ArrayBuffer.isView(payload)) {
    const view = payload as ArrayBufferView<ArrayBuffer>
    const buffer = view.buffer.slice(view.byteOffset, view.byteOffset + view.byteLength)
    return new Blob([buffer], { type: fallbackMimeType })
  }
  throw new TaskFailureError('后端结果文件不是有效音频。', `received_type=${typeof payload}`)
}

function pickBrowserAudioUrl(...candidates: Array<string | null | undefined>): string | null {
  for (const candidate of candidates) {
    const normalized = normalizeBrowserAudioUrl(candidate)
    if (normalized) return normalized
  }
  return null
}

function normalizeBrowserAudioUrl(url: string | null | undefined): string | null {
  const normalized = readString(url)
  if (!normalized) return null
  const reason = getFetchableAudioUrlReason(normalized)
  if (reason !== 'ok') {
    console.warn('[App] 忽略不可用于浏览器音频请求的地址', {
      url: normalized,
      reason,
    })
    return null
  }
  return normalized
}

function getFetchableAudioUrlReason(url: string): FetchableAudioUrlReason {
  const normalized = url.trim()
  if (!normalized) return 'empty'
  if (
    normalized.startsWith('blob:') ||
    normalized.startsWith('data:') ||
    normalized.startsWith('http://') ||
    normalized.startsWith('https://') ||
    normalized.startsWith('/api/') ||
    normalized.startsWith('/files/') ||
    normalized.startsWith('/uploads/')
  ) {
    return 'ok'
  }
  if (
    normalized.startsWith('file://') ||
    /^[a-zA-Z]:[\\/]/.test(normalized) ||
    /^\/(home|tmp|var|mnt|Users|private)\//.test(normalized)
  ) {
    return 'filesystem_path'
  }
  if (normalized.startsWith('/')) {
    return 'filesystem_path'
  }
  return 'ok'
}

function buildStyleEvidenceRequest(metadata: ResultMetadata, promptText: string, fallbackModelPresetId: string): StyleEvidenceRequest | null {
  const normalizedPrompt = promptText.trim()
  const inputPath = metadata.input_vocals_path ?? metadata.input_audio_path
  const outputPath = metadata.final_output_path

  if (!normalizedPrompt || !inputPath || !outputPath) return null

  return {
    inputPath,
    outputPath,
    promptText: normalizedPrompt,
    modelPresetId: metadata.effective_model_preset_id ?? metadata.model_preset_id ?? fallbackModelPresetId,
  }
}

function resolveRecommendedManualPresetId(
  presets: Array<{ preset_id: string; ready?: boolean }>,
  activePresetId: string,
): string {
  const preferred = presets.find((item) => item.preset_id === DEFAULT_MANUAL_PRESET_ID && item.ready !== false)
  if (preferred) return preferred.preset_id
  const active = presets.find((item) => item.preset_id === activePresetId)
  if (active) return active.preset_id
  return activePresetId || DEFAULT_PRESET_ID
}

function buildPresetOptionLabel(preset: {
  preset_id: string
  display_name: string
  speaker: string
  ready?: boolean
  internal_test_only?: boolean
}): string {
  const status = preset.ready === false ? '未就绪' : '可用'
  const scope = preset.internal_test_only ? '内部测试' : '公开链路'
  return `${preset.display_name} (${preset.preset_id} / ${preset.speaker || 'unknown'} / ${status} / ${scope})`
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

function pickPositiveNumber(...values: unknown[]): number | null {
  for (const value of values) {
    const n = Number(value)
    if (Number.isFinite(n) && n > 0) return n
  }
  return null
}

function pickFiniteNumber(...values: unknown[]): number | null {
  for (const value of values) {
    const n = Number(value)
    if (Number.isFinite(n) && n >= 0) return n
  }
  return null
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
  return `${value.toFixed(2)} 秒`
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
  if (runtimeIndex >= 0) return normalized.slice(runtimeIndex)
  return basenamePath(normalized)
}

export default App
