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

/** 把文件落盘到 files/<卡片id>/，返回相对路径 */
export async function saveAsset(
  project: string,
  nodeId: string,
  name: string,
  data: string,
): Promise<string> {
  if (isDesktop) return cmd<string>('save_asset', { project, nodeId, name, data })
  const r = await fetch(`${API}/asset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project, nodeId, name, data }),
  })
  if (!r.ok) throw new Error(await r.text())
  const j = await r.json()
  return j.rel as string
}

/** 新建项目：目录 + 初始 flow.json */
export async function createProject(name: string, doc: Doc): Promise<void> {
  if (isDesktop) {
    await cmd('create_project', { name, doc })
    return
  }
  const r = await fetch(`${API}/create_project`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, doc }),
  })
  if (!r.ok) throw new Error(await r.text())
}

/** 写一个文本文件（导出网页用）。桌面版返回绝对路径；浏览器里直接下载 */
export async function writeExport(
  project: string,
  fileName: string,
  content: string,
): Promise<string> {
  if (isDesktop) return cmd<string>('write_export', { project, fileName, content })
  const blob = new Blob([content], { type: 'text/html;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = fileName
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 4000)
  return fileName
}

/** 用系统默认程序打开（桌面版） */
export async function openPath(path: string): Promise<void> {
  if (!isDesktop) return
  await cmd('open_path', { path })
}

/** 打开项目里的附件 / 截图 */
export async function openAsset(project: string, rel: string): Promise<void> {
  if (!isDesktop) {
    window.open(fileUrl(project, rel), '_blank')
    return
  }
  await cmd('open_asset', { project, path: rel })
}

