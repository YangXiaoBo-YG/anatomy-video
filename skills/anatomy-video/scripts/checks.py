"""检查合一：一次跑完，出一份报告。低清预览上先跑，全过才渲高清；高清出来后再跑一遍作为最后防线。
用法：uv run --with playwright==1.63.0 --with numpy --with pillow python checks.py --root 根 --page 成片页 --video 预览或成片.mp4 [--report 报告.txt]
两部分：
  页面检查（DOM，不截图，每 0.1 秒一次，切点前后 ±1 秒加密到每秒 30 帧）：
    文字叠文字（文字栏各行之间、文字栏与字幕）；文字压到物件（在物件页里取点，看文字底下是不是实心体或线）；
    标题孤字折行（最后一行只剩一两个字）；字幕某一行只有一两个字；文字栏字号小于 22px（手机上看不清）；
    物件内部的半透明（Anatomy 不允许实心体半透明；场景之间的叠化不算）
  无状态检查（截图，每 0.25 秒一次）：整片按顺序画一遍、按打乱的顺序再画一遍，同一时刻画面必须一样（分块并行渲染的前提）
  视频检查（像素）：
    出框（内容压进四周 3% 安全边距，底部字幕区不算）；静止段（画面连续 3 秒以上几乎不变）
退出码：有错误为 1。提醒逐条看，不一定要改。
"""
import argparse, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

PAGE_PROBE = r'''() => {
  const out = { overlap: [], onFig: [], orphan: [], subOrphan: [], small: [], alpha: [] };
  const vis = (el) => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) o *= +getComputedStyle(e).opacity; return o; };
  const items = [...document.querySelectorAll('.it')].filter((e) => vis(e) > 0.5);
  // 每一行文字拆成文字节点：记下每段的矩形和它自己的字号（大数字配小单位、标题前的装饰短线都不会被误判）
  const textRects = (e) => { const out = [], w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) { if (!n.textContent.trim()) continue; const fs = parseFloat(getComputedStyle(n.parentElement).fontSize);
      const rg = document.createRange(); rg.selectNodeContents(n); for (const q of rg.getClientRects()) if (q.width > 0) out.push({ q, fs }); }
    return out; };
  const R = items.map((e) => { const r = e.getBoundingClientRect(), tr = textRects(e); return { e, r, tr, text: e.textContent.trim().slice(0, 16), fs: Math.min(...tr.map((x) => x.fs), 99) }; });
  const subs = document.querySelector('#subs'); const sr = subs && subs.textContent.trim() ? subs.getBoundingClientRect() : null;
  const inter = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  for (let i = 0; i < R.length; i++) {
    for (let j = i + 1; j < R.length; j++) if (inter(R[i].r, R[j].r) > 20) out.overlap.push(R[i].text + ' ⟷ ' + R[j].text);
    if (sr && inter(R[i].r, sr) > 20) out.overlap.push(R[i].text + ' ⟷ 字幕');
    if (R[i].fs < 22) out.small.push(R[i].text + ' ' + R[i].fs + 'px');
    // 孤字折行：按竖直方向是否重叠把文字矩形归成行，最后一行宽度不到 2.2 个字（按该行最大字号）就报
    const lines = []; for (const x of [...R[i].tr].sort((a, b) => a.q.top - b.q.top)) { const c = (x.q.top + x.q.bottom) / 2, ln = lines[lines.length - 1];
      if (ln && c > ln.top && c < ln.bottom) { ln.left = Math.min(ln.left, x.q.left); ln.right = Math.max(ln.right, x.q.right); ln.bottom = Math.max(ln.bottom, x.q.bottom); ln.fs = Math.max(ln.fs, x.fs); }
      else lines.push({ top: x.q.top, bottom: x.q.bottom, left: x.q.left, right: x.q.right, fs: x.fs }); }
    if (lines.length > 1) { const ln = lines[lines.length - 1], w = ln.right - ln.left; if (w < 2.2 * ln.fs) out.orphan.push(R[i].text + `（第 ${lines.length} 行只有约 ${Math.max(1, Math.round(w / ln.fs))} 个字宽）`); }
  }
  if (sr) for (const line of subs.innerText.split('\n')) if (line.trim() && line.trim().length <= 2) out.subOrphan.push(subs.innerText.replace('\n', ' / ').slice(0, 30));
  // 文字压物件：在每张可见物件页里，取文字矩形内 4×3 个点，看点下面是不是物件的实心体或线
  const figs = [...document.querySelectorAll('iframe')].filter((f) => vis(f) > 0.5);
  for (const f of figs) {
    const fr = f.getBoundingClientRect(), sc = fr.width / f.clientWidth, d = f.contentDocument; if (!d) continue;
    for (const x of R) {
      let hit = 0;
      for (let u = 0; u < 4; u++) for (let v = 0; v < 3; v++) {
        const px = x.r.left + x.r.width * (u + .5) / 4, py = x.r.top + x.r.height * (v + .5) / 3;
        const el = d.elementFromPoint((px - fr.left) / sc, (py - fr.top) / sc);
        if (el && el.closest && el.closest('.iso-solid, .iso-line, [class*="iso-"] path, polygon')) hit++;
      }
      if (hit >= 2) out.onFig.push(x.text + ' 压在 ' + f.src.split('/').pop().replace('-light.html', '') + ` 上（${hit}/12 点）`);
    }
    if (vis(f) > 0.99) for (const el of d.querySelectorAll('[style*="opacity"]')) {
      const o = +el.style.opacity; if (o > 0.05 && o < 0.95 && (el.matches('.iso-solid, g') && el.querySelector && el.querySelector('.iso-solid') || el.matches('.iso-solid')))
        out.alpha.push(f.src.split('/').pop().replace('-light.html', '') + ' ' + (el.getAttribute('data-name') || el.tagName) + ' 透明度 ' + o.toFixed(2));
    }
  }
  return out;
}'''

def page_checks(a):
    from playwright.sync_api import sync_playwright
    from common import serve, open_page
    srv, port = serve(a.root); found = {}
    with sync_playwright() as p:
        b, pg, errs = open_page(p, port, a.page)
        total = pg.evaluate('window.__total'); pg.evaluate('() => { window.render(0) }')
        cuts = pg.evaluate('[...(window.__cuts || new Map()).values()].map(c => c.cut)')
        ts = {round(i / 10, 3) for i in range(int(total * 10) + 1)}
        for c in cuts: ts |= {round(c + k / 30, 3) for k in range(-30, 31)}
        for t in sorted(ts):
            if t < 0 or t > total: continue
            pg.evaluate('t => window.render(t)', t)
            for kind, items in pg.evaluate(PAGE_PROBE).items():
                for it in items: found.setdefault((kind, it), []).append(t)
        b.close()
    srv.shutdown(); return found, errs

def state_checks(a, step=0.25, seed=7):
    """无状态检查（CLAUDE.md：帧和帧之间不保存状态）：整片按时间顺序画一遍；再开一个全新页面，按打乱的顺序画一遍。
    打乱后每张物件图“上一次被画成什么样”是随机的；某个镜头没有完整重设姿态，同一时刻两遍的画面就对不上。
    这是分块并行渲染的前提（每一块的“上一次”也是随机的）。比较用 160×90 灰度缩略图，抗锯齿的细微差别不算。"""
    import io, random
    from PIL import Image
    from playwright.sync_api import sync_playwright
    from common import serve, open_page
    srv, port = serve(a.root)
    thumb = lambda png: Image.open(io.BytesIO(png)).convert('L').resize((160, 90), Image.BOX).tobytes()
    differ = lambda x, y: sum(abs(p - q) > 12 for p, q in zip(x, y)) > 3
    def run(order):
        with sync_playwright() as p:
            b, pg, _ = open_page(p, port, a.page, 0.5); out = {}
            for t in order: pg.evaluate('t => window.render(t)', t); out[t] = thumb(pg.screenshot(type='png'))
            b.close(); return out
    with sync_playwright() as p:
        b, pg, _ = open_page(p, port, a.page, 0.5); total = pg.evaluate('window.__total'); b.close()
    ts = [round(k * step, 3) for k in range(int(total / step) + 1)]
    sh = ts[:]; random.Random(seed).shuffle(sh)
    A, B = run(ts), run(sh)
    srv.shutdown(); return [t for t in ts if differ(A[t], B[t])]

def spans(times, gap=0.12):
    out = []
    for t in sorted(times):
        if out and t - out[-1][1] <= gap: out[-1][1] = t
        else: out.append([t, t])
    return out

def video_checks(path, margin=0.03, ignore_bottom=0.14):
    import numpy as np
    w, h, fps = 480, 270, 10
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={fps},scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    F = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.int16)
    mx, my, bottom = int(w * margin), int(h * margin), int(h * (1 - ignore_bottom))
    edge = []
    for i, f in enumerate(F):
        bg = np.median(np.stack([f[0, 0], f[0, -1], f[-1, 0], f[-1, -1]]), axis=0)
        c = np.abs(f - bg).max(axis=2) > 18; c[bottom:] = False
        ys, xs = np.nonzero(c)
        if not len(xs): continue
        s = [n for n, bad in (('左', xs.min() < mx), ('右', xs.max() >= w - mx), ('上', ys.min() < my)) if bad]
        if s: edge.append((i / fps, s))
    g = F[:, :bottom].mean(axis=3)
    d = np.r_[1.0, np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))]
    still, run = [], None
    for i, v in enumerate(d):
        if v < 0.05 and run is None: run = i
        if (v >= 0.05 or i == len(d) - 1) and run is not None:
            if (i - run) / fps >= 3.0: still.append((run / fps, (i - run) / fps))
            run = None
    return edge, still, len(F) / fps

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root'); ap.add_argument('--page'); ap.add_argument('--video'); ap.add_argument('--report')
    ap.add_argument('--still', type=float, default=4.0, help='静止超过这么多秒算错误（CLAUDE.md：每 2–4 秒要有新东西）')
    a = ap.parse_args()
    E, W, L = [], [], []
    if a.page:
        found, errs = page_checks(a)
        names = {'overlap': ('文字叠在一起', E), 'onFig': ('文字压到物件', E), 'orphan': ('标题孤字折行', E), 'subOrphan': ('字幕孤字成行', W),
                 'small': ('文字栏字号偏小', W), 'alpha': ('物件内部半透明', W)}
        for (kind, it), ts in sorted(found.items(), key=lambda kv: kv[1][0]):
            label, bucket = names[kind]
            for t0, t1 in spans(ts):
                if kind == 'alpha' and t1 - t0 < 0.4: continue          # 一闪而过的淡入不算
                bucket.append(f'{t0:7.2f}s–{t1:.2f}s  {label}：{it}')
        if errs: W += ['页面报错：' + e for e in errs[:5]]
        for t0, t1 in spans(state_checks(a), gap=0.26):
            E.append(f'{t0:7.2f}s–{t1:.2f}s  画面依赖前一帧（有状态）：顺序画和打乱顺序画结果不一样；检查这段镜头的 pose 是否完整重设')
        L.append(f'页面检查：{a.page}')
    if a.video:
        edge, still, dur = video_checks(a.video)
        for t0, t1 in spans([t for t, _ in edge], gap=0.11):
            sides = sorted({x for t, s in edge if t0 <= t <= t1 for x in s})
            E.append(f'{t0:7.2f}s–{t1:.2f}s  出框：压到{"、".join(sides)}')
        for t0, d in still:
            (E if d > a.still else W).append(f'{t0:7.2f}s–{t0 + d:.2f}s  画面静止 {d:.1f}s')
        L.append(f'视频检查：{a.video}（{dur:.1f}s）')
    E.sort(); W.sort()
    out = '\n'.join(L + [f'错误 {len(E)} 条，提醒 {len(W)} 条', '', '== 错误（必须改）=='] + (E or ['（无）']) + ['', '== 提醒（逐条看）=='] + (W or ['（无）']))
    print(out)
    if a.report: Path(a.report).write_text(out, encoding='utf-8')
    sys.exit(1 if E else 0)

if __name__ == '__main__':
    main()
