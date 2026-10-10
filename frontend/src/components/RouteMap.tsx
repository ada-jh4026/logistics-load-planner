import { useMemo } from 'react'
import type { JobResponse, SolveRequest } from '../protocol/contract'
import type { Derived } from '../lib/derive'
import { hhmm } from '../lib/format'
import { stopColor, VEHICLE_LINE } from '../lib/palette'

interface Props {
  request: SolveRequest
  response: JobResponse | null
  derived: Derived
  selectedVehicleId: string | null
  onSelectVehicle: (id: string) => void
}

/** 平面坐标路线示意：欧氏直线连线，不是真实道路路径。 */
export function RouteMap({ request, response, derived, selectedVehicleId, onSelectVehicle }: Props) {
  const { toX, toY, gridLines, viewBox, viewH } = useMemo(() => {
    const pts = [request.depot, ...request.stores]
    const xs = pts.map((p) => p.x_km)
    const ys = pts.map((p) => p.y_km)
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    const span = Math.max(maxX - minX, maxY - minY, 1)
    const pad = span * 0.18 + 0.5
    const x0 = minX - pad
    const y0 = minY - pad
    const w = maxX - minX + pad * 2
    const h = maxY - minY + pad * 2
    const W = 1000
    const H = 1000 * (h / w)
    const scale = W / w
    const toX = (x: number) => (x - x0) * scale
    const toY = (y: number) => H - (y - y0) * scale // 北向上
    const step = span > 20 ? 5 : span > 8 ? 2 : 1
    const gridLines: { x1: number; y1: number; x2: number; y2: number; label?: string }[] = []
    for (let gx = Math.ceil(x0 / step) * step; gx <= x0 + w; gx += step) {
      gridLines.push({ x1: toX(gx), y1: 0, x2: toX(gx), y2: H, label: `${gx} km` })
    }
    for (let gy = Math.ceil(y0 / step) * step; gy <= y0 + h; gy += step) {
      gridLines.push({ x1: 0, y1: toY(gy), x2: W, y2: toY(gy) })
    }
    return { toX, toY, gridLines, viewBox: `0 0 ${W} ${H}`, viewH: H }
  }, [request])

  const routes = response?.result?.routes ?? []
  const selectedRoute = selectedVehicleId ? derived.routesByVehicle.get(selectedVehicleId) ?? null : null

  return (
    <div className="route-map">
      <svg viewBox={viewBox} preserveAspectRatio="xMidYMid meet" role="img" aria-label="路线示意图">
        <g className="grid">
          {gridLines.map((l, i) => (
            <line key={i} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} />
          ))}
          {gridLines
            .filter((l) => l.label)
            .map((l, i) => (
              <text key={`t${i}`} x={l.x1 + 6} y={viewH - 10} className="tick">
                {l.label}
              </text>
            ))}
        </g>

        {/* 非选中车辆：灰色细线；选中车辆：钢蓝实线，最后绘制以压在上层 */}
        {routes
          .filter((r) => r.vehicle_id !== selectedVehicleId)
          .map((r) => (
            <polyline
              key={r.vehicle_id}
              className="leg dim"
              points={legPoints(r.store_ids)}
              onClick={() => onSelectVehicle(r.vehicle_id)}
              style={{ cursor: 'pointer' }}
            >
              <title>
                {r.vehicle_id}：{r.store_ids.join(' → ')}
              </title>
            </polyline>
          ))}
        {selectedRoute && (
          <polyline className="leg" stroke={VEHICLE_LINE} points={legPoints(selectedRoute.store_ids)}>
            <title>
              {selectedRoute.vehicle_id}：{selectedRoute.store_ids.join(' → ')}
            </title>
          </polyline>
        )}

        {request.stores.map((s) => {
          const idx = selectedRoute ? selectedRoute.store_ids.indexOf(s.id) : -1
          const onSelected = idx >= 0
          const unassigned = derived.unassignedStoreIds.has(s.id)
          const stop = selectedRoute?.stops.find((st) => st.store_id === s.id)
          const cls = `node store ${unassigned ? 'unassigned' : ''} ${!onSelected && !unassigned ? 'dim' : ''}`
          return (
            <g key={s.id} className={cls} transform={`translate(${toX(s.x_km)} ${toY(s.y_km)})`}>
              <title>
                {s.id} · 时间窗 {hhmm(s.window_start_min)}–{hhmm(s.window_end_min)} · 服务 {s.service_min} 分钟
                {stop ? ` · 到达 ${hhmm(stop.arrival_min)}，开始 ${hhmm(stop.service_start_min)}` : ''}
                {unassigned ? ' · 未配送' : ''}
              </title>
              <circle r={onSelected ? 18 : 13} stroke={onSelected ? stopColor(idx, selectedRoute!.store_ids.length) : undefined} />
              {onSelected && (
                <text textAnchor="middle" dy="8" style={{ fontWeight: 600, fill: '#1c2733' }}>
                  {idx + 1}
                </text>
              )}
              <text x={24} dy="8">
                {s.id}
              </text>
            </g>
          )
        })}

        <g className="node depot" transform={`translate(${toX(request.depot.x_km)} ${toY(request.depot.y_km)})`}>
          <title>仓库 {request.depot.id} · {hhmm(request.depot.departure_min)} 出发</title>
          <rect x={-14} y={-14} width={28} height={28} />
          <text x={24} dy="8">
            仓库
          </text>
        </g>
      </svg>
    </div>
  )

  function legPoints(storeIds: string[]): string {
    const seq = [request.depot, ...storeIds.map((id) => derived.storesById.get(id)!).filter(Boolean), request.depot]
    return seq.map((p) => `${toX(p.x_km)},${toY(p.y_km)}`).join(' ')
  }
}
