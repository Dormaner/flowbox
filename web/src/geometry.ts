// 连线几何：跟 canvas_demo.py / editor_qt.py / html_export.py 是同一套规则
// （右边出、左边进，直角 + 13 圆角，往回连的线绕一圈）。

export const CARD_W = 190
export const CARD_H = 88

export type Pt = [number, number]

export function edgePoints(sx: number, sy: number, tx: number, ty: number): Pt[] {
  const dx = tx - sx
  const dy = ty - sy
  if (Math.abs(dy) < 3 || (Math.abs(dy) <= 26 && dx >= 36)) {
    return [[sx, sy], [tx, ty]]
  }
  if (dx >= 36) {
    const mx = sx + Math.max(30, Math.min(dx * 0.5, 150))
    return [[sx, sy], [mx, sy], [mx, ty], [tx, ty]]
  }
  const out = 34
  const ydet = ty >= sy - 4
    ? Math.max(sy, ty) + CARD_H / 2 + 22
    : Math.min(sy, ty) - CARD_H / 2 - 22
  return [
    [sx, sy], [sx + out, sy], [sx + out, ydet],
    [tx - out, ydet], [tx - out, ty], [tx, ty],
  ]
}

export function roundPath(pts: Pt[], r = 13): string {
  if (pts.length < 2) return ''
  let d = `M ${pts[0][0]} ${pts[0][1]}`
  for (let i = 1; i < pts.length - 1; i++) {
    const [p0, p1, p2] = [pts[i - 1], pts[i], pts[i + 1]]
    const v1 = [p1[0] - p0[0], p1[1] - p0[1]]
    const v2 = [p2[0] - p1[0], p2[1] - p1[1]]
    const l1 = Math.hypot(v1[0], v1[1]) || 1
    const l2 = Math.hypot(v2[0], v2[1]) || 1
    const r1 = Math.min(r, l1 / 2)
    const r2 = Math.min(r, l2 / 2)
    const a: Pt = [p1[0] - (v1[0] / l1) * r1, p1[1] - (v1[1] / l1) * r1]
    const b: Pt = [p1[0] + (v2[0] / l2) * r2, p1[1] + (v2[1] / l2) * r2]
    d += ` L ${a[0]} ${a[1]} Q ${p1[0]} ${p1[1]} ${b[0]} ${b[1]}`
  }
  const last = pts[pts.length - 1]
  d += ` L ${last[0]} ${last[1]}`
  return d
}

export function edgePath(sx: number, sy: number, tx: number, ty: number): string {
  return roundPath(edgePoints(sx, sy, tx, ty))
}

/** 路径中点，用来放连线标签 */
export function pathMid(pts: Pt[]): Pt {
  if (pts.length < 2) return [0, 0]
  let total = 0
  const segs: { d: number; i: number }[] = []
  for (let i = 0; i < pts.length - 1; i++) {
    const d = Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
    segs.push({ d, i })
    total += d
  }
  let acc = 0
  for (const s of segs) {
    if (acc + s.d >= total / 2) {
      const t = s.d <= 1e-9 ? 0 : (total / 2 - acc) / s.d
      return [
        pts[s.i][0] + (pts[s.i + 1][0] - pts[s.i][0]) * t,
        pts[s.i][1] + (pts[s.i + 1][1] - pts[s.i][1]) * t,
      ]
    }
    acc += s.d
  }
  return pts[0]
}
