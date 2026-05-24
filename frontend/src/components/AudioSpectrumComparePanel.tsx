import { useEffect, useMemo, useRef, useState } from 'react'

type AudioSpectrumComparePanelProps = {
  inputUrl?: string | null
  outputUrl?: string | null
  inputLabel?: string
  outputLabel?: string
  onMetadata?: (metadata: SpectrumMetadata) => void
}

type SpectrumStatus = 'missing' | 'loading' | 'ready' | 'error'

type SpectrumData = {
  timeBins: number
  freqBins: number
  values: Float32Array
}

type SpectrumMetadata = {
  label: 'input' | 'output'
  durationSeconds?: number
  sampleRate?: number
}

type SpectrumPayload = {
  spectrum: SpectrumData
  durationSeconds: number
  sampleRate: number
}

const CANVAS_HEIGHT = 140
const TIME_BINS = 96
const FREQ_BINS = 48
const FFT_SIZE = 128
const DFT_KERNELS = buildDftKernels(FREQ_BINS, FFT_SIZE)

export default function AudioSpectrumComparePanel({
  inputUrl = null,
  outputUrl = null,
  inputLabel = '上传音频',
  outputLabel = '转换后音频',
  onMetadata,
}: AudioSpectrumComparePanelProps) {
  const hasAnyAudio = Boolean(inputUrl || outputUrl)
  if (!hasAnyAudio) return null

  return (
    <div className="spectrum-compare">
      <details className="spectrum-details" open>
        <summary>频谱图对比</summary>
        <div className="spectrum-grid">
          <SpectrumCard
            url={inputUrl}
            label={inputLabel}
            metadataLabel="input"
            missingMessage="上传音频暂不可预览"
            onMetadata={onMetadata}
          />
          <SpectrumCard
            url={outputUrl}
            label={outputLabel}
            metadataLabel="output"
            missingMessage="转换后音频暂不可预览"
            onMetadata={onMetadata}
          />
        </div>
      </details>
    </div>
  )
}

function SpectrumCard({
  url,
  label,
  metadataLabel,
  missingMessage,
  onMetadata,
}: {
  url?: string | null
  label: string
  metadataLabel: 'input' | 'output'
  missingMessage: string
  onMetadata?: (metadata: SpectrumMetadata) => void
}) {
  const [status, setStatus] = useState<SpectrumStatus>('missing')
  const [data, setData] = useState<SpectrumData | null>(null)
  const [errorReason, setErrorReason] = useState<string | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  const normalizedUrl = useMemo(() => {
    if (!url) return null
    const trimmed = url.trim()
    return trimmed ? trimmed : null
  }, [url])

  useEffect(() => {
    if (!normalizedUrl) {
      setStatus('missing')
      setData(null)
      setErrorReason(null)
      return
    }

    const controller = new AbortController()
    let cancelled = false
    setStatus('loading')
    setData(null)
    setErrorReason(null)

    void generateSpectrumData(normalizedUrl, controller.signal)
      .then((payload) => {
        if (cancelled) return
        setData(payload.spectrum)
        onMetadata?.({
          label: metadataLabel,
          durationSeconds: payload.durationSeconds,
          sampleRate: payload.sampleRate,
        })
        setStatus('ready')
      })
      .catch((error: unknown) => {
        if (cancelled) return
        if (isAbortError(error)) return
        setData(null)
        const reason = toReason(error)
        setErrorReason(reason)
        setStatus('error')
        console.warn('[AudioSpectrumComparePanel] 频谱生成失败', {
          label,
          url: normalizedUrl,
          reason,
          error,
        })
      })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [metadataLabel, normalizedUrl, onMetadata])

  useEffect(() => {
    if (status !== 'ready' || !data || !canvasRef.current) return

    const canvas = canvasRef.current

    const render = (): boolean => {
      try {
        drawSpectrum(canvas, data)
        return true
      } catch (error) {
        const reason = toReason(error)
        setStatus('error')
        setErrorReason(reason)
        console.warn('[AudioSpectrumComparePanel] 频谱绘制失败', {
          label,
          reason,
          error,
        })
        return false
      }
    }

    if (!render()) return

    if (typeof ResizeObserver === 'undefined') return

    const observer = new ResizeObserver(() => {
      render()
    })
    observer.observe(canvas)
    return () => {
      observer.disconnect()
    }
  }, [status, data])

  return (
    <article className="spectrum-card" aria-label={label}>
      <h4>{label}</h4>
      {status === 'missing' && <p className="spectrum-text">{missingMessage}</p>}
      {status === 'loading' && <p className="spectrum-text">频谱生成中...</p>}
      {status === 'error' && (
        <p className="spectrum-text spectrum-warning" title={errorReason ? `原因：${errorReason}` : undefined}>
          {errorReason ? `${label}频谱生成失败：${errorReason}` : `${label}频谱生成失败`}
        </p>
      )}
      {status === 'ready' && <canvas ref={canvasRef} className="spectrum-canvas" aria-label={`${label}频谱图`} />}
    </article>
  )
}

async function generateSpectrumData(url: string, signal: AbortSignal): Promise<SpectrumPayload> {
  const normalizedUrl = url.trim()
  if (!normalizedUrl) {
    throw new SpectrumRenderError('地址为空')
  }

  let response: Response
  try {
    response = await fetch(normalizedUrl, { signal })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new SpectrumRenderError('请求失败')
  }

  if (!response.ok) {
    throw new SpectrumRenderError('请求失败')
  }

  const contentType = response.headers.get('content-type')?.toLowerCase() ?? ''
  if (
    contentType &&
    !contentType.startsWith('audio/') &&
    !contentType.includes('application/octet-stream')
  ) {
    throw new SpectrumRenderError('返回内容不是音频')
  }

  const arrayBuffer = await response.arrayBuffer()
  if (!arrayBuffer.byteLength) {
    throw new SpectrumRenderError('音频数据为空')
  }
  if (signal.aborted) {
    throw new DOMException('aborted', 'AbortError')
  }

  const AudioContextClass =
    window.AudioContext ||
    (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!AudioContextClass) {
    throw new SpectrumRenderError('音频解码失败')
  }

  const context = new AudioContextClass()
  try {
    let decoded: AudioBuffer
    try {
      decoded = await context.decodeAudioData(arrayBuffer.slice(0))
    } catch {
      throw new SpectrumRenderError('音频解码失败')
    }
    const channelData = decoded.getChannelData(0)
    return {
      spectrum: buildSpectrum(channelData, TIME_BINS, FREQ_BINS, FFT_SIZE),
      durationSeconds: decoded.duration,
      sampleRate: decoded.sampleRate,
    }
  } finally {
    await context.close().catch(() => undefined)
  }
}

function buildSpectrum(samples: Float32Array, timeBins: number, freqBins: number, fftSize: number): SpectrumData {
  const values = new Float32Array(timeBins * freqBins)
  if (!samples.length) {
    return { timeBins, freqBins, values }
  }

  const halfWindow = Math.floor(fftSize / 2)
  const step = samples.length / timeBins
  let peak = 0

  for (let timeIndex = 0; timeIndex < timeBins; timeIndex += 1) {
    const center = Math.floor((timeIndex + 0.5) * step)
    const frame = new Float32Array(fftSize)
    for (let n = 0; n < fftSize; n += 1) {
      const sampleIndex = center - halfWindow + n
      frame[n] = sampleIndex >= 0 && sampleIndex < samples.length ? samples[sampleIndex] : 0
    }

    for (let freqIndex = 0; freqIndex < freqBins; freqIndex += 1) {
      const kernel = DFT_KERNELS[freqIndex]
      let real = 0
      let imag = 0
      for (let n = 0; n < fftSize; n += 1) {
        const sample = frame[n]
        real += sample * kernel.cos[n]
        imag -= sample * kernel.sin[n]
      }
      const magnitude = Math.sqrt(real * real + imag * imag)
      const valueIndex = freqIndex * timeBins + timeIndex
      values[valueIndex] = magnitude
      if (magnitude > peak) peak = magnitude
    }
  }

  if (peak > 0) {
    const normalizer = Math.log1p(peak)
    for (let index = 0; index < values.length; index += 1) {
      values[index] = Math.log1p(values[index]) / normalizer
    }
  }

  return { timeBins, freqBins, values }
}

function drawSpectrum(canvas: HTMLCanvasElement, data: SpectrumData) {
  const context = canvas.getContext('2d')
  if (!context) {
    throw new SpectrumRenderError('Canvas 初始化失败')
  }

  const dpr = Math.max(1, window.devicePixelRatio || 1)
  const width = Math.max(1, Math.floor(canvas.clientWidth))
  const height = CANVAS_HEIGHT

  if (canvas.width !== Math.floor(width * dpr) || canvas.height !== Math.floor(height * dpr)) {
    canvas.width = Math.floor(width * dpr)
    canvas.height = Math.floor(height * dpr)
  }
  canvas.style.height = `${height}px`

  context.setTransform(dpr, 0, 0, dpr, 0, 0)
  context.clearRect(0, 0, width, height)

  const background = context.createLinearGradient(0, 0, 0, height)
  background.addColorStop(0, '#0b1220')
  background.addColorStop(1, '#162033')
  context.fillStyle = background
  context.fillRect(0, 0, width, height)

  const cellWidth = width / data.timeBins
  const cellHeight = height / data.freqBins

  for (let timeIndex = 0; timeIndex < data.timeBins; timeIndex += 1) {
    for (let freqIndex = 0; freqIndex < data.freqBins; freqIndex += 1) {
      const value = data.values[freqIndex * data.timeBins + timeIndex]
      context.fillStyle = energyColor(value)
      context.fillRect(
        timeIndex * cellWidth,
        height - (freqIndex + 1) * cellHeight,
        Math.ceil(cellWidth + 0.5),
        Math.ceil(cellHeight + 0.5),
      )
    }
  }

  context.fillStyle = 'rgba(226, 232, 240, 0.92)'
  context.font = '11px "Segoe UI", "PingFang SC", sans-serif'
  context.fillText('时间', Math.max(4, width - 32), height - 6)

  context.save()
  context.translate(12, 54)
  context.rotate(-Math.PI / 2)
  context.fillText('频率/能量', 0, 0)
  context.restore()
}

function energyColor(value: number): string {
  const clamped = Math.max(0, Math.min(1, value))
  const hue = 212 - clamped * 170
  const saturation = 84
  const lightness = 20 + clamped * 56
  return `hsl(${hue} ${saturation}% ${lightness}%)`
}

function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException) {
    return error.name === 'AbortError'
  }
  if (!error || typeof error !== 'object') return false
  return (error as { name?: string }).name === 'AbortError'
}

function toReason(error: unknown): string {
  if (error instanceof SpectrumRenderError) return error.reason
  return '频谱生成失败'
}

class SpectrumRenderError extends Error {
  reason: string

  constructor(reason: string) {
    super(reason)
    this.name = 'SpectrumRenderError'
    this.reason = reason
  }
}

function buildDftKernels(freqBins: number, fftSize: number): Array<{ cos: Float32Array; sin: Float32Array }> {
  const kernels: Array<{ cos: Float32Array; sin: Float32Array }> = []
  const maxK = Math.max(1, Math.floor(fftSize / 2) - 1)

  for (let index = 0; index < freqBins; index += 1) {
    const k = 1 + Math.floor((index / Math.max(1, freqBins - 1)) * maxK)
    const cos = new Float32Array(fftSize)
    const sin = new Float32Array(fftSize)
    for (let n = 0; n < fftSize; n += 1) {
      const angle = (2 * Math.PI * k * n) / fftSize
      cos[n] = Math.cos(angle)
      sin[n] = Math.sin(angle)
    }
    kernels.push({ cos, sin })
  }

  return kernels
}
