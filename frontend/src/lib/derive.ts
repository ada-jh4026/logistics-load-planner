import type { Box, JobResponse, Route, SolveRequest, Store, Vehicle } from '../protocol/contract'

/** 把请求与响应整理成页面直接可用的索引；不重算任何路线或布局。 */
export interface Derived {
  storesById: Map<string, Store>
  boxesById: Map<string, Box>
  vehiclesById: Map<string, Vehicle>
  routesByVehicle: Map<string, Route>
  unusedVehicles: Vehicle[]
  unassignedStoreIds: Set<string>
}

export function derive(request: SolveRequest, response: JobResponse | null): Derived {
  const storesById = new Map(request.stores.map((s) => [s.id, s]))
  const boxesById = new Map(request.boxes.map((b) => [b.id, b]))
  const vehiclesById = new Map(request.vehicles.map((v) => [v.id, v]))
  const routes = response?.result?.routes ?? []
  const routesByVehicle = new Map(routes.map((r) => [r.vehicle_id, r]))
  const unusedVehicles = request.vehicles.filter((v) => !routesByVehicle.has(v.id))
  const unassignedStoreIds = new Set((response?.result?.unassigned ?? []).map((u) => u.store_id))
  return { storesById, boxesById, vehiclesById, routesByVehicle, unusedVehicles, unassignedStoreIds }
}

/** 门店在该车路线中的到站序号（0 起），不在路线中为 -1。 */
export function stopIndexOf(route: Route, storeId: string): number {
  return route.store_ids.indexOf(storeId)
}

export function routeWeightKg(route: Route, boxesById: Map<string, Box>): number {
  return route.box_ids.reduce((s, id) => s + (boxesById.get(id)?.weight_kg ?? 0), 0)
}

export const STATUS_WORD: Record<JobResponse['status'], string> = {
  queued: '排队中',
  running: '计算中',
  succeeded: '全部配送',
  partial: '部分配送',
  failed: '求解失败',
}

export const METHOD_WORD: Record<SolveRequest['options']['method'], string> = {
  greedy: '简单贪心基线',
  sequential: '先路线后装载（不反馈）',
  coupled: '配载与路线协同',
}

export const TERMINATION_WORD: Record<string, string> = {
  completed: '搜索完成',
  time_limit: '达到时间预算',
  iteration_limit: '达到迭代上限',
  internal_error: '内部错误',
}
