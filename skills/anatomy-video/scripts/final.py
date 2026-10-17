"""成片合成：片头叠化进正片 + 配乐配音 + 核对。
用法：python final.py --intro 片头.mp4 --video 正片无声.mp4 --audio 混音.wav --out 成片.mp4 [--lead 3]
--lead 必须和 mix.py 的 --lead 相同：片头在第 lead 秒开始叠化（0.4 秒），正片第 0 帧正好落在第 lead 秒，人声也后移了 lead 秒。
不给 --intro 时直接把正片和混音合在一起（--lead 应为 0）。
核对：响度 -14 LUFS（±0.5）、时长与混音相差不超过 0.1 秒；不合格退出码 1。
"""
import argparse, re, subprocess, sys
ap = argparse.ArgumentParser()
ap.add_argument('--intro'); ap.add_argument('--video', required=True); ap.add_argument('--audio', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--lead', type=float, default=0.0)
a = ap.parse_args()
dur = lambda f: float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout)
if a.intro:
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', a.intro, '-i', a.video, '-i', a.audio, '-filter_complex',
           f'[0:v][1:v]xfade=transition=fade:duration=0.4:offset={a.lead},format=yuv420p[v]', '-map', '[v]', '-map', '2:a',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '16']
else:
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', a.video, '-i', a.audio, '-map', '0:v', '-map', '1:a', '-c:v', 'copy']
subprocess.run(cmd + ['-c:a', 'aac', '-b:a', '192k', '-shortest', a.out], check=True)
r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', a.out, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
lufs = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', r)[-1]); d_out, d_aud = dur(a.out), dur(a.audio)
ok = abs(lufs + 14) <= 0.5 and abs(d_out - d_aud) <= 0.1
print(f'{a.out}：{d_out:.2f}s（混音 {d_aud:.2f}s），响度 {lufs:.1f} LUFS → {"合格" if ok else "不合格"}')
if abs(lufs + 14) > 0.5: print(f'  响度差 {lufs + 14:+.1f} dB：重跑 mix.py，或在这里加 -af volume={-(lufs + 14):.1f}dB')
sys.exit(0 if ok else 1)
