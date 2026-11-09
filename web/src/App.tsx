import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
  type Connection,
  type Edge,
  type EdgeProps,
  type Node,
} from '@xyflow/react'
import CardNode, { EditorCtx } from './CardNode'
import Drawer from './Drawer'
import { CARD_W, CARD_H, edgePath, edgePoints, pathMid } from './geometry'
import { DEFAULT_STATUSES, type Doc, type FlowNode, type Status } from './types'
import { listProjects, loadProject, saveProject } from './storage'

const nodeTypes = { card: CardNode }

function FlowEdge({ id, sourceX, sourceY, targetX, targetY, data }: EdgeProps) {
  const pts = edgePoints(sourceX, sourceY, targetX, targetY)
  const d = edgePath(sourceX, sourceY, targetX, targetY)
  const [mx, my] = pathMid(pts)
  const label = (data as any)?.label as string | undefined
  return (
    <>
      <path id={id} className="react-flow__edge-path" d={d} fill="none" markerEnd="url(#fb-arrow)" />
      {label ? (
        <EdgeLabelRenderer>
          <div
            className="elabel nodrag nopan"
            style={{ transform: `translate(-50%,-50%) translate(${mx}px,${my - 10}px)` }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  )
}
const edgeTypes = { fb: FlowEdge }

function ArrowDefs() {
  return (
    <svg style={{ position: 'absolute', width: 0, height: 0 }} aria-hidden>
      <defs>
        <marker
          id="fb-arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M0,0 L10,5 L0,10 z" fill="#3C4149" />
        </marker>
      </defs>
    </svg>
  )
}

type Snap = { nodes: Node[]; edges: Edge[] }

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
  const [, setHistVer] = useState(0)
  const rf = useReactFlow()

  const nodesRef = useRef(nodes)
  nodesRef.current = nodes
  const edgesRef = useRef(edges)
  edgesRef.current = edges
  const statusesRef = useRef(statuses)
  statusesRef.current = statuses
  const selRef = useRef<string | null>(null)
  selRef.current = selId

  const past = useRef<string[]>([])
  const future = useRef<string[]>([])

  const snap = (): Snap => ({
    nodes: JSON.parse(JSON.stringify(nodesRef.current)),
    edges: JSON.parse(JSON.stringify(edgesRef.current)),
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

  const ctx = useMemo(() => ({ statuses, patch, cycleState }), [statuses, patch, cycleState])

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
        groups: [],
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
    [pushHistory, setEdges],
  )

  const lastPane = useRef({ t: 0, x: 0, y: 0 })

  const onPaneClick = (e: React.MouseEvent) => {
    // 自己数双击：React Flow 的 pane 会吃掉原生 dblclick，detail 也不一定可靠
    ;(window as any).__pc = ((window as any).__pc || 0) + 1
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
      if (typing) return
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
  }, [undo, redo, addNode, addNext, delSelected])

  const sel = nodes.find((n) => n.id === selId)

  return (
    <EditorCtx.Provider value={ctx}>
      <ArrowDefs />
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
          <button onClick={() => addNode()} title="Ctrl+N">
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
          <span className="meta">{dirty ? '未保存…' : msg}</span>
        </div>

        <div className="main">
          <div className="canvas">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              onConnect={onConnect}
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
              <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#d9dee5" />
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
              onPatch={(p) => patch(sel.id, p)}
              onClose={() => setSelId(null)}
            />
          ) : null}
        </div>
      </div>
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
