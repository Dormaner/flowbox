import { useState } from 'react'
import type { Field, FlowNode, Status } from './types'
import { FieldEdit, FieldView } from './fieldui'

/** 字段类型：label 是给人看的，hint 是选的时候那句解释 */
export const FIELD_TYPES: { type: string; label: string; hint: string }[] = [
  { type: 'text', label: '文字', hint: '一句话，比如「谁办」' },
  { type: 'longtext', label: '多行文本', hint: '整段说明，回车换行' },
  { type: 'number', label: '数字', hint: '金额、天数' },
  { type: 'date', label: '日期', hint: '2026-12-31' },
  { type: 'user', label: '人员', hint: '谁负责' },
  { type: 'select', label: '单选', hint: '从固定选项里挑一个' },
  { type: 'multiselect', label: '多选', hint: '可以挑多个' },
  { type: 'list', label: '清单', hint: '一条一行，可勾选' },
  { type: 'checkbox', label: '复选框', hint: '是 / 否' },
  { type: 'link', label: '超链接', hint: '网址 + 按钮文字' },
  { type: 'attachment', label: '附件', hint: '挂真实文件，一行一个' },
  { type: 'image', label: '图片', hint: '截图，一行一张' },
]

const labelOf = (t: string) => FIELD_TYPES.find((x) => x.type === t)?.label || t

function blankValue(type: string): any {
  if (type === 'list' || type === 'multiselect' || type === 'attachment' || type === 'image')
    return []
  if (type === 'checkbox') return false
  if (type === 'link') return { url: '', text: '' }
  return ''
}

/** 换类型时尽量把旧值带过去，带不过去就留空，绝不抛错 */
export function convert(type: string, v: any): any {
  if (type === 'list' || type === 'multiselect') {
    if (Array.isArray(v))
      return v.map((x) => (typeof x === 'object' && x ? x.text ?? x.name ?? '' : String(x)))
    return String(v ?? '').split('\n').map((s) => s.trim()).filter(Boolean)
  }
  if (type === 'attachment') return Array.isArray(v) ? v.filter((x) => typeof x === 'object') : []
  if (type === 'image') return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []
  if (type === 'checkbox') return v === true || v === 'true' || v === '是'
  if (type === 'link') {
    if (v && typeof v === 'object') return { url: v.url || '', text: v.text || '' }
    return { url: String(v ?? ''), text: '' }
  }
  if (Array.isArray(v))
    return v.map((x) => (typeof x === 'object' && x ? x.text ?? x.name ?? '' : x)).join('\n')
  if (v && typeof v === 'object') return v.url || v.name || ''
  return v == null ? '' : String(v)
}

type Props = {
  node: FlowNode
  statuses: Status[]
  project: string
  mode: 'edit' | 'view'
  width: number
  onWidth: (w: number) => void
  float: boolean
  onToggleFloat: () => void
  pos: { x: number; y: number }
  onPos: (p: { x: number; y: number }) => void
  onPatch: (patch: Partial<FlowNode>) => void
  onClose: () => void
  onToast: (msg: string) => void
}

export default function Drawer({
  node,
  statuses,
  project,
  mode,
  width,
  onWidth,
  float,
  onToggleFloat,
  pos,
  onPos,
  onPatch,
  onClose,
  onToast,
}: Props) {
  const fields = node.fields || []
  const [picking, setPicking] = useState(false)
  const edit = mode === 'edit'

  const setFields = (next: Field[]) => onPatch({ fields: next })
  const putField = (idx: number, value: any, extra?: Partial<Field>) => {
    setFields(fields.map((f, i) => (i === idx ? { ...f, ...extra, value } : f)))
  }
  const renameField = (idx: number, label: string) => {
    const t = label.trim()
    if (!t || t === fields[idx].label) return
    setFields(fields.map((f, i) => (i === idx ? { ...f, label: t } : f)))
  }
  const retypeField = (idx: number, type: string) => {
    if (fields[idx].type === type) return
    setFields(fields.map((x, i) => (i === idx ? { ...x, type, value: convert(type, x.value) } : x)))
  }
  const moveField = (idx: number, dir: -1 | 1) => {
    const j = idx + dir
    if (j < 0 || j >= fields.length) return
    const next = fields.slice()
    const tmp = next[idx]
    next[idx] = next[j]
    next[j] = tmp
    setFields(next)
  }
  const deleteField = (idx: number) => {
    const f = fields[idx]
    if (!window.confirm(`删除字段「${f.label || '未命名'}」？可以用 Ctrl+Z 撤回。`)) return
    setFields(fields.filter((_, i) => i !== idx))
  }
  const addField = (type: string) => {
    setPicking(false)
    setFields([...fields, { type, label: labelOf(type), value: blankValue(type) }])
  }

  const startResize = (e: React.PointerEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const startX = e.clientX
    const startW = width
    document.body.style.cursor = 'col-resize'
    const move = (ev: PointerEvent) =>
      onWidth(Math.min(820, Math.max(300, startW + (startX - ev.clientX))))
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      document.body.style.cursor = ''
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  const startDrag = (e: React.PointerEvent) => {
    if (!float) return
    if ((e.target as HTMLElement).closest('button, .resizer')) return
    e.preventDefault()
    const ox = e.clientX - pos.x
    const oy = e.clientY - pos.y
    const move = (ev: PointerEvent) =>
      onPos({
        x: Math.min(window.innerWidth - 160, Math.max(0, ev.clientX - ox)),
        y: Math.min(window.innerHeight - 80, Math.max(0, ev.clientY - oy)),
      })
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  return (
    <aside
      className={'drawer' + (float ? ' float' : '')}
      style={{ width, ...(float ? { left: pos.x, top: pos.y } : {}) }}
    >
      <div className="resizer" onPointerDown={startResize} title="拖动调宽" />
      <div
        className="dh"
        onPointerDown={startDrag}
        style={{ cursor: float ? 'move' : 'default' }}
      >
        <span>{edit ? '卡片 · 编辑' : '卡片 · 预览'}</span>
        <span className="sp" />
        <button
          title={float ? '停靠到右侧' : '变成浮动窗口（可拖动）'}
          onClick={onToggleFloat}
        >
          {float ? '⇥' : '⧉'}
        </button>
        <button onClick={onClose}>✕</button>
      </div>
      <div className="db">
        {edit ? (
          <input
            className="dname"
            defaultValue={node.name}
            key={node.id + ':name'}
            onBlur={(e) => onPatch({ name: e.target.value.trim() || '未命名' })}
          />
        ) : (
          <div className="dname-ro">{node.name}</div>
        )}

        {edit ? (
          <textarea
            className="dsum"
            defaultValue={node.summary || ''}
            key={node.id + ':sum'}
            placeholder="一句话说明这一步（会显示在卡片上）"
            onBlur={(e) => onPatch({ summary: e.target.value })}
          />
        ) : node.summary ? (
          <div className="dsum-ro">{node.summary}</div>
        ) : null}

        <div className="drow">
          <span>状态</span>
          <div className="chips">
            {statuses.map((s) => {
              const on = s.key === (node.state || statuses[0]?.key)
              return (
                <span
                  key={s.key}
                  className={'chip' + (on ? ' on' : '') + (edit ? '' : ' ro')}
                  onClick={edit ? () => onPatch({ state: s.key }) : undefined}
                >
                  <i style={{ background: s.color }} />
                  {s.label}
                </span>
              )
            })}
          </div>
        </div>

        {fields.map((f, i) => (
          <div className="dfield" key={node.id + ':' + i}>
            <div className="fl">
              {edit ? (
                <input
                  className="fname"
                  defaultValue={f.label}
                  key={node.id + ':' + i + ':' + f.label}
                  placeholder="字段名"
                  onBlur={(e) => renameField(i, e.target.value)}
                />
              ) : (
                <span className="flabel">{f.label || '未命名字段'}</span>
              )}
              {edit ? (
                <>
                  <select
                    className="ftype"
                    value={f.type || 'text'}
                    onChange={(e) => retypeField(i, e.target.value)}
                    title="换类型（旧值会尽量带过去）"
                  >
                    {FIELD_TYPES.map((t) => (
                      <option key={t.type} value={t.type}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                  <button
                    className="mini"
                    disabled={i === 0}
                    onClick={() => moveField(i, -1)}
                    title="上移"
                  >
                    ↑
                  </button>
                  <button
                    className="mini"
                    disabled={i === fields.length - 1}
                    onClick={() => moveField(i, 1)}
                    title="下移"
                  >
                    ↓
                  </button>
                  <button className="mini danger" onClick={() => deleteField(i)} title="删除字段">
                    ✕
                  </button>
                </>
              ) : null}
            </div>
            {edit ? (
              <FieldEdit
                field={f}
                project={project}
                nodeId={node.id}
                onChange={(v, extra) => putField(i, v, extra)}
                onError={onToast}
              />
            ) : (
              <FieldView field={f} project={project} />
            )}
          </div>
        ))}

        {edit ? (
          <>
            <button className="addfield" onClick={() => setPicking((v) => !v)}>
              ＋ 添加字段
            </button>
            {picking ? (
              <div className="typemenu">
                {FIELD_TYPES.map((t) => (
                  <button key={t.type} onClick={() => addField(t.type)}>
                    <b>{t.label}</b>
                    <span>{t.hint}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </aside>
  )
}
