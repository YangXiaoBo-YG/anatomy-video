"""各工具共用：本地静态服务、找浏览器、打开成片页面。
运行方式统一为：uv run --with playwright==1.63.0 python <脚本>
  1.63.0 对应已装好的浏览器 chromium_headless_shell-1243；不写版本号时 uv 会拉新版，新版要找 1248，会直接报错。
"""
import functools, glob, http.server, os, socketserver, threading

# 临时文件一律放 F 盘（用户规矩：C 盘不再占用）。只改本进程及其子进程（浏览器、ffmpeg），不动系统设置。
TMP = os.environ.get('AV_TMP', 'F:/tools/tmp'); os.makedirs(TMP, exist_ok=True)
os.environ['TEMP'] = os.environ['TMP'] = os.environ['TMPDIR'] = TMP

def chrome():
    if os.environ.get('AV_CHROME'): return os.environ['AV_CHROME']
    roots = [os.environ.get('PLAYWRIGHT_BROWSERS_PATH', ''), 'F:/tools/playwright-browsers']
    for r in roots:
        c = sorted(glob.glob(f'{r}/chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe'))
        if c: return c[-1]
    return None

class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def serve(root):
    """在 root 上开一个只监听本机的静态服务，返回 (server, port)。"""
    socketserver.ThreadingTCPServer.daemon_threads = True
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(_Quiet, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]

def open_page(p, port, page, scale=1.0, timeout=300000):
    """打开成片页面并等它准备好（物件图加载完、字体加载完）。返回 (browser, page, errors)。
    scale < 1 用于低清预览：页面仍按 1920×1080 排版，只把截图缩小，排版和高清完全一致。"""
    b = p.chromium.launch(executable_path=chrome())
    pg = b.new_context(viewport={'width': 1920, 'height': 1080}, device_scale_factor=scale).new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    perr = []; pg.on('pageerror', lambda e: perr.append(str(e)))
    pg.goto(f'http://127.0.0.1:{port}/{page.lstrip("/")}')
    # 每秒看一次：准备好就走；页面脚本一报错立刻停（语法错误时页面永远准备不好，不能干等到超时）
    for _ in range(int(timeout / 1000)):
        if pg.evaluate('window.__ready === true || window.__bootFailed === true'): break
        if perr: raise SystemExit('页面脚本出错，启动不了：' + ' | '.join(perr[:3]))
        pg.wait_for_timeout(1000)
    else:
        raise SystemExit(f'页面 {timeout // 1000} 秒还没准备好')
    if pg.evaluate('window.__bootFailed === true'): raise SystemExit('页面启动失败：' + ' | '.join(errs))
    pg.evaluate('document.fonts.ready.then(() => true)')
    return b, pg, errs
