export type Field = {
  type: string
  label: string
  value: any
  hint?: string
  /** 单选 / 多选的候选项 */
  options?: string[]
}

export type FlowNode = {
  id: string
  name: string
  summary?: string
  x: number
  y: number
  state?: string
  /** 卡片正文（Markdown）：新模型的主内容 */
  body?: string
  /** 卡片宽度（170 / 220 / 300），高度按内容自动算 */
  w?: number
  /** 老数据：字段数组，加载时会转成 body */
  fields?: Field[]
}

export type FlowEdge = { a: string; b: string; label?: string }

export type Status = { key: string; label: string; color: string }

export type Group = { id: string; name: string; members: string[]; color?: string }

export type Doc = {
  nodes: FlowNode[]
  edges: FlowEdge[]
  statuses: Status[]
  groups?: Group[]
}

export const DEFAULT_STATUSES: Status[] = [
  { key: 'todo', label: '未开始', color: '#C7CBD1' },
  { key: 'doing', label: '进行中', color: '#2563EB' },
  { key: 'done', label: '已完成', color: '#15803D' },
]
