import { useCallback, useEffect, useRef, useState } from 'react'
import type { JobResponse, SolveRequest } from '../protocol/contract'
import type { AgentHealth, CompareResponse, ExplainResponse, Focus, InterpretResponse } from '../protocol/agent'
import { ApiError } from './api'
import { compare, explain, fetchAgentHealth, interpret } from './agentApi'

export type AgentStatus = { kind: 'probing' } | { kind: 'offline' } | { kind: 'online'; health: AgentHealth }

export interface RunPair {
  request: SolveRequest
  response: JobResponse
}

export interface AssistantState {
  status: AgentStatus
  explanation: { focus: Focus; vehicleId: string | null; result: ExplainResponse } | null
  explaining: boolean
  interpretation: { instruction: string; result: InterpretResponse } | null
  interpreting: boolean
  comparison: { result: CompareResponse; baseline: RunPair; candidate: RunPair } | null
  comparing: boolean
  error: string | null
}

const initial: AssistantState = {
  status: { kind: 'probing' },
  explanation: null,
  explaining: false,
  interpretation: null,
  interpreting: false,
  comparison: null,
  comparing: false,
  error: null,
}

/**
 * 调度助手状态机。把三种能力的调用、等待与错误集中在一处；
 * 「确认补丁 → 重算 → 对比」由 App 编排：App 记下 baseline，等新结果到达后调用 runCompare。
 */
export function useAssistant() {
  const [s, set] = useState<AssistantState>(initial)
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    fetchAgentHealth()
      .then((h) => alive.current && set((x) => ({ ...x, status: { kind: 'online', health: h } })))
      .catch(() => alive.current && set((x) => ({ ...x, status: { kind: 'offline' } })))
    return () => {
      alive.current = false
    }
  }, [])

  const fail = (e: unknown) => {
    const msg = e instanceof ApiError ? `${e.message}（${e.code}）` : (e as Error).message
    set((x) => ({ ...x, error: msg, explaining: false, interpreting: false, comparing: false }))
  }

  const runExplain = useCallback(async (request: SolveRequest, response: JobResponse, focus: Focus, vehicleId: string | null, question?: string) => {
    set((x) => ({ ...x, explaining: true, error: null }))
    try {
      const result = await explain(request, response, focus, vehicleId, question)
      if (!alive.current) return
      set((x) => ({ ...x, explaining: false, explanation: { focus, vehicleId, result } }))
    } catch (e) {
      fail(e)
    }
  }, [])

  const runInterpret = useCallback(async (request: SolveRequest, instruction: string) => {
    set((x) => ({ ...x, interpreting: true, error: null, interpretation: null }))
    try {
      const result = await interpret(request, instruction)
      if (!alive.current) return
      set((x) => ({ ...x, interpreting: false, interpretation: { instruction, result } }))
    } catch (e) {
      fail(e)
    }
  }, [])

  const runCompare = useCallback(async (baseline: RunPair, candidate: RunPair, instruction?: string) => {
    set((x) => ({ ...x, comparing: true, error: null }))
    try {
      const result = await compare(baseline, candidate, instruction)
      if (!alive.current) return
      set((x) => ({ ...x, comparing: false, comparison: { result, baseline, candidate } }))
    } catch (e) {
      fail(e)
    }
  }, [])

  const clearInterpretation = useCallback(() => set((x) => ({ ...x, interpretation: null })), [])
  /** 新方案开始计算时调用：旧方案的解释不再有效，对比结果保留到新对比到达 */
  const clearExplanation = useCallback(() => set((x) => ({ ...x, explanation: null })), [])
  const clearAll = useCallback(() => set((x) => ({ ...x, explanation: null, interpretation: null, comparison: null, error: null })), [])
  const clearError = useCallback(() => set((x) => ({ ...x, error: null })), [])

  return { s, runExplain, runInterpret, runCompare, clearInterpretation, clearExplanation, clearAll, clearError }
}
