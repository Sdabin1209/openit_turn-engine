"""Answer Normalizer 규칙 시험. 규칙 문장은 docs/rules/answer_normalizer.md (5절)의 번호를 따른다."""
import pytest
from fixtures import *
from turn_engine import normalize, ContractViolation


def chk(items, **kw):
    r = normalize(normalizer_input(items, **kw))
    return r["item_checks"], r["missing_required_slots"]


def one(text, slot=None, **kw):
    slot = slot or ref(SLEEP, "hours")
    return chk([item(0, slot, text)], **kw)[0][0]


# ----- 규칙 1: 단위 -----
def test_n1_unit_less_number_single_unit_slot_uses_that_unit():
    c = one("일곱이요")
    assert c["standard_value"] == {"amount": 7, "unit": "시간"} and c["problems"] == []


def test_n1_unit_less_number_multi_unit_slot_is_no_unit():
    c = one("두 번이요", ref(VISIT, "times"))
    assert c["standard_value"] is None and c["problems"] == ["NO_UNIT"]


def test_n1_other_name_is_same_unit():
    c = one("7시간쯤")
    assert c["standard_value"] == {"amount": 7, "unit": "시간"}


def test_n1_converted_unit_is_standardized_to_target_unit():
    c = one("세 잔", ref(AMOUNT, "amount"), currents=[cur(ref(DRINK, "status"), "마심")])
    assert c["standard_value"] == {"amount": 0.6, "unit": "병"}


def test_n1_converted_unit_counts_as_another_unit():
    # 병과 잔은 서로 다른 단위이므로 단위 없는 숫자는 NO_UNIT
    c = one("세 개요", ref(AMOUNT, "amount"), currents=[cur(ref(DRINK, "status"), "마심")])
    assert c["problems"] == ["NO_UNIT"]


# ----- 규칙 2: 어림, 범위, 풀 수 없는 값 -----
def test_n2_approximation_is_that_value_with_metadata():
    c = one("7시간 정도")
    assert c["standard_value"] == {"amount": 7, "unit": "시간"}
    assert c["value_metadata"]["precision"] == "approximate"


def test_n2_range_is_ambiguous_only_even_without_unit():
    c = one("두세 병", ref(AMOUNT, "amount"), currents=[cur(ref(DRINK, "status"), "마심")])
    assert c["problems"] == ["AMBIGUOUS"] and c["standard_value"] is None
    c = one("두세 번", ref(VISIT, "times"))
    assert c["problems"] == ["AMBIGUOUS"]  # NO_UNIT를 더하지 않는다


def test_n2_unresolvable_words_are_ambiguous():
    assert one("가끔")["problems"] == ["AMBIGUOUS"]
    assert one("가끔", ref(DRINK, "status"))["problems"] == ["AMBIGUOUS"]


def test_n2_negative_value_is_the_no_choice():
    c = one("안 마시고요", ref(DRINK, "status"))
    assert c["standard_value"] == "안 마심" and c["problems"] == []


# ----- 규칙 8: 말을 선택지·단위에 잇는 기준 -----
def test_n8_choice_name_contained():
    assert one("소주요", ref(AMOUNT, "kind"), currents=[cur(ref(DRINK, "status"), "마심")])["standard_value"] == "소주"


def test_n8_stem_contained_means_the_choice():
    assert one("마시고요", ref(DRINK, "status"))["standard_value"] == "마심"


def test_n8_two_matches_is_ambiguous_not_invented():
    c = one("소주도 맥주도", ref(AMOUNT, "kind"), currents=[cur(ref(DRINK, "status"), "마심")])
    assert c["problems"] == ["AMBIGUOUS"]


def test_n8_nothing_matches_is_ambiguous():
    assert one("그냥요", ref(AMOUNT, "kind"), currents=[cur(ref(DRINK, "status"), "마심")])["problems"] == ["AMBIGUOUS"]


def test_n8_unit_matching_two_units_is_ambiguous():
    c = one("두 병 두 잔", ref(AMOUNT, "amount"), currents=[cur(ref(DRINK, "status"), "마심")])
    assert c["problems"] == ["AMBIGUOUS"]


def test_n8_choice_catalog_synonyms_to_coded_value():
    qs = questions()
    qs[0]["slots"][0] = slot_def("status", catalog=[
        {"code": "C1", "label": "마심", "synonyms": ["한잔해요"]}, {"code": "C2", "label": "안 마심", "synonyms": []}],
        yn={"yes": "C1", "no": "C2"})
    r = normalize(normalizer_input([item(0, ref(DRINK, "status"), "한잔해요")], qs=qs))
    assert r["item_checks"][0]["standard_value"] == {"code": "C1", "label": "마심"}


# ----- 범위 / 위험 기준 (규칙 7) -----
def test_n7_out_of_range_is_a_problem_without_standard_value():
    c = one("30시간")
    assert c["problems"] == ["OUT_OF_RANGE"] and c["standard_value"] is None


def test_n7_risk_rule_hit():
    c = one("심함이요", ref(PAIN, "level"))
    assert c["standard_value"] == "심함" and c["risk_rule"] == "IMMEDIATE"
    assert one("약함이요", ref(PAIN, "level"))["risk_rule"] is None


def test_n7_unknown_target_is_marked_not_dropped():
    cs, _ = chk([item(0, ref("q_none", "x"), "네")])
    assert cs[0]["problems"] == ["UNKNOWN_TARGET"] and cs[0]["vs_current"] == "NOT_APPLICABLE"
    cs, _ = chk([item(0, ref(SLEEP, "nope"), "네")])
    assert cs[0]["problems"] == ["UNKNOWN_TARGET"]


# ----- 규칙 5, 6: 비교 -----
def test_n5_current_unknown_or_refusal_means_no_current():
    for v in ("U", "R", None):
        c = one("7시간", currents=[cur(ref(SLEEP, "hours"), v)])
        assert c["vs_current"] == "NO_CURRENT"


def test_n_vs_current_and_pending():
    s = ref(SLEEP, "hours")
    assert one("7시간", currents=[cur(s, {"amount": 7, "unit": "시간"})])["vs_current"] == "EQUAL"
    assert one("8시간", currents=[cur(s, {"amount": 7, "unit": "시간"})])["vs_current"] == "DIFFERENT"
    p = [{"pending_id": "p1", "slot": s, "value": {"amount": 8, "unit": "시간"}}]
    c = one("8시간", currents=[cur(s, {"amount": 7, "unit": "시간"})], pendings=p)
    assert c["vs_pending"] == "EQUAL"
    assert one("9시간", pendings=p)["vs_pending"] == "DIFFERENT"


def test_n6_items_without_standard_value_are_not_applicable():
    c = one("가끔", currents=[cur(ref(SLEEP, "hours"), {"amount": 7, "unit": "시간"})])
    assert c["vs_current"] == "NOT_APPLICABLE" and c["vs_pending"] == "NOT_APPLICABLE"
    cs, _ = chk([item(0, ref(SLEEP, "hours"), None, "SAYS_UNKNOWN")])
    assert cs[0]["vs_current"] == "NOT_APPLICABLE"


# ----- 규칙 3, 4: 선행 슬롯과 후속 항목 -----
DRINK_YES = [cur(ref(DRINK, "status"), "마심")]


def test_n4_followup_with_matching_prerequisite_is_ok():
    cs, _ = chk([item(0, ref(AMOUNT, "kind"), "소주")], currents=DRINK_YES)
    assert not cs[0]["prerequisite_unmet"] and cs[0]["problems"] == []


def test_n4_no_prerequisite_answer_is_unmet():
    cs, _ = chk([item(0, ref(AMOUNT, "kind"), "소주")])
    assert cs[0]["prerequisite_unmet"]


def test_n4_prerequisite_unknown_or_refusal_is_unmet():
    for v in ("U", "R"):
        cs, _ = chk([item(0, ref(AMOUNT, "kind"), "소주")], currents=[cur(ref(DRINK, "status"), v)])
        assert cs[0]["prerequisite_unmet"]


def test_n3_prerequisite_value_from_this_utterance_is_used():
    cs, _ = chk([item(0, ref(DRINK, "status"), "마시고요"), item(1, ref(AMOUNT, "kind"), "소주")])
    assert not cs[1]["prerequisite_unmet"] and cs[1]["problems"] == []


def test_n3_prerequisite_unknown_in_this_utterance_means_no_answer():
    cs, _ = chk([item(0, ref(DRINK, "status"), None, "SAYS_UNKNOWN"), item(1, ref(AMOUNT, "kind"), "소주")],
                currents=DRINK_YES)
    assert cs[1]["prerequisite_unmet"]


def test_n3_confirm_yes_uses_pending_value():
    s = ref(DRINK, "status")
    aw = {"action": "ASK_CONFIRM", "targets": [s], "target_pending_id": "p1"}
    p = [{"pending_id": "p1", "slot": s, "value": "마심"}]
    cs, _ = chk([item(0, None, None, "CONFIRM_YES"), item(1, ref(AMOUNT, "kind"), "소주")],
                currents=[cur(s, "안 마심")], pendings=p, awaiting=aw)
    assert not cs[1]["prerequisite_unmet"]


def test_n4_conflicting_prerequisite_makes_followup_unmet():
    # 현재값은 안 마심, 이번에 마심이라고 하며 소주도 말함(정정 표지 없음): 충돌이 될 값이라 아직 확정이 아니다
    cs, _ = chk([item(0, ref(DRINK, "status"), "마시고요"), item(1, ref(AMOUNT, "kind"), "소주")],
                currents=[cur(ref(DRINK, "status"), "안 마심")])
    assert cs[1]["prerequisite_unmet"]
    # 정정 표지가 있으면 확정된 값
    cs, _ = chk([item(0, ref(DRINK, "status"), "마시고요", "CORRECTION_MARKED"), item(1, ref(AMOUNT, "kind"), "소주")],
                currents=[cur(ref(DRINK, "status"), "안 마심")])
    assert not cs[1]["prerequisite_unmet"]


def test_n4_value_that_does_not_match_condition_is_mismatch_on_both():
    # B4: 술 안 마신다는 말과 소주를 마신다는 말이 같이 옴
    cs, _ = chk([item(0, ref(DRINK, "status"), "안 마시고요"), item(1, ref(AMOUNT, "kind"), "소주")])
    assert cs[1]["problems"] == ["MISMATCH"] and cs[1]["mismatched_slots"] == [ref(DRINK, "status")]
    assert cs[0]["problems"] == ["MISMATCH"] and cs[0]["mismatched_slots"] == [ref(AMOUNT, "kind")]
    assert not cs[1]["prerequisite_unmet"]


def test_n4_mismatch_from_current_value_flags_only_followup():
    cs, _ = chk([item(0, ref(AMOUNT, "kind"), "소주")], currents=[cur(ref(DRINK, "status"), "안 마심")])
    assert cs[0]["problems"] == ["MISMATCH"] and cs[0]["mismatched_slots"] == [ref(DRINK, "status")]


def test_n4_negative_unknown_refusal_or_later_are_unmet_not_mismatch():
    cur_no = [cur(ref(DRINK, "status"), "안 마심")]
    for it in (item(0, ref(AMOUNT, "kind"), None, "SAYS_UNKNOWN"), item(0, ref(AMOUNT, "kind"), None, "SAYS_REFUSAL"),
               item(0, ref(AMOUNT, "kind"), None, "CORRECTION_MARKED"), item(0, ref(AMOUNT, "kind"), "가끔"),
               item(0, ref(AMOUNT, "kind"), None, "PROGRESS_OP", op="LATER")):
        cs, _ = chk([it], currents=cur_no)
        assert cs[0]["prerequisite_unmet"] and "MISMATCH" not in cs[0]["problems"], it


def test_n4_negative_value_of_followup_is_unmet():
    qs = questions()
    qs[1]["slots"][1] = slot_def("kind", choices=["소주", "안 마심"], yn={"yes": "소주", "no": "안 마심"})
    r = normalize(normalizer_input([item(0, ref(AMOUNT, "kind"), "안 마시고요")], currents=[cur(ref(DRINK, "status"), "안 마심")], qs=qs))
    assert r["item_checks"][0]["prerequisite_unmet"] and r["item_checks"][0]["problems"] == []


def test_n4_confirm_item_of_unmet_question_is_unmet():
    s = ref(AMOUNT, "kind")
    aw = {"action": "ASK_CONFIRM", "targets": [s], "target_pending_id": "p1"}
    p = [{"pending_id": "p1", "slot": s, "value": "맥주"}]
    cs, _ = chk([item(0, None, None, "CONFIRM_YES")], currents=[cur(ref(DRINK, "status"), "안 마심")], pendings=p, awaiting=aw)
    assert cs[0]["prerequisite_unmet"]


# ----- 빠진 필수 슬롯 -----
def test_missing_required_slots_of_touched_question():
    cs, miss = chk([item(0, ref(AMOUNT, "amount"), "두 병")], currents=DRINK_YES)
    assert miss == [ref(AMOUNT, "kind")]


def test_no_missing_when_other_slot_is_answered_unknown_or_in_current():
    _, miss = chk([item(0, ref(AMOUNT, "amount"), "두 병")], currents=DRINK_YES + [cur(ref(AMOUNT, "kind"), "소주")])
    assert miss == []
    _, miss = chk([item(0, ref(AMOUNT, "amount"), "두 병"), item(1, ref(AMOUNT, "kind"), None, "SAYS_UNKNOWN")], currents=DRINK_YES)
    assert miss == []


def test_no_missing_for_untouched_or_unmet_question():
    _, miss = chk([item(0, ref(SLEEP, "hours"), "7시간")])
    assert miss == []
    _, miss = chk([item(0, ref(AMOUNT, "amount"), "두 병")])  # 선행 불충족
    assert miss == []


def test_optional_slots_are_never_missing():
    qs = questions()
    qs[2]["slots"].append(slot_def("extra", required=False))
    r = normalize(normalizer_input([item(0, ref(SLEEP, "hours"), "7시간")], qs=qs))
    assert r["missing_required_slots"] == []


# ----- 계약 -----
def test_contract_violation_on_bad_input():
    bad = normalizer_input([item(0, ref(SLEEP, "hours"), "7")])
    del bad["pendings"]
    with pytest.raises(ContractViolation) as e:
        normalize(bad)
    assert "pendings" in str(e.value) or e.value.errors
    bad = normalizer_input([item(0, ref(SLEEP, "hours"), "7")])
    bad["items"][0]["intent"] = "NOPE"
    with pytest.raises(ContractViolation):
        normalize(bad)


def test_violation_message_does_not_contain_input_values():
    bad = normalizer_input([item(0, ref(SLEEP, "hours"), "민감한말")])
    bad["items"][0]["intent"] = "NOPE"
    with pytest.raises(ContractViolation) as e:
        normalize(bad)
    assert "민감한말" not in str(e.value) and "NOPE" not in str(e.value)


def test_input_is_not_mutated():
    inp = normalizer_input([item(0, ref(AMOUNT, "amount"), "두 병"), item(1, ref(DRINK, "status"), "안 마시고요")],
                           currents=DRINK_YES)
    before = deep(inp)
    normalize(inp)
    assert inp == before
