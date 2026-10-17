"""预检：不截图、不渲染视频，几十秒内查出时间轴和内容上的错误。
用法：uv run --with playwright==1.63.0 python preflight.py --root 服务根目录 --page 成片页相对路径 [--params 参数口径表.md] [--report 报告.txt]
成片页要求（见 references/成片页约定.md）：window.TL 时间轴；A(锚点) 记入 window.__anchors；CUT(锚点) 记入 window.__cuts；
  window.render(t)、window.__total；文字栏每一行 class="it"。
检查项：
  错误（必须改）：锚点在稿子里找不到；切点没落在锚点所在那一句的句首前 0.2 秒（H100 一集 7 个切点提前一句就是这个）
  提醒（逐条看）：切点锚点不在句首（镜头会比这个词早切很多）；锚点在稿子里出现多次却没写第几次；锚点落在没实测到的字上；
                  两个相邻锚点相隔超过 3.5 秒（可能出现空拍）；画面和字幕上的数字在参数口径表里找不到
退出码：有错误为 1。
"""
import argparse, json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).parent)); from common import serve, open_page

ap = argparse.ArgumentParser()
ap.add_argument('--root', required=True); ap.add_argument('--page', required=True)
ap.add_argument('--params'); ap.add_argument('--report'); ap.add_argument('--gap', type=float, default=3.5)
a = ap.parse_args()
srv, port = serve(a.root)
with sync_playwright() as p:
    b, pg, errs = open_page(p, port, a.page)
    total = pg.evaluate('window.__total')
    # 每 0.25 秒调一次 render(t)：只有镜头在场时才会调用的锚点也能全部记下来
    pg.evaluate('''(total) => { for (let t = 0; t <= total; t += 0.25) window.render(t); window.render(0); }''', total)
    TL = pg.evaluate('window.TL')
    anchors = pg.evaluate('[...(window.__anchors || new Map()).values()]')
    cuts = pg.evaluate('[...(window.__cuts || new Map()).values()]')
    missing = pg.evaluate('typeof missing !== "undefined" ? [...new Set(missing)] : []')
    texts = pg.evaluate('[...document.querySelectorAll(".it")].map(e => e.textContent)')
    b.close()
srv.shutdown()

E, W = [], []                      # 错误、提醒
FULL = ''.join(c[0] for c in TL['chars']); S = TL['sentences']
fmt = lambda t: f'{t:7.2f}s'
for m in missing: E.append(f'锚点找不到：「{m}」（稿子里没有这几个字，检查读法写法，如 H一百、吉字节）')
# 切点：锚点所在的句子 = 句首不晚于锚点的最后一句
for c in sorted(cuts, key=lambda c: c['anchor']):
    own = [s for s in S if s['s'] <= c['anchor'] + 0.05]
    if not own: E.append(f'{fmt(c["anchor"])}  切点「{c["str"]}」前面没有句子'); continue
    want = own[-1]['s'] - 0.2
    if abs(c['cut'] - want) > 0.01:
        E.append(f'{fmt(c["anchor"])}  切点「{c["str"]}」切在 {c["cut"]:.2f}s，应为 {want:.2f}s（所在句：{own[-1]["text"][:18]}…）；差 {c["cut"] - want:+.2f}s')
    elif c['anchor'] - own[-1]['s'] > 1.0:
        W.append(f'{fmt(c["anchor"])}  切点锚点「{c["str"]}」不在句首，镜头比这个词早 {c["anchor"] - own[-1]["s"] + 0.2:.1f}s 切')
# 锚点
for x in sorted(anchors, key=lambda x: x['t']):
    if x['count'] > 1 and x['n'] == 1:
        occ = [TL['chars'][m.start()][1] for m in re.finditer(re.escape(x['str']), FULL)]
        W.append(f'{fmt(x["t"])}  锚点「{x["str"]}」在稿子里出现 {x["count"]} 次（{", ".join(f"{t:.1f}s" for t in occ)}），默认取第 1 次；要后面的请写 A("{x["str"]}", 2)')
    if x.get('measured') == 0:
        W.append(f'{fmt(x["t"])}  锚点「{x["str"]}」落在没有实测时间的字上，时间是估算的')
# 空拍：相邻锚点（含切点）相隔太久
ts = sorted({round(x['t'], 2) for x in anchors} | {round(c['cut'], 2) for c in cuts} | {0.0})
ts.append(round(TL['duration'], 2))
for t0, t1 in zip(ts, ts[1:]):
    if t1 - t0 > a.gap:
        said = ''.join(ch[0] for ch in TL['chars'] if t0 <= ch[1] < t1)[:24]
        W.append(f'{fmt(t0)}  {t0:.1f}–{t1:.1f}s 共 {t1 - t0:.1f}s 没有任何锚点触发的变化（这段在说：{said}…）')
# 数字核对
if a.params:
    num = lambda s: {n.replace(',', '') for n in re.findall(r'\d+(?:[.,]\d+)*', s)}
    known = num(Path(a.params).read_text(encoding='utf-8'))
    seen = {}
    for src, items in (('文字栏', texts), ('字幕', [s['text'] for s in S])):
        for t in items:
            for n in num(t) - known: seen.setdefault((n, src), t.strip()[:30])
    for (n, src), ctx in sorted(seen.items(), key=lambda kv: float(kv[0][0]) if kv[0][0].replace('.', '', 1).isdigit() else 0):
        W.append(f'         {src}里的数字 {n} 在参数口径表里找不到：{ctx}')

lines = [f'预检：{a.page}  时长 {TL["duration"]:.1f}s  锚点 {len(anchors)} 个  切点 {len(cuts)} 个',
         '切点（给 sheet.py --cuts）：' + ','.join(f'{c["cut"]:.2f}' for c in sorted(cuts, key=lambda c: c['cut'])),
         f'错误 {len(E)} 条，提醒 {len(W)} 条', '', '== 错误（必须改）=='] + (E or ['（无）']) + ['', '== 提醒（逐条看）=='] + (W or ['（无）'])
if errs: lines += ['', '== 页面报错 =='] + errs[:10]
out = '\n'.join(lines); print(out)
if a.report: Path(a.report).write_text(out, encoding='utf-8')
sys.exit(1 if E else 0)
