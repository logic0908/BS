import type { AudioStyleFeatures, StyleEvidenceCompareResponse } from '../types'

interface StyleEvidencePanelProps {
  analysis: StyleEvidenceCompareResponse
  promptText: string
  fallbackNotice?: string | null
}

const RAW_FEATURE_ROWS = [
  { key: 'pitch_height_score', label: '音高中心分数' },
  { key: 'brightness_score', label: '亮度分数' },
  { key: 'energy_score', label: '能量分数' },
  { key: 'softness_score', label: '柔和度分数' },
  { key: 'thickness_score', label: '厚度分数' },
  { key: 'spectral_centroid_mean', label: '频谱质心均值' },
  { key: 'spectral_bandwidth_mean', label: '频谱带宽均值' },
  { key: 'spectral_rolloff_mean', label: '频谱滚降均值' },
  { key: 'zero_crossing_rate_mean', label: '过零率均值' },
  { key: 'f0_median', label: '基频 F0 中位数' },
  { key: 'voiced_ratio', label: '有声帧比例' },
  { key: 'low_energy_ratio', label: '低能量片段比例' },
  { key: 'mid_energy_ratio', label: '中能量片段比例' },
  { key: 'high_energy_ratio', label: '高能量片段比例' },
]

function StyleEvidencePanel({ analysis, promptText, fallbackNotice }: StyleEvidencePanelProps) {
  return (
    <div className="style-evidence-panel">
      <div className="section-header">
        <div>
          <div className="section-kicker">风格证据</div>
          <h2>转换前后风格证据对比</h2>
          <p>该面板基于音高、能量、频谱等可测指标，辅助展示转换是否朝提示词方向移动。</p>
        </div>
      </div>

      {fallbackNotice ? <div className="notice-card notice-warning">{fallbackNotice}</div> : null}

      <div className="style-evidence-grid">
        <article className="detail-card">
          <div className="detail-card-header">
            <h3>提示词解析</h3>
          </div>
          <div className="style-evidence-copy">
            <div>
              <div className="field-label">原提示词</div>
              <div className="style-evidence-text">{promptText || analysis.prompt_text}</div>
            </div>
            <div>
              <div className="field-label">匹配关键词</div>
              <div className="chip-row">
                {(analysis.prompt_targets.matched_keywords.length > 0
                  ? analysis.prompt_targets.matched_keywords
                  : ['未命中明确关键词']
                ).map((keyword) => (
                  <span key={keyword} className="summary-pill">
                    <span>关键词</span>
                    <strong>{keyword}</strong>
                  </span>
                ))}
              </div>
            </div>
            <div>
              <div className="field-label">目标方向</div>
              <ul className="plain-list">
                {(analysis.prompt_targets.human_readable_targets.length > 0
                  ? analysis.prompt_targets.human_readable_targets
                  : ['当前提示词未形成明确方向目标']
                ).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        </article>

        <article className="detail-card">
          <div className="detail-card-header">
            <h3>五维方向对比</h3>
          </div>
          <div className="bar-compare-list">
            {analysis.radar.dimensions.map((dimension, index) => (
              <div key={dimension} className="bar-compare-item">
                <div className="bar-compare-header">
                  <strong>{dimensionLabel(dimension)}</strong>
                  <span>{directionHint(analysis.prompt_targets.target_dimensions[dimension])}</span>
                </div>
                <div className="bar-compare-track-group">
                  <BarMetric label="输入" value={analysis.radar.input[index]} tone="input" />
                  <BarMetric label="输出" value={analysis.radar.output[index]} tone="output" />
                  <BarMetric label="目标" value={analysis.radar.target[index]} tone="target" />
                </div>
              </div>
            ))}
          </div>
        </article>
      </div>

      <article className="detail-card">
        <div className="detail-card-header">
          <h3>风格方向判断</h3>
        </div>
        <div className="evidence-table-wrap">
          <table className="evidence-table">
            <thead>
              <tr>
                <th>指标</th>
                <th>输入</th>
                <th>输出</th>
                <th>变化</th>
                <th>目标方向</th>
                <th>是否符合</th>
                <th>解释</th>
              </tr>
            </thead>
            <tbody>
              {analysis.comparisons.map((item) => (
                <tr key={item.key}>
                  <td>{item.label}</td>
                  <td>{formatMetricValue(item.input_value)}</td>
                  <td>{formatMetricValue(item.output_value)}</td>
                  <td>{formatSignedValue(item.delta)}</td>
                  <td>{directionHint(item.expected_direction)}</td>
                  <td>{item.matches_prompt ? '是' : '否'}</td>
                  <td>{item.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <article className="detail-card">
        <div className="detail-card-header">
          <h3>输入 / 输出指标表</h3>
        </div>
        <div className="evidence-table-wrap">
          <table className="evidence-table">
            <thead>
              <tr>
                <th>指标</th>
                <th>输入</th>
                <th>输出</th>
              </tr>
            </thead>
            <tbody>
              {RAW_FEATURE_ROWS.map((row) => (
                <tr key={row.key}>
                  <td>{row.label}</td>
                  <td>{formatMetricValue(readFeatureValue(analysis.input, row.key))}</td>
                  <td>{formatMetricValue(readFeatureValue(analysis.output, row.key))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <article className="detail-card">
        <div className="detail-card-header">
          <h3>自动结论</h3>
        </div>
        <div className="summary-card">
          <div className={`summary-level summary-${analysis.summary.level}`}>{summaryLabel(analysis.summary.level)}</div>
          <p>{analysis.summary.text}</p>
          <div className="config-summary">
            <div className="summary-pill">
              <span>匹配项</span>
              <strong>
                {analysis.summary.matched_count}/{analysis.summary.total_count}
              </strong>
            </div>
            <div className="summary-pill">
              <span>得分</span>
              <strong>{formatMetricValue(analysis.summary.score)}</strong>
            </div>
          </div>
        </div>
      </article>

      {analysis.warnings.length > 0 ? (
        <div className="notice-card notice-info">
          <ul className="plain-list">
            {analysis.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="notice-card notice-info">该分析为启发式客观指标，仅用于展示变化趋势，不能替代人工听评。</div>
    </div>
  )
}

function readFeatureValue(features: AudioStyleFeatures, key: string): number | null {
  const value = features[key as keyof AudioStyleFeatures]
  return typeof value === 'number' ? value : null
}

function BarMetric({ label, value, tone }: { label: string; value: number; tone: 'input' | 'output' | 'target' }) {
  return (
    <div className="bar-metric">
      <div className="bar-metric-label">
        <span>{label}</span>
        <strong>{value.toFixed(2)}</strong>
      </div>
      <div className="bar-track">
        <div className={`bar-fill bar-${tone}`} style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }} />
      </div>
    </div>
  )
}

function formatMetricValue(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '暂无'
  }
  return value.toFixed(3)
}

function formatSignedValue(value: number | null): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '暂无'
  }
  return `${value > 0 ? '+' : ''}${value.toFixed(3)}`
}

function dimensionLabel(dimension: string): string {
  const labels: Record<string, string> = {
    brightness: '亮度',
    energy: '能量',
    softness: '柔和度',
    thickness: '厚度',
    pitch_height: '音高中心',
  }
  return labels[dimension] ?? dimension
}

function directionHint(direction: string | null | undefined): string {
  if (direction === 'up') return '提升'
  if (direction === 'slightly_up') return '略提升'
  if (direction === 'down') return '降低'
  if (direction === 'slightly_down') return '略降低'
  if (direction === 'medium') return '保持中性'
  return '未指定'
}

function summaryLabel(level: string): string {
  if (level === 'strong') return '证据较强'
  if (level === 'partial') return '证据部分成立'
  if (level === 'weak') return '证据较弱'
  return '证据不足'
}

export default StyleEvidencePanel
