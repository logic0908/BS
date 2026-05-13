import type { InputQualitySummary, ResultMetadata, StyleEvidenceCompareResponse } from '../types'
import { formatSeconds, labelOf } from '../utils/displayLabels'

type MetricRow = {
  key: string
  input: number | null
  output: number | null
}

interface KeyMetricsComparePanelProps {
  analysis: StyleEvidenceCompareResponse | null
  resultMetadata: ResultMetadata | null
  inputQuality: InputQualitySummary | null
}

const METRIC_KEYS = [
  'brightness_score',
  'energy_score',
  'softness_score',
  'thickness_score',
  'f0_median',
  'spectral_centroid_mean',
  'voiced_ratio',
  'duration_seconds',
] as const

function getMetricValue(source: Record<string, unknown> | null | undefined, key: string): number | null {
  if (!source) return null
  const value = source[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function formatValue(key: string, value: number | null): string {
  if (value === null) return '未返回'
  if (key === 'duration_seconds') return formatSeconds(value)
  return value.toFixed(3)
}

function formatDelta(key: string, input: number | null, output: number | null): string {
  if (input === null || output === null) return '未返回'
  const delta = output - input
  if (key === 'duration_seconds') return formatSeconds(delta)
  return `${delta >= 0 ? '+' : ''}${delta.toFixed(3)}`
}

function buildRows(
  analysis: StyleEvidenceCompareResponse | null,
  resultMetadata: ResultMetadata | null,
  inputQuality: InputQualitySummary | null,
): MetricRow[] {
  const input = (analysis?.input ?? null) as Record<string, unknown> | null
  const output = (analysis?.output ?? null) as Record<string, unknown> | null

  return METRIC_KEYS.map((key) => {
    if (key === 'duration_seconds') {
      const inputDuration = inputQuality?.duration ?? getMetricValue(input, 'duration_seconds')
      const outputDuration =
        (typeof resultMetadata?.duration_seconds === 'number' ? resultMetadata.duration_seconds : null) ??
        getMetricValue(output, 'duration_seconds')
      return {
        key,
        input: inputDuration,
        output: outputDuration,
      }
    }

    return {
      key,
      input: getMetricValue(input, key),
      output: getMetricValue(output, key),
    }
  })
}

function KeyMetricsComparePanel({ analysis, resultMetadata, inputQuality }: KeyMetricsComparePanelProps) {
  const rows = buildRows(analysis, resultMetadata, inputQuality)

  return (
    <article className="card compact-card" aria-label="关键指标对比">
      <div className="card-header compact-header">
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
                <td>{labelOf(row.key)}</td>
                <td>{formatValue(row.key, row.input)}</td>
                <td>{formatValue(row.key, row.output)}</td>
                <td>{formatDelta(row.key, row.input, row.output)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  )
}

export default KeyMetricsComparePanel
