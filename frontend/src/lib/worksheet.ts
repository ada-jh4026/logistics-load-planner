// 现场装卸作业单：按车生成可打印 HTML。只用响应里的 unload_steps / placements 与请求里的箱件信息，不做任何推算。
import type { Route, SolveRequest } from '../protocol/contract'
import type { Derived } from './derive'
import { hhmm, windowText } from './format'

function esc(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!)
}

export interface WorksheetInput {
  request: SolveRequest
  route: Route
  derived: Derived
  /** 3D 车厢快照（dataURL），可选 */
  snapshot?: string | null
  runId: string
  isMock: boolean
}

export function buildWorksheetHtml({ request, route, derived, snapshot, runId, isMock }: WorksheetInput): string {
  const vehicle = derived.vehiclesById.get(route.vehicle_id)!
  const stops = route.stops
  const unloadRows = route.unload_steps
    .map((st) => {
      const b = derived.boxesById.get(st.box_id)!
      const p = route.placements.find((x) => x.box_id === st.box_id)
      const stopIdx = route.store_ids.indexOf(st.store_id) + 1
      return `<tr>
        <td class="n">${st.step}</td>
        <td>${stopIdx}. ${esc(st.store_id)}</td>
        <td class="id">${esc(b.id)}</td>
        <td>${b.length_mm} × ${b.width_mm} × ${b.height_mm}</td>
        <td class="n">${b.weight_kg}</td>
        <td>${b.fragile ? '<span class="frag">易碎</span>' : ''}</td>
        <td class="pos">${p ? `${p.x_mm}, ${p.y_mm}, ${p.z_mm}${p.rotation_xy ? '，横放 90°' : ''}` : '—'}</td>
        <td class="chk">☐</td>
      </tr>`
    })
    .join('')
  const loadRows = [...route.unload_steps]
    .reverse()
    .map((st, i) => {
      const b = derived.boxesById.get(st.box_id)!
      const p = route.placements.find((x) => x.box_id === st.box_id)
      return `<tr><td class="n">${i + 1}</td><td class="id">${esc(b.id)}</td><td>${esc(st.store_id)}</td><td class="pos">${p ? `距后门 ${(p.x_mm / 1000).toFixed(2)} m，离左壁 ${(p.y_mm / 1000).toFixed(2)} m，离地 ${(p.z_mm / 1000).toFixed(2)} m` : '—'}</td><td>${b.fragile ? '易碎，顶面不得承载' : ''}</td><td class="chk">☐</td></tr>`
    })
    .join('')
  const stopRows = stops
    .map((s, i) => {
      const store = derived.storesById.get(s.store_id)
      const n = route.unload_steps.filter((st) => st.store_id === s.store_id).length
      return `<tr><td class="n">${i + 1}</td><td>${esc(s.store_id)}</td><td>${hhmm(s.arrival_min)}</td><td>${store ? windowText(store.window_start_min, store.window_end_min) : '—'}</td><td class="n">${n}</td></tr>`
    })
    .join('')
  const weight = route.box_ids.reduce((s, id) => s + (derived.boxesById.get(id)?.weight_kg ?? 0), 0)

  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>装卸作业单 ${esc(route.vehicle_id)} · ${esc(request.case_id)}</title>
<style>
  @page { size: A4; margin: 14mm; }
  body { font: 12px/1.45 "Microsoft YaHei", "PingFang SC", sans-serif; color: #1c2733; margin: 0; }
  h1 { font-size: 18px; margin: 0 0 2px; }
  .meta { color: #4f5b68; margin-bottom: 10px; }
  .stripe { height: 6px; background: repeating-linear-gradient(135deg, #f2b600 0 8px, #1c1c1c 8px 16px); margin: 0 0 10px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 10px; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 12px; }
  th, td { border: 1px solid #b9c2cc; padding: 4px 6px; text-align: left; vertical-align: top; }
  th { background: #eef1f4; font-weight: 600; }
  td.n { text-align: right; width: 2.2em; }
  td.id { font-weight: 600; }
  td.pos { color: #4f5b68; }
  td.chk { text-align: center; width: 2em; font-size: 14px; }
  .frag { color: #d03b3b; font-weight: 600; }
  h2 { font-size: 14px; margin: 12px 0 6px; }
  .rules { margin: 0; padding-left: 18px; color: #4f5b68; }
  .snap { max-width: 100%; border: 1px solid #d7dde4; }
  .note { color: #7b8794; font-size: 11px; margin-top: 10px; }
  .sig { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 14px; }
  .sig div { border-top: 1px solid #1c2733; padding-top: 4px; }
  @media print { .noprint { display: none; } }
</style></head><body>
<div class="noprint" style="margin-bottom:10px"><button onclick="window.print()">打印</button></div>
<div class="stripe"></div>
<h1>现场装卸作业单 · 车辆 ${esc(route.vehicle_id)}</h1>
<div class="meta">案例 ${esc(request.case_id)} · 运行 ${esc(runId)} · 车厢 ${vehicle.length_mm / 1000} × ${vehicle.width_mm / 1000} × ${vehicle.height_mm / 1000} m，额定 ${vehicle.max_weight_kg} kg · 本车 ${route.box_ids.length} 箱 ${weight} kg · ${hhmm(request.depot.departure_min)} 出发，${hhmm(route.return_min)} 回仓${isMock ? ' · <b>演示数据</b>' : ''}</div>
<div class="grid">
  <div>
    <h2>配送顺序</h2>
    <table><thead><tr><th>#</th><th>门店</th><th>预计到达</th><th>收货时间窗</th><th>卸箱数</th></tr></thead><tbody>${stopRows}</tbody></table>
    <h2>作业规则</h2>
    <ul class="rules">
      <li>后门为坐标原点，箱件沿后门方向水平抽出，不得穿过其他箱件。</li>
      <li>每站卸完全部箱件再前往下一站；先取上层箱，再取被它压住的底箱。</li>
      <li>易碎箱轻拿轻放，顶面不得承载。</li>
      <li>装货按「装货顺序」表从空车起逐件放入，最后卸的最先装、靠车头。</li>
    </ul>
  </div>
  <div>${snapshot ? `<h2>车厢装载示意（后门在黄黑条一侧）</h2><img class="snap" src="${snapshot}" alt="车厢装载示意">` : ''}</div>
</div>
<h2>卸货顺序（到站后按此逐件取出）</h2>
<table><thead><tr><th>步</th><th>门店</th><th>箱件</th><th>长 × 宽 × 高 (mm)</th><th>重 (kg)</th><th>备注</th><th>位置 x, y, z (mm)</th><th>完成</th></tr></thead><tbody>${unloadRows}</tbody></table>
<h2>装货顺序（出发前，卸货的逆序）</h2>
<table><thead><tr><th>步</th><th>箱件</th><th>门店</th><th>放置位置</th><th>备注</th><th>完成</th></tr></thead><tbody>${loadRows}</tbody></table>
<div class="sig"><div>装车员</div><div>司机</div><div>复核</div></div>
<p class="note">位置为箱件最小角相对后门左下角的坐标；布局来自求解服务并经独立校验器重算承托、碰撞与卸货路径。本单由系统生成，现场以实际货物为准。</p>
</body></html>`
}

/** 在新窗口打开作业单（Blob URL，不依赖 document.write）。弹窗被拦截时返回 false。 */
export function openWorksheet(html: string): boolean {
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }))
  const w = window.open(url, '_blank')
  if (!w) {
    URL.revokeObjectURL(url)
    return false
  }
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
  return true
}
