// 求解器与智能体服务的 HTTP 客户端。地址只用同源相对路径，由 Vite 代理或生产网关转发。
import { z } from 'zod'
import { ApiErrorSchema, JobResponseSchema, SolveRequestSchema, type JobResponse, type SolveRequest } from '../protocol/contract'

export class ApiError extends Error {
  status: number
  code: string
  details: { path: string; message: string }[]
  constructor(status: number, code: string, message: string, details: { path: string; message: string }[] = []) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

export const ERROR_HINT: Record<string, string> = {
  INVALID_INPUT: '请求不符合协议，请检查导入的数据。',
  NOT_FOUND: '任务不存在，服务可能已重启。请重新提交。',
  QUEUE_FULL: '服务队列已满，请稍后再试。',
  INTERNAL_ERROR: '服务内部错误。',
  NETWORK: '无法连接服务。请确认求解服务已在 8000 端口启动。',
  BAD_RESPONSE: '服务返回的数据不符合协议 v0.1。',
}

async function http<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, { ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) } })
  } catch (e) {
    throw new ApiError(0, 'NETWORK', ERROR_HINT.NETWORK + ` (${(e as Error).message})`)
  }
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    if (res.ok) throw new ApiError(res.status, 'BAD_RESPONSE', ERROR_HINT.BAD_RESPONSE)
  }
  if (!res.ok) {
    const parsed = ApiErrorSchema.safeParse(body)
    if (parsed.success) {
      const e = parsed.data.error
      throw new ApiError(res.status, e.code, e.message, e.details)
    }
    throw new ApiError(res.status, 'HTTP_' + res.status, `服务返回 HTTP ${res.status}`)
  }
  const parsed = schema.safeParse(body)
  if (!parsed.success) {
    throw new ApiError(res.status, 'BAD_RESPONSE', ERROR_HINT.BAD_RESPONSE + ' ' + parsed.error.issues.slice(0, 3).map((i) => i.path.join('.')).join('、'))
  }
  return parsed.data
}

export const ExampleItemSchema = z.object({ case_id: z.string(), label: z.string(), description: z.string() })
export type ExampleItem = z.infer<typeof ExampleItemSchema>

export const HealthSchema = z.object({ status: z.string(), schema_version: z.string() })

export function fetchHealth(): Promise<{ status: string; schema_version: string }> {
  return http('/api/health', HealthSchema)
}

export function fetchExamples(): Promise<ExampleItem[]> {
  return http('/api/examples', z.array(ExampleItemSchema))
}

export function fetchExample(caseId: string): Promise<SolveRequest> {
  return http(`/api/examples/${encodeURIComponent(caseId)}`, SolveRequestSchema)
}

const AckSchema = z.object({ schema_version: z.string(), run_id: z.string(), status: z.string() })

export function submitSolve(request: SolveRequest): Promise<{ run_id: string }> {
  return http('/api/solve', AckSchema, { method: 'POST', body: JSON.stringify(request) })
}

export function fetchJob(runId: string): Promise<JobResponse> {
  return http(`/api/jobs/${encodeURIComponent(runId)}`, JobResponseSchema)
}

const TERMINAL = new Set(['succeeded', 'partial', 'failed'])

/**
 * 每 intervalMs 轮询一次直到终态。signal 中止时停止轮询并以 AbortError 拒绝。
 * onUpdate 在每次拿到非终态响应时回调（用于显示排队/计算中）。
 */
export async function pollJob(
  runId: string,
  opts: { intervalMs?: number; signal?: AbortSignal; onUpdate?: (r: JobResponse) => void } = {},
): Promise<JobResponse> {
  const interval = opts.intervalMs ?? 500
  for (;;) {
    if (opts.signal?.aborted) throw new DOMException('轮询已取消', 'AbortError')
    const r = await fetchJob(runId)
    if (TERMINAL.has(r.status)) return r
    opts.onUpdate?.(r)
    await new Promise<void>((resolve, reject) => {
      const t = setTimeout(resolve, interval)
      opts.signal?.addEventListener('abort', () => {
        clearTimeout(t)
        reject(new DOMException('轮询已取消', 'AbortError'))
      }, { once: true })
    })
  }
}
