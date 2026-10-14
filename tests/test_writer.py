"""Record Writer 규칙 시험. 규칙 문장은 docs/rules/record_writer.md (7절)의 번호를 따른다."""
import pytest
from fixtures import *
from turn_engine import write_record, ContractViolation

SL = ref(SLEEP, "hours")
H7 = {"amount": 7, "unit": "시간"}
H8 = {"amount": 8, "unit": "시간"}
QS = [{"question_id": q["question_id"], "slot_ids": [s["slot_id"] for s in q["slots"]]} for q in questions()]


def J(target, status, value=None, handling="NONE", ids=None, risk=None, **kw):
    j = {"target": target, "status": status, "reasons": [], "value_now": value, "said_value": None,
         "pending_handling": handling, "target_pending_ids": ids or [], "mismatched_slots": [], "risk_rule": risk}
    j.update(kw)
    return j


def R(slot, current=None, pend=None):
    cv = "NONE" if current is None else current if current in ("UNKNOWN_RECORD", "REFUSAL_RECORD") else {"answer": current}
    return {"slot": slot, "current_value": cv, "pending": pend}


def P(value, pid="p1", risk=None):
    return {"pending_id": pid, "value": value, "risk_mark": risk}


def run(judgments, records, inval=None):
    return write_record({"judgments": judgments, "invalidated_questions": inval or [], "question_slots": QS,
                         "target_records": records})


def acts(out):
    return [(d["action"], skey_(d["slot"])) for d in out["store_decisions"]]


def skey_(s):
    return (s["question_id"], s["slot_id"])


def test_w1_first_answer_is_first_write():
    out = run([J(SL, "ANSWERED", H7)], [R(SL)])
    d = out["store_decisions"]
    assert [x["action"] for x in d] == ["FIRST_WRITE"] and d[0]["value"] == H7
    assert out["store_summary"]["changed_slots"] == [{"slot": SL, "previous_value": None, "new_value": H7, "kind": "FIRST_ANSWER"}]


def test_w1_same_value_writes_nothing():
    out = run([J(SL, "ANSWERED", H7)], [R(SL, H7)])
    assert out["store_decisions"] == [] and out["store_summary"]["changed_slots"] == []


def test_w1_same_value_with_drop_only_drops_pending():
    out = run([J(SL, "ANSWERED", H7, "DROP", ["p1"])], [R(SL, H7, P(H8))])
    assert acts(out) == [("DROP_PENDING", ("q_sleep", "hours"))]
    assert out["store_decisions"][0]["pending_id"] == "p1"
    assert out["store_summary"]["resolved_pendings"] == [{"slot": SL, "handling": "DROP"}]


def test_w1_correction_is_new_revision():
    out = run([J(SL, "CORRECTION", H8)], [R(SL, H7)])
    assert acts(out) == [("NEW_REVISION", ("q_sleep", "hours"))]
    assert out["store_summary"]["changed_slots"][0] == {"slot": SL, "previous_value": H7, "new_value": H8, "kind": "CORRECTION"}


def test_w1_correction_accepting_pending_is_accept_pending():
    out = run([J(SL, "CORRECTION", H8, "ACCEPT", ["p1"])], [R(SL, H7, P(H8))])
    d = out["store_decisions"]
    assert [x["action"] for x in d] == ["ACCEPT_PENDING"] and d[0]["pending_id"] == "p1" and d[0]["value"] == H8
    assert out["store_summary"]["resolved_pendings"] == [{"slot": SL, "handling": "ACCEPT"}]
    assert out["store_summary"]["changed_slots"][0]["kind"] == "CORRECTION"


def test_w1_conflict_sets_pending_with_new_id():
    out = run([J(SL, "CONFLICT", H8, "CREATE")], [R(SL, H7)])
    d = out["store_decisions"][0]
    assert d["action"] == "SET_PENDING" and d["value"] == H8 and d["pending_id"]
    assert out["store_summary"]["created_pendings"] == [{"slot": SL}] and out["store_summary"]["resolved_pendings"] == []


def test_w1_conflict_replacing_pending_reports_replace():
    out = run([J(SL, "CONFLICT", {"amount": 9, "unit": "시간"}, "CREATE", ["p1"])], [R(SL, H7, P(H8))])
    assert out["store_summary"]["resolved_pendings"] == [{"slot": SL, "handling": "REPLACE"}]
    assert out["store_decisions"][0]["pending_id"] != "p1"


def test_w3_pending_id_is_new_per_pending_and_deterministic():
    a = run([J(SL, "CONFLICT", H8, "CREATE")], [R(SL, H7)])["store_decisions"][0]["pending_id"]
    b = run([J(SL, "CONFLICT", H8, "CREATE")], [R(SL, H7)])["store_decisions"][0]["pending_id"]
    c = run([J(SL, "CONFLICT", {"amount": 9, "unit": "시간"}, "CREATE")], [R(SL, H7)])["store_decisions"][0]["pending_id"]
    d = run([J(SL, "CONFLICT", H8, "CREATE", ["p1"])], [R(SL, H7, P({"amount": 6, "unit": "시간"}))])["store_decisions"][0]["pending_id"]
    assert a == b and len({a, c, d}) == 3


def test_w1_unknown_and_refusal_records():
    out = run([J(SL, "UNKNOWN")], [R(SL, H7)])
    assert acts(out) == [("RECORD_UNKNOWN", ("q_sleep", "hours"))]
    assert out["store_summary"]["unknown_refused_records"] == [{"slot": SL, "record": "UNKNOWN_RECORD"}]
    out = run([J(SL, "REJECTED")], [R(SL)])
    assert acts(out) == [("RECORD_REFUSAL", ("q_sleep", "hours"))]
    assert out["store_summary"]["unknown_refused_records"][0]["record"] == "REFUSAL_RECORD"


def test_w1_unknown_over_same_record_is_unchanged():
    assert run([J(SL, "UNKNOWN")], [R(SL, "UNKNOWN_RECORD")])["store_decisions"] == []


def test_w1_answer_after_unknown_record_is_stored_as_first_answer():
    out = run([J(SL, "ANSWERED", H7)], [R(SL, "UNKNOWN_RECORD")])
    assert out["store_summary"]["changed_slots"][0]["kind"] == "FIRST_ANSWER"
    assert out["store_summary"]["changed_slots"][0]["previous_value"] is None


def test_w1_confirm_only_accept_and_drop():
    out = run([J(SL, None, None, "ACCEPT", ["p1"])], [R(SL, H7, P(H8))])
    assert acts(out) == [("ACCEPT_PENDING", ("q_sleep", "hours"))] and out["store_decisions"][0]["value"] == H8
    out = run([J(SL, None, None, "DROP", ["p1"])], [R(SL, H7, P(H8))])
    assert acts(out) == [("DROP_PENDING", ("q_sleep", "hours"))]


def test_w1_unclear_missing_unmet_store_nothing():
    for st in ("UNCLEAR", "MISSING", "PREREQUISITE_UNMET"):
        assert run([J(SL, st)], [R(SL)])["store_decisions"] == []


def test_w1_invalidation_only_for_slots_with_record_or_pending_and_first():
    d = ref(DRINK, "status")
    a, k = ref(AMOUNT, "amount"), ref(AMOUNT, "kind")
    out = run([J(d, "CORRECTION", "안 마심")], [R(d, "마심"), R(a, {"amount": 2, "unit": "병"}), R(k)], inval=[AMOUNT])
    assert acts(out) == [("INVALIDATE", ("q_amount", "amount")), ("NEW_REVISION", ("q_drink", "status"))]
    assert out["store_summary"]["invalidated_questions"] == [AMOUNT]


def test_w1_invalidation_includes_slot_with_only_pending():
    a = ref(AMOUNT, "amount")
    out = run([], [R(a, None, P({"amount": 3, "unit": "병"}))], inval=[AMOUNT])
    assert acts(out) == [("INVALIDATE", ("q_amount", "amount"))]


def test_w1_summary_lists_only_actually_invalidated_questions():
    out = run([], [R(ref(AMOUNT, "amount")), R(ref(AMOUNT, "kind"))], inval=[AMOUNT])
    assert out["store_decisions"] == [] and out["store_summary"]["invalidated_questions"] == []


def test_w1_invalidation_comes_first_so_same_turn_value_survives():
    d = ref(DRINK, "status")
    a = ref(AMOUNT, "amount")
    out = run([J(a, "ANSWERED", {"amount": 1, "unit": "병"}), J(d, "CORRECTION", "마심")],
              [R(d, "안 마심"), R(a, {"amount": 2, "unit": "병"})], inval=[AMOUNT])
    assert [x["action"] for x in out["store_decisions"]][0] == "INVALIDATE"


def test_w1_drop_is_added_after_actions_that_keep_pending():
    for st, act in (("CORRECTION", "NEW_REVISION"), ("UNKNOWN", "RECORD_UNKNOWN"), ("REJECTED", "RECORD_REFUSAL")):
        out = run([J(SL, st, H8 if st == "CORRECTION" else None, "DROP", ["p1"])], [R(SL, H7, P(H8))])
        assert [x["action"] for x in out["store_decisions"]] == [act, "DROP_PENDING"], st


def test_w1_drop_even_when_unknown_record_is_unchanged():
    out = run([J(SL, "UNKNOWN", None, "DROP", ["p1"])], [R(SL, "UNKNOWN_RECORD", P(H8))])
    assert [x["action"] for x in out["store_decisions"]] == ["DROP_PENDING"]


def test_w2_whole_question_judgment_spreads_over_slots_except_judged_ones():
    out = run([J(whole(AMOUNT), "UNKNOWN"), J(ref(AMOUNT, "kind"), "ANSWERED", "소주")],
              [R(ref(AMOUNT, "amount")), R(ref(AMOUNT, "kind"))])
    assert acts(out) == [("RECORD_UNKNOWN", ("q_amount", "amount")), ("FIRST_WRITE", ("q_amount", "kind"))]


def test_w1_risk_mark_follows_judgment():
    out = run([J(ref(PAIN, "level"), "ANSWERED", "심함", risk="IMMEDIATE")], [R(ref(PAIN, "level"))])
    assert out["store_decisions"][0]["risk_mark"] == "IMMEDIATE"
    out = run([J(ref(PAIN, "level"), "CONFLICT", "심함", "CREATE", risk="ON_RESULT")], [R(ref(PAIN, "level"), "약함")])
    assert out["store_decisions"][0]["risk_mark"] == "ON_RESULT"


def test_value_metadata_is_passed_through():
    md = {"precision": "approximate", "evidence": []}
    out = run([J(SL, "ANSWERED", H7, value_metadata=md)], [R(SL)])
    assert out["store_decisions"][0]["value_metadata"] == md


def test_unchanged_slots_not_emitted_and_empty_input():
    assert run([], [])["store_decisions"] == []


def test_schema_violation():
    with pytest.raises(ContractViolation):
        write_record({"judgments": [], "invalidated_questions": [], "question_slots": QS})
