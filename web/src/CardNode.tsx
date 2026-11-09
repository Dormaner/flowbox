import { createContext, memo, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Handle, NodeResizer, Position, type NodeProps } from '@xyflow/react'
import { HoverCtx } from './hover'
import { bodyOf } from './migrate'
import { mdStats } from './markdown'
import { MAX_H, MAX_W, MIN_H, MIN_W } from './layout'
import type { FlowNode, Status } from './types'

type Ctx = {
  statuses: Status[]
  mode: 'edit' | 'view'
  patch: (id: string, patch: Partial<FlowNode>) => void
  cycleState: (id: string) => void
  resize: (id: string, w: number, h: number) => void
  toggleCollapse: (id: string) => void
  focusOn: (id: string) => void
  childCount: (id: string) => number
  dragContainer: (id: string, e: React.PointerEvent) => void
}

export const EditorCtx = createContext<Ctx>({
  statuses: [],
  mode: 'edit',
  patch: () => {},
  cycleState: () => {},
  resize: () => {},
  toggleCollapse: () => {},
  focusOn: () => {},
  childCount: () => 0,
  dragContainer: () => {},
})

// 新建卡片只自动进一次改名，撤销 / 重做时不要又弹出来
const autoEdited = new Set<string>()

function CardNodeInner({ id, data, selected }: NodeProps) {
  const n = (data as any).node as FlowNode
  const ctx = useContext(EditorCtx)
  const { setHover } = useContext(HoverCtx)
  const [editing, setEditing] = useState<null | 'title' | 'sum'>(null)
  const [draft, setDraft] = useState('')
  const taRef = useRef<HTMLTextAreaElement>(null)

  const st = ctx.statuses.find((s) => s.key === (n.state || ctx.statuses[0]?.key))
  const color = st?.color || '#C7CBD1'
  const stats = mdStats(bodyOf(n))
  const summary = (n.summary || stats.summary || '').replace(/\s+/g, ' ').trim()
  const chips: string[] = []
  if (stats.checks.total) chips.push(`${stats.checks.done}/${stats.checks.total} 材料`)
  if (stats.files.length) chips.push(`📎 ${stats.files.length}`)
  if (stats.owner) chips.push(stats.owner)
  if (stats.due) chips.push(stats.due)

  useEffect(() => {
    if ((data as any).autoEdit && !autoEdited.has(id)) {
      autoEdited.add(id)
      setDraft(n.name || '')
      setEditing('title')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useLayoutEffect(() => {
    if (editing && taRef.current) {
      taRef.current.focus()
      taRef.current.select()
    }
  }, [editing])

  const start = (which: 'title' | 'sum') => (e: React.MouseEvent) => {
    e.stopPropagation()
    setDraft(which === 'title' ? n.name || '' : n.summary || '')
    setEditing(which)
  }

  const commit = () => {
    if (!editing) return
    if (editing === 'title') ctx.patch(id, { name: draft.trim() || '未命名' })
    else ctx.patch(id, { summary: draft })
    setEditing(null)
  }

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && editing === 'title') {
      e.preventDefault()
      commit()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setEditing(null)
    } else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      commit()
    }
  }

  if (n.kind === 'container') {
    const count = Number((data as any).kids ?? ctx.childCount(id))
    return (
      <>
        <NodeResizer
          isVisible={!!selected}
          minWidth={MIN_W}
          minHeight={MIN_H}
          maxWidth={MAX_W}
          maxHeight={MAX_H}
          lineClassName="nl"
          handleClassName="nh"
          onResizeEnd={(_e, p) => ctx.resize(id, p.width, p.height)}
        />
        <div
          className={`card cont nodrag${selected ? ' sel' : ''}${n.collapsed ? ' folded' : ''}`}
          onMouseEnter={() => setHover(id)}
          onMouseLeave={() => setHover(null)}
          onPointerDown={(e) => ctx.dragContainer(id, e)}
        >
          <div className="chead">
            <span
              className="cttl"
              onDoubleClick={(e) => {
                e.stopPropagation()
                const v = window.prompt('分组名字', n.name || '新分组')
                if (v !== null) ctx.patch(id, { name: v.trim() || '新分组' })
              }}
              title="双击改名"
            >
              {n.name || '新分组'}
            </span>
            <span className="ccnt">{count} 步</span>
            <button
              className="cbtn nodrag"
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation()
                ctx.toggleCollapse(id)
              }}
            >
              {n.collapsed ? '展开' : '折叠'}
            </button>
            <button
              className="cbtn nodrag"
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation()
                ctx.focusOn(id)
              }}
            >
              聚焦
            </button>
          </div>
          <div className="cmini">
            {n.collapsed
              ? `${count} 张卡片已折叠`
              : count
                ? '卡片会跟着这个框一起走'
                : '把卡片拖进来'}
          </div>
          <Handle type="target" position={Position.Left} className="port left" />
          <Handle type="source" position={Position.Right} className="port right" />
        </div>
      </>
    )
  }

  return (
    <>
      <NodeResizer
        isVisible={!!selected}
        minWidth={MIN_W}
        minHeight={MIN_H}
        maxWidth={MAX_W}
        maxHeight={MAX_H}
        lineClassName="nl"
        handleClassName="nh"
        onResizeEnd={(_e, p) => ctx.resize(id, p.width, p.height)}
      />
      <div
        className={`card${selected ? ' sel' : ''}`}
        onMouseEnter={() => setHover(id)}
        onMouseLeave={() => setHover(null)}
      >
      <i
        className="dot"
        style={{ background: color }}
        title={(st?.label || '状态') + '（点一下切换）'}
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation()
          ctx.cycleState(id)
        }}
      />
      {editing === 'title' ? (
        <textarea
          ref={taRef}
          className="edit nodrag"
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={onKey}
        />
      ) : (
        <div
          className="ttl"
          onDoubleClick={start('title')}
          onClick={(e) => {
            if (e.detail >= 2) start('title')(e)
          }}
        >
          {n.name || '未命名'}
        </div>
      )}

      {editing === 'sum' ? (
        <textarea
          ref={taRef}
          className="edit sum-edit nodrag"
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={onKey}
        />
      ) : (
        <div
          className="sum"
          onDoubleClick={start('sum')}
          onClick={(e) => {
            if (e.detail >= 2) start('sum')(e)
          }}
        >
          {summary}
        </div>
      )}

      {chips.length ? <div className="mini">{chips.join(' · ')}</div> : null}

      <Handle type="target" position={Position.Left} className="port left" />
      <Handle type="source" position={Position.Right} className="port right" />
      </div>
    </>
  )
}

export default memo(CardNodeInner)
