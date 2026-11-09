import type { Doc, FlowNode, Status } from './types'
import { fieldText, normList, optionsOf, parseLink } from './fields'
import { CARD_H, CARD_W, edgePath, pathMid } from './geometry'
import { fileDataUrl } from './storage'

const esc = (s: any) =>
  String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

const baseName = (rel: string) => (rel.split(/[\\/]/).pop() || rel).replace(/\.[^.]+$/, '')

/** 把图片读成 data URL，导出后不依赖任何外部文件 */
async function inlineImages(project: string, doc: Doc): Promise<Record<string, string>> {
  const rels = new Set<string>()
  for (const n of doc.nodes) {
    for (const f of n.fields || []) {
      if (f.type === 'image') {
        for (const r of Array.isArray(f.value) ? f.value : []) rels.add(String(r))
      } else if (f.type === 'attachment') {
        for (const m of Array.isArray(f.value) ? f.value : []) {
          const rel = String((m as any)?.file || '')
          if (/\.(png|jpe?g|gif|webp|bmp)$/i.test(rel)) rels.add(rel)
        }
      }
    }
  }
  const out: Record<string, string> = {}
  for (const rel of rels) {
    try {
      out[rel] = await fileDataUrl(project, rel)
    } catch {
      /* 读不到就留空 */
    }
  }
  return out
}

function fieldHtml(f: any, images: Record<string, string>): string {
  const t = f?.type || 'text'
  const v = f?.value
  const label = `<div class="fl">${esc(f?.label || '')}</div>`

  if (t === 'image') {
    const items: any[] = Array.isArray(v) ? v : []
    if (!items.length) return label + '<div class="vempty">—</div>'
    const cells = items
      .map((m) => {
        const rel = String(m)
        const src = images[rel] || ''
        const name = baseName(rel)
        return `<div class="imgcell">${
          src
            ? `<img class="imgsrc" src="${src}" alt="">`
            : '<div class="imgsrc ph"></div>'
        }<span class="imgname">${esc(name)}</span></div>`
      })
      .join('')
    return label + `<div class="assets">${cells}</div>`
  }

  if (t === 'attachment') {
    const items: any[] = Array.isArray(v) ? v : []
    if (!items.length) return label + '<div class="vempty">—</div>'
    const rows = items
      .map((m) => {
        const rel = String(m?.file || '')
        const mark = `<span class="mk${m?.done ? ' ok' : ''}">${m?.done ? '✓' : '○'}</span>`
        return `<div class="ar">${mark}<span class="an">${esc(m?.name || baseName(rel))}</span></div>`
      })
      .join('')
    return label + `<div class="assets">${rows}</div>`
  }

  if (t === 'list') {
    const items = normList(v)
    if (!items.length) return label + '<div class="vempty">—</div>'
    return (
      label +
      '<div class="assets">' +
      items
        .map(
          (it) =>
            `<div class="vr"><span class="mk${it.done ? ' ok' : ''}">${it.done ? '✓' : '○'}</span><span class="vt${it.done ? ' done' : ''}">${esc(it.text)}</span></div>`,
        )
        .join('') +
      '</div>'
    )
  }

  if (t === 'select' || t === 'multiselect') {
    const opts = optionsOf(f)
    const sel = Array.isArray(v) ? v.map(String) : v ? [String(v)] : []
    const all = opts.length ? opts : sel
    if (!all.length) return label + '<div class="vempty">—</div>'
    const tags = all
      .map((o) => `<span class="tag${sel.includes(o) ? ' on' : ''}">${esc(o)}</span>`)
      .join('')
    return label + `<div class="tags">${tags}</div>`
  }

  if (t === 'link') {
    const obj = v && typeof v === 'object' ? v : { url: String(v || ''), text: '' }
    const { kind, href } = parseLink(obj.url)
    if (kind === 'empty') return label + '<div class="vempty">—</div>'
    const label2 =
      obj.text ||
      (kind === 'path' ? href.split(/[\\/]/).pop() : href.replace(/^https?:\/\//, ''))
    if (kind === 'path') {
      return (
        label +
        `<span class="vbtn ghost" title="${esc(href)}">${esc(label2)}（本地文件）</span>`
      )
    }
    return label + `<a class="vbtn" href="${esc(href)}" target="_blank" rel="noreferrer">${esc(label2)} ↗</a>`
  }

  if (t === 'checkbox') {
    return label + `<div class="${v ? 'vbool yes' : 'vbool'}">${v ? '✓ 是' : '— 否'}</div>`
  }

  const text = String(v ?? '').trim()
  if (!text) return label + '<div class="vempty">—</div>'
  if (t === 'number') {
    const n = Number(text.replace(/[,\s]/g, ''))
    const shown = Number.isFinite(n) ? n.toLocaleString('zh-CN') : text
    return label + `<div class="vnum">${esc(shown)}</div>`
  }
  return label + `<div class="vtext">${esc(text)}</div>`
}

const PAD = 70

const EXPORT_CSS = `
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{font:14px/1.6 "Microsoft YaHei UI","PingFang SC",system-ui,sans-serif;color:#1f2329;
 background-color:#fbfbfc;display:flex;flex-direction:column;overflow:hidden;
 background-image:
  linear-gradient(#eef1f4 1px,transparent 1px),
  linear-gradient(90deg,#eef1f4 1px,transparent 1px),
  linear-gradient(#e4e8ec 1px,transparent 1px),
  linear-gradient(90deg,#e4e8ec 1px,transparent 1px);
 background-size:22px 22px,22px 22px,110px 110px,110px 110px}
header{display:flex;align-items:center;gap:12px;padding:9px 16px;background:#fff;
 border-bottom:1px solid #e6e8eb;flex:0 0 auto;z-index:5}
.h1{font-size:15px;font-weight:600}
.meta{font-size:12.5px;color:#8a94a6}
.sp{flex:1}
.search{display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:8px;background:#f2f3f5}
.search input{border:0;outline:0;background:transparent;font:inherit;font-size:13px;width:190px}
.zoom{display:flex;align-items:center;gap:2px;padding:2px;border-radius:8px;background:#f2f3f5}
.zoom button{font:inherit;font-size:12.5px;border:0;background:transparent;padding:4px 8px;
 border-radius:6px;cursor:pointer;color:#3f4652}
.zoom button:hover{background:#e4e6ea}
#pct{min-width:44px;text-align:center;font-size:12px;color:#6b7280}
#legend{display:flex;gap:14px;padding:6px 16px;background:#fff;border-bottom:1px solid #eef0f2;
 font-size:12px;color:#5b6373;flex:0 0 auto}
#legend i{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px}
#legend b{color:#1f2329}
main{position:relative;flex:1;min-height:0;overflow:hidden;cursor:grab}
main.drag{cursor:grabbing}
#world{position:absolute;left:0;top:0;transform-origin:0 0}
#edges{position:absolute;left:0;top:0;overflow:visible}
.edge{fill:none;stroke:#8a94a6;stroke-width:1.8;transition:opacity .15s,stroke .15s}
.edge.dim{opacity:.1}
.edge.hl{stroke:#2563eb;stroke-width:2.4}
.elab{font-size:11px;fill:#5b6373;text-anchor:middle;paint-order:stroke;stroke:#fbfbfc;stroke-width:4px}
.card{position:absolute;width:190px;height:88px;padding:10px 12px;background:#fff;
 border:1px solid #e3e5e8;border-radius:12px;cursor:pointer;
 box-shadow:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.04);
 transition:box-shadow .16s,border-color .16s,transform .16s}
.card:hover{transform:translateY(-1px);border-color:#c3cbd6;box-shadow:0 6px 18px rgba(16,24,40,.12)}
.card.hl{border-color:#2563eb;box-shadow:0 0 0 3px #e0e7ff,0 6px 18px rgba(37,99,235,.16)}
.card.dim{opacity:.25}
.card.hit{border-color:#f59e0b;box-shadow:0 0 0 3px #fef3c7}
.ct{font-size:13px;font-weight:600;line-height:1.35;max-height:2.7em;overflow:hidden;padding-right:10px}
.cs{margin-top:3px;font-size:11.5px;line-height:1.4;color:#6b7280;max-height:2.8em;overflow:hidden}
.dot{position:absolute;top:9px;right:9px;width:8px;height:8px;border-radius:50%}
#panel{position:absolute;top:0;right:0;bottom:0;width:min(400px,86vw);background:#fff;
 border-left:1px solid #e6e8eb;box-shadow:-12px 0 34px rgba(16,24,40,.1);overflow:auto;
 padding:18px 20px 40px;transform:translateX(103%);transition:transform .22s;z-index:4}
#panel.open{transform:none}
#pclose{position:absolute;top:8px;right:12px;border:0;background:transparent;font-size:15px;
 color:#9aa1aa;cursor:pointer}
.ptitle{font-size:16px;font-weight:600}
.psum{font-size:12.5px;color:#6b7280;margin-top:2px;white-space:pre-wrap}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;padding:3px 9px;
 border-radius:20px;background:#f4f5f7;color:#3f4652;margin-top:8px}
.chip i{width:7px;height:7px;border-radius:50%}
.fl{font-size:11px;color:#8a94a6;margin-top:14px}
.vtext{font-size:13px;white-space:pre-wrap;word-break:break-word}
.vtext.done{color:#9aa1aa;text-decoration:line-through}
.vnum{font-size:13px;text-align:right;font-variant-numeric:tabular-nums}
.vbool{font-size:12.5px;color:#9aa1aa}
.vbool.yes{color:#15803d;font-weight:600}
.vempty{font-size:12.5px;color:#c3c9d2}
.vbtn{display:inline-flex;align-items:center;gap:4px;margin-top:4px;padding:4px 12px;font-size:12.5px;
 color:#fff;background:#2563eb;border-radius:7px;text-decoration:none}
.assets{display:flex;flex-direction:column;gap:6px;margin-top:4px}
.ar,.vr{display:flex;align-items:center;gap:8px;font-size:12.5px;padding:2px 0}
.imgcell{position:relative}
.imgsrc{display:block;width:100%;border-radius:8px;border:1px solid #e6e8eb;background:#f2f3f5}
.imgsrc.ph{height:90px}
.imgname{position:absolute;right:6px;bottom:6px;max-width:calc(100% - 16px);font-size:10.5px;
 color:#fff;background:rgba(17,24,39,.62);padding:1px 7px;border-radius:6px;overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap}
.vbtn.ghost{background:#eef2ff;color:#1e40af;cursor:default}
.mk{width:16px;text-align:center;color:#b9c0cb;flex:0 0 auto}
.mk.ok{color:#15803d}
.an{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
.tag{font-size:12px;padding:3px 10px;border-radius:14px;border:1px solid #e6e8eb;
 background:#fafbfc;color:#9aa1aa}
.tag.on{background:#eef2ff;border-color:#b9c9fb;color:#1e40af;font-weight:600}
footer{padding:8px 16px;background:#fff;border-top:1px solid #eef0f2;font-size:11.5px;
 color:#9aa1aa;flex:0 0 auto}
@media print{header,#legend,footer,#panel{display:none!important}}
`

const EXPORT_JS = `
(function(){
  var W=__W__, H=__H__, E=__E__;
  var main=document.getElementById('m'), world=document.getElementById('w');
  var s=1,tx=0,ty=0;
  function apply(){ world.style.transform='translate('+tx+'px,'+ty+'px) scale('+s+')';
    document.getElementById('pct').textContent=Math.round(s*100)+'%'; }
  function fit(){ var r=main.getBoundingClientRect();
    s=Math.max(0.2,Math.min((r.width-80)/W,(r.height-80)/H,1.1));
    tx=(r.width-W*s)/2; ty=(r.height-H*s)/2; apply(); }
  function zoomAt(f,cx,cy){ var ns=Math.max(0.2,Math.min(2.6,s*f));
    if(Math.abs(ns-s)<1e-4) return;
    if(cx==null){ cx=main.clientWidth/2; cy=main.clientHeight/2; }
    tx=cx-(cx-tx)*(ns/s); ty=cy-(cy-ty)*(ns/s); s=ns; apply(); }
  main.addEventListener('wheel',function(e){ e.preventDefault();
    var r=main.getBoundingClientRect();
    zoomAt(Math.exp(-e.deltaY*0.0016), e.clientX-r.left, e.clientY-r.top); },{passive:false});
  var drag=null;
  main.addEventListener('pointerdown',function(e){ if(e.target.closest('.card')) return;
    drag={x:e.clientX-tx,y:e.clientY-ty}; main.classList.add('drag'); });
  window.addEventListener('pointermove',function(e){ if(!drag) return;
    tx=e.clientX-drag.x; ty=e.clientY-drag.y; apply(); });
  window.addEventListener('pointerup',function(){ drag=null; main.classList.remove('drag'); });
  var nxt={},prv={};
  E.forEach(function(p){ (nxt[p[0]]=nxt[p[0]]||[]).push(p[1]); (prv[p[1]]=prv[p[1]]||[]).push(p[0]); });
  function bfs(k,map){ var seen={},st=[k];
    while(st.length){ var c=st.pop(); (map[c]||[]).forEach(function(x){ if(!seen[x]){seen[x]=1;st.push(x);} }); }
    delete seen[k]; return seen; }
  function clearAll(){
    document.querySelectorAll('.card').forEach(function(el){ el.classList.remove('hl','dim'); });
    document.querySelectorAll('.edge').forEach(function(el){ el.classList.remove('hl','dim'); });
    document.getElementById('panel').classList.remove('open'); }
  function select(k){
    var F=bfs(k,nxt), B=bfs(k,prv), keep={}; keep[k]=1;
    Object.keys(F).forEach(function(x){ keep[x]=1; });
    Object.keys(B).forEach(function(x){ keep[x]=1; });
    document.querySelectorAll('.card').forEach(function(el){ var kk=+el.dataset.k;
      el.classList.toggle('hl',kk===k); el.classList.toggle('dim',!keep[kk]); });
    document.querySelectorAll('.edge').forEach(function(el){ var a=+el.dataset.a, b=+el.dataset.b;
      var on=((a===k)||(a in B))&&((b===k)||(b in F));
      el.classList.toggle('hl',on); el.classList.toggle('dim',!on); });
    var tpl=document.getElementById('t'+k), body=document.getElementById('pbody');
    body.innerHTML=''; if(tpl) body.appendChild(tpl.content.cloneNode(true));
    document.getElementById('panel').classList.add('open'); }
  document.querySelectorAll('.card').forEach(function(el){
    el.addEventListener('click',function(e){ e.stopPropagation(); select(+el.dataset.k); }); });
  main.addEventListener('click',function(e){ if(!e.target.closest('.card')) clearAll(); });
  document.getElementById('pclose').onclick=clearAll;
  document.getElementById('z-in').onclick=function(){ zoomAt(1.2); };
  document.getElementById('z-out').onclick=function(){ zoomAt(1/1.2); };
  document.getElementById('z-fit').onclick=fit;
  document.getElementById('z-one').onclick=function(){ zoomAt(1/s); };
  var q=document.getElementById('q');
  q.addEventListener('input',function(){ var v=q.value.trim().toLowerCase();
    document.querySelectorAll('.card').forEach(function(el){
      el.classList.toggle('hit', !!v && (el.dataset.s||'').indexOf(v)>=0); }); });
  document.addEventListener('keydown',function(e){ if(e.target.tagName==='INPUT') return;
    if(e.key==='/'){ e.preventDefault(); q.focus(); }
    else if(e.key==='Escape'){ clearAll(); } });
  fit();
})();
`

export async function buildExportHtml(
  doc: Doc,
  project: string,
  statuses: Status[],
): Promise<string> {
  const images = await inlineImages(project, doc)
  const nodes: FlowNode[] = (doc.nodes || []).slice().sort((a, b) => a.x - b.x || a.y - b.y)
  const index: Record<string, number> = {}
  nodes.forEach((n, i) => {
    index[n.id] = i
  })

  const xs = nodes.length ? nodes.map((n) => n.x) : [0]
  const ys = nodes.length ? nodes.map((n) => n.y) : [0]
  const x1 = Math.min(...xs) - PAD
  const y1 = Math.min(...ys) - PAD
  const x2 = Math.max(...nodes.map((n) => n.x + CARD_W), 320) + PAD
  const y2 = Math.max(...nodes.map((n) => n.y + CARD_H), 200) + PAD
  const ox = -x1
  const oy = -y1
  const W = Math.max(x2 - x1, 400)
  const H = Math.max(y2 - y1, 300)

  const stOf = (n: FlowNode) =>
    statuses.find((s) => s.key === (n.state || statuses[0]?.key)) || statuses[0]

  const cards = nodes
    .map((n, i) => {
      const st = stOf(n)
      const hay = [n.name, n.summary, ...(n.fields || []).map((f) => `${f.label} ${fieldText(f)}`)]
        .join(' ')
        .toLowerCase()
      return `<div class="card" data-k="${i}" data-s="${esc(hay)}" style="left:${n.x + ox}px;top:${n.y + oy}px"><div class="ct">${esc(n.name || '未命名')}</div><div class="cs">${esc(n.summary || '')}</div><i class="dot" style="background:${esc(st?.color || '#C7CBD1')}"></i></div>`
    })
    .join('')

  const tpls = nodes
    .map((n, i) => {
      const st = stOf(n)
      const fields = (n.fields || []).map((f) => fieldHtml(f, images)).join('')
      const sum = n.summary ? `<div class="psum">${esc(n.summary)}</div>` : ''
      return `<template id="t${i}"><div class="ptitle">${esc(n.name || '未命名')}</div>${sum}<span class="chip"><i style="background:${esc(st?.color || '#C7CBD1')}"></i>${esc(st?.label || '')}</span>${fields}</template>`
    })
    .join('')

  const paths: string[] = []
  const pairs: number[][] = []
  for (const e of doc.edges || []) {
    const ia = index[e.a]
    const ib = index[e.b]
    if (ia === undefined || ib === undefined) continue
    const A = nodes[ia]
    const B = nodes[ib]
    const sx = A.x + CARD_W + ox
    const sy = A.y + CARD_H / 2 + oy
    const tx = B.x + ox
    const ty = B.y + CARD_H / 2 + oy
    paths.push(`<path class="edge" data-a="${ia}" data-b="${ib}" d="${edgePath(sx, sy, tx, ty)}"/>`)
    pairs.push([ia, ib])
    if (e.label) {
      const [mx, my] = pathMid(sx, sy, tx, ty)
      paths.push(
        `<text class="elab" x="${mx.toFixed(1)}" y="${(my - 6).toFixed(1)}">${esc(e.label)}</text>`,
      )
    }
  }

  const legend = statuses
    .map((s) => {
      const n = nodes.filter((x) => (x.state || statuses[0]?.key) === s.key).length
      return `<span><i style="background:${esc(s.color)}"></i>${esc(s.label)} <b>${n}</b></span>`
    })
    .join('')

  const meta = `${nodes.length} 步 · ${pairs.length} 条连线 · 导出于 ${new Date().toLocaleString('zh-CN')}`
  const js = EXPORT_JS.replace('__W__', String(Math.round(W)))
    .replace('__H__', String(Math.round(H)))
    .replace('__E__', JSON.stringify(pairs))

  return `<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(project)} · 流程</title><style>${EXPORT_CSS}</style></head><body>
<header><div class="h1">${esc(project)}</div><div class="meta">${esc(meta)}</div><span class="sp"></span>
<label class="search">⌕<input id="q" placeholder="搜步骤、字段、材料"></label>
<div class="zoom"><button id="z-out">−</button><span id="pct">100%</span><button id="z-in">＋</button><button id="z-fit">适应</button><button id="z-one">1:1</button></div></header>
<div id="legend">${legend}</div>
<main id="m"><div id="w"><svg id="edges" width="${Math.round(W)}" height="${Math.round(H)}">${paths.join('')}</svg>${cards}${tpls}</div></main>
<aside id="panel"><button id="pclose">✕</button><div id="pbody"></div></aside>
<footer>由「流程盒子」导出 · 只读 · 滚轮缩放 · 拖动平移 · 点卡片看这一步的材料</footer>
<script>${js}</script></body></html>`
}



