import React from 'react'

import { STYLE_PRESETS } from '../types'

interface StyleControlsProps {
  prompt: string
  setPrompt: (val: string) => void
  intensity: number
  setIntensity: (val: number) => void
  onConvert: () => void
  isLoading: boolean
  disabled: boolean
  onAppendPreset?: (preset: string) => void
  promptError?: string | null
  actionLabel?: string
}

const StyleControls: React.FC<StyleControlsProps> = ({
  prompt,
  setPrompt,
  intensity,
  setIntensity,
  onConvert,
  isLoading,
  disabled,
  onAppendPreset,
  promptError,
  actionLabel,
}) => {
  const appendPreset = (preset: string) => {
    if (onAppendPreset) {
      onAppendPreset(preset)
      return
    }
    setPrompt(prompt.trim() ? `${prompt}、${preset}` : preset)
  }

  const canConvert = !disabled && Boolean(prompt.trim()) && !isLoading

  return (
    <div className="prompt-card">
      <div className="prompt-section">
        <div className="field-label">目标风格描述</div>
        <textarea
          aria-label="style-prompt"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          disabled={isLoading}
          placeholder="例如：流行、清亮、少年感、带一点气声"
          className="styled-textarea"
        />
        <div className="prompt-tags">
          {STYLE_PRESETS.map((preset) => (
            <button
              key={preset}
              type="button"
              className="tag-button"
              onClick={() => appendPreset(preset)}
              disabled={isLoading}
            >
              {preset}
            </button>
          ))}
        </div>
        {promptError && <div className="inline-hint warning-text">{promptError}</div>}
      </div>

      <div className="strength-card">
        <div className="strength-header">
          <div className="field-label">风格强度</div>
          <div className="strength-value">{intensity.toFixed(2)}</div>
        </div>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={intensity}
          onChange={(event) => setIntensity(parseFloat(event.target.value))}
          disabled={isLoading}
          className="styled-slider"
        />
        <div className="strength-help">强度越高，目标风格越明显；强度较低时更保留原音频特征。</div>
      </div>

      <button
        type="button"
        onClick={onConvert}
        disabled={!canConvert}
        className="primary-button"
      >
        {isLoading ? '转换中...' : actionLabel || '开始转换'}
      </button>
    </div>
  )
}

export default StyleControls
