import { useRef, useState } from 'react'
import type { JobResponse, SolveRequest } from '../protocol/contract'
import type { CaseOption } from '../lib/cases'
import { importRequestFile } from '../lib/importRequest'
import type { SolveState } from '../lib/useSolver'

interface Props {
  options: CaseOption[]
  selectedKey: string
  onSelect: (key: string) => void
  onImport: (request: SolveRequest, fileName: string) => void
  importedName: string | null
  response: JobResponse | null
  serviceOnline: boolean | null
  solveState: SolveState
  waitedSec: number
  onRun: () => void
  onCancel: () => void
  onCompareMethods: () => void
  comparing: boolean
  comparingMethod: string | null
}

export function TopBar({ options, selectedKey, onSelect, onImport, importedName, response, serviceOnline, solveState, waitedSec, onRun, onCancel, onCompareMethods, comparing, comparingMethod }: Props) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [issues, setIssues] = useState<string[] | null>(null)
  const busy = solveState.phase === 'submitting' || solveState.phase === 'polling' || comparing

  async function handleFile(file: File | undefined) {
    if (!file) return
    const r = await importRequestFile(file)
    if (r.ok) {
      setIssues(null)
      onImport(r.request, file.name)
    } else {
      setIssues(r.issues)
    }
    if (fileRef.current) fileRef.current.value = ''
  }

  const runHint =
    serviceOnline === false
      ? '求解服务未连接。启动后端（8000 端口）后刷新页面。'
      : serviceOnline === null
        ? '正在探测求解服务。'
        : '把当前请求提交给求解服务并等待结果。'

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-stripe" aria-hidden="true" />
        <div>
          <h1>配载工作台</h1>
          <small>城市配送：路线、装载与卸货一体规划</small>
        </div>
      </div>

      <div className="topbar-controls">
        <label htmlFor="scenario">案例</label>
        <select id="scenario" className="select" value={importedName ? '__imported__' : selectedKey} onChange={(e) => onSelect(e.target.value)} disabled={busy}>
          {importedName && <option value="__imported__">已导入：{importedName}</option>}
          {options.some((o) => o.source === 'service') && (
            <optgroup label="求解服务案例（真实求解）">
              {options
                .filter((o) => o.source === 'service')
                .map((o) => (
                  <option key={o.key} value={o.key}>
                    {o.label}
                  </option>
                ))}
            </optgroup>
          )}
          {options.some((o) => o.source === 'archive') && (
            <optgroup label="历史实验记录（真实求解输出，离线）">
              {options
                .filter((o) => o.source === 'archive')
                .map((o) => (
                  <option key={o.key} value={o.key}>
                    {o.label}
                  </option>
                ))}
            </optgroup>
          )}
          <optgroup label="本地样例（手工界面样例）">
            {options
              .filter((o) => o.source === 'sample')
              .map((o) => (
                <option key={o.key} value={o.key}>
                  {o.label}
                </option>
              ))}
          </optgroup>
        </select>
        <label className={`btn quiet file-btn ${busy ? 'disabled' : ''}`}>
          导入 JSON
          <input ref={fileRef} type="file" accept="application/json,.json" disabled={busy} onChange={(e) => handleFile(e.target.files?.[0])} />
        </label>
        {busy ? (
          <button className="btn secondary" onClick={onCancel} title="停止等待；服务端任务不会被中断">
            {comparing ? `对比中：${comparingMethod ?? ''}` : solveState.phase === 'polling' && solveState.status === 'running' ? '计算中' : '排队中'}
            {!comparing && waitedSec > 0 ? ` ${waitedSec}s` : ''}，取消
          </button>
        ) : (
          <>
            <button className="btn" onClick={onRun} disabled={serviceOnline !== true} title={runHint}>
              运行求解
            </button>
            <button className="btn secondary" onClick={onCompareMethods} disabled={serviceOnline !== true} title="同一请求依次用简单贪心、先路线后装载、配载与路线协同求解，并排比较">
              对比三种方法
            </button>
          </>
        )}
      </div>

      <div className="topbar-status">
        {serviceOnline === false && <span className="tag critical" title="GET /api/health 失败">求解服务未连接</span>}
        {serviceOnline === true && <span className="tag good">求解服务已连接</span>}
        {response?.is_mock && (
          <span className="tag mock" title="响应是手工构造的界面样例，不是算法结果">
            演示数据
          </span>
        )}
        {response && !response.is_mock && !response.run_id.startsWith('archive-') && (
          <span className="tag good" title="由求解服务实际计算得到">
            真实求解
          </span>
        )}
        {response && response.run_id.startsWith('archive-') && (
          <span className="tag" title="主线离线实验保存的真实求解输出（可能来自旧代码版本），不是当前服务实时计算">
            历史记录
          </span>
        )}
        {response && response.data_source === 'synthetic' && (
          <span className="tag" title="输入为模拟业务数据，非企业真实数据">
            模拟数据
          </span>
        )}
        {response && <span className="tag" title={response.run_id}>运行 {response.run_id.slice(0, 8)}</span>}
      </div>

      {issues && (
        <div className="import-issues" role="alert">
          <strong>导入失败，文件不符合协议 v0.1。</strong>
          <ul>
            {issues.slice(0, 12).map((i, k) => (
              <li key={k}>{i}</li>
            ))}
            {issues.length > 12 && <li>还有 {issues.length - 12} 项未显示。</li>}
          </ul>
          <button className="btn quiet" style={{ marginTop: 8 }} onClick={() => setIssues(null)}>
            关闭
          </button>
        </div>
      )}
    </header>
  )
}
