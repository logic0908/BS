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
  originalLabel = '原始音频',
  convertedLabel = '转换音频',
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
      return '当前聚焦：转换音频'
    }
    if (originalUrl) {
      return '当前聚焦：原始音频'
    }
    return '请先上传音频'
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
    <div className="compare-panel">
      <div className="compare-actions">
        <button type="button" className="secondary-button" onClick={playOriginal} disabled={!canPlayOriginal}>
          <PlayCircle className="button-icon" />
          播放原始
        </button>
        <button type="button" className="secondary-button" onClick={playConverted} disabled={!canPlayConverted}>
          <PlayCircle className="button-icon" />
          播放转换
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
            下载转换结果
          </a>
        ) : null}
      </div>

      <div className="compare-summary">{activeSummary}</div>

      <div className="compare-grid">
        <div className={`compare-card ${activeSide === 'original' ? 'is-active' : ''}`}>
          <WaveformPlayer
            ref={originalRef}
            audioUrl={originalUrl}
            label={originalLabel}
            waveColor="#2563eb"
            progressColor="#0f172a"
          />
        </div>
        <div className={`compare-card ${activeSide === 'converted' ? 'is-active' : ''}`}>
          <WaveformPlayer
            ref={convertedRef}
            audioUrl={convertedUrl}
            label={convertedLabel}
            waveColor="#d97706"
            progressColor="#7c2d12"
          />
        </div>
      </div>
    </div>
  )
}

export default AudioComparePanel
