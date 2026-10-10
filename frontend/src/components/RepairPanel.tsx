import { useState } from 'react'
import type { JobResponse, RepairEvent } from '../protocol/contract'
import { ACTION_WORD, describeEvent, OUTCOME_WORD, REASON_WORD, REPAIR_STATUS_CLASS, REPAIR_STATUS_WORD, summarize } from '../lib/repair'
import { num, pct } from '../lib/format'

export interface RepairFocus {
  eventId: number
  side: 'before' | 'after'
}

interface Props {
  response: JobResponse | null
  focus: RepairFocus | null
  onFocus: (f: RepairFocus | null) => void
}

/**
 * 协同修复区域：是否触发、初始/最终服务数、尝试/采用次数、冲突与接受动作时间线。
 * 旧记录（repair_trace 为 null）显示「未提供记录」；拒绝事件折叠；选中接受事件可切换修复前/后快照（只读后端快照）。
 */
export function RepairPanel({ response, focus, onFocus }: Props) {
  const [showRejected, setShowRejected] = useState(false)
  const result = response?.result ?? null
  if (!result) return null

  const s = summarize(result)
  if (!s) {
    return (
      <section className="section">
        <h2>协同修复</h2>
        <p className="empty">
          {response?.method === 'coupled' ? '此记录未提供修复过程（旧版响应）。' : `方法「${response?.method}」不做协同修复，无记录。`}
        </p>
      </section>
    )
  }
  const t = s.trace
  const total = t.final_metrics.total_stores
  const visible = t.events.filter((e) => e.outcome !== 'rejected' || showRejected)

  return (
    <section className="section repair">
      <h2>
        协同修复
        <span className={`tag ${REPAIR_STATUS_CLASS[t.status]}`} style={{ marginLeft: 8 }}>
          {REPAIR_STATUS_WORD[t.status]}
        </span>
      </h2>

      <table className="kv">
        <tbody>
          <tr>
            <th>可执行门店</th>
            <td>
              {t.initial_metrics.served_stores} / {total}
              <span className="arrow"> → </span>
              <strong>{t.final_metrics.served_stores} / {total}</strong>
            </td>
          </tr>
          <tr>
            <th>尝试 / 采用</th>
            <td>
              {t.attempted_count} / {t.accepted_count}
            </td>
          </tr>
          <tr>
            <th>费用</th>
            <td>
              {num(t.initial_metrics.total_cost, 1)}
              <span className="arrow"> → </span>
              {num(t.final_metrics.total_cost, 1)}
              <span className="unit">元</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p className="empty" style={{ marginTop: 6 }}>
        {t.status === 'not_needed'
          ? '初始方案已全部可执行，协同修复未触发。'
          : t.accepted_count === 0
            ? `检查了 ${t.attempted_count} 个候选，没有一个通过完整校验并改善方案；方案保持初始状态。`
            : s.sameServedSet
              ? `修复前后服务门店集合相同，费用变化 ${s.costDelta! >= 0 ? '+' : ''}${num(s.costDelta!, 1)} 元。`
              : '修复改变了服务门店集合（覆盖从 ' + s.initialServedSet.length + ' 店到 ' + s.finalServedSet.length + ' 店），费用不可直接比较。'}
        {t.truncated && ` 日志已截断，省略 ${t.omitted_count} 条拒绝记录；计数不受影响。`}
      </p>

      {t.events.length > 0 && (
        <>
          <div className="assist-row" style={{ marginTop: 8 }}>
            <span className="assist-label">过程</span>
            {s.rejected.length > 0 && (
              <button className="btn quiet" onClick={() => setShowRejected((v) => !v)}>
                {showRejected ? '收起被拒尝试' : `显示 ${s.rejected.length} 条被拒尝试`}
              </button>
            )}
          </div>
          <ol className="timeline">
            {visible.map((e) => (
              <TimelineItem key={e.event_id} e={e} focus={focus} onFocus={onFocus} />
            ))}
          </ol>
        </>
      )}
    </section>
  )
}

function TimelineItem({ e, focus, onFocus }: { e: RepairEvent; focus: RepairFocus | null; onFocus: (f: RepairFocus | null) => void }) {
  const active = focus?.eventId === e.event_id
  const canSnapshot = e.outcome === 'accepted' && e.routes_before && e.routes_after
  return (
    <li className={`tl ${e.outcome} ${active ? 'active' : ''}`}>
      <button
        className="tl-head"
        onClick={() => onFocus(active ? null : { eventId: e.event_id, side: 'after' })}
        title={e.message}
      >
        <span className="tl-mark" aria-hidden="true" />
        <span className="tl-text">
          <span className="tl-title">
            {OUTCOME_WORD[e.outcome]} · {ACTION_WORD[e.action]}
          </span>
          <span className="tl-sub">{describeEvent(e)}</span>
          {e.reason_code && <span className="tl-reason">{REASON_WORD[e.reason_code] ?? e.reason_code}</span>}
        </span>
      </button>
      {active && (
        <div className="tl-detail">
          <p>{e.message}</p>
          {e.box_ids.length > 0 && (
            <p className="empty">
              涉及箱件 {e.box_ids.length} 个：{e.box_ids.slice(0, 8).join('、')}
              {e.box_ids.length > 8 ? '…' : ''}
            </p>
          )}
          {canSnapshot && e.metrics_before && e.metrics_after && (
            <>
              <table className="kv">
                <tbody>
                  <tr>
                    <th>可执行门店</th>
                    <td>
                      {e.metrics_before.served_stores}
                      <span className="arrow"> → </span>
                      {e.metrics_after.served_stores}
                    </td>
                  </tr>
                  <tr>
                    <th>车辆</th>
                    <td>
                      {e.metrics_before.used_vehicles}
                      <span className="arrow"> → </span>
                      {e.metrics_after.used_vehicles}
                    </td>
                  </tr>
                  <tr>
                    <th>费用</th>
                    <td>
                      {num(e.metrics_before.total_cost, 1)}
                      <span className="arrow"> → </span>
                      {num(e.metrics_after.total_cost, 1)}
                      <span className="unit">元</span>
                    </td>
                  </tr>
                  <tr>
                    <th>体积利用率</th>
                    <td>
                      {pct(e.metrics_before.volume_utilization)}
                      <span className="arrow"> → </span>
                      {pct(e.metrics_after.volume_utilization)}
                    </td>
                  </tr>
                </tbody>
              </table>
              <div className="assist-buttons" style={{ marginTop: 6 }}>
                <button className={`btn quiet ${focus?.side === 'before' ? 'on' : ''}`} onClick={() => onFocus({ eventId: e.event_id, side: 'before' })}>
                  查看修复前布局
                </button>
                <button className={`btn quiet ${focus?.side === 'after' ? 'on' : ''}`} onClick={() => onFocus({ eventId: e.event_id, side: 'after' })}>
                  查看修复后布局
                </button>
              </div>
              <p className="empty">3D 显示的是后端随事件保存的已验证快照，不是前端推算。</p>
            </>
          )}
          {!canSnapshot && e.outcome !== 'accepted' && <p className="empty">此事件没有布局快照；只能按文本诊断与实体高亮查看。</p>}
        </div>
      )}
    </li>
  )
}
