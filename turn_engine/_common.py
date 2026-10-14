"""공통 도구: 계약 검증, 오류, 슬롯 키, 값 비교. I/O·시간·난수를 쓰지 않는다."""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources

from jsonschema import Draft202012Validator

SUPPORTED_RUNTIME_CONTRACT_VERSION = 1


class ContractViolation(ValueError):
    """입력이 문진 스키마(입력 계약)를 위반했다. 입력 값은 메시지에 담지 않는다."""

    def __init__(self, contract: str, errors: list[str]):
        self.contract = contract
        self.errors = errors
        super().__init__(f"{contract} 계약 위반: " + "; ".join(errors[:5]))


class OutputContractError(RuntimeError):
    """엔진 내부 결함: 만든 출력이 출력 계약을 위반했다(입력 탓이 아니다)."""

    def __init__(self, contract: str, errors: list[str]):
        self.contract = contract
        self.errors = errors
        super().__init__(f"{contract} 출력 계약 위반(엔진 결함): " + "; ".join(errors[:5]))


def _schema_pkg():
    return resources.files("turn_engine") / "_schemas"


def _check_contract_version() -> None:
    text = (_schema_pkg() / "CONTRACT_VERSION").read_text(encoding="utf-8").strip()
    if int(text) != SUPPORTED_RUNTIME_CONTRACT_VERSION:
        raise RuntimeError(
            f"문진 스키마 정수 버전 {text}는 지원하지 않는다(지원: {SUPPORTED_RUNTIME_CONTRACT_VERSION})"
        )


_check_contract_version()


@lru_cache(maxsize=None)
def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((_schema_pkg() / f"{name}.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _errors(name: str, data) -> list[str]:
    out = []
    for e in sorted(_validator(name).iter_errors(data), key=lambda e: [str(p) for p in e.absolute_path]):
        path = "/".join(str(p) for p in e.absolute_path) or "(root)"
        out.append(f"{path}: {e.validator}")  # 값은 싣지 않는다(개인정보)
    return out


def check_input(name: str, data) -> None:
    errs = _errors(name, data)
    if errs:
        raise ContractViolation(name, errs)


def check_output(name: str, data) -> None:
    errs = _errors(name, data)
    if errs:
        raise OutputContractError(name, errs)


# ---------- 슬롯 키와 값 ----------

def skey(ref: dict) -> tuple:
    return (ref["question_id"], ref["repeat_key"], ref["slot_id"])


def ref_of(key: tuple) -> dict:
    return {"question_id": key[0], "repeat_key": key[1], "slot_id": key[2]}


def is_whole(target) -> bool:
    return isinstance(target, dict) and target.get("whole_question") is True


def is_slot(target) -> bool:
    return isinstance(target, dict) and "slot_id" in target


def tkey(target) -> tuple:
    """Target의 비교 키."""
    if is_whole(target):
        return ("W", target["question_id"])
    return ("S",) + skey(target)


def _canon(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, dict):
        return {k: _canon(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_canon(x) for x in v]
    return v


def vkey(value) -> str:
    """값의 비교 키(정규 JSON). 정수로 떨어지는 실수는 정수와 같다."""
    return json.dumps(_canon(value), sort_keys=True, ensure_ascii=False)


def same_value(a, b) -> bool:
    return vkey(a) == vkey(b)


def value_matches_text(value, text: str) -> bool:
    """선행 조건의 값 문자열(text)과 표준 값이 맞는가: 문자열 값은 같음, 코드 값은 code 또는 label 같음."""
    if isinstance(value, str):
        return value == text
    if isinstance(value, dict) and "code" in value:
        return value["code"] == text or value.get("label") == text
    return False


def uniq(seq):
    seen = set()
    out = []
    for x in seq:
        k = json.dumps(x, sort_keys=True, ensure_ascii=False) if not isinstance(x, (str, int, tuple)) else x
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out
