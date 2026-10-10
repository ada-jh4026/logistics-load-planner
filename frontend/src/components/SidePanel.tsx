import type { ReactNode } from 'react'
import type { JobResponse, SolveRequest } from '../protocol/contract'
import type { Derived } from '../lib/derive'
import { METHOD_WORD, routeWeightKg, STATUS_WORD, TERMINATION_WORD } from '../lib/derive'
import { hhmm, num, pct } from '../lib/format'
import { boxVolumeMm3 } from '../lib/geometry'

interface Props {
  request: SolveRequest
  response: JobResponse | null
  derived: Derived
  selectedVehicleId: string | null
  selectedBoxId: string | null
  assistant?: ReactNode
}

export function SidePanel({ response, derived, selectedVehicleId, selectedBoxId, assistant }: Props) {
  const result = response?.result ?? null
  const m = result?.metrics ?? null
  const route = selectedVehicleId ? derived.routesByVehicle.get(selectedVehicleId) ?? null : null
  const vehicle = selectedVehicleId ? derived.vehiclesById.get(selectedVehicleId) ?? null : null
  const box = selectedBoxId ? derived.boxesById.get(selectedBoxId) ?? null : null
  const placement = box && route ? route.placements.find((p) => p.box_id === box.id) ?? null : null

  const statusClass = response?.status === 'succeeded' ? 'good' : response?.status === 'partial' ? 'partial' : response?.status === 'failed' ? 'critical' : ''

  return (
    <aside className="side" aria-label="方案详情">
      <section className="section">
        <div className="headline">
          <span className={`word ${statusClass}`}>{response ? STATUS_WORD[response.status] : '尚无方案'}</span>
          {response && (
            <span className="meta">
              {METHOD_WORD[response.method]}
              {response.termination_reason ? `，${TERMINATION_WORD[response.termination_reason] ?? response.termination_reason}` : ''}
              {response.elapsed_ms > 0 ? `，${num(response.elapsed_ms, 0)} ms` : ''}
            </span>
          )}
        </div>
        {response?.status === 'failed' && response.error && (
          <div className="error-box" style={{ marginTop: 10 }}>
            <code>{response.error.code}</code>
            <div>{response.error.message}</div>
            <div className="empty" style={{ marginTop: 4 }}>
              旧方案已清空。请重新提交求解。
            </div>
          </div>
        )}
      </section>

      {m && (
        <section className="section">
          <h2>方案指标</h2>
          <table className="kv">
            <tbody>
              <Row k="配送门店" v={`${m.served_stores} / ${m.total_stores}`} u={pct(m.completion_rate)} />
              <Row k="配送箱件" v={`${m.served_boxes} / ${m.total_boxes}`} />
              <Row k="启用车辆" v={String(m.used_vehicles)} u="辆" />
              <Row k="总里程" v={num(m.total_distance_km, 1)} u="km" />
              <Row k="总费用" v={num(m.total_cost, 1)} u="元" />
              <Row k="准时率" v={pct(m.on_time_rate)} />
              <Row k="体积利用率" v={pct(m.volume_utilization)} />
              <Row k="载重利用率" v={pct(m.weight_utilization)} />
              <Row k="卸货阻挡" v={String(m.unload_block_count)} u="处" />
            </tbody>
          </table>
          <p className="empty" style={{ marginTop: 8 }}>
            里程按平面直线距离与固定车速换算，不是真实道路测算。
          </p>
        </section>
      )}

      {result && (
        <section className="section">
          <h2>独立校验</h2>
          <div className="validation">
            <span className={`dot ${result.validation.valid ? 'good' : 'critical'}`} />
            <span>{result.validation.valid ? '方案通过独立约束校验' : `发现 ${result.validation.violations.length} 项违规`}</span>
          </div>
          {result.validation.violations.length > 0 && (
            <ul className="violations">
              {result.validation.violations.map((v, i) => (
                <li key={i}>
                  {v.code}
                  {v.vehicle_id ? ` · ${v.vehicle_id}` : ''}
                  {v.store_id ? ` · ${v.store_id}` : ''}：{v.message}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {route && vehicle && (
        <section className="section">
          <h2>
            {vehicle.id} 行程
            <span className="count">
              {vehicle.length_mm / 1000} × {vehicle.width_mm / 1000} × {vehicle.height_mm / 1000} m
            </span>
          </h2>
          <table className="kv">
            <thead>
              <tr>
                <th>门店</th>
                <td style={{ fontWeight: 400, color: 'var(--ink-2)' }}>到达</td>
                <td style={{ fontWeight: 400, color: 'var(--ink-2)' }}>开始</td>
                <td style={{ fontWeight: 400, color: 'var(--ink-2)' }}>时间窗</td>
              </tr>
            </thead>
            <tbody>
              {route.stops.map((s, i) => {
                const store = derived.storesById.get(s.store_id)
                const wait = s.service_start_min - s.arrival_min
                return (
                  <tr key={s.store_id}>
                    <th>
                      {i + 1}. {s.store_id}
                      {wait > 0.01 && <span className="unit">等 {num(wait, 0)} 分</span>}
                    </th>
                    <td>{hhmm(s.arrival_min)}</td>
                    <td>{hhmm(s.service_start_min)}</td>
                    <td>{store ? `${hhmm(store.window_start_min)}–${hhmm(store.window_end_min)}` : '—'}</td>
                  </tr>
                )
              })}
              <tr>
                <th>回仓</th>
                <td colSpan={3}>{hhmm(route.return_min)}</td>
              </tr>
            </tbody>
          </table>
          <table className="kv" style={{ marginTop: 8 }}>
            <tbody>
              <Row k="里程" v={num(route.distance_km, 1)} u="km" />
              <Row k="费用" v={`${num(vehicle.fixed_cost, 0)} + ${vehicle.cost_per_km} × ${num(route.distance_km, 1)} = ${num(route.cost, 1)}`} u="元" />
              <Row k="载重" v={`${num(routeWeightKg(route, derived.boxesById), 0)} / ${num(vehicle.max_weight_kg, 0)}`} u="kg" />
              <Row
                k="体积"
                v={pct(
                  route.box_ids.reduce((s, id) => s + boxVolumeMm3(derived.boxesById.get(id)!), 0) /
                    (vehicle.length_mm * vehicle.width_mm * vehicle.height_mm),
                )}
              />
            </tbody>
          </table>
        </section>
      )}

      {box && (
        <section className="section box-info">
          <h2>箱件 {box.id}</h2>
          <dl>
            <dt>门店</dt>
            <dd>{box.store_id}</dd>
            <dt>尺寸 长×宽×高</dt>
            <dd>
              {box.length_mm} × {box.width_mm} × {box.height_mm} mm
            </dd>
            <dt>重量</dt>
            <dd>{box.weight_kg} kg</dd>
            <dt>易碎</dt>
            <dd>{box.fragile ? '是，顶面不得承载' : '否'}</dd>
            <dt>允许水平旋转</dt>
            <dd>{box.allow_rotate_xy ? '是' : '否'}</dd>
            {placement && (
              <>
                <dt>位置 最小角 x,y,z</dt>
                <dd>
                  {placement.x_mm}, {placement.y_mm}, {placement.z_mm} mm
                </dd>
                <dt>旋转</dt>
                <dd>{placement.rotation_xy}°</dd>
              </>
            )}
          </dl>
        </section>
      )}

      {assistant}
    </aside>
  )
}

function Row({ k, v, u }: { k: string; v: string; u?: string }) {
  return (
    <tr>
      <th>{k}</th>
      <td>
        {v}
        {u && <span className="unit">{u}</span>}
      </td>
    </tr>
  )
}
