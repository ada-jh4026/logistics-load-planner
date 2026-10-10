import { formatIssues, SolveRequestSchema, type SolveRequest } from '../protocol/contract'

export type ImportResult = { ok: true; request: SolveRequest } | { ok: false; issues: string[] }

/** 读取用户选择的 JSON 文件并按协议校验；失败时逐条列出字段问题，不生成半截请求。 */
export async function importRequestFile(file: File): Promise<ImportResult> {
  let text: string
  try {
    text = await file.text()
  } catch {
    return { ok: false, issues: ['无法读取文件。'] }
  }
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch (e) {
    return { ok: false, issues: [`不是合法的 JSON：${(e as Error).message}`] }
  }
  const parsed = SolveRequestSchema.safeParse(raw)
  if (!parsed.success) return { ok: false, issues: formatIssues(parsed.error) }
  const issues = semanticIssues(parsed.data)
  if (issues.length) return { ok: false, issues }
  return { ok: true, request: parsed.data }
}

/** 协议里写明、但 schema 表达不了的引用与范围检查（与后端 422 规则对应，前端只做提前提示）。 */
function semanticIssues(r: SolveRequest): string[] {
  const issues: string[] = []
  const dup = (ids: string[], what: string) => {
    const seen = new Set<string>()
    for (const id of ids) {
      if (seen.has(id)) issues.push(`${what} ID 重复：${id}`)
      seen.add(id)
    }
  }
  dup(r.stores.map((s) => s.id), '门店')
  dup(r.vehicles.map((v) => v.id), '车辆')
  dup(r.boxes.map((b) => b.id), '箱件')
  const storeIds = new Set(r.stores.map((s) => s.id))
  for (const b of r.boxes) {
    if (!storeIds.has(b.store_id)) issues.push(`箱件 ${b.id} 引用了不存在的门店 ${b.store_id}`)
    if (b.length_mm <= 0 || b.width_mm <= 0 || b.height_mm <= 0 || b.weight_kg <= 0) issues.push(`箱件 ${b.id} 尺寸或重量必须为正`)
  }
  const boxed = new Set(r.boxes.map((b) => b.store_id))
  for (const s of r.stores) {
    if (!boxed.has(s.id)) issues.push(`门店 ${s.id} 没有任何箱件`)
    if (s.window_end_min < s.window_start_min) issues.push(`门店 ${s.id} 时间窗颠倒`)
    if (s.service_min < 0) issues.push(`门店 ${s.id} 服务时长为负`)
    if (s.window_start_min < 0 || s.window_end_min > 1440) issues.push(`门店 ${s.id} 时间窗超出 0..1440`)
  }
  for (const v of r.vehicles) {
    if (v.length_mm <= 0 || v.width_mm <= 0 || v.height_mm <= 0 || v.max_weight_kg <= 0) issues.push(`车辆 ${v.id} 尺寸或载重必须为正`)
    if (v.fixed_cost < 0 || v.cost_per_km < 0) issues.push(`车辆 ${v.id} 费用为负`)
  }
  if (r.options.speed_kmph <= 0) issues.push('options.speed_kmph 必须为正')
  if (r.options.time_limit_ms < 100 || r.options.time_limit_ms > 60000) issues.push('options.time_limit_ms 应在 100..60000')
  if (r.options.max_iterations < 1 || r.options.max_iterations > 10000) issues.push('options.max_iterations 应在 1..10000')
  if (r.depot.departure_min < 0 || r.depot.departure_min > 1440) issues.push('depot.departure_min 超出 0..1440')
  return issues
}
