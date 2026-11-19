"""What the scripts of this skill share: where the skill keeps its own things on this machine, and where the tools it needs are.

The skill's own things live in one folder, ~/.cache/auto-demo-recording unless AUTO_DEMO_HOME names another:

    venv/            the Python that records, draws and checks (demo_env.py setup makes it)
    models/          whisper-large-v3 and campplus_zh.onnx for checking; the two speech models, if they were put here
    tts-venv/        a Python with the speech model's packages, if one was made here
    settings.json    where things are on this machine when they are somewhere else

Each thing is looked for in this order: its environment variable, settings.json, the folder above, the usual
download places. The first that exists is taken.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

HOME = Path(os.environ.get('AUTO_DEMO_HOME') or Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'auto-demo-recording').expanduser()
BIN = 'Scripts' if os.name == 'nt' else 'bin'
HUB = Path(os.environ.get('HF_HUB_CACHE') or Path(os.environ.get('HF_HOME') or Path.home() / '.cache/huggingface') / 'hub').expanduser()
SPEECH = 'Qwen3-TTS-12Hz-1.7B'   # the local speech model this skill reads the captions with: its CustomVoice and its Base variant

# name: (environment variable, what the path must contain to count, where it is by default)
THINGS = {
    'python': ('DEMO_PYTHON', None, lambda: [HOME / 'venv' / BIN / 'python']),
    'chromium': ('DEMO_CHROMIUM', None, lambda: []),
    'tts_python': ('QWEN_TTS_PYTHON', None, lambda: [HOME / 'tts-venv' / BIN / 'python']),
    'tts_custom': ('QWEN_TTS_CUSTOM', 'model.safetensors', lambda: [HOME / 'models' / f'{SPEECH}-CustomVoice', *sorted(HUB.glob(f'models--Qwen--{SPEECH}-CustomVoice/snapshots/*'))]),
    'tts_base': ('QWEN_TTS_BASE', 'model.safetensors', lambda: [HOME / 'models' / f'{SPEECH}-Base', *sorted(HUB.glob(f'models--Qwen--{SPEECH}-Base/snapshots/*'))]),
    'whisper': ('DEMO_WHISPER', 'model.bin', lambda: [HOME / 'models/whisper-large-v3', *sorted(HUB.glob('models--Systran--faster-whisper-large-v3/snapshots/*'))]),
    'voiceprint': ('DEMO_VOICEPRINT', None, lambda: [HOME / 'models/campplus_zh.onnx']),
}


def settings():
    try:
        return json.loads((HOME / 'settings.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def remember(**values):
    """Write down where things are on this machine; an empty value forgets one."""
    kept = {**settings(), **values}
    kept = {key: value for key, value in kept.items() if value}
    HOME.mkdir(parents=True, exist_ok=True)
    (HOME / 'settings.json').write_text(json.dumps(kept, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return kept


def where(name):
    """Where one of THINGS is on this machine, or None."""
    variable, inside, usual = THINGS[name]
    named = [os.environ.get(variable), settings().get(name)]
    for path in [Path(value).expanduser() for value in named if value] + usual():
        if (path / inside).is_file() if inside else path.exists():
            return path
    return None


def need(name, how):
    """Where it is, or stop and say how to get it."""
    path = where(name)
    if not path:
        raise SystemExit(f'缺 {name}：{how}')
    return path


# ---------- how a caption is said ----------
# The recorder gives a caption as much time as saying it takes, and the narration says it by the same rules.
DIGITS = '零一二三四五六七八九'
HAN = chr(0x4E00) + '-' + chr(0x9FFF)   # the Chinese characters, for use inside [...] of a pattern
COUNTED = '个|项|份|件|场|种|边|条|次|位|名|张|页|行|段|步|类|组|天|分钟|小时|秒|周|倍|处|遍|封|台|套|家|层|块|篇|本|句|批|轮|栏|列|人|户|笔|万|亿|千|百'
AMOUNT = re.compile(r'\s*(?:多|余|来)?(?:' + COUNTED + '|元|字|章|节|岁|米|度|帧|例|起|门|所|间|辆|道|题|单|票|分|年|月|日|号|像素|毫秒|公里|千克|公斤|毫米|厘米|GB|MB|KB|TB|ms|px|fps|Hz|kg|km|cm|mm)')
PAUSES = '，。；：、！？,.;:!?'


def cardinal(n, first=True):
    """A whole number read as an amount: 十二, 一百零五, 一千二百, 三万零五十."""
    if n < 10 ** 4:
        out, gap = '', False
        for power, unit in ((3, '千'), (2, '百'), (1, '十'), (0, '')):
            digit = n // 10 ** power % 10
            if digit:
                out += ('零' if gap else '') + ('' if (power, digit) == (1, 1) and first and not out else DIGITS[digit]) + unit
            gap = bool(out) and not digit
        return out or DIGITS[0]
    power, unit = (8, '亿') if n >= 10 ** 8 else (4, '万')
    head, rest = divmod(n, 10 ** power)
    return cardinal(head, first) + unit + (('零' if rest < 10 ** (power - 1) else '') + cardinal(rest, False) if rest else '')


def one_by_one(digits):
    return ''.join(DIGITS[int(digit)] for digit in digits)


def spoken(text, say=None):
    """A caption the way it is said in Mandarin: numbers as words, letter names apart.

    `say` gives the reading of whatever these rules get wrong, e.g. {'WPS 365': 'W P S 三六五'}: its keys are found
    whatever their case and with or without the blanks. The rules: a date, a year (digit by digit), a per cent,
    a range, a decimal, 2 before a counting word (两), a whole number (below a hundred or before a unit as an
    amount, else digit by digit), a short word in capitals (letter by letter).
    """
    for key, value in sorted((say or {}).items(), key=lambda item: -len(item[0])):
        text = re.sub(r'\s*'.join(re.escape(part) for part in key.split()), lambda match: value, text, flags=re.IGNORECASE)
    amount = lambda number: cardinal(int(number.split('.')[0])) + ''.join('点' + one_by_one(part) for part in number.split('.')[1:])
    text = re.sub(r'(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)', lambda m: f'{one_by_one(m[1])}年{cardinal(int(m[2]))}月{cardinal(int(m[3]))}日', text)
    text = re.sub(r'(?<!\d)(\d{4})\s*年', lambda m: one_by_one(m[1]) + '年', text)
    text = re.sub(r'(\d+(?:\.\d+)?)\s*[%％]', lambda m: '百分之' + amount(m[1]), text)
    text = re.sub(r'(?<![\d.-])(\d{1,3})\s*[-~～—–]\s*(\d{1,3})(?![\d.-])', lambda m: f'{m[1]}到{m[2]}', text)
    text = re.sub(r'\d+(?:\.\d+)+', lambda m: amount(m[0]), text)
    text = re.sub(r'(?<![\d.第])(?<!第\s)2(?![\d.])\s*(?=' + COUNTED + ')', '两', text)
    text = re.sub(r'\d+', lambda m: one_by_one(m[0]) if (m[0][0] == '0' and len(m[0]) > 1) or (len(m[0]) > 2 and not AMOUNT.match(m.string, m.end())) else cardinal(int(m[0])), text)
    text = re.sub(r'(?<![A-Za-z])[A-Z]{2,5}(?![A-Za-z])', lambda m: ' '.join(m[0]), text)
    text = re.sub(r'(?<=[' + HAN + r'，。；：、”])\s+(?=[' + HAN + r'“])', '', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


def syllables(text):
    """How many syllables saying a text takes: one for each Chinese character, one for each letter said by its name, two for another word."""
    return len(re.findall('[' + HAN + ']', text)) + sum(len(word) if word.isupper() else 2 for word in re.findall(r'[A-Za-z]+', text))
