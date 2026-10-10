import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { JobResponse, SolveRequest } from './protocol/contract'
import { derive } from './lib/derive'
import { ARCHIVE_OPTIONS, loadCase, loadServiceCases, SAMPLE_OPTIONS, type CaseOption } from './lib/cases'
import { eventVehicles, snapshotRoutes } from './lib/repair'
import { RepairPanel, type RepairFocus } from './components/RepairPanel'
import { ERROR_HINT } from './lib/api'
import { useSolver } from './lib/useSolver'
import { useAssistant, type RunPair } from './lib/useAssistant'
import { AssistantPanel } from './components/AssistantPanel'
import { TopBar } from './components/TopBar'
import { VehicleRail } from './components/VehicleRail'
import { CargoView } from './components/CargoView'
import { RouteMap } from './components/RouteMap'
import { UnloadStrip } from './components/UnloadStrip'
import { SidePanel } from './components/SidePanel'

type View = '3d' | 'map'

export default function App() {
  const [options, setOptions] = useState<CaseOption[]>([...ARCHIVE_OPTIONS, ...SAMPLE_OPTIONS])
  const [serviceOnline, setServiceOnline] = useState<boolean | null>(null)
  const [selectedKey, setSelectedKey] = useState(SAMPLE_OPTIONS[0].key)
  const [importedName, setImportedName] = useState<string | null>(null)
  const [request, setRequest] = useState<SolveRequest | null>(null)
  const [response, setResponse] = useState<JobResponse | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [view, setView] = useState<View>('3d')
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null)
  const [selectedBoxId, setSelectedBoxId] = useState<string | null>(null)
  const [unloadDone, setUnloadDone] = useState(0)
  const [resetKey, setResetKey] = useState(0)
  const [repairFocus, setRepairFocus] = useState<RepairFocus | null>(null)

  // 探测求解服务：可达则把服务案例放在前面并默认选中第一个服务案例
  useEffect(() => {
    let alive = true
    loadServiceCases().then((svc) => {
      if (!alive) return
      if (svc) {
        setOptions([...svc, ...ARCHIVE_OPTIONS, ...SAMPLE_OPTIONS])
        setServiceOnline(true)
        if (svc.length > 0) setSelectedKey(svc[0].key)
      } else {
        setServiceOnline(false)
      }
    })
    return () => {
      alive = false
    }
  }, [])

  // 切换案例：加载请求，清空旧结果，不让旧数字冒充新结果。
  useEffect(() => {
    if (importedName) return
    const opt = options.find((o) => o.key === selectedKey)
    if (!opt) return
    let alive = true
    setLoadError(null)
    loadCase(opt)
      .then(({ request, response }) => {
        if (!alive) return
        setRequest(request)
        setResponse(response)
        setSelectedBoxId(null)
        setUnloadDone(0)
        setRepairFocus(null)
      })
      .catch((e) => {
        if (!alive) return
        setLoadError(`读取案例失败：${(e as Error).message}`)
      })
    return () => {
      alive = false
    }
  }, [selectedKey, options, importedName])

  const assistant = useAssistant()
  // 「指令 → 确认 → 重算 → 对比」：确认时记下基线，新结果到达后自动对比
  const [pendingCompare, setPendingCompare] = useState<{ baseline: RunPair; patched: SolveRequest; instruction: string } | null>(null)
  const pendingRef = useRef(pendingCompare)
  pendingRef.current = pendingCompare

  const onResult = useCallback(
    (r: JobResponse) => {
      setResponse(r)
      setSelectedBoxId(null)
      setUnloadDone(0)
      setRepairFocus(null)
      const pend = pendingRef.current
      if (pend) {
        setPendingCompare(null)
        if (r.result && (r.status === 'succeeded' || r.status === 'partial')) {
          assistant.runCompare(pend.baseline, { request: pend.patched, response: r }, pend.instruction)
        }
      }
    },
    [assistant.runCompare],
  )
  const solver = useSolver(onResult)

  function handleSelect(key: string) {
    if (key === '__imported__') return
    solver.cancel()
    setPendingCompare(null)
    assistant.clearAll()
    setImportedName(null)
    setSelectedKey(key)
  }

  function handleConfirmPatch(patched: SolveRequest, instruction: string) {
    if (!request) return
    const baseline: RunPair | null = response?.result && (response.status === 'succeeded' || response.status === 'partial') ? { request, response } : null
    assistant.clearInterpretation()
    assistant.clearExplanation()
    setImportedName(importedName ?? `调整后：${request.case_id}`)
    setRequest(patched)
    setResponse(null)
    if (baseline) setPendingCompare({ baseline, patched, instruction })
    solver.run(patched)
  }

  function handleImport(req: SolveRequest, name: string) {
    solver.cancel()
    setPendingCompare(null)
    assistant.clearAll()
    setImportedName(name)
    setRequest(req)
    setResponse(null)
    setSelectedBoxId(null)
    setUnloadDone(0)
  }

  function handleRun() {
    if (!request) return
    setPendingCompare(null)
    assistant.clearExplanation()
    setResponse(null) // 新任务开始即清空旧方案
    solver.run(request)
  }

  // 修复事件快照：选中 accepted 事件时，3D/路线图改读后端随事件保存的 routes_before / routes_after
  const focusedEvent = useMemo(() => {
    if (!repairFocus || !response?.result?.repair_trace) return null
    return response.result.repair_trace.events.find((e) => e.event_id === repairFocus.eventId) ?? null
  }, [repairFocus, response])
  const snapshot = useMemo(() => (focusedEvent && repairFocus ? snapshotRoutes(focusedEvent, repairFocus.side) : null), [focusedEvent, repairFocus])
  const displayResponse = useMemo<JobResponse | null>(() => {
    if (!response?.result || !snapshot) return response
    return { ...response, result: { ...response.result, routes: snapshot } }
  }, [response, snapshot])
  const derived = useMemo(() => (request ? derive(request, displayResponse) : null), [request, displayResponse])
  const highlightStoreIds = useMemo(() => new Set(focusedEvent?.store_ids ?? []), [focusedEvent])
  const highlightBoxIds = useMemo(() => new Set(focusedEvent?.box_ids ?? []), [focusedEvent])

  // 默认选中第一辆启用的车；没有方案时选第一辆车。
  useEffect(() => {
    if (!request || !derived) return
    const firstUsed = request.vehicles.find((v) => derived.routesByVehicle.has(v.id)) ?? request.vehicles[0]
    setSelectedVehicleId(firstUsed?.id ?? null)
    setUnloadDone(0)
    setSelectedBoxId(null)
  }, [request, derived])

  useEffect(() => {
    if (!focusedEvent) return
    const vids = eventVehicles(focusedEvent)
    const prefer = repairFocus?.side === 'before' ? vids[0] : vids[vids.length - 1]
    if (prefer) setSelectedVehicleId(prefer)
    setUnloadDone(0)
    setSelectedBoxId(null)
  }, [focusedEvent, repairFocus?.side])

  const vehicle = derived && selectedVehicleId ? derived.vehiclesById.get(selectedVehicleId) ?? null : null
  const route = derived && selectedVehicleId ? derived.routesByVehicle.get(selectedVehicleId) ?? null : null

  const unloadedIds = useMemo(() => {
    const s = new Set<string>()
    route?.unload_steps.slice(0, unloadDone).forEach((st) => s.add(st.box_id))
    return s
  }, [route, unloadDone])
  const currentBoxId = route && unloadDone < route.unload_steps.length ? route.unload_steps[unloadDone].box_id : null

  const failed = response?.status === 'failed'
  const busy = solver.busy
  const solveError = solver.state.phase === 'error' ? solver.state.error : null

  return (
    <div className="app">
      <TopBar
        options={options}
        selectedKey={selectedKey}
        onSelect={handleSelect}
        onImport={handleImport}
        importedName={importedName}
        response={response}
        serviceOnline={serviceOnline}
        solveState={solver.state}
        waitedSec={solver.waitedSec}
        onRun={handleRun}
        onCancel={solver.cancel}
      />
      <div className="workspace">
        {request && derived ? (
          <VehicleRail
            request={request}
            response={response}
            derived={derived}
            selectedVehicleId={selectedVehicleId}
            onSelectVehicle={(id) => {
              setSelectedVehicleId(id)
              setUnloadDone(0)
              setSelectedBoxId(null)
            }}
          />
        ) : (
          <aside className="rail" />
        )}

        <main className="center">
          <div className="stage">
            <div className="stage-tabs" role="tablist" aria-label="视图">
              <button role="tab" aria-selected={view === '3d'} onClick={() => setView('3d')}>
                车厢装载
              </button>
              <button role="tab" aria-selected={view === 'map'} onClick={() => setView('map')}>
                路线示意
              </button>
            </div>
            {view === '3d' && (
              <div className="stage-actions">
                <button className="btn quiet" onClick={() => setResetKey((k) => k + 1)}>
                  重置视角
                </button>
              </div>
            )}

            {loadError ? (
              <div className="stage-message">
                <div>
                  <div className="big">案例读取失败</div>
                  <div>{loadError}</div>
                </div>
              </div>
            ) : !request || !derived ? (
              <div className="stage-message">
                <div>
                  <div className="big">正在读取案例</div>
                </div>
              </div>
            ) : solveError ? (
              <div className="stage-message">
                <div>
                  <div className="big">提交失败</div>
                  <div>{solveError.message}</div>
                  <div className="empty" style={{ marginTop: 6 }}>
                    错误码 {solveError.code}。{ERROR_HINT[solveError.code] ?? ''}输入已保留，可直接重试。
                  </div>
                  {solveError.details.length > 0 && (
                    <ul className="violations" style={{ textAlign: 'left', display: 'inline-block' }}>
                      {solveError.details.slice(0, 8).map((d, i) => (
                        <li key={i}>
                          {d.path}：{d.message}
                        </li>
                      ))}
                    </ul>
                  )}
                  <div style={{ marginTop: 10 }}>
                    <button className="btn quiet" onClick={solver.dismissError}>
                      关闭
                    </button>
                  </div>
                </div>
              </div>
            ) : busy ? (
              <div className="stage-message" aria-live="polite">
                <div>
                  <div className="big">{solver.state.phase === 'polling' && solver.state.status === 'running' ? '计算中' : '排队中'}</div>
                  <div>
                    {solver.state.phase === 'polling' ? `任务 ${solver.state.runId.slice(0, 8)}，已等待 ${solver.waitedSec} 秒` : '正在提交请求'}
                  </div>
                  {solver.waitedSec >= 75 && (
                    <div className="empty" style={{ marginTop: 6 }}>
                      等待较长，请检查求解服务状态或取消后重试。
                    </div>
                  )}
                </div>
              </div>
            ) : failed ? (
              <div className="stage-message">
                <div>
                  <div className="big">求解失败</div>
                  <div>{response?.error?.message ?? '服务返回错误。'}</div>
                  <div className="empty" style={{ marginTop: 6 }}>
                    错误码 {response?.error?.code}。页面不保留上一次的方案。
                  </div>
                </div>
              </div>
            ) : !response?.result ? (
              <div className="stage-message">
                <div>
                  <div className="big">尚无方案</div>
                  <div>
                    {importedName ? `已导入 ${importedName}：` : '当前案例：'}
                    {request.stores.length} 家门店、{request.boxes.length} 箱、{request.vehicles.length} 辆车。
                  </div>
                  <div className="empty" style={{ marginTop: 6 }}>
                    {serviceOnline ? '点击「运行求解」生成方案。' : '求解服务未连接，启动后端后刷新页面。'}
                  </div>
                </div>
              </div>
            ) : view === '3d' && vehicle ? (
              <>
                <CargoView
                  vehicle={vehicle}
                  route={route}
                  derived={derived}
                  unloadedIds={unloadedIds}
                  currentBoxId={currentBoxId}
                  selectedBoxId={selectedBoxId}
                  onSelectBox={setSelectedBoxId}
                  resetKey={resetKey}
                  highlightIds={highlightBoxIds}
                />
                {snapshot && focusedEvent && (
                  <div className="snapshot-banner">
                    正在查看修复事件 {focusedEvent.event_id} 的{repairFocus?.side === 'before' ? '修复前' : '修复后'}快照（后端已验证布局）
                  </div>
                )}
                <div className="stage-legend" aria-label="图例">
                  <span className="legend-item">
                    <span className="legend-door" /> 后门（x=0），卸货方向
                  </span>
                  <span className="legend-item">
                    <span className="legend-fragile" /> 易碎箱
                  </span>
                  <span className="legend-item">颜色 = 到站顺序</span>
                  {!route && <span className="legend-item">该车未启用，车厢为空</span>}
                </div>
                <div className="stage-note">拖动旋转 · 滚轮缩放 · 点击箱件查看</div>
              </>
            ) : (
              <>
                <RouteMap
                  request={request}
                  response={response}
                  derived={derived}
                  selectedVehicleId={selectedVehicleId}
                  onSelectVehicle={(id) => {
                    setSelectedVehicleId(id)
                    setUnloadDone(0)
                  }}
                  highlightStoreIds={highlightStoreIds}
                />
                {snapshot && focusedEvent && (
                  <div className="snapshot-banner">
                    正在查看修复事件 {focusedEvent.event_id} 的{repairFocus?.side === 'before' ? '修复前' : '修复后'}快照
                  </div>
                )}
                <div className="stage-note">平面坐标与直线连线，仅示意配送顺序，不是道路导航</div>
              </>
            )}
          </div>

          {derived && (
            <UnloadStrip route={failed || busy ? null : route} derived={derived} done={unloadDone} onChange={setUnloadDone} onFocusBox={setSelectedBoxId} />
          )}
        </main>

        {request && derived ? (
          <SidePanel
            request={request}
            response={busy ? null : response}
            derived={derived}
            selectedVehicleId={selectedVehicleId}
            selectedBoxId={selectedBoxId}
            repair={<RepairPanel response={busy ? null : response} focus={repairFocus} onFocus={setRepairFocus} />}
            assistant={
              <AssistantPanel
                request={request}
                response={busy ? null : response}
                selectedVehicleId={selectedVehicleId}
                state={assistant.s}
                onExplain={(focus, vid, q) => response && assistant.runExplain(request, response, focus, vid, q)}
                onInterpret={(ins) => assistant.runInterpret(request, ins)}
                onConfirmPatch={handleConfirmPatch}
                onDiscardPatch={assistant.clearInterpretation}
                onClearError={assistant.clearError}
                resolving={busy && pendingCompare !== null}
                solverOnline={serviceOnline === true}
              />
            }
          />
        ) : (
          <aside className="side" />
        )}
      </div>
    </div>
  )
}
