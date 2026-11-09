import type { FlowNode } from './types'
import { bodyOf } from './migrate'
import { mdStats } from './markdown'

/** 宽度三档：窄 / 标准 / 宽 */
export const WIDTHS = [170, 220, 300]
export const DEFAULT_W = 220

export function cardWidth(node: FlowNode): number {
  const w = Number(node.w) || DEFAULT_W
  return Math.max(150, Math.min(420, w))
}

/**
 * 高度按内容估：标题（最多 2 行）+ 摘要 1 行 + 小字标签 1 行。
 * 画布和导出都用这一个函数，保证两边长得一样。
 */
export function cardHeight(node: FlowNode): number {
  const inner = cardWidth(node) - 24
  const perLine = Math.max(6, Math.floor(inner / 13))
  const titleLen = [...String(node.name || '未命名')].length
  const tLines = Math.min(2, Math.max(1, Math.ceil(titleLen / perLine)))
  const stats = mdStats(bodyOf(node))
  const summary = String(node.summary || stats.summary || '').trim()
  const chips =
    stats.checks.total > 0 || stats.files.length > 0 || Boolean(stats.owner) || Boolean(stats.due)

  let h = 10 + tLines * 17.6
  if (summary) h += 3 + 16.2
  if (chips) h += 3 + 14.5
  h += 10 + 2
  return Math.round(Math.max(72, Math.min(220, h)))
}

export function cardSize(node: FlowNode): { w: number; h: number } {
  return { w: cardWidth(node), h: cardHeight(node) }
}
