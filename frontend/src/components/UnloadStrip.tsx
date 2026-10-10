import type { Route } from '../protocol/contract'
import type { Derived } from '../lib/derive'
import { stopColor } from '../lib/palette'

interface Props {
  route: Route | null
  derived: Derived
  /** 已完成的步数 0..n */
  done: number
  onChange: (done: number) => void
  onFocusBox: (id: string | null) => void
}

export function UnloadStrip({ route, derived, done, onChange, onFocusBox }: Props) {
  if (!route) {
    return (
      <div className="unload">
        <div className="unload-controls">
          <div className="progress">—</div>
        </div>
        <p className="empty">选择一辆已启用的车辆查看卸货步骤。</p>
      </div>
    )
  }
  const steps = route.unload_steps
  const n = steps.length
  const current = done < n ? steps[done] : null

  return (
    <div className="unload" aria-label="卸货步骤">
      <div className="unload-controls">
        <div className="progress">
          {done} / {n}
          <small>已卸</small>
        </div>
        <div className="buttons">
          <button className="btn quiet" onClick={() => onChange(0)} disabled={done === 0}>
            重置
          </button>
          <button className="btn quiet" onClick={() => onChange(Math.max(0, done - 1))} disabled={done === 0}>
            上一步
          </button>
          <button className="btn secondary" onClick={() => onChange(Math.min(n, done + 1))} disabled={done >= n}>
            下一步
          </button>
        </div>
        <small className="empty">装货按卸货逆序进行</small>
      </div>
      <div className="steps" role="list">
        {steps.map((s, i) => {
          const box = derived.boxesById.get(s.box_id)
          const idx = route.store_ids.indexOf(s.store_id)
          const cls = `step ${i < done ? 'done' : ''} ${current && current.step === s.step ? 'current' : ''}`
          return (
            <button
              key={s.step}
              role="listitem"
              className={cls}
              onClick={() => {
                onChange(i)
                onFocusBox(s.box_id)
              }}
              title={box ? `${box.length_mm}×${box.width_mm}×${box.height_mm} mm，${box.weight_kg} kg` : s.box_id}
            >
              <span className="n">{s.step}</span>
              <span className="what">
                <span className="swatch" style={{ background: stopColor(idx, route.store_ids.length), display: 'inline-block', marginRight: 6, verticalAlign: '-1px' }} />
                卸 {s.box_id}
                {box?.fragile && <span className="fragile-mark">易碎</span>}
              </span>
              <span className="where">
                第 {idx + 1} 站 {s.store_id}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
