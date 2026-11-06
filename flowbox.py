#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flowbox.py — 流程盒 demo

左边是事项，中间是步骤卡片，右边是材料。
材料拖进来会自动改名、按阶段分组，鼠标停上去放大预览。

    python flowbox.py
    python flowbox.py --selftest
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from PIL import Image, ImageTk
except Exception:
    Image = ImageTk = None

try:
    import pypdfium2 as pdfium
except Exception:
    pdfium = None

try:
    from pypdf import PdfReader, PdfWriter
except Exception:
    PdfReader = PdfWriter = None


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(APP_DIR))) / "flowbox"
CASES_DIR = DATA_DIR / "cases"
TEMPLATES_DIR = DATA_DIR / "templates"
EXAMPLE_DIR = APP_DIR / "examples"

BG = "#F4F5F7"
CARD = "#FFFFFF"
TEXT = "#1F2329"
SUB = "#6B7280"
LINE = "#E3E5E8"
ACCENT = "#2563EB"
ACCENT_BG = "#EAF1FE"
OK = "#15803D"
OK_BG = "#E8F5EC"
WARN = "#B45309"
WARN_BG = "#FDF3E3"
MUTED = "#F0F1F3"

FONT = ("Microsoft YaHei UI", 10)
FONT_S = ("Microsoft YaHei UI", 9)
FONT_B = ("Microsoft YaHei UI", 10, "bold")
FONT_H = ("Microsoft YaHei UI", 13, "bold")
FONT_T = ("Microsoft YaHei UI", 16, "bold")

TYPE_LABEL = {"url": "网址", "path": "客户端内嵌", "app": "客户端内嵌",
              "exe": "本机程序", "template": "模板"}


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


def today() -> str:
    return time.strftime("%Y-%m-%d")


def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write_json(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def scan_templates():
    out = []
    for d in (TEMPLATES_DIR, EXAMPLE_DIR):
        if not d.exists():
            continue
        for f in sorted(d.glob("*.flow.json")):
            try:
                data = read_json(f)
            except Exception:
                continue
            if data.get("kind") == "flow" and isinstance(data.get("steps"), list):
                data["_path"] = str(f)
                out.append(data)
    return out


VALID_KINDS = {"action", "wait", "offline"}


def validate_flow(flow) -> list[str]:
    errs = []
    if flow.get("schema") != 1:
        errs.append("schema 不是 1，这个版本打不开")
    if flow.get("kind") != "flow":
        errs.append("kind 不是 flow")
    if not flow.get("name"):
        errs.append("缺少 name")
    steps = flow.get("steps")
    if not isinstance(steps, list) or not steps:
        return errs + ["没有 steps"]
    ids = set()
    for i, s in enumerate(steps):
        sid = s.get("id")
        if not sid:
            errs.append(f"第 {i + 1} 步缺 id")
        elif sid in ids:
            errs.append(f"步骤 id 重复：{sid}")
        ids.add(sid)
        if s.get("kind") not in VALID_KINDS:
            errs.append(f"{sid} 的 kind 不合法")
        if not s.get("name"):
            errs.append(f"{sid} 缺 name")
    for s in steps:
        for nxt in s.get("next", []) or []:
            if nxt not in ids:
                errs.append(f"{s.get('id')} 指向不存在的步骤 {nxt}")
    return errs


def fill(text, ctx):
    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}",
                  lambda m: str(ctx.get(m.group(1), "") or ""), text)


def auto_name(idx, label, src, when=None):
    when = when or today()
    ext = Path(src).suffix.lower() or ".dat"
    safe = re.sub(r'[\\/:*?"<>|]', "_", label or "材料")
    return f"{idx:02d}_{safe}_{when}{ext}"


def sanitize(flow):
    f = json.loads(json.dumps(flow))
    f.pop("_path", None)
    d = f.get("dicts", {}) or {}
    for key, items in list(d.items()):
        if items:
            d[key] = ["{%s}" % key[:-1] if key.endswith("s") else "{%s}" % key]
    return f


def find_step(flow, sid):
    for s in flow.get("steps", []) or []:
        if s.get("id") == sid:
            return s
    return None


def edge_path():
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if Path(p).exists():
            return p
    return None


def open_url(url, profile_dir=None):
    """用独立配置目录打开链接，登录一次之后 cookie 会留在里面。"""
    edge = edge_path()
    try:
        if edge:
            args = [edge]
            if profile_dir:
                args.append(f"--user-data-dir={profile_dir}")
            args.append(url)
            import subprocess
            subprocess.Popen(args)
            return True
        import webbrowser
        webbrowser.open(url)
        return True
    except Exception:
        return False


def find_material(flow, mid):
    for s in flow.get("steps", []) or []:
        for m in s.get("materials", []) or []:
            if m.get("id") == mid:
                return m
    return None


def step_index(flow, sid):
    for i, s in enumerate(flow.get("steps", []) or []):
        if s.get("id") == sid:
            return i
    return 0


def ctx_of(case):
    flow = case["flow"]
    f = case.get("fields", {}) or {}
    ctx = dict(f)
    nos = f.get("patent_nos")
    if isinstance(nos, str):
        nos = [x for x in re.split(r"[+,\s、]+", nos) if x]
    if not isinstance(nos, list):
        nos = []
    ctx["patent_nos"] = "+".join(str(x) for x in nos)
    ctx["year"] = time.strftime("%Y")
    ctx["month"] = str(int(time.strftime("%m")))
    dicts = flow.get("dicts", {}) or {}
    ctx["vendor"] = (dicts.get("vendors") or [""])[0]
    for k in ("title", "amount", "company", "owner", "project", "org_unit"):
        if ctx.get(k) is None:
            ctx[k] = ""
    return ctx


def pdf_text(path, limit=4000):
    if PdfReader is None:
        return ""
    try:
        r = PdfReader(str(path))
        out = []
        for p in r.pages[:3]:
            out.append(p.extract_text() or "")
        return "\n".join(out)[:limit]
    except Exception:
        return ""


def pdf_has_text(path, kw):
    kw = (kw or "").strip()
    if not kw:
        return True
    return kw in pdf_text(path)


def merge_pdfs(paths, out_path):
    if PdfWriter is None:
        return False, "没有 pypdf"
    w = PdfWriter()
    n = 0
    for p in paths:
        try:
            r = PdfReader(str(p))
            for page in r.pages:
                w.add_page(page)
                n += 1
        except Exception:
            continue
    if n == 0:
        return False, "没有可合并的 PDF"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as fh:
        w.write(fh)
    return True, f"{n} 页"


# ---------------------------------------------------------------- 预览

_preview_cache = {}


def render_preview(path, max_w=520, max_h=680):
    """把图片或 PDF 首页渲染成 PIL 图，带缓存。"""
    p = Path(path)
    if not p.exists():
        return None
    try:
        key = (str(p), p.stat().st_mtime, max_w, max_h)
    except Exception:
        key = (str(p), 0, max_w, max_h)
    if key in _preview_cache:
        return _preview_cache[key]
    img = None
    suffix = p.suffix.lower()
    try:
        if suffix == ".pdf" and pdfium is not None:
            doc = pdfium.PdfDocument(str(p))
            page = doc[0]
            w, h = page.get_size()
            scale = min(max_w / w, max_h / h) if w and h else 1.0
            img = page.render(scale=max(0.05, min(2.0, scale))).to_pil()
            doc.close()
        elif Image is not None and suffix in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"):
            img = Image.open(p)
            img.load()
            img = img.convert("RGB")
            img.thumbnail((max_w, max_h), Image.LANCZOS)
    except Exception:
        img = None
    _preview_cache[key] = img
    return img


class HoverPreview:
    """鼠标停 280ms 后在旁边弹一个放大的预览窗。"""

    def __init__(self, root):
        self.root = root
        self.win = None
        self.lbl = None
        self.photo = None
        self.job = None
        self.hide_job = None

    def attach(self, widget, path):
        widget.bind("<Enter>", lambda e: self._later(path), add="+")
        widget.bind("<Leave>", lambda e: self._leave(), add="+")

    def _later(self, path):
        self._cancel_jobs()
        self.job = self.root.after(280, lambda: self._show(path))

    def _leave(self):
        self._cancel_jobs()
        self.hide_job = self.root.after(160, self._hide)

    def _cancel_jobs(self):
        for attr in ("job", "hide_job"):
            j = getattr(self, attr)
            if j:
                try:
                    self.root.after_cancel(j)
                except Exception:
                    pass
                setattr(self, attr, None)

    def _hide(self):
        self.hide_job = None
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None
        self.lbl = None
        self.photo = None

    def _show(self, path):
        self.job = None
        img = render_preview(path)
        if img is None:
            return
        if self.win is None:
            self.win = tk.Toplevel(self.root)
            self.win.overrideredirect(True)
            try:
                self.win.attributes("-topmost", True)
            except Exception:
                pass
            frame = tk.Frame(self.win, bg="#111827")
            frame.pack()
            self.lbl = tk.Label(frame, bg="#111827", bd=0)
            self.lbl.pack(padx=2, pady=2)
        self.photo = ImageTk.PhotoImage(img)
        self.lbl.configure(image=self.photo)
        x, y = self.root.winfo_pointerxy()
        w, h = img.size
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        px, py = x + 26, y + 18
        if px + w + 10 > sw:
            px = max(0, x - w - 26)
        if py + h + 10 > sh:
            py = max(0, sh - h - 10)
        self.win.geometry(f"+{px}+{py}")
        self.win.deiconify()


class ScrollFrame(tk.Frame):
    """可滚动容器，内容放在 .inner 里。"""

    def __init__(self, master, bg=CARD, **kw):
        super().__init__(master, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=e.width))
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")

    def clear(self):
        for c in self.inner.winfo_children():
            c.destroy()


# ---------------------------------------------------------------- 数据

class Store:
    def __init__(self):
        for d in (DATA_DIR, CASES_DIR, TEMPLATES_DIR):
            d.mkdir(parents=True, exist_ok=True)
        self.templates = scan_templates()

    def cases(self):
        out = []
        if not CASES_DIR.exists():
            return out
        for d in CASES_DIR.iterdir():
            f = d / "case.json"
            if f.exists():
                try:
                    out.append(read_json(f))
                except Exception:
                    continue
        out.sort(key=lambda c: c.get("updated", ""), reverse=True)
        return out

    def case_dir(self, case):
        return CASES_DIR / case["id"]

    def new_case(self, tpl):
        cid = uuid.uuid4().hex[:8]
        d = CASES_DIR / cid
        (d / "files").mkdir(parents=True, exist_ok=True)
        flow = json.loads(json.dumps(tpl))
        flow.pop("_path", None)
        steps = {}
        for s in flow.get("steps", []):
            steps[s["id"]] = {"state": "todo"}
        case = {
            "id": cid,
            "template_id": flow.get("id"),
            "template_name": flow.get("name"),
            "flow": flow,
            "fields": {},
            "steps": steps,
            "materials": [],
            "created": now(),
            "updated": now(),
            "current": (flow.get("steps") or [{}])[0].get("id"),
            "log": [],
        }
        self.save(case)
        return case

    def save(self, case):
        case["updated"] = now()
        write_json(CASES_DIR / case["id"] / "case.json", case)

    def seed_if_empty(self):
        cs = self.cases()
        if cs or not self.templates:
            return cs
        case = self.new_case(self.templates[0])
        case["fields"] = {
            "title": "2026 年专利年费缴纳",
            "amount": 1000,
            "company": "中国建筑第五工程局有限公司",
            "owner": "牛其祥",
            "patent_nos": ["2023118567720"],
            "project": "城市更新改造技术研究院-本部",
            "org_unit": "城市更新改造技术研究院",
            "deadline": "",
        }
        self.save(case)
        return self.cases()

    def add_material(self, case, src, material_id=None, step_id=None):
        src = Path(src)
        if not src.exists():
            return None
        mat = find_material(case["flow"], material_id) if material_id else None
        label = (mat or {}).get("name") or src.stem
        idx = 1 + sum(1 for m in case.get("materials", []) if m.get("step") == step_id)
        fname = auto_name(idx, label, src)
        step = find_step(case["flow"], step_id) if step_id else None
        sub = "其他"
        if step_id:
            safe = re.sub(r'[\\/:*?"<>|]', "_", (step or {}).get("name", "") or "步骤")[:16]
            sub = f"{step_id}_{safe}"
        folder = self.case_dir(case) / "files" / sub
        folder.mkdir(parents=True, exist_ok=True)
        dst = folder / fname
        base, n = dst.stem, 1
        while dst.exists():
            n += 1
            dst = folder / f"{base}_{n}{src.suffix.lower()}"
        try:
            shutil.copy2(src, dst)
        except Exception:
            return None
        rec = {
            "id": uuid.uuid4().hex[:8],
            "material_id": material_id,
            "step": step_id,
            "name": dst.name,
            "file": f"files/{sub}/{dst.name}",
            "added": now(),
        }
        case.setdefault("materials", []).append(rec)
        self.save(case)
        return rec

    def remove_material(self, case, rec):
        try:
            (self.case_dir(case) / rec["file"]).unlink()
        except Exception:
            pass
        case["materials"] = [m for m in case.get("materials", []) if m.get("id") != rec.get("id")]
        self.save(case)


def material_path(case, rec):
    return CASES_DIR / case["id"] / rec["file"]


def run_checks(case, step):
    """返回自动检查发现的问题；manual 类只做提示。"""
    have = {}
    for m in case.get("materials", []) or []:
        mid = m.get("material_id")
        if mid and mid not in have:
            have[mid] = m
    problems = []
    for ch in step.get("checks", []) or []:
        t = ch.get("type")
        if t == "materials_present":
            ids = (ch.get("args") or {}).get("ids", [])
            miss = []
            for mid in ids:
                if mid in have:
                    continue
                mat = find_material(case["flow"], mid)
                miss.append((mat or {}).get("name", mid))
            if miss:
                problems.append(ch.get("message", "材料不全") + "：缺 " + "、".join(miss))
        elif t == "pdf_contains":
            args = ch.get("args") or {}
            mid = args.get("material")
            kw = fill(args.get("keyword", ""), ctx_of(case))
            rec = have.get(mid)
            if rec and kw:
                p = material_path(case, rec)
                if p.suffix.lower() == ".pdf" and not pdf_has_text(p, kw):
                    problems.append(ch.get("message", "PDF 里没有找到关键词"))
    return problems


def assemble_pack(case, step):
    """按 assemble.order 把材料合并成一个打印包。"""
    rules = step.get("assemble") or []
    if not rules:
        return False, "这一步没有打印包规则"
    rule = rules[0]
    order = rule.get("order", [])
    out_name = rule.get("output", "打印包.pdf")
    by_mid = {}
    for m in case.get("materials", []) or []:
        mid = m.get("material_id")
        if mid and mid not in by_mid:
            by_mid[mid] = m
    paths = []
    for mid in order:
        rec = by_mid.get(mid)
        if not rec:
            continue
        p = material_path(case, rec)
        if p.exists() and p.suffix.lower() == ".pdf":
            paths.append(p)
    out = CASES_DIR / case["id"] / out_name
    return merge_pdfs(paths, out)


# ---------------------------------------------------------------- 界面

def flat_btn(parent, text, cmd, fg=TEXT, bg=CARD, font=FONT_S, pad=(10, 5)):
    b = tk.Label(parent, text=text, fg=fg, bg=bg, font=font,
                 padx=pad[0], pady=pad[1], cursor="hand2")
    b.bind("<Button-1>", lambda e: cmd())
    b.bind("<Enter>", lambda e: b.configure(bg="#EEF0F3"))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b


class App:
    W, H = 1180, 800

    def __init__(self, root):
        self.root = root
        self.store = Store()
        self.cases = self.store.seed_if_empty()
        self.case = self.cases[0] if self.cases else None
        self.hover = HoverPreview(root)
        self.editing = False
        self.root.title("流程盒 demo")
        geom = os.environ.get("FLOWBOX_GEOM") or f"{self.W}x{self.H}+120+60"
        self.root.geometry(geom)
        self.root.minsize(980, 640)
        self.root.configure(bg=BG)
        self._build()
        self._refresh_cases()
        self._refresh_all()
        if self.case:
            n = len(self.case["flow"].get("steps", []))
            self.say(f"共 {n} 步 · 点上面任意一步可以跳转")

    def _build(self):
        top = tk.Frame(self.root, bg=CARD, height=56)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="流程盒", bg=CARD, fg=TEXT, font=FONT_T).pack(
            side="left", padx=(18, 10), pady=10)
        self.lbl_tpl = tk.Label(top, text="", bg=CARD, fg=SUB, font=FONT_S)
        self.lbl_tpl.pack(side="left", pady=18)

        flat_btn(top, "导入流程", self.import_flow, fg=ACCENT).pack(side="right", padx=(0, 14), pady=13)
        flat_btn(top, "导出脱敏", lambda: self.export_flow(True), fg=SUB).pack(side="right", pady=13)
        flat_btn(top, "导出", lambda: self.export_flow(False), fg=SUB).pack(side="right", pady=13)
        self.btn_edit = flat_btn(top, "编辑流程", self.toggle_edit, fg=SUB)
        self.btn_edit.pack(side="right", padx=(0, 10), pady=13)
        flat_btn(top, "＋ 新建事项", self.new_case, bg=MUTED).pack(side="right", padx=(0, 14), pady=13)

        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=CARD, width=238)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="事项", bg=CARD, fg=SUB, font=FONT_S).pack(
            anchor="w", padx=16, pady=(14, 6))
        self.case_scroll = ScrollFrame(left, bg=CARD)
        self.case_scroll.pack(fill="both", expand=True)

        tk.Frame(body, bg=LINE, width=1).pack(side="left", fill="y")

        center = tk.Frame(body, bg=BG)
        center.pack(side="left", fill="both", expand=True)
        self.strip = tk.Frame(center, bg=BG, height=74)
        self.strip.pack(fill="x", padx=16, pady=(12, 4))
        self.strip.pack_propagate(False)
        self.card_footer = tk.Frame(center, bg=CARD)
        self.card_footer.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
        self.card_scroll = ScrollFrame(center, bg=CARD)
        self.card_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        tk.Frame(body, bg=LINE, width=1).pack(side="left", fill="y")

        right = tk.Frame(body, bg=CARD, width=330)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        head = tk.Frame(right, bg=CARD)
        head.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(head, text="材料", bg=CARD, fg=SUB, font=FONT_S).pack(side="left")
        flat_btn(head, "＋ 添加", self.add_any_material, fg=ACCENT).pack(side="right")
        self.mat_scroll = ScrollFrame(right, bg=CARD)
        self.mat_scroll.pack(fill="both", expand=True)

        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x")
        self.status = tk.Label(self.root, text="", bg=BG, fg=SUB, font=FONT_S, anchor="w")
        self.status.pack(fill="x", padx=16, pady=6)

    # ---------------- 通用
    def say(self, msg, kind="info"):
        color = {"info": SUB, "ok": OK, "warn": WARN, "err": "#B91C1C"}.get(kind, SUB)
        self.status.configure(text=msg, fg=color)

    def _copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.say("已复制到剪贴板", "ok")

    def _open(self, target):
        target = (target or "").strip()
        if not target:
            self.say("这一步没有填入口地址", "warn")
            return
        if target.startswith("http"):
            ok = open_url(target, DATA_DIR / "browser")
            self.say("已用独立浏览器打开，登录一次之后会记住" if ok else "打开失败",
                     "ok" if ok else "err")
            return
        if "://" in target:
            try:
                os.startfile(target)          # 自定义协议，唤起客户端
                self.say("已唤起客户端")
            except Exception as e:
                self.say(f"唤不起来：{e}", "err")
            return
        if target.lower().endswith((".exe", ".bat", ".cmd")):
            try:
                import subprocess
                subprocess.Popen([target])
                self.say("已启动：" + Path(target).name)
            except Exception as e:
                self.say(f"启动失败：{e}", "err")
            return
        try:
            os.startfile(target)  # noqa: S606
            self.say("已打开：" + target)
        except Exception as e:
            self.say(f"打不开：{e}", "err")

    def show_chain(self, entry):
        chain = entry.get("chain") or []
        win = tk.Toplevel(self.root)
        win.title("分步打开")
        win.geometry("460x430")
        win.configure(bg=CARD)
        tk.Label(win, text="按顺序点这几下：", bg=CARD, fg=SUB,
                 font=FONT_S).pack(anchor="w", padx=16, pady=(14, 6))
        box = tk.Frame(win, bg=CARD)
        box.pack(fill="both", expand=True, padx=16)
        for i, name in enumerate(chain, 1):
            row = tk.Frame(box, bg="#FAFBFC", highlightbackground=LINE, highlightthickness=1)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=str(i), bg="#FAFBFC", fg=SUB, font=FONT_S,
                     width=3).pack(side="left", padx=(8, 0), pady=7)
            tk.Label(row, text=name, bg="#FAFBFC", fg=TEXT, font=FONT).pack(side="left")
            flat_btn(row, "复制", lambda t=name: self._copy(t), fg=SUB,
                     bg="#FAFBFC").pack(side="right", padx=8)
        tk.Label(win, text="页面里的点击没法替你做——每家 OA 的页面结构都不一样，\n"
                           "写死的坐标一升级就废。这里只把路径列出来。",
                 bg=CARD, fg=SUB, font=FONT_S, justify="left").pack(
            anchor="w", padx=16, pady=10)
        flat_btn(win, "关闭", win.destroy).pack(anchor="e", padx=16, pady=(0, 12))

    # ---------------- 左栏
    def _refresh_cases(self):
        box = self.case_scroll
        box.clear()
        if not self.cases:
            tk.Label(box.inner, text="还没有事项\n点右上角新建", bg=CARD, fg=SUB,
                     font=FONT_S, justify="left").pack(anchor="w", padx=16, pady=20)
            return
        for c in self.cases:
            active = self.case and c["id"] == self.case["id"]
            bg = ACCENT_BG if active else CARD
            row = tk.Frame(box.inner, bg=bg, cursor="hand2")
            row.pack(fill="x", padx=8, pady=2)
            name = (c.get("fields") or {}).get("title") or c.get("template_name") or "未命名"
            tk.Label(row, text=name, bg=bg, fg=TEXT, font=FONT, anchor="w",
                     justify="left", wraplength=190).pack(anchor="w", padx=10, pady=(8, 0))
            done = sum(1 for s in (c.get("steps") or {}).values() if s.get("state") == "done")
            total = len((c.get("flow") or {}).get("steps", []) or [])
            tk.Label(row, text=f"{done}/{total} 步 · {c.get('template_name', '')}",
                     bg=bg, fg=SUB, font=FONT_S, anchor="w").pack(
                anchor="w", padx=10, pady=(1, 8))
            for w in [row] + list(row.winfo_children()):
                w.bind("<Button-1>", lambda e, cid=c["id"]: self.select_case(cid))

    def select_case(self, cid):
        for c in self.cases:
            if c["id"] == cid:
                self.case = c
                break
        self._refresh_cases()
        self._refresh_all()

    def goto(self, sid):
        self.case["current"] = sid
        st = self.case["steps"].setdefault(sid, {"state": "todo"})
        if st.get("state") == "todo":
            st["state"] = "doing"
            st["since"] = today()
        self.store.save(self.case)
        self._refresh_strip()
        self._refresh_card()

    def _refresh_all(self):
        if not self.case:
            return
        self.lbl_tpl.configure(
            text=f"{self.case.get('template_name', '')} · v{self.case['flow'].get('version', '')}")
        self._refresh_strip()
        self._refresh_card()
        self._refresh_materials()

    # ---------------- 步骤条
    def _refresh_strip(self):
        for c in self.strip.winfo_children():
            c.destroy()
        flow = self.case["flow"]
        cur = self.case.get("current")
        for i, s in enumerate(flow.get("steps", [])):
            st = (self.case.get("steps", {}).get(s["id"]) or {}).get("state", "todo")
            is_cur = s["id"] == cur
            if st == "done":
                fg, bg = OK, OK_BG
            elif is_cur:
                fg, bg = ACCENT, ACCENT_BG
            else:
                fg, bg = SUB, MUTED
            short = s["name"].replace("《", "").replace("》", "")
            if len(short) > 6:
                short = short[:6] + "…"
            b = tk.Label(self.strip, text=f"{i + 1} {short}", fg=fg, bg=bg,
                         font=FONT_S, padx=8, pady=5, cursor="hand2")
            b.grid(row=i // 4, column=i % 4, padx=(0, 6), pady=2, sticky="w")
            b.bind("<Button-1>", lambda e, sid=s["id"]: self.goto(sid))
        if self.editing:
            n = len(flow.get("steps", []))
            add = tk.Label(self.strip, text="＋ 加一步", fg=ACCENT, bg=ACCENT_BG,
                           font=FONT_S, padx=8, pady=5, cursor="hand2")
            add.grid(row=n // 4, column=n % 4, padx=(0, 6), pady=2, sticky="w")
            add.bind("<Button-1>", lambda e: self.add_step())

    # ---------------- 步骤卡片
    def _case_info(self):
        f = self.case.get("fields") or {}
        parts = []
        if f.get("title"):
            parts.append(str(f["title"]))
        if f.get("amount"):
            parts.append(f"{f['amount']} 元")
        if f.get("project"):
            parts.append(str(f["project"]))
        nos = f.get("patent_nos")
        if nos:
            parts.append("、".join(nos) if isinstance(nos, list) else str(nos))
        return " · ".join(parts)

    def _section(self, body, title):
        wrap = tk.Frame(body, bg=CARD)
        wrap.pack(fill="x", padx=22, pady=(14, 0))
        tk.Label(wrap, text=title, bg=CARD, fg=SUB, font=FONT_S).pack(anchor="w", pady=(0, 4))
        return wrap

    def _refresh_card(self):
        sf = self.card_scroll
        sf.clear()
        if not self.case:
            return
        body = sf.inner
        flow = self.case["flow"]
        step = find_step(flow, self.case.get("current"))
        if not step:
            return
        idx = step_index(flow, step["id"])
        st = self.case["steps"].setdefault(step["id"], {"state": "todo"})

        head = tk.Frame(body, bg=CARD)
        head.pack(fill="x", padx=24, pady=(20, 0))
        smap = {"done": "已完成", "doing": "进行中"}
        tk.Label(head, text=f"第 {idx + 1} 步 / 共 {len(flow['steps'])} 步 · "
                            f"{smap.get(st.get('state'), '未开始')}",
                 bg=CARD, fg=SUB, font=FONT_S).pack(anchor="w")
        tk.Label(head, text=step.get("name", ""), bg=CARD, fg=TEXT, font=FONT_H,
                 wraplength=520, justify="left").pack(anchor="w", pady=(4, 2))
        if step.get("summary"):
            tk.Label(head, text=step["summary"], bg=CARD, fg=SUB, font=FONT,
                     wraplength=520, justify="left").pack(anchor="w")
        self._main_actions(head, step)

        info = self._case_info()
        if info:
            tk.Label(body, text=info, bg=CARD, fg="#9CA3AF", font=FONT_S, anchor="w",
                     justify="left", wraplength=520).pack(fill="x", padx=24, pady=(10, 0))

        if step.get("kind") == "wait":
            self._card_wait(body, step, st)
        if step.get("materials"):
            self._card_materials(body, step)
        if step.get("entry") or step.get("account") or step.get("notes"):
            n = len(step.get("notes") or []) + (1 if step.get("account") else 0)
            self._collapsible(body, f"账号与注意 · {n} 条",
                              lambda p: self._fill_notes(p, step))
        if step.get("fields"):
            self._collapsible(body, f"要填的内容 · {len(step['fields'])} 项",
                              lambda p: self._card_fields(p, step))
        for c in self.card_footer.winfo_children():
            c.destroy()
        self._card_actions(self.card_footer, step, st)

    def _main_actions(self, parent, step):
        entries = step.get("entry") or []
        if not entries:
            return
        bar = tk.Frame(parent, bg=CARD)
        bar.pack(fill="x", pady=(12, 0))
        first = entries[0]
        val = (first.get("value") or "").strip()
        label = first.get("label") or "打开"
        etype = first.get("type") or ""
        if val.startswith("http"):
            text = f"打开 {label}"
        elif "://" in val:
            text = f"唤起 {label}"
        elif etype == "exe" or val.lower().endswith((".exe", ".bat", ".cmd")):
            text = f"启动 {label}"
        else:
            text = ""
        shown = False
        if text:
            solid_btn(bar, text, lambda v=val: self._open(v)).pack(side="left")
            shown = True
        if first.get("chain"):
            flat_btn(bar, "分步打开", lambda e=first: self.show_chain(e),
                     fg=ACCENT, bg=ACCENT_BG, pad=(12, 6)).pack(
                side="left", padx=(10 if shown else 0, 0))
            shown = True
        if not shown:
            flat_btn(bar, "复制路径", lambda v=val: self._copy(v),
                     fg=ACCENT, bg=ACCENT_BG, pad=(12, 6)).pack(side="left")

    def _collapsible(self, parent, title, builder):
        wrap = tk.Frame(parent, bg=CARD)
        wrap.pack(fill="x", padx=24, pady=(12, 0))
        head = tk.Label(wrap, text="▸ " + title, bg=CARD, fg=SUB, font=FONT_S,
                        cursor="hand2")
        head.pack(anchor="w")
        body = tk.Frame(wrap, bg=CARD)
        state = {"open": False}

        def toggle(_e=None):
            state["open"] = not state["open"]
            head.configure(text=("▾ " if state["open"] else "▸ ") + title)
            if state["open"]:
                if not body.winfo_children():
                    builder(body)
                body.pack(fill="x", pady=(6, 0))
            else:
                body.pack_forget()

        head.bind("<Button-1>", toggle)
        return wrap

    def _fill_notes(self, parent, step):
        for e in step.get("entry") or []:
            row = tk.Frame(parent, bg=CARD)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=e.get("label", ""), bg=CARD, fg=SUB, font=FONT_S,
                     width=9, anchor="w").pack(side="left")
            tk.Label(row, text=e.get("value", ""), bg=CARD, fg=TEXT, font=FONT_S,
                     anchor="w", justify="left", wraplength=330).pack(
                side="left", fill="x", expand=True)
            flat_btn(row, "复制", lambda v=e.get("value", ""): self._copy(v),
                     fg=SUB).pack(side="right")
            tag = TYPE_LABEL.get(e.get("type") or "", "")
            if tag:
                tk.Label(row, text=tag, bg=CARD, fg="#9CA3AF", font=FONT_S).pack(
                    side="right", padx=(0, 8))
        if step.get("account"):
            row = tk.Frame(parent, bg=CARD)
            row.pack(fill="x", pady=(8, 1))
            tk.Label(row, text="账号", bg=CARD, fg=SUB, font=FONT_S, width=9,
                     anchor="w").pack(side="left")
            tk.Label(row, text=step["account"], bg=CARD, fg=TEXT, font=FONT,
                     anchor="w", justify="left", wraplength=330).pack(
                side="left", fill="x", expand=True)
        for n in step.get("notes") or []:
            row = tk.Frame(parent, bg=CARD)
            row.pack(fill="x", pady=1)
            tk.Label(row, text="·", bg=CARD, fg=WARN, font=FONT).pack(side="left", anchor="n")
            tk.Label(row, text=n, bg=CARD, fg=TEXT, font=FONT_S, anchor="w",
                     justify="left", wraplength=400).pack(side="left", padx=(4, 0))

    def _card_account(self, body, step):
        txt = step.get("account", "")
        warn = "负责人" in txt
        box = tk.Frame(body, bg=WARN_BG if warn else MUTED)
        box.pack(fill="x", padx=22, pady=(12, 0))
        tk.Label(box, text="用这个账号", bg=box["bg"], fg=WARN if warn else SUB,
                 font=FONT_S).pack(side="left", padx=(10, 8), pady=8)
        tk.Label(box, text=txt, bg=box["bg"], fg=TEXT, font=FONT,
                 wraplength=460, justify="left").pack(side="left", pady=8)

    def _card_fields(self, body, step):
        box = self._section(body, "要填的内容")
        ctx = ctx_of(self.case)
        for f in step.get("fields", []):
            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f.get("label", ""), bg=CARD, fg=SUB, font=FONT_S,
                     width=13, anchor="w").pack(side="left")
            val = f.get("template") or f.get("value")
            val = fill(str(val), ctx) if isinstance(val, str) else val
            if f.get("unit"):
                val = f"{val} {f['unit']}"
            tk.Label(row, text=str(val), bg=CARD,
                     fg=SUB if f.get("locked") else TEXT, font=FONT,
                     anchor="w", justify="left", wraplength=380).pack(
                side="left", fill="x", expand=True)
            if f.get("locked"):
                tk.Label(row, text="固定", bg=CARD, fg=SUB, font=FONT_S).pack(side="right")
            elif f.get("note"):
                tk.Label(row, text=f["note"], bg=CARD, fg=WARN, font=FONT_S).pack(side="right")

    def _card_notes(self, body, step):
        box = self._section(body, "注意")
        for n in step.get("notes", []):
            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", pady=1)
            tk.Label(row, text="·", bg=CARD, fg=WARN, font=FONT).pack(side="left", anchor="n")
            tk.Label(row, text=n, bg=CARD, fg=TEXT, font=FONT_S, anchor="w",
                     justify="left", wraplength=560).pack(side="left", padx=(4, 0))

    def _card_materials(self, body, step):
        box = self._section(body, "要交的材料")
        have = {m.get("material_id") for m in self.case.get("materials", [])
                if m.get("material_id")}
        for m in step.get("materials", []):
            ok = m["id"] in have
            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", pady=2)
            tk.Label(row, text="✓" if ok else "○", bg=CARD, fg=OK if ok else SUB,
                     font=FONT_B if ok else FONT).pack(side="left")
            tk.Label(row, text=m.get("name", ""), bg=CARD, fg=TEXT if ok else SUB,
                     font=FONT, anchor="w").pack(side="left", padx=(8, 6))
            if ok:
                rec = next((x for x in self.case.get("materials", [])
                            if x.get("material_id") == m["id"]), None)
                if rec:
                    flat_btn(row, "看", lambda r=rec: self._open(str(material_path(self.case, r))),
                             fg=ACCENT).pack(side="right")
            else:
                flat_btn(row, "选文件",
                         lambda mid=m["id"], sid=step["id"]: self.pick_material(mid, sid),
                         fg=ACCENT).pack(side="right")

    def _card_wait(self, body, step, st):
        since = st.get("since") or today()
        days = 0
        try:
            t0 = time.mktime(time.strptime(since, "%Y-%m-%d"))
            days = max(0, int((time.time() - t0) // 86400))
        except Exception:
            pass
        box = tk.Frame(body, bg=MUTED)
        box.pack(fill="x", padx=22, pady=(14, 0))
        info = f"已等待 {days} 天"
        if step.get("approvers"):
            info += f" · {step['approvers']} 位审批人"
        if step.get("eta_days"):
            info += f" · 预计 {step['eta_days']} 天"
        tk.Label(box, text=info, bg=MUTED, fg=TEXT, font=FONT).pack(side="left", padx=12, pady=9)
        flat_btn(box, "复制催办话术", lambda: self._copy(
            f"您好，我这边有一笔{self.case.get('fields', {}).get('title', '申请')}"
            f"的流程卡在审批，方便的时候麻烦看一下，谢谢。"), fg=ACCENT).pack(
            side="right", padx=10)

    def _card_actions(self, parent, step, st):
        bar = tk.Frame(parent, bg=CARD)
        bar.pack(fill="x", padx=6, pady=2)
        if self.editing:
            solid_btn(bar, "完成编辑", self.toggle_edit).pack(side="left")
            flat_btn(bar, "编辑内容", lambda: self.edit_step(step), fg=ACCENT).pack(
                side="left", padx=10)
            flat_btn(bar, "上移", lambda: self.move_step(-1)).pack(side="left", padx=4)
            flat_btn(bar, "下移", lambda: self.move_step(1)).pack(side="left", padx=4)
            flat_btn(bar, "删除", lambda: self.delete_step(step), fg="#B91C1C").pack(
                side="left", padx=4)
            return
        if st.get("state") == "done":
            tk.Label(bar, text="✓ 这一步已完成", bg=CARD, fg=OK, font=FONT).pack(side="left")
        else:
            solid_btn(bar, "完成这一步", lambda: self.finish_step(step)).pack(side="left")
        if step.get("generate"):
            flat_btn(bar, "生成草稿", lambda: self.generate_draft(step), fg=ACCENT,
                     bg=ACCENT_BG, pad=(12, 6)).pack(side="left", padx=10)
        if step.get("assemble"):
            flat_btn(bar, "合并打印包", lambda: self.do_assemble(step), fg=ACCENT,
                     bg=ACCENT_BG, pad=(12, 6)).pack(side="left")

    # ---------------- 材料
    def pick_material(self, mid, sid):
        p = filedialog.askopenfilename(title="选择材料")
        if not p:
            return
        rec = self.store.add_material(self.case, p, mid, sid)
        if rec:
            self._refresh_all()
            self._refresh_cases()
            self.say("已添加：" + rec["name"], "ok")
        else:
            self.say("添加失败", "err")

    def add_any_material(self):
        if not self.case:
            return
        p = filedialog.askopenfilename(title="选择材料")
        if not p:
            return
        rec = self.store.add_material(self.case, p, None, self.case.get("current"))
        if rec:
            self._refresh_all()
            self.say("已添加：" + rec["name"], "ok")

    def remove_material(self, rec):
        if not messagebox.askyesno("删除材料", f"删掉「{rec.get('name')}」？"):
            return
        self.store.remove_material(self.case, rec)
        self._refresh_all()

    def _refresh_materials(self):
        box = self.mat_scroll
        box.clear()
        self._thumbs = []
        ms = self.case.get("materials", []) if self.case else []
        if not ms:
            tk.Label(box.inner, text="还没有材料\n点右上角「添加」", bg=CARD, fg=SUB,
                     font=FONT_S, justify="left").pack(anchor="w", padx=16, pady=16)
            return
        groups = {}
        for rec in ms:
            groups.setdefault(rec.get("step") or "", []).append(rec)
        order = [s["id"] for s in self.case["flow"].get("steps", [])]
        for sid in order + ([""] if "" in groups else []):
            items = groups.get(sid) or []
            if not items:
                continue
            step = find_step(self.case["flow"], sid)
            if step:
                title = f"{step_index(self.case['flow'], sid) + 1} · {step['name']}"
            else:
                title = "其他"
            tk.Label(box.inner, text=f"{title} · {len(items)} 份", bg=CARD, fg=SUB,
                     font=FONT_S).pack(anchor="w", padx=16, pady=(12, 4))
            for rec in items:
                self._material_row(box.inner, rec)

    def _material_row(self, parent, rec):
        p = material_path(self.case, rec)
        card = tk.Frame(parent, bg="#FAFBFC", highlightbackground=LINE,
                        highlightthickness=1, cursor="hand2")
        card.pack(fill="x", padx=12, pady=3)
        img = render_preview(p, 96, 68)
        if img is not None and ImageTk is not None:
            ph = ImageTk.PhotoImage(img)
            self._thumbs.append(ph)
            lab = tk.Label(card, image=ph, bg="#FAFBFC", bd=0)
        else:
            lab = tk.Label(card, text="文件", bg="#FAFBFC", fg=SUB, font=FONT_S, width=10)
        lab.pack(side="left", padx=6, pady=6)
        self.hover.attach(lab, p)
        right = tk.Frame(card, bg="#FAFBFC")
        right.pack(side="left", fill="x", expand=True, padx=(2, 6))
        shown = rec.get("name", "")
        if len(shown) > 13:
            shown = shown[:12] + "…"
        tk.Label(right, text=shown, bg="#FAFBFC", fg=TEXT, font=FONT_S,
                 anchor="w", justify="left").pack(anchor="w", pady=(9, 0))
        tk.Label(right, text=rec.get("added", ""), bg="#FAFBFC", fg=SUB,
                 font=FONT_S).pack(anchor="w")
        flat_btn(card, "×", lambda r=rec: self.remove_material(r), fg=SUB,
                 bg="#FAFBFC").pack(side="right", padx=6)
        for w in (card, lab, right):
            w.bind("<Button-1>", lambda e, pp=p: self._open(str(pp)))

    # ---------------- 动作
    def finish_step(self, step):
        problems = run_checks(self.case, step)
        if problems:
            msg = "\n".join("· " + x for x in problems)
            if not messagebox.askyesno("还有检查没过", f"{msg}\n\n仍然标记为已完成吗？"):
                self.say(problems[0], "warn")
                return
        st = self.case["steps"].setdefault(step["id"], {})
        st["state"] = "done"
        st["done_at"] = now()
        nxt = (step.get("next") or [None])[0]
        if nxt:
            self.case["current"] = nxt
            ns = self.case["steps"].setdefault(nxt, {"state": "todo"})
            if ns.get("state") == "todo":
                ns["state"] = "doing"
                ns["since"] = today()
        self.store.save(self.case)
        self._refresh_all()
        self._refresh_cases()
        self.say("已完成：" + step.get("name", ""), "ok")

    def generate_draft(self, step):
        tpl = (step.get("generate") or {}).get("template", "")
        text = fill(tpl, ctx_of(self.case))
        win = tk.Toplevel(self.root)
        win.title("申请草稿")
        win.geometry("620x460")
        win.configure(bg=CARD)
        tk.Label(win, text="复制下面的内容，粘到申请单里", bg=CARD, fg=SUB,
                 font=FONT_S).pack(anchor="w", padx=16, pady=(12, 4))
        txt = tk.Text(win, wrap="word", font=FONT, bd=0, bg="#FAFBFC", padx=12, pady=10)
        txt.pack(fill="both", expand=True, padx=16, pady=8)
        txt.insert("1.0", text)
        bar = tk.Frame(win, bg=CARD)
        bar.pack(fill="x", padx=16, pady=(0, 12))
        solid_btn(bar, "复制", lambda: (self._copy(txt.get("1.0", "end-1c")),
                                        win.destroy())).pack(side="right")
        flat_btn(bar, "关闭", win.destroy).pack(side="right", padx=8)

    def do_assemble(self, step):
        ok, msg = assemble_pack(self.case, step)
        if not ok:
            self.say("合并失败：" + msg, "err")
            return
        out = self.store.case_dir(self.case) / step["assemble"][0].get("output", "打印包.pdf")
        self.say("打印包已生成（" + msg + "）", "ok")
        self._open(str(out))

    # ---------------- 编辑流程
    def toggle_edit(self):
        self.editing = not self.editing
        try:
            self.btn_edit.configure(fg=ACCENT if self.editing else SUB)
        except Exception:
            pass
        self._refresh_strip()
        self._refresh_card()
        self.say("编辑模式：加步骤、改内容、调顺序" if self.editing else "已退出编辑")

    def relink(self):
        steps = self.case["flow"].get("steps", [])
        for i, s in enumerate(steps):
            s["next"] = [steps[i + 1]["id"]] if i + 1 < len(steps) else []

    def add_step(self):
        sid = "s" + uuid.uuid4().hex[:4]
        step = {"id": sid, "name": "新步骤", "summary": "", "phase": "其他",
                "kind": "action", "automation": "manual", "entry": [], "notes": [],
                "materials": [], "next": []}
        self.case["flow"].setdefault("steps", []).append(step)
        self.case["steps"].setdefault(sid, {"state": "todo"})
        self.relink()
        self.case["current"] = sid
        self.store.save(self.case)
        self._refresh_all()
        self.edit_step(step)

    def move_step(self, delta):
        step = find_step(self.case["flow"], self.case.get("current"))
        steps = self.case["flow"].get("steps", [])
        if not step:
            return
        i = steps.index(step)
        j = i + delta
        if 0 <= j < len(steps):
            steps[i], steps[j] = steps[j], steps[i]
            self.relink()
            self.store.save(self.case)
            self._refresh_all()

    def delete_step(self, step):
        steps = self.case["flow"].get("steps", [])
        if len(steps) <= 1:
            self.say("至少留一步", "warn")
            return
        if not messagebox.askyesno("删除步骤", f"删掉「{step['name']}」？"):
            return
        self.case["flow"]["steps"] = [s for s in steps if s["id"] != step["id"]]
        self.case["steps"].pop(step["id"], None)
        self.relink()
        self.case["current"] = self.case["flow"]["steps"][0]["id"]
        self.store.save(self.case)
        self._refresh_all()
        self._refresh_cases()

    def edit_step(self, step):
        win = tk.Toplevel(self.root)
        win.title("编辑步骤")
        win.geometry("600x680")
        win.configure(bg=CARD)
        box = tk.Frame(win, bg=CARD)
        box.pack(fill="both", expand=True, padx=18, pady=12)

        def lbl(t):
            tk.Label(box, text=t, bg=CARD, fg=SUB, font=FONT_S).pack(anchor="w", pady=(8, 2))

        def entry(value):
            e = tk.Entry(box, font=FONT, bd=1, relief="solid")
            e.insert(0, value or "")
            e.pack(fill="x")
            return e

        def text(value, h):
            t = tk.Text(box, height=h, font=FONT, bd=1, relief="solid", wrap="word")
            t.insert("1.0", value or "")
            t.pack(fill="x")
            return t

        lbl("名称")
        e_name = entry(step.get("name", ""))
        lbl("一句话（卡片上那行小字）")
        e_sum = entry(step.get("summary", ""))
        lbl("用谁的账号（可空）")
        e_acc = entry(step.get("account", ""))
        lbl("入口（每行：标签 | 地址，地址可以是网址或路径）")
        e_ent = text("\n".join(f"{x.get('label', '')} | {x.get('value', '')}"
                               for x in (step.get("entry") or [])), 3)
        lbl("注意（每行一条）")
        e_note = text("\n".join(step.get("notes") or []), 6)
        lbl("材料（每行一个名字）")
        e_mat = text("\n".join(m.get("name", "") for m in (step.get("materials") or [])), 3)

        kind = tk.StringVar(value=step.get("kind", "action"))
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x", pady=(10, 0))
        tk.Label(row, text="类型", bg=CARD, fg=SUB, font=FONT_S).pack(side="left")
        for val, name in (("action", "动作"), ("wait", "等待"), ("offline", "线下")):
            tk.Radiobutton(row, text=name, value=val, variable=kind, bg=CARD,
                           font=FONT_S, activebackground=CARD).pack(side="left", padx=6)

        def save():
            step["name"] = e_name.get().strip() or step.get("name", "步骤")
            step["summary"] = e_sum.get().strip()
            step["kind"] = kind.get()
            acc = e_acc.get().strip()
            if acc:
                step["account"] = acc
            else:
                step.pop("account", None)
            ents = []
            for line in e_ent.get("1.0", "end").splitlines():
                line = line.strip()
                if not line:
                    continue
                if "|" in line:
                    a, b = [x.strip() for x in line.split("|", 1)]
                else:
                    a, b = "打开", line
                ents.append({"type": "url" if b.startswith("http") else "path",
                             "label": a or "打开", "value": b})
            step["entry"] = ents
            step["notes"] = [x.strip() for x in e_note.get("1.0", "end").splitlines()
                             if x.strip()]
            old = step.get("materials") or []
            mats = []
            for i, line in enumerate([x.strip() for x in e_mat.get("1.0", "end").splitlines()
                                      if x.strip()]):
                base = old[i] if i < len(old) else {}
                mats.append({**base, "id": base.get("id") or f"{step['id']}_m{i + 1}",
                             "name": line, "required": True,
                             "usage": base.get("usage", "upload")})
            step["materials"] = mats
            self.store.save(self.case)
            win.destroy()
            self._refresh_all()
            self._refresh_cases()
            self.say("已保存")

        bar = tk.Frame(win, bg=CARD)
        bar.pack(fill="x", padx=18, pady=(0, 12))
        solid_btn(bar, "保存", save).pack(side="right")
        flat_btn(bar, "取消", win.destroy).pack(side="right", padx=8)

    # ---------------- 模板
    def new_case(self):
        if not self.store.templates:
            self.say("没有可用模板", "err")
            return
        tpl = self.store.templates[0]
        case = self.store.new_case(tpl)
        case["fields"] = {
            "title": tpl.get("name", "") + " 事项",
            "amount": 0,
            "company": "",
            "owner": "",
            "patent_nos": [],
            "project": "",
            "org_unit": "",
            "deadline": "",
        }
        self.store.save(case)
        self.cases = self.store.cases()
        self.case = case
        self._refresh_cases()
        self._refresh_all()
        self.say("新建了一个事项")

    def import_flow(self):
        p = filedialog.askopenfilename(title="导入流程",
                                       filetypes=[("流程文件", "*.flow.json"), ("所有文件", "*.*")])
        if not p:
            return
        try:
            flow = read_json(p)
        except Exception as e:
            messagebox.showerror("导入失败", f"读不了这个文件：\n{e}")
            return
        errs = validate_flow(flow)
        if errs:
            messagebox.showerror("导入失败", "\n".join(errs[:8]))
            return
        n_step = len(flow.get("steps", []))
        n_check = sum(len(s.get("checks") or []) for s in flow.get("steps", []))
        ok = messagebox.askokcancel(
            "导入流程",
            f"{flow.get('name')}\n"
            f"更新于 {flow.get('updated', '未知')}\n\n"
            f"{n_step} 步 · {n_check} 项检查\n\n导入为一个新模板并新建事项？")
        if not ok:
            return
        write_json(TEMPLATES_DIR / f"{flow.get('id', 'flow')}.flow.json", flow)
        self.store.templates = scan_templates()
        case = self.store.new_case(flow)
        case["fields"] = {"title": flow.get("name", "") + " 事项", "amount": 0}
        self.store.save(case)
        self.cases = self.store.cases()
        self.case = case
        self._refresh_cases()
        self._refresh_all()
        self.say("已导入：" + flow.get("name", ""), "ok")

    def export_flow(self, clean=False):
        if not self.case:
            return
        flow = sanitize(self.case["flow"]) if clean else self.case["flow"]
        name = (flow.get("id") or "flow") + (".clean" if clean else "") + ".flow.json"
        p = filedialog.asksaveasfilename(
            title="导出流程", defaultextension=".flow.json", initialfile=name,
            filetypes=[("流程文件", "*.flow.json")])
        if not p:
            return
        write_json(p, flow)
        self.say(("脱敏" if clean else "") + "已导出：" + Path(p).name, "ok")




def solid_btn(parent, text, cmd, bg=ACCENT, fg="white"):
    b = tk.Label(parent, text=text, bg=bg, fg=fg, font=FONT, padx=14, pady=6,
                 cursor="hand2")
    b.bind("<Button-1>", lambda e: cmd())
    b.bind("<Enter>", lambda e: b.configure(bg="#1D4ED8"))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b


# ---------------------------------------------------------------- 自检

def selftest() -> int:
    import tempfile

    ok = True

    def check(name, cond, extra=""):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))

    tpl_path = EXAMPLE_DIR / "patent-annual-fee.flow.json"
    check("模板文件存在", tpl_path.exists())
    if not tpl_path.exists():
        return 1
    flow = read_json(tpl_path)
    errs = validate_flow(flow)
    check("模板通过校验", not errs, str(errs))
    check("步骤数 = 7", len(flow["steps"]) == 7, str(len(flow["steps"])))

    case = {
        "id": "t1", "flow": flow,
        "fields": {"title": "2026 年专利年费缴纳", "amount": 1000,
                   "company": "中国建筑第五工程局有限公司", "owner": "牛其祥",
                   "patent_nos": ["2023118567720", "2024105510076"],
                   "project": "城市更新改造技术研究院-本部",
                   "org_unit": "城市更新改造技术研究院"},
        "steps": {s["id"]: {"state": "todo"} for s in flow["steps"]},
        "materials": [], "current": "s1",
    }
    ctx = ctx_of(case)
    check("申请号拼接", ctx["patent_nos"] == "2023118567720+2024105510076", ctx["patent_nos"])

    step1 = find_step(flow, "s1")
    draft = fill(step1["generate"]["template"], ctx)
    check("草稿没有残留占位符", "{" not in draft)
    check("草稿含事由", "2026 年专利年费缴纳" in draft)
    check("草稿含金额", "1000" in draft)

    step5 = find_step(flow, "s5")
    summary = next(f for f in step5["fields"] if f["label"] == "付款摘要")
    line = fill(summary["template"], ctx)
    check("付款摘要含公司和人名", "中国建筑第五工程局有限公司" in line and "牛其祥" in line, line)

    name = auto_name(2, "中央非税收入统一票据", "x.PDF", "2026-11-05")
    check("自动命名", name == "02_中央非税收入统一票据_2026-11-05.pdf", name)

    clean = sanitize(flow)
    check("脱敏替换客商", clean["dicts"]["vendors"] == ["{vendor}"],
          str(clean["dicts"]["vendors"]))

    bad = json.loads(json.dumps(flow))
    bad["steps"][0]["next"] = ["s99"]
    check("坏流程能报错", bool(validate_flow(bad)))

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        if Image is not None:
            p = td / "a.png"
            Image.new("RGB", (300, 200), (200, 210, 220)).save(p)
            img = render_preview(p, 100, 100)
            check("图片预览渲染", img is not None and max(img.size) <= 100,
                  str(img.size if img else None))
        else:
            check("图片预览渲染", True, "PIL 不可用，跳过")

        if pdfium is not None and PdfWriter is not None:
            try:
                paths = []
                for i in range(2):
                    doc = pdfium.PdfDocument.new()
                    doc.new_page(200 + i * 20, 300)
                    fp = td / f"p{i}.pdf"
                    doc.save(str(fp))
                    doc.close()
                    paths.append(fp)
                out = td / "merged.pdf"
                good, msg = merge_pdfs(paths, out)
                check("PDF 合并", good and out.exists(), msg)
                if good:
                    check("合并后页数 = 2", len(PdfReader(str(out)).pages) == 2)
            except Exception as e:
                check("PDF 合并", False, str(e))
        else:
            check("PDF 合并", True, "依赖缺失，跳过")

    print("\n自检" + ("全部通过" if ok else "有失败项"))
    return 0 if ok else 1


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="流程盒 demo")
    p.add_argument("--selftest", action="store_true", help="跑一遍不依赖界面的自检")
    p.add_argument("--data-dir", default=None, help="数据目录，默认 %%LOCALAPPDATA%%\\flowbox")
    a = p.parse_args(argv)

    if a.selftest:
        return selftest()

    if a.data_dir:
        global DATA_DIR, CASES_DIR, TEMPLATES_DIR
        DATA_DIR = Path(a.data_dir)
        CASES_DIR = DATA_DIR / "cases"
        TEMPLATES_DIR = DATA_DIR / "templates"

    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())







