import { useEffect, useState } from 'react'
import type { Field, FlowNode, Status } from './types'
import { fileDataUrl, fileUrl, isDesktop } from './storage'

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

type Props = {
  node: FlowNode
  statuses: Status[]
  project: string
  onPatch: (patch: Partial<FlowNode>) => void
  onClose: () => void
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
        onBlur={(e) => onChange(e.target.value.split('\n').map((s) => s.trim()).filter(Boolean))}
      />
    )
  }

  if (t === 'longtext') {
    return <textarea defaultValue={String(v || '')} onBlur={(e) => onChange(e.target.value)} />
  }

  if (t === 'link') {
    const obj = typeof v === 'object' && v ? v : { url: String(v || ''), text: '' }
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
            <span className={'mk' + (m?.done ? ' ok' : '')}>{m?.done ? '✓' : '○'}</span>
            <span>{m?.name || '（未命名材料）'}</span>
            {m?.file ? (
              isDesktop ? (
                <span style={{ fontSize: 11.5, color: '#9aa1aa' }}>{m.file}</span>
              ) : (
                <a href={fileUrl(project, m.file)} target="_blank" rel="noreferrer">
                  打开
                </a>
              )
            ) : null}
          </div>
        ))}
        {items.length === 0 ? <div className="mat">（还没有材料，把文件拖到卡片上）</div> : null}
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

export default function Drawer({ node, statuses, project, onPatch, onClose }: Props) {
  const fields = node.fields || []

  const setField = (idx: number, value: any) => {
    const next = fields.map((f, i) => (i === idx ? { ...f, value } : f))
    onPatch({ fields: next })
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
              <span>{f.label || '未命名字段'}</span>
              <span className="sp" />
              <span>{f.type}</span>
            </div>
            <FieldView field={f} project={project} onChange={(v) => setField(i, v)} />
          </div>
        ))}

        <button className="addfield">＋ 添加字段</button>
      </div>
    </aside>
  )
}
