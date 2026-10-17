"""配乐（代码合成）+ 人声闪避 + 响度标准化到 -14 LUFS。没有给音乐时用它（CLAUDE.md：配乐用代码合成，放在节拍上）。
用法：python mix.py 配音.mp3 输出.wav [--lead 3] [--pad 0.5] [--tail 2.5]
--lead：片头秒数。人声整体后移这么多；片头开始和正片开始各有一个低音落点。
--pad：正片开头到第一个字之间的留白，必须和 make_timeline.py 的 --lead 相同。
--tail：人声结束后保留的秒数，最后 1.5 秒淡出。
配乐：Dm–B♭–C–Am 四小节循环，每小节 4 秒，每拍 1 秒一个拨弦音；人声出现时配乐压低一半。
需要：numpy、scipy（uv run --with numpy --with scipy python mix.py …）
"""
import argparse, os, json, subprocess, tempfile, wave
from pathlib import Path
import numpy as np
from scipy.signal import butter, lfilter

ap = argparse.ArgumentParser(); ap.add_argument('voice'); ap.add_argument('out')
ap.add_argument('--lead', type=float, default=0.0); ap.add_argument('--pad', type=float, default=0.5); ap.add_argument('--tail', type=float, default=2.5)
a = ap.parse_args()
SR = 44100; tmp = Path(tempfile.mkdtemp(dir=os.makedirs(os.environ.get('AV_TMP', 'F:/tools/tmp'), exist_ok=True) or os.environ.get('AV_TMP', 'F:/tools/tmp')))
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', a.voice, '-ar', str(SR), '-ac', '1', str(tmp / 'v.wav')], check=True)
w = wave.open(str(tmp / 'v.wav')); Vv = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
DUR = len(Vv) / SR + a.tail + a.lead + a.pad; N = int(SR * DUR); M = np.zeros(N)
mid2f = lambda m: 440 * 2 ** ((m - 69) / 12)
def lp(x, f): b, c = butter(2, f / (SR / 2)); return lfilter(b, c, x)
def put(sig, t0, g=1.):
    i = int(t0 * SR); j = min(N, i + len(sig))
    if 0 <= i < N: M[i:j] += sig[:j - i] * g
tt = lambda d: np.arange(int(SR * d)) / SR
def pluck(m, d=2.4):
    f = mid2f(m); t = tt(d)
    return lp(sum(k * np.sin(2 * np.pi * f * h * t) * np.exp(-e * t) for h, k, e in [(1, 1, 1.8), (2, .3, 3), (3, .1, 5)]), 3000) * np.minimum(1, t / .01)
def pad(ms, t0, d, g):
    t = tt(d)
    for m in ms: put(lp(np.sin(2 * np.pi * mid2f(m) * t) + .2 * np.sin(2 * np.pi * mid2f(m) * 2 * t), 800) * np.minimum(1, t / 1.5) * np.minimum(1, (d - t) / 1.5), t0, g / len(ms))
CH = [[38, 45, 50, 53], [34, 41, 46, 50], [36, 43, 48, 52], [33, 40, 45, 48]]   # Dm B♭ C Am
for k in range(int(DUR / 4.0) + 1):
    t0 = k * 4.0
    if t0 >= DUR: break
    c = CH[k % 4]; pad(c, t0, 5.2, .20)
    for i, m in enumerate([c[1] + 12, c[2] + 12, c[3] + 12, c[2] + 12]):
        if t0 + i < DUR - 1: put(pluck(m), t0 + i, .07)
t = tt(.6)
for t0 in sorted({0.3, a.lead + 0.3}): put(lp(np.sin(2 * np.pi * 55 * t) * np.exp(-t * 5), 200), t0, .2)
VO = np.zeros(N); i0 = int((a.lead + a.pad) * SR); n = min(N - i0, len(Vv)); VO[i0:i0 + n] = Vv[:n]
env = lp(np.convolve(np.abs(VO), np.ones(int(.06 * SR)) / int(.06 * SR), 'same'), 12)
duck = 1 - .5 * np.clip(env / (np.percentile(env, 95) + 1e-9), 0, 1)
mix = VO + M * duck * 1.4; mix *= np.minimum(1, (DUR - np.arange(N) / SR) / 1.5); mix = mix / np.abs(mix).max() * .8
with wave.open(str(tmp / 'pre.wav'), 'wb') as o: o.setnchannels(1); o.setsampwidth(2); o.setframerate(SR); o.writeframes((mix * 32767).astype(np.int16).tobytes())
r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(tmp / 'pre.wav'), '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'], capture_output=True, text=True).stderr
j = json.loads(r[r.rindex('{'):r.rindex('}') + 1])
af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
      f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(tmp / 'pre.wav'), '-af', af, '-ar', '48000', '-ac', '2', a.out], check=True)
chk = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', a.out, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
print(a.out, [l.strip() for l in chk.splitlines() if 'I:' in l or 'Peak:' in l][-2:], f'{DUR:.1f}s')
