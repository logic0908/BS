import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { fireEvent, screen, waitFor } from '@testing-library/dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'

import App from './App'

const { createWaveSurferMock } = vi.hoisted(() => ({
  createWaveSurferMock: vi.fn(),
}))

vi.mock('axios')

vi.mock('wavesurfer.js', () => ({
  default: {
    create: createWaveSurferMock,
  },
}))

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

const mockedAxios = axios as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
}

const defaultHealthResponse = {
  data: {
    ok: true,
    app_status: 'ok',
    mock_mode: false,
    task_backend_mode: 'celery',
    svc_model_presets: {
      active_preset_id: 'final_primary',
      fallback_preset_id: 'tech_villager',
      presets: [
        {
          preset_id: 'final_primary',
          display_name: '当前可用默认 So-VITS-SVC 模型',
          ready: true,
          speaker: 'lain',
          style_tags: ['baseline', 'demo'],
          source_repo: 'SuCicada/Lain-so-vits-svc-4.1',
          source_url: 'https://huggingface.co/SuCicada/Lain-so-vits-svc-4.1',
          license: 'gpl',
          is_configured: true,
          is_demo_quality: true,
          smoke_test_passed: true,
          is_technical_validation_only: false,
        },
        {
          preset_id: 'final_male_youth',
          display_name: '少年感男声目标模型',
          ready: false,
          speaker: '',
          style_tags: ['male', 'youth', 'bright'],
          source_repo: 'Kuugo/Nova-Adult_So-Vits-SVC',
          source_url: 'https://huggingface.co/Kuugo/Nova-Adult_So-Vits-SVC',
          license: 'license_unknown',
          is_configured: false,
          is_demo_quality: false,
          smoke_test_passed: false,
          is_technical_validation_only: false,
        },
        {
          preset_id: 'tech_villager',
          display_name: '技术验收模型：Minecraft Villager',
          ready: true,
          speaker: 'villager',
          style_tags: ['technical', 'validation'],
          source_repo: 'Sucial/so-vits-svc4.1-Minecraft_villager',
          source_url: 'https://huggingface.co/Sucial/so-vits-svc4.1-Minecraft_villager',
          license: 'cc-by-nc-sa-4.0',
          is_configured: true,
          is_demo_quality: false,
          smoke_test_passed: true,
          is_technical_validation_only: true,
        },
      ],
    },
    timestamp: '2026-05-03T00:00:00+00:00',
  },
}

const defaultSovitsCheckResponse = {
  data: {
    SOVITS_MOCK: false,
    SOVITS_DEVICE: 'cuda',
    torch_cuda_available: true,
    torch_device_count: 1,
    f0_method: 'rmvpe',
    auto_predict_f0: false,
    slice_db: -40,
    clip_seconds: 0,
    pad_seconds: 0.5,
    svc_model_presets: defaultHealthResponse.data.svc_model_presets,
  },
}

const defaultUploadResponse = {
  data: {
    vocals_id: 'vocals-1',
    is_vocal_only: false,
    input_quality_summary: {
      duration: 12.4,
      sample_rate: 44100,
      channels: 2,
      rms: 0.0812,
      peak: 0.6342,
      low_energy_ratio: 0.18,
      clipping_ratio: 0,
      silence_ratio: 0.12,
      is_too_short: false,
      is_probably_silent: false,
      quality_level: 'good',
      warnings: [],
    },
  },
}

const flush = async () => {
  await Promise.resolve()
  await Promise.resolve()
}

function buildWaveSurferInstance() {
  const handlers: Record<string, () => void> = {}
  return {
    on: vi.fn((event: string, callback: () => void) => {
      handlers[event] = callback
    }),
    load: vi.fn(() => {
      handlers.ready?.()
    }),
    play: vi.fn(async () => {}),
    pause: vi.fn(() => {}),
    stop: vi.fn(() => {}),
    destroy: vi.fn(() => {}),
  }
}

describe('App demo workspace', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    mockedAxios.post.mockReset()
    mockedAxios.get.mockReset()
    createWaveSurferMock.mockReset()
    createWaveSurferMock.mockImplementation(() => buildWaveSurferInstance())
    vi.stubGlobal(
      'URL',
      Object.assign(globalThis.URL ?? {}, {
        createObjectURL: vi.fn(() => 'blob:mock-url'),
        revokeObjectURL: vi.fn(),
      }),
    )

    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') {
        return defaultHealthResponse
      }
      if (url === '/api/v1/system/sovits-check') {
        return defaultSovitsCheckResponse
      }
      throw new Error(`Unexpected GET ${String(url)}`)
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

  it('默认显示正式演示工作台与关键状态徽章', async () => {
    await act(async () => {
      root.render(<App />)
      await flush()
    })

    expect(screen.getByText('基于文本提示词控制的歌声风格转换系统')).toBeInTheDocument()
    expect(screen.getByText('v1.1 真实多风格 preset 接入工作台')).toBeInTheDocument()
    expect(screen.getByText('真实 SVC')).toBeInTheDocument()
    expect(screen.getAllByText('Celery / Redis').length).toBeGreaterThan(0)
    expect(screen.getByText('GPU 可见')).toBeInTheDocument()
    expect(screen.getByText('Adapter trained 已接入')).toBeInTheDocument()
    expect(screen.getByText('查看技术详情')).toBeInTheDocument()
    expect(screen.getByText('source_repo：SuCicada/Lain-so-vits-svc-4.1')).toBeInTheDocument()
    expect(screen.getByText('license：gpl')).toBeInTheDocument()
  })

  it('上传后显示输入质量摘要与风险提示', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') {
        return {
          data: {
            ...defaultUploadResponse.data,
            input_quality_summary: {
              ...defaultUploadResponse.data.input_quality_summary,
              quality_level: 'warn',
              warnings: ['音频较短，转换结果可能不够稳定。'],
            },
          },
        }
      }
      throw new Error(`Unexpected POST ${String(url)}`)
    })

    await act(async () => {
      root.render(<App />)
      await flush()
    })

    await act(async () => {
      fireEvent.click(screen.getByText('Mock Upload'))
      await flush()
    })

    expect(screen.getByText('输入质量')).toBeInTheDocument()
    expect(screen.getAllByText('一般').length).toBeGreaterThan(0)
    expect(screen.getByText('音频较短，转换结果可能不够稳定。')).toBeInTheDocument()
  })

  it('bad 质量只提示不阻止默认 SVC 转换', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') {
        return {
          data: {
            ...defaultUploadResponse.data,
            input_quality_summary: {
              ...defaultUploadResponse.data.input_quality_summary,
              quality_level: 'bad',
              warnings: ['音频整体能量偏低或静音比例过高，可能导致转换失败或输出空洞。'],
              is_probably_silent: true,
            },
          },
        }
      }
      if (url === '/api/v1/convert') {
        return { data: { task_id: 'task-bad' } }
      }
      throw new Error(`Unexpected POST ${String(url)}`)
    })
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') {
        return defaultHealthResponse
      }
      if (url === '/api/v1/system/sovits-check') {
        return defaultSovitsCheckResponse
      }
      if (url === '/api/v1/tasks/task-bad') {
        return {
          data: {
            status: 'succeeded',
            stage: 'completed',
            progress: 100,
            message: '转换完成',
            result_metadata: {
              inference_mode: 'real',
              model_preset_id: 'final_primary',
              model_display_name: '当前可用默认 So-VITS-SVC 模型',
              speaker: 'lain',
              task_backend_mode: 'celery',
            },
          },
        }
      }
      if (url === '/api/v1/tasks/task-bad/result') {
        return { data: new Blob(['wav']) }
      }
      throw new Error(`Unexpected GET ${String(url)}`)
    })

    await act(async () => {
      root.render(<App />)
      await flush()
    })

    await act(async () => {
      fireEvent.click(screen.getByText('Mock Upload'))
      await flush()
    })

    await act(async () => {
      fireEvent.change(screen.getByLabelText('style-prompt'), { target: { value: '清亮、少年感' } })
      await flush()
    })

    expect(screen.getByText('输入质量较差，但不会阻止转换；建议在答辩演示前优先换用更干净的人声片段。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '开始转换' })).toBeEnabled()
  })

  it('默认 SVC 转换会携带高级参数并继续使用 /api/v1/convert', async () => {
    mockedAxios.post.mockImplementation(async (url: string, payload?: Record<string, unknown>) => {
      if (url === '/api/v1/upload') {
        return defaultUploadResponse
      }
      if (url === '/api/v1/convert') {
        return { data: { task_id: 'task-1', engine: 'sovits' } }
      }
      throw new Error(`Unexpected POST ${String(url)} ${JSON.stringify(payload)}`)
    })
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') {
        return defaultHealthResponse
      }
      if (url === '/api/v1/system/sovits-check') {
        return defaultSovitsCheckResponse
      }
      if (url === '/api/v1/tasks/task-1') {
        return {
          data: {
            status: 'succeeded',
            stage: 'completed',
            progress: 100,
            message: '转换完成',
            result_metadata: {
              inference_mode: 'real',
              model_preset_id: 'final_primary',
              model_display_name: '当前可用默认 So-VITS-SVC 模型',
              speaker: 'lain',
              task_backend_mode: 'celery',
              adapter_mode: 'trained',
              f0_method: 'rmvpe',
              auto_predict_f0: false,
              model_preset_ready: true,
            },
            selected_style: {
              style_id: 'male_youth',
              style_label: '少年感男声',
              model_preset_id: 'final_male_youth',
              model_preset_ready: false,
              model_preset_configured: false,
              current_style_has_dedicated_model: true,
              model_preset_notice: '该风格尚未绑定目标模型',
              reason: '命中关键词：清亮；选择 male_youth',
            },
          },
        }
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

    await act(async () => {
      fireEvent.click(screen.getByText('Mock Upload'))
      await flush()
    })

    await act(async () => {
      fireEvent.change(screen.getByLabelText('style-prompt'), { target: { value: '流行、清亮、少年感' } })
      await flush()
    })

    await act(async () => {
      fireEvent.click(screen.getByText('高级转换参数'))
      await flush()
    })

    await act(async () => {
      fireEvent.change(screen.getAllByRole('spinbutton')[0], { target: { value: '-2' } })
      await flush()
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始转换' }))
      await flush()
    })

    expect(mockedAxios.post).toHaveBeenCalledWith(
      '/api/v1/convert',
      expect.objectContaining({
        vocals_id: 'vocals-1',
        prompt_text: '流行、清亮、少年感',
        style_strength: 0.65,
        model_preset_id: 'final_primary',
        transpose: -2,
        f0_method: 'rmvpe',
        auto_predict_f0: false,
        slice_db: -40,
        clip_seconds: 0,
        pad_seconds: 0.5,
        allow_preset_fallback: false,
        engine: 'sovits',
      }),
    )
    expect(mockedAxios.post).not.toHaveBeenCalledWith('/api/v1/tasks', expect.anything())
    await waitFor(() => {
      expect(screen.getByText('A/B 波形对比')).toBeInTheDocument()
    })
    expect(screen.getAllByText('rmvpe').length).toBeGreaterThan(0)
    expect(
      screen.getByText('当前提示词匹配“少年感男声”风格，但该风格尚未绑定可用 SVC 目标模型；当前不会伪装为该风格转换。'),
    ).toBeInTheDocument()
  })

  it('开启 allow_preset_fallback 时显示请求 preset 与实际使用 preset', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') {
        return defaultUploadResponse
      }
      if (url === '/api/v1/convert') {
        return { data: { task_id: 'task-fallback', engine: 'sovits' } }
      }
      throw new Error(`Unexpected POST ${String(url)}`)
    })
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') {
        return defaultHealthResponse
      }
      if (url === '/api/v1/system/sovits-check') {
        return defaultSovitsCheckResponse
      }
      if (url === '/api/v1/tasks/task-fallback') {
        return {
          data: {
            status: 'succeeded',
            stage: 'completed',
            progress: 100,
            message: '转换完成',
            result_metadata: {
              inference_mode: 'real',
              model_preset_id: 'final_primary',
              requested_model_preset_id: 'final_male_youth',
              effective_model_preset_id: 'final_primary',
              preset_fallback_used: true,
              preset_fallback_reason:
                '当前提示词匹配专用风格 preset，但该 preset 尚未绑定可用 SVC 模型；本次已回退到 final_primary/lain，结果不代表该专用风格真实效果。',
              model_display_name: '当前可用默认 So-VITS-SVC 模型',
              speaker: 'lain',
              task_backend_mode: 'celery',
              adapter_mode: 'trained',
              f0_method: 'rmvpe',
              auto_predict_f0: false,
              model_preset_ready: true,
            },
            selected_style: {
              style_id: 'male_youth',
              style_label: '少年感男声',
              model_preset_id: 'final_male_youth',
              model_preset_ready: false,
              current_style_has_dedicated_model: true,
            },
          },
        }
      }
      if (url === '/api/v1/tasks/task-fallback/result') {
        return { data: new Blob(['wav']) }
      }
      throw new Error(`Unexpected GET ${String(url)}`)
    })

    await act(async () => {
      root.render(<App />)
      await flush()
    })
    await act(async () => {
      fireEvent.click(screen.getByText('Mock Upload'))
      await flush()
    })
    await act(async () => {
      fireEvent.change(screen.getByLabelText('style-prompt'), { target: { value: '少年感、男声、清亮' } })
      await flush()
    })
    await act(async () => {
      fireEvent.click(screen.getByText('高级转换参数'))
      await flush()
    })
    await act(async () => {
      const checkboxes = screen.getAllByRole('checkbox')
      fireEvent.click(checkboxes[checkboxes.length - 1])
      await flush()
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始转换' }))
      await flush()
    })

    expect(mockedAxios.post).toHaveBeenCalledWith(
      '/api/v1/convert',
      expect.objectContaining({
        allow_preset_fallback: true,
      }),
    )
    await waitFor(() => {
      expect(screen.getByText('当前提示词匹配专用风格 preset，但该 preset 尚未绑定可用 SVC 模型；本次已回退到 final_primary/lain，结果不代表该专用风格真实效果。')).toBeInTheDocument()
    })
    expect(screen.getAllByText('final_male_youth').length).toBeGreaterThan(0)
    expect(screen.getAllByText('final_primary').length).toBeGreaterThan(0)
  })

  it('WaveSurfer 初始化失败时会回退到原生播放器', async () => {
    createWaveSurferMock.mockImplementationOnce(() => {
      throw new Error('boom')
    })
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') {
        return defaultUploadResponse
      }
      throw new Error(`Unexpected POST ${String(url)}`)
    })

    await act(async () => {
      root.render(<App />)
      await flush()
    })

    await act(async () => {
      fireEvent.click(screen.getByText('Mock Upload'))
      await flush()
    })

    expect(screen.getByText('WaveSurfer 初始化失败，已回退到原生播放器。')).toBeInTheDocument()
  })
})
