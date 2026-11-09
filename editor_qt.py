"""editor_qt.py — 流程盒子（Qt 画布版）

跟 canvas_demo.py 读同一份数据：projects/<项目>/flow.json + files/ + snapshots/，
两个程序可以轮流打开同一个项目。

画布这块整个换成 Qt 的 Graphics View：缩放、框选、拖拽、抗锯齿、吸附都是框架自带，
连线几何仍然用 canvas_demo 那套算法，导出的网页跟这里看到的一模一样。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction, QColor, QFont, QFontMetrics, QKeySequence, QPainter, QPainterPath,
    QPen, QPixmap, QPolygonF, QTextOption, QUndoCommand, QUndoStack,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGraphicsItem,
    QGraphicsObject, QGraphicsPathItem, QGraphicsScene, QGraphicsView, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

import html_export

APP_DIR = (Path(sys.executable).resolve().parent
           if getattr(sys, "frozen", False) else Path(__file__).resolve().parent)
PROJECTS = APP_DIR / "projects"
DEFAULT_PROJECT = "专利年费"

CARD_W, CARD_H = 190, 88
GRID = 22
SNAP = 10

COL_BG = QColor("#F7F8FA")
COL_CARD = QColor("#FFFFFF")
COL_BORDER = QColor("#E3E5E8")
COL_BORDER_HOVER = QColor("#C3CBD6")
COL_TEXT = QColor("#1F2329")
COL_SUB = QColor("#6B7280")
COL_ACCENT = QColor("#2563EB")
COL_LINE = QColor("#3C4149")
COL_SHADOW = QColor(16, 24, 40)


# ---------------------------------------------------------------- 数据读写

def default_statuses() -> list:
    return [{"key": "todo", "label": "未开始", "color": "#C7CBD1"},
            {"key": "doing", "label": "进行中", "color": "#2563EB"},
            {"key": "done", "label": "已完成", "color": "#15803D"}]


def load_flow(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    for k in ("nodes", "edges", "groups"):
        if not isinstance(d.get(k), list):
            d[k] = []
    if not d.get("statuses"):
        d["statuses"] = default_statuses()
    return d


def save_flow(p: Path, d: dict) -> None:
    """先写临时文件再替换，断电也不会把 flow.json 弄坏。"""
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def keep_snapshot(proj: Path, flow: Path) -> None:
    snap = proj / "snapshots"
    snap.mkdir(exist_ok=True)
    try:
        shutil.copy2(flow, snap / f"{time.strftime('%Y%m%d-%H%M%S')}.json")
    except Exception:
        return
    olds = sorted(snap.glob("*.json"))
    for f in olds[:-5]:
        try:
            f.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------- 连线几何
# 跟 canvas_demo.py 里的 round_path / edge_points 是同一套，别分开改。

def round_path(pts: list, r: float = 13.0, steps: int = 8) -> list:
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


def bezier_link(sx, sy, tx, ty, steps=28):
    """贝塞尔连线：跟 canvas_demo.py / web/src/geometry.ts 同一套规则。"""
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


def edge_points(a: dict, b: dict) -> list:
    """走线：贝塞尔，水平切线。返回扁平坐标表，画布和导出都用它。"""
    x1, y1 = a["x"] + CARD_W, a["y"] + CARD_H / 2
    x2, y2 = b["x"], b["y"] + CARD_H / 2
    return bezier_link(x1, y1, x2, y2)


# ---------------------------------------------------------------- 卡片

def wrap_lines(text: str, fm: QFontMetrics, width: float, max_lines: int) -> list:
    """按字符折行（中文没空格），放不下的最后一行加省略号。"""
    text = text or ""
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            if len(lines) >= max_lines:
                break
            continue
        if cur and fm.horizontalAdvance(cur + ch) > width:
            lines.append(cur)
            cur = ch
            if len(lines) >= max_lines:
                break
        else:
            cur += ch
    if len(lines) < max_lines and cur:
        lines.append(cur)
    if lines and len(lines) >= max_lines:
        rest = text[len("".join(lines)):]
        if rest:
            lines[-1] = fm.elidedText(lines[-1] + rest,
                                      Qt.TextElideMode.ElideRight, int(width))
    return lines[:max_lines]


class CardItem(QGraphicsObject):
    PORT_R = 5.5

    def __init__(self, canvas, node: dict):
        super().__init__()
        self.canvas = canvas
        self.node = node
        self.hover = False
        self.setZValue(2)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                      | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
                      | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setPos(node.get("x", 0), node.get("y", 0))

    def boundingRect(self) -> QRectF:
        return QRectF(-10, -10, CARD_W + 34, CARD_H + 26)

    def port_pos(self) -> QPointF:
        return QPointF(CARD_W, CARD_H / 2)

    def paint(self, p: QPainter, opt, widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(0, 0, CARD_W, CARD_H)

        for dy, alpha, sp in ((6, 8, 2.0), (3, 12, 1.0), (1, 20, 0.0)):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(COL_SHADOW.red(), COL_SHADOW.green(),
                              COL_SHADOW.blue(), alpha))
            p.drawRoundedRect(r.adjusted(-sp, dy - 1, sp, dy + sp),
                              13 + sp, 13 + sp)

        if self.isSelected():
            p.setPen(QPen(QColor(37, 99, 235, 55), 6.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(-2, -2, 2, 2), 14, 14)
            border, bw = COL_ACCENT, 2.0
        else:
            border, bw = (COL_BORDER_HOVER if self.hover else COL_BORDER), 1.0
        p.setPen(QPen(border, bw))
        p.setBrush(COL_CARD)
        p.drawRoundedRect(r, 12, 12)

        inner_w = CARD_W - 30
        f_title = QFont(self.canvas.ui_font)
        f_title.setPixelSize(13)
        f_title.setWeight(QFont.Weight.DemiBold)
        fm_t = QFontMetrics(f_title)
        p.setFont(f_title)
        p.setPen(COL_TEXT)
        y = 10 + fm_t.ascent()
        for ln in wrap_lines(self.node.get("name") or "未命名", fm_t, inner_w, 2):
            p.drawText(QPointF(12, y), ln)
            y += fm_t.lineSpacing()

        summary = (self.node.get("summary") or "").strip()
        if summary:
            f_sub = QFont(self.canvas.ui_font)
            f_sub.setPixelSize(11)
            fm_s = QFontMetrics(f_sub)
            p.setFont(f_sub)
            p.setPen(COL_SUB)
            top = y + 1
            for ln in wrap_lines(summary, fm_s, inner_w, 2):
                p.drawText(QPointF(12, top + fm_s.ascent()), ln)
                top += fm_s.lineSpacing()

        p.setPen(QPen(QColor("#FFFFFF"), 1.5))
        p.setBrush(self.canvas.status_color(self.node.get("state")))
        p.drawEllipse(QPointF(CARD_W - 15, 15), 4.2, 4.2)

        if self.hover or self.canvas.linking_from is self:
            p.setPen(QPen(QColor("#FFFFFF"), 2))
            p.setBrush(COL_ACCENT)
            p.drawEllipse(self.port_pos(), self.PORT_R, self.PORT_R)

    def hoverEnterEvent(self, ev):
        self.hover = True
        self.update()
        super().hoverEnterEvent(ev)

    def hoverLeaveEvent(self, ev):
        self.hover = False
        self.update()
        super().hoverLeaveEvent(ev)

    def mousePressEvent(self, ev):
        d = ev.pos() - self.port_pos()
        if (d.x() ** 2 + d.y() ** 2) ** 0.5 <= self.PORT_R + 5:
            self.canvas.begin_link(self, ev.scenePos())
            ev.accept()
            return
        self.canvas.before_drag()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        self.canvas.after_drag()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.canvas.update_edges()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, ev):
        self.canvas.open_node.emit(self.node)
        ev.accept()


# ---------------------------------------------------------------- 连线

class EdgeItem(QGraphicsPathItem):
    PEN = QPen(COL_LINE, 2.2, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    PEN_HOT = QPen(COL_ACCENT, 3.0, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    def __init__(self, canvas, edge: dict):
        super().__init__()
        self.canvas = canvas
        self.edge = edge
        self.label_item = None
        self.setZValue(1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setBrush(Qt.BrushStyle.NoBrush)
        self.setPen(QPen(self.PEN))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def rebuild(self, a: dict, b: dict):
        pts = edge_points(a, b)
        path = QPainterPath()
        path.moveTo(pts[0], pts[1])
        for i in range(2, len(pts), 2):
            path.lineTo(pts[i], pts[i + 1])
        self.setPath(path)

        label = str(self.edge.get("label") or "").strip()
        if not label:
            if self.label_item is not None:
                self.label_item.setVisible(False)
            return
        pt = path.pointAtPercent(0.5)
        if self.label_item is None:
            from PySide6.QtWidgets import QGraphicsSimpleTextItem
            self.label_item = QGraphicsSimpleTextItem(self)
            f = QFont(self.canvas.ui_font)
            f.setPixelSize(11)
            self.label_item.setFont(f)
            self.label_item.setBrush(QColor("#5B6373"))
            self.label_item.setZValue(3)
        self.label_item.setText(label)
        self.label_item.setVisible(True)
        br = self.label_item.boundingRect()
        self.label_item.setPos(pt.x() - br.width() / 2, pt.y() - br.height() - 4)

    def paint(self, p: QPainter, opt, widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        super().paint(p, opt, widget)
        # 箭头
        path = self.path()
        if path.isEmpty():
            return
        pct = 1.0
        tip = path.pointAtPercent(pct)
        prev = path.pointAtPercent(max(0.0, pct - 0.004))
        dx, dy = tip.x() - prev.x(), tip.y() - prev.y()
        ln = (dx * dx + dy * dy) ** 0.5 or 1.0
        ux, uy = dx / ln, dy / ln
        size = 9.0
        left = QPointF(tip.x() - ux * size - uy * 4.2,
                       tip.y() - uy * size + ux * 4.2)
        right = QPointF(tip.x() - ux * size + uy * 4.2,
                        tip.y() - uy * size - ux * 4.2)
        head = QPolygonF([tip, left, right])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(COL_ACCENT if self.isSelected() else COL_LINE)
        p.drawPolygon(head)

    def hoverEnterEvent(self, ev):
        self.setPen(QPen(self.PEN_HOT))
        super().hoverEnterEvent(ev)

    def hoverLeaveEvent(self, ev):
        self.setPen(QPen(self.PEN))
        super().hoverLeaveEvent(ev)

    def contextMenuEvent(self, ev):
        self.canvas.edge_menu(self, ev.screenPos())
        ev.accept()

    def mouseDoubleClickEvent(self, ev):
        self.canvas.edit_edge_label(self)
        ev.accept()


# ---------------------------------------------------------------- 画布

class GroupItem(QGraphicsItem):
    def __init__(self, rect: QRectF, name: str, color: QColor):
        super().__init__()
        self.rect = rect
        self.name = name
        self.color = color
        self.setZValue(-1)

    def boundingRect(self) -> QRectF:
        return self.rect.adjusted(-4, -4, 4, 4)

    def paint(self, p: QPainter, opt, widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor("#C9D6EA"), 1))
        p.setBrush(self.color)
        p.drawRoundedRect(self.rect, 14, 14)
        if self.name:
            f = QFont()
            f.setPixelSize(11)
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            p.setPen(QColor("#5B6B82"))
            p.drawText(self.rect.adjusted(10, 5, -8, 0),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                       self.name)


class Canvas(QGraphicsView):
    open_node = Signal(object)
    add_at = Signal(QPointF)
    zoom_changed = Signal(int)

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.ui_font = QFont("Microsoft YaHei UI", 9)
        self.cards = {}          # id -> CardItem
        self.edges = []          # EdgeItem 列表
        self.linking_from = None
        self.temp_edge = None
        self._drag_before = None
        self._pan = None

        sc = QGraphicsScene(self)
        sc.setSceneRect(-5000, -5000, 10000, 10000)
        self.setScene(sc)
        self.setRenderHints(QPainter.RenderHint.Antialiasing
                            | QPainter.RenderHint.TextAntialiasing
                            | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setBackgroundBrush(COL_BG)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def drawBackground(self, p: QPainter, rect: QRectF):
        p.fillRect(rect, COL_BG)
        if self.transform().m11() < 0.4:
            return
        step = GRID
        p.setPen(QPen(QColor("#D9DEE5"), 1.0))
        x = int(rect.left()) - int(rect.left()) % step
        while x < rect.right():
            y = int(rect.top()) - int(rect.top()) % step
            while y < rect.bottom():
                p.drawPoint(QPointF(x, y))
                y += step
            x += step

    # --- 建图
    def rebuild(self):
        self.scene().clear()
        self.cards, self.edges = {}, []
        data = self.app.data

        for g in data.get("groups") or []:
            mem = [n for n in data["nodes"]
                   if n.get("id") in (g.get("members") or [])]
            if not mem:
                continue
            x1 = min(n["x"] for n in mem) - 16
            y1 = min(n["y"] for n in mem) - 34
            x2 = max(n["x"] + CARD_W for n in mem) + 16
            y2 = max(n["y"] + CARD_H for n in mem) + 16
            self.scene().addItem(GroupItem(QRectF(x1, y1, x2 - x1, y2 - y1),
                                           g.get("name") or "组",
                                           QColor(g.get("color") or "#EAF1FE")))

        for e in data["edges"]:
            it = EdgeItem(self, e)
            self.scene().addItem(it)
            self.edges.append(it)

        for n in data["nodes"]:
            it = CardItem(self, n)
            self.scene().addItem(it)
            self.cards[n["id"]] = it

        self.update_edges()

    def update_edges(self):
        for it in self.edges:
            a = self.app.node(it.edge.get("a"))
            b = self.app.node(it.edge.get("b"))
            if not a or not b:
                it.setVisible(False)
                continue
            it.setVisible(True)
            it.rebuild(a, b)

    def status_color(self, key) -> QColor:
        for s in self.app.status_list():
            if s.get("key") == key:
                return QColor(s.get("color") or "#C7CBD1")
        return QColor("#C7CBD1")

    def poly(self, pts: list) -> QPainterPath:
        path = QPainterPath()
        if len(pts) < 4:
            return path
        path.moveTo(pts[0], pts[1])
        for i in range(2, len(pts), 2):
            path.lineTo(pts[i], pts[i + 1])
        return path

    # --- 视图
    def zoom_by(self, factor: float):
        now = self.transform().m11()
        new = max(0.2, min(2.8, now * factor))
        if abs(new - now) < 1e-4:
            return
        self.scale(new / now, new / now)
        self.zoom_changed.emit(round(new * 100))

    def reset_zoom(self):
        now = self.transform().m11()
        if now:
            self.scale(1 / now, 1 / now)
        self.zoom_changed.emit(100)

    def fit_all(self):
        nodes = self.app.data["nodes"]
        if not nodes:
            self.reset_zoom()
            return
        x1 = min(n["x"] for n in nodes) - 60
        y1 = min(n["y"] for n in nodes) - 60
        x2 = max(n["x"] + CARD_W for n in nodes) + 60
        y2 = max(n["y"] + CARD_H for n in nodes) + 60
        vw = max(200, self.viewport().width() - 80)
        vh = max(200, self.viewport().height() - 80)
        z = min(vw / (x2 - x1), vh / (y2 - y1), 1.1)
        z = max(0.75, z)          # 缩得太小就没法读了，宁可让人自己拖
        self.reset_zoom()
        self.scale(z, z)
        self.centerOn((x1 + x2) / 2, (y1 + y2) / 2)
        self.zoom_changed.emit(round(z * 100))

    def wheelEvent(self, ev):
        dy = ev.angleDelta().y()
        dx = ev.angleDelta().x()
        mods = ev.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            if dy:
                self.zoom_by(1.0018 ** dy)
            ev.accept()
            return
        if mods & Qt.KeyboardModifier.ShiftModifier:
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - dy)
        else:
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - dy)
            if dx:
                self.horizontalScrollBar().setValue(
                    self.horizontalScrollBar().value() - dx)
        ev.accept()

    # --- 鼠标
    def card_at(self, scene_pos: QPointF):
        for it in self.scene().items(scene_pos):
            if isinstance(it, CardItem):
                return it
        return None

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.MiddleButton:
            self._pan = ev.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._pan is not None:
            d = ev.position() - self._pan
            self._pan = ev.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(d.x()))
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(d.y()))
            ev.accept()
            return
        if self.linking_from is not None and self.temp_edge is not None:
            p = self.mapToScene(ev.position().toPoint())
            a = self.linking_from.node
            self.temp_edge.setPath(self.poly(
                edge_points({"x": a["x"], "y": a["y"]},
                            {"x": p.x(), "y": p.y() - CARD_H / 2})))
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._pan is not None and ev.button() == Qt.MouseButton.MiddleButton:
            self._pan = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            ev.accept()
            return
        if self.linking_from is not None:
            self.finish_link(self.card_at(
                self.mapToScene(ev.position().toPoint())))
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        p = self.mapToScene(ev.position().toPoint())
        card = self.card_at(p)
        if card is not None:
            self.open_node.emit(card.node)
        else:
            self.add_at.emit(p)
        ev.accept()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
            ev.accept()
            return
        if ev.key() == Qt.Key.Key_Escape and self.linking_from is not None:
            self.cancel_link()
            ev.accept()
            return
        super().keyPressEvent(ev)

    # --- 连线
    def begin_link(self, card, scene_pos: QPointF):
        self.linking_from = card
        it = QGraphicsPathItem()
        it.setPen(QPen(COL_ACCENT, 2.0, Qt.PenStyle.DashLine))
        it.setZValue(6)
        self.scene().addItem(it)
        self.temp_edge = it
        card.update()

    def cancel_link(self):
        if self.temp_edge is not None:
            self.scene().removeItem(self.temp_edge)
            self.temp_edge = None
        if self.linking_from is not None:
            self.linking_from.update()
        self.linking_from = None

    def finish_link(self, target):
        src = self.linking_from
        self.cancel_link()
        if src is None or target is None or target is src:
            return
        a, b = src.node.get("id"), target.node.get("id")
        for e in self.app.data["edges"]:
            if e.get("a") == a and e.get("b") == b:
                self.app.say("这两张卡片已经连过了")
                return
        before = self.app.json_state()
        self.app.data["edges"].append({"a": a, "b": b})
        self.app.commit(before, "连线")
        self.rebuild()

    # --- 拖动
    def before_drag(self):
        self._drag_before = self.app.json_state()

    def after_drag(self):
        before = self._drag_before
        self._drag_before = None
        if before is None:
            return
        moved = False
        for nid, it in self.cards.items():
            n = self.app.node(nid)
            if not n:
                continue
            x, y = it.pos().x(), it.pos().y()
            if it.isSelected():
                sx, sy = round(x / SNAP) * SNAP, round(y / SNAP) * SNAP
                if abs(sx - x) <= 2 and abs(sy - y) <= 2:
                    it.setPos(sx, sy)
                    x, y = sx, sy
            if n["x"] != x or n["y"] != y:
                n["x"], n["y"] = x, y
                moved = True
        if moved:
            self.app.commit(before, "移动卡片")
            self.update_edges()

    # --- 删除 / 菜单
    def delete_selected(self):
        sel = list(self.scene().selectedItems())
        if not sel:
            return
        before = self.app.json_state()
        ids = {it.node["id"] for it in sel if isinstance(it, CardItem)}
        drop_edges = [it.edge for it in sel if isinstance(it, EdgeItem)]
        if ids:
            self.app.data["nodes"] = [n for n in self.app.data["nodes"]
                                      if n["id"] not in ids]
            self.app.data["edges"] = [
                e for e in self.app.data["edges"]
                if e.get("a") not in ids and e.get("b") not in ids]
            for g in self.app.data.get("groups") or []:
                g["members"] = [m for m in (g.get("members") or [])
                                if m not in ids]
        if drop_edges:
            self.app.data["edges"] = [e for e in self.app.data["edges"]
                                      if e not in drop_edges]
        self.app.commit(before, "删除")
        self.app.close_drawer()
        self.rebuild()

    def node_menu(self, card, screen_pos):
        m = QMenu(self)
        m.addAction("编辑这张卡片", lambda: self.open_node.emit(card.node))
        sub = m.addMenu("卡片状态")
        for s in self.app.status_list():
            act = sub.addAction(("● " if s["key"] == card.node.get("state") else "")
                                + str(s.get("label") or s["key"]))
            act.triggered.connect(
                lambda _=False, k=s["key"], n=card.node: self.app.set_state(n, k))
        m.addSeparator()
        m.addAction("删除这张卡片", lambda: self.delete_card(card))
        m.exec(screen_pos)

    def delete_card(self, card):
        before = self.app.json_state()
        nid = card.node.get("id")
        self.app.data["nodes"] = [n for n in self.app.data["nodes"]
                                  if n["id"] != nid]
        self.app.data["edges"] = [e for e in self.app.data["edges"]
                                  if e.get("a") != nid and e.get("b") != nid]
        self.app.commit(before, "删除卡片")
        self.app.close_drawer()
        self.rebuild()

    def edge_menu(self, item, screen_pos):
        m = QMenu(self)
        m.addAction("改标签…", lambda: self.edit_edge_label(item))
        m.addAction("删除这条线", lambda: self.delete_edge(item))
        m.exec(screen_pos)

    def edit_edge_label(self, item):
        from PySide6.QtWidgets import QInputDialog
        before = self.app.json_state()
        text, ok = QInputDialog.getText(
            self, "连线标签", "写在这条线上的字（比如「驳回」），留空就是不写：",
            text=item.edge.get("label") or "")
        if not ok:
            return
        item.edge["label"] = text.strip()
        self.app.commit(before, "改连线标签")
        a = self.app.node(item.edge.get("a"))
        b = self.app.node(item.edge.get("b"))
        if a and b:
            item.rebuild(a, b)

    def delete_edge(self, item):
        before = self.app.json_state()
        self.app.data["edges"] = [e for e in self.app.data["edges"]
                                  if e is not item.edge]
        self.app.commit(before, "删除连线")
        self.rebuild()

    def contextMenuEvent(self, ev):
        p = self.mapToScene(ev.pos())
        card = self.card_at(p)
        if card is not None:
            self.node_menu(card, ev.globalPos())
            return
        m = QMenu(self)
        m.addAction("在这儿新建卡片", lambda: self.add_at.emit(p))
        m.addSeparator()
        m.addAction("适应窗口", self.fit_all)
        m.addAction("100%", self.reset_zoom)
        m.exec(ev.globalPos())


# ---------------------------------------------------------------- 右侧抽屉

FIELD_TYPES = [("文本", "text"), ("多行文本", "longtext"), ("单选", "select"),
               ("多选", "multiselect"), ("清单", "list"), ("人员", "user"),
               ("日期", "date"), ("附件", "attachment"), ("图片", "image"),
               ("数字", "number"), ("复选框", "checkbox"), ("超链接", "link")]


class Drawer(QScrollArea):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.node = None
        self._timer = None
        self._before = None
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedWidth(372)
        self.setStyleSheet("QScrollArea{background:#FFFFFF;border-left:1px solid #E6E8EB}")
        self.host = QWidget()
        self.host.setStyleSheet("background:#FFFFFF")
        self.lay = QVBoxLayout(self.host)
        self.lay.setContentsMargins(16, 14, 16, 20)
        self.lay.setSpacing(8)
        self.setWidget(self.host)
        self.hide()

    # --- 提交
    def schedule_commit(self):
        if self._before is None:
            self._before = self.app.json_state()
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._flush)
        self._timer.start(600)

    def _flush(self):
        before, self._before = self._before, None
        if before:
            self.app.commit(before, "改卡片")

    def _clear(self):
        while self.lay.count():
            item = self.lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def open(self, node: dict):
        self.node = node
        self._clear()

        head = QHBoxLayout()
        title = QLabel("卡片")
        title.setStyleSheet("color:#8A94A6;font-size:11px")
        head.addWidget(title)
        head.addStretch(1)
        close = QToolButton()
        close.setText("✕")
        close.clicked.connect(self.hide_panel)
        head.addWidget(close)
        self.lay.addLayout(head)

        name = QLineEdit(node.get("name") or "")
        name.setPlaceholderText("这一步叫什么")
        name.setStyleSheet("QLineEdit{font-size:15px;font-weight:600;"
                           "border:1px solid transparent;border-radius:6px;padding:4px 6px}"
                           "QLineEdit:hover{border-color:#E6E8EB}"
                           "QLineEdit:focus{border-color:#C7D2FE;background:#FFFFFF}")
        name.editingFinished.connect(
            lambda: self._set(node, "name", name.text().strip() or "未命名"))
        self.lay.addWidget(name)

        summary = QPlainTextEdit(node.get("summary") or "")
        summary.setFixedHeight(56)
        summary.setPlaceholderText("一句话说明这一步（会显示在卡片上）")
        summary.textChanged.connect(
            lambda: (node.__setitem__("summary", summary.toPlainText()),
                     self.schedule_commit(), self.app.touch_card(node)))
        self.lay.addWidget(summary)

        row = QHBoxLayout()
        row.addWidget(QLabel("状态"))
        combo = QComboBox()
        for s in self.app.status_list():
            combo.addItem(str(s.get("label") or s["key"]), s["key"])
        cur = node.get("state")
        idx = combo.findData(cur)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.currentIndexChanged.connect(
            lambda _i: self.app.set_state(node, combo.currentData()))
        row.addWidget(combo, 1)
        self.lay.addLayout(row)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#EEF0F2")
        self.lay.addWidget(line)

        fields = node.setdefault("fields", [])
        for f in fields:
            self.lay.addWidget(FieldRow(self, node, f))

        add = QPushButton("＋ 添加字段")
        add.setStyleSheet("QPushButton{border:1px dashed #D8DDE3;border-radius:8px;"
                          "padding:7px;color:#6B7280;background:#FFFFFF}"
                          "QPushButton:hover{border-color:#93B4F7;color:#2563EB}")
        menu = QMenu(add)
        for label, kind in FIELD_TYPES:
            menu.addAction(label, lambda k=kind: self._add_field(node, k))
        add.setMenu(menu)
        self.lay.addWidget(add)
        self.lay.addStretch(1)

        self.show()
        name.setFocus()
        name.selectAll()

    def hide_panel(self):
        self.hide()
        self.node = None

    def _set(self, node, key, value):
        if node.get(key) == value:
            return
        before = self.app.json_state()
        node[key] = value
        self.app.commit(before, "改卡片")
        self.app.touch_card(node)

    def _add_field(self, node, kind):
        before = self.app.json_state()
        label = dict((k, v) for v, k in FIELD_TYPES).get(kind, kind)
        value = "" if kind != "attachment" and kind != "image" and kind != "list" \
            and kind != "multiselect" else []
        if kind == "checkbox":
            value = False
        if kind == "link":
            value = {"url": "", "text": ""}
        node.setdefault("fields", []).append(
            {"type": kind, "label": label, "value": value})
        self.app.commit(before, "加字段")
        self.open(node)


class FieldRow(QWidget):
    def __init__(self, drawer, node, field):
        super().__init__()
        self.drawer = drawer
        self.node = node
        self.field = field
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 7, 0, 0)
        lay.setSpacing(3)

        head = QHBoxLayout()
        lab = QLabel(field.get("label") or "未命名字段")
        lab.setStyleSheet("color:#8A94A6;font-size:11px")
        head.addWidget(lab)
        head.addStretch(1)
        more = QToolButton()
        more.setText("⋯")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(more)
        menu.addAction("改字段名", self.rename)
        menu.addAction("删除这个字段", self.remove)
        more.setMenu(menu)
        head.addWidget(more)
        lay.addLayout(head)

        t = field.get("type") or "text"
        val = field.get("value")

        if t == "longtext":
            ed = QPlainTextEdit(str(val or ""))
            ed.setFixedHeight(74)
            ed.textChanged.connect(lambda: self._put(ed.toPlainText()))
            lay.addWidget(ed)
        elif t in ("multiselect", "list"):
            items = val if isinstance(val, list) else []
            ed = QPlainTextEdit("\n".join(str(x) for x in items))
            ed.setPlaceholderText("一行一条")
            ed.setFixedHeight(74)
            ed.textChanged.connect(
                lambda: self._put([s.strip() for s in
                                   ed.toPlainText().split("\n") if s.strip()]))
            lay.addWidget(ed)
        elif t == "checkbox":
            cb = QCheckBox("是")
            cb.setChecked(bool(val))
            cb.toggled.connect(lambda on: self._put(on))
            lay.addWidget(cb)
        elif t == "link":
            v0 = val if isinstance(val, dict) else {"url": str(val or ""),
                                                    "text": ""}
            url = QLineEdit(v0.get("url") or "")
            url.setPlaceholderText("网址，比如 oa.example.com")
            txt = QLineEdit(v0.get("text") or "")
            txt.setPlaceholderText("按钮上写的字，比如「打开 OA」")

            def put_link():
                self._put({"url": url.text().strip(),
                           "text": txt.text().strip()})
            url.textChanged.connect(put_link)
            txt.textChanged.connect(put_link)
            lay.addWidget(url)
            lay.addWidget(txt)
        elif t in ("attachment", "image"):
            materials_ui(lay, drawer, node, field, t == "image")
        else:
            ed = QLineEdit(str(val or ""))
            ed.setPlaceholderText({"number": "填数字", "date": "2026-12-31",
                                   "user": "谁负责"}.get(t, "填内容"))
            ed.textChanged.connect(lambda: self._put(ed.text()))
            lay.addWidget(ed)

    def _put(self, value):
        self.field["value"] = value
        self.drawer.schedule_commit()
        self.drawer.app.touch_card(self.node)

    def rename(self):
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "字段名", "这个字段叫什么：",
                                        text=self.field.get("label") or "")
        if not ok:
            return
        before = self.drawer.app.json_state()
        self.field["label"] = text.strip()
        self.drawer.app.commit(before, "改字段名")
        self.drawer.open(self.node)

    def remove(self):
        before = self.drawer.app.json_state()
        fields = self.node.get("fields") or []
        if self.field in fields:
            fields.remove(self.field)
        self.drawer.app.commit(before, "删字段")
        self.drawer.open(self.node)


# ---------------------------------------------------------------- 附件 / 截图

def open_path(p: Path):
    try:
        os.startfile(p)          # noqa: S606
    except Exception as e:
        QMessageBox.warning(None, "打不开", str(e))


def toggle_material(drawer, field, idx):
    items = field.get("value") or []
    if 0 <= idx < len(items) and isinstance(items[idx], dict):
        before = drawer.app.json_state()
        items[idx]["done"] = not items[idx].get("done")
        drawer.app.commit(before, "勾材料")
        drawer.open(drawer.node)


def pick_file(drawer, node, field, images: bool):
    app = drawer.app
    path, _ = QFileDialog.getOpenFileName(
        None, "选图片" if images else "选文件", "",
        "图片 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)"
        if images else "所有文件 (*.*)")
    if not path:
        return
    src = Path(path)
    nid = node.get("id") or "n"
    d = app.proj / "files" / nid
    d.mkdir(parents=True, exist_ok=True)
    dst, i = d / src.name, 1
    while dst.exists():
        dst = d / f"{src.stem}_{i}{src.suffix}"
        i += 1
    try:
        shutil.copy2(src, dst)
    except Exception as e:
        QMessageBox.warning(None, "复制失败", str(e))
        return
    rel = f"files/{nid}/{dst.name}"
    before = app.json_state()
    items = field.get("value")
    if not isinstance(items, list):
        items = []
        field["value"] = items
    if images:
        items.append(rel)
    else:
        items.append({"name": src.stem[:40], "file": rel, "done": True})
    app.commit(before, "加材料")
    drawer.open(node)


def materials_ui(lay, drawer, node, field, images: bool):
    app = drawer.app
    items = field.get("value")
    if not isinstance(items, list):
        items = []
        field["value"] = items

    if images:
        strip = QHBoxLayout()
        strip.setSpacing(6)
        for rel in items:
            fp = app.proj / str(rel)
            if not fp.exists():
                continue
            pm = QPixmap(str(fp))
            if pm.isNull():
                continue
            lb = QLabel()
            lb.setPixmap(pm.scaled(78, 52, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation))
            lb.setStyleSheet("border:1px solid #E6E8EB;border-radius:4px;padding:1px")
            strip.addWidget(lb)
        strip.addStretch(1)
        lay.addLayout(strip)
        btn = QPushButton("＋ 选图片（直接拖到卡片上也行）")
        btn.clicked.connect(lambda: pick_file(drawer, node, field, True))
        lay.addWidget(btn)
        return

    for idx, m in enumerate(list(items)):
        if not isinstance(m, dict):
            continue
        row = QHBoxLayout()
        row.setSpacing(6)
        mark = QToolButton()
        mark.setText("✓" if m.get("done") else "○")
        mark.setStyleSheet("QToolButton{border:0;color:%s}"
                           % ("#15803D" if m.get("done") else "#9AA1AA"))
        mark.clicked.connect(
            lambda _=False, i=idx: toggle_material(drawer, field, i))
        row.addWidget(mark)
        nm = QLabel(m.get("name") or "（未命名材料）")
        row.addWidget(nm, 1)
        rel = str(m.get("file") or "")
        if rel and (app.proj / rel).exists():
            b = QToolButton()
            b.setText("打开")
            b.clicked.connect(lambda _=False, r=rel: open_path(app.proj / r))
            row.addWidget(b)
        lay.addLayout(row)

    add = QPushButton("＋ 选文件")
    add.clicked.connect(lambda: pick_file(drawer, node, field, False))
    lay.addWidget(add)


# ---------------------------------------------------------------- 主窗口

class StateCmd(QUndoCommand):
    """整份快照式撤销：flow.json 只有几 KB，够用，也不容易出错。"""

    def __init__(self, app, before: str, after: str, text: str):
        super().__init__(text)
        self.app = app
        self.before = before
        self.after = after
        self.skip = True

    def redo(self):
        if self.skip:          # push 时 Qt 会自动调一次 redo，跳过它
            self.skip = False
            return
        self.app.apply_state(self.after)

    def undo(self):
        self.app.apply_state(self.before)


QSS = """
QMainWindow { background:#F7F8FA; }
QToolBar { background:#FFFFFF; border:0; border-bottom:1px solid #E6E8EB;
           padding:6px 10px; spacing:5px; }
QToolBar QLabel { color:#8A94A6; padding:0 2px; }
QToolButton { padding:5px 9px; border-radius:7px; color:#3F4652; }
QToolButton:hover { background:#F0F2F5; }
QComboBox { background:#F2F3F5; border:1px solid transparent; border-radius:7px;
            padding:4px 8px; min-width:120px; }
QComboBox:hover { background:#E9ECF0; }
QComboBox QAbstractItemView { border:1px solid #E6E8EB; background:#FFFFFF;
            selection-background-color:#EEF2FF; selection-color:#1F2329; }
QStatusBar { background:#FFFFFF; border-top:1px solid #E6E8EB; color:#8A94A6; }
QLineEdit, QPlainTextEdit { background:#F7F8FA; border:1px solid #E6E8EB;
            border-radius:7px; padding:5px 7px; selection-background-color:#C7D2FE; }
QLineEdit:focus, QPlainTextEdit:focus { border-color:#C7D2FE; background:#FFFFFF; }
QPushButton { border:1px solid #E6E8EB; border-radius:7px; padding:6px 10px;
            background:#FFFFFF; color:#3F4652; }
QPushButton:hover { border-color:#C7D2FE; color:#2563EB; }
QMenu { background:#FFFFFF; border:1px solid #E6E8EB; padding:4px; }
QMenu::item { padding:5px 24px 5px 12px; border-radius:5px; }
QMenu::item:selected { background:#EEF2FF; color:#1F2329; }
QScrollBar:vertical { width:9px; background:transparent; }
QScrollBar::handle:vertical { background:#D8DDE3; border-radius:4px; min-height:30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
"""


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("流程盒子")
        self.resize(1320, 840)
        self.data = {"nodes": [], "edges": [], "groups": [],
                     "statuses": default_statuses()}
        self.proj_name = DEFAULT_PROJECT
        self.proj = PROJECTS / DEFAULT_PROJECT
        self._last_snap = 0.0
        self.undo_stack = QUndoStack(self)
        self.canvas = Canvas(self)
        self.drawer = Drawer(self)
        self._build()

        self.canvas.open_node.connect(self.drawer.open)
        self.canvas.add_at.connect(self.on_add_at)
        self.canvas.zoom_changed.connect(
            lambda p: self.lbl_zoom.setText(f"{p}%"))
        self.open_project(self._first_project())

    def _first_project(self) -> str:
        names = []
        if PROJECTS.exists():
            names = sorted(p.name for p in PROJECTS.iterdir()
                           if p.is_dir() and (p / "flow.json").exists())
        if DEFAULT_PROJECT in names:
            return DEFAULT_PROJECT
        return names[0] if names else DEFAULT_PROJECT

    def _build(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addWidget(QLabel("项目"))
        self.cb_proj = QComboBox()
        self.cb_proj.currentTextChanged.connect(self.on_proj_changed)
        tb.addWidget(self.cb_proj)
        tb.addSeparator()

        tb.addAction("新建卡片", self.on_add_at_center).setShortcut("Ctrl+N")
        act_u = self.undo_stack.createUndoAction(self, "撤销")
        act_u.setShortcut(QKeySequence.StandardKey.Undo)
        tb.addAction(act_u)
        act_r = self.undo_stack.createRedoAction(self, "重做")
        act_r.setShortcut(QKeySequence.StandardKey.Redo)
        tb.addAction(act_r)
        tb.addSeparator()
        tb.addAction("适应", self.canvas.fit_all).setShortcut("Ctrl+0")
        tb.addAction("100%", self.canvas.reset_zoom).setShortcut("Ctrl+1")
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setMinimumWidth(46)
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb.addWidget(self.lbl_zoom)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        tb.addAction("导出网页", self.export_html)
        tb.addAction("打开文件夹", lambda: open_path(self.proj))
        save = QAction("保存", self)
        save.setShortcut(QKeySequence.StandardKey.Save)
        save.triggered.connect(self.save)
        tb.addAction(save)

        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.canvas, 1)
        lay.addWidget(self.drawer)
        self.setCentralWidget(central)

        self.statusBar().showMessage(
            "双击空白新建卡片 · 从卡片右边的小圆点拖到另一张卡片连线 · "
            "中键拖动平移 · Ctrl+滚轮缩放 · Delete 删除")

    def refresh_projects(self):
        names = []
        if PROJECTS.exists():
            names = sorted(p.name for p in PROJECTS.iterdir() if p.is_dir())
        self.cb_proj.blockSignals(True)
        self.cb_proj.clear()
        self.cb_proj.addItems(names)
        i = self.cb_proj.findText(self.proj_name)
        if i >= 0:
            self.cb_proj.setCurrentIndex(i)
        self.cb_proj.blockSignals(False)

    def on_proj_changed(self, name: str):
        if name and name != self.proj_name:
            self.open_project(name)

    # --- 项目
    def open_project(self, name: str):
        self.proj_name = name
        self.proj = PROJECTS / name
        self.proj.mkdir(parents=True, exist_ok=True)
        (self.proj / "files").mkdir(exist_ok=True)
        (self.proj / "snapshots").mkdir(exist_ok=True)
        p = self.proj / "flow.json"
        if p.exists():
            self.data = load_flow(p)
        else:
            self.data = {"nodes": [], "edges": [], "groups": [],
                         "statuses": default_statuses()}
            save_flow(p, self.data)
        self.undo_stack.clear()
        self.drawer.hide_panel()
        self.canvas.rebuild()
        self.canvas.fit_all()
        self.refresh_projects()
        self.setWindowTitle(f"流程盒子 — {name}")

    def save(self):
        p = self.proj / "flow.json"
        try:
            if p.exists() and time.time() - self._last_snap > 90:
                keep_snapshot(self.proj, p)
                self._last_snap = time.time()
            save_flow(p, self.data)
        except Exception as e:
            self.say("保存失败：" + str(e))

    # --- 数据小工具
    def status_list(self) -> list:
        st = self.data.get("statuses")
        if not st:
            st = default_statuses()
            self.data["statuses"] = st
        return st

    def node(self, nid):
        for n in self.data["nodes"]:
            if n.get("id") == nid:
                return n
        return None

    def json_state(self) -> str:
        return json.dumps(self.data, ensure_ascii=False, sort_keys=True)

    def commit(self, before: str, text: str):
        after = self.json_state()
        if after == before:
            return
        self.undo_stack.push(StateCmd(self, before, after, text))
        self.save()

    def apply_state(self, state: str):
        self.data = json.loads(state)
        self.canvas.rebuild()
        if self.drawer.node is not None:
            n = self.node(self.drawer.node.get("id"))
            if n is not None:
                self.drawer.open(n)
            else:
                self.drawer.hide_panel()

    def touch_card(self, node: dict):
        it = self.canvas.cards.get(node.get("id"))
        if it is not None:
            it.update()

    def set_state(self, node: dict, key: str):
        if node.get("state") == key:
            return
        before = self.json_state()
        node["state"] = key
        self.commit(before, "改状态")
        self.touch_card(node)

    def close_drawer(self):
        self.drawer.hide_panel()

    def say(self, msg: str):
        self.statusBar().showMessage(msg, 4000)

    # --- 新建卡片
    def on_add_at_center(self):
        c = self.canvas.viewport().rect().center()
        self.on_add_at(self.canvas.mapToScene(c))

    def on_add_at(self, pos: QPointF):
        before = self.json_state()
        nid = "n" + uuid.uuid4().hex[:8]
        x = max(0, round((pos.x() - CARD_W / 2) / SNAP) * SNAP)
        y = max(0, round((pos.y() - CARD_H / 2) / SNAP) * SNAP)
        node = {"id": nid, "name": "新卡片", "summary": "", "x": x, "y": y,
                "state": self.status_list()[0]["key"], "fields": []}
        self.data["nodes"].append(node)
        self.commit(before, "新建卡片")
        self.canvas.rebuild()
        self.drawer.open(node)
        self.say("新加了一张卡片，在右边改名字")

    # --- 导出
    def build_html(self) -> str:
        geo = []
        for e in self.data["edges"]:
            a, b = self.node(e.get("a")), self.node(e.get("b"))
            if a and b:
                geo.append({"a": e["a"], "b": e["b"],
                            "pts": edge_points(a, b),
                            "label": e.get("label") or ""})
        return html_export.render(self.proj_name, self.data,
                                  self.status_list(), self.proj, geo)

    def export_html(self):
        html = self.build_html()
        path, _ = QFileDialog.getSaveFileName(
            self, "导出只读网页", f"{self.proj_name}.html", "网页 (*.html)")
        if not path:
            return
        try:
            Path(path).write_text(html, encoding="utf-8")
            self.say("已导出：" + Path(path).name)
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))


def main():
    import argparse
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--shot", default=None)
    ap.add_argument("--project", default=None)
    args, _ = ap.parse_known_args()

    qapp = QApplication([sys.argv[0]])
    qapp.setFont(QFont("Microsoft YaHei UI", 9))
    qapp.setStyleSheet(QSS)
    w = App()
    if args.project and (PROJECTS / args.project / "flow.json").exists():
        w.open_project(args.project)
    w.show()
    if args.shot:
        def grab():
            w.canvas.fit_all()
            QTimer.singleShot(500, lambda: (w.grab().save(args.shot),
                                            qapp.quit()))
        QTimer.singleShot(700, grab)
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()










