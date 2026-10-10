import type { JobResponse } from '../protocol/contract'
import { METHOD_WORD } from '../lib/derive'
import { num, pct } from '../lib/format'
import { comparableCost, METHODS, type CompareState, type Method, type MethodRun } from '../lib/useMethodCompare'

interface Props {
  state: CompareState
  currentRunId: string | null
  onShow: (r: JobResponse) => void
  onClear: () => void
}

const ROWS: { key: string; label: string; get: (r: MethodRun) => string }[] = [
  { key: 'served', label: '配送门店', get: (r) => `${r.response.result?.metrics.served_stores ?? '—'} / ${r.response.result?.metrics.total_stores ?? '—'}` },
  { key: 'veh', label: '启用车辆', get: (r) => String(r.response.result?.metrics.used_vehicles ?? '—') },
  { key: 'cost', label: '总费用（元）', get: (r) => num(r.response.result?.metrics.total_cost, 1) },
  { key: 'dist', label: '总里程（km）', get: (r) => num(r.response.result?.metrics.total_distance_km, 1) },
  { key: 'vol', label: '体积利用率', get: (r) => pct(r.response.result?.metrics.volume_utilization) },
  { key: 'valid', label: '独立校验', get: (r) => (r.response.result?.validation.valid ? '通过' : '未通过') },
  { key: 'repair', label: '协同修复', get: (r) => repairWord(r) },
  { key: 'ms', label: '耗时（ms）', get: (r) => num(r.response.elapsed_ms, 0) },
]

const SHORT: Record<Method, string> = { greedy: '贪心', sequential: '顺序', coupled: '协同' }

function repairWord(r: MethodRun): string {
  const t = r.response.result?.repair_trace
  if (r.method !== 'coupled') return '—'
  if (!t) return '无记录'
  return { not_needed: '未触发', repaired: `采用 ${t.accepted_count} 次`, partially_repaired: `部分，采用 ${t.accepted_count} 次`, unresolved: '未解决', budget_exhausted: '预算退出' }[t.status]
}

/** 同一请求三种方法的并排结果；费用改善率只在可比时显示。 */
export function MethodCompare({ state, currentRunId, onShow, onClear }: Props) {
  if (state.phase === 'idle') return null
  const runs: MethodRun[] = state.phase === 'done' ? state.runs : state.done
  const byMethod = new Map(runs.map((r) => [r.method, r]))

  const coupled = byMethod.get('coupled')
  const deltas: { vs: Method; rate: number | null; reason: string }[] = coupled
    ? (['greedy', 'sequential'] as Method[]).map((vs) => {
        const base = byMethod.get(vs)
        if (!base) return { vs, rate: null, reason: '缺少该方法结果' }
        if (!comparableCost(base, coupled)) {
          const same = base.servedSet.length === coupled.servedSet.length && base.servedSet.every((s, i) => s === coupled.servedSet[i])
          return { vs, rate: null, reason: same ? '未通过校验或基线费用为 0' : `服务门店集合不同（${base.servedSet.length} 店 vs ${coupled.servedSet.length} 店）` }
        }
        const b = base.response.result!.metrics.total_cost
        const c = coupled.response.result!.metrics.total_cost
        return { vs, rate: (c - b) / b, reason: '' }
      })
    : []

  return (
    <section className="section">
      <h2>
        三种方法对比
        {state.phase === 'running' && <span className="count">正在求解 {METHOD_WORD[state.current]}…</span>}
        {state.phase === 'error' && <span className="count" style={{ color: 'var(--critical)' }}>{state.message}</span>}
      </h2>
      <table className="kv compare-table">
        <thead>
          <tr>
            <th></th>
            {METHODS.map((m) => (
              <td key={m} title={METHOD_WORD[m]}>
                <div className="cmp-head">{SHORT[m]}</div>
              </td>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.key}>
              <th>{row.label}</th>
              {METHODS.map((m) => {
                const r = byMethod.get(m)
                return <td key={m}>{r ? row.get(r) : state.phase === 'running' && state.current === m ? '…' : '—'}</td>
              })}
            </tr>
          ))}
          <tr>
            <th>查看</th>
            {METHODS.map((m) => {
              const r = byMethod.get(m)
              const active = r && r.response.run_id === currentRunId
              return (
                <td key={m}>
                  {r && (
                    <button className={`btn quiet ${active ? 'on' : ''}`} onClick={() => onShow(r.response)}>
                      {active ? '正在看' : '查看'}
                    </button>
                  )}
                </td>
              )
            })}
          </tr>
        </tbody>
      </table>
      {state.phase === 'done' && (
        <ul className="cmp-notes">
          {deltas.map((d) => (
            <li key={d.vs}>
              协同相对{SHORT[d.vs]}（{METHOD_WORD[d.vs]}）：
              {d.rate === null ? <span className="empty">费用不可比，{d.reason}</span> : <strong>{d.rate <= 0 ? '' : '+'}{(d.rate * 100).toFixed(1)}%</strong>}
            </li>
          ))}
          <li className="empty">费用只在服务门店集合相同且均通过独立校验时比较；所有方法共用同一数据、校验器与时间预算。</li>
        </ul>
      )}
      <div className="assist-buttons" style={{ marginTop: 8 }}>
        <button className="btn quiet" onClick={onClear}>
          关闭对比
        </button>
      </div>
    </section>
  )
}
