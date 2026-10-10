// 与 docs/playbook/CONTRACT.md v0.1 一一对应。字段名、单位、枚举以该文件为准；这里只做运行时校验与类型推导。
import { z } from 'zod'

export const SCHEMA_VERSION = '0.1' as const

const finite = z.number().finite()

export const DepotSchema = z.object({
  id: z.string().min(1),
  x_km: finite,
  y_km: finite,
  departure_min: finite,
})

export const StoreSchema = z.object({
  id: z.string().min(1),
  x_km: finite,
  y_km: finite,
  window_start_min: finite,
  window_end_min: finite,
  service_min: finite,
})

export const VehicleSchema = z.object({
  id: z.string().min(1),
  length_mm: finite,
  width_mm: finite,
  height_mm: finite,
  max_weight_kg: finite,
  fixed_cost: finite,
  cost_per_km: finite,
})

export const BoxSchema = z.object({
  id: z.string().min(1),
  store_id: z.string().min(1),
  length_mm: finite,
  width_mm: finite,
  height_mm: finite,
  weight_kg: finite,
  fragile: z.boolean(),
  allow_rotate_xy: z.boolean(),
})

export const MethodSchema = z.enum(['greedy', 'sequential', 'coupled'])

export const OptionsSchema = z.object({
  method: MethodSchema,
  seed: z.number().int(),
  time_limit_ms: z.number().int(),
  max_iterations: z.number().int(),
  speed_kmph: finite,
})

export const SolveRequestSchema = z.object({
  schema_version: z.literal(SCHEMA_VERSION),
  case_id: z.string().min(1),
  data_source: z.string(),
  depot: DepotSchema,
  stores: z.array(StoreSchema).min(1),
  vehicles: z.array(VehicleSchema).min(1),
  boxes: z.array(BoxSchema).min(1),
  options: OptionsSchema,
})

export const StopSchema = z.object({
  store_id: z.string(),
  arrival_min: finite,
  service_start_min: finite,
  departure_min: finite,
})

export const PlacementSchema = z.object({
  box_id: z.string(),
  x_mm: finite,
  y_mm: finite,
  z_mm: finite,
  rotation_xy: z.union([z.literal(0), z.literal(90)]),
})

export const UnloadStepSchema = z.object({
  step: z.number().int(),
  store_id: z.string(),
  box_id: z.string(),
})

export const RouteSchema = z.object({
  vehicle_id: z.string(),
  store_ids: z.array(z.string()),
  stops: z.array(StopSchema),
  return_min: finite,
  distance_km: finite,
  cost: finite,
  box_ids: z.array(z.string()),
  placements: z.array(PlacementSchema),
  unload_steps: z.array(UnloadStepSchema),
})

export const ReasonCodeSchema = z.enum([
  'BOX_TOO_LARGE',
  'CAPACITY_LIMIT',
  'TIME_WINDOW',
  'SEARCH_EXHAUSTED',
  'TIME_LIMIT',
])

export const UnassignedSchema = z.object({
  store_id: z.string(),
  box_ids: z.array(z.string()),
  reason_code: ReasonCodeSchema,
  message: z.string(),
})

export const ViolationSchema = z.object({
  code: z.string(),
  vehicle_id: z.string().nullable(),
  box_ids: z.array(z.string()),
  store_id: z.string().nullable(),
  message: z.string(),
})

export const MetricsSchema = z.object({
  total_stores: z.number().int(),
  served_stores: z.number().int(),
  total_boxes: z.number().int(),
  served_boxes: z.number().int(),
  completion_rate: finite,
  used_vehicles: z.number().int(),
  total_distance_km: finite,
  total_cost: finite,
  on_time_rate: finite.nullable(),
  volume_utilization: finite.nullable(),
  weight_utilization: finite.nullable(),
  unload_block_count: z.number().int(),
})

export const DiagnosticSchema = z.object({
  iteration: z.number().int(),
  action: z.string(),
  reason_code: z.string().nullable().optional(),
  message: z.string(),
})

export const ResultSchema = z.object({
  routes: z.array(RouteSchema),
  unassigned: z.array(UnassignedSchema),
  validation: z.object({ valid: z.boolean(), violations: z.array(ViolationSchema) }),
  metrics: MetricsSchema,
  diagnostics: z.array(DiagnosticSchema),
})

export const JobStatusSchema = z.enum(['queued', 'running', 'succeeded', 'partial', 'failed'])
export const TerminationSchema = z
  .enum(['completed', 'time_limit', 'iteration_limit', 'internal_error'])
  .nullable()

export const JobResponseSchema = z.object({
  schema_version: z.literal(SCHEMA_VERSION),
  run_id: z.string(),
  case_id: z.string(),
  status: JobStatusSchema,
  data_source: z.string(),
  is_mock: z.boolean(),
  method: MethodSchema,
  termination_reason: TerminationSchema,
  elapsed_ms: finite,
  result: ResultSchema.nullable(),
  error: z.object({ code: z.string(), message: z.string() }).nullable(),
})

export const ApiErrorSchema = z.object({
  schema_version: z.literal(SCHEMA_VERSION),
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.array(z.object({ path: z.string(), message: z.string() })),
  }),
})

export type Depot = z.infer<typeof DepotSchema>
export type Store = z.infer<typeof StoreSchema>
export type Vehicle = z.infer<typeof VehicleSchema>
export type Box = z.infer<typeof BoxSchema>
export type SolveOptions = z.infer<typeof OptionsSchema>
export type SolveRequest = z.infer<typeof SolveRequestSchema>
export type Stop = z.infer<typeof StopSchema>
export type Placement = z.infer<typeof PlacementSchema>
export type UnloadStep = z.infer<typeof UnloadStepSchema>
export type Route = z.infer<typeof RouteSchema>
export type Unassigned = z.infer<typeof UnassignedSchema>
export type ReasonCode = z.infer<typeof ReasonCodeSchema>
export type Metrics = z.infer<typeof MetricsSchema>
export type Result = z.infer<typeof ResultSchema>
export type JobStatus = z.infer<typeof JobStatusSchema>
export type JobResponse = z.infer<typeof JobResponseSchema>
export type ApiError = z.infer<typeof ApiErrorSchema>

/** 把 zod 错误整理成「路径：问题」列表，供导入失败时逐条显示。 */
export function formatIssues(err: z.ZodError): string[] {
  return err.issues.map((i) => `${i.path.join('.') || '(根)'}：${i.message}`)
}

/** 未配送原因码的中文说明，页面与解释文本共用。 */
export const REASON_LABEL: Record<ReasonCode, string> = {
  BOX_TOO_LARGE: '箱件尺寸超过所有车厢',
  CAPACITY_LIMIT: '载重或容量不足',
  TIME_WINDOW: '时间窗无法满足',
  SEARCH_EXHAUSTED: '在搜索范围内未找到可行装载',
  TIME_LIMIT: '求解时间预算用尽',
}
