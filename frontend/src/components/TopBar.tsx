import { useRef, useState } from 'react'
import type { JobResponse, SolveRequest } from '../protocol/contract'
import type { Scenario } from '../lib/mock'
import { importRequestFile } from '../lib/importRequest'

interface Props {
  scenarios: Scenario[]
  scenarioId: string
  onScenarioChange: (id: string) => void
  onImport: (request: SolveRequest, fileName: string) => void
  importedName: string | null
  response: JobResponse | null
  onRun: () => void
  runEnabled: boolean
  runHint: string
}

export function TopBar({ scenarios, scenarioId, onScenarioChange, onImport, importedName, response, onRun, runEnabled, runHint }: Props) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [issues, setIssues] = useState<string[] | null>(null)

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
        <select
          id="scenario"
          className="select"
          value={importedName ? '__imported__' : scenarioId}
          onChange={(e) => onScenarioChange(e.target.value)}
        >
          {importedName && <option value="__imported__">已导入：{importedName}</option>}
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
        <label className="btn quiet file-btn">
          导入 JSON
          <input ref={fileRef} type="file" accept="application/json,.json" onChange={(e) => handleFile(e.target.files?.[0])} />
        </label>
        <button className="btn" onClick={onRun} disabled={!runEnabled} title={runHint}>
          运行求解
        </button>
      </div>

      <div className="topbar-status">
        {response?.is_mock && (
          <span className="tag mock" title="响应是手工构造的界面样例，不是算法结果">
            演示数据
          </span>
        )}
        {response && response.data_source === 'synthetic' && (
          <span className="tag" title="输入为模拟业务数据，非企业真实数据">
            模拟数据
          </span>
        )}
        {response && <span className="tag">运行 {response.run_id}</span>}
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
