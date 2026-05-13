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

  beforeEach(() => {
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

  async function runSuccessFlow(prompt = '清亮少年感男声') {
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
    expect(screen.getByText('模型预设（model_preset / final_primary）')).toBeInTheDocument()
    expect(screen.getByText('目标音色（speaker / lain）')).toBeInTheDocument()
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
