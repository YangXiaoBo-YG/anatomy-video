"""把豆包异步接口返回的字级时间（sentences[].words[]）贴回稿子上的每个字，取代语音识别对齐。
用法：python tts_timing.py（通常由 tts.py 自动调用） 接口结果.json 稿子.txt 输出前缀 [--asr 识别对齐.timing.json]
输出：
  前缀.timing.json  与 align.py 同格式：稿子每个字（去掉空白和标点）的起止时间
  前缀.readings.txt 稿子写法 → 引擎实际念的字（数字、型号、单位的读法都在这里核对）
  有 --asr 时，打印两种时间的差值（验收用）
贴法：引擎念的字和稿子逐字比对。一样的字直接取时间；写法不同的一段（如 80 → 八十）
      用引擎念这段的时间范围按字数均分；稿子有、引擎没念的字记为未实测。
"""
import argparse, json, difflib, statistics
ap = argparse.ArgumentParser(); ap.add_argument('result'); ap.add_argument('script'); ap.add_argument('out'); ap.add_argument('--asr')
a = ap.parse_args()
PUNCT = set('，。、：；？！,.:;?!“”"‘’\'（）()《》<>【】[]—-…·\n\r\t ')
d = json.load(open(a.result, encoding='utf-8'))
script = open(a.script, encoding='utf-8').read()
S = [(i, c) for i, c in enumerate(script) if c not in PUNCT and not c.isspace()]
# 引擎念的字：每个 word 拆成字，时间在 word 内均分
T = []
for s in d['sentences']:
    for w in s['words']:
        cs = [c for c in w['word'] if c not in PUNCT and not c.isspace()]
        for k, c in enumerate(cs):
            dur = (w['endTime'] - w['startTime']) / len(cs)
            T.append((c, w['startTime'] + k * dur, w['startTime'] + (k + 1) * dur, w['confidence']))
norm = lambda c: c.lower()
sm = difflib.SequenceMatcher(None, [norm(c) for _, c in S], [norm(t[0]) for t in T], autojunk=False)
out, readings = {}, []
for op, i1, i2, j1, j2 in sm.get_opcodes():
    if op == 'equal':
        for k in range(i2 - i1): out[i1 + k] = (T[j1 + k][1], T[j1 + k][2], True)
    elif op == 'replace':
        t0, t1 = T[j1][1], T[j2 - 1][2]; n = i2 - i1
        for k in range(n): out[i1 + k] = (t0 + (t1 - t0) * k / n, t0 + (t1 - t0) * (k + 1) / n, True)
        readings.append((t0, ''.join(c for _, c in S[i1:i2]), ''.join(t[0] for t in T[j1:j2])))
    elif op == 'delete':
        readings.append((T[j1][1] if j1 < len(T) else T[-1][2], ''.join(c for _, c in S[i1:i2]), '（没念）'))
    elif op == 'insert':
        readings.append((T[j1][1], '（稿子没有）', ''.join(t[0] for t in T[j1:j2])))
# 没念的字：按前后已知时间插值
known = sorted(out); chars = []
for k, (i, c) in enumerate(S):
    if k in out: s, e, m = out[k]
    else:
        prev = max([x for x in known if x < k], default=None); nxt = min([x for x in known if x > k], default=None)
        s = e = out[prev][1] if prev is not None else (out[nxt][0] if nxt is not None else 0.0); m = False
    chars.append({'i': i, 'ch': c, 's': round(s, 3), 'e': round(e, 3), 'measured': m})
json.dump({'source': 'tts-timestamp', 'chars': chars}, open(a.out + '.timing.json', 'w', encoding='utf-8'), ensure_ascii=False)
with open(a.out + '.readings.txt', 'w', encoding='utf-8') as f:
    f.write('时间  稿子写法 → 引擎念的字\n')
    for t, x, y in readings: f.write(f'{t:7.2f}s  {x} → {y}\n')
low = [t for t in T if t[3] < 0.5]
print(f'稿子 {len(S)} 字，引擎 {len(T)} 字；逐字一致 {sum(1 for o in sm.get_opcodes() if o[0]=="equal" for _ in range(o[2]-o[1]))} 字，'
      f'写法不同 {sum(1 for r in readings if r[2] not in ("（没念）",) and r[1] != "（稿子没有）")} 处，没念 {sum(1 for r in readings if r[2]=="（没念）")} 处，'
      f'多念 {sum(1 for r in readings if r[1]=="（稿子没有）")} 处；置信度 < 0.5 的字 {len(low)} 个')
if a.asr:
    asr = {c['i']: c for c in json.load(open(a.asr, encoding='utf-8'))['chars']}
    diffs = [abs(c['s'] - asr[c['i']]['s']) for c in chars if c['measured'] and c['i'] in asr and asr[c['i']]['measured']]
    diffs.sort()
    print(f'与识别对齐比较 {len(diffs)} 字：中位差 {statistics.median(diffs):.3f}s，90% 在 {diffs[int(len(diffs)*.9)]:.3f}s 内，最大 {diffs[-1]:.3f}s')
