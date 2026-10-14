"""시험용 오케스트레이터 시뮬레이터(survey-service의 몫을 흉내 낸다). 저장소 효과는 시험이 가정한 것이며 계약이 아니다."""
from __future__ import annotations

import copy

import turn_engine as te
from fixtures import questions, settings, ref
from turn_engine._common import skey
from turn_engine.judge import awaiting_of


def empty_pr():
    return {"attempt_counts": [], "confirm_counts": [], "unknown_counts": [], "refusal_counts": [],
            "unrecognized_streak": 0, "ask_counts": []}


class Session:
    def __init__(self, qs=None, **st):
        self.qs = qs or questions()
        self.settings = settings(**st)
        self.rec = {}
        for q in self.qs:
            for s in q["slots"]:
                k = (q["question_id"], "", s["slot_id"])
                self.rec[k] = {"slot": ref(k[0], k[2], k[1]), "current_value": "NONE", "risk_mark": None,
                               "history": [], "pending": None}
        self.skipped = []
        self.cstop = []
        self.open = {"correction_requests": [], "stop_requested": False, "deferred": []}
        self.pr = empty_pr()
        self.last = None
        self.status = "IN_PROGRESS"
        self.history = []
        self.alerts = []
        self.turns = 0
        self.flow = "CONTINUE"

    # ---------- 입력 조립 ----------
    def bank(self):
        return {"version": 1, "questions": self.qs, "session_settings": self.settings}

    def awaiting(self):
        a = awaiting_of(self.last)
        if a is None:
            return None
        return {"action": a["action"], "targets": a["targets"], "target_pending_id": a["target_pending_id"]}

    def pendings(self):
        return [{"pending_id": r["pending"]["pending_id"], "slot": r["slot"], "value": r["pending"]["value"]}
                for r in self.rec.values() if r["pending"]]

    def currents(self):
        return [{"slot": r["slot"], "current_value": r["current_value"]} for r in self.rec.values()]

    def answer_records(self):
        return copy.deepcopy(list(self.rec.values()))

    # ---------- 한 턴 ----------
    def turn(self, items, utterance="발화"):
        self.turns += 1
        norm_in = {"items": items, "related_questions": self.qs, "current_values": self.currents(),
                   "pendings": self.pendings(), "awaiting": self.awaiting(), "turn_index": self.turns}
        self.last_inputs = {"normalize": copy.deepcopy(norm_in)}
        norm = te.normalize(norm_in)
        jin = {
            "items": items, "item_checks": norm["item_checks"], "missing_required_slots": norm["missing_required_slots"],
            "utterance": utterance, "risk_phrases": self.settings["risk_phrases"], "last_directive": self.last,
            "pendings": [{"pending_id": p["pending_id"], "slot": p["slot"]} for p in self.pendings()],
            "affected_followups": [{"question_id": q["question_id"], "followups": q["affected_followups"]}
                                   for q in self.qs if q["affected_followups"]],
            "question_slots": [{"question_id": q["question_id"], "slot_ids": [s["slot_id"] for s in q["slots"]]} for q in self.qs],
        }
        self.last_inputs["judge"] = copy.deepcopy(jin)
        j = te.judge(jin)
        win = {"judgments": j["judgments"], "invalidated_questions": j["invalidated_questions"],
               "question_slots": jin["question_slots"],
               "target_records": [{"slot": r["slot"], "current_value": r["current_value"], "pending": r["pending"]}
                                  for r in self.rec.values()]}
        self.last_inputs["write_record"] = copy.deepcopy(win)
        w = te.write_record(win)
        self.apply_store(w)
        pin = self.plan_input("UTTERANCE", j["utterance_judgment"], j["judgments"], w["store_summary"])
        self.last_inputs["plan"] = copy.deepcopy(pin)
        out = te.plan(pin)
        self.apply_plan(out)
        self.last_norm, self.last_judge, self.last_write, self.last_plan = norm, j, w, out
        return out

    def plan_input(self, kind, uj, judgments, summary):
        return {"turn_kind": kind, "utterance_judgment": uj, "judgments": judgments, "store_summary": summary,
                "answer_records": self.answer_records(), "last_directive": self.last, "skipped": copy.deepcopy(self.skipped),
                "confirm_stopped": copy.deepcopy(self.cstop), "open_requests": copy.deepcopy(self.open),
                "planner_record": copy.deepcopy(self.pr), "question_bank": self.bank()}

    def nonutterance(self, kind):
        pin = self.plan_input(kind, None, [], None)
        self.last_inputs = {"plan": copy.deepcopy(pin)}
        out = te.plan(pin)
        self.apply_plan(out)
        self.last_plan = out
        return out

    def apply_store(self, w):
        for d in w["store_decisions"]:
            r = self.rec[skey(d["slot"])]
            a = d["action"]
            if a in ("FIRST_WRITE", "NEW_REVISION"):
                r["current_value"] = {"answer": d["value"]}
                r["history"].append(d["value"])
                r["risk_mark"] = d["risk_mark"]
            elif a == "RECORD_UNKNOWN":
                r["current_value"] = "UNKNOWN_RECORD"
            elif a == "RECORD_REFUSAL":
                r["current_value"] = "REFUSAL_RECORD"
            elif a == "SET_PENDING":
                r["pending"] = {"pending_id": d["pending_id"], "value": d["value"], "risk_mark": d["risk_mark"]}
            elif a == "ACCEPT_PENDING":
                r["current_value"] = {"answer": d["value"]}
                r["history"].append(d["value"])
                r["pending"] = None
            elif a == "DROP_PENDING":
                r["pending"] = None
            elif a == "INVALIDATE":
                r["current_value"] = "NONE"
                r["pending"] = None

    def apply_plan(self, out):
        p = out["progress_record_update"]
        self.last = p["last_directive"]
        self.open = p["open_requests"]
        rm = set(p["skipped_remove"])
        add = {s["question_id"] for s in p["skipped_add"]}
        self.skipped = [s for s in self.skipped if s["question_id"] not in rm and s["question_id"] not in add] + p["skipped_add"]
        self.cstop = [c for c in self.cstop if skey(c) not in {skey(x) for x in p["confirm_stopped_remove"]}] + p["confirm_stopped_add"]
        if p["session_status"]:
            self.status = p["session_status"]
        self.history += p["pause_history_add"]
        self.pr = out["planner_record_update"]
        if out["staff_alert"]:
            self.alerts.append(out["staff_alert"])
        self.flow = out["flow"]

    # ---------- 읽기 쉬운 도우미 ----------
    def action(self):
        return self.last["action"]

    def ans(self, q, slot):
        c = self.rec[(q, "", slot)]["current_value"]
        return c["answer"] if isinstance(c, dict) else c

    def pend(self, q, slot):
        return self.rec[(q, "", slot)]["pending"]
