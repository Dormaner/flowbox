import type { Doc } from './types'

// 桌面版走 Tauri 命令；在浏览器里调试时走本地 bridge.py（同样四个动作）
const API = 'http://127.0.0.1:8765'
const internals = (window as any).__TAURI_INTERNALS__

export const isDesktop = Boolean(internals?.invoke)

async function cmd<T>(name: string, args?: Record<string, unknown>): Promise<T> {
  return internals.invoke(name, args) as Promise<T>
}

export async function listProjects(): Promise<string[]> {
  if (isDesktop) return cmd<string[]>('list_projects')
  const r = await fetch(`${API}/projects`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function loadProject(name: string): Promise<Doc> {
  if (isDesktop) return cmd<Doc>('load_flow', { project: name })
  const r = await fetch(`${API}/flow?project=${encodeURIComponent(name)}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function saveProject(name: string, doc: Doc): Promise<void> {
  if (isDesktop) {
    await cmd('save_flow', { project: name, doc })
    return
  }
  const r = await fetch(`${API}/flow`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project: name, doc }),
  })
  if (!r.ok) throw new Error(await r.text())
}

/** 附件 / 截图在项目 files/ 下，浏览器预览走 bridge，桌面版走 Rust 命令 */
export function fileUrl(project: string, rel: string): string {
  return `${API}/file?project=${encodeURIComponent(project)}&path=${encodeURIComponent(rel)}`
}

export async function fileDataUrl(project: string, rel: string): Promise<string> {
  if (!isDesktop) return fileUrl(project, rel)
  return cmd<string>('file_data_url', { project, path: rel })
}

