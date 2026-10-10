// 业务坐标（CONTRACT/DECISIONS D05）：后门 x=0，x 向车头，y 沿车宽，z 向上，单位 mm，位置为箱件最小角。
// Three.js 场景：Y 轴向上，单位 m。统一在这里转换，组件里不再各写一套。
import type { Box, Placement, Vehicle } from '../protocol/contract'

export const MM_PER_M = 1000

/** 旋转 90 度交换长宽；高度不变。 */
export function rotatedDims(box: Box, rotation: 0 | 90): [number, number, number] {
  return rotation === 90
    ? [box.width_mm, box.length_mm, box.height_mm]
    : [box.length_mm, box.width_mm, box.height_mm]
}

export interface SceneBox {
  box: Box
  placement: Placement
  /** 场景中心点（m），Y 向上 */
  center: [number, number, number]
  /** 场景尺寸（m），顺序对应场景 x/y/z，即业务 L/H/W */
  size: [number, number, number]
}

/** 业务 (x,y,z) mm → 场景 (x, z, y) m */
export function toScene(x_mm: number, y_mm: number, z_mm: number): [number, number, number] {
  return [x_mm / MM_PER_M, z_mm / MM_PER_M, y_mm / MM_PER_M]
}

export function placeBox(box: Box, placement: Placement): SceneBox {
  const [L, W, H] = rotatedDims(box, placement.rotation_xy)
  const center = toScene(placement.x_mm + L / 2, placement.y_mm + W / 2, placement.z_mm + H / 2)
  return { box, placement, center, size: [L / MM_PER_M, H / MM_PER_M, W / MM_PER_M] }
}

/** 车厢在场景中的尺寸与中心（m）。 */
export function vehicleScene(v: Vehicle) {
  const size: [number, number, number] = [v.length_mm / MM_PER_M, v.height_mm / MM_PER_M, v.width_mm / MM_PER_M]
  const center: [number, number, number] = [size[0] / 2, size[1] / 2, size[2] / 2]
  return { size, center }
}

export function boxVolumeMm3(b: Box): number {
  return b.length_mm * b.width_mm * b.height_mm
}
