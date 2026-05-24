import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { fireEvent, screen, waitFor, within } from '@testing-library/dom'
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
      presets: [
        { preset_id: 'final_primary', ready: true, display_name: 'Default', speaker: 'lain', internal_test_only: false },
        {
          preset_id: 'final_male_powerful',
          ready: true,
          display_name: 'Powerful Male',
          speaker: 'AY',
          internal_test_only: true,
          temporary_demo_reason: '用于本地毕业设计效果对比，授权状态待确认，不作为公开演示默认模型',
        },
        {
          preset_id: 'final_male_youth',
          ready: true,
          display_name: 'Youth Male',
          speaker: 'Nova_Adult',
          internal_test_only: true,
          temporary_demo_reason: '用于本地毕业设计效果对比，授权状态待确认，不作为公开演示默认模型',
        },
      ],
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
    prompt_text: '清亮少年感男声',
    input: {
      ok: true,
      brightness_score: 0.2,
      energy_score: 0.3,
      softness_score: 0.4,
      thickness_score: 0.7,
      f0_median: 190,
      spectral_centroid_mean: 2100,
      voiced_ratio: 0.92,
      duration_seconds: 12.4,
    },
    output: {
      ok: true,
      brightness_score: 0.5,
      energy_score: 0.44,
      softness_score: 0.35,
      thickness_score: 0.52,
      f0_median: 220,
      spectral_centroid_mean: 2450,
      voiced_ratio: 0.93,
      duration_seconds: 12.3,
    },
    prompt_targets: {
      prompt_text: '清亮少年感男声',
      target_dimensions: { brightness: 'up' },
      matched_keywords: ['清亮', '男声'],
      human_readable_targets: ['亮度提升'],
    },
    comparisons: [],
    radar: { dimensions: [], input: [], output: [], target: [] },
    summary: {
      matched_count: 3,
      total_count: 5,
      score: 0.6,
      level: 'partial',
      text: '旧面板字段',
    },
    warnings: ['旧说明'],
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
      adapter_type: 'trained_mlp',
      adapter_checkpoint: '/home/featurize/work/BS/runtime/style_adapter/text_style_adapter_1000.pt',
      model_preset_id: 'final_primary',
      effective_model_preset_id: 'final_primary',
      internal_test_only: false,
      speaker: 'lain',
      duration_seconds: 12.3,
      sample_rate: 44100,
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

describe('App compact localized dashboard', () => {
  let container: HTMLDivElement
  let root: Root
  let canvasContextSpy: { mockRestore: () => void } | null = null
  let fetchMock: ReturnType<typeof vi.fn>
  let decodedDuration = 8.1
  let decodedSampleRate = 48000

  beforeEach(() => {
    decodedDuration = 8.1
    decodedSampleRate = 48000
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    mockedAxios.get.mockReset()
    mockedAxios.post.mockReset()

    vi.stubGlobal(
      'URL',
      Object.assign(globalThis.URL ?? {}, {
        createObjectURL: vi.fn(() => `blob:mock-${Math.random()}`),
        revokeObjectURL: vi.fn(),
      }),
    )

    fetchMock = vi.fn(async () => ({
      ok: true,
      headers: {
        get: (key: string) => (key.toLowerCase() === 'content-type' ? 'audio/wav' : null),
      },
      arrayBuffer: async () => new ArrayBuffer(32),
    }))
    vi.stubGlobal('fetch', fetchMock)

    class MockAudioContext {
      async decodeAudioData(_input: ArrayBuffer) {
        return {
          duration: decodedDuration,
          sampleRate: decodedSampleRate,
          getChannelData: () => {
            const values = new Float32Array(2048)
            values.fill(0.1)
            return values
          },
        } as unknown as AudioBuffer
      }

      async close() {
        return undefined
      }
    }
    vi.stubGlobal('AudioContext', MockAudioContext)

    canvasContextSpy = vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => {
      const gradient = { addColorStop: vi.fn() } as unknown as CanvasGradient
      return {
        clearRect: vi.fn(),
        fillRect: vi.fn(),
        setTransform: vi.fn(),
        createLinearGradient: vi.fn(() => gradient),
        fillText: vi.fn(),
        save: vi.fn(),
        restore: vi.fn(),
        translate: vi.fn(),
        rotate: vi.fn(),
      } as unknown as CanvasRenderingContext2D
    })

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
    canvasContextSpy?.mockRestore()
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

  async function runSuccessFlow(prompt = '清亮少年感男声', metadataOverrides?: Record<string, unknown>) {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') return uploadOk
      if (url === '/api/v1/convert') return { data: { task_id: 'task-1' } }
      if (url === '/api/v1/style-analysis/compare') return { data: styleEvidenceResponse() }
      throw new Error(`Unexpected POST ${url}`)
    })

    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') return defaultHealth
      if (url === '/api/v1/system/sovits-check') return defaultCheck
      if (url === '/api/v1/tasks/task-1') return { data: successTaskData(metadataOverrides) }
      if (url === '/api/v1/tasks/task-1/result') return { data: new Blob(['wav']) }
      throw new Error(`Unexpected GET ${url}`)
    })

    await renderApp()
    await selectAndUpload()

    await act(async () => {
      fireEvent.change(screen.getByLabelText('风格提示词'), { target: { value: prompt } })
      await flush()
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始风格转换' }))
      await flush()
    })

    await waitFor(() => expect(screen.getByText('转换成功')).toBeInTheDocument())
  }

  it('存在三列工作台并移除转换前后音频对比卡片', async () => {
    await renderApp()

    expect(screen.getByTestId('workspace-grid')).toBeInTheDocument()
    expect(screen.getByTestId('input-column')).toBeInTheDocument()
    expect(screen.getByTestId('result-column')).toBeInTheDocument()
    expect(screen.getByTestId('metrics-column')).toBeInTheDocument()

    expect(screen.queryByText('转换前后音频对比')).not.toBeInTheDocument()
    expect(screen.queryByText('转换前后音频可以对比播放')).not.toBeInTheDocument()
  })

  it('转换成功后显示频谱图对比，并保留结果/指标/技术链路主结构', async () => {
    await runSuccessFlow()

    expect(screen.getByText('转换结果')).toBeInTheDocument()
    expect(screen.getByText('关键指标对比')).toBeInTheDocument()
    expect(screen.getByText('技术链路')).toBeInTheDocument()

    expect(screen.getByText('频谱图对比')).toBeInTheDocument()
    expect(screen.getAllByText('上传音频').length).toBeGreaterThan(0)
    expect(screen.getAllByText('转换后音频').length).toBeGreaterThan(0)

    expect(screen.queryByText('转换前后音频对比')).not.toBeInTheDocument()
    expect(screen.queryByText('转换前后音频可以对比播放')).not.toBeInTheDocument()
  })

  it('注入强度控件默认 0.10，支持 0-1 范围和 0.05 步长，并随请求发送', async () => {
    mockedAxios.post.mockImplementation(async (url: string, payload?: Record<string, unknown>) => {
      if (url === '/api/v1/upload') return uploadOk
      if (url === '/api/v1/convert') return { data: { task_id: 'task-1', payload } }
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

    const slider = container.querySelector('#film-strength-slider') as HTMLInputElement
    expect(slider).toBeTruthy()
    expect(slider.min).toBe('0')
    expect(slider.max).toBe('1')
    expect(slider.step).toBe('0.05')
    expect(slider.value).toBe('0.1')
    expect(screen.getByText('注入强度（0.10）')).toBeInTheDocument()

    await act(async () => {
      fireEvent.change(slider, { target: { value: '0.35' } })
      await flush()
    })
    expect(screen.getByText('注入强度（0.35）')).toBeInTheDocument()

    await act(async () => {
      fireEvent.change(screen.getByLabelText('风格提示词'), { target: { value: '清亮风格' } })
      await flush()
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始风格转换' }))
      await flush()
    })
    await waitFor(() => expect(screen.getByText('转换成功')).toBeInTheDocument())

    const convertCall = mockedAxios.post.mock.calls.find((call) => call[0] === '/api/v1/convert')
    expect(convertCall).toBeTruthy()
    expect((convertCall?.[1] as Record<string, unknown>)?.film_strength).toBe(0.35)
  })

  it('默认自动模式不会强制传 final_primary，而是让后端按提示词选模型', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') return uploadOk
      if (url === '/api/v1/convert') return { data: { task_id: 'task-1' } }
      if (url === '/api/v1/style-analysis/compare') return { data: styleEvidenceResponse() }
      throw new Error(`Unexpected POST ${url}`)
    })

    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') return defaultHealth
      if (url === '/api/v1/system/sovits-check') return defaultCheck
      if (url === '/api/v1/tasks/task-1') {
        return {
          data: successTaskData({
            model_preset_id: 'final_male_powerful',
            effective_model_preset_id: 'final_male_powerful',
            speaker: 'AY',
          }),
        }
      }
      if (url === '/api/v1/tasks/task-1/result') return { data: new Blob(['wav']) }
      throw new Error(`Unexpected GET ${url}`)
    })

    await renderApp()
    await selectAndUpload()

    await act(async () => {
      fireEvent.change(screen.getByLabelText('风格提示词'), { target: { value: '低沉磁性叙事感' } })
      await flush()
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始风格转换' }))
      await flush()
    })

    await waitFor(() => expect(screen.getByText('转换成功')).toBeInTheDocument())
    const convertCall = mockedAxios.post.mock.calls.find((call) => call[0] === '/api/v1/convert')
    expect(convertCall).toBeTruthy()
    expect((convertCall?.[1] as Record<string, unknown>)?.model_preset_id).toBeUndefined()
    expect(screen.getByTestId('tech-main-fields').textContent ?? '').toContain('模型预设final_male_powerful')
  })

  it('手动模式会显式传所选模型，并提示内部测试模型边界', async () => {
    mockedAxios.post.mockImplementation(async (url: string) => {
      if (url === '/api/v1/upload') return uploadOk
      if (url === '/api/v1/convert') return { data: { task_id: 'task-1' } }
      if (url === '/api/v1/style-analysis/compare') return { data: styleEvidenceResponse() }
      throw new Error(`Unexpected POST ${url}`)
    })

    mockedAxios.get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/system/health') return defaultHealth
      if (url === '/api/v1/system/sovits-check') return defaultCheck
      if (url === '/api/v1/tasks/task-1') {
        return {
          data: successTaskData({
            model_preset_id: 'final_male_powerful',
            effective_model_preset_id: 'final_male_powerful',
            internal_test_only: true,
            temporary_demo_reason: '用于本地毕业设计效果对比，授权状态待确认，不作为公开演示默认模型',
            speaker: 'AY',
          }),
        }
      }
      if (url === '/api/v1/tasks/task-1/result') return { data: new Blob(['wav']) }
      throw new Error(`Unexpected GET ${url}`)
    })

    await renderApp()
    await selectAndUpload()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '手动选择模型' }))
      await flush()
    })

    const modelSelect = screen.getByLabelText('手动模型预设') as HTMLSelectElement
    expect(modelSelect.value).toBe('final_male_powerful')
    expect(screen.getByText('用于本地毕业设计效果对比，授权状态待确认，不作为公开演示默认模型')).toBeInTheDocument()

    await act(async () => {
      fireEvent.change(screen.getByLabelText('风格提示词'), { target: { value: '低沉磁性叙事感' } })
      await flush()
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '开始风格转换' }))
      await flush()
    })

    await waitFor(() => expect(screen.getByText('转换成功')).toBeInTheDocument())
    const convertCall = mockedAxios.post.mock.calls.find((call) => call[0] === '/api/v1/convert')
    expect(convertCall).toBeTruthy()
    expect((convertCall?.[1] as Record<string, unknown>)?.model_preset_id).toBe('final_male_powerful')
    expect(screen.getAllByText('用于本地毕业设计效果对比，授权状态待确认，不作为公开演示默认模型').length).toBeGreaterThan(0)
  })

  it('选择上传文件后优先使用本地 blob URL 生成上传频谱', async () => {
    const createObjectURL = globalThis.URL.createObjectURL as unknown as ReturnType<typeof vi.fn>
    createObjectURL.mockReset()
    createObjectURL
      .mockImplementationOnce(() => 'blob:local-input-preview')
      .mockImplementationOnce(() => 'blob:converted-output')

    await runSuccessFlow('清亮风格')

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled()
    })
    const calledUrls = fetchMock.mock.calls.map((call) => String(call[0]))
    expect(calledUrls).toContain('blob:local-input-preview')
  })

  it('缺少 inputUrl 时显示“上传音频暂不可预览”', async () => {
    const createObjectURL = globalThis.URL.createObjectURL as unknown as ReturnType<typeof vi.fn>
    createObjectURL.mockReset()
    createObjectURL
      .mockImplementationOnce(() => '')
      .mockImplementation(() => `blob:mock-${Math.random()}`)

    await runSuccessFlow('清亮风格')

    expect(screen.getByText('上传音频暂不可预览')).toBeInTheDocument()
  })

  it('缺少 output blob URL 时回退到 result_url 生成输出频谱', async () => {
    const createObjectURL = globalThis.URL.createObjectURL as unknown as ReturnType<typeof vi.fn>
    createObjectURL.mockReset()
    createObjectURL
      .mockImplementationOnce(() => 'blob:local-input-preview')
      .mockImplementationOnce(() => '')

    await runSuccessFlow('清亮风格')

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled()
    })
    const calledUrls = fetchMock.mock.calls.map((call) => String(call[0]))
    expect(calledUrls).toContain('/api/v1/tasks/task-1/result')
  })

  it('metadata.output_url 指向服务器本地路径时，输出频谱仍优先使用已下载 blob URL', async () => {
    const createObjectURL = globalThis.URL.createObjectURL as unknown as ReturnType<typeof vi.fn>
    createObjectURL.mockReset()
    createObjectURL
      .mockImplementationOnce(() => 'blob:local-input-preview')
      .mockImplementationOnce(() => 'blob:converted-output')

    await runSuccessFlow('清亮风格', { output_url: '/tmp/runtime/converted.wav' })

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled()
    })

    const calledUrls = fetchMock.mock.calls.map((call) => String(call[0]))
    expect(calledUrls).toContain('blob:converted-output')
    expect(calledUrls).not.toContain('/tmp/runtime/converted.wav')
  })

  it('metadata duration/sample_rate 为 0 且无运行时元数据时显示未返回', async () => {
    fetchMock.mockReset()
    fetchMock.mockImplementation(async () => ({
      ok: true,
      headers: {
        get: (key: string) => (key.toLowerCase() === 'content-type' ? 'text/html; charset=utf-8' : null),
      },
      arrayBuffer: async () => new ArrayBuffer(16),
    }))

    await runSuccessFlow('清亮风格', { duration_seconds: 0, sample_rate: 0 })

    const resultMain = screen.getByTestId('result-main-fields').textContent ?? ''
    expect(resultMain).toContain('音频时长未返回')
    expect(resultMain).toContain('采样率未返回')
    expect(resultMain).not.toContain('0.00 秒')
    expect(resultMain).not.toContain('0 Hz')
  })

  it('output audio loadedmetadata 可回填时长显示', async () => {
    fetchMock.mockReset()
    fetchMock.mockImplementation(async () => ({
      ok: true,
      headers: {
        get: (key: string) => (key.toLowerCase() === 'content-type' ? 'text/html; charset=utf-8' : null),
      },
      arrayBuffer: async () => new ArrayBuffer(16),
    }))

    await runSuccessFlow('清亮风格', { duration_seconds: 0, sample_rate: 0 })

    const outputAudio = container.querySelector('.result-audio') as HTMLAudioElement
    Object.defineProperty(outputAudio, 'duration', {
      value: 8.5,
      configurable: true,
    })

    await act(async () => {
      fireEvent.loadedMetadata(outputAudio)
      await flush()
    })

    expect(screen.getByText('8.50 秒')).toBeInTheDocument()
  })

  it('频谱解码成功时回填采样率显示', async () => {
    decodedSampleRate = 32000
    await runSuccessFlow('清亮风格', { sample_rate: 0 })

    await waitFor(() => {
      expect(screen.getByText('32000 Hz')).toBeInTheDocument()
    })
  })

  it('技术链路优先显示后端返回的注入强度', async () => {
    await runSuccessFlow('清亮风格', { film_strength: 0.45 })

    const techMain = screen.getByTestId('tech-main-fields').textContent ?? ''
    expect(techMain).toContain('注入强度0.45')
  })

  it('input 频谱请求返回 text/html 时显示上传频谱失败文案', async () => {
    fetchMock.mockReset()
    fetchMock
      .mockImplementationOnce(async () => ({
        ok: true,
        headers: {
          get: (key: string) => (key.toLowerCase() === 'content-type' ? 'text/html; charset=utf-8' : null),
        },
        arrayBuffer: async () => new ArrayBuffer(16),
      }))
      .mockImplementation(async () => ({
        ok: true,
        headers: {
          get: (key: string) => (key.toLowerCase() === 'content-type' ? 'audio/wav' : null),
        },
        arrayBuffer: async () => new ArrayBuffer(16),
      }))

    await runSuccessFlow('清亮风格')

    await waitFor(() => {
      expect(screen.getByText('上传音频频谱生成失败：返回内容不是音频')).toBeInTheDocument()
    })
  })

  it('output 频谱请求返回非音频时显示具体失败原因', async () => {
    fetchMock.mockReset()
    fetchMock
      .mockImplementationOnce(async () => ({
        ok: true,
        headers: {
          get: (key: string) => (key.toLowerCase() === 'content-type' ? 'audio/wav' : null),
        },
        arrayBuffer: async () => new ArrayBuffer(16),
      }))
      .mockImplementationOnce(async () => ({
        ok: true,
        headers: {
          get: (key: string) => (key.toLowerCase() === 'content-type' ? 'text/html; charset=utf-8' : null),
        },
        arrayBuffer: async () => new ArrayBuffer(16),
      }))

    await runSuccessFlow('清亮风格')

    await waitFor(() => {
      expect(screen.getByText('转换后音频频谱生成失败：返回内容不是音频')).toBeInTheDocument()
    })
  })

  it('主界面显示中文字段和中文值，且主显示区不出现英文原字段', async () => {
    await runSuccessFlow()

    expect(screen.getAllByText('条件控制模式').length).toBeGreaterThan(0)
    expect(screen.getAllByText('注入强度').length).toBeGreaterThan(0)
    expect(screen.getAllByText('音频时长').length).toBeGreaterThan(0)
    expect(screen.getAllByText('采样率').length).toBeGreaterThan(0)
    expect(screen.getByText('结果接口')).toBeInTheDocument()
    expect(screen.getAllByText('适配器权重').length).toBeGreaterThan(0)
    expect(screen.getAllByText('已加载训练适配器').length).toBeGreaterThan(0)
    expect(screen.getAllByText('目标音色').length).toBeGreaterThan(0)
    expect(screen.getAllByText('模型预设').length).toBeGreaterThan(0)

    expect(screen.getAllByText('内部 FiLM 注入').length).toBeGreaterThan(0)
    expect(screen.getAllByText('训练适配器').length).toBeGreaterThan(0)
    expect(screen.getByText('训练得到的 MLP 适配器')).toBeInTheDocument()
    expect(screen.getAllByText('主模型预设').length).toBeGreaterThan(0)
    expect(screen.getAllByText('当前目标音色 lain').length).toBeGreaterThan(0)
    expect(screen.getAllByText('是').length).toBeGreaterThan(0)

    const taskMain = screen.getByTestId('task-main-fields').textContent ?? ''
    const resultMain = screen.getByTestId('result-main-fields').textContent ?? ''
    const techMain = screen.getByTestId('tech-main-fields').textContent ?? ''
    const mainVisibleText = `${taskMain}${resultMain}${techMain}`

    expect(mainVisibleText).not.toContain('condition_mode')
    expect(mainVisibleText).not.toContain('film_strength')
    expect(mainVisibleText).not.toContain('duration_seconds')
    expect(mainVisibleText).not.toContain('sample_rate')
    expect(mainVisibleText).not.toContain('result_url')
    expect(mainVisibleText).not.toContain('adapter_checkpoint')
    expect(mainVisibleText).not.toContain('text_style_adapter_loaded')
  })

  it('字段说明默认折叠，展开后显示中英对照术语', async () => {
    await runSuccessFlow('清亮风格')

    const termsDetails = screen.getByTestId('terms-details') as HTMLDetailsElement
    expect(termsDetails.open).toBe(false)

    await act(async () => {
      fireEvent.click(within(termsDetails).getByText('字段说明'))
      await flush()
    })

    expect(termsDetails.open).toBe(true)
    expect(screen.getByText('模型预设（model_preset）')).toBeInTheDocument()
    expect(screen.getByText('目标音色（speaker）')).toBeInTheDocument()
    expect(screen.getByText('音频时长（duration_seconds）')).toBeInTheDocument()
    expect(screen.getByText('内部 FiLM 注入（internal_film）')).toBeInTheDocument()
    expect(screen.getByText('已加载训练适配器（text_style_adapter_loaded）')).toBeInTheDocument()
    expect(screen.getByText('适配器权重（adapter_checkpoint）')).toBeInTheDocument()
  })

  it('prompt 包含男声且目标音色为 lain 时显示中文边界 warning', async () => {
    await runSuccessFlow('清亮、少年感、男声')

    await waitFor(() => {
      expect(screen.getByText(/当前提示词包含“男声”方向/)).toBeInTheDocument()
    })
  })

  it('succeeded 但无 result_url 时显示错误且不显示成功播放器', async () => {
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
      fireEvent.change(screen.getByLabelText('风格提示词'), { target: { value: '清亮风格' } })
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
})
