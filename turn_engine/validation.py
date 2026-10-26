"""LoRA-A 출력(ActionExtraction)의 의미 검증 안전망(D75, I8 v2). 순수 함수. I/O·시간·난수 없음.

형식(스키마)은 model-runtime이 검증한다. 여기서는 스키마로 표현할 수 없는 규칙을 본다.
위반이 있으면 호출자(survey-service)는 `OUTPUT_INVALID`와 같게 처리한다(값을 지어내지 않는다).
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import NamedTuple

from boundary_contracts import validator

from ._common import ContractViolation
from .flow import QuestionFlowTable

SAVED_STATUSES = ("ANSWERED", "CORRECTION")
NULL_STATUSES = ("MISSING", "UNCLEAR", "UNKNOWN", "REJECTED")
FOLLOW_ACTIONS = ("NEXT", "CORRECT", "HOLD", "SKIP")

CODES = ("OUTPUT_SCHEMA", "TARGET_NOT_IN_VALUES", "NEXT_ITEM_MISMATCH", "SKIP_ORDER_MISMATCH", "SAVE_RULE", "UNKNOWN_ITEM")


class Violation(NamedTuple):
    code: str
    path: str
    message: str  # 입력·출력의 값을 싣지 않는다(개인정보)


@lru_cache(maxsize=None)
def _v(name):
    return validator(name)


def _path(err) -> str:
    return "/".join(str(p) for p in err.absolute_path) or "(root)"


def item_of(key: str) -> str:
    """모델 키(`Q7[soju].amount`, `Q4_1.status`)의 문항 ID."""
    return key.rsplit(".", 1)[0].split("[")[0]


def _slot_of(key: str) -> str:
    return re.sub(r"\[[^\]]*\]", "", key)


def validate_extraction(input: dict, output: dict, flow: QuestionFlowTable) -> list[Violation]:
    """입력이 `ActionExtractionInput`을 어기면 ContractViolation. 출력의 위반은 목록으로 돌려준다(없으면 빈 목록)."""
    errs = sorted(_v("ActionExtractionInput").iter_errors(input), key=_path)
    if errs:
        raise ContractViolation("ActionExtractionInput", [f"{_path(e)}: {e.validator}" for e in errs])
    out: list[Violation] = []
    values = output.get("values") if isinstance(output, dict) else None
    if not isinstance(values, list) or not all(isinstance(v, dict) for v in values) or not isinstance(output.get("action"), str):
        return [Violation("OUTPUT_SCHEMA", "(root)", "출력 구조가 ActionExtraction이 아니다")]

    # 저장 규칙은 아래에서 따로 본다. 같은 칸의 스키마 오류는 겹치므로 거르고 나머지 형식 오류만 낸다.
    for e in sorted(_v("ActionExtraction").iter_errors(output), key=_path):
        p = list(e.absolute_path)
        if len(p) == 3 and p[0] == "values" and p[2] in ("save", "value", "precision"):
            continue
        out.append(Violation("OUTPUT_SCHEMA", _path(e), f"{e.validator}"))

    keys = []
    for i, v in enumerate(values):
        k, st = v.get("key"), v.get("status")
        keys.append(k if isinstance(k, str) else "")
        want_save = st in SAVED_STATUSES
        if v.get("save") is not want_save:
            out.append(Violation("SAVE_RULE", f"values/{i}/save", "save는 status가 ANSWERED 또는 CORRECTION일 때만 true"))
        if st in NULL_STATUSES and v.get("value") is not None:
            out.append(Violation("SAVE_RULE", f"values/{i}/value", "status가 MISSING·UNCLEAR·UNKNOWN·REJECTED이면 value는 null"))
        if want_save and v.get("value") is None:
            out.append(Violation("SAVE_RULE", f"values/{i}/value", "저장하는 값(ANSWERED·CORRECTION)은 null일 수 없다"))

    keyset = set(keys)
    targets = output.get("targets") or []
    if not isinstance(targets, list):
        targets = []
    for i, t in enumerate(targets):
        if t not in keyset:
            out.append(Violation("TARGET_NOT_IN_VALUES", f"targets/{i}", "targets 항목이 values의 key에 없다"))

    action, nxt, qid = output["action"], output.get("next_item"), input["question_id"]
    if not isinstance(nxt, str):
        return out
    all_keys = [k for k in keys if k] + [t for t in targets if isinstance(t, str)]
    unknown = sorted({item_of(k) for k in all_keys if flow.index(item_of(k)) is None} | ({qid} if flow.index(qid) is None else set()))
    if unknown:
        out.append(Violation("UNKNOWN_ITEM", "values", f"문항 순서 표에 없는 문항 {len(unknown)}개"))
        return out
    if nxt != "END" and flow.index(nxt) is None:
        out.append(Violation("UNKNOWN_ITEM", "next_item", "next_item이 문항 순서 표에 없다"))
        return out

    if action in ("REASK", "REDIRECT"):
        if nxt != qid:
            out.append(Violation("NEXT_ITEM_MISMATCH", "next_item", f"{action}의 next_item은 입력 question_id와 같아야 한다"))
    elif action == "CONFIRM":
        if nxt not in {item_of(t) for t in targets if isinstance(t, str)}:
            out.append(Violation("NEXT_ITEM_MISMATCH", "next_item", "CONFIRM의 next_item은 targets 칸의 문항이어야 한다"))
    elif action in FOLLOW_ACTIONS:
        saved = {_slot_of(k): v.get("value") for k, v in zip(keys, values) if v.get("save") is True and k}
        # 같은 말에서 가장 뒤 문항의 값이 기준이다.
        base = max((item_of(k) for k in all_keys), key=flow.order.index) if all_keys else qid
        expected = flow.next_item(base, saved)
        if nxt != expected:
            if nxt in {item_of(k) for k in keys if k}:
                pass  # 같은 말에서 일부 칸이 이미 채워진 문항으로 넘어감: 계약이 허용한다(위반이 아니다)
            else:
                plain = flow.plain_next(base)
                pos = len(flow.order) if nxt == "END" else flow.index(nxt)
                pplain = len(flow.order) if plain == "END" else flow.index(plain)
                code = "SKIP_ORDER_MISMATCH" if pos >= pplain else "NEXT_ITEM_MISMATCH"
                out.append(Violation(code, "next_item", f"{action}의 next_item이 문항 순서·건너뛰기 규칙과 다르다"))
    return out
