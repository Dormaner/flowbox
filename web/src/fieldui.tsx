import { useEffect, useRef, useState } from 'react'
import type { Field } from './types'
import { humanSize, normList, optionsOf, parseLink } from './fields'
import { fileDataUrl, openAsset, openUrl } from './storage'
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

/** 图片占满一行：名字放图片右下角，按钮悬停才出来 */
function BigImg({
  project,
  rel,
  onClick,
}: {
  project: string
  rel: string
  onClick?: () => void
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
  const name = (rel.split(/[\\/]/).pop() || rel)
  return (
    <div className="imgrow">
      {src ? (
        <img className="imgsrc" src={src} alt="" onClick={onClick} />
      ) : (
        <div className="imgsrc ph" onClick={onClick} />
      )}
      <span className="imgname" title={rel}>
        {name}
      </span>
    </div>
  )
}

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

  if (t === 'image') {
    const items: string[] = Array.isArray(v) ? v.map(String) : []
    return (
      <div className="assets">
        {items.map((rel, i) => (
          <div className="imgcell" key={i}>
            <BigImg project={project} rel={rel} onClick={() => openAsset(project, rel)} />
            <div className="imgbtns">
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
          </div>
        ))}
        <button className="ar-add" onClick={() => fileRef.current?.click()}>
          ＋ 添加图片
        </button>
        {hidden}
      </div>
    )
  }

  if (t === 'attachment') {
    const items: any[] = Array.isArray(v) ? v : []
    return (
      <div className="assets">
        {items.map((m, i) => {
          const rel = String(m?.file || '')
          return (
            <div className="assetrow" key={i}>
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
              <span className="ar-name" title={rel}>
                {m?.name || baseName(rel)}
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
          ＋ 添加附件
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
    const { kind, href } = parseLink(obj.url)
    return (
      <div>
        <input
          type="text"
          defaultValue={obj.url || ''}
          placeholder="网址，或本地文件 C:\xxx.pdf / \\server\共享\xx.docx"
          onBlur={(e) => onChange({ ...obj, url: e.target.value.trim() })}
        />
        <input
          type="text"
          defaultValue={obj.text || ''}
          placeholder="按钮上写的字，比如「打开 OA」"
          style={{ marginTop: 4 }}
          onBlur={(e) => onChange({ ...obj, text: e.target.value.trim() })}
        />
        {kind !== 'empty' ? (
          <div className="linktest">
            <button className="ar-act" onClick={() => openUrl(obj.url)}>
              测试打开 ↗
            </button>
            <span className="linkkind">{kind === 'path' ? '本地文件' : '网址'}</span>
          </div>
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

  if (t === 'image') {
    const items: string[] = Array.isArray(v) ? v.map(String) : []
    if (!items.length) return <div className="vempty">—</div>
    return (
      <div className="assets">
        {items.map((rel, i) => (
          <BigImg key={i} project={project} rel={rel} onClick={() => openAsset(project, rel)} />
        ))}
      </div>
    )
  }

  if (t === 'attachment') {
    const items: any[] = Array.isArray(v) ? v : []
    if (!items.length) return <div className="vempty">—</div>
    return (
      <div className="assets">
        {items.map((m, i) => {
          const rel = String(m?.file || '')
          return (
            <div className="assetrow" key={i}>
              <span className={'ar-mark' + (m?.done ? ' ok' : '')}>{m?.done ? '✓' : '○'}</span>
              <span className="ar-name" title={rel}>
                {m?.name || baseName(rel)}
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
    const { kind, href } = parseLink(obj.url)
    if (kind === 'empty') return <div className="vempty">—</div>
    const label =
      obj.text ||
      (kind === 'path'
        ? href.split(/[\\/]/).pop()
        : href.replace(/^https?:\/\//, '').replace(/\/$/, ''))
    return (
      <button className="vbtn" title={href} onClick={() => openUrl(obj.url)}>
        {label} ↗
      </button>
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


