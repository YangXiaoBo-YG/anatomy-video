"""开工前的环境自检：一分钟内告诉你缺什么。
用法：uv run --with playwright==1.63.0 python doctor.py [--tts]   （--tts 时再合成一句测试句，确认语音服务和音色可用）
检查：ffmpeg/ffprobe、浏览器（与 playwright 1.63.0 匹配）、Node（Anatomy 画图要 20.10+）、中文字体、
      语音密钥是否存在（只说有没有，不打印内容）、F 盘剩余空间、uv 缓存和浏览器目录不在 C 盘。
"""
import argparse, os, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from common import chrome
ap = argparse.ArgumentParser(); ap.add_argument('--tts', action='store_true'); a = ap.parse_args()
ok = True
def say(good, msg):
    global ok; ok &= bool(good); print(('  ✓ ' if good else '  ✗ ') + msg)
def ver(cmd):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.splitlines()[0]
    except Exception: return ''
print('环境自检')
say(ver(['ffmpeg', '-version']), 'ffmpeg ' + ver(['ffmpeg', '-version'])[:40])
say(ver(['ffprobe', '-version']), 'ffprobe')
c = chrome(); say(c and Path(c).exists(), f'浏览器 {c}')
nv = ver(['node', '--version']); say(nv and tuple(map(int, nv.lstrip('v').split('.')[:2])) >= (20, 10), f'Node {nv}（Anatomy 需要 20.10+）')
say(Path('C:/Windows/Fonts/msyh.ttc').exists(), '中文字体 微软雅黑')
def has_key():
    if os.environ.get('VOLC_API_KEY'): return True
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k: return bool(winreg.QueryValueEx(k, 'VOLC_API_KEY')[0])
    except Exception: return False
say(has_key(), '语音密钥 VOLC_API_KEY 已设置（不显示内容）')
free = shutil.disk_usage('F:/').free / 2 ** 30; say(free > 20, f'F 盘剩余 {free:.0f} GB（整片高清的分块和中间文件约 1–2 GB）')
uvc = os.environ.get('UV_CACHE_DIR', ''); pwb = os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '')
say(uvc and not uvc.upper().startswith('C:'), f'uv 缓存目录 {uvc or "（未设置，会落到 C 盘）"}')
say(not pwb or not pwb.upper().startswith('C:'), f'浏览器目录 {pwb or "（未设置，用 F:/tools/playwright-browsers）"}')
if a.tts:
    import tempfile
    d = Path(tempfile.mkdtemp(dir=os.makedirs(os.environ.get('AV_TMP', 'F:/tools/tmp'), exist_ok=True) or os.environ.get('AV_TMP', 'F:/tools/tmp'))); (d / 't.txt').write_text('H一百 的显存是 80 吉字节。', encoding='utf-8')
    r = subprocess.run([sys.executable, str(Path(__file__).with_name('tts.py')), str(d / 't.txt'), str(d / 't')], capture_output=True, text=True)
    say(r.returncode == 0 and (d / 't.mp3').exists(), '语音合成测试句' + ('' if r.returncode == 0 else '：' + (r.stderr or r.stdout)[-200:]))
print('全部通过' if ok else '有未通过的项目，先处理再开工'); sys.exit(0 if ok else 1)
