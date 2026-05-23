#!/usr/bin/env python3
"""Minimal web takeover console for Android via ADB.

Usage:
  python tools/web_takeover.py --device-id <adb_id> --host 0.0.0.0 --port 8765
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Android 接管控制台</title>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; margin: 12px; }
    .row { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px; }
    button { padding:8px 12px; }
    #screen { width: 100%; max-width: 420px; border:1px solid #ccc; border-radius:8px; }
    .hint { color:#666; font-size:13px; }
    input { padding:8px; min-width:260px; }
  </style>
</head>
<body>
  <h3>手机接管控制台</h3>
  <div class="row">
    <button onclick="post('/api/key',{key:'HOME'})">Home</button>
    <button onclick="post('/api/key',{key:'BACK'})">Back</button>
    <button onclick="post('/api/key',{key:'APP_SWITCH'})">Recent</button>
    <button onclick="refresh()">刷新截图</button>
  </div>
  <div class="row">
    <input id="txt" placeholder="输入文本（会自动转义空格）" />
    <button onclick="sendText()">输入文本</button>
  </div>
  <img id="screen" src="/frame.jpg" onclick="tap(event)" />
  <p class="hint">点击截图即可点按对应坐标；截图每 1.5 秒自动刷新。</p>

<script>
const img = document.getElementById('screen');

async function post(url, body){
  const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body||{})});
  const t = await r.text();
  if(!r.ok){ alert('操作失败: '+t); }
}

function refresh(){
  img.src = '/frame.jpg?t=' + Date.now();
}

function tap(e){
  const rect = img.getBoundingClientRect();
  const x = Math.round((e.clientX - rect.left) * (img.naturalWidth / rect.width));
  const y = Math.round((e.clientY - rect.top) * (img.naturalHeight / rect.height));
  post('/api/tap', {x,y}).then(refresh);
}

function sendText(){
  const text = document.getElementById('txt').value || '';
  if(!text) return;
  post('/api/text', {text}).then(refresh);
}

setInterval(refresh, 1500);
</script>
</body>
</html>
"""


ADB_BIN = os.environ.get("ADB_BIN", "adb")


def run_adb(device_id: str, *parts: str) -> subprocess.CompletedProcess:
    cmd = [ADB_BIN]
    if device_id:
        cmd += ["-s", device_id]
    cmd += list(parts)
    return subprocess.run(cmd, capture_output=True)


def adb_shell(device_id: str, shell_cmd: str) -> subprocess.CompletedProcess:
    return run_adb(device_id, "shell", shell_cmd)


class Handler(BaseHTTPRequestHandler):
    device_id: str = ""

    def _json(self, status: int, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/frame.jpg"):
            p = run_adb(self.device_id, "exec-out", "screencap", "-p")
            if p.returncode != 0 or not p.stdout:
                self.send_error(500, p.stderr.decode("utf-8", "ignore") or "screencap failed")
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(p.stdout)))
            self.end_headers()
            self.wfile.write(p.stdout)
            return

        self.send_response(HTTPStatus.OK)
        body = HTML.encode("utf-8")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            self._json(400, {"ok": False, "error": "bad json"})
            return

        if self.path == "/api/tap":
            x = int(data.get("x", -1))
            y = int(data.get("y", -1))
            p = adb_shell(self.device_id, f"input tap {x} {y}")
            if p.returncode != 0:
                self._json(500, {"ok": False, "error": p.stderr.decode("utf-8", "ignore")})
                return
            self._json(200, {"ok": True, "action": "tap", "x": x, "y": y})
            return

        if self.path == "/api/key":
            key = str(data.get("key", "BACK")).upper()
            key_map = {"BACK": 4, "HOME": 3, "APP_SWITCH": 187}
            code = key_map.get(key, 4)
            p = adb_shell(self.device_id, f"input keyevent {code}")
            if p.returncode != 0:
                self._json(500, {"ok": False, "error": p.stderr.decode("utf-8", "ignore")})
                return
            self._json(200, {"ok": True, "action": "key", "key": key})
            return

        if self.path == "/api/text":
            text = str(data.get("text", ""))
            encoded = urllib.parse.quote(text, safe="")
            # adb input text needs spaces as %s
            encoded = encoded.replace("%20", "%s")
            p = adb_shell(self.device_id, f"input text {encoded}")
            if p.returncode != 0:
                self._json(500, {"ok": False, "error": p.stderr.decode("utf-8", "ignore")})
                return
            self._json(200, {"ok": True, "action": "text"})
            return

        self._json(404, {"ok": False, "error": "not found"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device-id", default="")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    # quick connectivity check
    p = run_adb(args.device_id, "get-state")
    if p.returncode != 0:
        raise SystemExit(f"ADB not ready: {p.stderr.decode('utf-8', 'ignore')}")

    Handler.device_id = args.device_id
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Web takeover running on http://{args.host}:{args.port} (device={args.device_id or 'default'})")
    server.serve_forever()


if __name__ == "__main__":
    main()
