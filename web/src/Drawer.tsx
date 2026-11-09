import { useEffect, useRef, useState } from 'react'
import type { FlowNode, Status } from './types'
import { bodyOf } from './migrate'
import { mdStats, mdToHtml } from './markdown'
import { fileDataUrl, fileUrl, isDesktop } from './storage'
import { uploadFile } from './assets'

const EMBED_RE = /!\[\[([^\]]+)\]\]/g

/** 把正文里引用到的文件换成能显示的地址（桌面版是 data URL） */
function useEmbeds(project: string, body: string) {
  const [map, setMap] = useState<Record<string, string>>({})
  useEffect(() => {
    const rels = new Set<string>()
    let m: RegExpExecArray | null
    EMBED_RE.lastIndex = 0
    while ((m = EMBED_RE.exec(body))) rels.add(m[1].trim())
    if (!rels.size) {
      setMap({})
      return
    }
    let alive = true
    ;(async () => {
      const next: Record<string, string> = {}
      for (const rel of rels) {
        try {
          next[rel] = await fileDataUrl(project, rel)
        } catch {
          /* 缺文件就留空 */
        }
      }
      if (alive) setMap(next)
    })()
    return () => {
      alive = false
    }
  }, [project, body, isDesktop])
  return map
}

type Props = {
  node: FlowNode | null
  statuses: Status[]
  project: string
  mode: 'edit' | 'view'
  onMode: (m: 'edit' | 'view') => void
  pin: boolean
  onTogglePin: () => void
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
  onMode,
  pin,
  onTogglePin,
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
  const edit = mode === 'edit'
  const n: FlowNode = node || ({ id: '', name: '', fields: [] } as unknown as FlowNode)
  const body = bodyOf(n)
  const stats = mdStats(body)
  const embeds = useEmbeds(project, body)
  const taRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  /** 在光标处插入一段文字 */
  const insert = (text: string) => {
    const ta = taRef.current
    const cur = body
    if (!ta) {
      onPatch({ body: `${cur}\n${text}`.trim() })
      return
    }
    const start = ta.selectionStart ?? cur.length
    const end = ta.selectionEnd ?? cur.length
    const next = cur.slice(0, start) + text + cur.slice(end)
    onPatch({ body: next })
    requestAnimationFrame(() => {
      ta.focus()
      ta.selectionStart = ta.selectionEnd = start + text.length
    })
  }

  const addFiles = async (files: File[]) => {
    if (!files.length) return
    const lines: string[] = []
    for (const f of files) {
      try {
        const saved = await uploadFile(project, n.id, f)
        lines.push(`![[${saved.rel}]]`)
      } catch (e: any) {
        onToast(e?.message || String(e))
      }
    }
    if (lines.length) insert(`\n${lines.join('\n')}\n`)
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === '/') {
      e.preventDefault()
      e.stopPropagation() // 别让 App 的全局快捷键再翻一次
      onMode(edit ? 'view' : 'edit')
      return
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
      e.preventDefault()
      wrap('**')
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault()
      insert('[](url)')
    }
    if (e.key === 'Tab' && !e.shiftKey) {
      e.preventDefault()
      insert('  ')
    }
  }

  /** 给选中文字加包裹（加粗、行内代码） */
  const wrap = (mark: string) => {
    const ta = taRef.current
    if (!ta) return
    const cur = body
    const s = ta.selectionStart ?? 0
    const e2 = ta.selectionEnd ?? 0
    const sel = cur.slice(s, e2) || (mark === '**' ? '加粗文字' : 'code')
    onPatch({ body: cur.slice(0, s) + mark + sel + mark + cur.slice(e2) })
    requestAnimationFrame(() => {
      ta.focus()
      ta.selectionStart = s + mark.length
      ta.selectionEnd = s + mark.length + sel.length
    })
  }

  const toggleTask = (index: number) => {
    const lines = body.split('\n')
    let n = -1
    for (let i = 0; i < lines.length; i++) {
      if (/^\s*[-*]\s+\[( |x|X)\]/.test(lines[i])) {
        n++
        if (n === index) {
          lines[i] = lines[i].replace(/\[( |x|X)\]/, (_m, c) => (c === ' ' ? '[x]' : '[ ]'))
          break
        }
      }
    }
    onPatch({ body: lines.join('\n') })
  }

  const startResize = (e: React.PointerEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const startX = e.clientX
    const startW = width
    document.body.style.cursor = 'col-resize'
    const move = (ev: PointerEvent) =>
      onWidth(Math.min(900, Math.max(340, startW + (startX - ev.clientX))))
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

  if (!node) {
    return (
      <aside className={'drawer' + (float ? ' float' : '')} style={{ width, ...(float ? { left: pos.x, top: pos.y } : {}) }}>
        <div className="resizer" onPointerDown={startResize} title="拖动调宽" />
        <div className="dh" onPointerDown={startDrag} style={{ cursor: float ? 'move' : 'default' }}>
          <div className="modesw">
            <button id="m-edit" className={edit ? 'on' : ''} onClick={() => onMode('edit')} title="Ctrl+/">
              编辑
            </button>
            <button id="m-view" className={!edit ? 'on' : ''} onClick={() => onMode('view')} title="Ctrl+/">
              预览
            </button>
          </div>
          <span className="sp" />
          <button id="d-pin" className={pin ? 'on' : ''} title="取消固定" onClick={onTogglePin}>
            📌
          </button>
          <button title={float ? '停靠到右侧' : '浮动窗口'} onClick={onToggleFloat}>
            {float ? '⇥' : '⧉'}
          </button>
          <button id="d-close" onClick={onClose}>✕</button>
        </div>
        <div className="db">
          <div className="dempty">
            点一张卡片，这里显示它的正文
            <span>拖边角改大小 · Ctrl+/ 切编辑与预览</span>
          </div>
        </div>
      </aside>
    )
  }

  return (
    <aside
      className={'drawer' + (float ? ' float' : '')}
      style={{ width, ...(float ? { left: pos.x, top: pos.y } : {}) }}
    >
      <div className="resizer" onPointerDown={startResize} title="拖动调宽" />
      <div className="dh" onPointerDown={startDrag} style={{ cursor: float ? 'move' : 'default' }}>
        <div className="modesw">
          <button id="m-edit" className={edit ? 'on' : ''} onClick={() => onMode('edit')} title="Ctrl+/">
            编辑
          </button>
          <button id="m-view" className={!edit ? 'on' : ''} onClick={() => onMode('view')} title="Ctrl+/">
            预览
          </button>
        </div>
        <span className="sp" />
        <button
          id="d-pin"
          className={pin ? 'on' : ''}
          title={pin ? '取消固定（不选卡片就收起）' : '固定在页面上（不选卡片也留着）'}
          onClick={onTogglePin}
        >
          📌
        </button>
        <button title={float ? '停靠到右侧' : '浮动窗口'} onClick={onToggleFloat}>
          {float ? '⇥' : '⧉'}
        </button>
        <button id="d-close" onClick={onClose}>✕</button>
      </div>

      <div className="db">
        {edit ? (
          <input
            className="dname"
            defaultValue={n.name}
            key={n.id + ':name'}
            onBlur={(e) => onPatch({ name: e.target.value.trim() || '未命名' })}
          />
        ) : (
          <div className="dname-ro">{n.name}</div>
        )}

        <div className="drow">
          <span>状态</span>
          <div className="chips">
            {statuses.map((s) => (
              <span
                key={s.key}
                className={'chip' + (s.key === (n.state || statuses[0]?.key) ? ' on' : '') + (edit ? '' : ' ro')}
                onClick={edit ? () => onPatch({ state: s.key }) : undefined}
              >
                <i style={{ background: s.color }} />
                {s.label}
              </span>
            ))}
          </div>
          {stats.checks.total ? (
            <span className="mcount">
              材料 {stats.checks.done}/{stats.checks.total}
            </span>
          ) : null}
        </div>

        <div className="drow">
          <span>大小</span>
          <span className="msize">
            {Math.round(n.w || 220)} × {Math.round(n.h || 0) || '自动'}
          </span>
          <button className="mini-btn" onClick={() => onPatch({ w: undefined, h: undefined })}>
            自适应
          </button>
          <span className="mcount">拖卡片边角随意改</span>
        </div>

        {edit ? (
          <>
            <div className="mdtools">
              <button title="加粗 Ctrl+B" onClick={() => wrap('**')}>
                <b>B</b>
              </button>
              <button title="标题" onClick={() => insert('\n## ')}>
                H
              </button>
              <button title="列表" onClick={() => insert('\n- ')}>
                • 列表
              </button>
              <button title="勾选清单" onClick={() => insert('\n- [ ] ')}>
                ☑ 清单
              </button>
              <button
                title="表格"
                onClick={() => insert('\n| 项目 | 金额 |\n| --- | --- |\n|  |  |\n')}
              >
                ▦ 表格
              </button>
              <button title="插入文件" onClick={() => fileRef.current?.click()}>
                📎 文件
              </button>
              <span className="sp" />
              <span className="mhint">Ctrl+/ 预览</span>
            </div>
            <textarea
              ref={taRef}
              className="md"
              value={body}
              spellCheck={false}
              onChange={(e) => onPatch({ body: e.target.value })}
              onKeyDown={onKeyDown}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                const fs = Array.from(e.dataTransfer?.files || [])
                if (fs.length) {
                  e.preventDefault()
                  void addFiles(fs)
                }
              }}
              onPaste={(e) => {
                const fs = Array.from(e.clipboardData.files || [])
                if (fs.length) {
                  e.preventDefault()
                  void addFiles(fs)
                }
              }}
              placeholder={'写这一步要做什么…\n\n要交的材料：\n- [ ] 合同\n- [ ] 发票'}
            />
            <input
              ref={fileRef}
              type="file"
              multiple
              style={{ display: 'none' }}
              onChange={(e) => {
                const fs = Array.from(e.target.files || [])
                e.target.value = ''
                void addFiles(fs)
              }}
            />
          </>
        ) : (
          <div
            className="mdview"
            dangerouslySetInnerHTML={{
              __html: mdToHtml(body, {
                resolve: (rel) => embeds[rel] || (isDesktop ? '' : fileUrl(project, rel)),
              }),
            }}
          />
        )}
      </div>
    </aside>
  )
}

