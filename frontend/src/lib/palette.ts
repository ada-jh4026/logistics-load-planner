// 箱件按「到站顺序」着色。≤8 站用固定顺序的分类色（已用 validate_palette 校验：浅色面全部通过，
// 三个槽位对比度 <3:1，页面以图例文字与门店标签作为补充编码）；>8 站退化为单色蓝的深浅序列。
export const STOP_CATEGORICAL = [
  '#2a78d6',
  '#eb6834',
  '#1baf7a',
  '#eda100',
  '#e87ba4',
  '#008300',
  '#4a3aa7',
  '#e34948',
] as const

const BLUE_RAMP = ['#86b6ef', '#6da7ec', '#5598e7', '#3987e5', '#2a78d6', '#256abf', '#1c5cab', '#184f95', '#104281', '#0d366b']

export function stopColor(stopIndex: number, stopCount: number): string {
  if (stopIndex < 0) return '#9aa5b1'
  if (stopCount <= STOP_CATEGORICAL.length) return STOP_CATEGORICAL[stopIndex]
  const t = stopCount <= 1 ? 0 : stopIndex / (stopCount - 1)
  return BLUE_RAMP[Math.round(t * (BLUE_RAMP.length - 1))]
}

/** 路线示意图里每辆车一条线：选中车用车辆色，其它车退为灰色（强调式）。 */
export const VEHICLE_LINE = '#2f5d8a'
