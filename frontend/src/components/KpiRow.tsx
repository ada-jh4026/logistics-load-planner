import type { JobResponse } from '../protocol/contract'
import { num, pct } from '../lib/format'

interface Props {
  response: JobResponse | null
}

/**
 * 方案的五个头条数字，位于中央视图上方。只读响应指标，不计算任何新值。
 * 状态色只用于「独立校验」这一格；其余数字用文字色，颜色不承担含义。
 */
export function KpiRow({ response }: Props) {
  const r = response?.result ?? null
  if (!r) return null
  const m = r.metrics
  const partial = m.served_stores < m.total_stores
  return (
    <div className="kpi-row" role="group" aria-label="方案头条指标">
      <div className={`kpi ${partial ? 'kpi-attn' : ''}`}>
        <span className="kpi-label">配送门店</span>
        <span className="kpi-value">
          {m.served_stores}
          <span className="kpi-of">/ {m.total_stores}</span>
        </span>
        <span className="kpi-sub">{pct(m.completion_rate)}，{m.served_boxes} / {m.total_boxes} 箱</span>
      </div>
      <div className="kpi">
        <span className="kpi-label">启用车辆</span>
        <span className="kpi-value">
          {m.used_vehicles}
          <span className="kpi-unit">辆</span>
        </span>
        <span className="kpi-sub">体积利用率 {pct(m.volume_utilization)}，载重 {pct(m.weight_utilization)}</span>
      </div>
      <div className="kpi">
        <span className="kpi-label">总费用</span>
        <span className="kpi-value">
          {num(m.total_cost, 1)}
          <span className="kpi-unit">元</span>
        </span>
        <span className="kpi-sub">总里程 {num(m.total_distance_km, 1)} km</span>
      </div>
      <div className="kpi">
        <span className="kpi-label">准时率</span>
        <span className="kpi-value">{pct(m.on_time_rate)}</span>
        <span className="kpi-sub">卸货阻挡 {m.unload_block_count} 处</span>
      </div>
      <div className={`kpi kpi-status ${r.validation.valid ? 'ok' : 'bad'}`}>
        <span className="kpi-label">独立校验</span>
        <span className="kpi-value">{r.validation.valid ? '通过' : '未通过'}</span>
        <span className="kpi-sub">{r.validation.valid ? '边界、碰撞、承托、时间窗、卸货均重算' : `${r.validation.violations.length} 项违规`}</span>
      </div>
    </div>
  )
}
