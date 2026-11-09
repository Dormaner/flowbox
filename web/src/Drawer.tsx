import { useEffect, useState } from 'react'
import type { Field, FlowNode, Status } from './types'
import { fileDataUrl, fileUrl, isDesktop } from './storage'

/** 字段类型：label 是给人看的，hint 是选的时候那句解释 */
export const FIELD_TYPES: { type: string; label: string; hint: string }[] = [
  { type: 'text', label: '文字', hint: '一句话，比如「谁办」' },
  { type: 'longtext', label: '多行文本', hint: '整段说明，回车换行' },
  { type: 'number', label: '数字', hint: '金额、天数' },
  { type: 'date', label: '日期', hint: '2026-12-31' },
  { type: 'user', label: '人员', hint: '谁负责' },
  { type: 'select', label: '单选', hint: '从固定选项里挑一个' },
  { type: 'multiselect', label: '多选', hint: '可以挑多个' },
  { type: 'list', label: '清单', hint: '一行一条' },
  { type: 'checkbox', label: '复选框', hint: '是 / 否' },
  { type: 'link', label: '超链接', hint: '网址 + 按钮文字' },
  { type: 'attachment', label: '附件', hint: '挂真实文件，能直接打开' },
  { type: 'image', label: '图片', hint: '截图，点开看大图' },
]

const labelOf = (t: string) => FIELD_TYPES.find((x) => x.type === t)?.label || t

function blankValue(type: string): any {
  if (type === 'list' || type === 'multiselect' || type === 'attachment' || type === 'image') return []
  if (type === 'checkbox') return false
  if (type === 'link') return { url: '', text: '' }
  return ''
}

/** 换类型时尽量把旧值带过去，带不过去就留空，绝不抛错 */
function convert(type: string, v: any): any {
  if (type === 'list' || type === 'multiselect') {
    if (Array.isArray(v)) return v.map((x) => (typeof x === 'object' && x ? x.name || '' : String(x)))
    return String(v ?? '').split('\n').map((s) => s.trim()).filter(Boolean)
  }
  if (type === 'attachment') return Array.isArray(v) ? v.filter((x) => typeof x === 'object') : []
  if (type === 'image') return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []
  if (type === 'checkbox') return v === true || v === 'true' || v === '是'
  if (type === 'link') {
    if (v && typeof v === 'object') return { url: v.url || '', text: v.text || '' }
    return { url: String(v ?? ''), text: '' }
  }
  if (Array.isArray(v)) return v.map((x) => (typeof x === 'object' && x ? x.name || '' : x)).join('\n')
  if (v && typeof v === 'object') return v.url || v.name || ''
  return v == null ? '' : String(v)
}

/** 截图：浏览器直接用 bridge 地址，桌面版向 Rust 要 data URL */
function LocalImg({ project, rel }: { project: string; rel: string }) {
  const [src, setSrc] = useState('')
  useEffect(() => {
    let alive = true
    fileDataUrl(project, rel)
      .then((u) => {
        if (alive) setSrc(u)
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [project, rel])
  return src ? <img src={src} alt="" /> : null
}

function FieldView({
  field,
  project,
  onChange,
}: {
  field: Field
  project: string
  onChange: (v: any) => void
}) {
  const t = field.type || 'text'
  const v = field.value

  if (t === 'list' || t === 'multiselect') {
    const items: string[] = Array.isArray(v) ? v : []
    return (
      <textarea
        defaultValue={items.join('\n')}
        placeholder="一行一条"
        onBlur={(e) => onChange(e.target.value.split('\n').map((s) => s.trim()).filter(Boolean))}
      />
    )
  }

  if (t === 'longtext') {
    return <textarea defaultValue={String(v || '')} onBlur={(e) => onChange(e.target.value)} />
  }

  if (t === 'link') {
    const obj = v && typeof v === 'object' ? v : { url: String(v || ''), text: '' }
    return (
      <>
        <input
          type="text"
          defaultValue={obj.url || ''}
          placeholder="网址，比如 oa.example.com"
          onBlur={(e) => onChange({ ...obj, url: e.target.value.trim() })}
        />
        <input
          type="text"
          defaultValue={obj.text || ''}
          placeholder="按钮上写的字，比如「打开 OA」"
          style={{ marginTop: 4 }}
          onBlur={(e) => onChange({ ...obj, text: e.target.value.trim() })}
        />
      </>
    )
  }

  if (t === 'checkbox') {
    return (
      <label style={{ fontSize: 12.5 }}>
        <input type="checkbox" defaultChecked={Boolean(v)} onChange={(e) => onChange(e.target.checked)} /> 是
      </label>
    )
  }

  if (t === 'attachment') {
    const items = Array.isArray(v) ? v : []
    return (
      <div>
        {items.map((m: any, i: number) => (
          <div className="mat" key={i}>
            <span
              className={'mk' + (m?.done ? ' ok' : '')}
              style={{ cursor: 'pointer' }}
              onClick={() => onChange(items.map((x: any, j: number) => (j === i ? { ...x, done: !x.done } : x)))}
            >
              {m?.done ? '✓' : '○'}
            </span>
            <span>{m?.name || '（未命名材料）'}</span>
            {m?.file && !isDesktop ? (
              <a href={fileUrl(project, m.file)} target="_blank" rel="noreferrer">
                打开
              </a>
            ) : null}
          </div>
        ))}
        {items.length === 0 ? <div className="mat">（还没有材料）</div> : null}
      </div>
    )
  }

  if (t === 'image') {
    const items = Array.isArray(v) ? v : []
    return (
      <div className="shots">
        {items.map((rel: string, i: number) => (
          <LocalImg key={i} project={project} rel={rel} />
        ))}
        {items.length === 0 ? <div className="mat">（还没有截图）</div> : null}
      </div>
    )
  }

  return <input type="text" defaultValue={String(v ?? '')} onBlur={(e) => onChange(e.target.value)} />
}

type Props = {
  node: FlowNode
  statuses: Status[]
  project: string
  onPatch: (patch: Partial<FlowNode>) => void
  onClose: () => void
}

export default function Drawer({ node, statuses, project, onPatch, onClose }: Props) {
  const fields = node.fields || []
  const [picking, setPicking] = useState(false)

  const setFields = (next: Field[]) => onPatch({ fields: next })

  const setField = (idx: number, value: any) => {
    setFields(fields.map((f, i) => (i === idx ? { ...f, value } : f)))
  }
  const renameField = (idx: number, label: string) => {
    const t = label.trim()
    if (!t || t === fields[idx].label) return
    setFields(fields.map((f, i) => (i === idx ? { ...f, label: t } : f)))
  }
  const retypeField = (idx: number, type: string) => {
    if (fields[idx].type === type) return
    setFields(
      fields.map((x, i) => (i === idx ? { ...x, type, value: convert(type, x.value) } : x)),
    )
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

  return (
    <aside className="drawer">
      <div className="dh">
        <span>卡片</span>
        <span className="sp" />
        <button onClick={onClose}>✕</button>
      </div>
      <div className="db">
        <input
          className="dname"
          defaultValue={node.name}
          key={node.id + ':name'}
          onBlur={(e) => onPatch({ name: e.target.value.trim() || '未命名' })}
        />
        <textarea
          className="dsum"
          defaultValue={node.summary || ''}
          key={node.id + ':sum'}
          placeholder="一句话说明这一步（会显示在卡片上）"
          onBlur={(e) => onPatch({ summary: e.target.value })}
        />

        <div className="drow">
          <span>状态</span>
          <div className="chips">
            {statuses.map((s) => (
              <span
                key={s.key}
                className={'chip' + (s.key === (node.state || statuses[0]?.key) ? ' on' : '')}
                onClick={() => onPatch({ state: s.key })}
              >
                <i style={{ background: s.color }} />
                {s.label}
              </span>
            ))}
          </div>
        </div>

        {fields.map((f, i) => (
          <div className="dfield" key={node.id + ':' + i}>
            <div className="fl">
              <input
                className="fname"
                defaultValue={f.label}
                key={node.id + ':' + i + ':' + f.label}
                placeholder="字段名"
                onBlur={(e) => renameField(i, e.target.value)}
              />
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
              <button className="mini" disabled={i === 0} onClick={() => moveField(i, -1)} title="上移">
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
            </div>
            <FieldView field={f} project={project} onChange={(v) => setField(i, v)} />
          </div>
        ))}

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
      </div>
    </aside>
  )
}

