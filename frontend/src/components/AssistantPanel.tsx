import { useState } from 'react'
import type { JobResponse, SolveRequest } from '../protocol/contract'
import type { Focus } from '../protocol/agent'
import type { AssistantState, RunPair } from '../lib/useAssistant'
import { describePatch } from '../lib/patchDescribe'
import { Markdown } from '../lib/markdown'
import { num, pct } from '../lib/format'

interface Props {
  request: SolveRequest
  response: JobResponse | null
  selectedVehicleId: string | null
  state: AssistantState
  onExplain: (focus: Focus, vehicleId: string | null, question?: string) => void
  onInterpret: (instruction: string) => void
  onConfirmPatch: (patched: SolveRequest, instruction: string) => void
  onDiscardPatch: () => void
  onClearError: () => void
  /** 正在为补丁重算时为 true：面板显示等待，不允许再发指令 */
  resolving: boolean
  solverOnline: boolean
}

const EXAMPLES = ['S01 最早 9 点半收货', '时间预算 20 秒', 'V02 今天不出车', '再加一辆和 V01 一样的车']

export function AssistantPanel(p: Props) {
  const [instruction, setInstruction] = useState('')
  const [question, setQuestion] = useState('')
  const { s } = { s: p.state }
  const hasResult = !!p.response?.result && (p.response.status === 'succeeded' || p.response.status === 'partial')
  const online = s.status.kind === 'online'
  const llmConfigured = s.status.kind === 'online' && s.status.health.llm.configured
  const modeLabel = s.status.kind === 'probing' ? '探测中' : s.status.kind === 'offline' ? '离线' : s.status.kind === 'online' && s.status.health.llm.configured ? `模型 ${s.status.health.llm.model}` : '模板模式'

  return (
    <section className="section assistant">
      <h2>
        调度助手
        <span className={`tag ${s.status.kind === 'offline' ? 'critical' : llmConfigured ? 'good' : ''}`} style={{ marginLeft: 8 }}>
          {modeLabel}
        </span>
      </h2>

      {s.status.kind === 'offline' && (
        <p className="empty">调度助手服务未连接（8001 端口）。其他功能不受影响。</p>
      )}

      {s.error && (
        <div className="error-box" style={{ marginBottom: 10 }}>
          <div>{s.error}</div>
          <button className="btn quiet" style={{ marginTop: 6 }} onClick={p.onClearError}>
            关闭
          </button>
        </div>
      )}

      {/* ---------- 解释 ---------- */}
      <div className="assist-block">
        <div className="assist-row">
          <span className="assist-label">解释当前方案</span>
          <div className="assist-buttons">
            <button className="btn quiet" disabled={!online || !hasResult || s.explaining} onClick={() => p.onExplain('overview', null, question)}>
              总览
            </button>
            <button className="btn quiet" disabled={!online || !hasResult || s.explaining} onClick={() => p.onExplain('unassigned', null, question)}>
              未配送
            </button>
            <button className="btn quiet" disabled={!online || !hasResult || s.explaining || !p.selectedVehicleId} onClick={() => p.onExplain('vehicle', p.selectedVehicleId, question)}>
              本车
            </button>
            <button className="btn quiet" disabled={!online || !hasResult || s.explaining || !p.selectedVehicleId} onClick={() => p.onExplain('unload', p.selectedVehicleId, question)}>
              装卸作业单
            </button>
          </div>
        </div>
        <input
          className="assist-input"
          placeholder="可选：想问的问题，例如「为什么 S02 没送」"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={!online || !hasResult}
        />
        {!hasResult && online && <p className="empty">先运行求解，再让助手解释方案。</p>}
        {s.explaining && <p className="empty">正在生成解释…</p>}
        {s.explanation && !s.explaining && (
          <div className="assist-output">
            <div className="assist-meta">
              <span className={`tag ${s.explanation.result.mode === 'llm' ? 'good' : ''}`}>{s.explanation.result.mode === 'llm' ? `模型 ${s.explanation.result.model}` : '模板'}</span>
              <span className="tag" title="解释中的每个数字都在服务端事实表中核对过">
                已核对 {s.explanation.result.grounding.checked_numbers} 个数字
              </span>
              <span className="empty">{focusWord(s.explanation.focus)}{s.explanation.vehicleId ? ` ${s.explanation.vehicleId}` : ''}</span>
            </div>
            <Markdown text={s.explanation.result.text} />
            {s.explanation.result.warnings.length > 0 && (
              <ul className="assist-warnings">
                {s.explanation.result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* ---------- 指令 ---------- */}
      <div className="assist-block">
        <div className="assist-row">
          <span className="assist-label">用一句话调整约束</span>
        </div>
        <form
          className="assist-form"
          onSubmit={(e) => {
            e.preventDefault()
            if (instruction.trim()) p.onInterpret(instruction.trim())
          }}
        >
          <input
            className="assist-input"
            placeholder="例如：S07 下午两点以后才能收货，V02 不出车"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            disabled={!online || s.interpreting || p.resolving}
          />
          <button className="btn secondary" type="submit" disabled={!online || s.interpreting || p.resolving || !instruction.trim()}>
            解析
          </button>
        </form>
        <div className="assist-examples">
          {EXAMPLES.map((ex) => (
            <button key={ex} className="chip-btn" type="button" disabled={!online || s.interpreting || p.resolving} onClick={() => setInstruction(ex)}>
              {ex}
            </button>
          ))}
        </div>
        {s.interpreting && <p className="empty">正在解析指令…</p>}
        {p.resolving && <p className="empty">已按确认的补丁提交求解，等待结果后自动对比。</p>}
        {s.interpretation && !s.interpreting && !p.resolving && (
          <InterpretationView
            request={p.request}
            instruction={s.interpretation.instruction}
            result={s.interpretation.result}
            solverOnline={p.solverOnline}
            onConfirm={() => s.interpretation!.result.patched_request && p.onConfirmPatch(s.interpretation!.result.patched_request, s.interpretation!.instruction)}
            onDiscard={p.onDiscardPatch}
          />
        )}
      </div>

      {/* ---------- 对比 ---------- */}
      {(s.comparing || s.comparison) && (
        <div className="assist-block">
          <div className="assist-row">
            <span className="assist-label">调整前后对比</span>
          </div>
          {s.comparing && <p className="empty">正在对比两次方案…</p>}
          {s.comparison && !s.comparing && <ComparisonView baseline={s.comparison.baseline} candidate={s.comparison.candidate} result={s.comparison.result} />}
        </div>
      )}
    </section>
  )
}

function focusWord(f: Focus): string {
  return { overview: '总览', unassigned: '未配送', unload: '装卸作业单', vehicle: '本车' }[f]
}

function InterpretationView({
  request,
  instruction,
  result,
  solverOnline,
  onConfirm,
  onDiscard,
}: {
  request: SolveRequest
  instruction: string
  result: import('../protocol/agent').InterpretResponse
  solverOnline: boolean
  onConfirm: () => void
  onDiscard: () => void
}) {
  const lines = describePatch(request, result.patch)
  const canApply = result.understood && result.patch.length > 0 && !!result.patched_request
  return (
    <div className="assist-output">
      <div className="assist-meta">
        <span className={`tag ${result.mode === 'llm' ? 'good' : ''}`}>{result.mode === 'llm' ? `模型 ${result.model}` : '规则'}</span>
        <span className="empty">「{instruction}」</span>
      </div>
      <p className="assist-summary">{result.summary}</p>
      {lines.length > 0 && (
        <table className="kv patch-table">
          <tbody>
            {lines.map((l, i) => (
              <tr key={i}>
                <th>
                  {l.subject}
                  {l.field ? ` · ${l.field}` : ''}
                </th>
                <td>
                  <span className="before">{l.before}</span>
                  <span className="arrow"> → </span>
                  <span className="after">{l.after}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {result.rejected_ops.length > 0 && (
        <ul className="assist-warnings">
          {result.rejected_ops.map((r, i) => (
            <li key={i}>未采纳：{r.reason}</li>
          ))}
        </ul>
      )}
      {result.warnings.length > 0 && (
        <ul className="assist-warnings">
          {result.warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}
      <div className="assist-buttons" style={{ marginTop: 8 }}>
        <button className="btn" disabled={!canApply || !solverOnline} onClick={onConfirm} title={solverOnline ? '把修改后的请求提交求解器' : '求解服务未连接'}>
          确认并重新求解
        </button>
        <button className="btn quiet" onClick={onDiscard}>
          放弃
        </button>
      </div>
      <p className="empty" style={{ marginTop: 6 }}>
        助手只生成修改建议；未经确认不会提交任何求解。
      </p>
    </div>
  )
}

const DELTA_ROWS: { key: string; label: string; kind: 'int' | 'num' | 'pct'; unit?: string }[] = [
  { key: 'served_stores', label: '配送门店', kind: 'int' },
  { key: 'used_vehicles', label: '启用车辆', kind: 'int', unit: '辆' },
  { key: 'total_cost', label: '总费用', kind: 'num', unit: '元' },
  { key: 'total_distance_km', label: '总里程', kind: 'num', unit: 'km' },
  { key: 'volume_utilization', label: '体积利用率', kind: 'pct' },
  { key: 'on_time_rate', label: '准时率', kind: 'pct' },
]

function ComparisonView({ baseline, candidate, result }: { baseline: RunPair; candidate: RunPair; result: import('../protocol/agent').CompareResponse }) {
  const f = (v: number | null, kind: 'int' | 'num' | 'pct') => (v === null ? '—' : kind === 'pct' ? pct(v) : kind === 'int' ? String(v) : num(v, 1))
  return (
    <div className="assist-output">
      <div className="assist-meta">
        <span className={`tag ${result.mode === 'llm' ? 'good' : ''}`}>{result.mode === 'llm' ? `模型 ${result.model}` : '模板'}</span>
        <span className="tag">已核对 {result.grounding.checked_numbers} 个数字</span>
        <span className={`tag ${result.comparable_cost ? 'good' : 'mock'}`} title={result.comparable_cost ? '服务门店集合相同且均通过校验' : '服务门店集合不同或未通过校验，费用不可直接比较'}>
          {result.comparable_cost ? '费用可比' : '费用不可比'}
        </span>
      </div>
      <table className="kv">
        <thead>
          <tr>
            <th></th>
            <td style={{ fontWeight: 400, color: 'var(--ink-2)' }} title={baseline.response.run_id}>
              调整前
            </td>
            <td style={{ fontWeight: 400, color: 'var(--ink-2)' }} title={candidate.response.run_id}>
              调整后
            </td>
          </tr>
        </thead>
        <tbody>
          {DELTA_ROWS.map((r) => {
            const d = result.deltas[r.key]
            if (!d) return null
            const up = d.delta !== null && d.delta > 1e-9
            const down = d.delta !== null && d.delta < -1e-9
            return (
              <tr key={r.key}>
                <th>{r.label}</th>
                <td>
                  {f(d.baseline, r.kind)}
                  {r.unit && <span className="unit">{r.unit}</span>}
                </td>
                <td className={up ? 'delta-up' : down ? 'delta-down' : ''}>
                  {f(d.candidate, r.kind)}
                  {r.unit && <span className="unit">{r.unit}</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {result.comparable_cost && result.cost_change_rate !== null && (
        <p className="assist-summary">费用变化 {(result.cost_change_rate * 100).toFixed(1)}%</p>
      )}
      <Markdown text={result.text} />
      {result.warnings.length > 0 && (
        <ul className="assist-warnings">
          {result.warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
