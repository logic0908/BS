import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { fireEvent, screen, waitFor } from '@testing-library/dom'
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
  default: ({ audioUrl }: { audioUrl: string }) => <div>Waveform:{audioUrl}</div>,
}))

vi.mock('./components/StyleControls', () => ({
  default: ({
    prompt,
    setPrompt,
    onConvert,
    disabled,
    isLoading,
    promptError,
    actionLabel,
  }: {
    prompt: string
    setPrompt: (value: string) => void
    onConvert: () => void
    disabled: boolean
    isLoading: boolean
    promptError?: string | null
    actionLabel?: string
  }) => (
    <div>
      <textarea
        aria-label="style-prompt"
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
      />
      {promptError ? <div>{promptError}</div> : null}
      <button
        type="button"
        disabled={disabled || !prompt.trim() || isLoading}
        onClick={onConvert}
      >
        {isLoading ? '转换中...' : actionLabel || '开始转换'}
      </button>
    </div>
  ),
}))

const mockedAxios = axios as any

const defaultHealthResponse = {
  data: {
    ok: true,
    app_status: 'ok',
    python_executable: '/usr/bin/python',
    python_version: '3.11',
    conda_env: 'base',
    mock_mode: true,
    frontend_build_info: null,
    timestamp: '2026-04-27T00:00:00+00:00',
  },
}

const defaultSovitsCheckResponse = {
  data: {
    SOVITS_MOCK: true,
    SOVITS_REPO_DIR_exists: true,
    SOVITS_MODEL_PATH_exists: true,
    SOVITS_CONFIG_PATH_exists: true,
    SOVITS_SPEAKER: 'speaker_a',
    SOVITS_DEVICE: 'cuda',
    SOVITS_PYTHON: '/usr/bin/python',
    torch_version: '2.3.0',
    torch_cuda_available: false,
    torch_cuda_version: '12.1',
    torch_device_count: 0,
    dev_nvidia_devices: [],
    nvidia_smi: { return_code: 1, stdout: '', stderr: 'not visible' },
    import_status: {
      numpy: { ok: true },
      scipy: { ok: true },
      librosa: { ok: true },
      numba: { ok: true },
    },
  },
}

const flush = async () => {
  await Promise.resolve()
  await Promise.resolve()
}

describe('App demo UI', () => {
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

  it('默认页面显示 Hero 与 SVC 主链路徽章', async () => {
    await act(async () => {
      root.render(<App />)
      await flush()
    })

    expect(screen.getByText('基于文本提示词控制的歌声风格转换系统')).toBeInTheDocument()
    expect(screen.getByText('SVC 主链路')).toBeInTheDocument()
  })

  it('未输入 prompt 时开始转换按钮禁用', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') {
        return { data: { vocals_id: 'vocals-1' } }
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

    expect(screen.getByText('请先输入目标风格描述')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '开始转换' })).toBeDisabled()
  })

  it('输入 prompt 且上传成功后会调用 /api/v1/convert', async () => {
    mockedAxios.post.mockImplementation(async (url: string, payload?: Record<string, unknown>) => {
      if (url === '/api/v1/upload') {
        return { data: { vocals_id: 'vocals-1' } }
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
            inference_mode: 'mock',
            result_metadata: {
              inference_mode: 'mock',
              mock_enabled: true,
              speaker: 'speaker_a',
              model_path: '/models/mock-model.pth',
              called_inference_main: false,
              final_output_path: '/tmp/converted.wav',
            },
            selected_style: {
              style_id: 'pop_bright',
              description: '流行、明亮、清澈、少年感',
              match_score: 88,
              matched_keywords: ['流行', '明亮'],
              reason: '命中关键词：流行、明亮；选择 pop_bright',
            },
          },
        }
      }
      if (url === '/api/v1/tasks/task-1/result') {
        return { data: new Blob(['wav']), headers: { 'x-svc-inference-mode': 'mock' } }
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
      fireEvent.click(screen.getByRole('button', { name: '开始转换' }))
      await flush()
    })

    expect(mockedAxios.post).toHaveBeenCalledWith(
      '/api/v1/convert',
      expect.objectContaining({
        vocals_id: 'vocals-1',
        prompt_text: '流行、清亮、少年感',
        style_strength: 0.65,
        engine: 'sovits',
      }),
    )
  })

  it('mock 模式显示 Mock SVC 提示', async () => {
    await act(async () => {
      root.render(<App />)
      await flush()
    })

    expect(screen.getAllByText(/当前为 Mock SVC，仅验证流程/).length).toBeGreaterThan(0)
  })

  it('real 模式显示 Real So-VITS-SVC 提示', async () => {
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') {
        return {
          data: {
            ...defaultHealthResponse.data,
            mock_mode: false,
          },
        }
      }
      if (url === '/api/v1/system/sovits-check') {
        return {
          data: {
            ...defaultSovitsCheckResponse.data,
            SOVITS_MOCK: false,
            torch_cuda_available: true,
            dev_nvidia_devices: ['/dev/nvidia0'],
            nvidia_smi: { return_code: 0, stdout: 'ok', stderr: '' },
          },
        }
      }
      throw new Error(`Unexpected GET ${String(url)}`)
    })

    await act(async () => {
      root.render(<App />)
      await flush()
    })

    expect(screen.getByText('真实 SVC')).toBeInTheDocument()
  })

  it('real 推理完成后显示真实 So-VITS-SVC 元信息', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') {
        return { data: { vocals_id: 'vocals-1' } }
      }
      if (url === '/api/v1/convert') {
        return { data: { task_id: 'task-real', engine: 'sovits' } }
      }
      throw new Error(`Unexpected POST ${String(url)}`)
    })
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') {
        return {
          data: {
            ...defaultHealthResponse.data,
            mock_mode: false,
          },
        }
      }
      if (url === '/api/v1/system/sovits-check') {
        return {
          data: {
            ...defaultSovitsCheckResponse.data,
            SOVITS_MOCK: false,
            torch_cuda_available: true,
            dev_nvidia_devices: ['/dev/nvidia0'],
            nvidia_smi: { return_code: 0, stdout: 'ok', stderr: '' },
          },
        }
      }
      if (url === '/api/v1/tasks/task-real') {
        return {
          data: {
            status: 'succeeded',
            stage: 'completed',
            progress: 100,
            message: '转换完成',
            inference_mode: 'real',
            result_metadata: {
              inference_mode: 'real',
              mock_enabled: false,
              speaker: 'villager',
              model_path: '/models/minecraft_villager/G_4000.pth',
              config_path: '/models/minecraft_villager/config.json',
              selected_output: '/repo/results/test.wav_0key_villager_sovits_pm.flac',
              final_output_path: '/tmp/converted.wav',
              return_code: 0,
              elapsed_seconds: 34.297,
              called_inference_main: true,
            },
            selected_style: {
              style_id: 'pop_bright',
              description: '流行、明亮、清澈、少年感',
              match_score: 88,
              matched_keywords: ['流行', '明亮'],
              reason: '命中关键词：流行、明亮；选择 pop_bright',
            },
          },
        }
      }
      if (url === '/api/v1/tasks/task-real/result') {
        return {
          data: new Blob(['wav']),
          headers: {
            'x-svc-inference-mode': 'real',
            'x-svc-model-path': '/models/minecraft_villager/G_4000.pth',
            'x-svc-speaker': 'villager',
          },
        }
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
      fireEvent.change(screen.getByLabelText('style-prompt'), { target: { value: '流行、清亮' } })
      await flush()
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始转换' }))
      await flush()
    })

    await waitFor(() => {
      expect(screen.getAllByText('真实 So-VITS-SVC').length).toBeGreaterThan(0)
    })
    expect(screen.getByText('villager')).toBeInTheDocument()
    expect(screen.getByText('G_4000.pth')).toBeInTheDocument()
    expect(screen.getByText('是')).toBeInTheDocument()
  })

  it('selected_style 存在时显示 style_id description reason', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') {
        return { data: { vocals_id: 'vocals-1' } }
      }
      if (url === '/api/v1/convert') {
        return { data: { task_id: 'task-1', engine: 'sovits' } }
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
      if (url === '/api/v1/tasks/task-1') {
        return {
          data: {
            status: 'succeeded',
            stage: 'completed',
            progress: 100,
            message: '转换完成',
            inference_mode: 'mock',
            result_metadata: {
              inference_mode: 'mock',
              mock_enabled: true,
              speaker: 'speaker_a',
              model_path: '/models/mock-model.pth',
              called_inference_main: false,
              final_output_path: '/tmp/converted.wav',
            },
            selected_style: {
              style_id: 'lyrical_soft',
              description: '抒情、温柔、细腻、治愈',
              match_score: 77,
              matched_keywords: ['温柔', '抒情'],
              reason: '命中关键词：温柔、抒情；选择 lyrical_soft',
            },
          },
        }
      }
      if (url === '/api/v1/tasks/task-1/result') {
        return { data: new Blob(['wav']), headers: { 'x-svc-inference-mode': 'mock' } }
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
      fireEvent.change(screen.getByLabelText('style-prompt'), { target: { value: '温柔抒情' } })
      await flush()
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始转换' }))
      await flush()
    })

    await waitFor(() => {
      expect(screen.getByText('风格匹配信息')).toBeInTheDocument()
    })
    expect(screen.getAllByText(/lyrical_soft/).length).toBeGreaterThan(0)
    expect(screen.getByText(/抒情、温柔、细腻、治愈/)).toBeInTheDocument()
    expect(screen.getByText(/命中关键词：温柔、抒情；选择 lyrical_soft/)).toBeInTheDocument()
  })

  it('match_score=0 时显示 fallback warning', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') {
        return { data: { vocals_id: 'vocals-1' } }
      }
      if (url === '/api/v1/convert') {
        return { data: { task_id: 'task-1', engine: 'sovits' } }
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
      if (url === '/api/v1/tasks/task-1') {
        return {
          data: {
            status: 'succeeded',
            stage: 'completed',
            progress: 100,
            message: '转换完成',
            inference_mode: 'mock',
            result_metadata: {
              inference_mode: 'mock',
              mock_enabled: true,
              speaker: 'speaker_a',
              model_path: '/models/mock-model.pth',
              called_inference_main: false,
              final_output_path: '/tmp/converted.wav',
            },
            selected_style: {
              style_id: 'pop_bright',
              description: '流行、明亮、清澈、少年感',
              match_score: 0,
              matched_keywords: [],
              reason: '未命中明显关键词；使用默认候选 pop_bright',
            },
          },
        }
      }
      if (url === '/api/v1/tasks/task-1/result') {
        return { data: new Blob(['wav']), headers: { 'x-svc-inference-mode': 'mock' } }
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
      fireEvent.change(screen.getByLabelText('style-prompt'), { target: { value: '未知风格' } })
      await flush()
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始转换' }))
      await flush()
    })

    expect(screen.getByText(/提示词未命中风格库，当前使用默认 preset/)).toBeInTheDocument()
  })

  it('StyleSinger 高级模式默认折叠，但可以展开', async () => {
    await act(async () => {
      root.render(<App />)
      await flush()
    })

    const summary = screen.getByText('高级模式：StyleSinger 乐谱/metadata 分支')
    const details = summary.closest('details')
    expect(details).not.toHaveAttribute('open')

    await act(async () => {
      fireEvent.click(summary)
      await flush()
    })

    expect(details).toHaveAttribute('open')
    expect(screen.getByText('extract_features')).toBeInTheDocument()
  })

  it('health panel 能显示 GPU 不可见提示', async () => {
    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') {
        return {
          data: {
            ...defaultHealthResponse.data,
            mock_mode: false,
          },
        }
      }
      if (url === '/api/v1/system/sovits-check') {
        return {
          data: {
            ...defaultSovitsCheckResponse.data,
            SOVITS_MOCK: false,
            torch_cuda_available: false,
            dev_nvidia_devices: [],
            nvidia_smi: { return_code: 1, stdout: '', stderr: 'not visible' },
          },
        }
      }
      throw new Error(`Unexpected GET ${String(url)}`)
    })

    await act(async () => {
      root.render(<App />)
      await flush()
    })

    await act(async () => {
      fireEvent.click(screen.getByText('系统状态与环境诊断'))
      await flush()
    })

    expect(screen.getAllByText(/当前 GPU 对容器不可见，真实推理可能失败/).length).toBeGreaterThan(0)
  })
})
