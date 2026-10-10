import type { JobResponse, SolveRequest } from '../protocol/contract'
import { REASON_LABEL } from '../protocol/contract'
import type { Derived } from '../lib/derive'
import { routeWeightKg } from '../lib/derive'
import { hhmm, num } from '../lib/format'
import { stopColor } from '../lib/palette'

interface Props {
  request: SolveRequest
  response: JobResponse | null
  derived: Derived
  selectedVehicleId: string | null
  onSelectVehicle: (id: string) => void
}

export function VehicleRail({ request, response, derived, selectedVehicleId, onSelectVehicle }: Props) {
  const unassigned = response?.result?.unassigned ?? []
  const used = request.vehicles.filter((v) => derived.routesByVehicle.has(v.id))

  return (
    <aside className="rail" aria-label="车辆与门店">
      <section className="section">
        <h2>
          车辆
          <span className="count">
            {used.length} / {request.vehicles.length} 辆启用
          </span>
        </h2>
        <div className="vehicle-list" role="listbox" aria-label="车辆列表">
          {request.vehicles.map((v) => {
            const route = derived.routesByVehicle.get(v.id)
            const selected = v.id === selectedVehicleId
            const weight = route ? routeWeightKg(route, derived.boxesById) : 0
            return (
              <button
                key={v.id}
                role="option"
                aria-selected={selected}
                className={`vehicle ${selected ? 'selected' : ''} ${route ? '' : 'unused'}`}
                onClick={() => onSelectVehicle(v.id)}
              >
                <span className="vid">{v.id}</span>
                {route ? (
                  <>
                    <span className="line1">
                      {route.store_ids.length} 站，{route.box_ids.length} 箱，{num(route.cost, 1)} 元
                    </span>
                    <span className="line2">
                      {hhmm(request.depot.departure_min)} 出发，{hhmm(route.return_min)} 回仓，{num(route.distance_km, 1)} km，载重 {num(weight, 0)} / {num(v.max_weight_kg, 0)} kg
                    </span>
                    <span className="stop-chips" style={{ gridColumn: '1 / -1' }}>
                      {route.store_ids.map((sid, i) => (
                        <span className="chip" key={sid}>
                          <span className="swatch" style={{ background: stopColor(i, route.store_ids.length) }} />
                          {i + 1}. {sid}
                        </span>
                      ))}
                    </span>
                  </>
                ) : (
                  <>
                    <span className="line1">未启用</span>
                    <span className="line2">
                      {v.length_mm / 1000} × {v.width_mm / 1000} × {v.height_mm / 1000} m，载重 {num(v.max_weight_kg, 0)} kg
                    </span>
                  </>
                )}
              </button>
            )
          })}
        </div>
      </section>

      <section className="section">
        <h2>
          未配送门店
          <span className="count">
            {unassigned.length} / {request.stores.length}
          </span>
        </h2>
        {unassigned.length === 0 ? (
          <p className="empty">{response?.result ? '所有门店都已安排配送。' : '尚无方案。'}</p>
        ) : (
          <div className="unassigned">
            {unassigned.map((u) => (
              <div className="unassigned-item" key={u.store_id}>
                <strong>{u.store_id}</strong>，{u.box_ids.length} 箱：{REASON_LABEL[u.reason_code]}
                <p>{u.message}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="section">
        <h2>
          案例
          <span className="count">{request.case_id}</span>
        </h2>
        <table className="kv">
          <tbody>
            <tr>
              <th>门店</th>
              <td>{request.stores.length}</td>
            </tr>
            <tr>
              <th>箱件</th>
              <td>{request.boxes.length}</td>
            </tr>
            <tr>
              <th>仓库出发</th>
              <td>{hhmm(request.depot.departure_min)}</td>
            </tr>
            <tr>
              <th>车速假设</th>
              <td>
                {request.options.speed_kmph}
                <span className="unit">km/h</span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </aside>
  )
}
