// 演示样例直接引用 docs/playbook/examples，不在前端复制一份字段。
// 这些响应 is_mock=true，是手工构造的界面样例，不是算法结果。
import { JobResponseSchema, SolveRequestSchema, type JobResponse, type SolveRequest } from '../protocol/contract'
import requestSuccess from '../../../docs/playbook/examples/request-success.json'
import responseSuccess from '../../../docs/playbook/examples/response-success.json'
import requestPartial from '../../../docs/playbook/examples/request-partial.json'
import responsePartial from '../../../docs/playbook/examples/response-partial.json'
import responseFailed from '../../../docs/playbook/examples/response-failed.json'

export interface Scenario {
  id: string
  label: string
  description: string
  request: SolveRequest
  response: JobResponse
}

function parse<T>(schema: { parse: (v: unknown) => T }, value: unknown, name: string): T {
  try {
    return schema.parse(value)
  } catch (e) {
    throw new Error(`样例 ${name} 不符合协议 v0.1：${(e as Error).message}`)
  }
}

export const SCENARIOS: Scenario[] = [
  {
    id: 'ui-success',
    label: '样例：全部配送',
    description: '1 家门店、1 辆车、2 箱；易碎箱在上，先卸。',
    request: parse(SolveRequestSchema, requestSuccess, 'request-success'),
    response: parse(JobResponseSchema, responseSuccess, 'response-success'),
  },
  {
    id: 'ui-partial',
    label: '样例：部分配送',
    description: '2 家门店；S02 的箱件尺寸超过车厢，未配送。',
    request: parse(SolveRequestSchema, requestPartial, 'request-partial'),
    response: parse(JobResponseSchema, responsePartial, 'response-partial'),
  },
  {
    id: 'ui-failed',
    label: '样例：求解失败',
    description: '服务内部错误时的页面反馈。',
    request: parse(SolveRequestSchema, requestSuccess, 'request-success'),
    response: parse(JobResponseSchema, responseFailed, 'response-failed'),
  },
]
