// 把 RFC 6902 补丁翻译成调度员能读的字段级变更，供确认前展示。
import type { SolveRequest } from '../protocol/contract'
import type { PatchOp } from '../protocol/agent'
import { hhmm } from './format'

export interface PatchLine {
  kind: 'replace' | 'remove' | 'add'
  subject: string
  field: string
  before: string
  after: string
}

const FIELD_LABEL: Record<string, string> = {
  departure_min: '出发时间',
  window_start_min: '最早收货',
  window_end_min: '最晚收货',
  service_min: '服务时长',
  fragile: '易碎',
  allow_rotate_xy: '允许旋转',
  method: '求解方法',
  seed: '随机种子',
  time_limit_ms: '时间预算',
  max_iterations: '最大迭代',
  speed_kmph: '车速',
}

const METHOD_WORD: Record<string, string> = { greedy: '简单贪心', sequential: '先路线后装载', coupled: '配载与路线协同' }

function fmt(field: string, v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (field.endsWith('_min') && field !== 'service_min' && typeof v === 'number') return hhmm(v)
  if (field === 'service_min') return `${v} 分钟`
  if (field === 'time_limit_ms' && typeof v === 'number') return `${v / 1000} 秒`
  if (field === 'speed_kmph') return `${v} km/h`
  if (field === 'method' && typeof v === 'string') return METHOD_WORD[v] ?? v
  if (typeof v === 'boolean') return v ? '是' : '否'
  return String(v)
}

export function describePatch(request: SolveRequest, patch: PatchOp[]): PatchLine[] {
  const lines: PatchLine[] = []
  // remove 的下标按补丁顺序对当前状态解析，这里用一个可变副本跟踪
  const vehicles = request.vehicles.map((v) => v.id)
  for (const op of patch) {
    const seg = op.path.split('/').filter(Boolean)
    if (op.op === 'replace' && seg.length === 2 && (seg[0] === 'depot' || seg[0] === 'options')) {
      const field = seg[1]
      const before = (request as unknown as Record<string, Record<string, unknown>>)[seg[0]][field]
      lines.push({ kind: 'replace', subject: seg[0] === 'depot' ? '仓库' : '求解选项', field: FIELD_LABEL[field] ?? field, before: fmt(field, before), after: fmt(field, op.value) })
    } else if (op.op === 'replace' && seg.length === 3 && (seg[0] === 'stores' || seg[0] === 'boxes')) {
      const idx = Number(seg[1])
      const field = seg[2]
      const item = (seg[0] === 'stores' ? request.stores : request.boxes)[idx] as unknown as Record<string, unknown> | undefined
      const subject = (seg[0] === 'stores' ? '门店 ' : '箱件 ') + (item?.id ?? `#${idx}`)
      lines.push({ kind: 'replace', subject, field: FIELD_LABEL[field] ?? field, before: fmt(field, item?.[field]), after: fmt(field, op.value) })
    } else if (op.op === 'remove' && seg[0] === 'vehicles' && seg.length === 2) {
      const idx = Number(seg[1])
      const id = vehicles[idx] ?? `#${idx}`
      vehicles.splice(idx, 1)
      lines.push({ kind: 'remove', subject: `车辆 ${id}`, field: '', before: '可用', after: '移除' })
    } else if (op.op === 'add' && seg[0] === 'vehicles') {
      const v = op.value as { id?: string } | undefined
      if (v?.id) vehicles.push(v.id)
      lines.push({ kind: 'add', subject: `车辆 ${v?.id ?? '?'}`, field: '', before: '—', after: '新增' })
    } else {
      lines.push({ kind: op.op, subject: op.path, field: '', before: '', after: JSON.stringify(op.value) })
    }
  }
  return lines
}
