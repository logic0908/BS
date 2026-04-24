// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'

import App from './App'

vi.mock('axios')

vi.mock('./components/FileUpload', () => ({
  default: ({ onFileSelect, disabled }: { onFileSelect: (file: File) => void; disabled?: boolean }) => (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onFileSelect(new File(['demo'], 'demo.wav', { type: 'audio/wav' }))}
    >
      Mock Upload
    </button>
  ),
}))

vi.mock('./components/WaveformPlayer', () => ({
  default: () => <div>Waveform</div>,
}))

vi.mock('./components/StyleControls', () => ({
  default: ({
    prompt,
    setPrompt,
    onConvert,
    isLoading,
    disabled,
  }: {
    prompt: string
    setPrompt: (value: string) => void
    onConvert: () => void
    isLoading: boolean
    disabled: boolean
  }) => (
    <div>
      <textarea
        aria-label="style-prompt"
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
      />
      <button type="button" disabled={disabled || !prompt.trim() || isLoading} onClick={onConvert}>
        Start Conversion
      </button>
    </div>
  ),
}))

const mockedAxios = axios as any

const flush = async () => {
  await Promise.resolve()
  await Promise.resolve()
}

describe('App quality warning flow', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    mockedAxios.post.mockReset()
    mockedAxios.get.mockReset()
    vi.stubGlobal(
      'URL',
      Object.assign(globalThis.URL ?? {}, {
        createObjectURL: vi.fn(() => 'blob:mock-url'),
      })
    )
  })

  afterEach(async () => {
    await act(async () => {
      root.unmount()
      await flush()
    })
    container.remove()
    vi.unstubAllGlobals()
  })

  it('test_frontend_shows_quality_warning_but_allows_convert', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/extract_features') {
        return {
          data: {
            ph: 'a,b',
            note: '60,62',
            note_dur: '0.2,0.2',
            note_type: '2,2',
            quality_ok: false,
            quality_reason: 'Too many micro segments in extracted features',
          },
        }
      }
      if (url === '/api/v1/tasks') {
        return { data: { task_id: 'task-1' } }
      }
      throw new Error(`Unexpected POST ${String(url)}`)
    })
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/tasks/task-1') {
        return { data: { status: 'completed', message: '转换完成' } }
      }
      if (url === '/api/v1/tasks/task-1/result') {
        return { data: new Blob(['wav']) }
      }
      throw new Error(`Unexpected GET ${String(url)}`)
    })

    await act(async () => {
      root.render(<App />)
      await flush()
    })

    const uploadButton = Array.from(container.querySelectorAll('button')).find((button) => button.textContent === 'Mock Upload')
    expect(Boolean(uploadButton)).toBe(true)

    await act(async () => {
      uploadButton!.click()
      await flush()
    })

    expect(container.textContent).toContain('当前提取的四维特征可信度较低，转换结果可能不稳定')
    expect(container.textContent).toContain('Too many micro segments in extracted features')

    const promptInput = container.querySelector('textarea[aria-label="style-prompt"]') as HTMLTextAreaElement | null
    expect(Boolean(promptInput)).toBe(true)

    await act(async () => {
      promptInput!.value = 'warm pop voice'
      promptInput!.dispatchEvent(new Event('input', { bubbles: true }))
      await flush()
    })

    const convertButton = Array.from(container.querySelectorAll('button')).find((button) => button.textContent === 'Start Conversion')
    expect(Boolean(convertButton)).toBe(true)
    expect(convertButton!.hasAttribute('disabled')).toBe(false)

    await act(async () => {
      convertButton!.click()
      await flush()
    })

    const taskPostCall = mockedAxios.post.mock.calls.find((call: unknown[]) => call[0] === '/api/v1/tasks')
    expect(Boolean(taskPostCall)).toBe(true)
  })

  it('test_frontend_no_longer_renders_blocked_conversion_message', async () => {
    mockedAxios.post.mockResolvedValue({
      data: {
        ph: 'a,b',
        note: '60,62',
        note_dur: '0.2,0.2',
        note_type: '2,2',
        quality_ok: false,
        quality_reason: 'Too many micro segments in extracted features',
      },
    })

    await act(async () => {
      root.render(<App />)
      await flush()
    })

    const uploadButton = Array.from(container.querySelectorAll('button')).find((button) => button.textContent === 'Mock Upload')
    expect(Boolean(uploadButton)).toBe(true)

    await act(async () => {
      uploadButton!.click()
      await flush()
    })

    expect(container.textContent?.includes('已阻止转换')).toBe(false)
    expect(container.textContent?.includes('无法继续转换')).toBe(false)
    expect(container.textContent?.includes('已阻止提取')).toBe(false)
  })
})
