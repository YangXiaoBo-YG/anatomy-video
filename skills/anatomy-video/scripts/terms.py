"""术语扫描：写完配音稿后先跑。禁用写法报错；新术语列出来，并挑出含新术语的句子做成 30 秒试读稿。
用法：python terms.py 配音稿.txt 输出前缀 [--table 读音表.md] [--max 180]
输出：前缀_试读.txt（送 tts.py 合成，用户听；确认后把新术语写回读音表）
退出码：有禁用写法为 1。
"""
import argparse, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from readings import load, token_re

ap = argparse.ArgumentParser(); ap.add_argument('script'); ap.add_argument('out')
ap.add_argument('--table'); ap.add_argument('--max', type=int, default=180, help='试读稿最多多少字（约 30 秒）')
a = ap.parse_args()
text = Path(a.script).read_text(encoding='utf-8'); rows = load(a.table)
ctx = lambda m: text[max(0, m.start() - 8):m.end() + 8].replace('\n', ' ')

bad = [(r, m) for r in rows if r['state'] == '禁用' for m in token_re(r['write']).finditer(text)]
# 表里已有的写法先遮掉（禁用的已经单独报了），剩下的英文、型号就是新术语
masked = text
for r in sorted(rows, key=lambda r: -len(r['write'])):
    masked = token_re(r['write']).sub(lambda m: '□' * len(m.group()), masked)
new = {}
for m in re.finditer(r'[A-Za-z][A-Za-z0-9+\-]*', masked): new.setdefault(m.group(), []).append(ctx(m))
pending = [r['write'] for r in rows if r['state'] == '待试读' and token_re(r['write']).search(text)]

print(f'禁用写法 {len(bad)} 处，新术语 {len(new)} 个，待试读 {len(pending)} 个')
for r, m in bad: print(f'  禁用「{r["write"]}」→ {r["note"]}：…{ctx(m)}…')
for w, cs in new.items(): print(f'  新术语「{w}」出现 {len(cs)} 次：…{cs[0]}…')
for w in pending: print(f'  待试读「{w}」')

# 试读稿：每个新术语、待试读词取第一次出现的那句话，凑到约 30 秒
want = list(new) + pending; picked = []
sents = [s.strip() for s in re.split(r'(?<=[。！？；\n])', text) if s.strip()]
for w in want:
    s = next((s for s in sents if token_re(w).search(s)), None)
    if s and s not in picked and sum(map(len, picked)) + len(s) <= a.max: picked.append(s)
if picked:
    Path(a.out + '_试读.txt').write_text('\n'.join(picked), encoding='utf-8')
    print(f'试读稿 {sum(map(len, picked))} 字 → {a.out}_试读.txt；合成：python tts.py {a.out}_试读.txt {a.out}_试读')
else:
    print('没有需要试读的新词')
sys.exit(1 if bad else 0)
