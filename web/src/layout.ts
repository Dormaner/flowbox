import type { FlowNode } from './types'
import { bodyOf } from './migrate'
import { mdStats } from './markdown'

/** 卡片默认宽度；高度不设时按内容算 */
export const DEFAULT_W = 220
export const DEFAULT_H = 88
export const MIN_W = 150
export const MIN_H = 56
export const MAX_W = 900
export const MAX_H = 900

export function cardWidth(node: FlowNode): number {
  const w = Number(node.w) || DEFAULT_W
  return Math.max(MIN_W, Math.min(MAX_W, w))
}

/**
 * 高度：用户拖过就用用户的；没拖过按内容估
 * （标题最多 2 行 + 摘要 1 行 + 小字标签 1 行）
 * 画布和导出都用这一个函数，保证两边长得一样。
 */
export function cardHeight(node: FlowNode): number {
  if (Number(node.h) > 0) return Math.max(MIN_H, Math.min(MAX_H, Number(node.h)))

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
