// 调度助手服务客户端（/agent/* 由 Vite 代理到 8001）。
import { z } from 'zod'
import type { JobResponse, SolveRequest } from '../protocol/contract'
import { ApiErrorSchema } from '../protocol/contract'
import {
  AgentHealthSchema,
  CompareResponseSchema,
  ExplainResponseSchema,
  InterpretResponseSchema,
  type AgentHealth,
  type CompareResponse,
  type ExplainResponse,
  type Focus,
  type InterpretResponse,
} from '../protocol/agent'
import { ApiError } from './api'

async function http<T>(path: string, schema: z.ZodType<T>, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined)
  } catch (e) {
    throw new ApiError(0, 'NETWORK', `无法连接调度助手服务（8001）：${(e as Error).message}`)
  }
  let json: unknown = null
  try {
    json = await res.json()
  } catch {
    throw new ApiError(res.status, 'BAD_RESPONSE', '调度助手返回的数据不是 JSON。')
  }
  if (!res.ok) {
    const p = ApiErrorSchema.safeParse(json)
    if (p.success) throw new ApiError(res.status, p.data.error.code, p.data.error.message, p.data.error.details)
    throw new ApiError(res.status, 'HTTP_' + res.status, `调度助手返回 HTTP ${res.status}`)
  }
  const p = schema.safeParse(json)
  if (!p.success) throw new ApiError(res.status, 'BAD_RESPONSE', '调度助手响应不符合 AGENT_CONTRACT v0.1：' + p.error.issues.slice(0, 3).map((i) => i.path.join('.')).join('、'))
  return p.data
}

export function fetchAgentHealth(): Promise<AgentHealth> {
  return http('/agent/health', AgentHealthSchema)
}

export function explain(request: SolveRequest, response: JobResponse, focus: Focus, vehicleId?: string | null, question?: string): Promise<ExplainResponse> {
  return http('/agent/explain', ExplainResponseSchema, {
    schema_version: '0.1',
    request,
    response,
    focus,
    vehicle_id: vehicleId ?? null,
    question: question || null,
  })
}

export function interpret(request: SolveRequest, instruction: string): Promise<InterpretResponse> {
  return http('/agent/interpret', InterpretResponseSchema, { schema_version: '0.1', request, instruction })
}

export function compare(baseline: { request: SolveRequest; response: JobResponse }, candidate: { request: SolveRequest; response: JobResponse }, instruction?: string): Promise<CompareResponse> {
  return http('/agent/compare', CompareResponseSchema, { schema_version: '0.1', baseline, candidate, instruction: instruction || null })
}
