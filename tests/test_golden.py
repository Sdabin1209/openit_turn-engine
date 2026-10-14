"""골든(원본 요구사항 케이스의 정적 예시)과 비교한다. 같지 않은 것은 tests/golden_known.json에 분류와 근거를 남긴다."""
import json
import pathlib

import pytest

import turn_engine as te

G = pathlib.Path(__file__).parent / "golden"
FUNC = {"AnswerNormalizerInput": te.normalize, "AnswerJudgeInput": te.judge,
        "RecordWriterInput": te.write_record, "DialoguePlannerInput": te.plan}
OUTC = {"AnswerNormalizerInput": "NormalizerOutput", "AnswerJudgeInput": "JudgeOutput",
        "RecordWriterInput": "StoreResult", "DialoguePlannerInput": "PlannerOutput"}


def pairs():
    for f in sorted(G.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(d, dict) or "specimens" not in d:
            continue
        inv = {v: k for k, v in OUTC.items()}
        by = {}
        for sp in d["specimens"]:
            if sp["role"] == "input":
                by.setdefault((sp["turn"], sp["contract"]), {})["input"] = sp["data"]
            elif sp["role"] == "output":
                by.setdefault((sp["turn"], inv[sp["contract"]]), {})["output"] = sp["data"]
        for (turn, c), v in sorted(by.items()):
            if c in FUNC and "input" in v and "output" in v:
                yield d["case"], turn, c, v["input"], v["output"]


def known():
    p = pathlib.Path(__file__).parent / "golden_known.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def mask(c, out):
    """확인 대기 ID는 새로 만드는 값이라 골든이 자리표시자(X, Y, N1)로 쓴다. 새로 둔 ID만 가린다."""
    if c == "RecordWriterInput":
        out = json.loads(json.dumps(out))
        for d in out["store_decisions"]:
            if d["action"] == "SET_PENDING":
                d["pending_id"] = "<new>"
    return out


ALL = list(pairs())


@pytest.mark.parametrize("case,turn,c,inp,exp", ALL, ids=[f"{a}-t{b}-{c[:6]}" for a, b, c, _, _ in ALL])
def test_golden(case, turn, c, inp, exp):
    key = f"{case}/t{turn}/{c}"
    k = known().get(key)  # [분류, 근거]
    try:
        got = FUNC[c](inp)
    except te.ContractViolation as e:
        assert k, f"{key}: 입력이 계약 위반 {e}"
        return
    got, exp = mask(c, got), mask(c, exp)
    if got == exp:
        assert not k, f"{key}: 이제 같아졌으니 golden_known.json에서 지운다"
        return
    assert k, f"{key}: 골든과 다르고 분류가 없다"


def test_every_known_difference_is_classified():
    ks = known()
    assert ks and all(v[0] in ("b", "c") and v[1] for v in ks.values()), [k for k, v in ks.items() if v[0] not in ("b", "c")]


def test_golden_coverage_is_the_whole_set():
    assert len({a for a, *_ in ALL}) >= 200 and len(ALL) >= 850
