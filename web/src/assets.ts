import { saveAsset } from './storage'

const MAX_BYTES = 20 * 1024 * 1024
const MAX_IMG_W = 1600

export const isImageFile = (f: File) => f.type.startsWith('image/')

const baseNoExt = (name: string) => name.replace(/\.[^.]+$/, '')

async function toBase64(blob: Blob): Promise<string> {
  const buf = new Uint8Array(await blob.arrayBuffer())
  let s = ''
  const chunk = 0x8000
  for (let i = 0; i < buf.length; i += chunk) {
    s += String.fromCharCode(...buf.subarray(i, i + chunk))
  }
  return btoa(s)
}

/** 截图先压到 1600 宽 JPEG，不然一个项目很快就几百兆 */
async function compressImage(file: File): Promise<{ name: string; base64: string } | null> {
  if (!isImageFile(file)) return null
  if (file.type === 'image/gif' || file.type === 'image/svg+xml') return null
  const url = URL.createObjectURL(file)
  try {
    const img = await new Promise<HTMLImageElement>((res, rej) => {
      const i = new Image()
      i.onload = () => res(i)
      i.onerror = rej
      i.src = url
    })
    const scale = Math.min(1, MAX_IMG_W / (img.naturalWidth || MAX_IMG_W))
    const w = Math.max(1, Math.round((img.naturalWidth || MAX_IMG_W) * scale))
    const h = Math.max(1, Math.round((img.naturalHeight || 1) * scale))
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, w, h)
    ctx.drawImage(img, 0, 0, w, h)
    const dataUrl = canvas.toDataURL('image/jpeg', 0.82)
    return { name: baseNoExt(file.name) + '.jpg', base64: dataUrl.split(',')[1] }
  } catch {
    return null
  } finally {
    URL.revokeObjectURL(url)
  }
}

export type Saved = { rel: string; name: string; size: number }

export async function uploadFile(
  project: string,
  nodeId: string,
  file: File,
): Promise<Saved> {
  if (file.size > MAX_BYTES) {
    throw new Error(`「${file.name}」超过 20 MB，没上传`)
  }
  if (isImageFile(file) && file.size > 200 * 1024) {
    const c = await compressImage(file)
    if (c) {
      const rel = await saveAsset(project, nodeId, c.name, c.base64)
      return { rel, name: c.name, size: Math.round((c.base64.length * 3) / 4) }
    }
  }
  const rel = await saveAsset(project, nodeId, file.name, await toBase64(file))
  return { rel, name: file.name, size: file.size }
}

/** 从 file 列表里挑：图片走 image 字段，其它走 attachment */
export function splitFiles(files: File[]) {
  return {
    images: files.filter(isImageFile),
    others: files.filter((f) => !isImageFile(f)),
  }
}
