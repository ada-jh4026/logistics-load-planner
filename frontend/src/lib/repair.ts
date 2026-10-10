// repair_trace 的派生视图：状态文案、计数、回放快照、可比性。全部从响应字段推导，不补算任何坐标。
import type { Metrics, RepairEvent, RepairStatus, RepairTrace, Result, Route } from '../protocol/contract'

export const REPAIR_STATUS_WORD: Record<RepairStatus, string> = {
  not_needed: '无需修复',
  repaired: '修复成功',
  partially_repaired: '部分修复',
  unresolved: '未解决',
  budget_exhausted: '预算退出',
}

export const REPAIR_STATUS_CLASS: Record<RepairStatus, string> = {
  not_needed: 'good',
  repaired: 'good',
  partially_repaired: 'partial',
  unresolved: 'critical',
  budget_exhausted: 'critical',
}

export const ACTION_WORD: Record<RepairEvent['action'], string> = {
  pack_failed: '装载失败',
  relocate: '搬移门店',
}

export const OUTCOME_WORD: Record<RepairEvent['outcome'], string> = {
  detected: '发现冲突',
  rejected: '尝试被拒',
  accepted: '已采用',
}

export const REASON_WORD: Record<string, string> = {
  SEARCH_EXHAUSTED: '启发式未找到布局',
  BOX_TOO_LARGE: '单件超过车厢',
  CAPACITY_LIMIT: '载重或容量不足',
  TIME_WINDOW: '时间窗不满足',
  TIME_LIMIT: '时间预算耗尽',
  NO_IMPROVEMENT: '目标分数未改善',
  UNLOAD_BLOCKED: '卸货路径被挡',
  SUPPORT_DEPENDENCY: '底箱被压不能先抽',
  OVERLAP: '箱件重叠',
  OUT_OF_BOUNDS: '超出车厢',
  UNSUPPORTED: '浮空或跨箱承托',
  FRAGILE_LOAD: '压在易碎箱上',
  OVERWEIGHT: '超载',
}

export interface RepairSummary {
  trace: RepairTrace
  detected: RepairEvent[]
  accepted: RepairEvent[]
  rejected: RepairEvent[]
  initialServedSet: string[]
  finalServedSet: string[]
  sameServedSet: boolean
  costDelta: number | null
}

export function servedSet(routes: Route[]): string[] {
  return routes.flatMap((r) => r.store_ids).sort()
}

export function summarize(result: Result): RepairSummary | null {
  const trace = result.repair_trace
  if (!trace) return null
  const initialServedSet = servedSet(trace.initial_routes)
  const finalServedSet = servedSet(result.routes)
  const same = initialServedSet.length === finalServedSet.length && initialServedSet.every((s, i) => s === finalServedSet[i])
  return {
    trace,
    detected: trace.events.filter((e) => e.outcome === 'detected'),
    accepted: trace.events.filter((e) => e.outcome === 'accepted'),
    rejected: trace.events.filter((e) => e.outcome === 'rejected'),
    initialServedSet,
    finalServedSet,
    sameServedSet: same,
    costDelta: same ? trace.final_metrics.total_cost - trace.initial_metrics.total_cost : null,
  }
}

/** 第 k 个 accepted 事件的「之前」与「之后」快照。routes_before / routes_after 由后端携带，前端只读取。 */
export function snapshotRoutes(event: RepairEvent, side: 'before' | 'after'): Route[] | null {
  return side === 'before' ? event.routes_before : event.routes_after
}

export function snapshotMetrics(event: RepairEvent, side: 'before' | 'after'): Metrics | null {
  return side === 'before' ? event.metrics_before : event.metrics_after
}

/** 事件涉及的车辆（用于联动高亮） */
export function eventVehicles(e: RepairEvent): string[] {
  return [e.source_vehicle_id, e.target_vehicle_id].filter((v): v is string => !!v)
}

export function describeEvent(e: RepairEvent): string {
  if (e.action === 'pack_failed') {
    return `车辆 ${e.source_vehicle_id ?? '?'} 装载失败：${e.store_ids.join('、')}`
  }
  const from = e.source_vehicle_id ? `从 ${e.source_vehicle_id} ` : '从未分配 '
  const to = e.target_vehicle_id ? `到 ${e.target_vehicle_id}` : ''
  return `${e.store_ids.join('、')} ${from}${to}`
}
