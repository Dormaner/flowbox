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
  /** 卡片宽度（默认 220，可拖边角自由改） */
  w?: number
  /** 卡片高度（不设 = 按内容自适应） */
  h?: number
  /** 容器卡：可以把别的卡片装进来，一起折叠/移动 */
  kind?: 'step' | 'container'
  /** 所属容器 id（拖进容器里自动设置） */
  parent?: string
  /** 容器是否折叠（折叠时子卡不显示） */
  collapsed?: boolean
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
