"""시험용 문항 정의와 입력 조립 도구. 값은 설명용 예시이며 실제 문항 값이 아니다."""
from __future__ import annotations

import copy

DRINK, AMOUNT, SLEEP, VISIT, PAIN, NOTE = "q_drink", "q_amount", "q_sleep", "q_visit", "q_pain", "q_note"


def ref(q, slot, rk=""):
    return {"question_id": q, "repeat_key": rk, "slot_id": slot}


def whole(q):
    return {"question_id": q, "whole_question": True}


def slot_def(slot_id, *, units=None, choices=None, yn=None, required=True, risk=None, catalog=None):
    d = {"slot_id": slot_id, "units": units or [], "choices": choices or [], "yes_no_map": yn,
         "required": required, "reask_sentence": f"{slot_id}를 다시 말씀해 주세요", "risk_rule": risk}
    if catalog:
        d["choice_catalog"] = catalog
        d["choices"] = []
    return d


def unit(name, synonyms=None, rng=None, conv=None, code=None):
    u = {"name": name, "synonyms": synonyms or [], "range": rng, "convert_to": conv}
    if code:
        u["code"] = code
    return u


def qdef(qid, order, slots, *, prereq=None, followups=None, limit=3, unk=2, ref_after=2, repeat_keys=None):
    return {
        "question_id": qid, "name": f"이름_{qid}", "order": order, "prerequisite": prereq,
        "question_sentence": f"{qid} 질문입니다", "refusal_explanation": f"{qid} 설명입니다",
        "guide_sentences": [{"guide_id": "g_why", "sentence": f"{qid} 안내"}],
        "affected_followups": followups or [],
        "policy": {"question_limit": limit, "unknown_accept_after": unk, "refusal_accept_after": ref_after},
        "repeat_keys": repeat_keys or [], "slots": slots,
    }


def questions():
    return [
        qdef(DRINK, 1, [slot_def("status", choices=["마심", "안 마심"], yn={"yes": "마심", "no": "안 마심"})],
             followups=[AMOUNT]),
        qdef(AMOUNT, 2, [
            slot_def("amount", units=[unit("병", ["병째"], [0, 30]),
                                      unit("잔", ["컵"], None, {"unit": "병", "factor": 0.2})]),
            slot_def("kind", choices=["소주", "맥주"]),
        ], prereq={"slot": ref(DRINK, "status"), "value": "마심"}),
        qdef(SLEEP, 3, [slot_def("hours", units=[unit("시간", ["시간쯤"], [0, 24])])]),
        qdef(VISIT, 4, [slot_def("times", units=[unit("주", ["주에", "일주일"]), unit("월", ["달에", "한달"])])]),
        qdef(PAIN, 5, [slot_def("level", choices=["약함", "심함"],
                                risk={"operator": "=", "value": "심함", "response": "IMMEDIATE"})]),
        qdef(NOTE, 6, [slot_def("text", required=False)]),
    ]


def settings(**kw):
    s = {
        "risk_phrases": ["가슴이 아파"], "confirm_limit": 2, "unrecognized_streak_limit": 2, "ask_limit": 2,
        "fixed_sentences": [{"key": k, "sentence": f"고정문장 {k}"} for k in
                            ["ASK_REPEAT", "OOS_NOTICE", "CALL_STAFF", "FAREWELL", "ASK_CONFIRM",
                             "ASK_CORRECTION_TARGET", "ASK_FINISH", "RISK_NOTICE", "RESUME", "SURVEY_STOPPED",
                             "WAIT_NOTICE", "ASK_STOP", "STAFF_NOTICE", "DEFERRED"]],
        "guide_list": [
            {"guide_id": "g_why", "selection_criterion": "왜 묻는지", "per_question": True, "sentence": None, "fill_value": None},
            {"guide_id": "g_left", "selection_criterion": "남은 문항 수", "per_question": False,
             "sentence": "남은 문항이 있어요", "fill_value": "REMAINING_COUNT"},
        ],
    }
    s.update(kw)
    return s


def item(n, target, value, intent="ANSWERED_INTENT", *, text=None, op=None, guide=None):
    return {"item_no": n, "target": target, "value": value, "source_text": text or (value or "발화"),
            "intent": intent, "progress_op": op, "guide_id": guide}


def cur(slot, v):
    """v: None(없음), 'U', 'R', 또는 값."""
    cv = "NONE" if v is None else "UNKNOWN_RECORD" if v == "U" else "REFUSAL_RECORD" if v == "R" else {"answer": v}
    return {"slot": slot, "current_value": cv}


def normalizer_input(items, *, currents=None, pendings=None, awaiting=None, qs=None, turn_index=1):
    return {"items": items, "related_questions": qs or questions(), "current_values": currents or [],
            "pendings": pendings or [], "awaiting": awaiting, "turn_index": turn_index}


def deep(x):
    return copy.deepcopy(x)


def judge_input(items, checks, *, missing=None, last=None, pendings=None, utterance="발화"):
    qs = questions()
    return {
        "items": items, "item_checks": checks, "missing_required_slots": missing or [], "utterance": utterance,
        "risk_phrases": ["가슴이 아파"], "last_directive": last, "pendings": pendings or [],
        "affected_followups": [{"question_id": q["question_id"], "followups": q["affected_followups"]}
                               for q in qs if q["affected_followups"]],
        "question_slots": [{"question_id": q["question_id"], "slot_ids": [s["slot_id"] for s in q["slots"]]} for q in qs],
    }
