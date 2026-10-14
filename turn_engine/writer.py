"""Record Writer: 판정을 응답 기록에 어떻게 반영할지 슬롯별로 정한다.
규칙 출처: docs/rules/record_writer.md (7절). 대응표는 docs/design.md."""
from __future__ import annotations

import hashlib
import json

from ._common import (
    check_input, check_output, is_whole, ref_of, same_value, skey, vkey,
)


def write_record(input: dict) -> dict:
    """(RecordWriterInput) -> StoreResult. 순수 함수."""
    check_input("RecordWriterInput", input)
    out = _Writer(input).run()
    check_output("StoreResult", out)
    return out


def new_pending_id(slot: dict, value, replaced_id, current) -> str:
    """확인 대기 ID(규칙 3). 난수·시간 없이 결정적으로 만든다: 슬롯, 새 값, 대체되는 이전 ID, 현재 값의 해시.
    (주입 방식은 change-requests/CR-004 참조)"""
    raw = json.dumps([skey(slot), vkey(value), replaced_id, vkey(current)], ensure_ascii=False, sort_keys=True)
    return "pnd-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


class _Writer:
    def __init__(self, inp):
        self.inp = inp
        self.rec = {}
        for r in inp["target_records"]:
            self.rec.setdefault(skey(r["slot"]), r)
        self.qslots = {x["question_id"]: x["slot_ids"] for x in inp["question_slots"]}
        self.decisions = []
        self.summary = {"changed_slots": [], "unknown_refused_records": [], "created_pendings": [],
                        "resolved_pendings": [], "invalidated_questions": []}

    # ---------- 도우미 ----------
    def cur(self, slot):
        r = self.rec.get(skey(slot))
        return r["current_value"] if r else "NONE"

    def pending(self, slot):
        r = self.rec.get(skey(slot))
        return r["pending"] if r else None

    def answer_of(self, cur):
        return cur["answer"] if isinstance(cur, dict) else None

    def decide(self, slot, action, value=None, pending_id=None, risk_mark=None, metadata=None):
        d = {"slot": slot, "action": action, "value": value, "pending_id": pending_id, "risk_mark": risk_mark}
        if metadata:
            d["value_metadata"] = metadata
        self.decisions.append(d)

    def slots_of_question(self, qid, exclude):
        """문항의 모든 슬롯(대상 기록이 있으면 그 참조, 없으면 repeat_key 빈 문자열)."""
        out = []
        for sid in self.qslots.get(qid, []):
            found = [r["slot"] for r in self.inp["target_records"]
                     if r["slot"]["question_id"] == qid and r["slot"]["slot_id"] == sid]
            refs = found or [ref_of((qid, "", sid))]
            for ref in refs:
                if skey(ref) not in exclude:
                    out.append(ref)
        return out

    # ---------- 실행 ----------
    def run(self) -> dict:
        self.invalidations()
        judged = {skey(j["target"]) for j in self.inp["judgments"] if not is_whole(j["target"])}
        for j in self.inp["judgments"]:
            if is_whole(j["target"]):
                for slot in self.slots_of_question(j["target"]["question_id"], judged):
                    self.apply(j, slot)
            else:
                self.apply(j, j["target"])
        return {"store_decisions": self.decisions, "store_summary": self.summary}

    def invalidations(self):
        for qid in self.inp["invalidated_questions"]:
            did = False
            for r in self.inp["target_records"]:
                s = r["slot"]
                if s["question_id"] != qid:
                    continue
                if r["current_value"] != "NONE" or r["pending"] is not None:
                    self.decide(s, "INVALIDATE", pending_id=r["pending"]["pending_id"] if r["pending"] else None)
                    did = True
            if did:
                self.summary["invalidated_questions"].append(qid)

    def apply(self, j, slot):
        status = j["status"]
        handling = j["pending_handling"]
        cur = self.cur(slot)
        pend = self.pending(slot)
        pid = (j["target_pending_ids"][0] if j["target_pending_ids"] else None) or (pend["pending_id"] if pend else None)
        value = j["value_now"]
        meta = j.get("value_metadata")

        if status is None:  # 확인 응답만의 받아들임·버림
            if handling == "ACCEPT" and pend is not None:
                self.accept(slot, cur, pend, j)
            elif handling == "DROP" and pid:
                self.drop(slot, pid)
            return
        if status == "ANSWERED":
            if not isinstance(cur, dict):
                if cur == "NONE":
                    self.write(slot, "FIRST_WRITE", None, value, j)
                else:
                    self.write(slot, "NEW_REVISION", None, value, j)
            # 같은 값이면 저장 없음(확인 대기 버림만)
        elif status == "CORRECTION":
            if handling == "ACCEPT" and pend is not None:
                self.accept(slot, cur, pend, j)
                return
            self.write(slot, "NEW_REVISION", self.answer_of(cur), value, j)
        elif status == "CONFLICT":
            replaced = j["target_pending_ids"][0] if j["target_pending_ids"] else (pend["pending_id"] if pend else None)
            nid = new_pending_id(slot, value, replaced, cur)
            self.decide(slot, "SET_PENDING", value, nid, j["risk_rule"], meta)
            self.summary["created_pendings"].append({"slot": slot})
            if replaced:
                self.summary["resolved_pendings"].append({"slot": slot, "handling": "REPLACE"})
            return
        elif status in ("UNKNOWN", "REJECTED"):
            rec = "UNKNOWN_RECORD" if status == "UNKNOWN" else "REFUSAL_RECORD"
            if cur != rec:
                self.decide(slot, "RECORD_UNKNOWN" if status == "UNKNOWN" else "RECORD_REFUSAL")
                self.summary["unknown_refused_records"].append({"slot": slot, "record": rec})
        else:
            return  # 애매·누락·선행 불충족은 저장하지 않는다
        if handling == "DROP" and pid:
            self.drop(slot, pid)

    def write(self, slot, action, previous, value, j):
        self.decide(slot, action, value, None, j["risk_rule"], j.get("value_metadata"))
        self.summary["changed_slots"].append({
            "slot": slot, "previous_value": previous, "new_value": value,
            "kind": "CORRECTION" if previous is not None else "FIRST_ANSWER"})

    def accept(self, slot, cur, pend, j):
        prev = self.answer_of(cur)
        self.decide(slot, "ACCEPT_PENDING", pend["value"], pend["pending_id"], pend["risk_mark"], pend.get("value_metadata"))
        self.summary["changed_slots"].append({
            "slot": slot, "previous_value": prev, "new_value": pend["value"],
            "kind": "CORRECTION" if prev is not None else "FIRST_ANSWER"})
        self.summary["resolved_pendings"].append({"slot": slot, "handling": "ACCEPT"})

    def drop(self, slot, pid):
        self.decide(slot, "DROP_PENDING", None, pid)
        self.summary["resolved_pendings"].append({"slot": slot, "handling": "DROP"})
