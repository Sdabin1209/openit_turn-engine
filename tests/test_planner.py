"""Dialogue Planner 규칙 시험. 규칙 문장은 docs/rules/dialogue_planner.md (8절)의 번호를 따른다.
시험은 sim.Session(오케스트레이터 흉내)으로 여러 턴을 이어 돌린다."""
import pytest
from fixtures import *
from sim import Session
from turn_engine import plan, ContractViolation

SL, DR, AM, AK = ref(SLEEP, "hours"), ref(DRINK, "status"), ref(AMOUNT, "amount"), ref(AMOUNT, "kind")
VT, PN, NT = ref(VISIT, "times"), ref(PAIN, "level"), ref(NOTE, "text")
H7 = {"amount": 7, "unit": "시간"}


def ans(s, slot, text, intent="ANSWERED_INTENT", n=0):
    return item(n, slot, text, intent)


def say(op, n=0, text=None):
    return item(n, None, None, "PROGRESS_OP", op=op, text=text)


def started(**kw):
    s = Session(**kw)
    s.nonutterance("SESSION_START")
    return s


def answered_all(s):
    s.turn([ans(s, DR, "안 마시고요"), ans(s, SL, "7시간", n=1), ans(s, VT, "주에 두 번", n=2),
            ans(s, PN, "약함", n=3), ans(s, NT, "없음", n=4)])
    return s


def tg(d):
    return [t.get("slot_id") or t["question_id"] for t in d["targets"]]


def kinds(d):
    return [n["kind"] for n in d["notices"]]


# ----- 8-3: 발화가 아닌 턴 -----
def test_83_session_start_asks_first_open_question_and_keeps_status():
    s = Session()
    out = s.nonutterance("SESSION_START")
    assert out["directive"]["action"] == "ASK_NEXT" and tg(out["directive"]) == [DRINK]
    assert out["progress_record_update"]["session_status"] is None and out["flow"] == "CONTINUE"


def test_83_session_start_resumes_where_it_left_off_from_facts():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    out = s.nonutterance("SESSION_START")  # 재접속
    assert tg(out["directive"]) == [SLEEP]


def test_83_resume_notice_status_and_history():
    s = started()
    s.turn([item(0, None, None, "RISK_SIGNAL")])
    out = s.nonutterance("RESUME")
    p = out["progress_record_update"]
    assert "RESUME" in kinds(out["directive"]) and p["session_status"] == "IN_PROGRESS"
    assert p["pause_history_add"] == [{"kind": "RESUME", "reasons": []}]
    assert out["directive"]["action"] == "ASK_NEXT"


def test_83_resume_asks_pending_confirmation_first():
    s = started()
    s.turn([ans(s, DR, "마시고요")])
    s.turn([ans(s, DR, "안 마시고요")])  # 충돌 -> 확인
    assert s.action() == "ASK_CONFIRM"
    s.turn([item(0, None, None, "RISK_SIGNAL")])
    out = s.nonutterance("RESUME")
    assert out["directive"]["action"] == "ASK_CONFIRM"


def test_83_intervention_end_and_left():
    for kind, status in (("INTERVENTION_END", "ENDED_STAFF"), ("END_LEFT", "ENDED_LEFT")):
        s = started()
        out = s.nonutterance(kind)
        d = out["directive"]
        assert d["action"] == "FAREWELL" and "SURVEY_STOPPED" in kinds(d) and out["flow"] == "END"
        assert out["progress_record_update"]["session_status"] == status and d["awaiting"] is None


def test_83_utterance_turn_without_judgment_is_violation():
    s = started()
    inp = s.plan_input("UTTERANCE", None, [], None)
    with pytest.raises(ContractViolation):
        plan(inp)


# ----- 규칙 0 -----
def test_r0_stop_refusal_clears_stop_request():
    s = started()
    s.turn([say("STOP")])
    assert s.action() == "ASK_STOP" and s.open["stop_requested"]
    s.turn([item(0, None, None, "CONFIRM_NO")])
    assert not s.open["stop_requested"] and s.action() == "ASK_NEXT"


def test_r0_correction_refusal_removes_request_and_keeps_previous():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    s.turn([item(0, SL, None, "CORRECTION_MARKED")])
    assert s.action() == "ASK_CORRECTION_TARGET" and tg(s.last) == ["hours"]
    s.turn([item(0, None, None, "CONFIRM_NO")])
    assert s.open["correction_requests"] == []
    n = [x for x in s.last["notices"] if x["kind"] == "KEPT_PREVIOUS"]
    assert len(n) == 1 and n[0]["value"] == H7 and n[0]["slot"] == SL


# ----- 규칙 1: 위험 -----
def test_r1_risk_signal_pauses_and_alerts_even_with_finish_yes():
    s = started()
    answered_all(s)
    assert s.action() == "ASK_FINISH"
    out = s.turn([item(0, None, None, "CONFIRM_YES"), item(1, None, None, "RISK_SIGNAL", text="가슴이 아파요")])
    assert out["directive"]["action"] == "RISK_NOTICE" and out["flow"] == "CONTINUE"
    assert out["progress_record_update"]["session_status"] == "PAUSED_RISK"
    assert out["progress_record_update"]["pause_history_add"] == [
        {"kind": "PAUSE", "reasons": [{"kind": "RISK_SIGNAL", "evidence": ["가슴이 아파요"]}]}]
    assert out["staff_alert"] == {"kind": "RISK", "reasons": [{"kind": "RISK_SIGNAL", "evidence": ["가슴이 아파요"]}]}
    assert out["directive"]["awaiting"]["action"] == "ASK_FINISH"  # 기다리는 답 = 지금 물을 것


def test_r1_immediate_risk_rule_of_a_slot():
    s = started()
    out = s.turn([ans(s, PN, "심함")])
    d, a = out["directive"], out["staff_alert"]
    assert d["action"] == "RISK_NOTICE" and a["kind"] == "RISK"
    assert a["reasons"] == [{"kind": "RISK_RULE", "target": [{"slot": PN, "question_name": "이름_q_pain", "value": "심함"}]}]
    assert out["progress_record_update"]["pause_history_add"][0]["reasons"] == [{"kind": "RISK_RULE", "target": [PN]}]


def test_r1_resume_does_not_pause_again_from_stored_risk_mark():
    s = started()
    s.turn([ans(s, PN, "심함")])
    s.nonutterance("RESUME")
    out = s.turn([ans(s, DR, "안 마시고요")])
    assert out["directive"]["action"] != "RISK_NOTICE" and out["staff_alert"] is None


def test_r1_on_result_risk_does_not_pause():
    qs = questions()
    qs[4]["slots"][0]["risk_rule"] = {"operator": "=", "value": "심함", "response": "ON_RESULT"}
    s = Session(qs=qs)
    s.nonutterance("SESSION_START")
    out = s.turn([ans(s, PN, "심함")])
    assert out["directive"]["action"] != "RISK_NOTICE" and s.rec[(PAIN, "", "level")]["risk_mark"] == "ON_RESULT"


# ----- 규칙 2: 사람 요청 -----
def test_r2_staff_request():
    s = started()
    out = s.turn([item(0, None, None, "USER_CALLED_STAFF", text="직원 불러주세요")])
    assert out["directive"]["action"] == "CALL_STAFF" and out["progress_record_update"]["session_status"] is None
    assert out["staff_alert"] == {"kind": "USER_CALLED_STAFF", "reasons": [{"kind": "USER_CALLED_STAFF", "evidence": ["직원 불러주세요"]}]}
    assert out["directive"]["awaiting"]["action"] == "ASK_NEXT"


def test_r1_beats_r2_and_alert_keeps_both_reasons():
    s = started()
    out = s.turn([item(0, None, None, "RISK_SIGNAL", text="쓰러질 것 같아요"), item(1, None, None, "USER_CALLED_STAFF", text="직원")])
    assert out["directive"]["action"] == "RISK_NOTICE"
    assert [r["kind"] for r in out["staff_alert"]["reasons"]] == ["RISK_SIGNAL", "USER_CALLED_STAFF"]


# ----- 규칙 3: 중단 요청 -----
def test_r3_stop_request_asks_confirmation_and_records_fact():
    s = started()
    out = s.turn([say("STOP")])
    assert out["directive"]["action"] == "ASK_STOP" and out["progress_record_update"]["open_requests"]["stop_requested"]
    assert s.pr["ask_counts"] == [{"subject": {"untargeted": "ASK_STOP"}, "count": 1}]


def test_r3_stop_fact_survives_interjection_and_is_asked_again_by_ask_chain():
    s = started()
    s.turn([say("STOP")])
    out = s.turn([say("WAIT")])  # 끼어든 말
    assert out["directive"]["action"] == "WAIT_NOTICE" and out["directive"]["awaiting"]["action"] == "ASK_STOP"


def test_r3_stop_limit_turns_request_off():
    s = started()
    s.turn([say("STOP")])
    s.turn([say("WAIT")]); s.turn([say("STOP")])  # 두 번째 중단 확인
    assert s.open["stop_requested"]
    out = s.turn([say("WAIT")])  # 물은 횟수가 상한(2)
    assert not s.open["stop_requested"] and out["directive"]["awaiting"]["action"] == "ASK_NEXT"
    assert not any("ASK_STOP" in str(c) for c in s.pr["ask_counts"])


# ----- 규칙 4: 반복 요청 -----
def test_r4_repeat_replays_last_directive_and_adds_guide():
    s = started()
    first = s.last
    out = s.turn([say("REPEAT")])
    d = out["directive"]
    assert d["action"] == first["action"] and d["targets"] == first["targets"] and d["notices"] == first["notices"]
    out = s.turn([say("REPEAT", 0), item(1, None, None, "GUIDE_REQUEST", guide="g_left")])
    assert kinds(out["directive"]) == ["GUIDE"] and out["directive"]["action"] == first["action"]


def test_r4_repeat_does_not_count_as_new_ask():
    s = started()
    s.turn([ans(s, DR, "마시고요")]); s.turn([ans(s, DR, "안 마시고요")])
    c0 = s.pr["confirm_counts"]
    s.turn([say("REPEAT")])
    assert s.pr["confirm_counts"] == c0 and s.last["action"] == "ASK_CONFIRM"


def test_r4_repeat_with_answer_makes_new_directive():
    s = started()
    s.turn([say("REPEAT"), ans(s, DR, "안 마시고요", n=1)])
    assert tg(s.last) == [SLEEP]


def test_r4_without_last_directive_asks_what_to_ask():
    s = Session()
    out = s.turn([say("REPEAT")])
    assert out["directive"]["action"] == "ASK_NEXT"


# ----- 규칙 5: 대기 요청 -----
def test_r5_wait_notice_and_answer_still_saved():
    s = started()
    out = s.turn([say("WAIT"), ans(s, DR, "안 마시고요", n=1)])
    assert out["directive"]["action"] == "WAIT_NOTICE" and s.ans(DRINK, "status") == "안 마심"
    assert out["directive"]["awaiting"]["action"] == "ASK_NEXT" and tg(out["directive"]["awaiting"]) == [SLEEP]


# ----- 규칙 6: 확인 응답 -----
def test_r6_finish_yes_ends_complete():
    s = started()
    answered_all(s)
    out = s.turn([item(0, None, None, "CONFIRM_YES")])
    assert out["directive"]["action"] == "FAREWELL" and out["flow"] == "END"
    assert out["progress_record_update"]["session_status"] == "ENDED_COMPLETE"


def test_r6_finish_yes_with_judgment_in_same_turn_does_not_end():
    s = started()
    answered_all(s)
    out = s.turn([item(0, None, None, "CONFIRM_YES"), item(1, SL, "8시간", "CORRECTION_MARKED")])
    assert out["flow"] == "CONTINUE" and "CORRECTION_ACK" in kinds(out["directive"])
    assert out["directive"]["action"] == "ASK_FINISH"


def test_r6_finish_yes_with_valueless_correction_asks_what_to_fix():
    s = started()
    answered_all(s)
    out = s.turn([item(0, None, None, "CONFIRM_YES"), item(1, SL, None, "CORRECTION_MARKED")])
    assert out["flow"] == "CONTINUE" and out["directive"]["action"] == "ASK_CORRECTION_TARGET"


def test_r6_finish_yes_with_open_things_does_not_end():
    s = started()
    answered_all(s)
    s.turn([ans(s, SL, "8시간")])  # 충돌 -> 확인 대기
    assert s.pend(SLEEP, "hours")
    s.last["awaiting"] = {"action": "ASK_FINISH", "targets": [], "target_pending_id": None, "say_values": []}
    s.last["action"] = "ASK_FINISH"
    out = s.turn([item(0, None, None, "CONFIRM_YES")])
    assert out["flow"] == "CONTINUE"


def test_r6_stop_yes_ends_user_stop_with_notice():
    s = started()
    s.turn([say("STOP")])
    out = s.turn([item(0, None, None, "CONFIRM_YES")])
    assert out["flow"] == "END" and out["progress_record_update"]["session_status"] == "ENDED_USER_STOP"
    assert out["directive"]["action"] == "FAREWELL" and "SURVEY_STOPPED" in kinds(out["directive"])


def test_r6_stop_yes_with_valueless_correction_fixes_first():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    s.turn([say("STOP")])
    out = s.turn([item(0, None, None, "CONFIRM_YES"), item(1, SL, None, "CORRECTION_MARKED")])
    assert out["flow"] == "CONTINUE" and out["directive"]["action"] == "ASK_CORRECTION_TARGET"


def test_r6_correction_target_yes_asks_same_target_again():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    s.turn([item(0, SL, None, "CORRECTION_MARKED")])
    out = s.turn([item(0, None, None, "CONFIRM_YES")])
    assert out["directive"]["action"] == "ASK_CORRECTION_TARGET" and out["directive"]["targets"] == [SL]


def test_r6_correction_target_yes_at_ask_limit_drops_request_and_goes_below():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    s.turn([item(0, SL, None, "CORRECTION_MARKED")])
    s.turn([item(0, None, None, "CONFIRM_YES")])
    out = s.turn([item(0, None, None, "CONFIRM_YES")])
    assert s.open["correction_requests"] == [] and out["directive"]["action"] != "ASK_CORRECTION_TARGET"


# ----- 규칙 6b, 9, 10: 시도 상한 -----
def test_r6b_question_skipped_when_attempts_reach_limit_without_usable_answer():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    assert s.action() == "ASK_NEXT" and tg(s.last) == [SLEEP]
    s.turn([say("WAIT")])  # 판정 없는 턴은 세지 않는다
    assert s.pr["attempt_counts"] == []
    s.turn([ans(s, PN, "약함")])  # 판정은 있으나 수면은 여전히 열려 있음 -> 1
    s.turn([ans(s, NT, "없음")])  # 2
    out = s.turn([ans(s, VT, "주에 두 번")])  # 3 -> 상한
    assert {x["question_id"]: x["reason"] for x in s.skipped}[SLEEP] == "ATTEMPTS_EXCEEDED"
    assert tg(out["directive"]) != ["hours"] and out["directive"]["action"] == "ASK_FINISH"


def test_r9_clarify_then_skip_at_limit():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    s.turn([ans(s, SL, "가끔")])
    assert s.action() == "ASK_CLARIFY" and s.last["reask_reasons"] == ["AMBIGUOUS"]
    assert s.last["say_values"][0]["role"] == "SAID" and s.last["say_values"][0]["value"] == "가끔"
    s.turn([ans(s, SL, "음")]); s.turn([ans(s, SL, "글쎄")])
    assert [x["reason"] for x in s.skipped if x["question_id"] == SLEEP] == ["ATTEMPTS_EXCEEDED"]
    assert tg(s.last) == [VISIT]


def test_r9_clarify_reasons_no_unit_and_range():
    s = started()
    s.turn([ans(s, DR, "안 마시고요"), ans(s, SL, "7시간", n=1)])
    s.turn([ans(s, VT, "두 번")])
    assert s.last["reask_reasons"] == ["NO_UNIT"]


def test_r9_mismatch_pair_is_asked_together_with_current_value_of_other_slot():
    s = started()
    s.turn([ans(s, DR, "마시고요")])
    out = s.turn([ans(s, DR, "안 마시고요", n=0), ans(s, AK, "소주", n=1)])
    d = out["directive"]
    assert d["action"] == "ASK_CLARIFY" and sorted(tg(d)) == ["kind", "status"]
    assert d["reask_reasons"] == ["MISMATCH"]


def test_r9_mismatch_with_current_prerequisite_shows_its_current_value():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    out = s.turn([ans(s, AK, "소주")])
    d = out["directive"]
    assert d["action"] == "ASK_CLARIFY" and tg(d) == ["kind"]
    assert {(v["role"], v["slot"]["slot_id"]) for v in d["say_values"]} == {("SAID", "kind"), ("CURRENT", "status")}


def test_r9_only_first_question_among_several_unclear():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    out = s.turn([ans(s, VT, "두 번"), ans(s, SL, "가끔", n=1)])
    assert tg(out["directive"]) == ["hours"]


def test_r10_missing_slot_is_reasked_with_just_saved_value():
    s = started()
    s.turn([ans(s, DR, "마시고요")])
    out = s.turn([ans(s, AM, "두 병")])
    d = out["directive"]
    assert d["action"] == "ASK_MISSING" and tg(d) == ["kind"] and d["reask_reasons"] == ["MISSING_SLOT"]
    assert [(v["role"], v["value"]) for v in d["say_values"]] == [("JUST_SAVED", {"amount": 2, "unit": "병"})]


def test_r10_missing_skipped_at_limit():
    s = started(); s.qs[1]["policy"]["question_limit"] = 1
    s.turn([ans(s, DR, "마시고요")])
    s.turn([ans(s, AM, "두 병")])
    assert [x["reason"] for x in s.skipped] == ["ATTEMPTS_EXCEEDED"] and tg(s.last) == [SLEEP]


# ----- 규칙 11: 모름·거절 -----
def test_r11_unknown_reasks_then_accepts_as_skip():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    s.turn([item(0, whole(SLEEP), None, "SAYS_UNKNOWN")])
    assert s.action() == "ASK_AFTER_UNKNOWN" and tg(s.last) == ["hours"]
    s.turn([item(0, whole(SLEEP), None, "SAYS_UNKNOWN")])
    assert [(x["question_id"], x["reason"]) for x in s.skipped] == [(SLEEP, "UNKNOWN_ACCEPTED")] and tg(s.last) == [VISIT]


def test_r11_refusal_asks_with_explanation_materials():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    out = s.turn([item(0, SL, None, "SAYS_REFUSAL")])
    d = out["directive"]
    assert d["action"] == "ASK_AFTER_REFUSAL"
    assert d["sentence_materials"]["refusal_explanations"] == [{"question_id": SLEEP, "sentence": "q_sleep 설명입니다"}]
    s.turn([item(0, SL, None, "SAYS_REFUSAL")])
    assert [x["reason"] for x in s.skipped] == ["REFUSAL_ACCEPTED"]


def test_r11_skip_is_released_when_user_answers_later():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    s.turn([item(0, SL, None, "SAYS_UNKNOWN")]); s.turn([item(0, SL, None, "SAYS_UNKNOWN")])
    assert s.skipped
    out = s.turn([ans(s, SL, "7시간")])
    assert out["progress_record_update"]["skipped_remove"] == [SLEEP] and s.skipped == []


def test_r11_unknown_of_already_skipped_question_goes_below():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    s.turn([item(0, SL, None, "SAYS_UNKNOWN")]); s.turn([item(0, SL, None, "SAYS_UNKNOWN")])
    out = s.turn([item(0, SL, None, "SAYS_UNKNOWN")])  # 기록이 같아 바뀌지 않는다
    assert out["directive"]["action"] == "ASK_NEXT" and tg(out["directive"]) == [VISIT]


# ----- 규칙 7: 정정 구체화 -----
def test_r7_valueless_correction_asks_target_with_current_value():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    out = s.turn([item(0, SL, None, "CORRECTION_MARKED")])
    d = out["directive"]
    assert d["action"] == "ASK_CORRECTION_TARGET" and d["targets"] == [SL]
    assert [(v["role"], v["value"]) for v in d["say_values"]] == [("CURRENT", H7)]
    assert out["progress_record_update"]["open_requests"]["correction_requests"] == [{"target": SL}]


def test_r7_untargeted_request_then_answer_clears_it():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    s.turn([item(0, None, None, "CORRECTION_MARKED")])
    assert s.action() == "ASK_CORRECTION_TARGET" and s.last["targets"] == [] and s.last["say_values"] == []
    s.turn([ans(s, SL, "8시간", "CORRECTION_MARKED")])
    assert s.open["correction_requests"] == [] and s.ans(SLEEP, "hours") == {"amount": 8, "unit": "시간"}


def test_r7_targeted_request_clears_untargeted_one():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    s.turn([item(0, None, None, "CORRECTION_MARKED")])
    s.turn([item(0, SL, None, "CORRECTION_MARKED")])
    assert s.open["correction_requests"] == [{"target": SL}]


def test_r7_this_turn_request_before_remaining_one():
    s = started()
    s.turn([ans(s, SL, "7시간"), ans(s, DR, "안 마시고요", n=1)])
    s.turn([item(0, SL, None, "CORRECTION_MARKED"), item(1, SL, None, "CORRECTION_MARKED")])
    s.turn([item(0, DR, None, "CORRECTION_MARKED")])
    assert tg(s.last) == ["status"]
    assert [r["target"] for r in s.open["correction_requests"]] == [SL, DR]


def test_r7_request_dropped_when_value_arrives_or_question_invalidated():
    s = started()
    s.turn([ans(s, DR, "마시고요"), ans(s, AM, "두 병", n=1), ans(s, AK, "소주", n=2)])
    s.turn([item(0, AM, None, "CORRECTION_MARKED")])
    assert s.open["correction_requests"]
    s.turn([ans(s, DR, "안 마시고요", "CORRECTION_MARKED")])  # 후속 문항 무효화
    assert s.open["correction_requests"] == []


def test_r7_ask_limit_removes_request_and_goes_below():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    s.turn([item(0, SL, None, "CORRECTION_MARKED")])  # 1번째
    s.turn([say("WAIT")])  # 대기 안내로 끝나 정정 구체화는 새로 묻지 않음
    s.last["awaiting"] = {"action": "ASK_CORRECTION_TARGET", "targets": [SL], "target_pending_id": None, "say_values": []}
    s.turn([ans(s, VT, "주에 두 번")])  # 2번째 물음(상한 2)
    out = s.turn([ans(s, NT, "없음")])
    assert s.open["correction_requests"] == [] and out["directive"]["action"] != "ASK_CORRECTION_TARGET"


def test_r7_later_moves_unanswered_correction_to_deferred_and_notifies():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    s.turn([item(0, SL, None, "CORRECTION_MARKED")])
    out = s.turn([item(0, whole(SLEEP), None, "PROGRESS_OP", op="LATER")])
    o = out["progress_record_update"]["open_requests"]
    assert o["correction_requests"] == [] and o["deferred"] == [{"kind": "CORRECTION_REQUEST", "target": SL}]
    assert "DEFERRED" in kinds(out["directive"]) and out["directive"]["action"] == "ASK_NEXT"


# ----- 규칙 8, 15, 16, 18: 확인 대기 -----
def conflict_session():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    s.turn([ans(s, SL, "7시간")])
    s.turn([ans(s, SL, "8시간")])
    return s


def test_r15_new_pending_is_confirmed_right_away_with_both_values():
    s = conflict_session()
    d = s.last
    assert d["action"] == "ASK_CONFIRM" and d["targets"] == [SL] and d["target_pending_id"] == s.pend(SLEEP, "hours")["pending_id"]
    assert [(v["role"], v["value"]["amount"]) for v in d["say_values"]] == [("CURRENT", 7), ("PENDING", 8)]
    assert s.pr["confirm_counts"] == [{"slot": SL, "count": 1}]


def test_r8_confirm_yes_accepts_and_acknowledges_correction():
    s = conflict_session()
    out = s.turn([item(0, None, None, "CONFIRM_YES")])
    assert s.ans(SLEEP, "hours")["amount"] == 8 and "CORRECTION_ACK" in kinds(out["directive"])
    assert s.pr["confirm_counts"] == []
    n = out["directive"]["notices"][0]
    assert n["previous_value"]["amount"] == 7 and n["value"]["amount"] == 8


def test_r8_confirm_no_keeps_previous_and_says_so():
    s = conflict_session()
    out = s.turn([item(0, None, None, "CONFIRM_NO")])
    assert s.ans(SLEEP, "hours")["amount"] == 7 and s.pend(SLEEP, "hours") is None
    assert "KEPT_PREVIOUS" in kinds(out["directive"]) and "CORRECTION_ACK" not in kinds(out["directive"])


def test_r8_unusable_answer_repeats_same_confirmation_then_stops_at_limit():
    s = conflict_session()
    s.turn([ans(s, SL, "많이")])  # 애매
    assert s.action() == "ASK_CONFIRM" and s.pr["confirm_counts"] == [{"slot": SL, "count": 2}]
    out = s.turn([ans(s, SL, "음")])  # 확인 상한(2) -> 확인 중단
    p = out["progress_record_update"]
    assert p["confirm_stopped_add"] == [SL] and "KEPT_PREVIOUS" in kinds(out["directive"])
    assert out["directive"]["action"] != "ASK_CONFIRM" and out["directive"]["action"] != "ASK_CLARIFY"


def test_r8_stopped_confirmation_is_not_asked_again_even_with_new_conflict_value():
    s = conflict_session()
    s.turn([ans(s, SL, "많이")]); s.turn([ans(s, SL, "음")])
    assert s.cstop == [SL]
    out = s.turn([ans(s, SL, "9시간")])  # 대체되는 새 값
    assert out["directive"]["action"] != "ASK_CONFIRM"


def test_r8_unrelated_talk_goes_below_and_rule16_asks_again():
    s = conflict_session()
    out = s.turn([ans(s, VT, "주에 두 번")])
    assert out["directive"]["action"] == "ASK_CONFIRM" and out["directive"]["targets"] == [SL]


def test_r8_stop_release_when_pending_resolved():
    s = conflict_session()
    s.turn([ans(s, SL, "많이")]); s.turn([ans(s, SL, "음")])
    out = s.turn([ans(s, SL, "7시간")])  # 현재 값과 같음 -> 버림
    assert out["progress_record_update"]["confirm_stopped_remove"] == [SL] and s.cstop == []


def test_r8_later_moves_pending_to_deferred_and_asks_after_questions():
    s = conflict_session()
    out = s.turn([item(0, whole(SLEEP), None, "PROGRESS_OP", op="LATER")])
    o = out["progress_record_update"]["open_requests"]
    assert o["deferred"] == [{"kind": "PENDING", "target": SL}] and "DEFERRED" in kinds(out["directive"])
    assert out["directive"]["action"] == "ASK_NEXT"  # 남은 문항을 먼저
    s.turn([ans(s, VT, "주에 두 번")]); s.turn([ans(s, PN, "약함")]); s.turn([ans(s, NT, "없음")])
    assert s.action() == "ASK_CONFIRM" and s.last["targets"] == [SL]  # 문항을 다 물은 뒤


def test_r18_deferred_pending_dropped_from_deferral_at_ask_limit():
    s = conflict_session()
    s.turn([item(0, whole(SLEEP), None, "PROGRESS_OP", op="LATER")])
    s.turn([ans(s, VT, "주에 두 번"), ans(s, PN, "약함", n=1), ans(s, NT, "없음", n=2)])
    assert s.action() == "ASK_CONFIRM" and s.pr["ask_counts"] == [{"subject": SL, "count": 1}]
    s.turn([ans(s, NT, "없음")])
    assert s.pr["ask_counts"] == [{"subject": SL, "count": 2}]
    s.turn([ans(s, NT, "없음")])  # 물음 상한: 미룸에서 뺀다
    assert s.open["deferred"] == [] and s.pr["ask_counts"] == []
    assert s.action() == "ASK_CONFIRM"  # 이제 보통의 남은 확인 대기(규칙 16)


def test_r16_remaining_pendings_in_question_order():
    s = started()
    s.turn([ans(s, DR, "안 마시고요"), ans(s, SL, "7시간", n=1)])
    s.turn([ans(s, SL, "8시간"), ans(s, DR, "마시고요", n=1)])
    assert s.action() == "ASK_CONFIRM" and s.last["targets"] == [DR]
    s.turn([item(0, None, None, "CONFIRM_YES")])  # 수면 확인 대기가 남아 있음
    assert s.action() == "ASK_CONFIRM" and s.last["targets"] == [SL]


def test_r15_beats_r16_for_new_pending_over_older_one():
    s = started()
    s.turn([ans(s, DR, "안 마시고요"), ans(s, SL, "7시간", n=1)])
    s.turn([ans(s, DR, "마시고요")])  # 확인 대기(첫 문항)
    s.turn([ans(s, SL, "8시간")])  # 이번 턴에 생긴 수면 확인 대기가 먼저
    assert s.last["targets"] == [SL]


# ----- 규칙 12, 13, 14 -----
def test_r12_guide_request_gives_notice_plus_current_question():
    s = started()
    out = s.turn([item(0, whole(DRINK), None, "GUIDE_REQUEST", guide="g_why")])
    d = out["directive"]
    assert d["action"] == "ASK_NEXT" and kinds(d) == ["GUIDE"] and d["notices"][0]["question_id"] == DRINK
    assert d["sentence_materials"]["guide_sentences"] == [{"guide_id": "g_why", "question_id": DRINK, "sentence": "q_drink 안내"}]


def test_r12_guide_without_target_uses_awaiting_question():
    s = started()
    out = s.turn([item(0, None, None, "GUIDE_REQUEST", guide="g_why")])
    assert out["directive"]["notices"][0]["question_id"] == DRINK


def test_r12_remaining_count_fill_value():
    s = started()
    out = s.turn([item(0, None, None, "GUIDE_REQUEST", guide="g_left")])
    n = out["directive"]["notices"][0]
    assert n["guide_id"] == "g_left" and n["value"] == "5"


def test_r12_guide_values_computed_after_this_turns_writes():
    s = started()
    out = s.turn([ans(s, DR, "안 마시고요"), item(1, None, None, "GUIDE_REQUEST", guide="g_left")])
    assert out["directive"]["notices"][0]["value"] == "4"  # 음주량 문항은 선행 불충족이라 세지 않는다


def test_r12_guide_with_later_keeps_notice_and_defers_question():
    s = started()
    out = s.turn([item(0, None, None, "GUIDE_REQUEST", guide="g_left"), item(1, None, None, "PROGRESS_OP", op="LATER")])
    d = out["directive"]
    assert kinds(d) == ["GUIDE", "DEFERRED"] and tg(d) == [SLEEP] and d["action"] == "ASK_NEXT"
    assert out["progress_record_update"]["open_requests"]["deferred"] == [{"kind": "QUESTION", "target": whole(DRINK)}]


def test_r13_per_question_guide_without_question_is_irrelevant():
    s = Session()
    out = s.turn([item(0, None, None, "GUIDE_REQUEST", guide="g_why")])  # 직전 지시가 없어 대상 문항 없음
    assert out["directive"]["action"] == "REDIRECT"


def test_r13_irrelevant_redirect_with_awaiting():
    s = started()
    out = s.turn([item(0, None, None, "OUT_OF_SCOPE")])
    d = out["directive"]
    assert d["action"] == "REDIRECT" and d["awaiting"]["action"] == "ASK_NEXT" and tg(d["awaiting"]) == [DRINK]
    assert d["sentence_materials"]["fixed_sentences"][0]["key"] == "OOS_NOTICE"


def test_r14_unrecognized_asks_again_then_staff_once():
    s = started()
    out = s.turn([item(0, None, None, "UNRECOGNIZED")])
    assert out["directive"]["action"] == "ASK_REPEAT" and out["directive"]["reask_reasons"] == ["UNRECOGNIZED"]
    assert out["staff_alert"] is None and s.pr["unrecognized_streak"] == 1
    out = s.turn([item(0, None, None, "UNRECOGNIZED")])
    assert out["directive"]["action"] == "STAFF_NOTICE" and out["staff_alert"] == {"kind": "CALL_STAFF", "reasons": []}
    out = s.turn([item(0, None, None, "UNRECOGNIZED")])
    assert out["directive"]["action"] == "ASK_REPEAT" and out["staff_alert"] is None


def test_r14_streak_reset_and_unchanged():
    s = started()
    s.turn([item(0, None, None, "UNRECOGNIZED")])
    s.turn([say("WAIT")])  # 요청만: 그대로
    assert s.pr["unrecognized_streak"] == 1
    s.turn([ans(s, DR, "안 마시고요")])
    assert s.pr["unrecognized_streak"] == 0
    s.turn([item(0, None, None, "UNRECOGNIZED")]); s.turn([item(0, None, None, "OUT_OF_SCOPE")])
    assert s.pr["unrecognized_streak"] == 0


# ----- 규칙 17, 19 -----
def test_r17_next_question_is_by_order_and_skips_closed_ones():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    assert tg(s.last) == [SLEEP]  # 음주량 문항은 선행 불충족이라 묻지 않는다


def test_r17_followup_question_opens_when_prerequisite_met():
    s = started()
    s.turn([ans(s, DR, "마시고요")])
    assert s.action() == "ASK_NEXT" and tg(s.last) == [AMOUNT]


def test_r17_partial_answer_asks_missing_slot_only_with_current_answer():
    s = started()
    s.turn([ans(s, DR, "마시고요")])
    s.turn([ans(s, AM, "두 병")])
    s.turn([say("WAIT")])
    s.turn([ans(s, PN, "약함")])  # 다른 문항에 답했을 뿐, 음주량 문항은 빈 슬롯이 남음
    assert s.action() in ("ASK_MISSING",) and tg(s.last) == ["kind"]
    assert [(v["role"], v["value"]) for v in s.last["say_values"]] == [("CURRENT", {"amount": 2, "unit": "병"})]


def test_r17_later_defers_asked_question_to_the_end():
    s = started()
    out = s.turn([say("LATER")])
    d = out["directive"]
    assert tg(d) == [SLEEP] and kinds(d) == ["DEFERRED"]
    assert out["progress_record_update"]["open_requests"]["deferred"] == [{"kind": "QUESTION", "target": whole(DRINK)}]
    s.turn([ans(s, SL, "7시간")]); s.turn([ans(s, VT, "주에 두 번")]); s.turn([ans(s, PN, "약함")]); s.turn([ans(s, NT, "없음")])
    assert s.action() == "ASK_NEXT" and tg(s.last) == [DRINK]  # 미룬 문항은 맨 뒤
    s.turn([ans(s, DR, "안 마시고요")])
    assert s.open["deferred"] == [] and s.action() == "ASK_FINISH"


def test_r17_same_deferral_not_recorded_twice():
    s = started()
    s.turn([say("LATER")]); s.turn([ans(s, SL, "7시간"), ans(s, VT, "주에 두 번", n=1), ans(s, PN, "약함", n=2), ans(s, NT, "없음", n=3)])
    s.turn([say("LATER")])
    assert len(s.open["deferred"]) == 1


def test_r19_finish_question_and_help_after_ask_limit():
    s = started()
    answered_all(s)
    assert s.action() == "ASK_FINISH" and s.pr["ask_counts"] == [{"subject": {"untargeted": "ASK_FINISH"}, "count": 1}]
    s.turn([item(0, None, None, "CONFIRM_NO")])  # 거부: 종료 확인 기다리는 중의 아니요는 사실을 바꾸지 않음
    assert s.action() == "ASK_FINISH"
    out = s.turn([item(0, None, None, "CONFIRM_NO")])
    assert out["directive"]["action"] == "STAFF_NOTICE" and out["staff_alert"] == {"kind": "CALL_STAFF", "reasons": []}
    assert out["directive"]["awaiting"]["action"] == "ASK_FINISH"
    out = s.turn([item(0, None, None, "CONFIRM_NO")])
    assert out["staff_alert"] is None and out["directive"]["action"] == "ASK_FINISH"


# ----- 8-2: 판단에 쓰는 값 -----
def test_82_notice_order_ack_then_kept_then_guide_then_rule_notices():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    s.turn([ans(s, VT, "주에 두 번")])
    s.turn([ans(s, SL, "8시간")])  # 충돌
    out = s.turn([item(0, SL, "9시간", "CORRECTION_MARKED"), item(1, None, None, "GUIDE_REQUEST", guide="g_left"),
                  item(2, None, None, "PROGRESS_OP", op="LATER")])
    assert kinds(out["directive"])[:2] == ["CORRECTION_ACK", "GUIDE"]
    assert kinds(out["directive"]).count("CORRECTION_ACK") == 1


def test_82_kept_previous_when_pending_dropped_and_value_unchanged():
    s = conflict_session()
    out = s.turn([ans(s, SL, "7시간")])
    assert kinds(out["directive"])[0] == "KEPT_PREVIOUS" and out["directive"]["notices"][0]["value"]["amount"] == 7


def test_82_attempt_counts_only_unusable_turns():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    s.turn([ans(s, SL, "가끔")])
    assert s.pr["attempt_counts"] == [{"question_id": SLEEP, "count": 1}]
    s.turn([say("REPEAT")]); s.turn([item(0, None, None, "OUT_OF_SCOPE")])
    assert s.pr["attempt_counts"] == [{"question_id": SLEEP, "count": 1}]
    s.turn([ans(s, SL, "8시간")])  # 정상 답: 문항이 닫혀 세지 않는다
    assert s.pr["attempt_counts"] == []  or s.pr["attempt_counts"] == [{"question_id": SLEEP, "count": 1}]


def test_82_attempts_cleared_for_invalidated_question():
    s = started()
    s.turn([ans(s, DR, "마시고요")])
    s.turn([ans(s, AM, "많이"), ])
    assert {"question_id": AMOUNT, "count": 1} in s.pr["attempt_counts"]
    s.turn([ans(s, DR, "안 마시고요", "CORRECTION_MARKED")])
    assert all(c["question_id"] != AMOUNT for c in s.pr["attempt_counts"])


def test_82_unknown_and_refusal_counts_per_question_turn():
    s = started()
    s.turn([ans(s, DR, "마시고요")])
    s.turn([item(0, AM, None, "SAYS_UNKNOWN"), item(1, AK, None, "SAYS_REFUSAL")])
    assert s.pr["unknown_counts"] == [{"question_id": AMOUNT, "count": 1}]
    assert s.pr["refusal_counts"] == [{"question_id": AMOUNT, "count": 1}]
    s.turn([item(0, whole(SLEEP), None, "SAYS_UNKNOWN")])
    assert {"question_id": SLEEP, "count": 1} in s.pr["unknown_counts"]


def test_82_asked_counts_reset_when_request_resolved():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    s.turn([item(0, SL, None, "CORRECTION_MARKED")])
    assert s.pr["ask_counts"] == [{"subject": SL, "count": 1}]
    s.turn([ans(s, SL, "8시간", "CORRECTION_MARKED")])
    assert s.pr["ask_counts"] == []


def test_82_invalidated_question_cleared_from_deferral_and_attempts():
    s = started()
    s.turn([ans(s, DR, "마시고요")])
    s.turn([say("LATER")])
    assert s.open["deferred"]
    s.turn([ans(s, DR, "안 마시고요", "CORRECTION_MARKED")])
    assert s.open["deferred"] == []


# ----- 8-4: 어떤 경우에도 지키는 것 -----
def test_84_answer_in_same_utterance_is_saved_regardless_of_request():
    s = started()
    s.turn([ans(s, DR, "안 마시고요"), item(1, None, None, "GUIDE_REQUEST", guide="g_left")])
    assert s.ans(DRINK, "status") == "안 마심"


def test_84_values_in_directive_match_records_after_write():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    s.turn([ans(s, SL, "8시간")])
    for v in s.last["say_values"]:
        if v["role"] == "CURRENT":
            assert v["value"] == s.ans(SLEEP, "hours")
        if v["role"] == "PENDING":
            assert v["value"] == s.pend(SLEEP, "hours")["value"]


def test_84_one_action_per_turn_and_skipped_never_asked_again():
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    s.turn([item(0, SL, None, "SAYS_UNKNOWN")]); s.turn([item(0, SL, None, "SAYS_UNKNOWN")])
    for text in ("가끔", "음"):
        s.turn([ans(s, VT, text)])
        assert SLEEP not in [t["question_id"] for t in s.last["targets"]]


def test_84_cooperating_user_reaches_complete_end():
    s = started()
    answers = [ans(s, DR, "마시고요"), ans(s, AM, "두 병"), ans(s, AK, "소주"), ans(s, SL, "7시간"),
               ans(s, VT, "주에 두 번"), ans(s, PN, "약함"), ans(s, NT, "없음")]
    for a in answers:
        s.turn([a])
    assert s.action() == "ASK_FINISH"
    s.turn([item(0, None, None, "CONFIRM_YES")])
    assert s.flow == "END" and s.status == "ENDED_COMPLETE"


def test_84_stubborn_user_still_ends_in_finite_turns():
    # 계속 애매·모름·거절만 하는 사용자도 건너뜀으로 끝에 닿는다
    s = started()
    for n in range(60):
        if s.flow == "END" or s.action() == "ASK_FINISH":
            break
        t = s.last["targets"][0] if s.last["targets"] else None
        mode = n % 3
        if t is None:
            s.turn([item(0, None, None, "UNRECOGNIZED")])
        elif mode == 0:
            s.turn([item(0, t, "음 글쎄")])
        elif mode == 1:
            s.turn([item(0, t, None, "SAYS_UNKNOWN")])
        else:
            s.turn([item(0, t, None, "SAYS_REFUSAL")])
    assert s.action() == "ASK_FINISH"


def test_84_user_who_keeps_changing_confirmed_value_ends():
    s = started()
    s.turn([ans(s, DR, "안 마시고요"), ans(s, SL, "7시간", n=1)])
    for h in range(8, 20):
        s.turn([ans(s, SL, f"{h}시간")])
    # 확인 대기가 계속 새 값으로 대체되어도 확인 상한(2)에서 확인 중단이 일어나 더 묻지 않는다
    assert s.cstop == [SL] and s.action() != "ASK_CONFIRM"


def test_84_user_who_keeps_refusing_finish_gets_staff_help():
    s = started()
    answered_all(s)
    for _ in range(4):
        s.turn([item(0, None, None, "CONFIRM_NO")])
    assert [a["kind"] for a in s.alerts].count("CALL_STAFF") == 1


def test_84_correction_possible_from_any_state():
    # 건너뛴 문항, 확인 중단 슬롯도 정정으로 원하는 값으로 바꿀 수 있다
    s = started()
    s.turn([ans(s, DR, "안 마시고요")])
    s.turn([item(0, SL, None, "SAYS_UNKNOWN")]); s.turn([item(0, SL, None, "SAYS_UNKNOWN")])
    s.turn([ans(s, SL, "6시간", "CORRECTION_MARKED")])
    assert s.ans(SLEEP, "hours")["amount"] == 6


# ----- 입력 불변과 결정성 -----
def test_input_not_mutated_and_deterministic():
    s = started()
    s.turn([ans(s, SL, "7시간")])
    s.turn([ans(s, SL, "8시간")])
    inp = s.plan_input("UTTERANCE", {"result": "REQUEST_ONLY", "valueless_correction_requests": [], "confirmation": "NONE",
                                      "requests": [{"kind": "WAIT", "guide_id": None, "target_question_id": None, "source_text": ["잠깐"]}],
                                      "risk_signal": None}, [], {"changed_slots": [], "unknown_refused_records": [], "created_pendings": [],
                                                                  "resolved_pendings": [], "invalidated_questions": []})
    before = deep(inp)
    a, b = plan(inp), plan(inp)
    assert inp == before and a == b
