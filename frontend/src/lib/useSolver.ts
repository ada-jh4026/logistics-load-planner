import { useCallback, useEffect, useRef, useState } from 'react'
import type { JobResponse, SolveRequest } from '../protocol/contract'
import { ApiError, ERROR_HINT, pollJob, submitSolve } from './api'

export type SolveState =
  | { phase: 'idle' }
  | { phase: 'submitting' }
  | { phase: 'polling'; runId: string; status: 'queued' | 'running'; startedAt: number }
  | { phase: 'error'; error: ApiError }

/**
 * 提交一次求解并轮询到终态。同一时刻只允许一个任务；再次提交会取消上一个轮询。
 * 终态响应通过 onResult 交给调用方；错误保留在 state 里，不清空用户输入。
 */
export function useSolver(onResult: (r: JobResponse) => void) {
  const [state, setState] = useState<SolveState>({ phase: 'idle' })
  const abortRef = useRef<AbortController | null>(null)
  const [now, setNow] = useState(() => Date.now())

  // 轮询期间每秒刷新一次「已等待」显示
  useEffect(() => {
    if (state.phase !== 'polling') return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [state.phase])

  useEffect(() => () => abortRef.current?.abort(), [])

  const run = useCallback(
    async (request: SolveRequest) => {
      abortRef.current?.abort()
      const ac = new AbortController()
      abortRef.current = ac
      setState({ phase: 'submitting' })
      try {
        const { run_id } = await submitSolve(request)
        if (ac.signal.aborted) return
        const startedAt = Date.now()
        setState({ phase: 'polling', runId: run_id, status: 'queued', startedAt })
        const final = await pollJob(run_id, {
          intervalMs: 500,
          signal: ac.signal,
          onUpdate: (r) => setState({ phase: 'polling', runId: run_id, status: r.status === 'running' ? 'running' : 'queued', startedAt }),
        })
        if (ac.signal.aborted) return
        setState({ phase: 'idle' })
        onResult(final)
      } catch (e) {
        if (ac.signal.aborted || (e instanceof DOMException && e.name === 'AbortError')) return
        const err = e instanceof ApiError ? e : new ApiError(0, 'NETWORK', ERROR_HINT.NETWORK)
        setState({ phase: 'error', error: err })
      }
    },
    [onResult],
  )

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setState({ phase: 'idle' })
  }, [])

  const dismissError = useCallback(() => setState((s) => (s.phase === 'error' ? { phase: 'idle' } : s)), [])

  const waitedSec = state.phase === 'polling' ? Math.floor((now - state.startedAt) / 1000) : 0
  return { state, run, cancel, dismissError, busy: state.phase === 'submitting' || state.phase === 'polling', waitedSec }
}
