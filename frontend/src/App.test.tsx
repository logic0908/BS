import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { fireEvent, screen, waitFor } from '@testing-library/dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'

import App from './App'

vi.mock('axios')

const { createWaveSurferMock } = vi.hoisted(() => ({
  createWaveSurferMock: vi.fn(),
}))

vi.mock('wavesurfer.js', () => ({
  default: {
    create: createWaveSurferMock,
  },
}))

let uploadCounter = 0
vi.mock('./components/FileUpload', () => ({
  default: ({ onFileSelect, disabled }: { onFileSelect: (file: File) => void; disabled?: boolean }) => (
    <button
      type="button"
      disabled={disabled}
      onClick={() => {
        uploadCounter += 1
        onFileSelect(new File(['demo'], `demo-${uploadCounter}.wav`, { type: 'audio/wav' }))
      }}
    >
      选择测试音频
    </button>
  ),
}))

const mockedAxios = axios as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
}

const defaultHealth = {
  data: {
    ok: true,
    mock_mode: false,
    svc_model_presets: {
      active_preset_id: 'final_primary',
      presets: [{ preset_id: 'final_primary', ready: true, display_name: 'Default', speaker: 'lain' }],
    },
    sovits: {
      condition_mode: 'internal_film',
      film_strength: 0.1,
      model_exists: true,
      config_exists: true,
    },
    text_conditioning: {
      film_strength: 0.1,
    },
  },
}

const defaultCheck = {
  data: {
    SOVITS_MOCK: false,
    torch_cuda_available: true,
    torch_device_count: 1,
    sovits: {
      condition_mode: 'internal_film',
      film_strength: 0.1,
      model_exists: true,
      config_exists: true,
    },
  },
}

const uploadOk = {
  data: {
    vocals_id: 'vocals-1',
    input_url: '/files/input.wav',
    vocals_url: '/files/vocals.wav',
    input_audio_path: '/tmp/input.wav',
    input_vocals_path: '/tmp/vocals.wav',
    input_quality_summary: {
      duration: 12.5,
      sample_rate: 44100,
      channels: 1,
      rms: 0.1,
      peak: 0.9,
      low_energy_ratio: 0.1,
      clipping_ratio: 0,
      silence_ratio: 0.05,
      is_too_short: false,
      is_probably_silent: false,
      quality_level: 'good',
      warnings: [],
    },
  },
}

function styleEvidenceResponse() {
  return {
    ok: true,
    prompt_text: '清亮少年感',
    input: { ok: true, brightness_score: 0.2 },
    output: { ok: true, brightness_score: 0.6 },
    prompt_targets: {
      prompt_text: '清亮少年感',
      target_dimensions: { brightness: 'up' },
      matched_keywords: ['清亮'],
      human_readable_targets: ['亮度提升'],
    },
    comparisons: [
      {
        key: 'brightness_score',
        label: '亮度',
        input_value: 0.2,
        output_value: 0.6,
        delta: 0.4,
        direction: 'up',
        expected_direction: 'up',
        matches_prompt: true,
        evidence_level: 'high',
        explanation: '符合目标',
      },
    ],
    radar: { dimensions: ['brightness'], input: [0.2], output: [0.6], target: [0.8] },
    summary: {
      matched_count: 1,
      total_count: 1,
      score: 1,
      level: 'strong',
      text: '输出方向匹配提示词。',
    },
    warnings: [],
  }
}

function successTaskData(overrides?: Record<string, unknown>) {
  return {
    status: 'succeeded',
    stage: 'completed',
    progress: 100,
    message: '转换完成',
    result_url: '/api/v1/tasks/task-1/result',
    result_metadata: {
      condition_mode: 'internal_film',
      film_strength: 0.1,
      executed_internal_film: true,
      text_style_adapter_loaded: true,
      adapter_mode: 'trained',
      adapter_type: 'internal_film',
      adapter_checkpoint: 'text_style_adapter_1000.pt',
      input_vocals_path: '/tmp/vocals.wav',
      final_output_path: '/tmp/output.wav',
      ...overrides,
    },
  }
}

const flush = async () => {
  await Promise.resolve()
  await Promise.resolve()
}

function buildWaveSurferInstance() {
  const handlers: Record<string, () => void> = {}
  return {
    on: vi.fn((event: string, cb: () => void) => {
      handlers[event] = cb
    }),
    load: vi.fn(() => handlers.ready?.()),
    play: vi.fn(async () => {}),
    pause: vi.fn(() => {}),
    stop: vi.fn(() => {}),
    destroy: vi.fn(() => {}),
  }
}

describe('App state flow', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    uploadCounter = 0
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    createWaveSurferMock.mockReset()
    createWaveSurferMock.mockImplementation(() => buildWaveSurferInstance())

    mockedAxios.get.mockReset()
    mockedAxios.post.mockReset()

    vi.stubGlobal(
      'URL',
      Object.assign(globalThis.URL ?? {}, {
        createObjectURL: vi.fn(() => `blob:mock-${Math.random()}`),
        revokeObjectURL: vi.fn(),
      }),
    )

    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') return defaultHealth
      if (url === '/api/v1/system/sovits-check') return defaultCheck
      throw new Error(`Unexpected GET ${url}`)
    })
  })

  afterEach(async () => {
    await act(async () => {
      root.unmount()
      await flush()
    })
    container.remove()
    vi.unstubAllGlobals()
  })

  async function renderApp() {
    await act(async () => {
      root.render(<App />)
      await flush()
    })
  }

  async function selectAndUpload() {
    await act(async () => {
      fireEvent.click(screen.getByText('选择测试音频'))
      await flush()
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '上传音频' }))
      await flush()
    })
  }

  it('初始状态禁用转换并显示等待上传', async () => {
    await renderApp()

    expect(screen.getByRole('button', { name: '请先上传音频' })).toBeDisabled()
    expect(screen.getByText('等待上传音频。')).toBeInTheDocument()
    expect(screen.getByText('转换结果将在这里显示')).toBeInTheDocument()
    expect(screen.queryByText('转换成功')).not.toBeInTheDocument()
  })

  it('选择/上传文件后显示文件名并可输入 prompt，且重新选择会清空旧结果', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') return uploadOk
      if (url === '/api/v1/convert') return { data: { task_id: 'task-1' } }
      if (url === '/api/v1/style-analysis/compare') return { data: styleEvidenceResponse() }
      throw new Error(`Unexpected POST ${url}`)
    })
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') return defaultHealth
      if (url === '/api/v1/system/sovits-check') return defaultCheck
      if (url === '/api/v1/tasks/task-1') return { data: successTaskData() }
      if (url === '/api/v1/tasks/task-1/result') return { data: new Blob(['wav']) }
      throw new Error(`Unexpected GET ${url}`)
    })

    await renderApp()
    await selectAndUpload()

    expect(screen.getByText('demo-1.wav')).toBeInTheDocument()

    await act(async () => {
      fireEvent.change(screen.getByLabelText('文本风格提示词'), { target: { value: '清亮少年感' } })
      await flush()
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始风格转换' }))
      await flush()
    })

    await waitFor(() => expect(screen.getByText('转换成功')).toBeInTheDocument())

    await act(async () => {
      fireEvent.click(screen.getByText('选择测试音频'))
      await flush()
    })

    expect(screen.getByText('demo-2.wav')).toBeInTheDocument()
    expect(screen.queryByText('转换成功')).not.toBeInTheDocument()
  })

  it('prompt 为空时转换按钮 disabled', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') return uploadOk
      throw new Error(`Unexpected POST ${url}`)
    })

    await renderApp()
    await selectAndUpload()

    expect(screen.getByRole('button', { name: '请输入风格提示词' })).toBeDisabled()
  })

  it('转换成功时显示输出播放器、下载按钮和关键 metadata', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') return uploadOk
      if (url === '/api/v1/convert') return { data: { task_id: 'task-1' } }
      if (url === '/api/v1/style-analysis/compare') return { data: styleEvidenceResponse() }
      throw new Error(`Unexpected POST ${url}`)
    })
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') return defaultHealth
      if (url === '/api/v1/system/sovits-check') return defaultCheck
      if (url === '/api/v1/tasks/task-1') return { data: successTaskData() }
      if (url === '/api/v1/tasks/task-1/result') return { data: new Blob(['wav']) }
      throw new Error(`Unexpected GET ${url}`)
    })

    await renderApp()
    await selectAndUpload()

    await act(async () => {
      fireEvent.change(screen.getByLabelText('文本风格提示词'), { target: { value: '清亮少年感' } })
      await flush()
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始风格转换' }))
      await flush()
    })

    await waitFor(() => expect(screen.getByText('转换成功')).toBeInTheDocument())
    expect(screen.getAllByText('下载输出音频').length).toBeGreaterThan(0)
    expect(screen.getAllByText('condition_mode').length).toBeGreaterThan(0)
    expect(screen.getAllByText('internal_film').length).toBeGreaterThan(0)
    expect(screen.getByText('executed_internal_film')).toBeInTheDocument()
    expect(screen.getByText('text_style_adapter_loaded')).toBeInTheDocument()
    expect(screen.getByText('adapter_checkpoint')).toBeInTheDocument()
    expect(screen.getByText('text_style_adapter_1000.pt')).toBeInTheDocument()
  })

  it('succeeded 但 result_url 缺失时显示错误且不显示成功', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') return uploadOk
      if (url === '/api/v1/convert') return { data: { task_id: 'task-1' } }
      throw new Error(`Unexpected POST ${url}`)
    })
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') return defaultHealth
      if (url === '/api/v1/system/sovits-check') return defaultCheck
      if (url === '/api/v1/tasks/task-1') return { data: { ...successTaskData(), result_url: null } }
      throw new Error(`Unexpected GET ${url}`)
    })

    await renderApp()
    await selectAndUpload()
    await act(async () => {
      fireEvent.change(screen.getByLabelText('文本风格提示词'), { target: { value: '清亮少年感' } })
      await flush()
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始风格转换' }))
      await flush()
    })

    await waitFor(() => expect(screen.getByText('转换失败')).toBeInTheDocument())
    expect(screen.getByText('任务状态为 succeeded，但 result_url 缺失。')).toBeInTheDocument()
    expect(screen.queryByText('转换成功')).not.toBeInTheDocument()
  })

  it('style-analysis 失败时主结果仍显示并出现 warning', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') return uploadOk
      if (url === '/api/v1/convert') return { data: { task_id: 'task-1' } }
      if (url === '/api/v1/style-analysis/compare') throw new Error('style-analysis failed')
      throw new Error(`Unexpected POST ${url}`)
    })
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') return defaultHealth
      if (url === '/api/v1/system/sovits-check') return defaultCheck
      if (url === '/api/v1/tasks/task-1') return { data: successTaskData() }
      if (url === '/api/v1/tasks/task-1/result') return { data: new Blob(['wav']) }
      throw new Error(`Unexpected GET ${url}`)
    })

    await renderApp()
    await selectAndUpload()
    await act(async () => {
      fireEvent.change(screen.getByLabelText('文本风格提示词'), { target: { value: '清亮少年感' } })
      await flush()
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始风格转换' }))
      await flush()
    })

    await waitFor(() => expect(screen.getByText('转换成功')).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText('风格证据分析失败，但不影响播放和下载。')).toBeInTheDocument())
  })

  it('转换失败时显示错误且不显示播放器', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') return uploadOk
      if (url === '/api/v1/convert') return { data: { task_id: 'task-failed' } }
      throw new Error(`Unexpected POST ${url}`)
    })
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') return defaultHealth
      if (url === '/api/v1/system/sovits-check') return defaultCheck
      if (url === '/api/v1/tasks/task-failed') {
        return {
          data: {
            status: 'failed',
            stage: 'failed',
            progress: 80,
            message: '推理失败',
            error: { code: 'RUNTIME_ERROR', message: '推理失败', details: { hint: 'check log' } },
          },
        }
      }
      throw new Error(`Unexpected GET ${url}`)
    })

    await renderApp()
    await selectAndUpload()
    await act(async () => {
      fireEvent.change(screen.getByLabelText('文本风格提示词'), { target: { value: '清亮少年感' } })
      await flush()
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始风格转换' }))
      await flush()
    })

    await waitFor(() => expect(screen.getByText('转换失败')).toBeInTheDocument())
    expect(screen.getAllByText('推理失败').length).toBeGreaterThan(0)
    expect(screen.queryByText('转换成功')).not.toBeInTheDocument()
  })

  it('布局 smoke：主容器、左侧输入卡片、右侧结果卡片存在', async () => {
    await renderApp()

    expect(screen.getByTestId('main-container')).toBeInTheDocument()
    expect(screen.getByTestId('input-card')).toBeInTheDocument()
    expect(screen.getByTestId('result-card')).toBeInTheDocument()
  })
})
