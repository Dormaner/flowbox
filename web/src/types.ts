export type Field = {
  type: string
  label: string
  value: any
  hint?: string
}

export type FlowNode = {
  id: string
  name: string
  summary?: string
  x: number
  y: number
  state?: string
  fields?: Field[]
}

export type FlowEdge = { a: string; b: string; label?: string }

export type Status = { key: string; label: string; color: string }

export type Doc = {
  nodes: FlowNode[]
  edges: FlowEdge[]
  statuses: Status[]
  groups?: { id: string; name: string; members: string[]; color?: string }[]
}

export const DEFAULT_STATUSES: Status[] = [
  { key: 'todo', label: '未开始', color: '#C7CBD1' },
  { key: 'doing', label: '进行中', color: '#2563EB' },
  { key: 'done', label: '已完成', color: '#15803D' },
]
