"""读音表的读取：terms.py 和 make_timeline.py 共用。"""
import re
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / 'references' / '读音表.md'

def load(path=None):
    rows = []
    for line in Path(path or DEFAULT).read_text(encoding='utf-8').splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 6 or cells[0] in ('稿子写法', '') or set(cells[0]) <= set('-'): continue
        rows.append({'write': cells[0], 'show': cells[1], 'tight': cells[2] == '是', 'state': cells[3], 'engine': cells[4], 'note': cells[5]})
    return rows

def token_re(word):
    """整词匹配：前面不能紧挨字母、后面不能紧挨字母或数字。192GB 里的 GB 算单位（会被查出），GB200 里的 GB 不算。"""
    return re.compile(r'(?<![A-Za-z])' + re.escape(word) + r'(?![A-Za-z0-9])')

def to_display(text, rows):
    """读法 → 字幕写法（吉字节 → GB），长的先换。"""
    for r in sorted((r for r in rows if r['show'] and r['show'] != r['write'] and r['state'] != '禁用'), key=lambda r: -len(r['write'])):
        text = re.sub((r'\s?' if r['tight'] else '') + re.escape(r['write']), r['show'], text)
    return text
