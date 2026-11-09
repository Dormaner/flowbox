import { useEffect, useRef, useState } from 'react'
import type { Field } from './types'
import { humanSize, normList, optionsOf } from './fields'
import { fileDataUrl, openAsset } from './storage'
import { uploadFile } from './assets'

export function Thumb({
  project,
  rel,
  w = 72,
  h = 48,
}: {
  project: string
  rel: string
  w?: number
  h?: number
}) {
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
  if (!src) return <span className="ar-thumb" style={{ width: w, height: h }} />
  return (
    <img
      className="ar-thumb"
      src={src}
      style={{ width: w, height: h, objectFit: 'cover' }}
      alt=""
    />
  )
}

const baseName = (rel: string) => (rel.split(/[\\/]/).pop() || rel).replace(/\.[^.]+$/, '')

export function FieldEdit({
  field,
  project,
  nodeId,
  onChange,
  onError,
}: {
  field: Field
  project: string
  nodeId: string
  onChange: (value: any, extra?: Partial<Field>) => void
  onError: (msg: string) => void
}) {
  const t = field.type || 'text'
  const v = field.value
  const fileRef = useRef<HTMLInputElement>(null)
  const [optOpen, setOptOpen] = useState(false)

  const addFiles = async (files: File[]) => {
    if (!files.length) return
    const next = Array.isArray(field.value) ? [...(field.value as any[])] : []
    for (const f of files) {
      try {
        const saved = await uploadFile(project, nodeId, f)
        if (t === 'image') next.push(saved.rel)
        else
          next.push({
            name: baseName(saved.rel),
            file: saved.rel,
            done: true,
            size: saved.size,
          })
      } catch (e: any) {
        onError(e?.message || String(e))
      }
    }
    onChange(next)
  }

  const hidden = (
    <input
      ref={fileRef}
      type="file"
      multiple
      style={{ display: 'none' }}
      accept={t === 'image' ? 'image/*' : undefined}
      onChange={(e) => {
        const files = Array.from(e.target.files || [])
        e.target.value = ''
        void addFiles(files)
      }}
    />
  )

  if (t === 'image' || t === 'attachment') {
    const items: any[] = Array.isArray(v) ? v : []
    return (
      <div className="assets">
        {items.map((m, i) => {
          const rel = t === 'image' ? String(m) : String(m?.file || '')
          const name = t === 'image' ? baseName(rel) : m?.name || baseName(rel)
          return (
            <div className="assetrow" key={i}>
              {t === 'image' ? (
                <Thumb project={project} rel={rel} />
              ) : (
                <span
                  className={'ar-mark' + (m?.done ? ' ok' : '')}
                  title="点一下切换备齐 / 未备"
                  onClick={() => {
                    const next = items.slice()
                    next[i] = { ...m, done: !m?.done }
                    onChange(next)
                  }}
                >
                  {m?.done ? '✓' : '○'}
                </span>
              )}
              <span className="ar-name" title={rel}>
                {name}
              </span>
              <span className="ar-meta">{humanSize(m?.size || 0)}</span>
              <button className="ar-act" onClick={() => openAsset(project, rel)}>
                打开
              </button>
              <button
                className="ar-act danger"
                title="移除"
                onClick={() => onChange(items.filter((_, j) => j !== i))}
              >
                ✕
              </button>
            </div>
          )
        })}
        <button className="ar-add" onClick={() => fileRef.current?.click()}>
          ＋ 添加{t === 'image' ? '图片' : '附件'}
        </button>
        {hidden}
      </div>
    )
  }

  if (t === 'list') {
    const items = normList(v)
    return (
      <div className="assets">
        {items.map((it, i) => (
          <div className="assetrow" key={i}>
            <input
              type="checkbox"
              checked={it.done}
              onChange={() => {
                const next = items.slice()
                next[i] = { ...it, done: !it.done }
                onChange(next)
              }}
            />
            <input
              className="ar-name ar-input"
              defaultValue={it.text}
              onBlur={(e) => {
                const next = items.slice()
                next[i] = { ...it, text: e.target.value }
                onChange(next)
              }}
            />
            <button
              className="ar-act danger"
              onClick={() => onChange(items.filter((_, j) => j !== i))}
            >
              ✕
            </button>
          </div>
        ))}
        <button className="ar-add" onClick={() => onChange([...items, { text: '', done: false }])}>
          ＋ 加一条
        </button>
      </div>
    )
  }

  if (t === 'select' || t === 'multiselect') {
    const opts = optionsOf(field)
    const multi = t === 'multiselect'
    const sel: string[] = multi
      ? Array.isArray(v)
        ? v.map(String)
        : []
      : v
        ? [String(v)]
        : []
    return (
      <div>
        <div className="tags">
          {opts.map((o) => {
            const on = sel.includes(o)
            return (
              <span
                key={o}
                className={'tag' + (on ? ' on' : '')}
                onClick={() => {
                  if (multi) onChange(on ? sel.filter((x) => x !== o) : [...sel, o])
                  else onChange(on ? '' : o)
                }}
              >
                {o}
              </span>
            )
          })}
          <span className="tag add" onClick={() => setOptOpen((x) => !x)}>
            ＋ 选项
          </span>
        </div>
        {optOpen ? (
          <textarea
            className="opts"
            defaultValue={opts.join('\n')}
            placeholder="一行一个选项，改完点别处生效"
            onBlur={(e) =>
              onChange(field.value, {
                options: e.target.value.split('\n').map((s) => s.trim()).filter(Boolean),
              })
            }
          />
        ) : null}
        {opts.length === 0 ? <div className="vempty">还没有选项，点「＋ 选项」加</div> : null}
      </div>
    )
  }

  if (t === 'link') {
    const obj = v && typeof v === 'object' ? v : { url: String(v || ''), text: '' }
    const url = obj.url || ''
    const href = /^[a-z][a-z0-9+.-]*:\/\//i.test(url) ? url : url ? `https://${url}` : ''
    return (
      <div>
        <input
          type="text"
          defaultValue={url}
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
        {href ? (
          <a
            className="ar-act"
            href={href}
            target="_blank"
            rel="noreferrer"
            style={{ marginTop: 6, display: 'inline-block' }}
          >
            测试打开 ↗
          </a>
        ) : null}
      </div>
    )
  }

  if (t === 'checkbox') {
    return (
      <label className="vcheck">
        <input
          type="checkbox"
          defaultChecked={Boolean(v)}
          onChange={(e) => onChange(e.target.checked)}
        />{' '}
        是
      </label>
    )
  }

  if (t === 'longtext') {
    return <textarea defaultValue={String(v || '')} onBlur={(e) => onChange(e.target.value)} />
  }

  return (
    <input
      type={t === 'date' ? 'date' : 'text'}
      defaultValue={String(v ?? '')}
      placeholder={t === 'number' ? '填数字' : t === 'user' ? '谁负责' : ''}
      onBlur={(e) => onChange(e.target.value)}
    />
  )
}

/** 只读渲染：预览模式和导出的网页都用它 */
export function FieldView({ field, project }: { field: Field; project: string }) {
  const t = field.type || 'text'
  const v = field.value

  if (t === 'image' || t === 'attachment') {
    const items: any[] = Array.isArray(v) ? v : []
    if (!items.length) return <div className="vempty">—</div>
    return (
      <div className="assets">
        {items.map((m, i) => {
          const rel = t === 'image' ? String(m) : String(m?.file || '')
          const name = t === 'image' ? baseName(rel) : m?.name || baseName(rel)
          return (
            <div className="assetrow" key={i}>
              {t === 'image' ? (
                <Thumb project={project} rel={rel} />
              ) : (
                <span className={'ar-mark' + (m?.done ? ' ok' : '')}>{m?.done ? '✓' : '○'}</span>
              )}
              <span className="ar-name" title={rel}>
                {name}
              </span>
              <span className="ar-meta">{humanSize(m?.size || 0)}</span>
              <button className="ar-act" onClick={() => openAsset(project, rel)}>
                打开
              </button>
            </div>
          )
        })}
      </div>
    )
  }

  if (t === 'list') {
    const items = normList(v)
    if (!items.length) return <div className="vempty">—</div>
    return (
      <div className="assets">
        {items.map((it, i) => (
          <div className="vrow" key={i}>
            <span className={'ar-mark' + (it.done ? ' ok' : '')}>{it.done ? '✓' : '○'}</span>
            <span className={'vtext' + (it.done ? ' done' : '')}>{it.text}</span>
          </div>
        ))}
      </div>
    )
  }

  if (t === 'select' || t === 'multiselect') {
    const opts = optionsOf(field)
    const sel = Array.isArray(v) ? v.map(String) : v ? [String(v)] : []
    const all = opts.length ? opts : sel
    if (!all.length) return <div className="vempty">—</div>
    return (
      <div className="tags">
        {all.map((o) => (
          <span key={o} className={'tag ro' + (sel.includes(o) ? ' on' : '')}>
            {o}
          </span>
        ))}
      </div>
    )
  }

  if (t === 'link') {
    const obj = v && typeof v === 'object' ? v : { url: String(v || ''), text: '' }
    const url = String(obj.url || '').trim()
    if (!url) return <div className="vempty">—</div>
    const href = /^[a-z][a-z0-9+.-]*:\/\//i.test(url) ? url : `https://${url}`
    return (
      <a className="vbtn" href={href} target="_blank" rel="noreferrer">
        {obj.text || url} ↗
      </a>
    )
  }

  if (t === 'checkbox') {
    return <span className={'vbool' + (v ? ' yes' : '')}>{v ? '✓ 是' : '— 否'}</span>
  }

  const text = String(v ?? '').trim()
  if (!text) return <div className="vempty">—</div>
  if (t === 'number') {
    const n = Number(text.replace(/[,\s]/g, ''))
    const shown = Number.isFinite(n) ? n.toLocaleString('zh-CN') : text
    return <div className="vnum">{shown}</div>
  }
  return <div className="vtext">{text}</div>
}


