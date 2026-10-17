"""逐帧渲染成片页：分块、并行；可出低清预览；改动后只重渲变了的块。
用法：
  整片：  uv run --with playwright==1.63.0 --with pillow python render.py --root 根 --page 成片页 --dir 输出目录 [--workers 4] [--fps 30]
  预览：  ... --dir preview --preview            （每秒 10 帧、截图缩小一半；排版和高清完全一致）
  局部：  ... --dir 输出目录 --only 76-80,229.5-235 （只重渲与这些秒数相交的块，再拼回）
  变了哪：... --dir preview --preview --diff     （重渲预览后与上一版逐帧比较，打印变了的秒数，可直接喂给 --only）
输出（输出目录里）：
  chunks/c0000.mp4 …   每块 --chunk 秒（默认 10 秒），每块单独编码、以关键帧开头，所以能无损拼接、单独替换
  hashes.json          每帧截图的指纹，用来比较两版哪里变了
  out.mp4              全部块无损拼接（不重新编码）
原理：页面是 window.render(t) 的纯函数，同一个 t 永远画出同一帧，所以分块、并行、单独重渲都不会和整片渲染不一致。
"""
import argparse, hashlib, io, json, math, multiprocessing as mp, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

def fingerprint(png):
    """帧指纹：缩成 160×90 灰度、每 16 级量化一次再取 md5。抗锯齿造成的单个像素差 1 级（同一帧两次渲染偶尔会有）不会改变指纹，
    看得见的变化（文字、零件、镜头）一定会改变。"""
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert('L').resize((160, 90), Image.BOX)
    return hashlib.md5(bytes(v >> 4 for v in im.tobytes())).hexdigest()[:12]

def worker(wid, port, page, scale, fps, chunk, nframes, cdir, q, res, boot):
    from playwright.sync_api import sync_playwright
    from common import open_page
    with sync_playwright() as p:
        with boot:                                    # 浏览器一个一个启动：同时启动 4 个、每个加载 9 张物件图会互相拖到超时
            b, pg, errs = open_page(p, port, page, scale)
        while True:
            k = q.get()
            if k is None: break
            f0, f1 = k * chunk * fps, min(nframes, (k + 1) * chunk * fps)
            tmp = cdir / f'c{k:04d}.part.mp4'
            ff = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'image2pipe', '-framerate', str(fps), '-c:v', 'png', '-i', '-',
                                   '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', '-r', str(fps), str(tmp)], stdin=subprocess.PIPE)
            hs = {}
            for i in range(f0, f1):
                pg.evaluate('t => window.render(t)', i / fps)
                png = pg.screenshot(type='png'); hs[i] = fingerprint(png); ff.stdin.write(png)
            ff.stdin.close(); ff.wait()
            if ff.returncode != 0: res.put(('fail', k, f'ffmpeg 退出码 {ff.returncode}')); continue
            n = int(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', str(tmp)],
                                   capture_output=True, text=True).stdout.strip() or 0)
            if n != f1 - f0: res.put(('fail', k, f'帧数 {n}，应为 {f1 - f0}')); continue
            tmp.replace(cdir / f'c{k:04d}.mp4'); res.put(('ok', k, hs))
        b.close()
        if errs: res.put(('errs', wid, errs[:5]))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True); ap.add_argument('--page', required=True); ap.add_argument('--dir', required=True)
    ap.add_argument('--fps', type=int); ap.add_argument('--workers', type=int, default=4); ap.add_argument('--chunk', type=int, default=10)
    ap.add_argument('--preview', action='store_true'); ap.add_argument('--only'); ap.add_argument('--diff', action='store_true')
    a = ap.parse_args()
    from common import serve
    fps = a.fps or (10 if a.preview else 30); scale = 0.5 if a.preview else 1.0
    out = Path(a.dir); cdir = out / 'chunks'; cdir.mkdir(parents=True, exist_ok=True)
    man_p, hash_p = out / 'manifest.json', out / 'hashes.json'
    srv, port = serve(a.root)
    from playwright.sync_api import sync_playwright
    from common import open_page
    with sync_playwright() as p:                    # 先问总时长
        b, pg, _ = open_page(p, port, a.page, scale); total = pg.evaluate('window.__total'); b.close()
    nframes = round(total * fps); nchunks = math.ceil(nframes / (a.chunk * fps))
    man = json.loads(man_p.read_text()) if man_p.exists() else None
    if man and (man['fps'], man['scale'], man['chunk']) != (fps, scale, a.chunk):
        sys.exit(f'{out} 里是 fps={man["fps"]} scale={man["scale"]} chunk={man["chunk"]} 的块，参数不同不能混拼；换个目录')
    old = {int(k): v for k, v in json.loads(hash_p.read_text()).items()} if hash_p.exists() else {}
    if a.only:
        want = set()
        for r in a.only.split(','):
            t0, t1 = (float(x) for x in r.split('-'))
            want |= set(range(max(0, int(t0 // a.chunk)), min(nchunks, int(t1 // a.chunk) + 1)))
        todo = sorted(want)
    else:
        todo = list(range(nchunks))
    for k in range(nchunks, 10 ** 4):                # 时长变短时，删掉多出来的旧块
        f = cdir / f'c{k:04d}.mp4'
        if not f.exists(): break
        f.unlink()
    print(f'{"预览" if a.preview else "高清"} {fps} 帧/秒，共 {nframes} 帧 {nchunks} 块；本次渲染 {len(todo)} 块，{a.workers} 路并行', flush=True)
    t0 = time.time(); q, res, boot = mp.Queue(), mp.Queue(), mp.Lock()
    for k in todo: q.put(k)
    nw = max(1, min(a.workers, len(todo)))
    for _ in range(nw): q.put(None)
    ps = [mp.Process(target=worker, args=(w, port, a.page, scale, fps, a.chunk, nframes, cdir, q, res, boot)) for w in range(nw)]
    for x in ps: x.start()
    new, fails, done = {}, [], 0
    import queue
    while done < len(todo):
        try: kind, k, v = res.get(timeout=30)
        except queue.Empty:
            if not any(x.is_alive() for x in ps): sys.exit(f'所有渲染进程都退出了，还差 {len(todo) - done} 块没完成')
            continue
        if kind == 'ok': new.update(v); done += 1; print(f'  块 {k} 完成（{done}/{len(todo)}，{time.time() - t0:.0f}s）', flush=True)
        elif kind == 'fail': fails.append((k, v)); done += 1; print(f'  块 {k} 失败：{v}', flush=True)
        else: print(f'  页面报错（第 {k} 路）：{v}', flush=True)
    for x in ps: x.join()
    srv.shutdown()
    if fails:                                         # 失败的块单路重跑一次
        print('重跑失败的块：', [k for k, _ in fails]); sys.exit(subprocess.call([sys.executable, __file__, '--root', a.root, '--page', a.page, '--dir', a.dir,
              '--workers', '1', '--chunk', str(a.chunk), '--fps', str(fps), '--only', ','.join(f'{k * a.chunk}-{k * a.chunk + 0.01}' for k, _ in fails)] + (['--preview'] if a.preview else [])))
    merged = {**old, **new}; merged = {k: v for k, v in merged.items() if k < nframes}
    if a.diff and old:
        ch = sorted(i for i in range(nframes) if old.get(i) != merged.get(i))
        rng, s = [], None
        for i, j in zip(ch, ch[1:] + [None]):
            s = i if s is None else s
            if j is None or j - i > 1: rng.append((s / fps, (i + 1) / fps)); s = None
        print('与上一版相比变了的区间：', ','.join(f'{x:.1f}-{y:.1f}' for x, y in rng) if rng else '（没有变化）')
    hash_p.write_text(json.dumps(merged)); man_p.write_text(json.dumps({'fps': fps, 'scale': scale, 'chunk': a.chunk, 'frames': nframes, 'page': a.page}))
    lst = out / 'chunks.txt'; lst.write_text(''.join(f"file 'chunks/c{k:04d}.mp4'\n" for k in range(nchunks)))
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(out / 'out.mp4')], check=True)
    n = int(subprocess.run(['ffprobe', '-v', 'error', '-count_packets', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_packets', '-of', 'csv=p=0', str(out / 'out.mp4')],
                           capture_output=True, text=True).stdout.strip())
    print(f'拼接完成 {out / "out.mp4"}：{n} 帧（应为 {nframes}）{"" if n == nframes else "  ← 帧数不对！"}；用时 {time.time() - t0:.0f}s')
    sys.exit(0 if n == nframes else 1)

if __name__ == '__main__':
    main()
