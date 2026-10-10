/** 当天零点起的分钟数 → HH:MM。内部保留精度，只在展示时取整。 */
export function hhmm(min: number): string {
  const m = Math.round(min)
  const h = Math.floor(m / 60) % 24
  return `${String(h).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
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
