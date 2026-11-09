import { createContext, memo, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { FlowNode, Status } from './types'

type Ctx = {
  statuses: Status[]
  patch: (id: string, patch: Partial<FlowNode>) => void
  cycleState: (id: string) => void
}

export const EditorCtx = createContext<Ctx>({
  statuses: [],
  patch: () => {},
  cycleState: () => {},
})

// 新建卡片只自动进一次改名，撤销 / 重做时不要又弹出来
const autoEdited = new Set<string>()

function CardNodeInner({ id, data, selected }: NodeProps) {
  const n = (data as any).node as FlowNode
  const ctx = useContext(EditorCtx)
  const [editing, setEditing] = useState<null | 'title' | 'sum'>(null)
  const [draft, setDraft] = useState('')
  const taRef = useRef<HTMLTextAreaElement>(null)

  const st = ctx.statuses.find((s) => s.key === (n.state || ctx.statuses[0]?.key))
  const color = st?.color || '#C7CBD1'

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

  return (
    <div className={`card${selected ? ' sel' : ''}`}>
      <i
        className="dot"
        style={{ background: color }}
        title={st?.label || '状态'}
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
          {n.summary || ''}
        </div>
      )}

      <Handle type="target" position={Position.Left} className="port left" />
      <Handle type="source" position={Position.Right} className="port right" />
    </div>
  )
}

export default memo(CardNodeInner)
