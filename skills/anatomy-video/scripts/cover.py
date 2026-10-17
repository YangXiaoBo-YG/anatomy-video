"""系列封面：同一个模板出封面图（缩略图）和片头视频（放在成片最前面）。
用户说的“封面”两样都要：B 站缩略图 + 视频开头 3 秒（第 01 集确认）。
用法：uv run --with playwright==1.63.0 python cover.py --root 服务根 --figsrc anatomy/hgx/hgx-light.html --pose '{"hs":0.6}' \
        --series 硬核拆解英伟达GPU --ep 01 --name H100 --sub 从八卡底板拆到TensorCore --meta "Hopper 架构 · 2022" \
        --png 封面.png --intro 片头.mp4 [--seconds 3.4]
片头：封面文字一直在，物件在 0.3–1.9 秒从合拢缓动到封面姿态，之后停在和封面图一模一样的画面。
--seconds 比片头长 0.4 秒，多出来的部分给 final.py 叠化进正片。
"""
import argparse, shutil, subprocess, sys, urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).parent)); from common import serve, chrome

ap = argparse.ArgumentParser()
for k in ('root', 'figsrc', 'pose', 'series', 'ep', 'name', 'sub', 'meta', 'png', 'intro', 'x', 'y', 's'): ap.add_argument('--' + k)
ap.add_argument('--seconds', type=float, default=3.4)
a = ap.parse_args()
root = Path(a.root); tdir = root / '_av_cover'; tdir.mkdir(exist_ok=True)
shutil.copy(Path(__file__).resolve().parents[1] / 'templates' / 'cover.html', tdir / 'cover.html')
# figsrc 写成相对服务根目录的路径、不带开头的斜杠：Git Bash 会把以 / 开头的参数改写成 C:/Program Files/Git/...
a.figsrc = '/' + a.figsrc.replace('\\', '/').split('/Git/')[-1].lstrip('/')
qs = urllib.parse.urlencode({k: v for k in ('series', 'ep', 'name', 'sub', 'meta', 'figsrc', 'pose', 'x', 'y', 's') if (v := getattr(a, k))})
srv, port = serve(root)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=chrome()); pg = b.new_page(viewport={'width': 1920, 'height': 1080})
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.goto(f'http://127.0.0.1:{port}/_av_cover/cover.html?{qs}')
    try: pg.wait_for_function('window.__ready === true', timeout=120000)
    except Exception: sys.exit('封面页没有准备好：' + ' | '.join(errs[:5]) + f'；地址参数：{qs}')
    pg.evaluate('document.fonts.ready.then(() => true)')
    if a.png:
        pg.evaluate('window.render(99)'); pg.screenshot(path=a.png); print('封面图 →', a.png)
    if a.intro:
        ff = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'png', '-i', '-',
                               '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', a.intro], stdin=subprocess.PIPE)
        for i in range(round(a.seconds * 30)):
            pg.evaluate('t => window.render(t)', i / 30); ff.stdin.write(pg.screenshot(type='png'))
        ff.stdin.close(); ff.wait(); print('片头 →', a.intro)
    b.close()
srv.shutdown(); shutil.rmtree(tdir, ignore_errors=True)
