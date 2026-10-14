"""Answer Judge 규칙 시험. 규칙 문장은 docs/rules/answer_judge.md (6절)의 번호를 따른다."""
import pytest
from fixtures import *
from turn_engine import normalize, judge, ContractViolation

DRINK_YES = [cur(ref(DRINK, "status"), "마심")]
SL = ref(SLEEP, "hours")
H7 = {"amount": 7, "unit": "시간"}
H8 = {"amount": 8, "unit": "시간"}


def ask(action, targets, pid=None):
    return {"action": action, "targets": targets, "target_pending_id": pid, "say_values": [], "reask_reasons": [],
            "notices": [], "sentence_materials": {k: [] for k in ["question_sentences", "refusal_explanations", "reask_sentences", "choices", "guide_sentences", "fixed_sentences"]},
            "awaiting": {"action": action, "targets": targets, "target_pending_id": pid, "say_values": []}}


def run(items, currents=None, pendings=None, last=None):
    pend = [{"pending_id": p["pending_id"], "slot": p["slot"], "value": p["value"]} for p in (pendings or [])]
    aw = None
    if last and last["awaiting"]:
        aw = {k: last["awaiting"][k] for k in ("action", "targets", "target_pending_id")}
    n = normalize(normalizer_input(items, currents=currents, pendings=pend, awaiting=aw))
    j = judge(judge_input(items, n["item_checks"], missing=n["missing_required_slots"], last=last,
                          pendings=[{"pending_id": p["pending_id"], "slot": p["slot"]} for p in pend]))
    return j


def jd(out, slot=None):
    js = out["judgments"]
    if slot is None:
        assert len(js) == 1, js
        return js[0]
    return next(j for j in js if j["target"] == slot)


# ----- 규칙 1: 상태 판정 순서 -----
def test_j1_first_answer_is_answered_even_if_marked_correction():
    j = jd(run([item(0, SL, "7시간")]))
    assert j["status"] == "ANSWERED" and j["value_now"] == H7 and j["pending_handling"] == "NONE"
    j = jd(run([item(0, SL, "7시간", "CORRECTION_MARKED")]))
    assert j["status"] == "ANSWERED"


def test_j1_same_as_current_is_answered():
    assert jd(run([item(0, SL, "7시간")], currents=[cur(SL, H7)]))["status"] == "ANSWERED"


def test_j1_different_from_current_is_conflict_with_new_pending():
    j = jd(run([item(0, SL, "8시간")], currents=[cur(SL, H7)]))
    assert j["status"] == "CONFLICT" and j["pending_handling"] == "CREATE" and j["value_now"] == H8


def test_j1_correction_marker_gives_correction():
    j = jd(run([item(0, SL, "8시간", "CORRECTION_MARKED")], currents=[cur(SL, H7)]))
    assert j["status"] == "CORRECTION" and j["value_now"] == H8


def test_j1_unknown_and_refusal():
    assert jd(run([item(0, SL, None, "SAYS_UNKNOWN")]))["status"] == "UNKNOWN"
    assert jd(run([item(0, SL, None, "SAYS_REFUSAL")]))["status"] == "REJECTED"


def test_j1_problem_means_unclear_with_reason():
    j = jd(run([item(0, ref(VISIT, "times"), "두 번이요")]))
    assert j["status"] == "UNCLEAR" and j["reasons"] == ["NO_UNIT"] and j["value_now"] is None
    assert j["said_value"] == "두 번이요"


def test_j1_unknown_before_problem_before_value():
    # 모름이 문제보다 먼저(같은 슬롯에 모름만)
    assert jd(run([item(0, ref(VISIT, "times"), None, "SAYS_UNKNOWN")]))["status"] == "UNKNOWN"


def test_j1_prerequisite_unmet_first():
    j = jd(run([item(0, ref(AMOUNT, "kind"), None, "SAYS_UNKNOWN")]))
    assert j["status"] == "PREREQUISITE_UNMET"
    j = jd(run([item(0, ref(AMOUNT, "kind"), "소주")]))
    assert j["status"] == "PREREQUISITE_UNMET"


def test_j1_missing_slots_get_missing_judgments():
    out = run([item(0, ref(AMOUNT, "amount"), "두 병")], currents=DRINK_YES)
    m = jd(out, ref(AMOUNT, "kind"))
    assert m["status"] == "MISSING" and m["reasons"] == ["MISSING_SLOT"]


def test_j1_mismatch_both_sides_unclear():
    out = run([item(0, ref(DRINK, "status"), "안 마시고요"), item(1, ref(AMOUNT, "kind"), "소주")])
    a, b = jd(out, ref(DRINK, "status")), jd(out, ref(AMOUNT, "kind"))
    assert a["status"] == b["status"] == "UNCLEAR" and a["reasons"] == b["reasons"] == ["MISMATCH"]
    assert a["mismatched_slots"] == [ref(AMOUNT, "kind")] and b["mismatched_slots"] == [ref(DRINK, "status")]


def test_j1_risk_rule_passes_through():
    j = jd(run([item(0, ref(PAIN, "level"), "심함")]))
    assert j["risk_rule"] == "IMMEDIATE" and j["status"] == "ANSWERED"


# ----- 규칙 2: 확인 대기가 있는 슬롯 -----
def pending(slot, value, pid="p1"):
    return {"pending_id": pid, "slot": slot, "value": value}


def test_j2_value_equal_to_pending_is_correction_accept():
    j = jd(run([item(0, SL, "8시간")], currents=[cur(SL, H7)], pendings=[pending(SL, H8)]))
    assert j["status"] == "CORRECTION" and j["pending_handling"] == "ACCEPT" and j["target_pending_ids"] == ["p1"]


def test_j2_value_equal_to_current_drops_pending():
    j = jd(run([item(0, SL, "7시간")], currents=[cur(SL, H7)], pendings=[pending(SL, H8)]))
    assert j["status"] == "ANSWERED" and j["pending_handling"] == "DROP"


def test_j2_correction_unknown_refusal_drop_pending():
    p = [pending(SL, H8)]
    for it, st in ((item(0, SL, "9시간", "CORRECTION_MARKED"), "CORRECTION"), (item(0, SL, None, "SAYS_UNKNOWN"), "UNKNOWN"),
                   (item(0, SL, None, "SAYS_REFUSAL"), "REJECTED")):
        j = jd(run([it], currents=[cur(SL, H7)], pendings=p))
        assert j["status"] == st and j["pending_handling"] == "DROP" and j["target_pending_ids"] == ["p1"]


def test_j2_third_value_replaces_pending():
    j = jd(run([item(0, SL, "9시간")], currents=[cur(SL, H7)], pendings=[pending(SL, H8)]))
    assert j["status"] == "CONFLICT" and j["pending_handling"] == "CREATE" and j["target_pending_ids"] == ["p1"]


def test_j2_unclear_with_pending_has_no_handling():
    j = jd(run([item(0, SL, "많이")], currents=[cur(SL, H7)], pendings=[pending(SL, H8)]))
    assert j["status"] == "UNCLEAR" and j["pending_handling"] == "NONE"


# ----- 확인 응답 (표) -----
CONF_LAST = ask("ASK_CONFIRM", [SL], "p1")


def test_confirm_yes_no_with_awaited_pending():
    out = run([item(0, None, None, "CONFIRM_YES")], currents=[cur(SL, H7)], pendings=[pending(SL, H8)], last=CONF_LAST)
    j = jd(out)
    assert j["status"] is None and j["pending_handling"] == "ACCEPT" and j["target_pending_ids"] == ["p1"]
    assert out["invalidated_questions"] == []
    out = run([item(0, None, None, "CONFIRM_NO")], currents=[cur(SL, H7)], pendings=[pending(SL, H8)], last=CONF_LAST)
    assert jd(out)["pending_handling"] == "DROP"


def test_confirm_without_awaiting_is_irrelevant():
    out = run([item(0, None, None, "CONFIRM_YES")])
    assert out["judgments"] == [] and out["utterance_judgment"]["result"] == "OUT_OF_SCOPE_ONLY"
    assert out["utterance_judgment"]["confirmation"] == "NONE"


def test_confirm_for_pending_not_in_list_is_irrelevant():
    out = run([item(0, None, None, "CONFIRM_YES")], last=CONF_LAST)
    assert out["judgments"] == [] and out["utterance_judgment"]["result"] == "OUT_OF_SCOPE_ONLY"


def test_confirm_yes_and_no_together_are_irrelevant_rule4():
    out = run([item(0, None, None, "CONFIRM_YES"), item(1, None, None, "CONFIRM_NO")],
              currents=[cur(SL, H7)], pendings=[pending(SL, H8)], last=CONF_LAST)
    assert out["judgments"] == [] and out["utterance_judgment"]["confirmation"] == "NONE"


def test_confirm_dropped_when_value_comes_with_it_rule4():
    out = run([item(0, None, None, "CONFIRM_YES"), item(1, SL, "9시간")], currents=[cur(SL, H7)],
              pendings=[pending(SL, H8)], last=CONF_LAST)
    assert len(out["judgments"]) == 1 and out["judgments"][0]["status"] == "CONFLICT"


def test_confirm_for_other_awaiting_kinds_is_utterance_confirmation():
    for act, tg in (("ASK_FINISH", []), ("ASK_STOP", []), ("ASK_CORRECTION_TARGET", [SL])):
        out = run([item(0, None, None, "CONFIRM_YES")], last=ask(act, tg))
        assert out["utterance_judgment"]["confirmation"] == "YES" and out["judgments"] == []
        assert out["utterance_judgment"]["result"] == "HAS_ANSWER"
        out = run([item(0, None, None, "CONFIRM_NO")], last=ask(act, tg))
        assert out["utterance_judgment"]["confirmation"] == "NO"


def test_confirm_yes_no_together_for_finish_is_none():
    out = run([item(0, None, None, "CONFIRM_YES"), item(1, None, None, "CONFIRM_NO")], last=ask("ASK_FINISH", []))
    assert out["utterance_judgment"]["confirmation"] == "NONE"


def test_confirm_item_of_unmet_question_is_prerequisite_unmet():
    s = ref(AMOUNT, "kind")
    last = ask("ASK_CONFIRM", [s], "p1")
    out = run([item(0, None, None, "CONFIRM_YES")], currents=[cur(ref(DRINK, "status"), "안 마심")],
              pendings=[pending(s, "맥주")], last=last)
    assert jd(out)["status"] == "PREREQUISITE_UNMET"


# ----- 정의에 없는 대상, 요청, 위험 -----
def test_unknown_target_answer_is_treated_as_irrelevant():
    out = run([item(0, ref("q_none", "x"), "네")])
    assert out["judgments"] == [] and out["utterance_judgment"]["result"] == "OUT_OF_SCOPE_ONLY"
    out = run([item(0, ref("q_none", "x"), None, "SAYS_UNKNOWN")])
    assert out["judgments"] == []


def test_j8_unknown_target_on_request_or_risk_is_treated_as_targetless():
    out = run([item(0, ref("q_none", "x"), None, "PROGRESS_OP", op="LATER")], last=ask("ASK_NEXT", [whole(SLEEP)]))
    r = out["utterance_judgment"]["requests"][0]
    assert r["kind"] == "LATER" and r["target_question_id"] is None
    out = run([item(0, ref("q_none", "x"), None, "USER_CALLED_STAFF")])
    assert out["utterance_judgment"]["requests"][0]["kind"] == "STAFF_REQUEST"
    out = run([item(0, ref("q_none", "x"), None, "RISK_SIGNAL", text="가슴이 아파요")])
    assert out["utterance_judgment"]["risk_signal"] == {"evidence": ["가슴이 아파요"]}


def test_j7_request_target_from_item_or_awaiting():
    last = ask("ASK_NEXT", [whole(SLEEP)])
    r = run([item(0, None, None, "PROGRESS_OP", op="LATER")], last=last)["utterance_judgment"]["requests"][0]
    assert r["target_question_id"] == SLEEP
    r = run([item(0, whole(VISIT), None, "PROGRESS_OP", op="LATER")], last=last)["utterance_judgment"]["requests"][0]
    assert r["target_question_id"] == VISIT
    r = run([item(0, None, None, "GUIDE_REQUEST", guide="g_why")], last=last)["utterance_judgment"]["requests"][0]
    assert r["kind"] == "GUIDE" and r["guide_id"] == "g_why" and r["target_question_id"] == SLEEP


def test_j7_awaiting_with_two_questions_gives_no_target():
    last = ask("ASK_CLARIFY", [SL, ref(VISIT, "times")])
    r = run([item(0, None, None, "PROGRESS_OP", op="LATER")], last=last)["utterance_judgment"]["requests"][0]
    assert r["target_question_id"] is None


def test_j7_same_requests_merge_and_collect_source_text():
    out = run([item(0, None, None, "PROGRESS_OP", op="REPEAT", text="다시요"),
               item(1, None, None, "PROGRESS_OP", op="REPEAT", text="한 번 더")])
    reqs = out["utterance_judgment"]["requests"]
    assert len(reqs) == 1 and reqs[0]["source_text"] == ["다시요", "한 번 더"]
    assert out["utterance_judgment"]["result"] == "REQUEST_ONLY"


def test_request_kinds():
    for op in ("REPEAT", "WAIT", "STOP"):
        assert run([item(0, None, None, "PROGRESS_OP", op=op)])["utterance_judgment"]["requests"][0]["kind"] == op
    assert run([item(0, None, None, "USER_CALLED_STAFF")])["utterance_judgment"]["requests"][0]["kind"] == "STAFF_REQUEST"


def test_later_of_unmet_question_is_irrelevant():
    out = run([item(0, whole(AMOUNT), None, "PROGRESS_OP", op="LATER")])
    assert out["utterance_judgment"]["requests"] == [] and out["utterance_judgment"]["result"] == "OUT_OF_SCOPE_ONLY"


def test_valueless_correction_is_a_request():
    out = run([item(0, SL, None, "CORRECTION_MARKED")])
    u = out["utterance_judgment"]
    assert out["judgments"] == [] and u["valueless_correction_requests"] == [{"target": SL}]
    assert u["result"] == "REQUEST_ONLY"
    out = run([item(0, None, None, "CORRECTION_MARKED")])
    assert out["utterance_judgment"]["valueless_correction_requests"] == [{"target": None}]


def test_valueless_correction_of_unmet_question_is_irrelevant():
    out = run([item(0, ref(AMOUNT, "kind"), None, "CORRECTION_MARKED")])
    assert out["utterance_judgment"]["valueless_correction_requests"] == []


def test_j3_valueless_correction_dropped_when_slot_has_value_judgment():
    out = run([item(0, SL, None, "CORRECTION_MARKED"), item(1, SL, "8시간")], currents=[cur(SL, H7)])
    assert out["utterance_judgment"]["valueless_correction_requests"] == []
    assert len(out["judgments"]) == 1


def test_risk_signal_result_and_evidence():
    out = run([item(0, None, None, "RISK_SIGNAL", text="숨이 안 쉬어져요")])
    u = out["utterance_judgment"]
    assert u["risk_signal"] == {"evidence": ["숨이 안 쉬어져요"]} and u["result"] == "REQUEST_ONLY"


def test_result_classification():
    assert run([item(0, None, None, "OUT_OF_SCOPE")])["utterance_judgment"]["result"] == "OUT_OF_SCOPE_ONLY"
    assert run([item(0, None, None, "UNRECOGNIZED")])["utterance_judgment"]["result"] == "UNRECOGNIZED_TURN"
    assert run([])["utterance_judgment"]["result"] == "UNRECOGNIZED_TURN"
    out = run([item(0, SL, "7시간"), item(1, None, None, "OUT_OF_SCOPE")])
    assert out["utterance_judgment"]["result"] == "HAS_ANSWER"
    out = run([item(0, None, None, "OUT_OF_SCOPE"), item(1, None, None, "PROGRESS_OP", op="WAIT")])
    assert out["utterance_judgment"]["result"] == "REQUEST_ONLY"


def test_prerequisite_unmet_answer_counts_as_answer_but_is_not_stored():
    out = run([item(0, ref(AMOUNT, "kind"), "소주")])
    assert out["utterance_judgment"]["result"] == "HAS_ANSWER"


# ----- 규칙 3: 같은 대상 합치기 -----
def test_j3_same_values_merge_correction_marker_wins():
    out = run([item(0, SL, "8시간"), item(1, SL, "여덟 시간", "CORRECTION_MARKED")], currents=[cur(SL, H7)])
    assert len(out["judgments"]) == 1 and out["judgments"][0]["status"] == "CORRECTION"


def test_j3_different_values_are_ambiguous_joined():
    out = run([item(0, SL, "7시간"), item(1, SL, "8시간")])
    j = jd(out)
    assert j["status"] == "UNCLEAR" and j["reasons"] == ["AMBIGUOUS"] and j["said_value"] == "7시간 / 8시간"


def test_j3_value_with_unclear_is_ambiguous():
    j = jd(run([item(0, SL, "7시간"), item(1, SL, "가끔")]))
    assert j["status"] == "UNCLEAR" and j["reasons"] == ["AMBIGUOUS"]


def test_j3_value_beats_unknown_and_confirm():
    j = jd(run([item(0, SL, "7시간"), item(1, SL, None, "SAYS_UNKNOWN")]))
    assert j["status"] == "ANSWERED"
    j = jd(run([item(0, None, None, "CONFIRM_YES"), item(1, SL, "9시간")], currents=[cur(SL, H7)],
               pendings=[pending(SL, H8)], last=CONF_LAST))
    assert j["status"] == "CONFLICT"


def test_j3_unknown_and_refusal_later_wins():
    assert jd(run([item(0, SL, None, "SAYS_UNKNOWN"), item(1, SL, None, "SAYS_REFUSAL")]))["status"] == "REJECTED"
    assert jd(run([item(0, SL, None, "SAYS_REFUSAL"), item(1, SL, None, "SAYS_UNKNOWN")]))["status"] == "UNKNOWN"


# ----- 규칙 5: 문항 전체 모름·거절 -----
def test_j5_whole_question_unknown_covers_remaining_slots_only():
    out = run([item(0, whole(AMOUNT), None, "SAYS_UNKNOWN"), item(1, ref(AMOUNT, "kind"), "소주")], currents=DRINK_YES)
    whole_j = [j for j in out["judgments"] if j["target"] == whole(AMOUNT)]
    assert len(whole_j) == 1 and whole_j[0]["status"] == "UNKNOWN"
    assert jd(out, ref(AMOUNT, "kind"))["status"] == "ANSWERED"


def test_j5_whole_question_with_no_remaining_slot_gives_no_judgment():
    out = run([item(0, whole(SLEEP), None, "SAYS_UNKNOWN"), item(1, SL, "7시간")])
    assert [j["target"] for j in out["judgments"]] == [SL]


def test_j5_whole_question_drops_pendings_of_remaining_slots():
    s = ref(AMOUNT, "kind")
    out = run([item(0, whole(AMOUNT), None, "SAYS_REFUSAL")], currents=DRINK_YES + [cur(s, "소주")], pendings=[pending(s, "맥주")])
    j = out["judgments"][0]
    assert j["status"] == "REJECTED" and j["pending_handling"] == "DROP" and j["target_pending_ids"] == ["p1"]


def test_j5_whole_question_covers_confirm_item():
    s = ref(AMOUNT, "kind")
    last = ask("ASK_CONFIRM", [s], "p1")
    out = run([item(0, whole(AMOUNT), None, "SAYS_UNKNOWN"), item(1, None, None, "CONFIRM_YES")],
              currents=DRINK_YES + [cur(s, "소주")], pendings=[pending(s, "맥주")], last=last)
    assert [j["status"] for j in out["judgments"]] == ["UNKNOWN"]


# ----- 규칙 6: 무효화 대상 문항 -----
def test_j6_invalidation_for_correction_unknown_refusal_and_accept():
    d = ref(DRINK, "status")
    out = run([item(0, d, "안 마시고요", "CORRECTION_MARKED")], currents=DRINK_YES)
    assert out["invalidated_questions"] == [AMOUNT]
    assert run([item(0, d, None, "SAYS_UNKNOWN")], currents=DRINK_YES)["invalidated_questions"] == [AMOUNT]
    assert run([item(0, d, None, "SAYS_REFUSAL")], currents=DRINK_YES)["invalidated_questions"] == [AMOUNT]
    last = ask("ASK_CONFIRM", [d], "p1")
    out = run([item(0, None, None, "CONFIRM_YES")], currents=DRINK_YES, pendings=[pending(d, "안 마심")], last=last)
    assert out["invalidated_questions"] == [AMOUNT]


def test_j6_no_invalidation_for_answer_conflict_or_unclear():
    d = ref(DRINK, "status")
    assert run([item(0, d, "마시고요")], currents=DRINK_YES)["invalidated_questions"] == []
    assert run([item(0, d, "안 마시고요")], currents=DRINK_YES)["invalidated_questions"] == []  # 충돌: 확인 대기만
    assert run([item(0, d, "글쎄")], currents=DRINK_YES)["invalidated_questions"] == []


def test_j6_first_answer_marked_correction_is_answered_and_not_invalidating():
    out = run([item(0, ref(DRINK, "status"), "안 마시고요", "CORRECTION_MARKED")])
    assert out["judgments"][0]["status"] == "ANSWERED" and out["invalidated_questions"] == []


# ----- 계약 -----
def test_missing_item_check_is_violation():
    inp = judge_input([item(0, SL, "7")], [])
    with pytest.raises(ContractViolation):
        judge(inp)


def test_schema_violation():
    inp = judge_input([item(0, SL, "7")], [])
    inp["utterance"] = 3
    with pytest.raises(ContractViolation):
        judge(inp)
