#!/usr/bin/env python3
"""Optimized Web Control for Android - 高帧率 ADB 截图流方案"""

import argparse
import json
import os
import subprocess
import threading
import time
import io
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image

ADB_BIN = os.environ.get("ADB_BIN", "adb")
DEVICE_ID = None
SCREEN_WIDTH = 1080
SCREEN_HEIGHT = 1920

# 截图缓存
latest_frame = None
frame_lock = threading.Lock()

class FrameCapture(threading.Thread):
    """后台持续截图线程"""
    def __init__(self, device_id, fps=20):
        super().__init__(daemon=True)
        self.device_id = device_id
        self.fps = fps
        self.running = True
        
    def run(self):
        global latest_frame
        interval = 1.0 / self.fps
        
        while self.running:
            try:
                # 快速截图
                cmd = [ADB_BIN, '-s', self.device_id, 'exec-out', 'screencap', '-p']
                result = subprocess.run(cmd, capture_output=True, timeout=2)
                
                if result.returncode == 0 and result.stdout:
                    # 压缩为 JPEG 以减少传输
                    img = Image.open(io.BytesIO(result.stdout))
                    
                    # 保持比例缩放，最大宽度 720
                    w, h = img.size
                    if w > 720:
                        ratio = 720 / w
                        new_size = (720, int(h * ratio))
                        img = img.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # 转换为 JPEG
                    buf = io.BytesIO()
                    img.convert('RGB').save(buf, 'JPEG', quality=75, optimize=True)
                    
                    with frame_lock:
                        latest_frame = buf.getvalue()
                        
            except Exception as e:
                print(f"[Capture] Error: {e}")
            
            time.sleep(interval)

def run_adb(device_id, *parts):
    cmd = [ADB_BIN]
    if device_id:
        cmd += ['-s', device_id]
    cmd += list(parts)
    return subprocess.run(cmd, capture_output=True)

def adb_shell(device_id, shell_cmd):
    return run_adb(device_id, 'shell', shell_cmd)

HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Android Web Control</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
      font-family: system-ui, sans-serif; 
      background: #0f0f23;
      color: #fff;
      height: 100vh;
      display: flex;
      overflow: hidden;
    }
    .main {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      padding: 20px;
    }
    #screen-container {
      position: relative;
      background: #000;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 8px 32px rgba(0,0,0,0.5);
      max-width: 100%;
      max-height: 100%;
    }
    #screen-img {
      display: block;
      max-width: 100%;
      max-height: 85vh;
      cursor: crosshair;
    }
    .sidebar {
      width: 70px;
      background: #1a1a2e;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 20px 0;
      gap: 12px;
      border-left: 1px solid #333;
    }
    .ctrl-btn {
      width: 48px;
      height: 48px;
      border: none;
      border-radius: 12px;
      background: #16213e;
      color: #fff;
      font-size: 20px;
      cursor: pointer;
      transition: all 0.15s;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #333;
    }
    .ctrl-btn:hover {
      background: #e94560;
      transform: scale(1.05);
      border-color: #e94560;
    }
    .ctrl-btn:active { transform: scale(0.95); }
    .status {
      position: absolute;
      top: 15px;
      left: 15px;
      padding: 8px 16px;
      background: rgba(0,0,0,0.7);
      border-radius: 20px;
      font-size: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
      backdrop-filter: blur(10px);
    }
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #ff4444;
      transition: background 0.3s;
    }
    .status-dot.online {
      background: #00ff88;
      box-shadow: 0 0 8px #00ff88;
    }
    .input-area {
      position: absolute;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      gap: 10px;
      background: rgba(0,0,0,0.7);
      padding: 10px;
      border-radius: 30px;
      backdrop-filter: blur(10px);
    }
    .input-area input {
      padding: 10px 20px;
      border: none;
      border-radius: 20px;
      background: rgba(255,255,255,0.1);
      color: #fff;
      width: 250px;
      outline: none;
    }
    .input-area button {
      padding: 10px 20px;
      border: none;
      border-radius: 20px;
      background: #e94560;
      color: #fff;
      cursor: pointer;
      font-weight: bold;
    }
    .fps-counter {
      position: absolute;
      top: 15px;
      right: 15px;
      padding: 6px 12px;
      background: rgba(0,0,0,0.6);
      border-radius: 15px;
      font-size: 12px;
      font-family: monospace;
    }
  </style>
</head>
<body>
  <div class="main">
    <div class="status">
      <div class="status-dot" id="statusDot"></div>
      <span id="statusText">Connecting...</span>
    </div>
    <div class="fps-counter" id="fps">0 FPS</div>
    
    <div id="screen-container">
      <img id="screen-img" src="/frame.jpg" alt="Screen">
    </div>
    
    <div class="input-area">
      <input type="text" id="textInput" placeholder="输入文字..." onkeypress="if(event.key==='Enter')sendText()">
      <button onclick="sendText()">发送</button>
    </div>
  </div>

  <div class="sidebar">
    <button class="ctrl-btn" onclick="sendKey('HOME')" title="Home">⌂</button>
    <button class="ctrl-btn" onclick="sendKey('BACK')" title="Back">←</button>
    <button class="ctrl-btn" onclick="sendKey('APP_SWITCH')" title="Recent">□</button>
    <button class="ctrl-btn" onclick="sendKey('POWER')" title="Power">⏻</button>
    <button class="ctrl-btn" onclick="sendKey('VOLUME_UP')" title="Volume+">+</button>
    <button class="ctrl-btn" onclick="sendKey('VOLUME_DOWN')" title="Volume-">−</button>
  </div>

  <script>
    const img = document.getElementById('screen-img');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const fpsEl = document.getElementById('fps');
    
    let frameCount = 0;
    let lastFpsTime = Date.now();
    let isConnected = false;
    
    // 持续刷新截图
    function updateFrame() {
      const newSrc = '/frame.jpg?t=' + Date.now();
      const newImg = new Image();
      
      newImg.onload = () => {
        img.src = newSrc;
        frameCount++;
        if (!isConnected) {
          isConnected = true;
          statusDot.classList.add('online');
          statusText.textContent = 'Connected';
        }
        setTimeout(updateFrame, 50); // 20fps max
      };
      
      newImg.onerror = () => {
        isConnected = false;
        statusDot.classList.remove('online');
        statusText.textContent = 'Reconnecting...';
        setTimeout(updateFrame, 1000);
      };
      
      newImg.src = newSrc;
    }
    
    // FPS 计数器
    setInterval(() => {
      const now = Date.now();
      const fps = Math.round(frameCount * 1000 / (now - lastFpsTime));
      fpsEl.textContent = fps + ' FPS';
      frameCount = 0;
      lastFpsTime = now;
    }, 1000);
    
    // 启动
    updateFrame();
    
    // 触控处理
    function getPos(e) {
      const rect = img.getBoundingClientRect();
      const scaleX = img.naturalWidth / rect.width;
      const scaleY = img.naturalHeight / rect.height;
      const clientX = e.clientX || (e.touches && e.touches[0].clientX);
      const clientY = e.clientY || (e.touches && e.touches[0].clientY);
      return {
        x: Math.round((clientX - rect.left) * scaleX),
        y: Math.round((clientY - rect.top) * scaleY)
      };
    }
    
    img.addEventListener('mousedown', async (e) => {
      const pos = getPos(e);
      await fetch('/api/tap', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(pos)
      });
    });
    
    img.addEventListener('touchstart', async (e) => {
      e.preventDefault();
      const pos = getPos(e);
      await fetch('/api/tap', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(pos)
      });
    });
    
    // 按键控制
    const KEY_MAP = {
      'HOME': 3, 'BACK': 4, 'APP_SWITCH': 187,
      'POWER': 26, 'VOLUME_UP': 24, 'VOLUME_DOWN': 25
    };
    
    async function sendKey(key) {
      await fetch('/api/key', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({key: KEY_MAP[key]})
      });
    }
    
    async function sendText() {
      const input = document.getElementById('textInput');
      const text = input.value;
      if (!text) return;
      await fetch('/api/text', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text})
      });
      input.value = '';
    }
  </script>
</body>
</html>
"""

class Handler(BaseHTTPRequestHandler):
    def _json(self, status, payload):
        data = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith('/frame.jpg'):
            global latest_frame
            with frame_lock:
                frame = latest_frame
            
            if frame:
                self.send_response(HTTPStatus.OK)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Content-Length', str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
            else:
                self.send_error(503, 'Frame not ready')
            return

        self.send_response(HTTPStatus.OK)
        body = HTML.encode('utf-8')
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(length) if length else b'{}'
        
        try:
            data = json.loads(raw.decode('utf-8'))
        except:
            self._json(400, {'ok': False, 'error': 'bad json'})
            return

        if self.path == '/api/tap':
            x, y = int(data.get('x', 0)), int(data.get('y', 0))
            adb_shell(DEVICE_ID, f'input tap {x} {y}')
            self._json(200, {'ok': True, 'action': 'tap', 'x': x, 'y': y})
            return

        if self.path == '/api/key':
            key = int(data.get('key', 4))
            adb_shell(DEVICE_ID, f'input keyevent {key}')
            self._json(200, {'ok': True, 'action': 'key', 'key': key})
            return

        if self.path == '/api/text':
            text = str(data.get('text', ''))
            encoded = text.replace(' ', '%s').replace('"', '\\"')
            adb_shell(DEVICE_ID, f'input text "{encoded}"')
            self._json(200, {'ok': True, 'action': 'text'})
            return

        self._json(404, {'ok': False, 'error': 'not found'})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device-id', default='')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--fps', type=int, default=20)
    args = parser.parse_args()

    global DEVICE_ID
    DEVICE_ID = args.device_id

    # 启动后台截图线程
    capture = FrameCapture(args.device_id, fps=args.fps)
    capture.start()

    # 等待第一帧
    print('[Server] Waiting for first frame...')
    for _ in range(50):
        with frame_lock:
            if latest_frame:
                break
        time.sleep(0.1)

    # 启动 HTTP 服务器
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'[Server] Running on http://{args.host}:{args.port}')
    print(f'[Server] Device: {args.device_id or "default"}, Target FPS: {args.fps}')
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[Server] Stopping...')
        capture.running = False
        server.shutdown()

if __name__ == '__main__':
    main()
