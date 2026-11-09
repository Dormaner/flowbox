#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""canvas_demo.py — 卡片流程 demo（缩放画布 + 多类型字段）

滚轮平移，Ctrl+滚轮缩放；从右侧圆点拖到别的卡片连线；
点卡片右边出详情；双击或「编辑」改字段。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
import uuid
import webbrowser
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import html_export          # 只读网页导出，跟本文件放一起

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:
    DND_FILES = None
    TkinterDnD = None

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except Exception:
    Image = ImageDraw = ImageFont = ImageTk = None

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent   # exe 旁边
else:
    APP_DIR = Path(__file__).resolve().parent
PROJECTS = APP_DIR / "projects"                    # 每个项目一个文件夹
DEFAULT_PROJECT = "专利年费"
_MUTEX = None

HINT = "双击空白加卡片 · 文件拖到卡片上就是截图/附件 · 中键/右键拖动平移 · Ctrl+滚轮缩放 · 拖右侧圆点到别的卡片连线"

CARD_W, CARD_H = 190, 88
BG = "#F4F5F7"
CARD = "#FFFFFF"
TEXT = "#1F2329"
SUB = "#6B7280"
LINE = "#D8DDE3"
GRID = "#E7EAEE"
ACCENT = "#2563EB"
ACCENT_BG = "#EAF1FE"
WARN = "#B45309"
WARN_BG = "#FDF3E3"
OK = "#15803D"
OK_BG = "#E8F5EC"
MUTED = "#EDEFF2"

FONT = ("Microsoft YaHei UI", 10)
FONT_S = ("Microsoft YaHei UI", 9)
FONT_B = ("Microsoft YaHei UI", 10, "bold")
FONT_H = ("Microsoft YaHei UI", 12, "bold")
FONT_T = ("Microsoft YaHei UI", 14, "bold")

TYPES = [("text", "文本"), ("longtext", "多行文本"), ("select", "单选"),
         ("multiselect", "多选"), ("list", "清单"), ("user", "人员"), ("date", "日期"),
         ("attachment", "附件"), ("image", "图片"), ("number", "数字"),
         ("checkbox", "复选框"), ("link", "超链接")]
TYPE_NAME = dict(TYPES)


def F(kind, label, value="", hint=""):
    return {"id": uuid.uuid4().hex[:6], "type": kind, "label": label,
            "value": value, "hint": hint}


def to_fields(s):
    out = []
    if s.get("shots"):
        out.append(F("image", "操作示意", list(s["shots"])))
    if s.get("notes"):
        out.append(F("multiselect", "注意", list(s["notes"])))
    if s.get("materials"):
        out.append(F("attachment", "要交的材料", [dict(m) for m in s["materials"]]))
    if s.get("account") and s["account"] != "—":
        out.append(F("user", "用谁的账号", s["account"]))
    e = s.get("entry")
    if e:
        f = F("link", "入口", e.get("value", ""))
        f["open_label"] = e.get("label", "打开")
        if e.get("chain"):
            f["chain"] = e["chain"]
        out.append(f)
    for f in s.get("fields") or []:
        out.append(F("text", f.get("label", ""), f.get("value", ""),
                     f.get("note", "")))
    if s.get("done_when"):
        out.append(F("text", "做完的标志", s["done_when"]))
    return out


STEPS = [
    {"id": "s1", "name": "填写《科技研发课题请示》",
     "summary": "在协同平台新建请示，附合同和通知函",
     "account": "本人",
     "entry": {"type": "path", "label": "友空间",
               "value": "工作台 → 协同平台 → 协同工作 → 新建事项",
               "chain": ["工作台", "信创协同", "流程中心", "发起流程",
                         "全部模板", "科技研发课题请示", "立即办理"]},
     "shots": ["files/s1/s1_a.png", "files/s1/s1_b.png"],
     "materials": [{"name": "与专利公司签订的合同", "hint": "PDF，长期合同，可复用"},
                   {"name": "专利公司缴费通知函", "hint": "PDF 或照片"}],
     "notes": ["标题格式必须是「关于……的请示」",
               "「公司」「妥否，请示」「XX课题组」「20XX年XX月」是固定格式",
               "不知道具体金额时，可以只写「列入课题专项经费」"],
     "example": {"title": "上次的正文",
                 "text": "关于2026年专利年费缴纳的请示\n\n城市更新改造技术研究院：\n\n"
                         "拟缴纳2026年专利年费，费用约1000元，列入课题专项经费。\n\n"
                         "妥否，请示。\n\n城市更新改造技术研究院-本部\n2026年11月"},
     "done_when": "协同里出现请示单号，状态是「审批中」"},
    {"id": "s2", "name": "等待请示审批", "summary": "5 位审批人，卡住就催一下",
     "account": "—",
     "notes": ["超过 3 天没动静，发消息问一下", "被打回不要改原单，按意见补材料重提"],
     "done_when": "审批状态变成「已通过」"},
    {"id": "s3", "name": "登录司库一体化平台", "summary": "换成课题负责人的账号登录",
     "account": "课题负责人（先退出自己的友空间账号）",
     "entry": {"type": "url", "label": "司库一体化平台",
               "value": "https://example.com/treasury"},
     "notes": ["自己的账号和负责人账号会冲突，必须先退出再扫码",
               "切换过组织机构后，要重新新建模板才生效"],
     "done_when": "能看到「对外成本费用付款申请」这个模板"},
    {"id": "s4", "name": "上传影像", "summary": "把年费票和代理费票传进报账系统",
     "account": "课题负责人",
     "entry": {"type": "path", "label": "报账系统",
               "value": "对外成本费用付款申请 → 影像"},
     "shots": ["files/s4/s4_a.png"],
     "materials": [{"name": "中央非税收入统一票据",
                    "hint": "必须 PDF，要在财政部平台验过", "done": True},
                   {"name": "代理费发票", "hint": "必须 PDF，不要和年费票合并"}],
     "notes": ["先切「发票」标签传年费票，再切「其他电子票据」传代理费",
               "多个发票会自动合成一张，为了清晰最好分开传",
               "传完关掉影像单据"],
     "done_when": "影像列表里出现两条，都能点开预览"},
    {"id": "s5", "name": "填写付款申请单", "summary": "按下面的值把单子填完",
     "account": "课题负责人",
     "entry": {"type": "path", "label": "报账系统", "value": "对外成本费用付款申请"},
     "shots": ["files/s5/s5_a.png"],
     "fields": [
         {"label": "成本费用属性", "value": "研发支出", "note": "固定"},
         {"label": "是否有合同", "value": "否", "note": "选否才能填客商"},
         {"label": "客商名称", "value": "长沙智路星耀知识产权代理有限公司"},
         {"label": "资金来源", "value": "专项", "note": "固定"},
         {"label": "付款摘要", "value": "中国建筑第五工程局有限公司（牛其祥）申请号 2023118567720"},
         {"label": "付款期", "value": "60 天", "note": "填 30 天被打回过"},
         {"label": "科研经费课题", "value": "城市更新改造技术研究院-本部"}],
     "notes": ["事由不用填，填完客商会自动带出", "两个专利一起缴时，摘要里写两个申请号"],
     "example": {"title": "上次的付款摘要",
                 "text": "中国建筑第五工程局有限公司（牛其祥）申请号 2023118567720+2024105510076"},
     "done_when": "拿到付款申请单号"},
    {"id": "s6", "name": "打印并粘贴", "summary": "报销单 → 票据 → 粘贴单，按这个顺序",
     "account": "—",
     "materials": [{"name": "报销单（付款申请单）", "hint": "黑白打印"},
                   {"name": "票据", "hint": "从小到大排"},
                   {"name": "费用报销粘贴单", "hint": "单位模板"}],
     "notes": ["报销单放第一个，粘贴单放最后", "票据不按顺序也能通过，但别漏页"],
     "done_when": "三份纸按顺序粘好，能一页页翻"},
    {"id": "s7", "name": "送财务处", "summary": "交到中建大厦 1014",
     "account": "—",
     "notes": ["工作日 9:00-11:30，14:00-17:00", "交之前拍一张照片留存"],
     "done_when": "财务签收，或者系统里状态变成「已受理」"},
]


TEMPLATE_DEFS = {
    "空白": [],
    "报销": [
        ("事前申请", "在 OA 里提费用申请，附上依据", ["先请示、再花钱"], ["申请单", "报价或通知函"]),
        ("等审批", "等审批人处理", ["超过 3 天催一下"], []),
        ("拿到发票", "让对方开票，抬头税号别错", ["发票必须是 PDF"], ["发票"]),
        ("填报销单", "在财务系统填单、传附件", ["金额必须和申请单一致"], ["发票", "审批截图"]),
        ("打印送单", "打印、粘贴、送到财务", ["报销单放第一，粘贴单放最后"], ["报销单", "粘贴单"]),
    ],
    "采购": [
        ("提采购申请", "写清型号、数量、预算", ["先查库存再买"], ["需求说明"]),
        ("比价", "至少三家报价", ["低于 5 万也要比价"], ["报价单"]),
        ("签合同", "走法务审合同", ["金额、工期、验收标准"], ["合同"]),
        ("验收", "收货验收、填验收单", ["拍照留档"], ["验收单"]),
        ("付款", "走付款流程", ["付款期 60 天"], ["发票", "验收单"]),
    ],
    "入职": [
        ("发 offer", "确认岗位、薪资、报到日期", ["抬头写公司全称"], ["offer 模板"]),
        ("收材料", "收齐证件和体检报告", ["身份证正反面都要"], ["身份证", "学历证明", "体检报告"]),
        ("建账号", "开通邮箱、OA、门禁", ["先开邮箱再开 OA"], []),
        ("签合同", "劳动合同、保密协议", ["一式两份"], ["劳动合同"]),
        ("入职培训", "讲制度、发手册", ["第一周内完成"], ["培训签到表"]),
    ],
}


def flow_from_template(items):
    nodes, edges = [], []
    for i, (name, summary, notes, mats) in enumerate(items):
        nid = f"t{i + 1}"
        fields = []
        if notes:
            fields.append(F("multiselect", "注意", notes))
        if mats:
            fields.append(F("attachment", "要交的材料",
                            [{"name": m, "hint": ""} for m in mats]))
        fields.append(F("text", "做完的标志", ""))
        nodes.append({"id": nid, "name": name, "summary": summary,
                      "x": 40 + i * 210, "y": 110, "state": "todo",
                      "fields": fields})
        if i:
            edges.append({"a": f"t{i}", "b": nid})
    return {"nodes": nodes, "edges": edges, "groups": []}


def seed():
    nodes = []
    for i, s in enumerate(STEPS):
        nodes.append({"id": s["id"], "name": s["name"], "summary": s["summary"],
                      "x": 40 + i * 210, "y": 110, "fields": to_fields(s),
                      "state": "done" if i < 4 else ("doing" if i == 4 else "todo")})
    nodes.append({"id": "f1", "name": "被打回：改材料",
                  "summary": "看驳回原因，补材料再交", "x": 250, "y": 260,
                  "state": "todo",
                  "fields": [F("multiselect", "注意",
                               ["把驳回意见截图存进这个事项里"]),
                             F("text", "做完的标志", "材料补齐，重新提交")]})
    edges = [{"a": f"s{i}", "b": f"s{i + 1}"} for i in range(1, 7)]
    edges += [{"a": "s2", "b": "f1", "label": "驳回", "kind": "reject"},
              {"a": "f1", "b": "s1", "label": "重新提交", "kind": "ok"}]
    return {"nodes": nodes, "edges": edges, "groups": []}


def _font(size):
    if ImageFont is None:
        return None
    for name in ("msyh.ttc", "simhei.ttf"):
        p = Path(r"C:\Windows\Fonts") / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def ensure_shots(proj: Path) -> None:
    """给示例项目造几张示意截图，按步骤分目录。"""
    files = proj / "files"
    files.mkdir(parents=True, exist_ok=True)
    specs = [("s1", "s1_a.png", "协同 · 新建事项"), ("s1", "s1_b.png", "请示正文"),
             ("s4", "s4_a.png", "影像 · 发票标签"), ("s5", "s5_a.png", "付款申请单")]
    for node_id, name, title in specs:
        d = files / node_id
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        if p.exists() or Image is None:
            continue
        img = Image.new("RGB", (720, 480), "white")
        dr = ImageDraw.Draw(img)
        dr.rectangle([0, 0, 719, 479], outline=(214, 219, 226), width=2)
        dr.rectangle([0, 0, 719, 46], fill=(244, 246, 249))
        dr.text((16, 14), title, fill=(60, 66, 76), font=_font(20))
        y = 78
        for w in (150, 210, 260, 190, 240):
            dr.rectangle([26, y, 26 + w, y + 16], fill=(234, 237, 242))
            dr.rectangle([200, y, 600, y + 16], outline=(208, 213, 220))
            y += 44
        dr.rectangle([188, 66, 610, 128], outline=(214, 62, 62), width=3)
        dr.text((620, 70), "点这里", fill=(214, 62, 62), font=_font(18))
        img.save(p)


def round_path(pts, r=13.0, steps=8):
    """把折线的拐角磨成圆弧（二次贝塞尔近似），返回扁平坐标表。"""
    if len(pts) < 2:
        return [c for p in pts for c in p]
    out = [pts[0][0], pts[0][1]]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        v1 = (p1[0] - p0[0], p1[1] - p0[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1 = (v1[0] ** 2 + v1[1] ** 2) ** 0.5
        l2 = (v2[0] ** 2 + v2[1] ** 2) ** 0.5
        if l1 < 1e-6 or l2 < 1e-6:
            continue
        r1, r2 = min(r, l1 / 2), min(r, l2 / 2)
        a = (p1[0] - v1[0] / l1 * r1, p1[1] - v1[1] / l1 * r1)
        b = (p1[0] + v2[0] / l2 * r2, p1[1] + v2[1] / l2 * r2)
        out += [a[0], a[1]]
        for k in range(1, steps):
            t = k / steps
            mt = 1 - t
            out.append(mt * mt * a[0] + 2 * mt * t * p1[0] + t * t * b[0])
            out.append(mt * mt * a[1] + 2 * mt * t * p1[1] + t * t * b[1])
        out += [b[0], b[1]]
    out += [pts[-1][0], pts[-1][1]]
    return out


def path_mid(pts):
    """按折线总长取一半处的点，标签放这儿最稳。"""
    if len(pts) < 4:
        return (pts[0] if pts else 0), (pts[1] if len(pts) > 1 else 0)
    total = 0.0
    segs = []
    for k in range(0, len(pts) - 2, 2):
        d = ((pts[k + 2] - pts[k]) ** 2 + (pts[k + 3] - pts[k + 1]) ** 2) ** 0.5
        segs.append((d, k))
        total += d
    half = total / 2
    acc = 0.0
    for d, k in segs:
        if acc + d >= half:
            t = 0 if d <= 1e-9 else (half - acc) / d
            return (pts[k] + (pts[k + 2] - pts[k]) * t,
                    pts[k + 1] + (pts[k + 3] - pts[k + 1]) * t)
        acc += d
    return pts[0], pts[1]


def bezier_link(sx, sy, tx, ty, steps=28):
    """贝塞尔连线：正向平着出、平着进；回退绕出去再兜回来。

    跟 web/src/geometry.ts 的 linkControls 是同一套规则，改一处必须改另一处。
    """
    dx = tx - sx
    if tx >= sx + 24:
        k = max(40.0, min(dx * 0.5, 180.0))
        c1x, c1y, c2x, c2y = sx + k, sy, tx - k, ty
    else:
        out = max(60.0, min(abs(dx) * 0.4, 140.0))
        lift = 26.0 if ty >= sy else -26.0
        c1x, c1y, c2x, c2y = sx + out, sy + lift, tx - out, ty + lift
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1.0 - t
        pts.append(mt ** 3 * sx + 3 * mt * mt * t * c1x
                   + 3 * mt * t * t * c2x + t ** 3 * tx)
        pts.append(mt ** 3 * sy + 3 * mt * mt * t * c1y
                   + 3 * mt * t * t * c2y + t ** 3 * ty)
    return pts


def round_rect(cv, x1, y1, x2, y2, r=10, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
           x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


class ScrollFrame(tk.Frame):
    def __init__(self, master, bg=CARD):
        super().__init__(master, bg=bg)
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
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all(
            "<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")

    def clear(self):
        for c in self.inner.winfo_children():
            c.destroy()


class App:
    def __init__(self, root):
        self.root = root
        root.title("卡片连线 demo")
        root.geometry("1240x900+60+30")
        root.configure(bg=BG)

        self.z = 1.0
        self.ox = 40.0
        self.oy = 20.0
        self.pan = None
        self._fonts = {}
        self.sel_node = None
        self.sel_edge = None
        self.sel_nodes = set()
        self.drag = None
        self.temp_line = None
        self.band = None
        self.drawer_node = None
        self._thumbs = []
        self._type_win = None
        self.undo_stack = []
        self.redo_stack = []
        self.show_grid = True
        self._toast_win = None
        self._toast_job = None

        PROJECTS.mkdir(parents=True, exist_ok=True)
        self.projects = self.scan_projects()
        name = os.environ.get("DEMO_PROJECT") or (
            self.projects[0] if self.projects else DEFAULT_PROJECT)
        self.open_project(name)

        self.build()
        self.build_menu()
        self.redraw()
        auto = os.environ.get("DEMO_OPEN")
        if auto:
            self.sel_node = auto
            self.redraw()
            self.open_drawer(auto)
        self.root.after(400, self.first_fit)

    def first_fit(self):
        """第一次打开时，如果内容比窗口宽，就缩到刚好放得下（不低于 70%）。"""
        try:
            w = self.cv.winfo_width()
            if w < 100:
                self.root.after(200, self.first_fit)
                return
            nodes = self.data.get("nodes") or []
            if not nodes:
                return
            x1 = min(n["x"] for n in nodes)
            x2 = max(n["x"] + CARD_W for n in nodes)
            need = x2 - x1 + 80
            if need > w and (w / need) >= 0.7:
                self.fit_view()
        except Exception:
            pass

    def scan_projects(self):
        out = []
        if PROJECTS.exists():
            for d in sorted(PROJECTS.iterdir()):
                if (d / "flow.json").exists():
                    out.append(d.name)
        return out

    def open_project(self, name):
        self.proj_name = name
        self.proj = PROJECTS / name
        (self.proj / "files").mkdir(parents=True, exist_ok=True)
        (self.proj / "snapshots").mkdir(parents=True, exist_ok=True)
        self.data = self.load()
        ensure_shots(self.proj)
        if not (self.proj / "flow.json").exists():
            self.write_flow()
        try:
            self.root.title(f"流程盒子 - {name}")
        except Exception:
            pass

    def _f(self, size, bold=False):
        key = (max(6, int(round(size))), bold)
        if key not in self._fonts:
            self._fonts[key] = tkfont.Font(family="Microsoft YaHei UI",
                                           size=key[0],
                                           weight="bold" if bold else "normal")
        return self._fonts[key]

    def w2s(self, x, y):
        return x * self.z + self.ox, y * self.z + self.oy

    def s2w(self, x, y):
        return (x - self.ox) / self.z, (y - self.oy) / self.z

    def load(self):
        p = self.proj / "flow.json"
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if d.get("nodes"):
                    return d
            except Exception:
                pass
        return seed()

    def write_flow(self):
        p = self.proj / "flow.json"
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, p)          # 原子替换，写到一半断电也不会坏

    def save(self):
        p = self.proj / "flow.json"
        if p.exists():
            snap = self.proj / "snapshots"
            snap.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(p, snap / time.strftime("%Y%m%d-%H%M%S.json"))
                old = sorted(snap.glob("*.json"))
                for f in old[:-5]:
                    f.unlink(missing_ok=True)
            except Exception:
                pass
        self.write_flow()
        self.say("已保存 · " + self.proj_name)

    def node(self, nid):
        for n in self.data["nodes"]:
            if n["id"] == nid:
                return n
        return None

    # ---------------- 骨架
    def build(self):
        top = tk.Frame(self.root, bg=CARD, height=46)
        top.pack(fill="x")
        top.pack_propagate(False)
        self.var_proj = tk.StringVar(value=getattr(self, "proj_name", ""))
        self.cb_proj = ttk.Combobox(top, textvariable=self.var_proj,
                                    values=self.projects, width=13,
                                    state="readonly", font=FONT_S)
        self.cb_proj.bind("<<ComboboxSelected>>",
                          lambda e: self.switch_project(self.var_proj.get()))

        def mkbtn(text, cmd, fg=TEXT, bg=CARD):
            b = tk.Label(top, text=text, fg=fg, bg=bg, font=FONT_S, padx=10, pady=5,
                         cursor="hand2")
            b.bind("<Button-1>", lambda e: cmd())
            b.pack(side="right", padx=4, pady=9)
            return b

        mkbtn("保存", self.save)
        mkbtn("＋ 加卡片", self.add_node, fg=ACCENT, bg=ACCENT_BG)
        mkbtn("1:1", self.reset_zoom)
        mkbtn("＋", lambda: self.zoom_at(1.2))
        mkbtn("－", lambda: self.zoom_at(1 / 1.2))
        self.lbl_zoom = tk.Label(top, text="100%", bg=CARD, fg=SUB, font=FONT_S)
        self.lbl_zoom.pack(side="right", padx=6, pady=13)

        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)
        self.body = body

        self.cv = tk.Canvas(body, bg=BG, highlightthickness=0, bd=0)
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.bind("<B1-Motion>", self.on_motion)
        self.cv.bind("<ButtonRelease-1>", self.on_release)
        self.cv.bind("<Button-1>", self.on_empty_press)
        self.cv.bind("<Double-Button-1>", self.on_empty_dbl)
        self.cv.bind("<Button-2>", self.start_pan)
        self.cv.bind("<Button-3>", self.on_right_press)
        self.cv.bind("<B2-Motion>", self.on_motion)
        self.cv.bind("<B3-Motion>", self.on_right_motion)
        self.cv.bind("<ButtonRelease-2>", self.on_release)
        self.cv.bind("<ButtonRelease-3>", self.on_right_release)
        self.cv.bind("<Delete>", lambda e: self.delete_sel())
        self.cv.bind("<BackSpace>", lambda e: self.delete_sel())
        self.cv.bind("<MouseWheel>", self.on_wheel)
        self.cv.bind("<Control-MouseWheel>", self.on_ctrl_wheel)
        self.cv.focus_set()

        if DND_FILES and hasattr(self.cv, "drop_target_register"):
            try:
                self.cv.drop_target_register(DND_FILES)
                self.cv.dnd_bind("<<Drop>>", self.on_drop)
            except Exception:
                pass

        self.drawer = tk.Frame(body, bg=CARD, width=400)
        self.dline = tk.Frame(body, bg=LINE, width=1)
        self.dscroll = ScrollFrame(self.drawer, bg=CARD)

        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x")
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=16, pady=6)
        self.hint = tk.Label(bar, text=HINT, bg=BG, fg="#9AA1AA", font=FONT_S,
                             anchor="w")
        self.hint.pack(side="left")
        self.status = tk.Label(bar, text="", bg=BG, fg=SUB, font=FONT_S, anchor="e")
        self.status.pack(side="right")

    def say(self, msg):
        self.status.configure(text=msg)
        self.toast(msg)

    def on_drop(self, e):
        try:
            paths = list(self.root.tk.splitlist(e.data))
        except Exception:
            paths = [str(e.data)]
        nid = self.hit_node(e.x, e.y) or self.sel_node
        if not nid:
            self.toast("拖到某张卡片上再松手")
            return "break"
        n = self.node(nid)
        if not n:
            return "break"
        imgs = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
        d = self.proj / "files" / nid
        d.mkdir(parents=True, exist_ok=True)
        n_img = n_att = 0
        for p in paths:
            p = str(p).strip("{}")
            fp = Path(p)
            if not fp.is_file():
                continue
            if fp.suffix.lower() in imgs:
                f = next((x for x in n.get("fields", []) if x.get("type") == "image"), None)
                if f is None:
                    f = F("image", "截图", [])
                    n.setdefault("fields", []).append(f)
                dst = d / f"shot_{uuid.uuid4().hex[:6]}{fp.suffix.lower()}"
                try:
                    shutil.copy2(fp, dst)
                except Exception:
                    continue
                if not isinstance(f.get("value"), list):
                    f["value"] = []
                f["value"].append(f"files/{nid}/{dst.name}")
                n_img += 1
            else:
                f = next((x for x in n.get("fields", []) if x.get("type") == "attachment"), None)
                if f is None:
                    f = F("attachment", "附件", [])
                    n.setdefault("fields", []).append(f)
                dst = d / f"{uuid.uuid4().hex[:6]}_{fp.stem[:30]}{fp.suffix.lower()}"
                try:
                    shutil.copy2(fp, dst)
                except Exception:
                    continue
                if not isinstance(f.get("value"), list):
                    f["value"] = []
                f["value"].append({"name": fp.stem, "hint": "",
                                   "file": f"files/{nid}/{dst.name}"})
                n_att += 1
        if not (n_img or n_att):
            return "break"
        self.snapshot()
        self.save()
        self.sel_node = nid
        self.redraw()
        if self.drawer_node == nid:
            self.fill_drawer(nid)
        else:
            self.open_drawer(nid)
        self.toast(f"拖进来 {n_img} 张图、{n_att} 个附件")
        return "break"

    def toast(self, msg):
        if self._toast_win is not None:
            try:
                self._toast_win.destroy()
            except Exception:
                pass
            self._toast_win = None
        try:
            w = tk.Toplevel(self.root)
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            tk.Label(w, text=msg, bg="#1F2329", fg="white", font=FONT_S,
                     padx=14, pady=7).pack()
            w.update_idletasks()
            x = self.root.winfo_rootx() + (self.root.winfo_width() - w.winfo_width()) // 2
            y = self.root.winfo_rooty() + self.root.winfo_height() - w.winfo_height() - 44
            w.geometry(f"+{max(0, x)}+{max(0, y)}")
            self._toast_win = w
            if self._toast_job:
                try:
                    self.root.after_cancel(self._toast_job)
                except Exception:
                    pass
            self._toast_job = self.root.after(1800, self._hide_toast)
        except Exception:
            pass

    def _hide_toast(self):
        self._toast_job = None
        if self._toast_win is not None:
            try:
                self._toast_win.destroy()
            except Exception:
                pass
            self._toast_win = None

    def tip(self, widget, text):
        """鼠标停上去显示链接的小浮条。"""
        state = {"win": None, "job": None}

        def show(_e=None):
            state["job"] = None
            if not text:
                return
            w = tk.Toplevel(self.root)
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            tk.Label(w, text=text, bg="#1F2329", fg="white", font=FONT_S,
                     padx=8, pady=4).pack()
            w.update_idletasks()
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            w.geometry(f"+{x}+{y}")
            state["win"] = w

        def hide(_e=None):
            if state["job"]:
                try:
                    self.root.after_cancel(state["job"])
                except Exception:
                    pass
                state["job"] = None
            if state["win"] is not None:
                try:
                    state["win"].destroy()
                except Exception:
                    pass
                state["win"] = None

        widget.bind("<Enter>", lambda e: state.__setitem__(
            "job", self.root.after(400, show)), add="+")
        widget.bind("<Leave>", hide, add="+")
        widget.bind("<Button-1>", hide, add="+")

    def on_empty_dbl(self, e):
        if self.hit_node(e.x, e.y):
            return "break"
        wx, wy = self.s2w(e.x, e.y)
        self.snapshot()
        nid = "n" + uuid.uuid4().hex[:4]
        self.data["nodes"].append({
            "id": nid, "name": "新步骤", "summary": "", "state": "todo",
            "x": max(0, round((wx - CARD_W / 2) / 10) * 10),
            "y": max(0, round((wy - CARD_H / 2) / 10) * 10),
            "fields": []})
        self.sel_node = nid
        self.redraw()
        self.inline_rename(nid)
        return "break"

    def inline_rename(self, nid):
        n = self.node(nid)
        sx, sy = self.w2s(n["x"], n["y"])
        e = tk.Entry(self.cv, font=self._f(10 * self.z), bd=1, relief="solid",
                     bg="white")
        e.insert(0, n.get("name", ""))
        e.select_range(0, "end")
        e.place(x=sx + 6, y=sy + 4, width=max(80, CARD_W * self.z - 12),
                height=max(20, 26 * self.z))
        e.focus_set()

        def commit(_e=None):
            n["name"] = e.get().strip() or "新步骤"
            try:
                e.destroy()
            except Exception:
                pass
            self.redraw()
            self.save()

        e.bind("<Return>", commit)
        e.bind("<FocusOut>", commit)
        e.bind("<Escape>", lambda ev: e.destroy())

    def cycle_state(self, nid):
        n = self.node(nid)
        if not n:
            return "break"
        self.snapshot()
        order = [s["key"] for s in self.status_list()]
        cur = n.get("state", order[0] if order else "todo")
        i = order.index(cur) if cur in order else 0
        n["state"] = order[(i + 1) % len(order)] if order else "todo"
        self.save()
        self.redraw()
        self.toast(self.status_label(n["state"]))
        if self.drawer_node == nid:
            self.fill_drawer(nid)
        return "break"

    # ---------------- 状态
    def status_list(self):
        st = self.data.get("statuses")
        if not st:
            st = [{"key": "todo", "label": "未开始", "color": "#C7CBD1"},
                  {"key": "doing", "label": "进行中", "color": "#2563EB"},
                  {"key": "done", "label": "已完成", "color": "#15803D"}]
            self.data["statuses"] = st
        return st

    def status_color(self, key):
        st = self.status_list()
        for s in st:
            if s["key"] == key:
                return s.get("color", "#C7CBD1")
        return st[0].get("color", "#C7CBD1") if st else "#C7CBD1"

    def status_label(self, key):
        st = self.status_list()
        for s in st:
            if s["key"] == key:
                return s.get("label", key)
        return st[0].get("label", key) if st else key

    def state_menu(self, ev, nid):
        n = self.node(nid)
        if not n:
            return "break"
        cur = n.get("state", "todo")
        m = tk.Menu(self.root, tearoff=0)
        for s in self.status_list():
            m.add_command(label=("● " if s["key"] == cur else "　 ") + s["label"],
                          command=lambda k=s["key"]: self.set_state(nid, k))
        m.add_separator()
        m.add_command(label="编辑状态…", command=self.edit_statuses)
        m.tk_popup(ev.x_root, ev.y_root)
        return "break"

    def set_state(self, nid, key):
        n = self.node(nid)
        if not n:
            return
        self.snapshot()
        n["state"] = key
        self.save()
        self.redraw()
        self.toast(self.status_label(key))
        if self.drawer_node == nid:
            self.fill_drawer(nid)

    def edit_statuses(self, after=None):
        win = tk.Toplevel(self.root)
        win.title("状态")
        win.geometry("320x400")
        win.configure(bg=CARD)
        tk.Label(win, text="每张卡片从这里选自己的进度", bg=CARD, fg=SUB,
                 font=FONT_S).pack(anchor="w", padx=14, pady=(12, 6))
        colors = ["#C7CBD1", "#2563EB", "#15803D", "#B45309", "#7C3AED", "#0891B2"]
        lst = [dict(s) for s in self.status_list()]
        box = tk.Frame(win, bg=CARD)
        box.pack(fill="both", expand=True, padx=14)

        def draw():
            for c in box.winfo_children():
                c.destroy()
            for i, s in enumerate(lst):
                r = tk.Frame(box, bg=CARD)
                r.pack(fill="x", pady=3)
                tk.Label(r, text="●", bg=CARD,
                         fg=s.get("color", "#999"), font=FONT).pack(side="left")
                sv = tk.StringVar(value=s.get("label", ""))
                tk.Entry(r, textvariable=sv, font=FONT_S, bd=1,
                         relief="solid").pack(side="left", fill="x",
                                              expand=True, padx=6)
                sv.trace_add("write", lambda *a, ss=s, v=sv: ss.__setitem__("label", v.get()))
                x = tk.Label(r, text="×", bg=CARD, fg="#B91C1C", cursor="hand2")
                x.pack(side="right")
                x.bind("<Button-1>", lambda e, ii=i: (lst.pop(ii), draw()))
            add = tk.Label(box, text="＋ 加一个状态", bg=ACCENT_BG, fg=ACCENT,
                           font=FONT_S, padx=8, pady=3, cursor="hand2")
            add.pack(anchor="w", pady=4)
            add.bind("<Button-1>", lambda e: (
                lst.append({"key": "s" + uuid.uuid4().hex[:4], "label": "新状态",
                            "color": colors[len(lst) % len(colors)]}), draw()))

        draw()

        def ok():
            self.snapshot()
            self.data["statuses"] = [s for s in lst if str(s.get("label", "")).strip()]
            self.save()
            win.destroy()
            self.redraw()
            if self.drawer_node:
                self.fill_drawer(self.drawer_node)
            if after:
                after()

        bar = tk.Frame(win, bg=CARD)
        bar.pack(fill="x", padx=14, pady=(0, 12))
        self._solid(bar, "保存", ok).pack(side="right")
        self._ghost(bar, "取消", win.destroy).pack(side="right", padx=8)

    # ---------------- 菜单
    def build_menu(self):
        bar = tk.Menu(self.root)
        m = tk.Menu(bar, tearoff=0)
        m.add_command(label="新建项目…", accelerator="Ctrl+N", command=self.new_project)
        m.add_command(label="打开项目…", accelerator="Ctrl+O", command=self.open_project_dialog)
        recent = tk.Menu(m, tearoff=0)
        for name in self.projects[:8]:
            recent.add_command(label=name, command=lambda n=name: self.switch_project(n))
        m.add_cascade(label="最近打开", menu=recent)
        m.add_separator()
        m.add_command(label="另存为副本…", accelerator="Ctrl+Shift+S",
                      command=self.save_as_copy)
        m.add_separator()
        m.add_command(label="导入 zip…", command=self.import_project)
        m.add_command(label="导出 zip…", accelerator="Ctrl+E", command=self.export_project)
        m.add_command(label="导出只读网页…", command=self.export_html)
        m.add_command(label="在文件夹中显示", command=self.reveal_project)
        m.add_separator()
        m.add_command(label="退出", command=self.root.destroy)
        bar.add_cascade(label="文件", menu=m)

        m = tk.Menu(bar, tearoff=0)
        m.add_command(label="撤销", accelerator="Ctrl+Z", command=self.undo)
        m.add_command(label="重做", accelerator="Ctrl+Y", command=self.redo)
        m.add_separator()
        m.add_command(label="删除选中", accelerator="Delete", command=self.delete_sel)
        m.add_command(label="查找…", accelerator="Ctrl+F", command=self.search)
        m.add_command(label="卡片状态…", command=self.edit_statuses)
        bar.add_cascade(label="编辑", menu=m)

        m = tk.Menu(bar, tearoff=0)
        m.add_command(label="放大", accelerator="Ctrl+=", command=lambda: self.zoom_at(1.2))
        m.add_command(label="缩小", accelerator="Ctrl+-", command=lambda: self.zoom_at(1 / 1.2))
        m.add_command(label="实际大小", accelerator="Ctrl+0", command=self.reset_zoom)
        m.add_command(label="适应窗口", accelerator="Ctrl+9", command=self.fit_view)
        m.add_separator()
        m.add_command(label="自动排列", command=self.auto_layout)
        self.var_grid = tk.BooleanVar(value=True)
        m.add_checkbutton(label="显示网格", variable=self.var_grid,
                          command=self.toggle_grid)
        bar.add_cascade(label="视图", menu=m)

        m = tk.Menu(bar, tearoff=0)
        m.add_command(label="快捷键", command=self.show_help)
        m.add_command(label="关于", command=self.show_about)
        bar.add_cascade(label="帮助", menu=m)

        self.root.config(menu=bar)
        for seq, fn in (("<Control-n>", self.new_project),
                        ("<Control-o>", self.open_project_dialog),
                        ("<Control-s>", self.save),
                        ("<Control-e>", self.export_project),
                        ("<Control-z>", self.undo),
                        ("<Control-y>", self.redo),
                        ("<Control-f>", self.search),
                        ("<Control-0>", self.reset_zoom),
                        ("<Control-9>", self.fit_view)):
            self.root.bind_all(seq, lambda e, f=fn: (f(), "break")[1])

    def open_project_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("打开项目")
        win.geometry("320x420")
        win.configure(bg=CARD)
        tk.Label(win, text="选一个项目", bg=CARD, fg=SUB, font=FONT_S).pack(
            anchor="w", padx=14, pady=(12, 6))
        lb = tk.Listbox(win, font=FONT, bd=0, highlightthickness=0,
                        selectbackground=ACCENT_BG, selectforeground=TEXT)
        for name in self.projects:
            lb.insert("end", name)
        lb.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        if self.proj_name in self.projects:
            lb.selection_set(self.projects.index(self.proj_name))

        def ok(_e=None):
            sel = lb.curselection()
            if sel:
                name = lb.get(sel[0])
                win.destroy()
                self.switch_project(name)

        lb.bind("<Double-Button-1>", ok)
        b = tk.Label(win, text="打开", bg=ACCENT, fg="white", font=FONT,
                     padx=14, pady=6, cursor="hand2")
        b.pack(anchor="e", padx=14, pady=(0, 12))
        b.bind("<Button-1>", ok)

    def save_as_copy(self):
        name = simpledialog.askstring("另存为副本", "新项目名字：",
                                      initialvalue=self.proj_name + " 副本",
                                      parent=self.root)
        if not name:
            return
        name = "".join(c for c in name.strip() if c not in '\\/:*?"<>|')
        if not name:
            return
        dst = PROJECTS / name
        if dst.exists():
            messagebox.showwarning("重名", "已经有同名项目了")
            return
        self.save()
        try:
            shutil.copytree(self.proj, dst)
        except Exception as e:
            messagebox.showerror("另存失败", str(e))
            return
        self.projects = self.scan_projects()
        self.cb_proj.configure(values=self.projects)
        self.open_project(name)
        self.var_proj.set(name)
        self.redraw()
        self.say("已另存为：" + name)

    def reveal_project(self):
        try:
            os.startfile(self.proj)      # noqa: S606
        except Exception:
            pass

    def toggle_grid(self):
        self.show_grid = bool(self.var_grid.get())
        self.redraw()

    def fit_view(self):
        nodes = self.data.get("nodes") or []
        if not nodes:
            return
        x1 = min(n["x"] for n in nodes) - 40
        y1 = min(n["y"] for n in nodes) - 40
        x2 = max(n["x"] + CARD_W for n in nodes) + 40
        y2 = max(n["y"] + CARD_H for n in nodes) + 40
        w = max(self.cv.winfo_width(), 400)
        h = max(self.cv.winfo_height(), 300)
        self.z = max(0.4, min(1.6, min(w / (x2 - x1), h / (y2 - y1))))
        self.ox = -x1 * self.z + (w - (x2 - x1) * self.z) / 2
        self.oy = -y1 * self.z + (h - (y2 - y1) * self.z) / 2
        self.redraw()

    def search(self):
        kw = simpledialog.askstring("查找", "在卡片名称、说明、字段里找：", parent=self.root)
        if not kw:
            return
        kw = kw.strip()
        for n in self.data.get("nodes", []):
            blob = " ".join([n.get("name", ""), n.get("summary", "")] +
                            [str(f.get("label", "")) + str(f.get("value", ""))
                             for f in n.get("fields") or []])
            if kw in blob:
                self.sel_node = n["id"]
                self.cv.focus_set()
                self.center_on(n)
                self.redraw()
                self.open_drawer(n["id"])
                self.say("找到了：" + n.get("name", ""))
                return
        self.say("没找到：" + kw)

    def center_on(self, n):
        w = max(self.cv.winfo_width(), 400)
        h = max(self.cv.winfo_height(), 300)
        self.ox = w / 2 - (n["x"] + CARD_W / 2) * self.z
        self.oy = h / 2 - (n["y"] + CARD_H / 2) * self.z

    def show_help(self):
        messagebox.showinfo(
            "快捷键",
            "双击空白：加一张卡\n双击卡片：编辑\n拖动卡片：移动\n"
            "中键/右键拖动：平移画布\nCtrl+滚轮：缩放\n"
            "Ctrl+S 保存　Ctrl+Z 撤销　Ctrl+F 查找\n"
            "Ctrl+0 实际大小　Ctrl+9 适应窗口\nDel 删除选中")

    def show_about(self):
        messagebox.showinfo(
            "关于",
            "卡片连线 demo\n\n把公司里的流程画成卡片，一张卡一步。\n"
            "数据在你自己的电脑上，每个项目一个文件夹。\n\n免费、开源、不联网。")

    # ---------------- 撤销
    def snapshot(self):
        self.undo_stack.append(json.dumps(self.data, ensure_ascii=False))
        if len(self.undo_stack) > 25:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            self.say("没有可撤销的了")
            return
        self.redo_stack.append(json.dumps(self.data, ensure_ascii=False))
        self.data = json.loads(self.undo_stack.pop())
        self.sel_node = None
        self.sel_edge = None
        self.redraw()
        self.say("撤销了一步")

    def redo(self):
        if not self.redo_stack:
            self.say("没有可重做的了")
            return
        self.undo_stack.append(json.dumps(self.data, ensure_ascii=False))
        self.data = json.loads(self.redo_stack.pop())
        self.sel_node = None
        self.sel_edge = None
        self.redraw()
        self.say("重做了一步")



    # ---------------- 缩放 / 平移
    def zoom_at(self, factor, sx=None, sy=None):
        if sx is None:
            sx = max(60, self.cv.winfo_width() / 2)
            sy = max(60, self.cv.winfo_height() / 2)
        wx, wy = self.s2w(sx, sy)
        self.z = max(0.4, min(2.0, self.z * factor))
        self.ox = sx - wx * self.z
        self.oy = sy - wy * self.z
        self.redraw()

    def reset_zoom(self):
        self.z = 1.0
        self.ox, self.oy = 40.0, 20.0
        self.redraw()

    def on_wheel(self, e):
        self.oy += 60 if e.delta > 0 else -60
        self.redraw()

    def on_ctrl_wheel(self, e):
        self.zoom_at(1.12 if e.delta > 0 else 1 / 1.12, e.x, e.y)
        return "break"

    def on_empty_press(self, e):
        if self.drag:
            return "break"
        if not (e.state & 0x0004):
            self.sel_nodes = set()
            self.sel_node = None
        self.sel_edge = None
        self.band = {"x": e.x, "y": e.y, "item": None}
        self.redraw()
        return "break"

    def start_pan(self, e):
        self.pan = {"x": e.x, "y": e.y, "ox": self.ox, "oy": self.oy}
        self.cv.configure(cursor="fleur")
        return "break"

    def draw_grid(self):
        if not self.show_grid:
            return
        cv = self.cv
        step = 24 * self.z
        while step < 12:
            step *= 2
        w = max(cv.winfo_width(), 800)
        h = max(cv.winfo_height(), 600)
        x = self.ox % step
        while x < w:
            cv.create_line(x, 0, x, h, fill=GRID)
            x += step
        y = self.oy % step
        while y < h:
            cv.create_line(0, y, w, y, fill=GRID)
            y += step

    def anchors(self, a, b):
        return (a["x"] + CARD_W, a["y"] + CARD_H / 2, b["x"], b["y"] + CARD_H / 2)

    def edge_points(self, a, b):
        """走线：贝塞尔，水平切线（跟 web/src/geometry.ts 同一套规则）。"""
        x1, y1, x2, y2 = self.anchors(a, b)
        return bezier_link(x1, y1, x2, y2)

    def redraw(self):
        cv = self.cv
        cv.delete("all")
        self.draw_grid()
        z = self.z
        try:
            self.lbl_zoom.configure(text=f"{int(z * 100)}%")
        except Exception:
            pass

        for i, e in enumerate(self.data["edges"]):
            a, b = self.node(e.get("a")), self.node(e.get("b"))
            if not a or not b:
                continue
            world = self.edge_points(a, b)
            pts = []
            for j in range(0, len(world), 2):
                sx, sy = self.w2s(world[j], world[j + 1])
                pts += [sx, sy]
            sel = self.sel_edge == i
            kind = e.get("kind")
            ecol = ACCENT if sel else "#3C4149"
            cv.create_line(*pts, fill=ecol,
                           width=(3.0 if sel else 2.2) * max(0.9, z),
                           dash=(6, 4) if kind == "reject" else None,
                           arrow=tk.LAST, arrowshape=(12, 14, 5),
                           capstyle=tk.ROUND, joinstyle=tk.ROUND,
                           tags=("edge", f"e_{i}"))
            cv.tag_bind(f"e_{i}", "<Button-1>",
                        lambda ev, idx=i: self.pick_edge(idx))
            cv.tag_bind(f"e_{i}", "<Double-Button-1>",
                        lambda ev, idx=i: self.edit_edge(idx))
            cv.tag_bind(f"e_{i}", "<Button-3>",
                        lambda ev, idx=i: self.edge_menu(ev, idx))
            if e.get("label"):
                mx, my = path_mid(pts)
                w = (8 * len(str(e["label"])) + 10) * z
                cv.create_rectangle(mx - w / 2, my - 9 * z, mx + w / 2, my + 9 * z,
                                    fill="white", outline="")
                cv.create_text(mx, my, text=str(e["label"]),
                               font=self._f(8 * z),
                               fill=ACCENT if sel else
                               {"ok": OK, "reject": "#B91C1C"}.get(kind, "#3C4149"),
                               tags=("edge", f"e_{i}"))

        for g in self.data.get("groups", []):
            mem = [self.node(i) for i in g.get("members", [])]
            mem = [m for m in mem if m]
            if not mem:
                continue
            gx1 = min(m["x"] for m in mem) - 16
            gy1 = min(m["y"] for m in mem) - 34
            gx2 = max(m["x"] + CARD_W for m in mem) + 16
            gy2 = max(m["y"] + CARD_H for m in mem) + 16
            a1 = self.w2s(gx1, gy1)
            a2 = self.w2s(gx2, gy2)
            round_rect(cv, a1[0], a1[1], a2[0], a2[1], 14 * z,
                       fill=g.get("color", "#EAF1FE"), outline="#C3CEDF",
                       width=1, tags=("group", f"g_{g['id']}"))
            cv.create_text(a1[0] + 10 * z, a1[1] + 6 * z,
                           text=g.get("name", "组"), anchor="nw",
                           font=self._f(9 * z, True), fill="#5B6B82",
                           tags=("group", f"g_{g['id']}"))

        for n in self.data["nodes"]:
            nid = n["id"]
            sx, sy = self.w2s(n["x"], n["y"])
            w, h = CARD_W * z, CARD_H * z
            sel = nid in self.sel_nodes
            tags = ("node", f"n_{nid}")
            round_rect(cv, sx, sy, sx + w, sy + h, 10 * z, fill=CARD,
                       outline=ACCENT if sel else LINE,
                       width=2 if sel else 1, tags=tags)
            cv.create_text(sx + 13 * z, sy + 10 * z, text=n.get("name", ""),
                           anchor="nw", width=w - 24 * z, font=self._f(10 * z, True),
                           fill=TEXT, tags=tags)
            cv.create_text(sx + 13 * z, sy + 40 * z, text=n.get("summary", ""),
                           anchor="nw", width=w - 24 * z, font=self._f(9 * z),
                           fill=SUB, tags=tags)
            cy = sy + h / 2
            r = max(4.6, 5.6 * z)
            cv.create_arc(sx - r, cy - r, sx + r, cy + r, start=90, extent=180,
                          style=tk.CHORD, fill="white", outline="#1F2329",
                          width=1.5, tags=("inport", f"in_{nid}"))
            cv.create_arc(sx + w - r, cy - r, sx + w + r, cy + r, start=270,
                          extent=180, style=tk.CHORD, fill="white",
                          outline="#1F2329", width=1.5,
                          tags=("outport", f"out_{nid}"))
            st = n.get("state", "todo")
            col = self.status_color(st)
            dr = 5 * z
            cv.create_oval(sx + w - 2 * dr - 7 * z, sy + 6 * z,
                           sx + w - 7 * z, sy + 6 * z + 2 * dr,
                           fill=col, outline="", tags=("st", f"st_{nid}"))
            cv.tag_bind(f"st_{nid}", "<Button-1>",
                        lambda ev, i=nid: self.state_menu(ev, i))
            cv.tag_bind(f"n_{nid}", "<Button-1>",
                        lambda ev, i=nid: self.press_node(ev, i))
            cv.tag_bind(f"n_{nid}", "<Double-Button-1>",
                        lambda ev, i=nid: self.edit_node(i))
            cv.tag_bind(f"out_{nid}", "<Button-1>",
                        lambda ev, i=nid: self.press_out(ev, i))

    # ---------------- 交互
    def near_out_port(self, sx, sy, nid):
        n = self.node(nid)
        px, py = self.w2s(n["x"] + CARD_W, n["y"] + CARD_H / 2)
        return ((px - sx) ** 2 + (py - sy) ** 2) ** 0.5 <= max(18.0, 20 * self.z)

    def nearest_in_port(self, sx, sy):
        best, bd = None, max(26.0, 28 * self.z)
        for n in self.data["nodes"]:
            px, py = self.w2s(n["x"], n["y"] + CARD_H / 2)
            d = ((px - sx) ** 2 + (py - sy) ** 2) ** 0.5
            if d < bd:
                best, bd = n["id"], d
        return best

    def press_node(self, e, nid):
        if self.near_out_port(e.x, e.y, nid):
            return self.press_out(e, nid)
        if e.state & 0x0004:            # Shift 加选
            if nid in self.sel_nodes:
                self.sel_nodes.discard(nid)
            else:
                self.sel_nodes.add(nid)
            self.sel_node = nid if nid in self.sel_nodes else None
        else:
            if nid not in self.sel_nodes:
                self.sel_nodes = {nid}
            self.sel_node = nid
        self.sel_edge = None
        n = self.node(nid)
        wx, wy = self.s2w(e.x, e.y)
        g = self.group_of(nid)
        if g:
            orig = {m: (self.node(m)["x"], self.node(m)["y"])
                    for m in g["members"] if self.node(m)}
            self.drag = {"nid": nid, "dx": wx - n["x"], "dy": wy - n["y"],
                         "orig": {nid: (n["x"], n["y"]), **orig}}
        else:
            self.drag = {"nid": nid, "dx": wx - n["x"], "dy": wy - n["y"]}
        self.cv.focus_set()
        self.redraw()
        self.open_drawer(nid)
        return "break"

    def press_out(self, e, nid):
        n = self.node(nid)
        sx, sy = self.w2s(n["x"] + CARD_W, n["y"] + CARD_H / 2)
        self.drag = {"from": nid}
        self.sel_edge = None
        self.temp_line = self.cv.create_line(sx, sy, e.x, e.y, fill="#2B3138",
                                             width=1.6, dash=(5, 4), arrow=tk.LAST)
        self.hl = self.cv.create_oval(0, 0, 0, 0, outline=OK, width=3,
                                      state="hidden")
        self.say("拖到目标卡片左边的半圆上松开")
        return "break"

    def pick_edge(self, idx):
        self.sel_edge = idx
        self.sel_node = None
        self.redraw()
        self.say("选中了一条连线，按 Delete 删除")
        return "break"

    def edit_edge(self, idx):
        e = self.data["edges"][idx]
        val = simpledialog.askstring("连线标签", "这一条代表什么？（留空表示去掉）",
                                     initialvalue=e.get("label", ""),
                                     parent=self.root)
        if val is None:
            return "break"
        self.snapshot()
        if val.strip():
            e["label"] = val.strip()
        else:
            e.pop("label", None)
        self.save()
        self.redraw()
        return "break"

    def edge_menu(self, ev, idx):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="改标签…", command=lambda: self.edit_edge(idx))
        m.add_separator()
        m.add_command(label="主流程（灰）", command=lambda: self.set_edge_kind(idx, None))
        m.add_command(label="通过（绿）", command=lambda: self.set_edge_kind(idx, "ok"))
        m.add_command(label="驳回（红虚线）", command=lambda: self.set_edge_kind(idx, "reject"))
        m.add_separator()
        m.add_command(label="删除连线", command=lambda: self.del_edge(idx))
        m.tk_popup(ev.x_root, ev.y_root)
        return "break"

    def set_edge_kind(self, idx, kind):
        self.snapshot()
        e = self.data["edges"][idx]
        if kind:
            e["kind"] = kind
        else:
            e.pop("kind", None)
        self.save()
        self.redraw()

    def del_edge(self, idx):
        self.snapshot()
        try:
            del self.data["edges"][idx]
        except Exception:
            pass
        self.sel_edge = None
        self.save()
        self.redraw()

    def on_motion(self, e):
        if self.pan:
            self.ox = self.pan["ox"] + (e.x - self.pan["x"])
            self.oy = self.pan["oy"] + (e.y - self.pan["y"])
            self.redraw()
            return
        if self.band is not None:
            b = self.band
            if b["item"]:
                self.cv.coords(b["item"], b["x"], b["y"], e.x, e.y)
            else:
                b["item"] = self.cv.create_rectangle(
                    b["x"], b["y"], e.x, e.y, outline=ACCENT, dash=(4, 3),
                    fill="", width=1)
            return
        d = self.drag
        if not d:
            return
        if d.get("nid"):
            n = self.node(d["nid"])
            if n:
                if not d.get("moved"):
                    d["moved"] = True
                    self.snapshot()
                wx, wy = self.s2w(e.x, e.y)
                nx, ny = wx - d["dx"], wy - d["dy"]
                nx = round(nx / 10.0) * 10
                ny = round(ny / 10.0) * 10
                for o in self.data["nodes"]:
                    if o["id"] == d["nid"]:
                        continue
                    if abs(nx - o["x"]) < 9 and not d.get("orig"):
                        nx = o["x"]
                    if abs(ny - o["y"]) < 9 and not d.get("orig"):
                        ny = o["y"]
                if d.get("orig"):
                    ddx, ddy = nx - n["x"], ny - n["y"]
                    for mid, (ox, oy) in d["orig"].items():
                        m = self.node(mid)
                        if m:
                            m["x"] = max(0, ox + ddx)
                            m["y"] = max(0, oy + ddy)
                else:
                    n["x"], n["y"] = max(0, nx), max(0, ny)
                self.redraw()
        elif d.get("from") and self.temp_line:
            n = self.node(d["from"])
            sx, sy = self.w2s(n["x"] + CARD_W, n["y"] + CARD_H / 2)
            self.cv.coords(self.temp_line, sx, sy, e.x, e.y)
            tgt = self.nearest_in_port(e.x, e.y)
            if tgt:
                m = self.node(tgt)
                px, py = self.w2s(m["x"], m["y"] + CARD_H / 2)
                r = max(10.0, 13 * self.z)
                self.cv.coords(self.hl, px - r, py - r, px + r, py + r)
                self.cv.itemconfigure(self.hl, state="normal")
            else:
                self.cv.itemconfigure(self.hl, state="hidden")

    def on_release(self, e):
        if self.pan:
            self.pan = None
            self.cv.configure(cursor="")
            return
        if self.band is not None:
            b = self.band
            self.band = None
            if b.get("item"):
                x1, y1, x2, y2 = b["x"], b["y"], e.x, e.y
                lo = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                picked = set()
                for n in self.data["nodes"]:
                    sx, sy = self.w2s(n["x"], n["y"])
                    ex, ey = sx + CARD_W * self.z, sy + CARD_H * self.z
                    if not (ex < lo[0] or sx > lo[2] or ey < lo[1] or sy > lo[3]):
                        picked.add(n["id"])
                if e.state & 0x0004:
                    self.sel_nodes |= picked
                else:
                    self.sel_nodes = picked
                self.sel_node = (list(picked)[0] if picked else None)
            self.redraw()
            return
        self.cv.configure(cursor="")
        d = self.drag
        self.drag = None
        if not d:
            return
        if d.get("from"):
            if self.temp_line:
                self.cv.delete(self.temp_line)
                self.temp_line = None
            try:
                self.cv.delete(self.hl)
            except Exception:
                pass
            target = self.nearest_in_port(e.x, e.y)
            src = d["from"]
            if target and target != src:
                if not any(x["a"] == src and x["b"] == target
                           for x in self.data["edges"]):
                    self.snapshot()
                    self.data["edges"].append({"a": src, "b": target})
                self.say("连上了：" + self.node(src)["name"] + " → "
                         + self.node(target)["name"])
            else:
                self.say("没落在卡片上，再试一次")
            self.redraw()

    def hit_node(self, sx, sy):
        wx, wy = self.s2w(sx, sy)
        for n in reversed(self.data["nodes"]):
            if n["x"] <= wx <= n["x"] + CARD_W and n["y"] <= wy <= n["y"] + CARD_H:
                return n["id"]
        return None

    # ---------------- 抽屉
    def open_drawer(self, nid):
        self.drawer_node = nid
        if not self.drawer.winfo_ismapped():
            self.drawer.pack(side="right", fill="y")
            self.drawer.pack_propagate(False)
            self.dline.pack(side="right", fill="y")
            self.dscroll.pack(fill="both", expand=True)
        self.fill_drawer(nid)

    def close_drawer(self):
        self.drawer_node = None
        self.drawer.pack_forget()
        self.dline.pack_forget()

    def _solid(self, parent, text, cmd):
        b = tk.Label(parent, text=text, bg=ACCENT, fg="white", font=FONT,
                     padx=12, pady=6, cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.configure(bg="#1D4ED8"))
        b.bind("<Leave>", lambda e: b.configure(bg=ACCENT))
        return b

    def _ghost(self, parent, text, cmd):
        b = tk.Label(parent, text=text, bg=ACCENT_BG, fg=ACCENT, font=FONT_S,
                     padx=10, pady=5, cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        return b

    def _label(self, p, text):
        tk.Label(p, text=text, bg=CARD, fg=SUB, font=FONT_S).pack(
            anchor="w", padx=16, pady=(14, 3))

    def fill_drawer(self, nid):
        n = self.node(nid)
        if not n:
            return
        p = self.dscroll.inner
        self.dscroll.clear()
        head = tk.Frame(p, bg=CARD)
        head.pack(fill="x", padx=16, pady=(16, 0))
        tk.Label(head, text=n.get("name", ""), bg=CARD, fg=TEXT, font=FONT_T,
                 wraplength=290, justify="left", anchor="w").pack(side="left")
        close = tk.Label(head, text="✕", bg=CARD, fg=SUB, font=FONT, cursor="hand2")
        close.pack(side="right", anchor="n")
        close.bind("<Button-1>", lambda e: self.close_drawer())
        edit = tk.Label(head, text="编辑", bg=CARD, fg=ACCENT, font=FONT_S,
                        cursor="hand2")
        edit.pack(side="right", anchor="n", padx=(0, 12))
        edit.bind("<Button-1>", lambda e: self.edit_node(nid))

        if n.get("summary"):
            tk.Label(p, text=n["summary"], bg=CARD, fg=SUB, font=FONT,
                     wraplength=330, justify="left", anchor="w").pack(
                fill="x", padx=16, pady=(6, 0))

        st = n.get("state", "todo")
        chip = tk.Label(p, text="● " + self.status_label(st), fg=self.status_color(st),
                        bg=MUTED, font=FONT_S, padx=8, pady=3, cursor="hand2")
        chip.pack(anchor="w", padx=16, pady=(8, 0))
        chip.bind("<Button-1>", lambda e: self.state_menu(e, nid))

        fields = n.get("fields") or []
        if not fields:
            tk.Label(p, text="还没有字段，点下面「＋ 添加字段」", bg=CARD, fg=SUB,
                     font=FONT_S).pack(anchor="w", padx=16, pady=(20, 0))
        for f in fields:
            self.render_field(p, f, nid)

        def add():
            self.add_field_dialog(n.setdefault("fields", []),
                                  lambda: (self.save(), self.fill_drawer(nid)))

        self._ghost(p, "＋ 添加字段", add).pack(anchor="w", padx=16, pady=(16, 20))

    def render_field(self, p, f, nid=None):
        t = f.get("type", "text")
        label = f.get("label", "") or "未命名字段"
        val = f.get("value")

        if t in ("text", "number", "date", "user", "select", "longtext"):
            self._label(p, label)
            tk.Label(p, text=str(val or "—"), bg=CARD, fg=TEXT, font=FONT,
                     wraplength=330, justify="left", anchor="w").pack(
                fill="x", padx=16)
            if f.get("hint"):
                tk.Label(p, text=f["hint"], bg=CARD, fg=SUB, font=FONT_S,
                         wraplength=330, justify="left", anchor="w").pack(
                    fill="x", padx=16)

        elif t in ("multiselect", "list"):
            items = val if isinstance(val, list) else []
            self._label(p, f"{label} · {len(items)} 条")
            for it in items:
                row = tk.Frame(p, bg=CARD)
                row.pack(fill="x", padx=16, pady=1)
                tk.Label(row, text="·", bg=CARD, fg=WARN, font=FONT).pack(
                    side="left", anchor="n")
                tk.Label(row, text=str(it), bg=CARD, fg=TEXT, font=FONT_S,
                         anchor="w", justify="left", wraplength=300).pack(
                    side="left", padx=(4, 0))

        elif t == "attachment":
            items = val if isinstance(val, list) else []
            done = sum(1 for m in items if isinstance(m, dict) and m.get("done"))
            self._label(p, f"{label} · {done}/{len(items)}")
            for idx, m in enumerate(items):
                if not isinstance(m, dict):
                    continue
                row = tk.Frame(p, bg=CARD)
                row.pack(fill="x", padx=16, pady=1)
                ok = bool(m.get("done"))
                dot = tk.Label(row, text="✓" if ok else "○", bg=CARD,
                               fg=OK if ok else SUB, font=FONT_B if ok else FONT,
                               cursor="hand2")
                dot.pack(side="left")
                dot.bind("<Button-1>", lambda e, ff=f, i=idx: self.toggle_material(ff, i))
                col = tk.Frame(row, bg=CARD)
                col.pack(side="left", fill="x", expand=True, padx=(6, 0))
                tk.Label(col, text=m.get("name", ""), bg=CARD, fg=TEXT,
                         font=FONT_S, anchor="w").pack(anchor="w")
                if m.get("hint"):
                    tk.Label(col, text=m["hint"], bg=CARD, fg=SUB, font=FONT_S,
                             anchor="w", wraplength=220).pack(anchor="w")
                if m.get("file") and (self.proj / m["file"]).exists():
                    b = tk.Label(row, text="看", bg=CARD, fg=ACCENT, font=FONT_S,
                                 cursor="hand2")
                    b.pack(side="right")
                    b.bind("<Button-1>", lambda e, ff=f, i=idx: self.open_material(ff, i))
                else:
                    b = tk.Label(row, text="选文件", bg=CARD, fg=ACCENT,
                                 font=FONT_S, cursor="hand2")
                    b.pack(side="right")
                    b.bind("<Button-1>", lambda e, ff=f, i=idx: self.pick_material(ff, i, nid))
            if nid:
                self._ghost(p, "＋ 选文件",
                            lambda: self.pick_material(
                                f, len(f.get("value") or []), nid)
                            ).pack(anchor="w", padx=16, pady=(4, 4))

        elif t == "image":
            items = [s for s in (val or []) if (self.proj / s).exists()]
            self._label(p, label)
            if not items:
                tk.Label(p, text="还没有截图", bg=CARD, fg=SUB,
                         font=FONT_S).pack(anchor="w", padx=16)
            for rel in items[:3]:
                try:
                    im = Image.open(self.proj / rel)
                    im.thumbnail((352, 280))
                    ph = ImageTk.PhotoImage(im)
                except Exception:
                    continue
                self._thumbs.append(ph)
                lab = tk.Label(p, image=ph, bd=1, relief="solid", cursor="hand2")
                lab.pack(anchor="w", padx=16, pady=(0, 6))
                lab.bind("<Button-1>", lambda e, r=rel: self.show_shot(r))
            if nid:
                self._ghost(p, "＋ 选图片",
                            lambda: self._add_shot(nid, f, self._shot_done)
                            ).pack(anchor="w", padx=16, pady=(0, 4))

        elif t == "link":
            url, text = self.link_parts(f)
            self._label(p, label)
            row = tk.Frame(p, bg=CARD)
            row.pack(fill="x", padx=16)
            btn = self._solid(row, text or "打开", lambda: self.open_link(f))
            btn.pack(side="left")
            self.tip(btn, url)
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="复制链接", command=lambda: self.copy_text(url))
            if f.get("chain"):
                menu.add_command(label="分步打开…", command=lambda: self.show_chain(f))
            btn.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

        elif t == "checkbox":
            self._label(p, label)
            tk.Label(p, text="☑ 是" if val else "☐ 否", bg=CARD, fg=TEXT,
                     font=FONT).pack(anchor="w", padx=16)

        else:
            self._label(p, label)
            tk.Label(p, text=str(val or ""), bg=CARD, fg=TEXT, font=FONT,
                     wraplength=330, justify="left", anchor="w").pack(
                fill="x", padx=16)

    # ---------------- 附件
    def _shot_done(self):
        self.snapshot()
        self.save()
        if self.drawer_node:
            self.fill_drawer(self.drawer_node)

    def _pick_into(self, f, nid, redraw):
        """直接把一个真实文件挂到附件字段上。"""
        path = filedialog.askopenfilename(title="选一个文件")
        if not path:
            return
        items = f.get("value")
        if not isinstance(items, list):
            items = []
            f["value"] = items
        d = self.proj / "files" / nid
        d.mkdir(parents=True, exist_ok=True)
        dst = d / f"{len(items) + 1:02d}_{Path(path).stem[:30]}{Path(path).suffix.lower()}"
        try:
            shutil.copy2(path, dst)
        except Exception as e:
            messagebox.showerror("复制失败", str(e))
            return
        items.append({"name": Path(path).stem[:40], "hint": "",
                      "file": f"files/{nid}/{dst.name}", "done": True})
        redraw()

    def toggle_material(self, f, idx):
        items = f.get("value") or []
        if 0 <= idx < len(items) and isinstance(items[idx], dict):
            self.snapshot()
            items[idx]["done"] = not items[idx].get("done")
            self.save()
            self.fill_drawer(self.drawer_node)

    def open_material(self, f, idx):
        items = f.get("value") or []
        if 0 <= idx < len(items):
            p = self.proj / (items[idx].get("file") or "")
            try:
                os.startfile(p)          # noqa: S606
            except Exception as e:
                messagebox.showerror("打不开", str(e))

    def pick_material(self, f, idx, nid):
        path = filedialog.askopenfilename(title="选一个文件")
        if not path:
            return
        d = self.proj / "files" / nid
        d.mkdir(parents=True, exist_ok=True)
        name = f"{idx + 1:02d}_{Path(path).stem[:30]}{Path(path).suffix.lower()}"
        dst = d / name
        try:
            shutil.copy2(path, dst)
        except Exception as e:
            messagebox.showerror("复制失败", str(e))
            return
        items = f.get("value")
        if not isinstance(items, list):
            items = []
            f["value"] = items
        while len(items) <= idx:
            items.append({"name": "", "hint": ""})
        if not items[idx].get("name"):
            items[idx]["name"] = Path(path).stem[:40]
        items[idx]["file"] = f"files/{nid}/{dst.name}"
        items[idx]["done"] = True
        self.snapshot()
        self.save()
        self.fill_drawer(self.drawer_node)
        self.toast("已附加：" + dst.name)

    # ---------------- 小动作
    def link_parts(self, f):
        """返回 (网址, 按钮上的字)。老数据是纯字符串，也认。"""
        v = f.get("value")
        label = f.get("label", "") or "打开"
        if isinstance(v, dict):
            url = str(v.get("url", "")).strip()
            text = str(v.get("text", "")).strip()
        else:
            url = str(v or "").strip()
            text = ""
        return url, (text or f.get("open_label") or label)

    def open_link(self, f):
        v, _ = self.link_parts(f)
        if not v:
            self.toast("这个入口还是空的，先编辑卡片把网址填上")
            return
        u = v
        has_scheme = bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", v)) \
            or v.lower().startswith(("mailto:", "file:", "tel:"))
        looks_url = bool(re.match(r"^[\w.-]+\.[a-zA-Z]{2,}([/:?#].*)?$", v)
                         or v.lower().startswith(("localhost", "\\\\", "/"))
                         or re.match(r"^\d{1,3}(\.\d{1,3}){3}", v))
        if not has_scheme and looks_url:
            u = "https://" + v
        if has_scheme or looks_url:
            ok = False
            try:
                ok = webbrowser.open(u)
            except Exception:
                ok = False
            if not ok:
                try:
                    os.startfile(u)          # noqa: S606
                    ok = True
                except Exception as e:
                    messagebox.showerror("打不开这个链接", f"{u}\n\n{e}")
                    return
            self.say("已打开：" + u)
        elif f.get("chain"):
            self.show_chain(f)
        else:
            self.copy_text(v)

    def copy_text(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text or "")
        self.say("已复制到剪贴板")

    def show_shot(self, rel):
        if Image is None:
            return
        win = tk.Toplevel(self.root)
        win.title("操作示意")
        win.configure(bg="#111827")
        try:
            im = Image.open(self.proj / rel)
            im.thumbnail((1000, 760))
            ph = ImageTk.PhotoImage(im)
            lab = tk.Label(win, image=ph, bg="#111827")
            lab.image = ph
            lab.pack(padx=8, pady=8)
        except Exception:
            tk.Label(win, text="打不开这张图", bg="#111827", fg="white").pack(padx=20, pady=20)

    def show_chain(self, f):
        chain = f.get("chain") or []
        win = tk.Toplevel(self.root)
        win.title("分步打开")
        win.geometry("430x430")
        win.configure(bg=CARD)
        tk.Label(win, text="客户端里没有网址，按顺序点这几下：", bg=CARD, fg=SUB,
                 font=FONT_S).pack(anchor="w", padx=16, pady=(14, 6))
        for i, name in enumerate(chain, 1):
            row = tk.Frame(win, bg="#FAFBFC", highlightbackground=LINE,
                           highlightthickness=1)
            row.pack(fill="x", padx=16, pady=2)
            tk.Label(row, text=str(i), bg="#FAFBFC", fg=SUB, font=FONT_S,
                     width=3).pack(side="left", padx=(8, 0), pady=7)
            tk.Label(row, text=name, bg="#FAFBFC", fg=TEXT, font=FONT).pack(side="left")
            self._ghost(row, "复制", lambda t=name: self.copy_text(t)).pack(
                side="right", padx=8)
        self._ghost(win, "关闭", win.destroy).pack(anchor="e", padx=16, pady=12)

    # ---------------- 加字段（飞书那种）
    def _close_type(self):
        if getattr(self, "_type_win", None) is not None:
            try:
                self._type_win.destroy()
            except Exception:
                pass
        self._type_win = None

    def _type_panel(self, anchor, current, on_pick):
        self._close_type()
        win = tk.Toplevel(self.root)
        self._type_win = win
        win.overrideredirect(True)
        win.configure(bg=CARD, highlightbackground=LINE, highlightthickness=1)
        x = anchor.winfo_rootx() + anchor.winfo_width() + 4
        y = anchor.winfo_rooty()
        win.geometry(f"230x560+{x}+{y}")
        win.lift()

        groups = [("常规", [("text", "文本"), ("select", "单选"), ("multiselect", "多选"),
                            ("user", "人员"), ("date", "日期"), ("attachment", "附件"),
                            ("number", "数字"), ("checkbox", "复选框"), ("link", "超链接")]),
                  ("业务", [("image", "图片")]),
                  ("暂不支持", [("formula", "公式"), ("lookup", "查找引用")])]
        for cat, items in groups:
            tk.Label(win, text=cat, bg=CARD, fg="#9CA3AF", font=FONT_S).pack(
                anchor="w", padx=12, pady=(8, 2))
            for key, name in items:
                disabled = key in ("formula", "lookup")
                row = tk.Label(win, text=name, bg=CARD,
                               fg="#C3C7CE" if disabled else TEXT,
                               font=FONT, anchor="w", padx=12, pady=6,
                               cursor="arrow" if disabled else "hand2")
                row.pack(fill="x")
                if key == current and not disabled:
                    tk.Label(row, text="✓", bg=CARD, fg=ACCENT,
                             font=FONT_S).place(relx=1.0, rely=0.5, anchor="e", x=-12)
                if not disabled:
                    row.bind("<Enter>", lambda e, r=row: r.configure(bg=ACCENT_BG))
                    row.bind("<Leave>", lambda e, r=row: r.configure(bg=CARD))
                    row.bind("<Button-1>", lambda e, k=key: (on_pick(k), self._close_type()))

    def add_field_dialog(self, fields, redraw):
        win = tk.Toplevel(self.root)
        win.title("添加字段")
        win.geometry("420x520")
        win.configure(bg=CARD)
        win.transient(self.root)
        state = {"type": "text", "rows": [], "val": "", "url": "", "text": "",
                 "chk": False}

        tk.Label(win, text="标题", bg=CARD, fg=SUB, font=FONT_S).pack(
            anchor="w", padx=16, pady=(14, 4))
        e_title = tk.Entry(win, font=FONT, bd=1, relief="solid")
        e_title.insert(0, "新字段")
        e_title.pack(fill="x", padx=16)

        tk.Label(win, text="字段类型", bg=CARD, fg=SUB, font=FONT_S).pack(
            anchor="w", padx=16, pady=(12, 4))
        row = tk.Frame(win, bg="#F7F8FA", highlightbackground=LINE,
                       highlightthickness=1)
        row.pack(fill="x", padx=16)
        chip = tk.Label(row, text="文本", bg="#F7F8FA", fg=TEXT, font=FONT,
                        anchor="w", padx=10, pady=8, cursor="hand2")
        chip.pack(side="left", fill="x", expand=True)
        arrow = tk.Label(row, text="›", bg="#F7F8FA", fg=SUB, font=FONT,
                         cursor="hand2")
        arrow.pack(side="right", padx=10)

        def pick(k):
            state["type"] = k
            chip.configure(text=TYPE_NAME.get(k, k))
            render_def()

        lbl_def = tk.Label(win, text="默认值（可留空）", bg=CARD, fg=SUB,
                           font=FONT_S)
        lbl_def.pack(anchor="w", padx=16, pady=(12, 4))
        defbox = tk.Frame(win, bg=CARD)
        defbox.pack(fill="x", padx=16)

        def render_def():
            build_def(defbox)

        def build_def(box):
            def draw_rows(bb=None):
                bb = bb or box
                for c in bb.winfo_children():
                    c.destroy()
                for i, item in enumerate(state["rows"]):
                    r = tk.Frame(bb, bg=CARD)
                    r.pack(fill="x", pady=2)
                    sv = tk.StringVar(value=item)
                    tk.Entry(r, textvariable=sv, font=FONT, bd=1,
                             relief="solid").pack(side="left", fill="x",
                                                  expand=True)
                    sv.trace_add(
                        "write",
                        lambda *a, ii=i, s=sv:
                        state["rows"].__setitem__(ii, s.get())
                        if ii < len(state["rows"]) else None)
                    x = tk.Label(r, text="×", bg=CARD, fg="#B91C1C",
                                 font=FONT_S, cursor="hand2", padx=6)
                    x.pack(side="right")
                    x.bind("<Button-1>", lambda e2, ii=i: (
                        state["rows"].pop(ii), draw_rows()))
                add = tk.Label(bb, text="＋ 添加", bg=ACCENT_BG, fg=ACCENT,
                               font=FONT_S, padx=8, pady=3, cursor="hand2")
                add.pack(anchor="w", pady=4)
                add.bind("<Button-1>",
                         lambda e2: (state["rows"].append(""), draw_rows()))

            for c in box.winfo_children():
                c.destroy()
            t = state["type"]
            if t == "link":
                lbl_def.configure(text="默认值")
                tk.Label(box, text="超链接", bg=CARD, fg=SUB,
                         font=FONT_S).pack(anchor="w", pady=(0, 3))
                u = tk.StringVar(value=state["url"])
                tk.Entry(box, textvariable=u, font=FONT, bd=1,
                         relief="solid").pack(fill="x")
                u.trace_add("write",
                            lambda *a, s=u: state.__setitem__("url", s.get()))
                tk.Label(box, text="文本（按钮上显示的字）", bg=CARD, fg=SUB,
                         font=FONT_S).pack(anchor="w", pady=(8, 3))
                tx = tk.StringVar(value=state["text"])
                tk.Entry(box, textvariable=tx, font=FONT, bd=1,
                         relief="solid").pack(fill="x")
                tx.trace_add("write",
                             lambda *a, s=tx: state.__setitem__("text", s.get()))
            elif t in ("multiselect", "list", "attachment", "image"):
                lbl_def.configure(text={
                    "attachment": "要收的材料（一行一个，可加可删）",
                    "image": "截图",
                }.get(t, "选项（一行一个，可加可删）"))
                if t == "image":
                    tk.Label(box, text="截图不用先填。建好以后在右边点「＋ 选图片」，"
                                       "或者直接把文件拖到卡片上。",
                             bg=CARD, fg=SUB, font=FONT_S, anchor="w",
                             justify="left", wraplength=360).pack(fill="x")
                else:
                    if not state["rows"]:
                        state["rows"] = ["", "", ""]
                    draw_rows()
            elif t == "checkbox":
                lbl_def.configure(text="默认值")
                var = tk.BooleanVar(value=state["chk"])
                tk.Checkbutton(box, text="默认勾上", variable=var, bg=CARD,
                               font=FONT_S, activebackground=CARD,
                               command=lambda: state.__setitem__("chk",
                                                                 var.get())
                               ).pack(anchor="w")
            elif t == "longtext":
                lbl_def.configure(text="默认值（可留空）")
                w = tk.Text(box, height=3, font=FONT, bd=1, relief="solid",
                            wrap="word")
                w.insert("1.0", state["val"])
                w.pack(fill="x")
                w.bind("<KeyRelease>",
                       lambda e, x=w: state.__setitem__(
                           "val", x.get("1.0", "end-1c")))
            else:
                lbl_def.configure(text="默认值（可留空）")
                ev = tk.StringVar(value=state["val"])
                tk.Entry(box, textvariable=ev, font=FONT, bd=1,
                         relief="solid").pack(fill="x")
                ev.trace_add("write",
                             lambda *a, s=ev: state.__setitem__("val", s.get()))

        for w in (row, chip, arrow):
            w.bind("<Button-1>", lambda e: self._type_panel(row, state["type"], pick))

        render_def()

        tk.Label(win, text="推荐", bg=CARD, fg=SUB, font=FONT_S).pack(
            anchor="w", padx=16, pady=(12, 4))
        rec = tk.Frame(win, bg=CARD)
        rec.pack(fill="x", padx=16)
        for title, kind in (("注意", "multiselect"), ("附件", "attachment"),
                            ("截图", "image"), ("做完的标志", "text"),
                            ("入口", "link")):
            b = tk.Label(rec, text=title, bg=ACCENT_BG, fg=ACCENT, font=FONT_S,
                         padx=8, pady=3, cursor="hand2")
            b.pack(side="left", padx=(0, 6))

            def use(t=title, k=kind):
                e_title.delete(0, "end")
                e_title.insert(0, t)
                pick(k)

            b.bind("<Button-1>", lambda e, f=use: f())

        bar = tk.Frame(win, bg=CARD)
        bar.pack(fill="x", padx=16, side="bottom", pady=16)

        def ok():
            self.snapshot()
            label = e_title.get().strip() or "未命名字段"
            kind = state["type"]
            rows = [x.strip() for x in state["rows"] if x.strip()]
            if kind == "link":
                val = {"url": state["url"].strip(), "text": state["text"].strip()}
            elif kind in ("multiselect", "list", "image"):
                val = rows
            elif kind == "attachment":
                val = [{"name": x, "hint": ""} for x in rows]
            elif kind == "checkbox":
                val = bool(state["chk"])
            else:
                val = state["val"]
            fields.append({"id": uuid.uuid4().hex[:6], "type": kind,
                           "label": label, "value": val, "hint": ""})
            win.destroy()
            self._close_type()
            redraw()

        self._solid(bar, "确定", ok).pack(side="right")
        self._ghost(bar, "取消",
                    lambda: (win.destroy(), self._close_type())).pack(side="right", padx=8)

    def _move_field(self, fields, idx, delta, redraw):
        j = idx + delta
        if 0 <= j < len(fields):
            fields[idx], fields[j] = fields[j], fields[idx]
            redraw()

    def _pick_type(self, f, redraw, target=None):
        if getattr(self, "_type_win", None) is not None:
            try:
                self._type_win.destroy()
            except Exception:
                pass
        win = tk.Toplevel(self.root)
        self._type_win = win
        win.title("选字段类型")
        win.geometry("240x450")
        win.configure(bg=CARD)
        tk.Label(win, text="选一个类型", bg=CARD, fg=SUB, font=FONT_S).pack(
            anchor="w", padx=14, pady=(12, 6))
        for key, name in TYPES:
            row = tk.Label(win, text=name, bg=CARD, fg=TEXT, font=FONT,
                           anchor="w", padx=14, pady=7, cursor="hand2")
            row.pack(fill="x")
            row.bind("<Button-1>", lambda e, k=key: self._apply_type(win, f, k, redraw, target))

    def _apply_type(self, win, f, kind, redraw, target):
        default = {"text": "", "longtext": "", "select": "", "multiselect": [],
                   "list": [], "user": "", "date": "", "attachment": [],
                   "image": [], "number": "", "checkbox": False, "link": ""}[kind]
        if f is None:
            target.append({"id": uuid.uuid4().hex[:6], "type": kind,
                           "label": TYPE_NAME.get(kind, kind), "value": default,
                           "hint": ""})
        else:
            f["type"] = kind
            f["value"] = default
        win.destroy()
        self._type_win = None
        redraw()

    def _add_shot(self, nid, f, redraw):
        path = filedialog.askopenfilename(
            title="选一张截图", filetypes=[("图片", "*.png *.jpg *.jpeg")])
        if not path:
            return
        d = self.proj / "files" / nid
        d.mkdir(parents=True, exist_ok=True)
        dst = d / f"shot_{uuid.uuid4().hex[:6]}{Path(path).suffix.lower()}"
        try:
            shutil.copy2(path, dst)
        except Exception:
            return
        if not isinstance(f.get("value"), list):
            f["value"] = []
        f["value"].append(f"files/{nid}/{dst.name}")
        redraw()

    def edit_node(self, nid):
        n = self.node(nid)
        if not n:
            return
        win = tk.Toplevel(self.root)
        win.title("编辑卡片")
        win.geometry("640x820")
        win.configure(bg=CARD)
        sf = ScrollFrame(win, bg=CARD)
        sf.pack(fill="both", expand=True)
        p = sf.inner

        def lab(t):
            tk.Label(p, text=t, bg=CARD, fg=SUB, font=FONT_S).pack(
                anchor="w", padx=16, pady=(10, 3))

        def ent(v):
            e = tk.Entry(p, font=FONT, bd=1, relief="solid")
            e.insert(0, v or "")
            e.pack(fill="x", padx=16)
            return e

        lab("名称")
        e_name = ent(n.get("name"))
        lab("一句话")
        e_sum = ent(n.get("summary"))

        lab("状态")
        sbar = tk.Frame(p, bg=CARD)
        sbar.pack(fill="x", padx=16)
        cur = n.get("state") or self.status_list()[0]["key"]
        picked = {"key": cur}
        sv = tk.StringVar(value=self.status_label(cur))
        cb = ttk.Combobox(sbar, textvariable=sv, state="readonly", font=FONT_S,
                          width=16,
                          values=[s["label"] for s in self.status_list()])
        cb.pack(side="left")

        def on_state(_e=None):
            for s in self.status_list():
                if s["label"] == sv.get():
                    picked["key"] = s["key"]
                    break

        cb.bind("<<ComboboxSelected>>", on_state)
        self._ghost(sbar, "编辑状态…",
                    lambda: self.edit_statuses(draw_states)).pack(
            side="left", padx=8)

        def draw_states():
            vals = [s["label"] for s in self.status_list()]
            cb.configure(values=vals)
            if sv.get() not in vals:
                for s in self.status_list():
                    if s["key"] == picked["key"]:
                        sv.set(s["label"])
                        break

        lab("字段")

        fields = [dict(f) for f in (n.get("fields") or [])]
        box = tk.Frame(p, bg=CARD)
        box.pack(fill="x", padx=16)

        def as_text(f):
            v = f.get("value")
            t = f["type"]
            if t in ("multiselect", "image"):
                return "\n".join(v if isinstance(v, list) else [])
            if t == "attachment":
                items = v if isinstance(v, list) else []
                return "\n".join(f"{(m or {}).get('name', '')}|{(m or {}).get('hint', '')}"
                                 for m in items)
            if t == "checkbox":
                return ""
            return "" if v is None else str(v)

        def draw():
            for c in box.winfo_children():
                c.destroy()
            if not fields:
                tk.Label(box, text="还没有字段，点下面「＋ 加字段」",
                         bg=CARD, fg=SUB, font=FONT_S).pack(anchor="w", pady=6)
            for i, f in enumerate(fields):
                t = f["type"]
                blk = tk.Frame(box, bg="#FAFBFC", highlightbackground=LINE,
                               highlightthickness=1)
                blk.pack(fill="x", pady=4)
                head = tk.Frame(blk, bg="#FAFBFC")
                head.pack(fill="x", padx=6, pady=(6, 2))
                tb = tk.Label(head, text=TYPE_NAME.get(t, t) + " ▾", bg=MUTED,
                              fg=TEXT, font=FONT_S, padx=6, pady=2, cursor="hand2")
                tb.pack(side="left")
                tb.bind("<Button-1>", lambda e, ff=f: self._pick_type(ff, draw))
                lv = tk.StringVar(value=f.get("label", ""))
                tk.Entry(head, textvariable=lv, font=FONT_S, bd=1, relief="solid",
                         width=16).pack(side="left", padx=6)
                lv.trace_add("write", lambda *a, ff=f, v=lv: ff.__setitem__("label", v.get()))

                for txt, cmd in (("×", lambda idx=i: (fields.pop(idx), draw())),
                                 ("↓", lambda idx=i: self._move_field(fields, idx, 1, draw)),
                                 ("↑", lambda idx=i: self._move_field(fields, idx, -1, draw))):
                    b = tk.Label(head, text=txt, bg="#FAFBFC",
                                 fg="#B91C1C" if txt == "×" else SUB,
                                 font=FONT_S, cursor="hand2", padx=3)
                    b.pack(side="right", padx=2)
                    b.bind("<Button-1>", lambda e, c=cmd: c())

                body = tk.Frame(blk, bg="#FAFBFC")
                body.pack(fill="x", padx=6, pady=(0, 6))
                if t == "checkbox":
                    var = tk.BooleanVar(value=bool(f.get("value")))
                    tk.Checkbutton(body, text="是", variable=var, bg="#FAFBFC",
                                   font=FONT_S, activebackground="#FAFBFC",
                                   command=lambda ff=f, v=var: ff.__setitem__("value", v.get())
                                   ).pack(anchor="w")
                elif t == "list":
                    lbox = tk.Frame(body, bg="#FAFBFC")
                    lbox.pack(fill="x")

                    def make_list_drawer(ff, bb):
                        def draw_it():
                            for c in bb.winfo_children():
                                c.destroy()
                            vals = ff.get("value")
                            if not isinstance(vals, list):
                                vals = []
                                ff["value"] = vals
                            for i2, v in enumerate(list(vals)):
                                r = tk.Frame(bb, bg="#FAFBFC")
                                r.pack(fill="x", pady=1)
                                sv = tk.StringVar(value=str(v))
                                tk.Entry(r, textvariable=sv, font=FONT_S, bd=1,
                                         relief="solid").pack(side="left", fill="x",
                                                              expand=True)
                                sv.trace_add(
                                    "write",
                                    lambda *a, vv=vals, ii=i2, s=sv:
                                    vv.__setitem__(ii, s.get()) if ii < len(vv) else None)
                                x2 = tk.Label(r, text="×", bg="#FAFBFC",
                                              fg="#B91C1C", cursor="hand2")
                                x2.pack(side="right", padx=4)
                                x2.bind("<Button-1>",
                                        lambda e, vv=vals, ii=i2:
                                        (vv.pop(ii), draw_it()))
                            add2 = tk.Label(bb, text="＋ 加一条", bg=ACCENT_BG,
                                            fg=ACCENT, font=FONT_S, padx=8, pady=3,
                                            cursor="hand2")
                            add2.pack(anchor="w", pady=3)
                            add2.bind("<Button-1>",
                                      lambda e, vv=vals: (vv.append(""), draw_it()))
                        return draw_it

                    make_list_drawer(f, lbox)()
                elif t == "link":
                    url0, text0 = self.link_parts(f)
                    if not isinstance(f.get("value"), dict):
                        f["value"] = {"url": url0, "text": text0}
                    for cap, key in (("超链接", "url"), ("文本", "text")):
                        tk.Label(body, text=cap, bg="#FAFBFC", fg=SUB,
                                 font=FONT_S).pack(anchor="w")
                        sv2 = tk.StringVar(value=f["value"].get(key, ""))
                        tk.Entry(body, textvariable=sv2, font=FONT_S, bd=1,
                                 relief="solid").pack(fill="x", pady=(0, 4))
                        sv2.trace_add(
                            "write",
                            lambda *a, ff=f, k=key, s=sv2:
                            ff["value"].__setitem__(k, s.get()))
                elif t in ("attachment", "image"):
                    items = f.get("value")
                    if not isinstance(items, list):
                        items = []
                        f["value"] = items
                    names = []
                    for m in items:
                        nm = m.get("name") if isinstance(m, dict) else Path(str(m)).name
                        if nm:
                            names.append(nm)
                    tk.Label(body, text=f"{len(items)} 个 · " + ("、".join(names) or "还没加"),
                             bg="#FAFBFC", fg=SUB, font=FONT_S, anchor="w",
                             justify="left", wraplength=520).pack(fill="x")
                    if t == "attachment":
                        self._ghost(body, "＋ 选文件",
                                    lambda ff=f: self._pick_into(ff, nid, draw)
                                    ).pack(anchor="w", pady=4)
                    else:
                        self._ghost(body, "＋ 选图片",
                                    lambda ff=f: self._add_shot(nid, ff, draw)
                                    ).pack(anchor="w", pady=4)
                elif t in ("multiselect", "longtext"):
                    tx = tk.Text(body, height=3, font=FONT_S, bd=1, relief="solid",
                                 wrap="word")
                    tx.insert("1.0", as_text(f))
                    tx.pack(fill="x")
                    tx.bind("<KeyRelease>", lambda e, ff=f, w=tx:
                            ff.__setitem__("value", w.get("1.0", "end-1c")))
                else:
                    vv = tk.StringVar(value=as_text(f))
                    tk.Entry(body, textvariable=vv, font=FONT, bd=1,
                             relief="solid").pack(fill="x")
                    vv.trace_add("write", lambda *a, ff=f, v=vv:
                                 ff.__setitem__("value", v.get()))


        draw()
        self._ghost(p, "＋ 加字段",
                    lambda: self.add_field_dialog(fields, draw)).pack(
            anchor="w", padx=16, pady=(10, 0))

        def save():
            self.snapshot()
            n["name"] = e_name.get().strip() or "未命名"
            n["summary"] = e_sum.get().strip()
            n["state"] = picked["key"]
            out = []
            for f in fields:
                t = f["type"]
                v = f.get("value")
                if t in ("multiselect", "image") and isinstance(v, str):
                    v = [x.strip() for x in v.splitlines() if x.strip()]
                elif t == "attachment" and isinstance(v, str):
                    items = []
                    for line in v.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        name, _, hint = line.partition("|")
                        items.append({"name": name.strip(), "hint": hint.strip()})
                    v = items
                item = {"id": f.get("id") or uuid.uuid4().hex[:6], "type": t,
                        "label": f.get("label", ""), "value": v,
                        "hint": f.get("hint", "")}
                if f.get("chain"):
                    item["chain"] = f["chain"]
                if f.get("open_label"):
                    item["open_label"] = f["open_label"]
                out.append(item)
            n["fields"] = out
            self.save()
            win.destroy()
            self.redraw()
            self.open_drawer(nid)

        bar = tk.Frame(p, bg=CARD)
        bar.pack(fill="x", padx=16, pady=16)
        self._solid(bar, "保存", save).pack(side="left")
        self._ghost(bar, "取消", win.destroy).pack(side="left", padx=8)

    # ---------------- 项目
    def switch_project(self, name):
        if not name or name == getattr(self, "proj_name", None):
            return
        self.save()
        self.open_project(name)
        self.sel_node = None
        self.sel_edge = None
        self.close_drawer()
        self.redraw()
        self.say("已切到项目：" + name)

    def ask_template(self):
        win = tk.Toplevel(self.root)
        win.title("从模板开始")
        win.geometry("300x320")
        win.configure(bg=CARD)
        tk.Label(win, text="选一个模板（可以之后再改）", bg=CARD, fg=SUB,
                 font=FONT_S).pack(anchor="w", padx=14, pady=(12, 6))
        lb = tk.Listbox(win, font=FONT, bd=0, highlightthickness=0,
                        selectbackground=ACCENT_BG)
        for name in TEMPLATE_DEFS:
            lb.insert("end", name)
        lb.selection_set(0)
        lb.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        res = {"v": None}

        def ok(_e=None):
            sel = lb.curselection()
            res["v"] = lb.get(sel[0]) if sel else "空白"
            win.destroy()

        lb.bind("<Double-Button-1>", ok)
        b = tk.Label(win, text="用这个", bg=ACCENT, fg="white", font=FONT,
                     padx=12, pady=6, cursor="hand2")
        b.pack(anchor="e", padx=14, pady=(0, 12))
        b.bind("<Button-1>", ok)
        win.transient(self.root)
        win.grab_set()
        self.root.wait_window(win)
        return res["v"]

    def export_html(self):
        p = filedialog.asksaveasfilename(
            title="导出只读网页", defaultextension=".html",
            initialfile=f"{self.proj_name}.html",
            filetypes=[("网页", "*.html")])
        if not p:
            return
        self.save()
        try:
            Path(p).write_text(self.build_html(), encoding="utf-8")
            self.toast("已导出：" + Path(p).name)
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def build_html(self):
        """只读网页：能缩放、能平移、能搜索，点卡片看这一步的材料。"""
        geo = []
        for e in self.data.get("edges", []):
            a, b = self.node(e.get("a")), self.node(e.get("b"))
            if a and b:
                geo.append({"a": e.get("a"), "b": e.get("b"),
                            "pts": self.edge_points(a, b),
                            "label": e.get("label") or ""})
        return html_export.render(self.proj_name, self.data,
                                  self.status_list(), self.proj, geo)

    def new_project(self):
        name = simpledialog.askstring("新建项目", "项目名字，比如「差旅报销」",
                                      parent=self.root)
        if not name:
            return
        name = "".join(c for c in name.strip() if c not in '\\/:*?"<>|')
        if not name:
            return
        d = PROJECTS / name
        if d.exists():
            messagebox.showwarning("重名", "已经有同名项目了")
            return
        (d / "files").mkdir(parents=True)
        (d / "snapshots").mkdir()
        flow = {"nodes": [{"id": "s1", "name": "第一步", "summary": "双击改名字",
                           "x": 80, "y": 40, "state": "todo", "fields": []}],
                "edges": [], "groups": []}
        tpl = self.ask_template()
        if tpl is None:
            return
        built = flow_from_template(TEMPLATE_DEFS.get(tpl, []))
        if built["nodes"]:
            flow = built
        (d / "flow.json").write_text(json.dumps(flow, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
        self.save()
        self.projects = self.scan_projects()
        self.cb_proj.configure(values=self.projects)
        self.open_project(name)
        self.var_proj.set(name)
        self.sel_node = None
        self.sel_edge = None
        self.close_drawer()
        self.redraw()
        self.say("新建了项目：" + name)

    def export_project(self):
        self.save()
        p = filedialog.asksaveasfilename(
            title="导出项目", defaultextension=".zip",
            initialfile=f"{self.proj_name}.zip",
            filetypes=[("压缩包", "*.zip")])
        if not p:
            return
        try:
            with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
                for f in self.proj.rglob("*"):
                    if f.is_file():
                        z.write(f, f.relative_to(self.proj))
            self.say("已导出：" + Path(p).name)
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def import_project(self):
        p = filedialog.askopenfilename(title="导入项目",
                                       filetypes=[("压缩包", "*.zip")])
        if not p:
            return
        base = Path(p).stem
        name, i = base, 2
        while (PROJECTS / name).exists():
            name = f"{base}-{i}"
            i += 1
        d = PROJECTS / name
        d.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(p) as z:
                z.extractall(d)
        except Exception as e:
            messagebox.showerror("导入失败", str(e))
            return
        self.save()
        self.projects = self.scan_projects()
        self.cb_proj.configure(values=self.projects)
        self.open_project(name)
        self.var_proj.set(name)
        self.sel_node = None
        self.sel_edge = None
        self.close_drawer()
        self.redraw()
        self.say("已导入：" + name)

    # ---------------- 右键 / 分组 / 对齐
    def on_right_press(self, e):
        self.rmenu = {"x": e.x, "y": e.y, "ox": self.ox, "oy": self.oy,
                      "moved": False}
        return "break"

    def on_right_motion(self, e):
        r = getattr(self, "rmenu", None)
        if not r:
            return
        if not r["moved"] and abs(e.x - r["x"]) + abs(e.y - r["y"]) > 5:
            r["moved"] = True
            self.cv.configure(cursor="fleur")
        if r["moved"]:
            self.ox = r["ox"] + (e.x - r["x"])
            self.oy = r["oy"] + (e.y - r["y"])
            self.redraw()

    def on_right_release(self, e):
        r = getattr(self, "rmenu", None)
        self.rmenu = None
        self.cv.configure(cursor="")
        if r and not r["moved"]:
            self.context_menu(e)

    def group_of(self, nid):
        for g in self.data.get("groups", []):
            if nid in g.get("members", []):
                return g
        return None

    def context_menu(self, e):
        n = len(self.sel_nodes) or (1 if self.sel_node else 0)
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="成组…", command=self.make_group,
                      state="normal" if n >= 2 else "disabled")
        if self.sel_node and self.group_of(self.sel_node):
            m.add_command(label="解组", command=self.ungroup)
        m.add_separator()
        if self.sel_node:
            sm = tk.Menu(m, tearoff=0)
            cur = self.node(self.sel_node).get("state", "todo")
            for s in self.status_list():
                sm.add_command(
                    label=("● " if s["key"] == cur else "　 ") + s["label"],
                    command=lambda k=s["key"], i=self.sel_node: self.set_state(i, k))
            sm.add_separator()
            sm.add_command(label="编辑状态…", command=self.edit_statuses)
            m.add_cascade(label="状态", menu=sm)
        st = "normal" if n >= 2 else "disabled"
        m.add_command(label="左对齐", command=lambda: self.align("left"), state=st)
        m.add_command(label="右对齐", command=lambda: self.align("right"), state=st)
        m.add_command(label="上对齐", command=lambda: self.align("top"), state=st)
        m.add_command(label="下对齐", command=lambda: self.align("bottom"), state=st)
        st3 = "normal" if n >= 3 else "disabled"
        m.add_command(label="横向等距", command=lambda: self.distribute("h"), state=st3)
        m.add_command(label="纵向等距", command=lambda: self.distribute("v"), state=st3)
        m.add_separator()
        m.add_command(label="删除", command=self.delete_sel,
                      state="normal" if n else "disabled")
        m.tk_popup(e.x_root, e.y_root)

    def make_group(self):
        ids = [n["id"] for n in self.data["nodes"] if n["id"] in self.sel_nodes]
        if len(ids) < 2:
            return
        name = simpledialog.askstring("成组", "组名：", initialvalue="新分组",
                                      parent=self.root)
        if name is None:
            return
        self.snapshot()
        colors = ["#EAF1FE", "#E8F5EC", "#FDF3E3", "#F3E8FF", "#E6F4F1"]
        groups = self.data.setdefault("groups", [])
        for g in groups:
            g["members"] = [m for m in g["members"] if m not in ids]
        self.data["groups"] = [g for g in groups if g["members"]]
        self.data["groups"].append({
            "id": uuid.uuid4().hex[:6], "name": name.strip() or "新分组",
            "color": colors[len(self.data["groups"]) % len(colors)],
            "members": ids})
        self.save()
        self.redraw()
        self.toast("已成组：" + (name.strip() or "新分组"))

    def ungroup(self):
        g = self.group_of(self.sel_node) if self.sel_node else None
        if not g:
            return
        self.snapshot()
        self.data["groups"].remove(g)
        self.save()
        self.redraw()
        self.toast("已解组")

    def _sel_list(self):
        return [n for n in self.data["nodes"] if n["id"] in self.sel_nodes]

    def align(self, mode):
        ns = self._sel_list()
        if len(ns) < 2:
            return
        self.snapshot()
        if mode == "left":
            v = min(n["x"] for n in ns)
            for n in ns:
                n["x"] = v
        elif mode == "right":
            v = max(n["x"] + CARD_W for n in ns)
            for n in ns:
                n["x"] = v - CARD_W
        elif mode == "top":
            v = min(n["y"] for n in ns)
            for n in ns:
                n["y"] = v
        elif mode == "bottom":
            v = max(n["y"] + CARD_H for n in ns)
            for n in ns:
                n["y"] = v - CARD_H
        self.save()
        self.redraw()

    def distribute(self, axis):
        ns = sorted(self._sel_list(), key=lambda n: n["x"] if axis == "h" else n["y"])
        if len(ns) < 3:
            return
        self.snapshot()
        if axis == "h":
            a, b = ns[0]["x"], ns[-1]["x"]
            step = (b - a) / (len(ns) - 1)
            for i, n in enumerate(ns):
                n["x"] = round(a + step * i)
        else:
            a, b = ns[0]["y"], ns[-1]["y"]
            step = (b - a) / (len(ns) - 1)
            for i, n in enumerate(ns):
                n["y"] = round(a + step * i)
        self.save()
        self.redraw()

    # ---------------- 增删
    def add_node(self):
        self.snapshot()
        n = len(self.data["nodes"]) + 1
        nid = f"n{n}"
        while self.node(nid):
            n += 1
            nid = f"n{n}"
        wx, wy = self.s2w(60, 60)
        self.data["nodes"].append({
            "id": nid, "name": "新步骤", "summary": "",
            "x": max(0, round(wx / 10) * 10), "y": max(0, round(wy / 10) * 10),
            "fields": []})
        self.sel_node = nid
        self.redraw()
        self.edit_node(nid)
        self.say("先把名称、注意、材料填上，保存后右边就能看到")

    def delete_sel(self):
        if self.sel_edge is None and not self.sel_nodes and self.sel_node is None:
            return
        self.snapshot()
        if self.sel_edge is not None:
            try:
                del self.data["edges"][self.sel_edge]
            except Exception:
                pass
            self.sel_edge = None
            self.redraw()
            self.toast("删掉一条连线")
            return
        ids = set(self.sel_nodes)
        if self.sel_node:
            ids.add(self.sel_node)
        self.data["nodes"] = [n for n in self.data["nodes"] if n["id"] not in ids]
        self.data["edges"] = [e for e in self.data["edges"]
                              if e["a"] not in ids and e["b"] not in ids]
        for g in self.data.get("groups", []):
            g["members"] = [m for m in g["members"] if m not in ids]
        self.data["groups"] = [g for g in self.data.get("groups", []) if g["members"]]
        self.sel_nodes = set()
        self.sel_node = None
        self.close_drawer()
        self.redraw()
        self.save()
        self.toast(f"删掉 {len(ids)} 张卡片")

    def auto_layout(self):
        nodes, edges = self.data["nodes"], self.data["edges"]
        ids = {n["id"] for n in nodes}
        incoming = {n["id"]: 0 for n in nodes}
        for e in edges:
            if e["b"] in incoming and e["a"] in ids:
                incoming[e["b"]] += 1
        roots = [n["id"] for n in nodes if incoming[n["id"]] == 0] or [nodes[0]["id"]]
        depth = {r: 0 for r in roots}
        queue = list(roots)
        while queue:
            cur = queue.pop(0)
            for e in edges:
                if e["a"] == cur and e["b"] in ids and e["b"] not in depth:
                    depth[e["b"]] = depth[cur] + 1
                    queue.append(e["b"])
        for n in nodes:
            depth.setdefault(n["id"], 0)
        rows = {}
        for n in nodes:
            rows.setdefault(depth[n["id"]], []).append(n)
        for d, items in rows.items():
            for i, n in enumerate(items):
                n["x"] = 60 + i * 220
                n["y"] = 18 + d * 100
        self.redraw()
        self.say("按连线的先后排好了")


def already_running() -> bool:
    global _MUTEX
    if sys.platform != "win32":
        return False
    import ctypes
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    _MUTEX = k32.CreateMutexW(None, True, "Local\\cardflow_demo")
    return ctypes.get_last_error() == 183


def main():
    root = TkinterDnD.Tk() if TkinterDnD else tk.Tk()
    if already_running():
        root.withdraw()
        messagebox.showinfo("卡片连线", "已经开着一个了，看看任务栏。")
        return 0
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

