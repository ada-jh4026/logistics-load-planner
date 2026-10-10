// 案例来源：求解服务的 data/cases（真实求解）与本地样例（手工 UI 样例）。
import type { JobResponse, SolveRequest } from '../protocol/contract'
import { fetchExample, fetchExamples, fetchHealth } from './api'
import { SCENARIOS } from './mock'
import { ARCHIVE_ENTRIES, loadArchive } from './archive'

export type CaseSource = 'service' | 'sample' | 'archive' | 'imported'

export interface CaseOption {
  key: string
  source: CaseSource
  label: string
  description: string
  caseId: string
}

export const SAMPLE_OPTIONS: CaseOption[] = SCENARIOS.map((s) => ({
  key: `sample:${s.id}`,
  source: 'sample',
  label: s.label,
  description: s.description,
  caseId: s.id,
}))

export const ARCHIVE_OPTIONS: CaseOption[] = ARCHIVE_ENTRIES.map((a) => ({
  key: `archive:${a.id}`,
  source: 'archive',
  label: a.label,
  description: a.description,
  caseId: a.id,
}))

const SERVICE_LABEL: Record<string, string> = {
  c01: '服务案例 c01：1 店 2 箱，正常配送',
  c02: '服务案例 c02：单件尺寸超过车厢',
  c03: '服务案例 c03：时间窗无法到达',
  c07: '服务案例 c07：车辆不足，门店原子分配',
}

export function serviceLabel(caseId: string): string {
  if (SERVICE_LABEL[caseId]) return SERVICE_LABEL[caseId]
  const m = /^(small|standard|stress)-(\d+)$/.exec(caseId)
  if (m) {
    const size = { small: '10 店', standard: '30 店', stress: '60 店' }[m[1]]
    return `服务案例 ${caseId}：${size}，种子 ${m[2]}`
  }
  return `服务案例 ${caseId}`
}

/** 探测求解服务；可达时返回案例列表，不可达返回 null。 */
export async function loadServiceCases(): Promise<CaseOption[] | null> {
  try {
    await fetchHealth()
    const items = await fetchExamples()
    return items.map((it) => ({
      key: `service:${it.case_id}`,
      source: 'service',
      label: serviceLabel(it.case_id),
      description: it.description,
      caseId: it.case_id,
    }))
  } catch {
    return null
  }
}

export async function loadCase(opt: CaseOption): Promise<{ request: SolveRequest; response: JobResponse | null }> {
  if (opt.source === 'sample') {
    const s = SCENARIOS.find((x) => x.id === opt.caseId)!
    return { request: s.request, response: s.response }
  }
  if (opt.source === 'archive') {
    const a = ARCHIVE_ENTRIES.find((x) => x.id === opt.caseId)!
    return loadArchive(a)
  }
  return { request: await fetchExample(opt.caseId), response: null }
}
