import { useMemo, useRef, useState } from 'react'
import { Download, PauseCircle, PlayCircle, Repeat2 } from 'lucide-react'

import WaveformPlayer, { type WaveformPlayerHandle } from './WaveformPlayer'

interface AudioComparePanelProps {
  originalUrl: string | null
  convertedUrl: string | null
  originalLabel?: string
  convertedLabel?: string
  downloadUrl?: string | null
  downloadFilename?: string
}

const AudioComparePanel: React.FC<AudioComparePanelProps> = ({
  originalUrl,
  convertedUrl,
  originalLabel = '输入音频',
  convertedLabel = '输出音频',
  downloadUrl,
  downloadFilename = 'converted.wav',
}) => {
  const originalRef = useRef<WaveformPlayerHandle | null>(null)
  const convertedRef = useRef<WaveformPlayerHandle | null>(null)
  const [activeSide, setActiveSide] = useState<'original' | 'converted'>('original')

  const canPlayOriginal = Boolean(originalUrl)
  const canPlayConverted = Boolean(convertedUrl)
  const canToggle = canPlayOriginal && canPlayConverted

  const activeSummary = useMemo(() => {
    if (activeSide === 'converted' && convertedUrl) {
      return '当前聚焦：输出音频'
    }
    if (originalUrl) {
      return '当前聚焦：输入音频'
    }
    return '输入音频不可预览'
  }, [activeSide, convertedUrl, originalUrl])

  const stopAll = () => {
    originalRef.current?.stop()
    convertedRef.current?.stop()
  }

  const playOriginal = () => {
    if (!originalUrl) {
      return
    }
    convertedRef.current?.stop()
    originalRef.current?.play()
    setActiveSide('original')
  }

  const playConverted = () => {
    if (!convertedUrl) {
      return
    }
    originalRef.current?.stop()
    convertedRef.current?.play()
    setActiveSide('converted')
  }

  const toggleAB = () => {
    if (!canToggle) {
      return
    }
    if (activeSide === 'original') {
      playConverted()
      return
    }
    playOriginal()
  }

  return (
    <section className="compare-panel" aria-label="输入输出音频对比">
      <div className="compare-actions">
        <button type="button" className="secondary-button" onClick={playOriginal} disabled={!canPlayOriginal}>
          <PlayCircle className="button-icon" />
          播放输入
        </button>
        <button type="button" className="secondary-button" onClick={playConverted} disabled={!canPlayConverted}>
          <PlayCircle className="button-icon" />
          播放输出
        </button>
        <button type="button" className="secondary-button" onClick={toggleAB} disabled={!canToggle}>
          <Repeat2 className="button-icon" />
          A/B 切换
        </button>
        <button type="button" className="secondary-button" onClick={stopAll} disabled={!canPlayOriginal && !canPlayConverted}>
          <PauseCircle className="button-icon" />
          停止
        </button>
        {downloadUrl ? (
          <a href={downloadUrl} download={downloadFilename} className="download-button">
            <Download className="button-icon" />
            下载输出音频
          </a>
        ) : null}
      </div>

      <div className="compare-summary" aria-live="polite">
        {activeSummary}
      </div>

      <div className="compare-grid">
        <div className={`compare-card ${activeSide === 'original' ? 'is-active' : ''}`}>
          <h4 className="audio-card-title">{originalLabel}</h4>
          {originalUrl ? <WaveformPlayer ref={originalRef} audioUrl={originalUrl} label={originalLabel} /> : <div className="waveform-placeholder">输入音频不可预览</div>}
        </div>
        <div className={`compare-card ${activeSide === 'converted' ? 'is-active' : ''}`}>
          <h4 className="audio-card-title">{convertedLabel}</h4>
          <WaveformPlayer ref={convertedRef} audioUrl={convertedUrl} label={convertedLabel} waveColor="#d97706" progressColor="#7c2d12" />
        </div>
      </div>
    </section>
  )
}

export default AudioComparePanel
