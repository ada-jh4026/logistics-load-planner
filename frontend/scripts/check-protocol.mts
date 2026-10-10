// 运行时协议检查：用真实响应与旧样例喂 Zod 模型。
//   npx --yes tsx frontend/scripts/check-protocol.mts   （仓库根目录）
import { readFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { JobResponseSchema, ResultSchema, SolveRequestSchema } from '../src/protocol/contract.ts'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const load = (p: string) => JSON.parse(readFileSync(resolve(root, p), 'utf-8'))
let failed = 0
const check = (label: string, fn: () => void) => {
  try {
    fn()
    console.log('PASS', label)
  } catch (e) {
    failed++
    console.log('FAIL', label, String((e as Error).message).slice(0, 300))
  }
}

for (const c of ['api-geometry-22', 'api-time-geometry-22']) {
  const d = `artifacts/repair-trace/${c}`
  if (!existsSync(resolve(root, d))) continue
  check(`${c} job_response.json 带 repair_trace`, () => {
    const job = JobResponseSchema.parse(load(`${d}/job_response.json`))
    const rt = job.result!.repair_trace!
    if (rt.status !== 'repaired' || rt.accepted_count < 1) throw new Error('trace 状态不符')
    const acc = rt.events.filter((e) => e.outcome === 'accepted')
    if (!acc.length || acc.some((e) => !e.routes_before || !e.routes_after)) throw new Error('accepted 事件缺快照')
    SolveRequestSchema.parse(load(`${d}/request.json`))
  })
}
check('旧样例 response-success.json 缺字段 → null', () => {
  const job = JobResponseSchema.parse(load('docs/playbook/examples/response-success.json'))
  if (job.result!.repair_trace !== null) throw new Error('应为 null')
})
check('旧样例 response-partial.json 缺字段 → null', () => {
  const job = JobResponseSchema.parse(load('docs/playbook/examples/response-partial.json'))
  if (job.result!.repair_trace !== null) throw new Error('应为 null')
})
check('small-11 Result not_needed', () => {
  const p = 'artifacts/repair-trace/small-11/response.json'
  if (!existsSync(resolve(root, p))) return
  const r = ResultSchema.parse(load(p))
  if (r.repair_trace?.status !== 'not_needed' || r.repair_trace.events.length !== 0) throw new Error('not_needed 解析不符')
})
check('非法 status 被拒绝', () => {
  const job = load('docs/playbook/examples/response-success.json')
  job.result.repair_trace = { version: 1, status: 'magic', initial_metrics: job.result.metrics, final_metrics: job.result.metrics, initial_routes: [], attempted_count: 0, accepted_count: 0, events: [], truncated: false, omitted_count: 0 }
  const r = JobResponseSchema.safeParse(job)
  if (r.success) throw new Error('应拒绝')
})
console.log(failed ? `${failed} 项失败` : '全部通过')
process.exit(failed ? 1 : 0)
