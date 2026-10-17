"""把字级时间（tts.py 的 .timing.json）整理成成片页用的 timeline.js。
用法：python make_timeline.py 配音.timing.json 配音稿.txt 配音.mp3 输出/timeline.js [--table 读音表.md] [--lead 0.5]
- chars：[字, 起, 止, 是否实测]，不含标点空白；成片页里的锚点 A("八颗H一百") 就在这上面找
- sentences：按句号、问号、叹号、分号、换行切句；字幕文字按读音表换回写法（吉字节 → GB，H一百 → H100）
- duration：配音时长
--lead：正片开头到第一个字的留白（默认 0.5 秒；mix.py 的 --pad 必须相同），所有时间整体后移
"""
import argparse, json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from readings import load, to_display

ap = argparse.ArgumentParser(); ap.add_argument('timing'); ap.add_argument('script'); ap.add_argument('audio'); ap.add_argument('out')
ap.add_argument('--table'); ap.add_argument('--lead', type=float, default=0.5)
a = ap.parse_args()
rows = load(a.table)
tim = json.load(open(a.timing, encoding='utf-8'))['chars']; script = Path(a.script).read_text(encoding='utf-8')
by_i = {c['i']: c for c in tim}; L = a.lead
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', a.audio], capture_output=True, text=True).stdout) + L
sents, start = [], 0
for m in re.finditer(r'[。？！；\n]', script + '\n'):
    idx = [i for i in range(start, min(m.end(), len(script))) if i in by_i]
    if idx:
        text = script[start:m.end()].strip().rstrip('。；\n')
        sents.append({'text': to_display(text, rows).strip(), 's': round(by_i[idx[0]]['s'] + L, 3), 'e': round(by_i[idx[-1]]['e'] + L, 3),
                      'measured': round(sum(by_i[i]['measured'] for i in idx) / len(idx), 3)})
    start = m.end()
chars = [[c['ch'], round(c['s'] + L, 3), round(c['e'] + L, 3), 1 if c['measured'] else 0] for c in tim]
Path(a.out).write_text('window.TL=' + json.dumps({'chars': chars, 'sentences': sents, 'events': {}, 'duration': round(dur, 3)}, ensure_ascii=False) + ';', encoding='utf-8')
low = [s for s in sents if s['measured'] < 0.8]
print(f'{len(chars)} 字 {len(sents)} 句，时长 {dur:.2f}s；实测覆盖低于 80% 的句子 {len(low)} 句')
for s in low: print(f'  {s["s"]:.1f}s {s["measured"]:.0%} {s["text"][:30]}')
