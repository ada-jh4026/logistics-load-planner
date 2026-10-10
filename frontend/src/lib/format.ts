/** 当天零点起的分钟数 → HH:MM。内部保留精度，只在展示时取整；恰为 1440（当天结束）显示 24:00 而不是 00:00。 */
export function hhmm(min: number): string {
  const m = Math.round(min)
  if (m === 1440) return '24:00'
  const h = Math.floor(m / 60) % 24
  return `${String(h).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}

/** 时间窗文本：[0, 1440] 这种「不限」窗口显示为「全天」，其余为 HH:MM–HH:MM。 */
export function windowText(startMin: number, endMin: number): string {
  if (startMin <= 0 && endMin >= 1440) return '全天'
  return `${hhmm(startMin)}–${hhmm(endMin)}`
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

export function num(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return v.toLocaleString('zh-CN', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
}

export function minutes(v: number): string {
  const r = Math.round(v * 10) / 10
  return `${num(r, 1)} 分钟`
}
