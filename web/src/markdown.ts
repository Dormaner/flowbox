// 卡片的 Markdown 内核：解析 front-matter、渲染 HTML、算摘要和统计
// 约定三条：YAML 卡头 / - [ ] 勾选清单 / ![[files/...]] 资源嵌入

export type MdStats = {
  meta: Record<string, string>
  summary: string
  checks: { total: number; done: number }
  images: string[]
  files: string[]
  title?: string
  owner?: string
  due?: string
}

const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;")

const IMG_RE = /\.(png|jpe?g|gif|webp|bmp|svg)$/i

/** 拆出卡头：--- 里面的 key: value */
export function splitFrontMatter(text: string): { meta: Record<string, string>; body: string } {
  const src = String(text || "").replace(/\r\n/g, "\n")
  if (!src.startsWith("---\n")) return { meta: {}, body: src }
  const end = src.indexOf("\n---", 4)
  if (end < 0) return { meta: {}, body: src }
  const head = src.slice(4, end)
  const body = src.slice(end + 4).replace(/^\n+/, "")
  const meta: Record<string, string> = {}
  for (const line of head.split("\n")) {
    const i = line.indexOf(":")
    if (i > 0) meta[line.slice(0, i).trim()] = line.slice(i + 1).trim()
  }
  return { meta, body }
}

/** 统计：勾选数、嵌入的图片/附件、第一个像样的段落 */
export function mdStats(text: string): MdStats {
  const { meta, body } = splitFrontMatter(text)
  let total = 0
  let done = 0
  const images: string[] = []
  const files: string[] = []
  for (const line of body.split("\n")) {
    const t = line.trim()
    const task = /^[-*]\s+\[( |x|X)\]\s+/.exec(t)
    if (task) {
      total++
      if (task[1].toLowerCase() === "x") done++
    }
    const re = /!\[\[([^\]]+)\]\]/g
    let m: RegExpExecArray | null
    while ((m = re.exec(t))) {
      const p = m[1].trim()
      if (IMG_RE.test(p)) images.push(p)
      else files.push(p)
    }
  }

  let summary = ""
  for (const raw of body.split("\n")) {
    const t = raw.trim()
    if (!t) continue
    if (t.startsWith("#")) continue
    if (t.startsWith("![[") || t.startsWith("|") || t.startsWith("```")) continue
    if (/^[-*]\s+\[( |x|X)\]/.test(t)) continue
    summary = t.replace(/^[-*>]\s*/, "").replace(/!\[\[[^\]]+\]\]/g, "〔文件〕")
    break
  }

  return {
    meta,
    summary,
    checks: { total, done },
    images,
    files,
    title: meta.title,
    owner: meta.owner || meta["负责人"] || meta["经办人"],
    due: meta.due || meta["截止"] || meta["截止日期"],
  }
}

/** 行内：**粗** *斜* `代码` [文字](链接) */
function inline(s: string): string {
  let out = esc(s)
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>")
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
  out = out.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
  out = out.replace(
    /\[([^\]]+)\]\(([^)\s]+)\)/g,
    (_m, txt, url) => `<a href="${url}" target="_blank" rel="noreferrer">${txt}</a>`,
  )
  return out
}

export type RenderCtx = { resolve: (rel: string) => string }

function embedHtml(rel: string, ctx: RenderCtx): string {
  const src = ctx.resolve(rel)
  const name = rel.split(/[\\/]/).pop() || rel
  if (IMG_RE.test(rel)) {
    return src
      ? `<img class="md-img" src="${src}" alt="" />`
      : `<span class="md-miss">图片缺失：${esc(name)}</span>`
  }
  return `<a class="md-file" href="${src || "#"}" target="_blank" rel="noreferrer">📎 ${esc(name)}</a>`
}

/** 极简 Markdown → HTML（够 SOP 用） */
export function mdToHtml(text: string, ctx: RenderCtx): string {
  const { body } = splitFrontMatter(text)
  const lines = body.replace(/\r\n/g, "\n").split("\n")
  const out: string[] = []
  let i = 0

  const flushList = (buf: string[], ordered: boolean) => {
    if (!buf.length) return
    out.push(`<${ordered ? "ol" : "ul"}>${buf.join("")}</${ordered ? "ol" : "ul"}>`)
    buf.length = 0
  }

  const inlineWithEmbeds = (s: string) =>
    inline(s).replace(/!\[\[([^\]]+)\]\]/g, (_m, rel) => embedHtml(String(rel).trim(), ctx))

  while (i < lines.length) {
    const t = lines[i].trim()

    if (!t) {
      i++
      continue
    }

    if (t.startsWith("```")) {
      const buf: string[] = []
      i++
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        buf.push(lines[i])
        i++
      }
      i++
      out.push(`<pre class="md-code"><code>${esc(buf.join("\n"))}</code></pre>`)
      continue
    }

    const single = /^!\[\[([^\]]+)\]\]$/.exec(t)
    if (single) {
      out.push(embedHtml(single[1].trim(), ctx))
      i++
      continue
    }

    const h = /^(#{1,6})\s+(.*)$/.exec(t)
    if (h) {
      out.push(`<h${Math.min(6, h[1].length + 1)}>${inline(h[2])}</h${Math.min(6, h[1].length + 1)}>`)
      i++
      continue
    }

    if (/^(-{3,}|\*{3,})$/.test(t)) {
      out.push("<hr />")
      i++
      continue
    }

    if (t.startsWith(">")) {
      const buf: string[] = []
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        buf.push(inline(lines[i].trim().replace(/^>\s?/, "")))
        i++
      }
      out.push(`<blockquote>${buf.join("<br />")}</blockquote>`)
      continue
    }

    if (t.startsWith("|") && i + 1 < lines.length && /^\|?[\s:-]+\|/.test(lines[i + 1].trim())) {
      const cells = (row: string) =>
        row.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim())
      const head = cells(t)
      i += 2
      const rows: string[][] = []
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(cells(lines[i]))
        i++
      }
      out.push(
        `<table class="md-table"><thead><tr>${head
          .map((c) => `<th>${inline(c)}</th>`)
          .join("")}</tr></thead><tbody>${rows
          .map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`)
          .join("")}</tbody></table>`,
      )
      continue
    }

    if (/^([-*]|\d+\.)\s+/.test(t)) {
      const ordered = /^\d+\.\s+/.test(t)
      const buf: string[] = []
      while (i < lines.length) {
        const ct = lines[i].trim()
        if (!/^([-*]|\d+\.)\s+/.test(ct)) break
        const task = /^[-*]\s+\[( |x|X)\]\s+(.*)$/.exec(ct)
        if (task) {
          const checked = task[1].toLowerCase() === "x"
          buf.push(
            `<li class="task${checked ? " done" : ""}"><span class="box">${
              checked ? "✓" : ""
            }</span><span class="tx">${inlineWithEmbeds(task[2])}</span></li>`,
          )
        } else {
          buf.push(`<li>${inlineWithEmbeds(ct.replace(/^([-*]|\d+\.)\s+/, ""))}</li>`)
        }
        i++
      }
      flushList(buf, ordered)
      continue
    }

    const buf: string[] = []
    while (i < lines.length) {
      const cur = lines[i].trim()
      if (!cur || /^(#{1,6}\s|[-*]\s|\d+\.\s|>|\||```)/.test(cur)) break
      buf.push(inlineWithEmbeds(cur))
      i++
    }
    out.push(`<p>${buf.join("<br />")}</p>`)
  }

  return out.join("\n")
}

