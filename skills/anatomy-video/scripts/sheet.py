"""抽帧图：给自评和给用户看用。三张图一次出齐。
用法：uv run --with pillow python sheet.py 视频.mp4 输出前缀 [--every 6] [--cuts 70.5,76.0,...] [--lead 0]
输出：
  前缀_抽帧.png     每 --every 秒一帧，6 列，左上角标时间（自评“画面变化、构图、文字”用）
  前缀_转场.png     每个切点之后 0.175 秒（叠化正中间）的帧：转场空白、半张页面、文字叠字都在这里暴露
  前缀_手机.png     6 张按手机宽度（约 390 点宽）缩小的帧：缩小后还看不看得清
--cuts 可以直接用预检报告里的切点；--lead 是片头秒数（成片里正片整体后移了多少）。
"""
import argparse, os, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('out')
ap.add_argument('--every', type=float, default=6); ap.add_argument('--cuts', default=''); ap.add_argument('--lead', type=float, default=0)
a = ap.parse_args()
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', a.video], capture_output=True, text=True).stdout)
font = next((ImageFont.truetype(f, 18) for f in ['C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/arial.ttf'] if Path(f).exists()), ImageFont.load_default())
tmp = Path(tempfile.mkdtemp(dir=os.makedirs(os.environ.get('AV_TMP', 'F:/tools/tmp'), exist_ok=True) or os.environ.get('AV_TMP', 'F:/tools/tmp')))

def grab(t, w):
    f = tmp / f'{t:.3f}_{w}.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', a.video, '-frames:v', '1', '-vf', f'scale={w}:-2', str(f)], check=True)
    return Image.open(f).convert('RGB')

def grid(ts, w, cols, path, label=lambda t: f'{int(t // 60)}:{t % 60:04.1f}'):
    ims = [grab(t, w) for t in ts]
    if not ims: return
    h = ims[0].height; rows = -(-len(ims) // cols)
    g = Image.new('RGB', (cols * w, rows * h), (20, 20, 20)); d = ImageDraw.Draw(g)
    for k, (t, im) in enumerate(zip(ts, ims)):
        x, y = (k % cols) * w, (k // cols) * h; g.paste(im, (x, y)); d.text((x + 6, y + 4), label(t), fill=(220, 40, 40), font=font)
    g.save(path); print('→', path, f'{len(ims)} 帧')

n = int(dur // a.every) + 1
grid([min(dur - 0.05, k * a.every) for k in range(n)], 320, 6, f'{a.out}_抽帧.png')
cuts = [float(x) + a.lead + 0.175 for x in a.cuts.split(',') if x.strip()]
if cuts: grid(cuts, 480, 4, f'{a.out}_转场.png', label=lambda t: f'切点 {t - 0.175:.2f}s 后 0.175s')
grid([dur * k / 7 for k in range(1, 7)], 390, 3, f'{a.out}_手机.png')
