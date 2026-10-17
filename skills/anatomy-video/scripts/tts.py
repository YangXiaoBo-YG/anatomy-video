"""整段配音：豆包语音合成 2.0 异步接口（submit → query），同时拿到音频和每个字的起止时间。
用法：python tts.py 稿子.txt 输出前缀 [--speaker zh_male_dayi_uranus_bigtts] [--rate -8]
输出：
  前缀.mp3           配音
  前缀.tts.json      接口原始结果（sentences[].words[]，字级时间和置信度），时间的唯一依据，保留
  前缀.timing.json   贴回稿子每个字的时间（由 tts_timing.py 生成，与 align.py 同格式，make_timeline 直接用）
  前缀.readings.txt  稿子写法 → 引擎实际念的字：数字、型号、单位的读法在这里核对
为什么不用流式接口：流式接口的 sentence.words 返回为空；异步接口才有字级时间（2026-10-15 实测）。
为什么不再用语音识别对齐：H100 一集实测，引擎时间与识别对齐中位差 0.03 秒；差得大的地方（GPC、NVLink 等英文缩写）
  对照音频静音位置核实，都是识别错了。
密钥只从用户环境变量 VOLC_API_KEY 读，不打印、不写文件。
"""
import argparse, json, subprocess, sys, time, uuid, os
from pathlib import Path
import requests
ap = argparse.ArgumentParser(); ap.add_argument('script'); ap.add_argument('out')
ap.add_argument('--speaker', default='zh_male_dayi_uranus_bigtts'); ap.add_argument('--rate', type=int, default=-8)
ap.add_argument('--resource', default='seed-tts-2.0')
a = ap.parse_args()
def key():
    if os.environ.get('VOLC_API_KEY'): return os.environ['VOLC_API_KEY']
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k: return winreg.QueryValueEx(k, 'VOLC_API_KEY')[0]
KEY = key(); BASE = 'https://openspeech.bytedance.com/api/v3/tts/'
H = lambda: {'X-Api-Key': KEY, 'X-Api-Resource-Id': a.resource, 'X-Api-Request-Id': str(uuid.uuid4()), 'Content-Type': 'application/json'}
text = Path(a.script).read_text(encoding='utf-8')
body = {'user': {'uid': 'anatomy-video'}, 'unique_id': str(uuid.uuid4()),
        'req_params': {'text': text, 'speaker': a.speaker, 'audio_params': {'format': 'mp3', 'sample_rate': 48000, 'speech_rate': a.rate, 'enable_timestamp': True}}}
t0 = time.time()
r = requests.post(BASE + 'submit', headers=H(), json=body, timeout=60).json()
if r.get('code') != 20000000: sys.exit(f'提交失败：{r.get("code")} {r.get("message")}')
task = r['data']['task_id']
while True:
    time.sleep(3)
    d = requests.post(BASE + 'query', headers=H(), json={'task_id': task}, timeout=60).json().get('data') or {}
    if d.get('task_status') != 1: break
    if time.time() - t0 > 900: sys.exit('合成超过 15 分钟，放弃')
if d.get('task_status') != 2 or not d.get('audio_url'): sys.exit(f'合成失败：{d}')
# 下载音频：网络中途断开时重试；下载完核对时长不短于最后一个字的结束时间（防止存下半截文件）
last_end = max(w['endTime'] for s in d['sentences'] for w in s['words'])
for k in range(6):
    try:
        r = requests.get(d['audio_url'], timeout=300); r.raise_for_status()
        Path(a.out + '.mp3').write_bytes(r.content)
        got = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', a.out + '.mp3'],
                                   capture_output=True, text=True).stdout or 0)
        if got >= last_end - 0.05: break
        print(f'音频只有 {got:.1f}s，应不短于 {last_end:.1f}s，重新下载')
    except requests.RequestException as e:
        print(f'下载中断（第 {k + 1} 次）：{type(e).__name__}，5 秒后重试')
    time.sleep(5)
else:
    sys.exit('音频下载 6 次都没成功；任务结果 30 分钟内有效，可稍后重跑')
Path(a.out + '.tts.json').write_text(json.dumps({k: v for k, v in d.items() if k != 'audio_url'}, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'合成完成 {time.time() - t0:.0f} 秒，{len(d["sentences"])} 句')
subprocess.run([sys.executable, str(Path(__file__).with_name('tts_timing.py')), a.out + '.tts.json', a.script, a.out], check=True)
