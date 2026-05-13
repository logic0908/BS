import { useMemo } from 'react'

import WaveformPlayer from './WaveformPlayer'

interface AudioComparePanelProps {
  originalUrl: string | null
  convertedUrl: string | null
  originalLabel?: string
  convertedLabel?: string
  originalDuration?: number | null
  convertedDuration?: number | null
  originalSampleRate?: number | null
  convertedSampleRate?: number | null
}

function formatNumber(value: number | null | undefined, unit = ''): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '未返回'
  }
  return `${value.toFixed(2)}${unit}`
}

const AudioComparePanel: React.FC<AudioComparePanelProps> = ({
  originalUrl,
  convertedUrl,
  originalLabel = '输入音频',
  convertedLabel = '输出音频',
  originalDuration,
  convertedDuration,
  originalSampleRate,
  convertedSampleRate,
}) => {
  const summary = useMemo(() => {
    if (!originalUrl && !convertedUrl) return '当前无可预览音频'
    if (!originalUrl) return '输入音频不可预览'
    if (!convertedUrl) return '等待输出音频生成'
    return '转换前后音频可对比播放'
  }, [convertedUrl, originalUrl])

  return (
    <article className="card compact-card" aria-label="转换前后音频对比">
      <div className="card-header">
        <h2>转换前后音频对比</h2>
        <span className="badge badge-neutral">A/B</span>
      </div>

      <div className="compare-summary" aria-live="polite">
        {summary}
      </div>

      <div className="compare-grid compact-compare-grid">
        <div className="compare-card">
          <h3 className="audio-card-title">{originalLabel}</h3>
          {originalUrl ? (
            <>
              <audio controls className="result-audio" src={originalUrl} />
              <WaveformPlayer audioUrl={originalUrl} label={originalLabel} height={72} />
            </>
          ) : (
            <div className="waveform-placeholder">输入音频不可预览</div>
          )}
          <div className="mini-meta">
            <span>时长：{formatNumber(originalDuration, ' s')}</span>
            <span>采样率：{formatNumber(originalSampleRate, ' Hz')}</span>
          </div>
        </div>

        <div className="compare-card">
          <h3 className="audio-card-title">{convertedLabel}</h3>
          {convertedUrl ? (
            <>
              <audio controls className="result-audio" src={convertedUrl} />
              <WaveformPlayer audioUrl={convertedUrl} label={convertedLabel} waveColor="#d97706" progressColor="#7c2d12" height={72} />
            </>
          ) : (
            <div className="waveform-placeholder">输出音频尚未生成</div>
          )}
          <div className="mini-meta">
            <span>时长：{formatNumber(convertedDuration, ' s')}</span>
            <span>采样率：{formatNumber(convertedSampleRate, ' Hz')}</span>
          </div>
        </div>
      </div>
    </article>
  )
}

export default AudioComparePanel
