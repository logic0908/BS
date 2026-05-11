import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'

export interface WaveformPlayerHandle {
  play: () => void
  pause: () => void
  stop: () => void
  isReady: () => boolean
}

interface WaveformPlayerProps {
  audioUrl: string | null
  label: string
  waveColor?: string
  progressColor?: string
  height?: number
}

const WaveformPlayer = forwardRef<WaveformPlayerHandle, WaveformPlayerProps>(function WaveformPlayer(
  {
    audioUrl,
    label,
    waveColor = '#1d4ed8',
    progressColor = '#0f172a',
    height = 96,
  },
  ref,
) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const waveSurferRef = useRef<WaveSurfer | null>(null)
  const [fallbackMode, setFallbackMode] = useState(false)
  const [isReady, setIsReady] = useState(false)

  useImperativeHandle(
    ref,
    () => ({
      play: () => {
        if (waveSurferRef.current) {
          void waveSurferRef.current.play()
          return
        }
        if (audioRef.current) {
          void audioRef.current.play()
        }
      },
      pause: () => {
        if (waveSurferRef.current) {
          waveSurferRef.current.pause()
          return
        }
        audioRef.current?.pause()
      },
      stop: () => {
        if (waveSurferRef.current) {
          waveSurferRef.current.stop()
          return
        }
        if (audioRef.current) {
          audioRef.current.pause()
          audioRef.current.currentTime = 0
        }
      },
      isReady: () => isReady || Boolean(audioRef.current),
    }),
    [isReady],
  )

  useEffect(() => {
    setIsReady(false)
    setFallbackMode(false)

    if (!audioUrl || !containerRef.current) {
      waveSurferRef.current?.destroy()
      waveSurferRef.current = null
      return
    }

    try {
      const waveSurfer = WaveSurfer.create({
        container: containerRef.current,
        height,
        waveColor,
        progressColor,
        cursorColor: '#94a3b8',
        normalize: true,
        barWidth: 2,
        barGap: 2,
        barRadius: 2,
      })
      waveSurferRef.current = waveSurfer

      waveSurfer.on('ready', () => setIsReady(true))
      waveSurfer.on('error', () => {
        setFallbackMode(true)
        setIsReady(false)
        waveSurfer.destroy()
        waveSurferRef.current = null
      })
      waveSurfer.load(audioUrl)
    } catch {
      setFallbackMode(true)
      waveSurferRef.current?.destroy()
      waveSurferRef.current = null
    }

    return () => {
      waveSurferRef.current?.destroy()
      waveSurferRef.current = null
    }
  }, [audioUrl, height, progressColor, waveColor])

  if (!audioUrl) {
    return <div className="waveform-placeholder">音频就绪后将在这里显示波形。</div>
  }

  return (
    <div className="waveform-player">
      <div className="waveform-label">{label}</div>
      {fallbackMode ? (
        <div className="waveform-fallback" data-testid={`waveform-fallback-${label}`}>
          <div className="waveform-fallback-note">音频波形可视化组件初始化失败，已回退到原生播放器。</div>
          <audio ref={audioRef} controls className="fallback-audio" src={audioUrl} />
        </div>
      ) : (
        <div className="waveform-stage">
          <div ref={containerRef} className="waveform-canvas" />
          {!isReady && <div className="waveform-loading">正在加载波形…</div>}
        </div>
      )}
    </div>
  )
})

export default WaveformPlayer
