"""validate_extraction(D75, 계약 2.0.0 I8) 시험. 입력은 설명용 예시이며 학습 데이터가 아니다."""
import copy
import json
import os
import pathlib
import subprocess
import sys
import warnings

import pytest

import turn_engine as te
from turn_engine import DATASET_V2_FLOW as FLOW, QuestionFlowTable, SkipRule, Violation, validate_extraction

ROOT = pathlib.Path(__file__).resolve().parent.parent


def inp(qid="Q4", state=None):
    return {"question_id": qid, "current_question": "질문", "user_utterance": "발화", "state": state or {}}


def val(key, value, status="ANSWERED", precision="exact", save=None):
    if save is None:
        save = status in ("ANSWERED", "CORRECTION")
    if status in ("MISSING", "UNCLEAR", "UNKNOWN", "REJECTED"):
        precision = "unspecified"
    return {"key": key, "value": value, "precision": precision, "status": status, "save": save}


def out(values, action, next_item, **kw):
    o = {"values": values, "action": action, "next_item": next_item}
    o.update(kw)
    return o


def codes(i, o, flow=FLOW):
    return [v.code for v in validate_extraction(i, o, flow)]


# 위반 없음

def test_next_follows_order():
    assert validate_extraction(inp("Q3"), out([val("Q3.answer", True)], "NEXT", "Q4"), FLOW) == []


def test_next_applies_skip_rule():
    o = out([val("Q4.answer", False)], "NEXT", "Q5")
    assert validate_extraction(inp("Q4"), o, FLOW) == []


def test_end_after_last_item():
    assert validate_extraction(inp("Q10"), out([val("Q10.answer", "없음")], "NEXT", "END"), FLOW) == []


def test_consecutive_skips():
    o = out([val("Q7.does_not_drink", True)], "NEXT", "Q8_1")
    assert validate_extraction(inp("Q7"), o, FLOW) == []


def test_zero_days_skips_followup():
    o = out([val("Q8_1.days", 0)], "NEXT", "Q9_1")
    assert validate_extraction(inp("Q8_1"), o, FLOW) == []


def test_reask_and_redirect_stay_on_question():
    o = out([val("Q8_1.days", None, "MISSING")], "REASK", "Q8_1", reason="MISSING", targets=["Q8_1.days"])
    assert validate_extraction(inp("Q8_1"), o, FLOW) == []
    assert validate_extraction(inp("Q8_1"), out([], "REDIRECT", "Q8_1", reason="OFF_TOPIC"), FLOW) == []


def test_confirm_points_at_target_item_even_if_earlier():
    o = out([val("Q4.answer", None, "CONFLICT")], "CONFIRM", "Q4", reason="CONFLICT_WITH_PREVIOUS", targets=["Q4.answer"])
    assert validate_extraction(inp("Q5"), o, FLOW) == []


def test_partially_prefilled_next_is_not_a_violation():
    # 계약이 허용한다: 같은 말에서 Q4 예와 Q4_1 칸이 함께 나오고 next_item이 Q4_1
    o = out([val("Q4.answer", True), val("Q4_1.status", "past")], "NEXT", "Q4_1")
    assert validate_extraction(inp("Q4"), o, FLOW) == []


def test_latest_item_in_one_utterance_is_the_base():
    o = out([val("Q3.answer", True), val("Q4.answer", False)], "NEXT", "Q5")
    assert validate_extraction(inp("Q3"), o, FLOW) == []


def test_bracketed_beverage_key_uses_unbracketed_slot_for_skip():
    o = out([val("Q7[soju].amount", 2), val("Q7.does_not_drink", False)], "NEXT", "Q7_1")
    assert validate_extraction(inp("Q7"), o, FLOW) == []


# 위반

def test_target_not_in_values():
    o = out([val("Q8_1.days", None, "MISSING")], "REASK", "Q8_1", reason="MISSING", targets=["Q8_1.other"])
    assert codes(inp("Q8_1"), o) == ["TARGET_NOT_IN_VALUES"]


def test_reask_next_item_must_equal_question_id():
    o = out([val("Q8_1.days", None, "MISSING")], "REASK", "Q8_2", reason="MISSING", targets=["Q8_1.days"])
    assert codes(inp("Q8_1"), o) == ["NEXT_ITEM_MISMATCH"]


def test_redirect_next_item_must_equal_question_id():
    assert codes(inp("Q8_1"), out([], "REDIRECT", "Q9_1", reason="OFF_TOPIC")) == ["NEXT_ITEM_MISMATCH"]


def test_confirm_next_item_must_be_target_item():
    o = out([val("Q4.answer", None, "CONFLICT")], "CONFIRM", "Q5", reason="CONFLICT_WITH_PREVIOUS", targets=["Q4.answer"])
    assert codes(inp("Q5"), o) == ["NEXT_ITEM_MISMATCH"]


def test_next_ignoring_skip_is_skip_order_mismatch():
    o = out([val("Q4.answer", False)], "NEXT", "Q4_1")
    assert codes(inp("Q4"), o) == ["SKIP_ORDER_MISMATCH"]


def test_skipping_without_rule_is_skip_order_mismatch():
    o = out([val("Q4.answer", True)], "NEXT", "Q5")
    assert codes(inp("Q4"), o) == ["SKIP_ORDER_MISMATCH"]


def test_going_backwards_is_next_item_mismatch():
    o = out([val("Q5.answer", True)], "NEXT", "Q3")
    assert codes(inp("Q5"), o) == ["NEXT_ITEM_MISMATCH"]


def test_end_too_early():
    assert codes(inp("Q9_1"), out([val("Q9_1.days", 3)], "NEXT", "END")) == ["SKIP_ORDER_MISMATCH"]


def test_skip_rule_needs_saved_value():
    # CONFLICT라 저장하지 않았으면 건너뛰기 조건이 아니다: Q4_1로 가는 것이 맞다
    o = out([val("Q4.answer", None, "UNCLEAR")], "HOLD", "Q4_1", reason="UNCERTAIN", targets=["Q4.answer"])
    assert codes(inp("Q4"), o) == []
    o = out([val("Q4.answer", None, "UNCLEAR")], "HOLD", "Q5", reason="UNCERTAIN", targets=["Q4.answer"])
    assert codes(inp("Q4"), o) == ["SKIP_ORDER_MISMATCH"]


def test_bool_and_number_are_not_confused_in_skip_rule():
    # Q8_1.days가 False(불리언)면 0 규칙에 해당하지 않는다
    o = out([val("Q8_1.days", False)], "NEXT", "Q9_1")
    assert codes(inp("Q8_1"), o) == ["SKIP_ORDER_MISMATCH"]


@pytest.mark.parametrize("status", ["MISSING", "UNCLEAR", "UNKNOWN", "REJECTED"])
def test_save_rule_null_statuses(status):
    o = out([val("Q3.answer", True, status, save=False)], "HOLD", "Q4", reason="UNCERTAIN", targets=["Q3.answer"])
    assert "SAVE_RULE" in codes(inp("Q3"), o)


def test_save_true_on_non_saving_status():
    o = out([val("Q3.answer", None, "UNCLEAR", save=True)], "REASK", "Q3", reason="MISSING", targets=["Q3.answer"])
    assert "SAVE_RULE" in codes(inp("Q3"), o)


def test_save_false_on_answered():
    assert "SAVE_RULE" in codes(inp("Q3"), out([val("Q3.answer", True, save=False)], "NEXT", "Q4"))


def test_unknown_item_is_reported():
    o = out([val("Q99.answer", True)], "NEXT", "Q4")
    assert codes(inp("Q3"), o) == ["UNKNOWN_ITEM"]
    assert codes(inp("Q99"), out([], "REDIRECT", "Q99", reason="OFF_TOPIC")) == ["UNKNOWN_ITEM"]
    assert codes(inp("Q3"), out([val("Q3.answer", True)], "NEXT", "Q99")) == ["UNKNOWN_ITEM"]


def test_non_schema_output_is_reported_not_raised():
    assert codes(inp("Q3"), {"values": "x"}) == ["OUTPUT_SCHEMA"]
    assert codes(inp("Q3"), {}) == ["OUTPUT_SCHEMA"]
    o = out([val("Q3.answer", True)], "NEXT", "Q4")
    o["extra"] = 1
    assert codes(inp("Q3"), o) == ["OUTPUT_SCHEMA"]


def test_violation_shape_and_no_values_in_message():
    o = out([val("Q3.answer", "비밀값123")], "NEXT", "Q9_2")
    vs = validate_extraction(inp("Q3"), o, FLOW)
    assert vs and all(isinstance(v, Violation) and len(v) == 3 for v in vs)
    assert all("비밀값123" not in repr(v) for v in vs)


# 입력 위반, 순수성, 결정성

def test_input_violation_raises_contract_violation():
    bad = inp("Q3")
    del bad["state"]
    with pytest.raises(te.ContractViolation) as e:
        validate_extraction(bad, out([], "REDIRECT", "Q3", reason="OFF_TOPIC"), FLOW)
    assert e.value.contract == "ActionExtractionInput"
    with pytest.raises(te.ContractViolation):
        validate_extraction(inp("not-an-id"), out([], "REDIRECT", "Q3", reason="OFF_TOPIC"), FLOW)


def test_deterministic_and_does_not_mutate_inputs():
    i = inp("Q4", {"Q3.answer": {"value": True, "status": "ANSWERED"}})
    o = out([val("Q4.answer", False)], "NEXT", "Q4_1")
    i0, o0 = copy.deepcopy(i), copy.deepcopy(o)
    r1 = validate_extraction(i, o, FLOW)
    r2 = validate_extraction(i, o, FLOW)
    assert r1 == r2 and i == i0 and o == o0


def test_empty_list_is_returned_as_list():
    r = validate_extraction(inp("Q3"), out([val("Q3.answer", True)], "NEXT", "Q4"), FLOW)
    assert r == [] and isinstance(r, list)


# 표

def test_custom_flow_table():
    flow = QuestionFlowTable(order=["Q1", "Q2", "Q3"], skips=[SkipRule("Q1.x", True, "Q2")])
    o = out([val("Q1.x", True)], "NEXT", "Q3")
    assert validate_extraction(inp("Q1"), o, flow) == []
    assert codes(inp("Q1"), out([val("Q1.x", False)], "NEXT", "Q3"), flow) == ["SKIP_ORDER_MISMATCH"]


def test_flow_table_rejects_bad_definitions():
    with pytest.raises(ValueError):
        QuestionFlowTable(order=["A", "A"])
    with pytest.raises(ValueError):
        QuestionFlowTable(order=["A"], skips=[SkipRule("A.x", True, "Z")])


def test_dataset_v2_flow_shape():
    assert len(FLOW.order) == 31 and FLOW.order[0] == "Q1.D01" and FLOW.order[-1] == "Q10"
    assert len(FLOW.skips) == 7


# 폐기 표시, 의존

@pytest.mark.parametrize("name", ["normalize", "judge", "write_record", "plan"])
def test_old_functions_are_marked_deprecated(name):
    fn = getattr(te, name)
    assert getattr(fn, "__deprecated__", False)
    with pytest.warns(DeprecationWarning):
        with pytest.raises(te.ContractViolation):
            fn({})


def test_boundary_contracts_pinned_to_v2_0_0():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "openit_boundary-contracts.git@v2.0.0" in text
    import boundary_contracts
    from importlib.metadata import version
    assert version("boundary-contracts") == "2.0.0"
    assert boundary_contracts.PIPELINE_SCHEMA_VERSION == "2.0"


# 학습 데이터 전수(선택): 환경변수에 JSONL 경로를 주면 돈다. 서버 데이터는 읽기 전용으로 표준입력에 흘려 검사하는
# scripts/validate_dataset_a.py가 기본 방법이다.

@pytest.mark.skipif(not os.environ.get("TURN_ENGINE_DATASET_A"), reason="TURN_ENGINE_DATASET_A(JSONL 경로, ':'로 구분) 없음")
def test_training_data_a_has_zero_violations():
    total = 0
    for path in os.environ["TURN_ENGINE_DATASET_A"].split(":"):
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            u, o = json.loads(r["messages"][1]["content"]), json.loads(r["messages"][2]["content"])
            assert validate_extraction(u, o, FLOW) == [], r.get("scenario_id")
            total += 1
    assert total > 0


def test_dataset_script_reports_violation_exit_code(tmp_path):
    good = {"messages": [{"role": "system", "content": "s"},
                         {"role": "user", "content": json.dumps(inp("Q3"))},
                         {"role": "assistant", "content": json.dumps(out([val("Q3.answer", True)], "NEXT", "Q4"))}],
            "scenario_id": "ok"}
    bad = copy.deepcopy(good)
    bad["messages"][2]["content"] = json.dumps(out([val("Q3.answer", True)], "NEXT", "Q9_2"))
    bad["scenario_id"] = "bad"
    script = str(ROOT / "scripts" / "validate_dataset_a.py")
    r = subprocess.run([sys.executable, script], input=json.dumps(good) + "\n", capture_output=True, text=True)
    assert r.returncode == 0 and "violating_rows=0" in r.stdout
    r = subprocess.run([sys.executable, script], input=json.dumps(good) + "\n" + json.dumps(bad) + "\n", capture_output=True, text=True)
    assert r.returncode == 1 and "violating_rows=1" in r.stdout
