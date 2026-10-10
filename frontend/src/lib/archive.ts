// 历史实验记录：主线 H01 之前/之后的真实求解输出（Result 外壳，artifacts/benchmarks/hetero-*）。
// 它们是真实算法结果，但来自旧代码版本与离线实验，页面上标为「历史记录」，不冒充当前服务的实时求解。
// 按需动态加载，不进入主包。import() 必须用字面量路径，Vite 才能解析仓库根目录外的文件。
import { JobResponseSchema, ResultSchema, SolveRequestSchema, type JobResponse, type SolveRequest } from '../protocol/contract'

export interface ArchiveEntry {
  id: string
  label: string
  description: string
  /** 相对仓库根目录的记录路径，供页面显示来源 */
  path: string
  load: () => Promise<{ request: unknown; response: unknown }>
}

export const ARCHIVE_ENTRIES: ArchiveEntry[] = [
  {
    id: 'hetero-repaired',
    label: '历史记录：修复成功（small-11 混合箱件，H01 后）',
    description: '10 店混合纸箱；初始 0 店可执行，逐店恢复到 10/10。',
    path: 'artifacts/benchmarks/hetero-mixed-after-20261010/runs/small-11-mixed-2/coupled',
    load: async () => ({
      request: (await import('../../../artifacts/benchmarks/hetero-mixed-after-20261010/runs/small-11-mixed-2/coupled/request.json')).default,
      response: (await import('../../../artifacts/benchmarks/hetero-mixed-after-20261010/runs/small-11-mixed-2/coupled/response.json')).default,
    }),
  },
  {
    id: 'hetero-partial-truncated',
    label: '历史记录：部分修复 + 日志截断（small-11，H01 前）',
    description: '修复前代码：8/10 店，拒绝记录被截断。',
    path: 'artifacts/benchmarks/hetero-mixed-before-20261010/runs/small-11-mixed-1/coupled',
    load: async () => ({
      request: (await import('../../../artifacts/benchmarks/hetero-mixed-before-20261010/runs/small-11-mixed-1/coupled/request.json')).default,
      response: (await import('../../../artifacts/benchmarks/hetero-mixed-before-20261010/runs/small-11-mixed-1/coupled/response.json')).default,
    }),
  },
  {
    id: 'hetero-budget',
    label: '历史记录：预算退出（standard-11，H01 前）',
    description: '修复前代码：30 店混合箱件，预算耗尽，0 店。',
    path: 'artifacts/benchmarks/hetero-mixed-before-20261010/runs/standard-11-mixed-2/coupled',
    load: async () => ({
      request: (await import('../../../artifacts/benchmarks/hetero-mixed-before-20261010/runs/standard-11-mixed-2/coupled/request.json')).default,
      response: (await import('../../../artifacts/benchmarks/hetero-mixed-before-20261010/runs/standard-11-mixed-2/coupled/response.json')).default,
    }),
  },
  {
    id: 'hetero-unresolved',
    label: '历史记录：未解决（hetero-dev-6，H01 前）',
    description: '修复前代码：3 店最小复现，尝试后仍 0 店。',
    path: 'artifacts/benchmarks/hetero-development-before-20261010/runs/hetero-dev-6/coupled',
    load: async () => ({
      request: (await import('../../../artifacts/benchmarks/hetero-development-before-20261010/runs/hetero-dev-6/coupled/request.json')).default,
      response: (await import('../../../artifacts/benchmarks/hetero-development-before-20261010/runs/hetero-dev-6/coupled/response.json')).default,
    }),
  },
  {
    id: 'hetero-not-needed',
    label: '历史记录：无需修复（hetero-long-2）',
    description: '固定正向控制案：一次装下，协同修复未触发。',
    path: 'artifacts/benchmarks/hetero-before-20261010/runs/hetero-long-2/coupled',
    load: async () => ({
      request: (await import('../../../artifacts/benchmarks/hetero-before-20261010/runs/hetero-long-2/coupled/request.json')).default,
      response: (await import('../../../artifacts/benchmarks/hetero-before-20261010/runs/hetero-long-2/coupled/response.json')).default,
    }),
  },
]

/** 把 Result 外壳包成 JobResponse；若已是 JobResponse 则原样校验。 */
export function toJobResponse(raw: unknown, caseId: string, runId: string): JobResponse {
  const asJob = JobResponseSchema.safeParse(raw)
  if (asJob.success) return asJob.data
  const result = ResultSchema.parse(raw)
  const full = result.metrics.served_stores === result.metrics.total_stores && result.validation.valid
  return JobResponseSchema.parse({
    schema_version: '0.1',
    run_id: runId,
    case_id: caseId,
    status: full ? 'succeeded' : 'partial',
    data_source: 'synthetic',
    is_mock: false,
    method: 'coupled',
    termination_reason: null,
    elapsed_ms: 0,
    result,
    error: null,
  })
}

export async function loadArchive(entry: ArchiveEntry): Promise<{ request: SolveRequest; response: JobResponse }> {
  const { request, response } = await entry.load()
  const req = SolveRequestSchema.parse(request)
  return { request: req, response: toJobResponse(response, req.case_id, `archive-${entry.id}`) }
}
