"""Dialogue Planner: 다음에 무엇을 말할지 정하고 응답 지시와 진행·Plan 기록 갱신을 만든다.
규칙 출처: docs/rules/dialogue_planner.md (8절). 규칙 번호는 문서의 (규칙 N)을 따른다. 대응표는 docs/design.md."""
from __future__ import annotations

import copy

from ._common import (
    ContractViolation, check_input, check_output, is_slot, is_whole, ref_of, skey, tkey, uniq, value_matches_text,
)
from .judge import awaiting_of

ASK_Q_ACTIONS = ("ASK_NEXT", "ASK_MISSING", "ASK_CLARIFY", "ASK_AFTER_UNKNOWN", "ASK_AFTER_REFUSAL")
FIXED_KEY_OF_ACTION = {
    "ASK_REPEAT": "ASK_REPEAT", "REDIRECT": "OOS_NOTICE", "CALL_STAFF": "CALL_STAFF", "FAREWELL": "FAREWELL",
    "ASK_CONFIRM": "ASK_CONFIRM", "ASK_CORRECTION_TARGET": "ASK_CORRECTION_TARGET", "ASK_FINISH": "ASK_FINISH",
    "RISK_NOTICE": "RISK_NOTICE", "WAIT_NOTICE": "WAIT_NOTICE", "ASK_STOP": "ASK_STOP", "STAFF_NOTICE": "STAFF_NOTICE",
}
FIXED_KEY_OF_NOTICE = {"RESUME": "RESUME", "SURVEY_STOPPED": "SURVEY_STOPPED", "DEFERRED": "DEFERRED"}
VALUE_STATUSES = ("ANSWERED", "CORRECTION")


def plan(input: dict) -> dict:
    """(DialoguePlannerInput) -> PlannerOutput. 순수 함수."""
    check_input("DialoguePlannerInput", input)
    out = _Planner(input).run()
    check_output("PlannerOutput", out)
    return out


def _whole(qid):
    return {"question_id": qid, "whole_question": True}


class _Ask:
    """묻는 행동 하나. commit은 이 행동이 실제 행동이 될 때만 부르는 횟수 갱신이다."""

    def __init__(self, action, targets=None, pending_id=None, say_values=None, reasons=None, commit=None):
        self.action = action
        self.targets = targets or []
        self.pending_id = pending_id
        self.say_values = say_values or []
        self.reasons = reasons or []
        self.commit = commit

    def as_ask_directive(self):
        return {"action": self.action, "targets": copy.deepcopy(self.targets), "target_pending_id": self.pending_id,
                "say_values": copy.deepcopy(self.say_values)}


class _Planner:
    def __init__(self, inp):
        self.inp = inp
        self.kind = inp["turn_kind"]
        self.J = inp["utterance_judgment"]
        if self.kind == "UTTERANCE" and self.J is None:
            raise ContractViolation("DialoguePlannerInput", ["utterance_judgment: UTTERANCE 턴에는 필요하다"])
        if self.J is None:  # 발화가 아닌 턴: 아무 말도 없었던 것으로 본다
            self.J = {"result": "HAS_ANSWER", "valueless_correction_requests": [], "confirmation": "NONE",
                      "requests": [], "risk_signal": None}
        self.guide_requests = []
        self.ignored_judgments = []
        self.judgments = inp["judgments"] if self.kind == "UTTERANCE" else []
        self.summary = inp["store_summary"] or {
            "changed_slots": [], "unknown_refused_records": [], "created_pendings": [],
            "resolved_pendings": [], "invalidated_questions": []}
        bank = inp["question_bank"]
        self.settings = bank["session_settings"]
        self.qs = sorted(bank["questions"], key=lambda q: (q["order"], q["question_id"]))
        self.qmap = {q["question_id"]: q for q in self.qs}
        self.rec = {skey(r["slot"]): r for r in inp["answer_records"]}
        self.last = inp["last_directive"]
        self.aw = awaiting_of(self.last)
        # 작업 상태(입력을 바꾸지 않는다)
        self.skipped = {s["question_id"]: s["reason"] for s in inp["skipped"]}
        self.skipped_add = []
        self.skipped_remove = []
        self.cstop = [skey(s) for s in inp["confirm_stopped"]]
        self.cstop_add, self.cstop_remove = [], []
        o = inp["open_requests"]
        self.corr = copy.deepcopy(o["correction_requests"])
        self.stop_requested = o["stop_requested"]
        self.deferred = copy.deepcopy(o["deferred"])
        pr = inp["planner_record"]
        self.attempts = {x["question_id"]: x["count"] for x in pr["attempt_counts"]}
        self.confirm_counts = {skey(x["slot"]): x["count"] for x in pr["confirm_counts"]}
        self.unknown_counts = {x["question_id"]: x["count"] for x in pr["unknown_counts"]}
        self.refusal_counts = {x["question_id"]: x["count"] for x in pr["refusal_counts"]}
        self.streak = pr["unrecognized_streak"]
        self.ask_counts = {self.subj_key(x["subject"]): [x["subject"], x["count"]] for x in pr["ask_counts"]}
        self.notices_early, self.notices_late = [], []
        self.session_status = None
        self.pause_add = []
        self.staff_alert = None
        self.flow = "CONTINUE"

    # =============== 조회 도우미 ===============
    @staticmethod
    def subj_key(subject):
        if "untargeted" in subject:
            return ("U", subject["untargeted"])
        return tkey(subject)

    def cur(self, key):
        r = self.rec.get(key)
        return r["current_value"] if r else "NONE"

    def answer(self, key):
        c = self.cur(key)
        return c["answer"] if isinstance(c, dict) else None

    def pending(self, key):
        r = self.rec.get(key)
        return r["pending"] if r else None

    def state(self, key):
        c = self.cur(key)
        if isinstance(c, dict):
            return "ANS"
        return {"UNKNOWN_RECORD": "UNK", "REFUSAL_RECORD": "REF"}.get(c, "NONE")

    def rks(self, q):
        return q["repeat_keys"] or [""]

    def active_rks(self, q):
        """반복 키가 있는 문항은 답이 있는 반복 키만 본다. 하나도 없으면 첫 반복 키(골든 V2: 선택 슬롯은 한 반복 키에 답이 있으면 닫힌다)."""
        rks = self.rks(q)
        qid = q["question_id"]
        act = [rk for rk in rks if any(self.state((qid, rk, s["slot_id"])) != "NONE" for s in q["slots"])]
        return act or rks[:1]

    def slot_keys(self, q):
        return [(q["question_id"], rk, s["slot_id"]) for rk in self.rks(q) for s in q["slots"]]

    def qname(self, qid):
        return self.qmap[qid]["name"] if qid in self.qmap else qid

    def prereq_ok(self, q):
        c = q["prerequisite"]
        if not c:
            return True
        v = self.answer(skey(c["slot"]))
        return v is not None and value_matches_text(v, c["value"])

    def q_open(self, q):
        """열린 문항(건너뜀 제외): 선행 조건 충족, 그리고 빈 필수 슬롯 또는 수용 시점 전의 모름·거절 슬롯."""
        if not self.prereq_ok(q):
            return False
        qid = q["question_id"]
        ua, ra = q["policy"]["unknown_accept_after"], q["policy"]["refusal_accept_after"]
        for rk in self.active_rks(q):
            keys = [(qid, rk, s["slot_id"]) for s in q["slots"]]
            req = [(qid, rk, s["slot_id"]) for s in q["slots"] if s["required"]]
            if req:
                if any(self.state(k) == "NONE" for k in req):
                    return True
            elif all(self.state(k) == "NONE" for k in keys):
                return True
            if any(self.state(k) == "UNK" for k in keys) and self.unknown_counts.get(qid, 0) < ua:
                return True
            if any(self.state(k) == "REF" for k in keys) and self.refusal_counts.get(qid, 0) < ra:
                return True
        return False

    def is_skipped(self, qid):
        return qid in self.skipped

    def deferred_keys(self, kind):
        return [tkey(d["target"]) for d in self.deferred if d["kind"] == kind]

    def sv(self, key, role, value, metadata=None):
        d = {"slot": ref_of(key), "question_name": self.qname(key[0]), "value": copy.deepcopy(value), "role": role}
        if metadata:
            d["value_metadata"] = copy.deepcopy(metadata)
        return d

    def current_sv(self, key):
        v = self.answer(key)
        if v is None:
            return None
        return self.sv(key, "CURRENT", v, self.rec[key].get("value_metadata"))

    def answers_sv(self, q, role="CURRENT"):
        out = []
        for k in self.slot_keys(q):
            v = self.answer(k)
            if v is not None:
                out.append(self.sv(k, role, v, self.rec[k].get("value_metadata")))
        return out

    def js(self, status=None):
        return [j for j in self.judgments if status is None or j["status"] == status]

    def jq(self, j):
        return j["target"]["question_id"]

    def qorder(self, qid):
        return self.qmap[qid]["order"] if qid in self.qmap else 10 ** 9

    # =============== 실행 ===============
    def run(self) -> dict:
        k = self.kind
        if k == "INTERVENTION_END":
            return self.finish_end("ENDED_STAFF")
        if k == "END_LEFT":
            return self.finish_end("ENDED_LEFT")
        if k == "RESUME":
            self.session_status = "IN_PROGRESS"
            self.pause_add.append({"kind": "RESUME", "reasons": []})
            self.notices_early.append(self.notice("RESUME"))
            return self.chain_turn(primary=("follow", None))
        if k == "SESSION_START":
            return self.chain_turn(primary=("follow", None))
        return self.utterance_turn()

    def finish_end(self, status):
        self.session_status = status
        self.flow = "END"
        self.notices_early.append(self.notice("SURVEY_STOPPED"))
        return self.build(("act", {"action": "FAREWELL"}), None)

    # ---------- 알릴 것 ----------
    def notice(self, kind, **kw):
        n = {"kind": kind, "guide_id": None, "question_id": None, "question_name": None, "slot": None,
             "previous_value": None, "value": None}
        n.update(kw)
        return n

    # ---------- 발화 턴 ----------
    def utterance_turn(self):
        J = self.J
        self.update_counters()
        self.release_facts()
        self.update_open_requests()
        self.build_early_notices()

        # (규칙 0) 확인 응답 거부는 먼저 사실을 고친다
        self.rule0()
        # (규칙 3)의 사실: 이번 턴의 중단 요청을 열린 요청으로 남긴다
        stop_now = any(r["kind"] == "STOP" for r in J["requests"])
        if stop_now:
            self.stop_requested = True

        primary = None
        awaiting = None
        gate_done = False
        seq = self.sequence()
        for typ, fn in seq:
            if typ == "act":
                if primary is not None:
                    continue
                res = fn()
                if res is not None:
                    primary = res
                continue
            # 묻는 규칙
            if typ == "ask6" and primary is not None:
                continue
            if primary is not None and not gate_done and typ in ("ask", "side"):
                gate_done = True
                gate = self.stop_gate()
                if gate is not None:
                    awaiting = gate
                    break
            res = fn()
            if isinstance(res, _Ask):
                awaiting = res
                if primary is None:
                    primary = ("ask", res)
                break
            if isinstance(res, tuple) and res[0] == "end":
                return self.build(res, None)
        if awaiting is None and primary is not None and primary[0] == "ask":
            awaiting = primary[1]
        return self.finish(primary, awaiting, stop_now)

    def sequence(self):
        return [
            ("act", self.rule1), ("act", self.rule2), ("act", self.rule3_prim), ("act", self.rule4), ("act", self.rule5),
            ("ask6", self.rule6),
            ("side", self.rule6b), ("ask", self.rule7), ("ask", self.rule8), ("ask", self.rule9),
            ("ask", self.rule10), ("ask", self.rule11),
            ("act", self.rule12), ("act", self.rule13), ("act", self.rule14),
            ("ask", self.rule15), ("ask", self.rule16), ("ask", self.rule17), ("ask", self.rule18),
            ("ask", self.rule19),
        ]

    def chain_turn(self, primary):
        """발화가 아닌 턴: 지금 물을 것을 계산한다."""
        awaiting = None
        gate = self.stop_gate()
        if gate is not None:
            awaiting = gate
        else:
            for fn in (self.rule6b, self.rule7, self.rule8, self.rule9, self.rule10, self.rule11, self.rule15,
                       self.rule16, self.rule17, self.rule18, self.rule19):
                res = fn()
                if isinstance(res, _Ask):
                    awaiting = res
                    break
        return self.finish(primary, awaiting, False)

    def stop_gate(self):
        """지금 물을 것(8-2.1): 열린 요청.중단 요청이 예이면 중단 확인. 물음 상한이면 요청을 아니요로 하고 계속한다."""
        if not self.stop_requested:
            return None
        sk = ("U", "ASK_STOP")
        n = self.ask_counts.get(sk, [None, 0])[1]
        if n >= self.settings["ask_limit"]:
            self.stop_requested = False
            self.ask_counts.pop(sk, None)
            return None
        return _Ask("ASK_STOP", commit=lambda: self.bump(({"untargeted": "ASK_STOP"}), 1))

    def bump(self, subject, d):
        k = self.subj_key(subject)
        cur = self.ask_counts.get(k, [subject, 0])
        self.ask_counts[k] = [subject, cur[1] + d]

    # ---------- 횟수 갱신 (8-2.2 ~ 8-2.5) ----------
    def update_counters(self):
        J = self.J
        touched = []
        for j in self.judgments:
            if j["status"] in ("UNCLEAR", "MISSING"):
                touched.append(self.jq(j))
        if self.aw and self.aw["action"] in ASK_Q_ACTIONS and self.judgments and self.aw["targets"]:
            q = self.aw["targets"][0]["question_id"]
            uk = any(j["status"] in ("UNKNOWN", "REJECTED") and self.jq(j) == q for j in self.judgments)
            if q in self.qmap and not uk and self.q_open(self.qmap[q]):
                touched.append(q)
        for q in uniq(touched):
            self.attempts[q] = self.attempts.get(q, 0) + 1
        for q in uniq([self.jq(j) for j in self.judgments if j["status"] == "UNKNOWN"]):
            self.unknown_counts[q] = self.unknown_counts.get(q, 0) + 1
        for q in uniq([self.jq(j) for j in self.judgments if j["status"] == "REJECTED"]):
            self.refusal_counts[q] = self.refusal_counts.get(q, 0) + 1
        res = J["result"]
        if res == "UNRECOGNIZED_TURN":
            self.streak += 1
        elif res in ("HAS_ANSWER", "OUT_OF_SCOPE_ONLY"):
            self.streak = 0

    # ---------- 해제 (8-2.8, 8-2.9, 8-2.3) ----------
    def release_facts(self):
        s = self.summary
        inval = set(s["invalidated_questions"])
        changed_q = {c["slot"]["question_id"] for c in s["changed_slots"]} | {
            r["slot"]["question_id"] for r in s["unknown_refused_records"]}
        for qid in list(self.skipped):
            if qid in inval or qid in changed_q:
                self.skipped_remove.append(qid)
                self.skipped.pop(qid)
        for qid in inval:
            self.attempts.pop(qid, None)
            self.deferred = [d for d in self.deferred if not (d["kind"] == "QUESTION" and d["target"]["question_id"] == qid)]
        resolved = {skey(r["slot"]) for r in s["resolved_pendings"] if r["handling"] in ("ACCEPT", "DROP")}
        for k in list(self.confirm_counts):
            if k in resolved or k[0] in inval:
                self.confirm_counts.pop(k)
        for k in list(self.cstop):
            if k in resolved or k[0] in inval:
                self.cstop.remove(k)
                self.cstop_remove.append(k)
        # 확인 대기가 없는 슬롯의 확인 중단·확인 횟수는 뜻이 없다(대체는 그대로 둔다)
        for k in list(self.cstop):
            if self.pending(k) is None:
                self.cstop.remove(k)
                self.cstop_remove.append(k)
        for k in list(self.confirm_counts):
            if self.pending(k) is None:
                self.confirm_counts.pop(k)

    # ---------- 열린 요청 고치기 (8-2.7) ----------
    def update_open_requests(self):
        J = self.J
        for r in J["valueless_correction_requests"]:
            if not any(self.same_target(x["target"], r["target"]) for x in self.corr):
                self.corr.append({"target": copy.deepcopy(r["target"])})
        value_judged = [j for j in self.judgments if j["status"] in VALUE_STATUSES] + [
            j for j in self.judgments if j["status"] is None and j["pending_handling"] == "ACCEPT"]
        inval = set(self.summary["invalidated_questions"])

        def resolved(t):
            if t is None:
                return False
            qid = t["question_id"]
            if qid in inval:
                return True
            q = self.qmap.get(qid)
            if q is not None and not self.prereq_ok(q):
                return True
            for j in value_judged:
                if is_whole(t):
                    if self.jq(j) == qid:
                        return True
                elif tkey(j["target"]) == tkey(t):
                    return True
            return False

        # 대상 없는 정정 요청: 정정 구체화를 기다리던 턴에 값 판정이나 대상 있는 값 없는 정정 요청이 오면 뺀다
        untargeted_answered = (
            self.aw is not None and self.aw["action"] == "ASK_CORRECTION_TARGET" and not self.aw["targets"]
            and (bool(value_judged) or any(r["target"] is not None for r in J["valueless_correction_requests"])))
        keep = []
        for r in self.corr:
            if r["target"] is None:
                if untargeted_answered and not any(x["target"] is None for x in J["valueless_correction_requests"]):
                    self.ask_counts.pop(("U", "ASK_CORRECTION_TARGET"), None)
                    continue
                keep.append(r)
            elif resolved(r["target"]):
                self.ask_counts.pop(tkey(r["target"]), None)
            else:
                keep.append(r)
        self.corr = keep
        # 미룸
        answered_q = {c["slot"]["question_id"] for c in self.summary["changed_slots"]} | {
            r["slot"]["question_id"] for r in self.summary["unknown_refused_records"]}
        nd = []
        for d in self.deferred:
            t = d["target"]
            if d["kind"] == "QUESTION":
                q = self.qmap.get(t["question_id"])
                if q is None or t["question_id"] in answered_q or not self.q_open(q):
                    continue
            elif d["kind"] == "PENDING":
                if is_slot(t) and self.pending(skey(t)) is None:
                    self.ask_counts.pop(tkey(t), None)
                    continue
            else:
                if resolved(t):
                    self.ask_counts.pop(tkey(t), None)
                    continue
            nd.append(d)
        self.deferred = nd

    @staticmethod
    def same_target(a, b):
        if a is None or b is None:
            return a is None and b is None
        return tkey(a) == tkey(b)

    # ---------- 이번 턴의 알릴 것 (8-2.10) ----------
    def build_early_notices(self):
        s = self.summary
        for c in s["changed_slots"]:
            if c["kind"] == "CORRECTION":
                k = skey(c["slot"])
                self.notices_early.append(self.notice(
                    "CORRECTION_ACK", question_id=k[0], question_name=self.qname(k[0]), slot=c["slot"],
                    previous_value=c["previous_value"], value=c["new_value"]))
        changed = {skey(c["slot"]) for c in s["changed_slots"]}
        for r in s["resolved_pendings"]:
            k = skey(r["slot"])
            if r["handling"] == "DROP" and k not in changed and self.answer(k) is not None:
                self.notices_early.append(self.notice(
                    "KEPT_PREVIOUS", question_id=k[0], question_name=self.qname(k[0]), slot=r["slot"], value=self.answer(k)))
        self.guide_requests = []
        remaining = sum(1 for q in self.qs if not self.is_skipped(q["question_id"]) and self.q_open(q))
        for r in self.J["requests"]:
            if r["kind"] != "GUIDE":
                continue
            g = next((x for x in self.settings["guide_list"] if x["guide_id"] == r["guide_id"]), None)
            if g is None:
                continue
            qid = r["target_question_id"]
            if g["per_question"]:
                q = self.qmap.get(qid)
                if q is None or not any(x["guide_id"] == g["guide_id"] for x in q["guide_sentences"]):
                    continue
            elif not g["sentence"]:
                continue
            n = self.notice("GUIDE", guide_id=g["guide_id"], question_id=qid if g["per_question"] else None,
                            question_name=self.qname(qid) if (g["per_question"] and qid) else None)
            if g["fill_value"] == "REMAINING_COUNT":
                n["value"] = {"amount": remaining, "unit": "문항"}  # 골든 E2, E5a, R11
            self.notices_early.append(n)
            self.guide_requests.append(r)

    # =============== 규칙 ===============
    def rule0(self):
        if self.J["confirmation"] != "NO" or not self.aw:
            return
        a = self.aw["action"]
        if a == "ASK_STOP":
            self.stop_requested = False
            self.ask_counts.pop(("U", "ASK_STOP"), None)
        elif a == "ASK_CORRECTION_TARGET":
            t = self.aw["targets"][0] if self.aw["targets"] else None
            self.corr = [r for r in self.corr if not self.same_target(r["target"], t)]
            self.ask_counts.pop(self.subj_key(t) if t else ("U", "ASK_CORRECTION_TARGET"), None)
            if t is not None:
                self.kept_notices(t)

    def kept_notices(self, t):
        if is_whole(t):
            keys = [k for k in self.slot_keys(self.qmap[t["question_id"]])] if t["question_id"] in self.qmap else []
        else:
            keys = [skey(t)]
        for k in keys:
            v = self.answer(k)
            if v is not None:
                self.notices_late.append(self.notice(
                    "KEPT_PREVIOUS", question_id=k[0], question_name=self.qname(k[0]), slot=ref_of(k), value=v))

    # (규칙 1) 위험
    def rule1(self):
        J = self.J
        risky = [j for j in self.judgments if j["risk_rule"] == "IMMEDIATE" and j["status"] in ("ANSWERED", "CORRECTION", "CONFLICT")
                 and is_slot(j["target"]) and j["value_now"] is not None]
        if not J["risk_signal"] and not risky:
            return None
        reasons, pause = [], []
        if J["risk_signal"]:
            ev = copy.deepcopy(J["risk_signal"]["evidence"])
            reasons.append({"kind": "RISK_SIGNAL", "evidence": ev})
            pause.append({"kind": "RISK_SIGNAL", "evidence": copy.deepcopy(ev)})
        if risky:
            reasons.append({"kind": "RISK_RULE", "target": [
                {"slot": j["target"], "question_name": self.qname(self.jq(j)), "value": j["value_now"]} for j in risky]})
            pause.append({"kind": "RISK_RULE", "target": [j["target"] for j in risky]})
        staff = [r for r in J["requests"] if r["kind"] == "STAFF_REQUEST"]
        if staff:
            reasons.append({"kind": "USER_CALLED_STAFF", "evidence": uniq([t for r in staff for t in r["source_text"]])})
        self.staff_alert = {"kind": "RISK", "reasons": reasons}
        self.session_status = "PAUSED_RISK"
        self.pause_add.append({"kind": "PAUSE", "reasons": pause})
        return ("act", {"action": "RISK_NOTICE"})

    # (규칙 2) 사람 요청
    def rule2(self):
        staff = [r for r in self.J["requests"] if r["kind"] == "STAFF_REQUEST"]
        if not staff:
            return None
        ev = uniq([t for r in staff for t in r["source_text"]])
        self.staff_alert = {"kind": "USER_CALLED_STAFF", "reasons": [{"kind": "USER_CALLED_STAFF", "evidence": ev}]}
        return ("act", {"action": "STAFF_NOTICE"})

    # (규칙 3) 이번 턴의 중단 요청 -> 중단 확인
    def rule3_prim(self):
        if not any(r["kind"] == "STOP" for r in self.J["requests"]):
            return None
        gate = self.stop_gate()
        if gate is None:
            return None
        return ("ask", gate)

    # (규칙 4) 반복 요청
    def rule4(self):
        J = self.J
        if J["result"] != "REQUEST_ONLY" or not any(r["kind"] == "REPEAT" for r in J["requests"]):
            return None
        if self.last is None:
            return ("follow", None)
        return ("replay", None)

    # (규칙 5) 대기 요청
    def rule5(self):
        if any(r["kind"] == "WAIT" for r in self.J["requests"]):
            return ("act", {"action": "WAIT_NOTICE"})
        return None

    # (규칙 6) 확인 응답
    def rule6(self):
        J, aw = self.J, self.aw
        if not aw or J["confirmation"] != "YES":
            return None
        a = aw["action"]
        valueless = J["valueless_correction_requests"]
        if a == "ASK_FINISH":
            if (not self.judgments and not valueless and not self.any_open_question()
                    and not self.waiting_pendings() and not self.corr and not self.stop_requested and not self.deferred):
                self.session_status = "ENDED_COMPLETE"
                self.flow = "END"
                return ("end", {"action": "FAREWELL"})
        elif a == "ASK_STOP":
            if not valueless:
                self.session_status = "ENDED_USER_STOP"
                self.flow = "END"
                self.notices_late.append(self.notice("SURVEY_STOPPED"))
                return ("end", {"action": "FAREWELL"})
        elif a == "ASK_CORRECTION_TARGET":
            if not valueless:
                t = aw["targets"][0] if aw["targets"] else None
                sk = self.subj_key(t) if t else ("U", "ASK_CORRECTION_TARGET")
                if self.ask_counts.get(sk, [None, 0])[1] >= self.settings["ask_limit"]:
                    return None  # 8-4절 7이 앞선다: 규칙 7이 열린 요청에서 뺀다
                return self.correction_ask(t)
        return None

    def any_open_question(self):
        return any(self.q_open(q) and not self.is_skipped(q["question_id"]) for q in self.qs)

    def waiting_pendings(self):
        return [k for k, r in self.rec.items() if r["pending"] is not None and k not in self.cstop]

    # (규칙 6b) 시도 초과 건너뜀
    def rule6b(self):
        aw = self.aw
        if not aw or aw["action"] not in ASK_Q_ACTIONS or not aw["targets"]:
            return None
        qid = aw["targets"][0]["question_id"]
        q = self.qmap.get(qid)
        if q is None or self.is_skipped(qid) or not self.q_open(q):
            return None
        if self.attempts.get(qid, 0) >= q["policy"]["question_limit"]:
            self.add_skip(qid, "ATTEMPTS_EXCEEDED")
        return None

    def add_skip(self, qid, reason):
        self.skipped[qid] = reason
        self.skipped_add = [s for s in self.skipped_add if s["question_id"] != qid]
        self.skipped_add.append({"question_id": qid, "reason": reason})
        if qid in self.skipped_remove:
            self.skipped_remove.remove(qid)  # 같은 턴에 다시 건너뛰면 추가만 낸다

    # (규칙 7) 정정 구체화
    def correction_ask(self, t):
        sv = []
        if t is not None:
            if is_whole(t):
                if t["question_id"] in self.qmap:
                    sv = self.answers_sv(self.qmap[t["question_id"]])
            else:
                x = self.current_sv(skey(t))
                sv = [x] if x else []
        subject = copy.deepcopy(t) if t is not None else {"untargeted": "ASK_CORRECTION_TARGET"}
        return _Ask("ASK_CORRECTION_TARGET", targets=[copy.deepcopy(t)] if t is not None else [], say_values=sv,
                    commit=lambda: self.bump(subject, 1))

    def rule7(self):
        if not self.corr:
            return None
        this_turn = [r["target"] for r in self.J["valueless_correction_requests"]]
        cand = None
        mine = [r for r in self.corr if any(self.same_target(r["target"], t) for t in this_turn)]
        cand = next((r for r in mine if r["target"] is not None), None) or next((r for r in mine), None)
        if cand is None:
            cand = self.corr[0]
        t = cand["target"]
        # 직전 기다리는 답이 그 정정 구체화였고 응답이 없었는데 나중에 요청이 있으면 미룸으로 옮긴다
        aw = self.aw
        if aw and aw["action"] == "ASK_CORRECTION_TARGET":
            at = aw["targets"][0] if aw["targets"] else None
            if self.same_target(at, t) and not self.responded_to(t):
                if self.later_for(t):
                    self.corr.remove(cand)
                    if t is not None and not any(self.same_target(d["target"], t) and d["kind"] == "CORRECTION_REQUEST" for d in self.deferred):
                        self.deferred.append({"kind": "CORRECTION_REQUEST", "target": copy.deepcopy(t)})
                    self.later_consumed = True
                    self.notices_late.append(self.defer_notice(t))
                    return None
        sk = self.subj_key(t) if t is not None else ("U", "ASK_CORRECTION_TARGET")
        if self.ask_counts.get(sk, [None, 0])[1] >= self.settings["ask_limit"]:
            self.corr.remove(cand)
            self.ask_counts.pop(sk, None)
            return None
        return self.correction_ask(t)

    later_consumed = False

    def responded_to(self, t):
        if self.J["confirmation"] != "NONE":
            return True
        for j in self.judgments:
            if j["status"] in VALUE_STATUSES + ("UNKNOWN", "REJECTED", "PREREQUISITE_UNMET", "CONFLICT", "UNCLEAR"):
                if t is None or (is_whole(t) and self.jq(j) == t["question_id"]) or tkey(j["target"]) == tkey(t):
                    return True
        return False

    def later_for(self, t):
        qid = t["question_id"] if t is not None else None
        return any(r["kind"] == "LATER" and r["target_question_id"] == qid for r in self.J["requests"])

    def defer_notice(self, t):
        qid = t["question_id"] if t is not None else None
        return self.notice("DEFERRED", question_id=qid, question_name=self.qname(qid) if qid else None,
                           slot=None)  # 골든(N7a, D3a): 미룸 알림에는 슬롯이 없다

    # (규칙 8) 확인 대기 확인에 대한 응답
    def confirm_ask(self, key, pend):
        cv = self.current_sv(key)
        sv = [cv] if cv else []
        sv.append(self.sv(key, "PENDING", pend["value"], pend.get("value_metadata")))
        return _Ask("ASK_CONFIRM", targets=[ref_of(key)], pending_id=pend["pending_id"], say_values=sv,
                    commit=lambda: self.confirm_counts.__setitem__(key, self.confirm_counts.get(key, 0) + 1))

    def rule8(self):
        aw = self.aw
        if not aw or aw["action"] != "ASK_CONFIRM" or not aw["targets"] or not is_slot(aw["targets"][0]):
            return None
        key = skey(aw["targets"][0])
        pend = self.pending(key)
        if pend is None or self.is_deferred_pending(key):
            return None
        for j in self.judgments:
            if is_slot(j["target"]) and skey(j["target"]) == key and (
                    j["status"] in ("CORRECTION", "UNKNOWN", "REJECTED") or j["pending_handling"] in ("ACCEPT", "DROP")):
                return None
        if self.confirm_resolved_by_whole(key):
            return None
        qid = key[0]
        if any(r["kind"] == "LATER" and r["target_question_id"] == qid for r in self.J["requests"]):
            if not self.is_deferred_pending(key):
                self.deferred.append({"kind": "PENDING", "target": ref_of(key)})
            self.later_consumed = True
            self.notices_late.append(self.defer_notice(ref_of(key)))
            return None
        bad = [j for j in self.judgments if is_slot(j["target"]) and skey(j["target"]) == key and j["status"] in ("UNCLEAR", "CONFLICT")]
        if bad:
            if self.confirm_counts.get(key, 0) >= self.settings["confirm_limit"]:
                if key not in self.cstop:
                    self.cstop.append(key)
                self.cstop_add.append(ref_of(key))  # 골든 N6, C8a: 이미 중단 목록에 있어도 상한 도달은 같은 처리
                self.ignored_judgments = self.ignored_judgments + bad
                v = self.answer(key)
                if v is not None:
                    self.notices_late.append(self.notice("KEPT_PREVIOUS", question_id=qid, question_name=self.qname(qid),
                                                         slot=ref_of(key), value=v))
                return None
            return self.confirm_ask(key, pend)
        return None

    def confirm_resolved_by_whole(self, key):
        for j in self.judgments:
            if is_whole(j["target"]) and j["status"] in ("UNKNOWN", "REJECTED") and self.jq(j) == key[0] and j["pending_handling"] == "DROP":
                return True
        return False

    def is_deferred_pending(self, key):
        return ("S",) + key in self.deferred_keys("PENDING")

    # (규칙 9) 애매
    def rule9(self):
        ign = self.ignored_judgments
        un = [j for j in self.js("UNCLEAR") if not any(j is x for x in ign)]
        if not un:
            return None
        un.sort(key=lambda j: self.qorder(self.jq(j)))
        first = un[0]
        group = [first]
        # 같은 문항의 애매 슬롯과, 다른 답과 맞지 않음으로 묶인 것을 함께
        changed = True
        while changed:
            changed = False
            for j in un:
                if any(j is g for g in group):
                    continue
                if self.jq(j) == self.jq(first) or self.linked(j, group):
                    group.append(j)
                    changed = True
        qids = uniq([self.jq(j) for j in group])
        over = [q for q in qids if self.attempts.get(q, 0) >= self.qmap[q]["policy"]["question_limit"]]
        if over:
            for q in over:
                if not self.is_skipped(q):
                    self.add_skip(q, "ATTEMPTS_EXCEEDED")
            return None
        group.sort(key=lambda j: (self.qorder(self.jq(j)), self.judgments.index(j)))
        targets = [j["target"] for j in group]
        reasons = uniq([r for j in group for r in j["reasons"]])
        sv = []
        for j in group:
            if j["said_value"]:
                sv.append(self.sv(skey(j["target"]), "SAID", j["said_value"]) if is_slot(j["target"]) else None)
        sv = [x for x in sv if x]
        said_keys = {skey(j["target"]) for j in group if is_slot(j["target"])}
        for j in group:
            for m in j["mismatched_slots"]:
                if skey(m) not in said_keys:
                    c = self.current_sv(skey(m))
                    if c and not any(x["slot"] == c["slot"] for x in sv):
                        sv.append(c)
        return _Ask("ASK_CLARIFY", targets=targets, say_values=sv, reasons=reasons)

    @staticmethod
    def linked(j, group):
        for g in group:
            if any(is_slot(g["target"]) and skey(m) == skey(g["target"]) for m in j["mismatched_slots"]):
                return True
            if any(is_slot(j["target"]) and skey(m) == skey(j["target"]) for m in g["mismatched_slots"]):
                return True
        return False

    # (규칙 10) 누락
    def rule10(self):
        ms = [j for j in self.js("MISSING") if not self.is_skipped(self.jq(j))]
        if not ms:
            return None
        ms.sort(key=lambda j: (self.qorder(self.jq(j)), self.judgments.index(j)))
        qid = self.jq(ms[0])
        q = self.qmap[qid]
        if self.attempts.get(qid, 0) >= q["policy"]["question_limit"]:
            self.add_skip(qid, "ATTEMPTS_EXCEEDED")
            return None
        targets = [j["target"] for j in ms if self.jq(j) == qid]
        sv = []
        for c in self.summary["changed_slots"]:
            if c["slot"]["question_id"] == qid:
                k = skey(c["slot"])
                sv.append(self.sv(k, "JUST_SAVED", c["new_value"], self.rec.get(k, {}).get("value_metadata")))
        return _Ask("ASK_MISSING", targets=targets, say_values=sv, reasons=[])  # 골든: 빠진 슬롯 되묻기는 되물을 이유를 비운다

    # (규칙 11) 모름·거절
    def rule11(self):
        us = [j for j in self.judgments if j["status"] in ("UNKNOWN", "REJECTED")]
        if not us:
            return None
        us.sort(key=lambda j: (self.qorder(self.jq(j)), self.judgments.index(j)))
        j = us[0]
        qid = self.jq(j)
        if self.is_skipped(qid):
            return None
        q = self.qmap[qid]
        unknown = j["status"] == "UNKNOWN"
        count = (self.unknown_counts if unknown else self.refusal_counts).get(qid, 0)
        accept = q["policy"]["unknown_accept_after" if unknown else "refusal_accept_after"]
        if count < accept:
            same = [x for x in us if self.jq(x) == qid and x["status"] == j["status"]]
            targets = []
            for x in same:
                for t in self.uk_slots(q, x, unknown):
                    if not any(tkey(t) == tkey(y) for y in targets):
                        targets.append(t)
            return self.after_ask(q, unknown, targets)
        self.add_skip(qid, "UNKNOWN_ACCEPTED" if unknown else "REFUSAL_ACCEPTED")
        return None

    def uk_slots(self, q, j, unknown):
        want = "UNK" if unknown else "REF"
        if is_slot(j["target"]):
            return [j["target"]]
        return [ref_of(k) for k in self.slot_keys(q) if self.state(k) == want]

    def after_ask(self, q, unknown, targets):
        return _Ask("ASK_AFTER_UNKNOWN" if unknown else "ASK_AFTER_REFUSAL", targets=targets)

    # (규칙 12) 안내 요청
    def rule12(self):
        J = self.J
        if J["result"] != "REQUEST_ONLY" or not self.guide_requests:
            return None
        if any(r["kind"] == "LATER" for r in J["requests"]):
            return None
        return ("follow", None)

    # (규칙 13) 무관
    def rule13(self):
        J = self.J
        only_oos = J["result"] == "OUT_OF_SCOPE_ONLY"
        guide_all_invalid = (J["result"] == "REQUEST_ONLY" and not self.guide_requests
                             and any(r["kind"] == "GUIDE" for r in J["requests"])
                             and not any(r["kind"] == "LATER" for r in J["requests"])
                             and not J["valueless_correction_requests"] and not self.corr_this_turn())
        if only_oos or guide_all_invalid:
            return ("act", {"action": "REDIRECT"})
        return None

    def corr_this_turn(self):
        return bool(self.J["valueless_correction_requests"])

    # (규칙 14) 알아듣지 못함
    def rule14(self):
        if self.J["result"] != "UNRECOGNIZED_TURN":
            return None
        if self.streak == self.settings["unrecognized_streak_limit"]:
            self.staff_alert = {"kind": "CALL_STAFF", "reasons": []}
            return ("act", {"action": "CALL_STAFF"})
        return ("act", {"action": "ASK_REPEAT", "reasons": ["UNRECOGNIZED"]})

    # (규칙 15) 이번 턴에 생긴 확인 대기
    def rule15(self):
        cands = []
        for i, c in enumerate(self.summary["created_pendings"]):
            k = skey(c["slot"])
            if self.pending(k) is None or k in self.cstop or self.is_deferred_pending(k):
                continue
            jidx = next((n for n, j in enumerate(self.judgments) if is_slot(j["target"]) and skey(j["target"]) == k), i)
            cands.append((self.qorder(k[0]), jidx, k))
        if not cands:
            return None
        k = sorted(cands)[0][2]
        return self.confirm_ask(k, self.pending(k))

    # (규칙 16) 남은 확인 대기
    def rule16(self):
        cands = []
        for q in self.qs:
            for k in self.slot_keys(q):
                if self.pending(k) is not None and k not in self.cstop and not self.is_deferred_pending(k):
                    cands.append(k)
        if not cands:
            return None
        return self.confirm_ask(cands[0], self.pending(cands[0]))

    # (규칙 17) 열린 문항
    def rule17(self):
        J = self.J
        # 이번 턴의 '나중에'를 그 문항의 미룸으로 옮긴다(규칙 7·8에서 옮기지 않았을 때)
        if J is not None and not self.later_consumed:
            for r in J["requests"]:
                qid = r["target_question_id"]
                if r["kind"] == "LATER" and qid in self.qmap:
                    q = self.qmap[qid]
                    if self.q_open(q) and not self.is_skipped(qid):
                        if not any(d["kind"] == "QUESTION" and d["target"]["question_id"] == qid for d in self.deferred):
                            self.deferred.append({"kind": "QUESTION", "target": _whole(qid)})
                            self.notices_late.append(self.defer_notice(_whole(qid)))
                        break
        dq = {d["target"]["question_id"] for d in self.deferred if d["kind"] == "QUESTION"}
        opens = [q for q in self.qs if not self.is_skipped(q["question_id"]) and self.q_open(q)]
        opens = [q for q in opens if q["question_id"] not in dq] + [q for q in opens if q["question_id"] in dq]
        if not opens:
            return None
        q = opens[0]
        qid = q["question_id"]
        for rk in self.active_rks(q):
            keys = [(qid, rk, s["slot_id"]) for s in q["slots"]]
            req = [k for k, s in zip(keys, q["slots"]) if s["required"]]
            empty = [k for k in (req if req else keys) if self.state(k) == "NONE"]
            has_ans = [k for k in keys if self.state(k) != "NONE"]
            if empty and has_ans:
                return _Ask("ASK_MISSING", targets=[ref_of(k) for k in empty], say_values=self.answers_sv(q),
                            reasons=[])  # 골든: 빠진 슬롯 되묻기는 되물을 이유를 비운다
            if empty:
                return _Ask("ASK_NEXT", targets=[_whole(qid)])
            ua, ra = q["policy"]["unknown_accept_after"], q["policy"]["refusal_accept_after"]
            unk = [k for k in keys if self.state(k) == "UNK"]
            ref = [k for k in keys if self.state(k) == "REF"]
            if unk and self.unknown_counts.get(qid, 0) < ua:
                return self.after_ask(q, True, [ref_of(k) for k in unk])
            if ref and self.refusal_counts.get(qid, 0) < ra:
                return self.after_ask(q, False, [ref_of(k) for k in ref])
        return None

    # (규칙 18) 미룬 확인 대기, 미룬 정정 요청
    def rule18(self):
        for kind in ("PENDING", "CORRECTION_REQUEST"):
            for d in list(self.deferred):
                if d["kind"] != kind:
                    continue
                t = d["target"]
                sk = self.subj_key(t)
                if self.ask_counts.get(sk, [None, 0])[1] >= self.settings["ask_limit"]:
                    self.deferred.remove(d)
                    self.ask_counts.pop(sk, None)
                    continue
                if kind == "PENDING":
                    k = skey(t)
                    pend = self.pending(k)
                    if pend is None:
                        continue
                    a = self.confirm_ask(k, pend)
                    inner = a.commit
                    a.commit = lambda inner=inner, t=t: (inner(), self.bump(t, 1))
                    return a
                a = self.correction_ask(t)
                return a
        # 미룸에서 빠진 확인 대기는 보통의 남은 확인 대기다(규칙 16)
        return self.rule16()

    # (규칙 19) 종료 확인
    def rule19(self):
        sk = ("U", "ASK_FINISH")
        n = self.ask_counts.get(sk, [None, 0])[1]
        if n < self.settings["ask_limit"]:
            return _Ask("ASK_FINISH", commit=lambda: self.bump({"untargeted": "ASK_FINISH"}, 1))
        # 물음 상한: 도움 요청 + 직원 알림. 기다리는 답은 없다(골든 H5b); 직원의 개입 결정이 끝이다
        self.staff_alert = {"kind": "CALL_STAFF", "reasons": []}
        return _Ask("STAFF_NOTICE_FINISH")

    # =============== 마무리 ===============
    def finish(self, primary, awaiting, stop_now):
        # 규칙 19의 도움 요청은 묻는 행동이 아니라 행동 STAFF_NOTICE다(알림은 이미 정했다)
        if awaiting is not None and awaiting.action == "STAFF_NOTICE_FINISH":
            awaiting = None
            if primary is None or primary[0] in ("ask", "follow"):
                primary = ("act", {"action": "CALL_STAFF"})
        if primary is None:
            primary = ("follow", None)
        return self.build(primary, awaiting)

    def build(self, primary, awaiting):
        typ, data = primary
        if typ == "end":
            return self.out(self.mkdirective(data["action"], [], None, None, [], []))
        if typ == "act":
            if awaiting is not None and awaiting.commit:  # 골든(G8b, H3d, H5a, R7): 행동 뒤에 이어 묻는 것도 센다
                awaiting.commit()
            d = self.mkdirective(data["action"], [], None, awaiting, [], data.get("reasons", []))
            return self.out(d)
        if typ == "ask":
            a = data
            if a.commit:
                a.commit()
            d = self.mkdirective(a.action, a.targets, a.pending_id, a, a.say_values, a.reasons)
            return self.out(d)
        if typ == "follow":
            a = awaiting
            if a is not None and a.commit:  # 골든(H3d, H3e): 재개·세션 시작 뒤 이어 묻는 것도 센다
                a.commit()
            if a is None:
                d = self.mkdirective("ASK_FINISH", [], None, None, [], [])
            else:
                d = self.mkdirective(a.action, a.targets, a.pending_id, a, a.say_values, a.reasons)
            return self.out(d)
        if typ == "replay":
            d = copy.deepcopy(self.last)
            have = {(n["kind"], n["guide_id"], n["question_id"]) for n in d["notices"]}
            for n in self.notices_early:
                if n["kind"] == "GUIDE" and (n["kind"], n["guide_id"], n["question_id"]) not in have:
                    d["notices"].append(n)
            d["sentence_materials"] = self.materials(d["action"], d["awaiting"], d["notices"], d["targets"])
            return self.out(d)
        raise AssertionError(typ)

    def mkdirective(self, action, targets, pending_id, awaiting, say_values, reasons):
        notices = uniq(self.notices_early + self.notices_late)
        aw_dir = awaiting.as_ask_directive() if isinstance(awaiting, _Ask) else None
        d = {
            "action": action, "targets": copy.deepcopy(targets), "target_pending_id": pending_id,
            "awaiting": aw_dir, "say_values": copy.deepcopy(say_values), "reask_reasons": list(reasons),
            "notices": notices,
        }
        d["sentence_materials"] = self.materials(action, aw_dir, notices, targets)
        return d

    # ---------- 문장 재료 (골든 209 케이스의 모양에 맞춘 해석; change-requests/CR-005 결정 절) ----------
    def ask_materials(self, m, act, tg):
        """묻는 행동 하나의 재료: 다음 문항 묻기·모름 뒤 재질문=문항 문장+선택지, 거절 시 설명 후 재질문=문항 문장+거절 설명+선택지,
        빠진 슬롯 되묻기·구체화 요청=대상 슬롯의 다시 묻기 문장+선택지."""
        if act not in ASK_Q_ACTIONS:
            return
        seen_q = {x["question_id"] for x in m["question_sentences"]}
        for t in tg:
            qid = t["question_id"]
            q = self.qmap.get(qid)
            if q is None:
                continue
            if act in ("ASK_NEXT", "ASK_AFTER_UNKNOWN", "ASK_AFTER_REFUSAL") and qid not in seen_q:
                seen_q.add(qid)
                m["question_sentences"].append({"question_id": qid, "sentence": q["question_sentence"]})
                if act == "ASK_AFTER_REFUSAL":
                    m["refusal_explanations"].append({"question_id": qid, "sentence": q["refusal_explanation"]})
            for s in [s for s in q["slots"] if is_whole(t) or s["slot_id"] == t["slot_id"]]:
                ref = ref_of((qid, "" if is_whole(t) else t["repeat_key"], s["slot_id"]))
                if act in ("ASK_MISSING", "ASK_CLARIFY") and not any(x["slot"] == ref for x in m["reask_sentences"]):
                    m["reask_sentences"].append({"slot": ref, "sentence": s["reask_sentence"]})
                names = [c["label"] for c in s.get("choice_catalog", [])] or list(s["choices"])
                if names and not any(x["slot"] == ref for x in m["choices"]):
                    m["choices"].append({"slot": ref, "choices": names})

    def materials(self, action, aw, notices, targets):
        m = {"question_sentences": [], "refusal_explanations": [], "reask_sentences": [], "choices": [],
             "guide_sentences": [], "fixed_sentences": []}
        self.ask_materials(m, action, targets)
        if action in ("REDIRECT", "ASK_REPEAT") and aw:  # 다시 묻는 행동은 기다리는 답의 재료도 담는다
            self.ask_materials(m, aw["action"], aw["targets"])
        for n in notices:
            if n["kind"] != "GUIDE":
                continue
            g = next((x for x in self.settings["guide_list"] if x["guide_id"] == n["guide_id"]), None)
            if g is None:
                continue
            if g["per_question"]:
                q = self.qmap.get(n["question_id"])
                gs = next((x for x in q["guide_sentences"] if x["guide_id"] == g["guide_id"]), None) if q else None
                if gs:
                    m["guide_sentences"].append({"guide_id": g["guide_id"], "question_id": q["question_id"], "sentence": gs["sentence"]})
            elif g["sentence"]:
                m["guide_sentences"].append({"guide_id": g["guide_id"], "question_id": None, "sentence": g["sentence"]})
        keys = []
        for a in [action]:
            if a in FIXED_KEY_OF_ACTION:
                keys.append(FIXED_KEY_OF_ACTION[a])
        for n in notices:
            if n["kind"] in FIXED_KEY_OF_NOTICE:
                keys.append(FIXED_KEY_OF_NOTICE[n["kind"]])
        for key in uniq(keys):
            f = next((x for x in self.settings["fixed_sentences"] if x["key"] == key), None)
            if f:
                m["fixed_sentences"].append({"key": key, "sentence": f["sentence"]})
        return m

    def out(self, directive):
        alert = copy.deepcopy(self.staff_alert)
        # 진행 기록·Plan 기록 갱신
        self.final_cleanup()
        o = {
            "correction_requests": copy.deepcopy(self.corr),
            "stop_requested": self.stop_requested,
            "deferred": copy.deepcopy(self.deferred),
        }
        removed = [q for q in self.skipped_remove if q not in {s["question_id"] for s in self.skipped_add}]
        return {
            "directive": directive,
            "flow": self.flow,
            "staff_alert": alert,
            "progress_record_update": {
                "last_directive": copy.deepcopy(directive),
                "open_requests": o,
                "skipped_add": copy.deepcopy(self.skipped_add),
                "skipped_remove": removed,
                "confirm_stopped_add": copy.deepcopy(self.cstop_add),
                "confirm_stopped_remove": [ref_of(k) for k in self.cstop_remove],
                "session_status": self.session_status,
                "pause_history_add": copy.deepcopy(self.pause_add),
            },
            "planner_record_update": self.record_update(),
        }

    def final_cleanup(self):
        # 풀린 대상의 물은 횟수를 0으로 되돌린다
        live = {tkey(r["target"]) for r in self.corr if r["target"] is not None}
        live |= {tkey(d["target"]) for d in self.deferred}
        for k in list(self.ask_counts):
            if k[0] in ("S", "W"):
                if k not in live:
                    self.ask_counts.pop(k)
            elif k == ("U", "ASK_CORRECTION_TARGET"):
                if not any(r["target"] is None for r in self.corr):
                    self.ask_counts.pop(k)
            elif k == ("U", "ASK_STOP"):
                if not self.stop_requested:
                    self.ask_counts.pop(k)
        for k in list(self.confirm_counts):
            if self.pending(k) is None and k not in [skey(c["slot"]) for c in self.summary["created_pendings"]]:
                self.confirm_counts.pop(k)

    def record_update(self):
        return {
            "attempt_counts": [{"question_id": k, "count": v} for k, v in self.attempts.items()],
            "confirm_counts": [{"slot": ref_of(k), "count": v} for k, v in self.confirm_counts.items()],
            "unknown_counts": [{"question_id": k, "count": v} for k, v in self.unknown_counts.items()],
            "refusal_counts": [{"question_id": k, "count": v} for k, v in self.refusal_counts.items()],
            "unrecognized_streak": self.streak,
            "ask_counts": [{"subject": copy.deepcopy(s), "count": c} for s, c in self.ask_counts.values()],
        }
