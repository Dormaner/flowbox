// 连线几何：贝塞尔 + 水平切线（Blender / Grasshopper 那种形态）
// canvas_demo.py 的 bezier_link 和 editor_qt.py 用同一套规则，三处必须同时改。

export const CARD_W = 190
export const CARD_H = 88

export type Pt = [number, number]

/** 控制点：正向平着出、平着进；回退时绕出去再兜回来 */
export function linkControls(
  sx: number,
  sy: number,
  tx: number,
  ty: number,
): { c1: Pt; c2: Pt; back: boolean } {
  const dx = tx - sx
  if (tx >= sx + 24) {
    const k = Math.max(40, Math.min(dx * 0.5, 180))
    return { c1: [sx + k, sy], c2: [tx - k, ty], back: false }
  }
  const out = Math.max(60, Math.min(Math.abs(dx) * 0.4, 140))
  const lift = ty >= sy ? 26 : -26
  return { c1: [sx + out, sy + lift], c2: [tx - out, ty + lift], back: true }
}

export function edgePath(sx: number, sy: number, tx: number, ty: number): string {
  const { c1, c2 } = linkControls(sx, sy, tx, ty)
  return `M ${sx} ${sy} C ${c1[0]} ${c1[1]}, ${c2[0]} ${c2[1]}, ${tx} ${ty}`
}

export function bezierAt(
  sx: number,
  sy: number,
  tx: number,
  ty: number,
  t: number,
): Pt {
  const { c1, c2 } = linkControls(sx, sy, tx, ty)
  const mt = 1 - t
  return [
    mt * mt * mt * sx + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t * t * t * tx,
    mt * mt * mt * sy + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t * t * t * ty,
  ]
}

/** 采样成折线（给需要点序列的地方用，比如箭头方向和 Python 侧对齐） */
export function edgeSamples(
  sx: number,
  sy: number,
  tx: number,
  ty: number,
  steps = 24,
): Pt[] {
  const out: Pt[] = []
  for (let i = 0; i <= steps; i++) out.push(bezierAt(sx, sy, tx, ty, i / steps))
  return out
}

export function pathMid(sx: number, sy: number, tx: number, ty: number): Pt {
  return bezierAt(sx, sy, tx, ty, 0.5)
}
