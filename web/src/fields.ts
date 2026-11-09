import type { Field } from './types'

/** 清单条目：老数据是纯字符串，新数据是 {text, done}，这里统一成后者 */
export type ListItem = { text: string; done: boolean }

export function normList(v: any): ListItem[] {
  if (!Array.isArray(v)) return []
  return v
    .map((x) =>
      x && typeof x === 'object'
        ? { text: String(x.text ?? x.name ?? ''), done: Boolean(x.done) }
        : { text: String(x ?? ''), done: false },
    )
    .filter((x) => x.text.trim() !== '')
}

export function optionsOf(f: Field): string[] {
  return Array.isArray(f.options) ? f.options.filter((x) => String(x).trim() !== '') : []
}

export function isMulti(t: string) {
  return t === 'multiselect'
}

/** 字段值的"人类可读"形式，搜索和导出都用 */
export function fieldText(f: Field): string {
  const t = f.type || 'text'
  const v = f.value
  if (t === 'list') return normList(v).map((x) => x.text).join(' ')
  if (t === 'attachment') return (Array.isArray(v) ? v : []).map((m: any) => m?.name || '').join(' ')
  if (t === 'link') return v && typeof v === 'object' ? `${v.text || ''} ${v.url || ''}` : String(v || '')
  if (Array.isArray(v)) return v.join(' ')
  if (v && typeof v === 'object') return Object.values(v).join(' ')
  return String(v ?? '')
}

/** 解析超链接：http(s) 直接开，本地路径（C:\ / \\server\ / file://）交给系统 */
export function parseLink(raw: string): { kind: 'url' | 'path' | 'empty'; href: string } {
  const v = String(raw || '').trim()
  if (!v) return { kind: 'empty', href: '' }
  if (/^file:\/\//i.test(v)) {
    return { kind: 'path', href: decodeURI(v.replace(/^file:\/\//i, '')) }
  }
  if (/^[a-z]:[\\/]/i.test(v) || v.startsWith('\\\\')) {
    return { kind: 'path', href: v }
  }
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(v)) {
    return { kind: 'url', href: v }
  }
  return { kind: 'url', href: `https://${v}` }
}

export function humanSize(bytes: number): string {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
