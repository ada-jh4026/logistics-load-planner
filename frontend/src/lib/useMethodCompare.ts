import { useCallback, useRef, useState } from 'react'
import type { JobResponse, SolveRequest } from '../protocol/contract'
import { ApiError, pollJob, submitSolve } from './api'

export const METHODS = ['greedy', 'sequential', 'coupled'] as const
export type Method = (typeof METHODS)[number]

export interface MethodRun {
  method: Method
  response: JobResponse
  servedSet: string[]
}

export type CompareState =
  | { phase: 'idle' }
  | { phase: 'running'; current: Method; done: MethodRun[] }
  | { phase: 'done'; runs: MethodRun[]; request: SolveRequest }
  | { phase: 'error'; message: string; done: MethodRun[] }

/**
 * 同一请求依次用三种方法求解（串行提交，避免占满服务队列），结果一起返回。
 * 只提交与轮询，不在前端重算任何指标。
 */
export function useMethodCompare() {
  const [state, setState] = useState<CompareState>({ phase: 'idle' })
  const abortRef = useRef<AbortController | null>(null)

  const run = useCallback(async (request: SolveRequest) => {
    abortRef.current?.abort()
    const ac = new AbortController()
    abortRef.current = ac
    const done: MethodRun[] = []
    for (const method of METHODS) {
      if (ac.signal.aborted) return
      setState({ phase: 'running', current: method, done: [...done] })
      try {
        const req: SolveRequest = { ...request, options: { ...request.options, method } }
        const { run_id } = await submitSolve(req)
        const resp = await pollJob(run_id, { intervalMs: 500, signal: ac.signal })
        done.push({ method, response: resp, servedSet: (resp.result?.routes ?? []).flatMap((r) => r.store_ids).sort() })
      } catch (e) {
        if (ac.signal.aborted) return
        setState({ phase: 'error', message: e instanceof ApiError ? `${e.message}（${e.code}）` : String((e as Error).message), done: [...done] })
        return
      }
    }
    setState({ phase: 'done', runs: done, request })
  }, [])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setState({ phase: 'idle' })
  }, [])

  const clear = useCallback(() => setState({ phase: 'idle' }), [])

  return { state, run, cancel, clear, busy: state.phase === 'running' }
}

/** 两次运行是否按 EVALUATION 口径可比费用：服务门店集合相同且均通过校验且基线费用 > 0。 */
export function comparableCost(a: MethodRun, b: MethodRun): boolean {
  const va = a.response.result?.validation.valid && b.response.result?.validation.valid
  if (!va) return false
  if (a.servedSet.length !== b.servedSet.length || a.servedSet.some((s, i) => s !== b.servedSet[i])) return false
  return (a.response.result?.metrics.total_cost ?? 0) > 0
}
