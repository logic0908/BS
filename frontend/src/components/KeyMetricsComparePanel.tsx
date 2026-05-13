import type { InputQualitySummary, ResultMetadata, StyleEvidenceCompareResponse } from '../types'

type MetricRow = {
  key: string
  label: string
  input: number | null
  output: number | null
}

interface KeyMetricsComparePanelProps {
  analysis: StyleEvidenceCompareResponse | null
  resultMetadata: ResultMetadata | null
  inputQuality: InputQualitySummary | null
}

const METRIC_DEFS: Array<{ key: string; label: string }> = [
  { key: 'brightness_score', label: '亮度' },
  { key: 'energy_score', label: '能量' },
  { key: 'softness_score', label: '柔和度' },
  { key: 'thickness_score', label: '厚度' },
  { key: 'f0_median', label: '基频中位数' },
  { key: 'spectral_centroid_mean', label: '频谱中心均值' },
  { key: 'voiced_ratio', label: '有声帧比例' },
  { key: 'duration_seconds', label: '时长' },
]

function getMetricValue(source: Record<string, unknown> | null | undefined, key: string): number | null {
  if (!source) return null
  const value = source[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function formatValue(value: number | null): string {
  if (value === null) return '未返回'
  return value.toFixed(3)
}

function formatDelta(input: number | null, output: number | null): string {
  if (input === null || output === null) return '未返回'
  const delta = output - input
  return `${delta >= 0 ? '+' : ''}${delta.toFixed(3)}`
}

function buildRows(
  analysis: StyleEvidenceCompareResponse | null,
  resultMetadata: ResultMetadata | null,
  inputQuality: InputQualitySummary | null,
): MetricRow[] {
  const input = (analysis?.input ?? null) as Record<string, unknown> | null
  const output = (analysis?.output ?? null) as Record<string, unknown> | null

  return METRIC_DEFS.map((def) => {
    if (def.key === 'duration_seconds') {
      const inputDuration = inputQuality?.duration ?? getMetricValue(input, 'duration_seconds')
      const outputDuration =
        (typeof resultMetadata?.duration_seconds === 'number' ? resultMetadata.duration_seconds : null) ??
        getMetricValue(output, 'duration_seconds')
      return {
        key: def.key,
        label: def.label,
        input: inputDuration,
        output: outputDuration,
      }
    }

    return {
      key: def.key,
      label: def.label,
      input: getMetricValue(input, def.key),
      output: getMetricValue(output, def.key),
    }
  })
}

function KeyMetricsComparePanel({ analysis, resultMetadata, inputQuality }: KeyMetricsComparePanelProps) {
  const rows = buildRows(analysis, resultMetadata, inputQuality)

  return (
    <article className="card compact-card" aria-label="关键指标对比">
      <div className="card-header">
        <h2>关键指标对比</h2>
        <span className="badge badge-neutral">核心指标</span>
      </div>

      <div className="metrics-table-wrap">
        <table className="metrics-table">
          <thead>
            <tr>
              <th>指标</th>
              <th>转换前</th>
              <th>转换后</th>
              <th>变化</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <td>{row.label}</td>
                <td>{formatValue(row.input)}</td>
                <td>{formatValue(row.output)}</td>
                <td>{formatDelta(row.input, row.output)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  )
}

export default KeyMetricsComparePanel
