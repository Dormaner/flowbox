"""给浏览器调试用的本地桥：把 projects/ 暴露成几个接口。

真正打包（Tauri）之后就不需要它了，命令在 src-tauri 里。
    python bridge.py            # 默认 127.0.0.1:8765
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent      # 仓库根目录
PROJECTS = ROOT / "projects"
PORT = 8765


def rebind(projects: Path) -> None:
    """换数据目录（自动化测试用，别碰真实项目）。"""
    global PROJECTS
    PROJECTS = projects


def flow_path(project: str) -> Path:
    name = "".join(c for c in project if c not in '\\/:*?"<>|')
    return PROJECTS / name / "flow.json"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):        # 安静点，别刷屏
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, data, code=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/projects":
            names = []
            if PROJECTS.exists():
                names = sorted(p.name for p in PROJECTS.iterdir()
                               if p.is_dir() and (p / "flow.json").exists())
            self._json(names)
            return
        if u.path == "/flow":
            p = flow_path((q.get("project") or [""])[0])
            if not p.exists():
                self._json({"error": "没有这个项目"}, 404)
                return
            self._json(json.loads(p.read_text(encoding="utf-8")))
            return
        if u.path == "/file":
            base = flow_path((q.get("project") or [""])[0]).parent
            target = (base / (q.get("path") or [""])[0]).resolve()
            if not str(target).startswith(str(base)) or not target.is_file():
                self.send_error(404)
                return
            raw = target.read_bytes()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type",
                             mimetypes.guess_type(str(target))[0]
                             or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_error(404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/flow":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        project = body.get("project") or ""
        doc = body.get("doc") or {}
        p = flow_path(project)
        p.parent.mkdir(parents=True, exist_ok=True)
        (p.parent / "files").mkdir(exist_ok=True)
        (p.parent / "snapshots").mkdir(exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, p)
        self._json({"ok": True})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    if len(sys.argv) > 2:
        rebind(Path(sys.argv[2]).resolve())
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"bridge on http://127.0.0.1:{port}  (projects = {PROJECTS})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
