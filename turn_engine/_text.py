"""한국어 텍스트 보조: 숫자 읽기, 어간, 이름 맞추기. 문서(rules/answer_normalizer.md 5절 8)의 기준만 쓴다."""
from __future__ import annotations

import re

_NATIVE_TENS = {"열": 10, "스물": 20, "스무": 20, "서른": 30, "마흔": 40, "쉰": 50, "예순": 60, "일흔": 70, "여든": 80, "아흔": 90}
_NATIVE_ONES = {"하나": 1, "한": 1, "둘": 2, "두": 2, "셋": 3, "세": 3, "석": 3, "넷": 4, "네": 4, "넉": 4,
                "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9}
_RANGE_WORDS = ["두서너", "서너", "서넛", "네다섯", "네댓", "너댓", "대여섯", "예닐곱", "일고여덟", "두세", "세네", "한두"]
_SINO = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}

_TENS_RE = "|".join(sorted(_NATIVE_TENS, key=len, reverse=True))
_ONES_RE = "|".join(sorted(_NATIVE_ONES, key=len, reverse=True))
_RANGE_RE = "|".join(sorted(_RANGE_WORDS, key=len, reverse=True))
_TOKEN = re.compile(
    rf"(?P<range>{_RANGE_RE})|(?P<arabic>\d+(?:\.\d+)?)|(?P<native>(?:{_TENS_RE})(?:{_ONES_RE})?|(?:{_ONES_RE}))"
    rf"|(?P<sino>[일이삼사오육칠팔구]?십[일이삼사오육칠팔구]?|[일이삼사오육칠팔구])"
)
_HANGUL = re.compile(r"[가-힣]")
_APPROX = ("정도", "쯤", "약 ", "대략")


def _sino_value(s: str) -> int:
    if "십" in s:
        a, _, b = s.partition("십")
        return (_SINO[a] if a else 1) * 10 + (_SINO[b] if b else 0)
    return _SINO[s]


def find_numbers(text: str, unit_names: list[str]):
    """숫자 토큰 목록 [(시작, 끝, 값 또는 None(어림 범위어))]. 한글 낱말 속의 글자를 숫자로 읽지 않도록,
    뒤에 한글이 이어지면 단위 이름·어림 표현·다른 숫자가 이어질 때만 숫자로 본다."""
    out = []
    pos = 0
    names = [n for n in unit_names if n]
    idx = [i for i, c in enumerate(text) if not c.isspace()]
    sq = "".join(text[i] for i in idx)
    spans = [(idx[m.start()], idx[m.end() - 1] + 1) for n in names for m in re.finditer(re.escape(squash(n)), sq)]
    while pos < len(text):
        m = _TOKEN.search(text, pos)
        if not m:
            break
        kind = m.lastgroup
        s, e = m.span()
        if kind != "arabic" and any(a <= s and e <= b for a, b in spans):
            pos = e  # 단위 이름 속의 글자('일주일'의 '일')는 숫자가 아니다
            continue
        # 앞이 한글이면(낱말 중간) 숫자가 아니다. 단, 바로 앞 토큰에 이어진 숫자는 허용.
        if kind != "arabic" and s > 0 and _HANGUL.match(text[s - 1]) and not (out and out[-1][1] == s):
            pos = s + 1
            continue
        rest = text[e:]
        ok = kind == "arabic" or (not rest) or (not _HANGUL.match(rest[0])) or rest.startswith(("이요", "요", "이나", "나", "에서", "정도", "쯤", "이", "번", "회", "개", "명"))
        if not ok:
            ok = any(rest.startswith(n) for n in names) or _TOKEN.match(rest) is not None
        if kind == "sino" and not any(rest.lstrip().startswith(n) for n in names):
            ok = False
        if not ok:
            pos = s + 1
            continue
        if kind == "range":
            out.append((s, e, None))
        elif kind == "arabic":
            v = float(m.group())
            out.append((s, e, int(v) if v.is_integer() else v))
        elif kind == "native":
            g = m.group()
            mt = re.match(rf"({_TENS_RE})?({_ONES_RE})?$", g)
            v = (_NATIVE_TENS[mt.group(1)] if mt.group(1) else 0) + (_NATIVE_ONES[mt.group(2)] if mt.group(2) else 0)
            out.append((s, e, v))
        else:
            out.append((s, e, _sino_value(m.group())))
        pos = e
    return out


def is_approximate(text: str) -> bool:
    return any(a in text for a in _APPROX)


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def strip_number_place(name: str) -> str:
    """단위 이름의 수 자리(숫자)와 공백을 뺀 글자."""
    return re.sub(r"[\d\s]+", "", name)


def stem(name: str) -> str | None:
    """선택지 이름의 어간(구현 해석, change-request CR-001): 끝 음절의 받침 ㄴ·ㄹ·ㅁ·ㅂ을 떼고, 끝이 '다'면 '다'를 뗀다.
    이름과 같거나 비면 없음."""
    n = squash(name)
    if len(n) < 2:
        return None
    last = n[-1]
    if "가" <= last <= "힣":
        code = ord(last) - 0xAC00
        jong = code % 28
        if jong in (4, 8, 16, 17):
            n2 = n[:-1] + chr(ord(last) - jong)
        elif last == "다":
            n2 = n[:-1]
        else:
            n2 = n
    else:
        n2 = n
    if n2 == n or not n2:
        return None
    return n2


NEGATION_MARKERS = ("안", "않", "못", "없")


def has_negation(text: str) -> bool:
    return any(m in text for m in NEGATION_MARKERS)
