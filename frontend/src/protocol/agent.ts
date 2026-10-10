// 与 docs/playbook/AGENT_CONTRACT.md v0.1 一一对应。
import { z } from 'zod'
import { JobResponseSchema, MetricsSchema, SolveRequestSchema, VehicleSchema } from './contract'

export const AgentModeSchema = z.enum(['llm', 'template'])
export const FocusSchema = z.enum(['overview', 'unassigned', 'unload', 'vehicle'])
export type Focus = z.infer<typeof FocusSchema>

export const GroundingSchema = z.object({
  checked_numbers: z.number().int(),
  unmatched_numbers: z.array(z.string()),
  passed: z.boolean(),
})

const base = {
  schema_version: z.literal('0.1'),
  mode: AgentModeSchema,
  model: z.string().nullable(),
  warnings: z.array(z.string()),
}

export const AgentHealthSchema = z.object({
  status: z.literal('ok'),
  schema_version: z.literal('0.1'),
  llm: z.object({ provider: z.string().nullable(), model: z.string().nullable(), configured: z.boolean() }),
})
export type AgentHealth = z.infer<typeof AgentHealthSchema>

export const ExplainResponseSchema = z.object({
  ...base,
  text: z.string(),
  facts: z.record(z.string(), z.unknown()),
  grounding: GroundingSchema,
})
export type ExplainResponse = z.infer<typeof ExplainResponseSchema>

export const IntentOpSchema = z.object({
  action: z.enum(['set', 'remove_vehicle', 'add_vehicle']),
  target: z.enum(['store', 'box', 'vehicle', 'depot', 'options']).nullable(),
  id: z.string().nullable(),
  field: z.string().nullable(),
  value: z.unknown(),
})
export type IntentOp = z.infer<typeof IntentOpSchema>

export const PatchOpSchema = z.object({
  op: z.enum(['replace', 'remove', 'add']),
  path: z.string(),
  value: z.unknown(),
})
export type PatchOp = z.infer<typeof PatchOpSchema>

export const InterpretResponseSchema = z.object({
  ...base,
  understood: z.boolean(),
  intent_ops: z.array(IntentOpSchema),
  patch: z.array(PatchOpSchema),
  patched_request: SolveRequestSchema.nullable(),
  rejected_ops: z.array(z.object({ intent: IntentOpSchema, reason: z.string() })),
  summary: z.string(),
})
export type InterpretResponse = z.infer<typeof InterpretResponseSchema>

export const MetricDeltaSchema = z.object({
  baseline: z.number().nullable(),
  candidate: z.number().nullable(),
  delta: z.number().nullable(),
})

export const CompareResponseSchema = z.object({
  ...base,
  deltas: z.record(z.string(), MetricDeltaSchema),
  same_served_set: z.boolean(),
  both_valid: z.boolean(),
  comparable_cost: z.boolean(),
  cost_change_rate: z.number().nullable(),
  text: z.string(),
  grounding: GroundingSchema,
})
export type CompareResponse = z.infer<typeof CompareResponseSchema>

export const RunPairSchema = z.object({ request: SolveRequestSchema, response: JobResponseSchema })
export type RunPair = z.infer<typeof RunPairSchema>

export { MetricsSchema, VehicleSchema }
