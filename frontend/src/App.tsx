import { useEffect, useMemo, useState } from 'react'
import type { JobResponse, SolveRequest } from './protocol/contract'
import { SCENARIOS } from './lib/mock'
import { derive } from './lib/derive'
import { TopBar } from './components/TopBar'
import { VehicleRail } from './components/VehicleRail'
import { CargoView } from './components/CargoView'
import { RouteMap } from './components/RouteMap'
import { UnloadStrip } from './components/UnloadStrip'
import { SidePanel } from './components/SidePanel'

type View = '3d' | 'map'

export default function App() {
  const [scenarioId, setScenarioId] = useState(SCENARIOS[0].id)
  const scenario = SCENARIOS.find((s) => s.id === scenarioId) ?? SCENARIOS[0]
  const [request, setRequest] = useState<SolveRequest>(scenario.request)
  const [response, setResponse] = useState<JobResponse | null>(scenario.response)
  const [importedName, setImportedName] = useState<string | null>(null)
  const [view, setView] = useState<View>('3d')
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null)
  const [selectedBoxId, setSelectedBoxId] = useState<string | null>(null)
  const [unloadDone, setUnloadDone] = useState(0)
  const [resetKey, setResetKey] = useState(0)

  // 切换案例：清空旧结果，不让旧数字冒充新结果。
  useEffect(() => {
    if (importedName) return
    setRequest(scenario.request)
    setResponse(scenario.response)
    setSelectedBoxId(null)
    setUnloadDone(0)
  }, [scenario, importedName])

  function handleScenarioChange(id: string) {
    if (id === '__imported__') return
    setImportedName(null)
    setScenarioId(id)
  }

  function handleImport(req: SolveRequest, name: string) {
    // 导入的是请求，还没有方案；旧样例的响应不能留在页面上。
    setImportedName(name)
    setRequest(req)
    setResponse(null)
    setSelectedBoxId(null)
    setUnloadDone(0)
  }

  const derived = useMemo(() => derive(request, response), [request, response])

  // 默认选中第一辆启用的车；没有方案时选第一辆车。
  useEffect(() => {
    const firstUsed = request.vehicles.find((v) => derived.routesByVehicle.has(v.id)) ?? request.vehicles[0]
    setSelectedVehicleId(firstUsed?.id ?? null)
    setUnloadDone(0)
    setSelectedBoxId(null)
  }, [request, derived])

  const vehicle = selectedVehicleId ? derived.vehiclesById.get(selectedVehicleId) ?? null : null
  const route = selectedVehicleId ? derived.routesByVehicle.get(selectedVehicleId) ?? null : null

  const unloadedIds = useMemo(() => {
    const s = new Set<string>()
    route?.unload_steps.slice(0, unloadDone).forEach((st) => s.add(st.box_id))
    return s
  }, [route, unloadDone])
  const currentBoxId = route && unloadDone < route.unload_steps.length ? route.unload_steps[unloadDone].box_id : null

  const failed = response?.status === 'failed'

  return (
    <div className="app">
      <TopBar
        scenarios={SCENARIOS}
        scenarioId={scenarioId}
        onScenarioChange={handleScenarioChange}
        onImport={handleImport}
        importedName={importedName}
        response={response}
        onRun={() => {}}
        runEnabled={false}
        runHint="求解服务接口（B13）完成后启用；当前展示的是样例数据。"
      />
      <div className="workspace">
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

            {failed ? (
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
                  <div>{importedName ? `已导入 ${importedName}：${request.stores.length} 家门店、${request.boxes.length} 箱、${request.vehicles.length} 辆车。` : '选择案例并运行求解。'}</div>
                  <div className="empty" style={{ marginTop: 6 }}>
                    求解服务接入后，点击「运行求解」生成方案。
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
                />
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
                />
                <div className="stage-note">平面坐标与直线连线，仅示意配送顺序，不是道路导航</div>
              </>
            )}
          </div>

          <UnloadStrip
            route={failed ? null : route}
            derived={derived}
            done={unloadDone}
            onChange={setUnloadDone}
            onFocusBox={setSelectedBoxId}
          />
        </main>

        <SidePanel
          request={request}
          response={response}
          derived={derived}
          selectedVehicleId={selectedVehicleId}
          selectedBoxId={selectedBoxId}
        />
      </div>
    </div>
  )
}
