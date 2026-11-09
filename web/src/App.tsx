import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  useReactFlow,
  addEdge,
  EdgeLabelRenderer,
  Panel,
  type Connection,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import CardNode, { EditorCtx } from './CardNode'
import Drawer from './Drawer'
import { HoverCtx } from './hover'
import { CARD_W, CARD_H, bezierAt, edgePath, pathMid } from './geometry'
import { DEFAULT_STATUSES, type Doc, type FlowNode, type Group, type Status } from './types'
import {
  createProject,
  isDesktop,
  listProjects,
  loadProject,
  openPath,
  saveProject,
  writeExport,
} from './storage'
import { isImageFile, uploadFile } from './assets'
import { buildExportHtml } from './exporter'

const nodeTypes = { card: CardNode, group: GroupBox }

/** 分组框：只是背景，不参与拖动和选中 */
function GroupBox({ data }: NodeProps) {
  const d = data as any
  return (
    <div className="groupbox" style={{ background: d.color || '#EAF1FE' }}>
      <span>{d.name}</span>
    </div>
  )
}

function FlowEdge({
  id,
  source,
  target,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
  selected,
}: EdgeProps) {
  const { hover } = useContext(HoverCtx)
  const d = edgePath(sourceX, sourceY, targetX, targetY)
  const [mx, my] = pathMid(sourceX, sourceY, targetX, targetY)
  const label = (data as any)?.label as string | undefined
  const dim = !!hover && hover !== source && hover !== target

  // 箭头只在悬停/选中时出现：按终点切线算一个三角
  const tip = bezierAt(sourceX, sourceY, targetX, targetY, 1)
  const prev = bezierAt(sourceX, sourceY, targetX, targetY, 0.96)
  const vx = tip[0] - prev[0]
  const vy = tip[1] - prev[1]
  const len = Math.hypot(vx, vy) || 1
  const ux = vx / len
  const uy = vy / len
  const head = 9
  const half = 4
  const p2 = [tip[0] - ux * head - uy * half, tip[1] - uy * head + ux * half]
  const p3 = [tip[0] - ux * head + uy * half, tip[1] - uy * head - ux * half]

  return (
    <g className={dim ? 'fb-dim' : selected ? 'fb-sel' : ''}>
      <path id={id} className="react-flow__edge-path" d={d} fill="none" />
      <path
        className="react-flow__edge-interaction"
        d={d}
        fill="none"
        strokeWidth={18}
        stroke="transparent"
      />
      <polygon
        className="fb-arrow"
        points={`${tip[0]},${tip[1]} ${p2[0]},${p2[1]} ${p3[0]},${p3[1]}`}
      />
      {label ? (
        <EdgeLabelRenderer>
          <div
            className="elabel nodrag nopan"
            style={{ transform: `translate(-50%,-50%) translate(${mx}px,${my - 9}px)` }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </g>
  )
}
const edgeTypes = { fb: FlowEdge }

type Snap = { nodes: Node[]; edges: Edge[]; groups: Group[] }

function Editor() {
  const [project, setProject] = useState('')
  const [projects, setProjects] = useState<string[]>([])
  const [statuses, setStatuses] = useState<Status[]>(DEFAULT_STATUSES)
  const [nodes, setNodes, onNodesChange] = useNodesState<any>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<any>([])
  const [selId, setSelId] = useState<string | null>(null)
  const [msg, setMsg] = useState('连上 bridge.py 才能读写项目')
  const [dirty, setDirty] = useState(false)
  const [zoom, setZoom] = useState(100)
  const [hover, setHover] = useState<string | null>(null)
  const hoverCtx = useMemo(() => ({ hover, setHover }), [hover])
  const [mode, setMode] = useState<'edit' | 'view'>('edit')
  const [groups, setGroups] = useState<Group[]>([])
  const [drawerW, setDrawerW] = useState(() => Number(localStorage.getItem('fb.drawerW')) || 372)
  const [drawerFloat, setDrawerFloat] = useState(false)
  const [drawerPos, setDrawerPos] = useState({ x: Math.max(0, window.innerWidth - 440), y: 88 })
  const [newOpen, setNewOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newTpl, setNewTpl] = useState('blank')
  const [, setHistVer] = useState(0)
  const rf = useReactFlow()

  const nodesRef = useRef(nodes)
  nodesRef.current = nodes
  const edgesRef = useRef(edges)
  edgesRef.current = edges
  const statusesRef = useRef(statuses)
  statusesRef.current = statuses
  const groupsRef = useRef(groups)
  groupsRef.current = groups
  const selRef = useRef<string | null>(null)
  selRef.current = selId

  const past = useRef<string[]>([])
  const future = useRef<string[]>([])

  const snap = (): Snap => ({
    nodes: JSON.parse(JSON.stringify(nodesRef.current)),
    edges: JSON.parse(JSON.stringify(edgesRef.current)),
    groups: JSON.parse(JSON.stringify(groupsRef.current)),
  })
  const pushHistory = useCallback(() => {
    past.current.push(JSON.stringify(snap()))
    if (past.current.length > 80) past.current.shift()
    future.current = []
    setHistVer((v) => v + 1)
  }, [])
  const restore = (s: string) => {
    const d = JSON.parse(s) as Snap
    setNodes(d.nodes)
    setEdges(d.edges)
    setGroups(d.groups || [])
    setDirty(true)
  }
  const undo = useCallback(() => {
    const s = past.current.pop()
    if (!s) return
    future.current.push(JSON.stringify(snap()))
    restore(s)
    setHistVer((v) => v + 1)
  }, [])
  const redo = useCallback(() => {
    const s = future.current.pop()
    if (!s) return
    past.current.push(JSON.stringify(snap()))
    restore(s)
    setHistVer((v) => v + 1)
  }, [])

  const patch = useCallback(
    (id: string, p: Partial<FlowNode>) => {
      pushHistory()
      setNodes((ns) =>
        ns.map((n) =>
          n.id === id
            ? { ...n, data: { ...n.data, node: { ...(n.data as any).node, ...p } } }
            : n,
        ),
      )
      setDirty(true)
    },
    [pushHistory, setNodes],
  )

  const cycleState = useCallback(
    (id: string) => {
      const list = statusesRef.current
      const n = nodesRef.current.find((x) => x.id === id)
      if (!n || !list.length) return
      const cur = (n.data as any).node.state || list[0].key
      const i = Math.max(0, list.findIndex((s) => s.key === cur))
      patch(id, { state: list[(i + 1) % list.length].key })
    },
    [patch],
  )

  const ctx = useMemo(
    () => ({ statuses, mode, patch, cycleState }),
    [statuses, mode, patch, cycleState],
  )

  const openProject = useCallback(
    async (name: string) => {
      try {
        const doc = await loadProject(name)
        const st = doc.statuses?.length ? doc.statuses : DEFAULT_STATUSES
        setProject(name)
        setStatuses(st)
        setNodes(
          (doc.nodes || []).map((n) => ({
            id: n.id,
            type: 'card',
            position: { x: n.x, y: n.y },
            data: { node: n },
            style: { width: CARD_W, height: CARD_H },
          })),
        )
        setEdges(
          (doc.edges || []).map((e, i) => ({
            id: 'e' + i,
            source: e.a,
            target: e.b,
            type: 'fb',
            data: { label: e.label || '' },
          })),
        )
        past.current = []
        future.current = []
        setGroups(doc.groups || [])
        setSelId(null)
        setDirty(false)
        setMsg(`${name} · ${doc.nodes?.length || 0} 步`)
        setTimeout(() => rf.fitView({ padding: 0.25, maxZoom: 1.1 }), 80)
      } catch (e: any) {
        setMsg('读不到项目：' + (e?.message || e))
      }
    },
    [rf, setEdges, setNodes],
  )

  useEffect(() => {
    ;(async () => {
      try {
        const ps = await listProjects()
        setProjects(ps)
        const name = ps.includes('专利年费') ? '专利年费' : ps[0]
        if (name) await openProject(name)
        else setMsg('projects/ 里还没有项目')
      } catch (e: any) {
        setMsg('读不到数据：' + (e?.message || e) + '（先运行 python bridge.py）')
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 改完一会儿就自动存
  useEffect(() => {
    if (!project || !dirty) return
    const t = setTimeout(async () => {
      const doc: Doc = {
        nodes: nodesRef.current.map((n) => ({
          ...((n.data as any).node as FlowNode),
          x: n.position.x,
          y: n.position.y,
        })),
        edges: edgesRef.current.map((e) => ({
          a: e.source,
          b: e.target,
          label: ((e.data as any)?.label as string) || '',
        })),
        statuses: statusesRef.current,
        groups: groupsRef.current,
      }
      try {
        await saveProject(project, doc)
        setDirty(false)
        setMsg(
          '已保存 ' +
            new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        )
      } catch (e: any) {
        setMsg('保存失败：' + (e?.message || e))
      }
    }, 700)
    return () => clearTimeout(t)
  }, [nodes, edges, statuses, dirty, project])

  const addNode = useCallback(
    (pos?: { x: number; y: number }) => {
      pushHistory()
      const v = rf.getViewport()
      const p =
        pos ?? {
          x: (-v.x + window.innerWidth / 2) / v.zoom - CARD_W / 2,
          y: (-v.y + window.innerHeight / 2) / v.zoom - CARD_H / 2,
        }
      const x = Math.round(p.x / 10) * 10
      const y = Math.round(p.y / 10) * 10
      const id = 'n' + Math.random().toString(16).slice(2, 10)
      const node: FlowNode = {
        id,
        name: '新卡片',
        summary: '',
        x,
        y,
        state: statusesRef.current[0]?.key || 'todo',
        fields: [],
      }
      setNodes((ns) => [
        ...ns,
        {
          id,
          type: 'card',
          position: { x, y },
          data: { node, autoEdit: true },
          style: { width: CARD_W, height: CARD_H },
        },
      ])
      setSelId(id)
      setDirty(true)
    },
    [pushHistory, rf, setNodes],
  )

  const addNext = useCallback(
    (fromId: string) => {
      const src = nodesRef.current.find((n) => n.id === fromId)
      if (!src) return
      addNode({ x: src.position.x + CARD_W + 70, y: src.position.y })
    },
    [addNode],
  )

  const delSelected = useCallback(() => {
    const ns = nodesRef.current.filter((n) => n.selected)
    const es = edgesRef.current.filter((e) => e.selected)
    if (!ns.length && !es.length) return
    pushHistory()
    const dead = new Set(ns.map((n) => n.id))
    setNodes((all) => all.filter((n) => !dead.has(n.id)))
    setEdges((all) =>
      all.filter((e) => !es.includes(e) && !dead.has(e.source) && !dead.has(e.target)),
    )
    setSelId(null)
    setDirty(true)
  }, [pushHistory, setEdges, setNodes])

  const onConnect = useCallback(
    (c: Connection) => {
      if (mode !== 'edit') return
      if (!c.source || !c.target || c.source === c.target) return
      pushHistory()
      setEdges((es) =>
        addEdge(
          {
            ...c,
            id: 'e' + Math.random().toString(16).slice(2, 8),
            type: 'fb',
            data: { label: '' },
          },
          es,
        ),
      )
      setDirty(true)
    },
    [pushHistory, setEdges, mode],
  )

  const lastPane = useRef({ t: 0, x: 0, y: 0 })

  const onPaneClick = (e: React.MouseEvent) => {
    // 自己数双击：React Flow 的 pane 会吃掉原生 dblclick，detail 也不一定可靠
    ;(window as any).__pc = ((window as any).__pc || 0) + 1
    if (mode !== 'edit') {
      setSelId(null)
      return
    }
    const now = Date.now()
    const dist = Math.hypot(e.clientX - lastPane.current.x, e.clientY - lastPane.current.y)
    const dbl = now - lastPane.current.t < 400 && dist < 12
    lastPane.current = { t: now, x: e.clientX, y: e.clientY }
    if (dbl) {
      lastPane.current.t = 0
      const p = rf.screenToFlowPosition({ x: e.clientX, y: e.clientY })
      addNode({ x: p.x - CARD_W / 2, y: p.y - CARD_H / 2 })
      return
    }
    setSelId(null)
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      const typing =
        !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)
      const meta = e.ctrlKey || e.metaKey
      const k = e.key.toLowerCase()
      if (meta && k === 'z') {
        e.preventDefault()
        if (e.shiftKey) redo()
        else undo()
        return
      }
      if (meta && k === 'y') {
        e.preventDefault()
        redo()
        return
      }
      if (meta && k === 'n') {
        e.preventDefault()
        addNode()
        return
      }
      if (meta && k === 'e') {
        e.preventDefault()
        setMode((m) => (m === 'edit' ? 'view' : 'edit'))
        return
      }
      if (typing) return
      if (mode !== 'edit') {
        if (e.key === 'Escape') setSelId(null)
        return
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault()
        delSelected()
      } else if (e.key === 'Escape') {
        setSelId(null)
      } else if (e.key === 'Enter' && selRef.current) {
        e.preventDefault()
        addNext(selRef.current)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [undo, redo, addNode, addNext, delSelected, mode])

  const baseName = (rel: string) => (rel.split(/[\\/]/).pop() || rel).replace(/\.[^.]+$/, '')

  // 拖文件 / 粘截图 / 选文件 三条路都走这里
  const addFilesToNode = useCallback(
    async (nodeId: string, files: File[]) => {
      if (!files.length) return
      const cur = nodesRef.current.find((n) => n.id === nodeId)
      if (!cur) return
      const node = (cur.data as any).node as FlowNode
      const fields = (node.fields || []).slice()
      const imgs = files.filter(isImageFile)
      const others = files.filter((f) => !isImageFile(f))

      const pushTo = async (type: 'image' | 'attachment', list: File[]) => {
        if (!list.length) return
        let idx = fields.findIndex((f) => f.type === type)
        if (idx < 0) {
          fields.push({ type, label: type === 'image' ? '图片' : '附件', value: [] })
          idx = fields.length - 1
        }
        const arr: any[] = Array.isArray(fields[idx].value) ? [...fields[idx].value] : []
        for (const f of list) {
          try {
            const saved = await uploadFile(project, nodeId, f)
            if (type === 'image') arr.push(saved.rel)
            else
              arr.push({
                name: baseName(saved.rel),
                file: saved.rel,
                done: true,
                size: saved.size,
              })
          } catch (e: any) {
            setMsg('上传失败：' + (e?.message || e))
          }
        }
        fields[idx] = { ...fields[idx], value: arr }
      }

      await pushTo('image', imgs)
      await pushTo('attachment', others)
      patch(nodeId, { fields })
      setSelId(nodeId)
      setMsg(`已添加 ${files.length} 个文件`)
    },
    [patch, project],
  )

  const onDrop = (e: React.DragEvent) => {
    const files = Array.from(e.dataTransfer?.files || [])
    if (!files.length) return
    e.preventDefault()
    if (mode !== 'edit') {
      setMsg('预览模式下不能改内容，切回编辑再拖')
      return
    }
    const p = rf.screenToFlowPosition({ x: e.clientX, y: e.clientY })
    const hit = nodesRef.current.find((n) => {
      const x = n.position.x
      const y = n.position.y
      return p.x >= x && p.x <= x + CARD_W && p.y >= y && p.y <= y + CARD_H
    })
    if (!hit) {
      setMsg('把文件拖到某张卡片上')
      return
    }
    void addFilesToNode(hit.id, files)
  }

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      const files = Array.from(e.clipboardData?.files || [])
      if (!files.length) return
      const id = selRef.current
      if (!id) {
        setMsg('先点一张卡片，再粘截图')
        return
      }
      e.preventDefault()
      void addFilesToNode(id, files)
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [addFilesToNode])

  const doNewProject = async () => {
    const name = newName.trim()
    if (!name) return
    try {
      const st = statusesRef.current
      const key = st[0]?.key || 'todo'
      const doc: Doc =
        newTpl === 'blank'
          ? { nodes: [], edges: [], statuses: st, groups: [] }
          : {
              nodes: [
                { id: 's1', name: '第一步', summary: '双击卡片改内容', x: 60, y: 200, state: key, fields: [] },
                { id: 's2', name: '第二步', summary: '', x: 340, y: 200, state: key, fields: [] },
                { id: 's3', name: '第三步', summary: '', x: 620, y: 200, state: key, fields: [] },
              ],
              edges: [
                { a: 's1', b: 's2' },
                { a: 's2', b: 's3' },
              ],
              statuses: st,
              groups: [],
            }
      await createProject(name, doc)
      setProjects(await listProjects())
      await openProject(name)
      setNewOpen(false)
      setNewName('')
    } catch (e: any) {
      setMsg('新建失败：' + (e?.message || e))
    }
  }

  const doExport = async () => {
    const doc: Doc = {
      nodes: nodesRef.current.map((n) => ({
        ...((n.data as any).node as FlowNode),
        x: n.position.x,
        y: n.position.y,
      })),
      edges: edgesRef.current.map((e) => ({
        a: e.source,
        b: e.target,
        label: ((e.data as any)?.label as string) || '',
      })),
      statuses: statusesRef.current,
      groups: groupsRef.current,
    }
    try {
      setMsg('正在生成…')
      const html = await buildExportHtml(doc, project, statusesRef.current)
      const p = await writeExport(project, `${project}.html`, html)
      setMsg('已导出：' + p)
      if (isDesktop) await openPath(p)
    } catch (e: any) {
      setMsg('导出失败：' + (e?.message || e))
    }
  }

  // 分组框从卡片位置实时算出来，不单独存坐标
  const rfNodes = useMemo(() => {
    const byId = new Map(nodes.map((n) => [n.id, n]))
    const boxes = groups
      .map((g) => {
        const mem = g.members.map((id) => byId.get(id)).filter(Boolean) as any[]
        if (!mem.length) return null
        const x1 = Math.min(...mem.map((m) => m.position.x)) - 16
        const y1 = Math.min(...mem.map((m) => m.position.y)) - 34
        const x2 = Math.max(...mem.map((m) => m.position.x + CARD_W)) + 16
        const y2 = Math.max(...mem.map((m) => m.position.y + CARD_H)) + 16
        return {
          id: 'g:' + g.id,
          type: 'group',
          position: { x: x1, y: y1 },
          data: { name: g.name, color: g.color || '#EAF1FE' },
          style: { width: x2 - x1, height: y2 - y1 },
          draggable: false,
          selectable: false,
          connectable: false,
          zIndex: -1,
        } as Node
      })
      .filter(Boolean) as Node[]
    return [...boxes, ...nodes]
  }, [nodes, groups])

  const selected = nodes.filter((n) => n.selected)

  const align = (kind: 'left' | 'hcenter' | 'right' | 'top' | 'vcenter' | 'bottom') => {
    if (selected.length < 2) return
    pushHistory()
    const xs = selected.map((n) => n.position.x)
    const ys = selected.map((n) => n.position.y)
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    setNodes((ns) =>
      ns.map((n) => {
        if (!n.selected) return n
        let { x, y } = n.position
        if (kind === 'left') x = minX
        if (kind === 'right') x = maxX
        if (kind === 'hcenter') x = (minX + maxX) / 2
        if (kind === 'top') y = minY
        if (kind === 'bottom') y = maxY
        if (kind === 'vcenter') y = (minY + maxY) / 2
        return { ...n, position: { x: Math.round(x), y: Math.round(y) } }
      }),
    )
    setDirty(true)
  }

  const distribute = (axis: 'x' | 'y') => {
    if (selected.length < 3) return
    pushHistory()
    const sorted = selected
      .slice()
      .sort((a, b) => (axis === 'x' ? a.position.x - b.position.x : a.position.y - b.position.y))
    const first = axis === 'x' ? sorted[0].position.x : sorted[0].position.y
    const last = axis === 'x' ? sorted[sorted.length - 1].position.x : sorted[sorted.length - 1].position.y
    const step = (last - first) / (sorted.length - 1)
    const target = new Map(sorted.map((n, i) => [n.id, Math.round(first + step * i)]))
    setNodes((ns) =>
      ns.map((n) =>
        n.selected
          ? {
              ...n,
              position:
                axis === 'x'
                  ? { x: target.get(n.id)!, y: n.position.y }
                  : { x: n.position.x, y: target.get(n.id)! },
            }
          : n,
      ),
    )
    setDirty(true)
  }

  const groupSelected = () => {
    if (selected.length < 2) return
    const name = window.prompt('给这个分组起个名字', '分组')
    if (name === null) return
    pushHistory()
    setGroups((gs) => [
      ...gs,
      {
        id: 'g' + Math.random().toString(16).slice(2, 8),
        name: name.trim() || '分组',
        members: selected.map((n) => n.id),
        color: '#EAF1FE',
      },
    ])
    setDirty(true)
  }

  const ungroupSelected = () => {
    if (!selected.length) return
    const ids = new Set(selected.map((n) => n.id))
    pushHistory()
    setGroups((gs) => gs.filter((g) => !g.members.every((m) => ids.has(m))))
    setDirty(true)
  }

  const sel = nodes.find((n) => n.id === selId)

  return (
    <EditorCtx.Provider value={ctx}>
      <HoverCtx.Provider value={hoverCtx}>
      <div className="app">
        <div className="tb">
          <div className="title">流程盒子</div>
          <select value={project} onChange={(e) => openProject(e.target.value)}>
            {projects.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <button onClick={() => setNewOpen(true)} title="新建一个流程">
            ＋ 新建
          </button>
          <button onClick={() => addNode()} title="Ctrl+N" disabled={mode !== 'edit'}>
            ＋ 卡片
          </button>
          <div className="group">
            <button onClick={undo} title="Ctrl+Z">
              撤销
            </button>
            <button onClick={redo} title="Ctrl+Y">
              重做
            </button>
          </div>
          <div className="group">
            <button onClick={() => rf.fitView({ padding: 0.25, maxZoom: 1.1 })}>适应</button>
            <button onClick={() => rf.zoomTo(1)}>100%</button>
          </div>
          <span className="meta">{zoom}%</span>
          <span className="legend">
            {statuses.map((s) => {
              const cnt = nodes.filter(
                (x) => ((x.data as any).node.state || statuses[0]?.key) === s.key,
              ).length
              return (
                <span className="lg" key={s.key}>
                  <i style={{ background: s.color }} />
                  {s.label}
                  <b>{cnt}</b>
                </span>
              )
            })}
          </span>
          <span className="sp" />
          <div className="group">
            <button
              id="m-edit"
              className={mode === 'edit' ? 'on' : ''}
              onClick={() => setMode('edit')}
              title="Ctrl+E"
            >
              编辑
            </button>
            <button
              id="m-view"
              className={mode === 'view' ? 'on' : ''}
              onClick={() => setMode('view')}
              title="Ctrl+E"
            >
              预览
            </button>
          </div>
          <button id="m-export" onClick={doExport} title="导出一份只读网页">
            导出网页
          </button>
          <span className="meta">{dirty ? '未保存…' : msg}</span>
        </div>

        <div className="main">
          <div className="canvas" onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
            <ReactFlow
              nodes={rfNodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              onConnect={onConnect}
              nodesDraggable={mode === 'edit'}
              nodesConnectable={mode === 'edit'}
              elementsSelectable
              onNodeClick={(_, n) => setSelId(n.id)}
              onPaneClick={onPaneClick}
              onNodeDragStart={pushHistory}
              onNodeDragStop={() => setDirty(true)}
              onNodesDelete={() => setDirty(true)}
              onEdgesDelete={() => setDirty(true)}
              onMove={(_, v) => setZoom(Math.round(v.zoom * 100))}
              deleteKeyCode={null}
              minZoom={0.15}
              maxZoom={2.6}
              selectionOnDrag
              panOnDrag={[1, 2]}
              zoomOnScroll
              zoomOnPinch
              zoomOnDoubleClick={false}
              fitView
              fitViewOptions={{ padding: 0.25, maxZoom: 1.1 }}
              proOptions={{ hideAttribution: true }}
            >
              <Background id="big" variant={BackgroundVariant.Lines} gap={110} color="#e4e8ec" lineWidth={1} />
              <Background id="small" variant={BackgroundVariant.Lines} gap={22} color="#eef1f4" lineWidth={1} />
              {mode === 'edit' && selected.length >= 2 ? (
                <Panel position="top-center" className="selbar">
                  <button onClick={() => align('left')} title="左对齐">⇤</button>
                  <button onClick={() => align('hcenter')} title="水平居中">⇔</button>
                  <button onClick={() => align('right')} title="右对齐">⇥</button>
                  <span className="sep" />
                  <button onClick={() => align('top')} title="顶对齐">⇡</button>
                  <button onClick={() => align('vcenter')} title="垂直居中">⇕</button>
                  <button onClick={() => align('bottom')} title="底对齐">⇣</button>
                  <span className="sep" />
                  <button onClick={() => distribute('x')} title="水平等距">⇹</button>
                  <button onClick={() => distribute('y')} title="垂直等距">⇳</button>
                  <span className="sep" />
                  <button onClick={groupSelected} title="把选中的卡片装进一个分组框">成组</button>
                  <button onClick={ungroupSelected} title="拆掉选中卡片所在的分组">解组</button>
                  <span className="cnt">{selected.length} 张</span>
                </Panel>
              ) : null}
              <Controls showInteractive={false} position="bottom-right" />
              <MiniMap
                pannable
                zoomable
                position="bottom-left"
                maskColor="rgba(247,248,250,.75)"
                style={{ width: 140, height: 90 }}
              />
            </ReactFlow>
            <div className="hint">
              双击空白新建 · 双击卡片就地改名 · 从右侧圆点拖到另一张连线 · 滚轮缩放 · 中键拖动平移 · Ctrl+Z
              撤销
            </div>
          </div>

          {sel ? (
            <Drawer
              node={(sel.data as any).node}
              statuses={statuses}
              project={project}
              mode={mode}
              width={drawerW}
              onWidth={(w) => {
                setDrawerW(w)
                localStorage.setItem('fb.drawerW', String(w))
              }}
              float={drawerFloat}
              onToggleFloat={() => setDrawerFloat((f) => !f)}
              pos={drawerPos}
              onPos={setDrawerPos}
              onPatch={(p) => patch(sel.id, p)}
              onClose={() => setSelId(null)}
              onToast={(m) => setMsg(m)}
            />
          ) : null}
        </div>

        {newOpen ? (
          <div className="modal-mask" onClick={() => setNewOpen(false)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <h3>新建流程</h3>
              <input
                autoFocus
                className="mname"
                placeholder="流程名字，比如「差旅报销」"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void doNewProject()
                  if (e.key === 'Escape') setNewOpen(false)
                }}
              />
              <div className="mrow">
                {[
                  ['blank', '空白'],
                  ['basic', '三步示例'],
                ].map(([k, label]) => (
                  <span
                    key={k}
                    className={'chip' + (newTpl === k ? ' on' : '')}
                    onClick={() => setNewTpl(k)}
                  >
                    {label}
                  </span>
                ))}
              </div>
              <div className="mfoot">
                <button onClick={() => setNewOpen(false)}>取消</button>
                <button className="primary" onClick={doNewProject} disabled={!newName.trim()}>
                  创建
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
      </HoverCtx.Provider>
    </EditorCtx.Provider>
  )



}

export default function App() {
  return (
    <ReactFlowProvider>
      <Editor />
    </ReactFlowProvider>
  )
}
