"""只读网页导出：把 flow.json 画成一张能缩放、能搜索的图。

canvas_demo.py 负责算几何（edge_points 已经把拐角磨圆了），这里只管排版和交互，
所以网页里的连线和编辑器里长得一模一样。

对外只有一个函数：render(name, data, statuses, proj_dir, edges_geo)
"""

from __future__ import annotations

import base64
import html as H
import io
import mimetypes
import re
from pathlib import Path

# 跟 canvas_demo 里的卡片尺寸保持一致，否则连线端点会飘
CARD_W, CARD_H = 190, 88

PAD = 70            # 画布四周留白
MAX_IMG_W = 1200    # 截图先压到 1200 宽再内嵌，不然一张 3MB 的 PNG 发不动
IMG_QUALITY = 82
ATTACH_MAX = 4 * 1024 * 1024        # 单个附件内嵌上限
ATTACH_BUDGET = 12 * 1024 * 1024    # 所有附件加起来的上限


def _esc(s) -> str:
    return H.escape("" if s is None else str(s))


def _mime(p: Path) -> str:
    return mimetypes.guess_type(str(p))[0] or "application/octet-stream"


def _img_uri(fp: Path) -> str:
    """图片压成 JPEG 再内嵌。失败就原样塞进去。"""
    try:
        from PIL import Image
        im = Image.open(fp)
        im.load()
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, "white")
            bg.paste(im, mask=im.split()[-1])
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")
        if im.width > MAX_IMG_W:
            h = max(1, round(im.height * MAX_IMG_W / im.width))
            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
            im = im.resize((MAX_IMG_W, h), resample)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=IMG_QUALITY, optimize=True,
                progressive=True)
        return "data:image/jpeg;base64," + base64.b64encode(
            buf.getvalue()).decode()
    except Exception:
        pass
    try:
        return f"data:{_mime(fp)};base64," + base64.b64encode(
            fp.read_bytes()).decode()
    except Exception:
        return ""


def _dl_link(fp: Path, budget: dict) -> str:
    """附件内嵌成下载链接，太大的就只报个体积。"""
    try:
        size = fp.stat().st_size
    except OSError:
        return ""
    if size > ATTACH_MAX or size > budget["left"]:
        mb = size / 1048576
        return f'<span class="toolarge">{mb:.1f} MB，未内嵌</span>'
    try:
        raw = fp.read_bytes()
    except OSError:
        return ""
    budget["left"] -= size
    return (f'<a class="dl" download="{_esc(fp.name)}" '
            f'href="data:{_mime(fp)};base64,'
            f'{base64.b64encode(raw).decode()}">下载</a>')


def _link_parts(f: dict) -> tuple[str, str]:
    """跟 canvas_demo.link_parts 一个意思：老数据是纯字符串也认，没写协议补 https。"""
    v = f.get("value")
    label = f.get("label") or "打开"
    if isinstance(v, dict):
        url = str(v.get("url") or "").strip()
        text = str(v.get("text") or "").strip()
    else:
        url = str(v or "").strip()
        text = ""
    if url and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "https://" + url
    return url, (text or f.get("open_label") or label)


def _search_text(n: dict) -> str:
    """搜索用的扁平文本：名字、说明、字段名、字段值、材料名全塞进去。"""
    parts = [str(n.get("name") or ""), str(n.get("summary") or "")]
    for f in n.get("fields") or []:
        parts.append(str(f.get("label") or ""))
        v = f.get("value")
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    parts += [str(x.get("name") or ""), str(x.get("hint") or "")]
                else:
                    parts.append(str(x))
        elif isinstance(v, dict):
            parts += [str(v.get("url") or ""), str(v.get("text") or "")]
        else:
            parts.append(str(v or ""))
    return " ".join(p for p in parts if p).lower()


def _state(n: dict, statuses: list) -> tuple[str, str, str]:
    key = n.get("state") or (statuses[0]["key"] if statuses else "todo")
    for s in statuses:
        if s.get("key") == key:
            return key, s.get("label", key), s.get("color", "#C7CBD1")
    return key, key, "#C7CBD1"


def _fields_html(n: dict, proj: Path, budget: dict) -> str:
    out = []
    for f in n.get("fields") or []:
        t = f.get("type", "text")
        label = _esc(f.get("label") or "未命名字段")
        val = f.get("value")
        hint = f'<div class="fh">{_esc(f["hint"])}</div>' if f.get("hint") else ""

        if t in ("text", "number", "date", "user", "select", "longtext"):
            v = str(val or "").strip()
            if not v:
                continue
            out.append(f'<div class="f"><div class="fl">{label}</div>'
                       f'<div class="fv">{_esc(v)}</div>{hint}</div>')

        elif t in ("multiselect", "list"):
            items = val if isinstance(val, list) else []
            items = [str(x) for x in items if str(x).strip()]
            if not items:
                continue
            out.append(f'<div class="f"><div class="fl">{label} · {len(items)} 条</div>'
                       '<ul class="items">'
                       + "".join(f"<li>{_esc(x)}</li>" for x in items)
                       + '</ul></div>')

        elif t == "attachment":
            items = [m for m in (val if isinstance(val, list) else [])
                     if isinstance(m, dict)]
            if not items:
                continue
            done = sum(1 for m in items if m.get("done"))
            rows = []
            for m in items:
                mk = "✓" if m.get("done") else "○"
                nm = _esc(m.get("name") or "（未命名材料）")
                mh = (f'<span class="mh">{_esc(m["hint"])}</span>'
                      if m.get("hint") else "")
                rel = str(m.get("file") or "")
                fp = proj / rel if rel else None
                extra = _dl_link(fp, budget) if fp and fp.is_file() else ""
                rows.append(f'<li class="{"ok" if m.get("done") else ""}">'
                            f'<span class="mk">{mk}</span>'
                            f'<span class="mt">{nm}{mh}</span>{extra}</li>')
            out.append(f'<div class="f"><div class="fl">{label} · {done}/{len(items)}</div>'
                       '<ul class="mat">' + "".join(rows) + '</ul></div>')

        elif t == "image":
            shots = []
            for rel in (val or [])[:8]:
                fp = proj / str(rel)
                if fp.is_file():
                    u = _img_uri(fp)
                    if u:
                        shots.append(f'<img class="shot" src="{u}" alt="">')
            if shots:
                out.append(f'<div class="f"><div class="fl">{label} · {len(shots)} 张</div>'
                           '<div class="shots">' + "".join(shots) + '</div></div>')

        elif t == "link":
            url, text = _link_parts(f)
            if url:
                out.append(f'<div class="f"><div class="fl">{label}</div>'
                           f'<div class="fv"><a class="go" href="{_esc(url)}"'
                           f' target="_blank" rel="noreferrer">{_esc(text)} ↗</a></div></div>')

        elif t == "checkbox":
            out.append(f'<div class="f"><div class="fl">{label}</div>'
                       f'<div class="fv">{"是" if val else "否"}</div></div>')

    return "".join(out)


def _card_html(k: int, n: dict, statuses: list, ox: float, oy: float) -> str:
    _key, lab, col = _state(n, statuses)
    return (f'<div class="card" id="c{k}" data-k="{k}" '
            f'data-s="{_esc(_search_text(n))}" '
            f'style="left:{n["x"] + ox}px;top:{n["y"] + oy}px">'
            f'<div class="ttl">{_esc(n.get("name") or "未命名")}</div>'
            f'<div class="sum">{_esc(n.get("summary") or "")}</div>'
            f'<i class="dot" style="background:{col}" title="{_esc(lab)}"></i>'
            f'<i class="idx">{k + 1}</i>'
            f'</div>')


def _article_html(k: int, n: dict, statuses: list, proj: Path,
                  budget: dict) -> str:
    _key, lab, col = _state(n, statuses)
    out = [f'<article class="stp" id="a{k}" data-k="{k}" '
           f'data-s="{_esc(_search_text(n))}">',
           '<div class="shi">',
           f'<span class="chip" style="color:{col}">● {_esc(lab)}</span>',
           f'<span class="no">第 {k + 1} 步</span>',
           '</div>',
           f'<h2>{_esc(n.get("name") or "未命名")}</h2>']
    if n.get("summary"):
        out.append(f'<p class="sum">{_esc(n["summary"])}</p>')
    out.append(_fields_html(n, proj, budget))
    out.append('</article>')
    return "".join(out)


def _mid(pts: list) -> tuple[float, float]:
    """折线总长一半处的点，连线标签放这儿最不容易压到别的线。"""
    if len(pts) < 4:
        return (pts[0], pts[1]) if len(pts) >= 2 else (0.0, 0.0)
    segs, total = [], 0.0
    for k in range(0, len(pts) - 2, 2):
        d = ((pts[k + 2] - pts[k]) ** 2
             + (pts[k + 3] - pts[k + 1]) ** 2) ** 0.5
        segs.append((d, k))
        total += d
    half, acc = total / 2, 0.0
    for d, k in segs:
        if acc + d >= half:
            t = 0.0 if d <= 1e-9 else (half - acc) / d
            return (pts[k] + (pts[k + 2] - pts[k]) * t,
                    pts[k + 1] + (pts[k + 3] - pts[k + 1]) * t)
        acc += d
    return pts[0], pts[1]


def _edges_svg(edges_geo: list, index: dict, ox: float, oy: float,
               w: float, h: float) -> tuple[str, list]:
    """返回 (svg 片段, 给 JS 用的 [[a,b],...])。"""
    paths, pairs = [], []
    for e in edges_geo:
        ka, kb = index.get(e.get("a")), index.get(e.get("b"))
        pts = e.get("pts") or []
        if ka is None or kb is None or len(pts) < 4:
            continue
        pairs.append([ka, kb])
        d = "M " + " L ".join(
            f"{pts[i] + ox:.1f} {pts[i + 1] + oy:.1f}"
            for i in range(0, len(pts) - 1, 2))
        paths.append(f'<path class="edge" data-e="{len(pairs) - 1}" '
                     f'data-a="{ka}" data-b="{kb}" d="{d}"/>')
        lab = str(e.get("label") or "").strip()
        if lab:
            mx, my = _mid(pts)
            paths.append(f'<text class="elab" data-a="{ka}" data-b="{kb}" '
                         f'x="{mx + ox:.1f}" y="{my + oy - 5:.1f}">'
                         f'{_esc(lab)}</text>')
    svg = (f'<svg id="edges" width="{w:.0f}" height="{h:.0f}" '
           f'viewBox="0 0 {w:.0f} {h:.0f}">'
           '<defs><marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" '
           'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
           '<path d="M0,0 L10,5 L0,10 z" fill="#3C4149"/></marker></defs>'
           + "".join(paths) + '</svg>')
    return svg, pairs


def _groups_html(data: dict, by_id: dict, index: dict, ox: float,
                 oy: float) -> str:
    out = []
    for g in data.get("groups") or []:
        ids = [i for i in (g.get("members") or []) if i in by_id]
        mem = [by_id[i] for i in ids]
        if not mem:
            continue
        x1 = min(m["x"] for m in mem) - 16 + ox
        y1 = min(m["y"] for m in mem) - 34 + oy
        x2 = max(m["x"] + CARD_W for m in mem) + 16 + ox
        y2 = max(m["y"] + CARD_H for m in mem) + 16 + oy
        col = g.get("color") or "#EAF1FE"
        ks = ",".join(str(index[i]) for i in ids)
        out.append(f'<div class="grp" data-k="{ks}" '
                   f'style="left:{x1:.0f}px;top:{y1:.0f}px;'
                   f'width:{x2 - x1:.0f}px;height:{y2 - y1:.0f}px;'
                   f'background:{_esc(col)}">'
                   f'<span>{_esc(g.get("name") or "组")}</span></div>')
    return "".join(out)


def _legend_html(statuses: list, nodes: list) -> str:
    out = []
    for s in statuses:
        n = sum(1 for x in nodes if (x.get("state") or statuses[0]["key"]) == s["key"])
        out.append(f'<span class="lg"><i style="background:'
                   f'{_esc(s.get("color") or "#C7CBD1")}"></i>'
                   f'{_esc(s.get("label") or s["key"])}'
                   f'<b>{n}</b></span>')
    return "".join(out)


def render(name: str, data: dict, statuses: list, proj_dir, edges_geo: list) -> str:
    """把项目和几何拼成一个自包含的 HTML 字符串。"""
    proj = Path(proj_dir)
    statuses = statuses or [{"key": "todo", "label": "未开始", "color": "#C7CBD1"}]
    nodes = sorted(data.get("nodes") or [],
                   key=lambda n: (n.get("x", 0), n.get("y", 0)))
    by_id = {n.get("id"): n for n in nodes}
    index = {n.get("id"): k for k, n in enumerate(nodes)}
    budget = {"left": ATTACH_BUDGET}

    xs = [n.get("x", 0) for n in nodes] or [0]
    ys = [n.get("y", 0) for n in nodes] or [0]
    x1 = min(xs) - PAD
    y1 = min(ys) - PAD
    x2 = max(n.get("x", 0) + CARD_W for n in nodes) + PAD
    y2 = max(n.get("y", 0) + CARD_H for n in nodes) + PAD
    ox, oy = -x1, -y1
    w, h = max(x2 - x1, 400), max(y2 - y1, 300)

    svg, pairs = _edges_svg(edges_geo or [], index, ox, oy, w, h)
    cards = "".join(_card_html(k, n, statuses, ox, oy)
                    for k, n in enumerate(nodes))
    arts = "".join(_article_html(k, n, statuses, proj, budget)
                   for k, n in enumerate(nodes))

    import json as _json
    import time as _time
    meta = (f"{len(nodes)} 步 · {len(pairs)} 条连线 · "
            f"{_time.strftime('%Y-%m-%d %H:%M')}")

    return (_TEMPLATE
            .replace("@@TITLE@@", _esc(name))
            .replace("@@META@@", _esc(meta))
            .replace("@@LEGEND@@", _legend_html(statuses, nodes))
            .replace("@@W@@", f"{w:.0f}")
            .replace("@@H@@", f"{h:.0f}")
            .replace("@@GROUPS@@", _groups_html(data, by_id, index, ox, oy))
            .replace("@@SVG@@", svg)
            .replace("@@CARDS@@", cards)
            .replace("@@ARTICLES@@", arts)
            .replace("@@EDGES@@", _json.dumps(pairs)))


# ---------------------------------------------------------------- 网页模板
# 拆成几段拼接，纯粹是为了每个字符串别太长，好看也好改。

_T1 = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>@@TITLE@@ · 流程</title>
<style>
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{display:flex;flex-direction:column;overflow:hidden;background:#f7f8fa;color:#1f2329;
 font:14px/1.6 "Microsoft YaHei UI","PingFang SC",system-ui,sans-serif;
 -webkit-font-smoothing:antialiased}
header{display:flex;align-items:center;flex-wrap:wrap;gap:12px;flex:0 0 auto;z-index:5;
 padding:9px 16px;background:#fff;border-bottom:1px solid #e6e8eb}
.h1{font-size:15px;font-weight:600}
.meta{font-size:12.5px;color:#8a94a6}
.sp{flex:1}
.search{display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:8px;
 background:#f2f3f5;border:1px solid transparent}
.search:focus-within{background:#fff;border-color:#c7d2fe;box-shadow:0 0 0 3px #eef2ff}
.search span{color:#9aa1aa;font-size:13px}
.search input{width:200px;border:0;outline:0;background:transparent;font:inherit;font-size:13px}
#qhits{font-size:11.5px;color:#9aa1aa;white-space:nowrap}
.zoom,.seg{display:flex;align-items:center;gap:2px;padding:2px;border-radius:8px;background:#f2f3f5}
button{font:inherit;font-size:12.5px;color:#3f4652;background:transparent;border:0;
 padding:5px 9px;border-radius:6px;cursor:pointer}
button:hover{background:#e4e6ea}
button.on{background:#fff;color:#1f2329;box-shadow:0 1px 2px rgba(0,0,0,.08)}
#pct{min-width:42px;text-align:center;font-size:12px;color:#6b7280}
#legend{display:flex;flex-wrap:wrap;gap:14px;flex:0 0 auto;padding:6px 16px;
 font-size:12px;color:#5b6373;background:#fff;border-bottom:1px solid #eef0f2}
.lg{display:inline-flex;align-items:center;gap:6px}
.lg i{width:8px;height:8px;border-radius:50%}
.lg b{font-weight:600;color:#1f2329}
main{position:relative;flex:1;min-height:0}
#stage{position:absolute;inset:0;overflow:hidden;cursor:grab;background-color:#fbfbfc;
 background-image:radial-gradient(#dfe3e8 1px,transparent 1px);background-size:22px 22px}
#stage.drag{cursor:grabbing}
#world{position:absolute;left:0;top:0;transform-origin:0 0;will-change:transform}
.grp{position:absolute;border:1px solid #c9d6ea;border-radius:14px;transition:opacity .15s}
.grp.dim{opacity:.15}
.grp span{position:absolute;left:10px;top:4px;font-size:11px;font-weight:600;color:#5b6b82}
#edges{position:absolute;left:0;top:0;overflow:visible}
.edge{fill:none;stroke:#8a94a6;stroke-width:1.8;stroke-linejoin:round;stroke-linecap:round;
 transition:opacity .15s,stroke .15s,stroke-width .15s}
.edge.dim{opacity:.1}
.edge.hl,.edge:hover{stroke:#2563eb;stroke-width:2.4;marker-end:url(#arw)}
.elab{font-size:11px;fill:#6b7280;text-anchor:middle;paint-order:stroke;stroke:#fbfbfc;
 stroke-width:4px;transition:opacity .15s}
.elab.dim{opacity:.08}
.card{position:absolute;width:190px;height:88px;padding:11px 12px;border-radius:12px;
 background:#fff;border:1px solid #e3e5e8;cursor:pointer;transition:opacity .16s,
 box-shadow .16s,border-color .16s,transform .16s;
 box-shadow:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.04)}
.card:hover{transform:translateY(-1px);border-color:#cbd2dc;
 box-shadow:0 6px 18px rgba(16,24,40,.12)}
.card .ttl{font-size:13px;font-weight:600;line-height:1.35;max-height:2.7em;overflow:hidden}
.card .sum{margin-top:3px;font-size:11.5px;line-height:1.4;color:#6b7280;
 max-height:2.8em;overflow:hidden}
.card .dot{position:absolute;top:9px;right:10px;width:7px;height:7px;border-radius:50%}
.card .idx{position:absolute;right:9px;bottom:5px;font-size:10.5px;font-style:normal;
 color:#b9c0cb}
.card.hl{border-color:#2563eb;box-shadow:0 0 0 3px #e0e7ff,0 6px 18px rgba(37,99,235,.18)}
.card.dim{opacity:.22}
.card.hit,.stp.hit{border-color:#f59e0b;box-shadow:0 0 0 3px #fef3c7}
"""

_T2 = r"""#listview{position:absolute;inset:0;display:none;overflow:auto;padding:26px 0 60px;
 background:#f7f8fa}
body.list #stage{display:none}
body.list #listview{display:block}
#listview .wrap{max-width:780px;margin:0 auto;padding:0 20px}
.stp{background:#fff;border:1px solid #e6e8eb;border-radius:14px;padding:18px 20px;
 margin:0 0 14px;transition:opacity .16s,border-color .16s,box-shadow .16s}
.stp.dim{opacity:.25}
.stp .shi{display:flex;align-items:center;gap:10px;font-size:12px}
.stp .chip{padding:2px 9px;border-radius:20px;background:#f4f5f7;font-size:11.5px}
.stp .no{color:#9aa1aa}
.stp h2{margin:8px 0 4px;font-size:17px}
.stp .sum{margin:0;font-size:13px;color:#6b7280}
.f{margin-top:12px}
.fl{margin-bottom:2px;font-size:11.5px;color:#8a94a6}
.fv{font-size:13.5px;white-space:pre-wrap}
.fh{margin-top:2px;font-size:12px;color:#9aa1aa}
ul.items,ul.mat{list-style:none;margin:4px 0 0;padding:0}
ul.items li{position:relative;margin:1px 0;padding-left:14px;font-size:13px}
ul.items li:before{content:"";position:absolute;left:2px;top:.62em;width:4px;height:4px;
 border-radius:50%;background:#f59e0b}
ul.mat li{display:flex;align-items:baseline;gap:7px;padding:2px 0;font-size:13px}
ul.mat .mk{flex:0 0 auto;width:12px;color:#b9c0cb}
ul.mat li.ok .mk{color:#15803d}
ul.mat .mt{flex:1}
ul.mat .mh{display:block;font-size:11.5px;color:#9aa1aa}
.dl{white-space:nowrap;font-size:12px;color:#2563eb;text-decoration:none;
 border:1px solid #dbe3f8;border-radius:6px;padding:1px 7px}
.dl:hover{background:#eef2ff}
.toolarge{white-space:nowrap;font-size:11.5px;color:#9aa1aa}
.shots{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.shot{display:block;width:100%;max-width:520px;border:1px solid #e6e8eb;border-radius:8px}
a.go{color:#2563eb;text-decoration:none;border-bottom:1px solid #cddafa}
#panel{position:absolute;top:0;right:0;bottom:0;z-index:4;width:min(430px,88vw);
 padding:18px 20px 40px;overflow:auto;background:#fff;border-left:1px solid #e6e8eb;
 box-shadow:-12px 0 34px rgba(16,24,40,.10);transform:translateX(103%);
 transition:transform .22s cubic-bezier(.2,.7,.3,1)}
#panel.open{transform:none}
#panel .stp{border:0;padding:0;margin:0}
.pclose{position:absolute;top:8px;right:12px;font-size:15px;color:#9aa1aa}
.pnav{display:flex;flex-wrap:wrap;gap:6px;margin-top:16px;font-size:12px;color:#8a94a6}
.pnav b{padding:2px 8px;border-radius:6px;background:#f2f3f5;color:#3f4652;
 font-weight:500;cursor:pointer}
.pnav b:hover{background:#e4e6ea}
.foot{display:flex;flex-wrap:wrap;gap:14px;flex:0 0 auto;padding:8px 16px;font-size:11.5px;
 color:#9aa1aa;background:#fff;border-top:1px solid #eef0f2}
kbd{padding:0 4px;border-radius:4px;background:#f2f3f5;font:inherit;font-size:10.5px;
 color:#5b6373}
@media (max-width:760px){
 .search input{width:110px}.meta{display:none}.foot span:last-child{display:none}
}
@media print{
 body{overflow:visible;background:#fff}
 header,#legend,#stage,#panel,.foot{display:none!important}
 #listview{display:block!important;position:static;padding:0}
 .stp{break-inside:avoid;box-shadow:none}
}
</style>
</head>
<body>
<header>
  <div class="h1">@@TITLE@@</div>
  <div class="meta">@@META@@</div>
  <div class="sp"></div>
  <label class="search"><span>⌕</span><input id="q" placeholder="搜步骤、字段、材料"><i id="qhits"></i></label>
  <div class="zoom">
    <button id="z-out" title="缩小">−</button><span id="pct">100%</span>
    <button id="z-in" title="放大">＋</button>
    <button id="z-fit" title="让整张图进入视野">适应</button>
    <button id="z-one" title="原始大小">1:1</button>
  </div>
  <div class="seg"><button id="v-graph" class="on">图</button><button id="v-list">列表</button></div>
</header>
<div id="legend">@@LEGEND@@</div>
<main>
  <div id="stage"><div id="world">@@GROUPS@@@@SVG@@@@CARDS@@</div></div>
  <section id="listview"><div class="wrap">@@ARTICLES@@</div></section>
  <aside id="panel">
    <button class="pclose" id="pclose">✕</button>
    <div id="pbody"></div>
    <div class="pnav" id="pnav"></div>
  </aside>
</main>
<div class="foot">
  <span>由「流程盒子」导出 · 只读</span>
  <span>滚轮缩放 · 拖动平移 · 点卡片看这一步的材料</span>
  <span><kbd>/</kbd> 搜索 <kbd>0</kbd> 适应 <kbd>Esc</kbd> 退出</span>
</div>
"""

_T3 = r"""<script>
(function () {
  var W = @@W@@, H = @@H@@, E = @@EDGES@@;
  var stage = document.getElementById('stage'),
      world = document.getElementById('world'),
      pct = document.getElementById('pct'),
      panel = document.getElementById('panel'),
      pbody = document.getElementById('pbody'),
      pnav = document.getElementById('pnav'),
      q = document.getElementById('q'),
      qhits = document.getElementById('qhits');
  var cards = [].slice.call(document.querySelectorAll('.card')),
      arts = [].slice.call(document.querySelectorAll('.stp')),
      edges = [].slice.call(document.querySelectorAll('.edge')),
      labels = [].slice.call(document.querySelectorAll('.elab')),
      grps = [].slice.call(document.querySelectorAll('.grp'));
  var s = 1, tx = 0, ty = 0, MIN = 0.2, MAX = 2.6, drag = null;

  function apply() {
    world.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + s + ')';
    pct.textContent = Math.round(s * 100) + '%';
  }
  function fit() {
    var r = stage.getBoundingClientRect();
    if (!r.width) { return; }
    s = Math.min((r.width - 70) / W, (r.height - 70) / H, 1.1);
    s = Math.max(MIN, Math.min(MAX, s));
    tx = (r.width - W * s) / 2;
    ty = (r.height - H * s) / 2;
    apply();
  }
  function zoomAt(f, mx, my) {
    var ns = Math.max(MIN, Math.min(MAX, s * f));
    if (Math.abs(ns - s) < 1e-4) { return; }
    if (mx == null) { mx = stage.clientWidth / 2; my = stage.clientHeight / 2; }
    tx = mx - (mx - tx) * (ns / s);
    ty = my - (my - ty) * (ns / s);
    s = ns;
    apply();
  }

  stage.addEventListener('wheel', function (e) {
    e.preventDefault();
    var r = stage.getBoundingClientRect();
    zoomAt(Math.exp(-e.deltaY * 0.0016), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });

  stage.addEventListener('pointerdown', function (e) {
    if (e.target.closest('.card')) { return; }
    drag = { x: e.clientX - tx, y: e.clientY - ty };
    stage.classList.add('drag');
  });
  window.addEventListener('pointermove', function (e) {
    if (!drag) { return; }
    tx = e.clientX - drag.x;
    ty = e.clientY - drag.y;
    apply();
  });
  window.addEventListener('pointerup', function () {
    drag = null;
    stage.classList.remove('drag');
  });
  stage.addEventListener('dblclick', function (e) {
    if (!e.target.closest('.card')) { fit(); }
  });
  stage.addEventListener('click', function (e) {
    if (!e.target.closest('.card')) { clearSel(); }
  });

  var NXT = {}, PRV = {};
  E.forEach(function (p) {
    (NXT[p[0]] = NXT[p[0]] || []).push(p[1]);
    (PRV[p[1]] = PRV[p[1]] || []).push(p[0]);
  });
  function bfs(start, map) {
    var seen = {}, st = [start], k, i, list;
    while (st.length) {
      k = st.pop();
      list = map[k] || [];
      for (i = 0; i < list.length; i++) {
        if (!seen[list[i]]) { seen[list[i]] = 1; st.push(list[i]); }
      }
    }
    delete seen[start];
    return seen;
  }
  function keys(o) {
    return Object.keys(o).map(Number).sort(function (a, b) { return a - b; });
  }
  function clearSel() {
    panel.classList.remove('open');
    cards.concat(arts).forEach(function (el) {
      el.classList.remove('hl', 'dim');
    });
    edges.forEach(function (el) { el.classList.remove('hl', 'dim'); });
    labels.forEach(function (el) { el.classList.remove('dim'); });
    grps.forEach(function (el) { el.classList.remove('dim'); });
  }
"""

_T4 = r"""  function select(k) {
    var F = bfs(k, NXT), B = bfs(k, PRV), keep = {};
    var inList = document.body.classList.contains('list');
    keep[k] = 1;
    keys(F).forEach(function (x) { keep[x] = 1; });
    keys(B).forEach(function (x) { keep[x] = 1; });
    cards.concat(arts).forEach(function (el) {
      var kk = +el.getAttribute('data-k');
      el.classList.toggle('hl', kk === k);
      el.classList.toggle('dim', !inList && !keep[kk]);
    });
    edges.forEach(function (el) {
      var a = +el.getAttribute('data-a'), b = +el.getAttribute('data-b');
      var on = ((a === k) || (a in B)) && ((b === k) || (b in F));
      el.classList.toggle('hl', on);
      el.classList.toggle('dim', !on);
    });
    labels.forEach(function (el) {
      var a = +el.getAttribute('data-a'), b = +el.getAttribute('data-b');
      el.classList.toggle('dim',
        !(((a === k) || (a in B)) && ((b === k) || (b in F))));
    });
    grps.forEach(function (el) {
      var ks = (el.getAttribute('data-k') || '').split(',');
      var near = ks.some(function (x) { return keep[+x]; });
      el.classList.toggle('dim', !near);
    });
    openPanel(k, F, B);
  }
  function openPanel(k, F, B) {
    var src = document.getElementById('a' + k), up = keys(B), dn = keys(F);
    pbody.innerHTML = '';
    if (src) {
      var c = src.cloneNode(true);
      c.removeAttribute('id');
      pbody.appendChild(c);
    }
    var h = '';
    if (up.length) {
      h += '<span>来自</span>' + up.map(function (x) {
        return '<b data-go="' + x + '">' + (x + 1) + '</b>';
      }).join('');
    }
    if (dn.length) {
      h += '<span>去往</span>' + dn.map(function (x) {
        return '<b data-go="' + x + '">' + (x + 1) + '</b>';
      }).join('');
    }
    pnav.innerHTML = h;
    [].slice.call(pnav.querySelectorAll('b')).forEach(function (el) {
      el.onclick = function () { focusCard(+el.getAttribute('data-go')); };
    });
    panel.classList.add('open');
    panel.scrollTop = 0;
  }
"""

_T5 = r"""  function focusCard(k) {
    if (document.body.classList.contains('list')) {
      var art = document.getElementById('a' + k);
      if (art) { art.scrollIntoView({ block: 'center' }); }
      select(k);
      return;
    }
    var el = document.getElementById('c' + k);
    if (el) {
      var cx = parseFloat(el.style.left) + 95,
          cy = parseFloat(el.style.top) + 44,
          r = stage.getBoundingClientRect();
      s = Math.max(s, 0.75);
      tx = r.width / 2 - cx * s;
      ty = r.height / 2 - cy * s;
      apply();
    }
    select(k);
  }

  cards.forEach(function (el) {
    el.addEventListener('click', function (e) {
      e.stopPropagation();
      select(+el.getAttribute('data-k'));
    });
  });

  function marks() {
    var v = q.value.trim().toLowerCase(), hits = 0;
    cards.forEach(function (el) {
      var on = !!v && (el.getAttribute('data-s') || '').indexOf(v) >= 0;
      el.classList.toggle('hit', on);
      if (on) { hits++; }
    });
    arts.forEach(function (el) {
      var on = !!v && (el.getAttribute('data-s') || '').indexOf(v) >= 0;
      el.classList.toggle('hit', on);
    });
    qhits.textContent = v ? (hits ? hits + ' 步' : '没找到') : '';
  }
  q.addEventListener('input', marks);
  q.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      var hit = document.querySelector('.card.hit') ||
                document.querySelector('.stp.hit');
      if (hit) {
        if (hit.classList.contains('card')) {
          focusCard(+hit.getAttribute('data-k'));
        } else {
          setView('list');
          hit.scrollIntoView({ block: 'center' });
        }
      }
    } else if (e.key === 'Escape') {
      q.value = '';
      marks();
      q.blur();
    }
  });

  function setView(v) {
    document.body.classList.toggle('list', v === 'list');
    document.getElementById('v-graph').classList.toggle('on', v !== 'list');
    document.getElementById('v-list').classList.toggle('on', v === 'list');
    if (v !== 'list') { fit(); }
  }
  document.getElementById('z-in').onclick = function () { zoomAt(1.2); };
  document.getElementById('z-out').onclick = function () { zoomAt(1 / 1.2); };
  document.getElementById('z-fit').onclick = fit;
  document.getElementById('z-one').onclick = function () { zoomAt(1 / s); };
  document.getElementById('pclose').onclick = clearSel;
  document.getElementById('v-graph').onclick = function () { setView('graph'); };
  document.getElementById('v-list').onclick = function () { setView('list'); };

  document.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT' || e.ctrlKey || e.metaKey) { return; }
    if (e.key === '/') { e.preventDefault(); q.focus(); }
    else if (e.key === '0') { fit(); }
    else if (e.key === '+' || e.key === '=') { zoomAt(1.2); }
    else if (e.key === '-') { zoomAt(1 / 1.2); }
    else if (e.key === 'Escape') { clearSel(); }
  });

  window.addEventListener('error', function (ev) {
    var d = document.createElement('div');
    d.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:99;'
      + 'padding:8px 12px;background:#b91c1c;color:#fff;'
      + 'font:12px/1.5 monospace';
    d.textContent = '页面脚本出错：' + ev.message;
    document.body.appendChild(d);
  });

  fit();
  window.__fb = { select: select, fit: fit, view: setView };
})();
</script>
</body>
</html>
"""

_TEMPLATE = _T1 + _T2 + _T3 + _T4 + _T5


