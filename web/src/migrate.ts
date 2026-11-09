import type { Field, FlowNode } from './types'
import { normList, parseLink } from './fields'

/** 老字段 → Markdown。只跑一次，跑完 fields 就不用了 */
export function fieldsToMarkdown(node: FlowNode): string {
  const fields: Field[] = node.fields || []
  const head: string[] = []
  const parts: string[] = []

  for (const f of fields) {
    const label = (f.label || '').trim()
    const t = f.type || 'text'
    const v = f.value

    if (t === 'text' || t === 'longtext' || t === 'number') {
      const s = String(v ?? '').trim()
      if (!s) continue
      if (/^(负责人|经办人?|谁)$/.test(label)) head.push(`owner: ${s}`)
      else if (/^(截止|截止日期)$/.test(label)) head.push(`due: ${s}`)
      else {
        if (label) parts.push(`## ${label}`)
        parts.push(s)
      }
      continue
    }

    if (t === 'date' || t === 'user' || t === 'select') {
      const s = String(v ?? '').trim()
      if (!s) continue
      if (/^(负责人|经办人?|谁)$/.test(label)) head.push(`owner: ${s}`)
      else if (/^(截止|截止日期)$/.test(label)) head.push(`due: ${s}`)
      else parts.push(`## ${label}\n${s}`)
      continue
    }

    if (t === 'multiselect' || t === 'list') {
      const items = t === 'list' ? normList(v).map((x) => ({ text: x.text, done: x.done })) : (Array.isArray(v) ? v : []).map((x) => ({ text: String(x), done: false }))
      if (!items.length) continue
      parts.push(`## ${label}`)
      for (const it of items) {
        const box = t === 'list' && it.done ? '[x]' : '[ ]'
        const line = t === 'list' ? `- ${box} ${it.text}` : `- ${it.text}`
        parts.push(line)
      }
      continue
    }

    if (t === 'checkbox') {
      parts.push(`- [${v ? 'x' : ' '}] ${label || '是'}`)
      continue
    }

    if (t === 'attachment') {
      const items = Array.isArray(v) ? v : []
      if (!items.length) continue
      parts.push(`## ${label}`)
      for (const m of items) {
        const nm = (m && m.name) || '附件'
        const rel = (m && m.file) || ''
        const box = m && m.done ? '[x]' : '[ ]'
        parts.push(`- ${box} ${nm}${rel ? ` ![[${rel}]]` : ''}`)
      }
      continue
    }

    if (t === 'image') {
      const items = Array.isArray(v) ? v : []
      if (!items.length) continue
      if (label) parts.push(`## ${label}`)
      for (const rel of items) parts.push(`![[${rel}]]`)
      continue
    }

    if (t === 'link') {
      const { kind, href } = parseLink(String((v && v.url) || v || ''))
      if (kind === 'empty') continue
      const text = (v && v.text) || href
      parts.push(`## ${label}\n[${text}](${href})`)
      continue
    }
  }

  const text = parts.join('\n\n').trim()
  if (head.length) return `---\n${head.join('\n')}\n---\n\n${text}`
  return text
}

/** 有 body 就用 body；没有就用老字段现算一份（不落盘，等第一次编辑再存） */
export function bodyOf(node: FlowNode): string {
  if (typeof node.body === 'string' && node.body.trim()) return node.body
  if (node.fields && node.fields.length) return fieldsToMarkdown(node)
  return node.summary || ''
}
