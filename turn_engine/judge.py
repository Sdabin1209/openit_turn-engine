"""Answer Judge: 이번 발화가 각 대상에 대해 무엇을 뜻하는지 판정한다.
규칙 출처: docs/rules/answer_judge.md (6절). 대응표는 docs/design.md."""
from __future__ import annotations

from ._common import (
    ContractViolation, check_input, check_output, is_slot, is_whole, same_value, skey, tkey, uniq,
)

ASK_QUESTION_ACTIONS = ("ASK_NEXT", "ASK_MISSING", "ASK_CLARIFY", "ASK_AFTER_UNKNOWN", "ASK_AFTER_REFUSAL")
REASONS = ("NO_UNIT", "OUT_OF_RANGE", "AMBIGUOUS", "MISMATCH")
VALUE_INTENTS = ("ANSWERED_INTENT", "CORRECTION_MARKED")
PROGRESS_KIND = {"REPEAT": "REPEAT", "WAIT": "WAIT", "LATER": "LATER", "STOP": "STOP"}


def judge(input: dict) -> dict:
    """(AnswerJudgeInput) -> JudgeOutput. 순수 함수."""
    check_input("AnswerJudgeInput", input)
    out = _Judge(input).run()
    check_output("JudgeOutput", out)
    return out


def awaiting_of(last_directive):
    """기다리는 답: 직전 지시의 awaiting, 없으면 지시 자체가 묻는 행동일 때 그것."""
    if not last_directive:
        return None
    if last_directive["awaiting"]:
        return last_directive["awaiting"]
    if last_directive["action"].startswith("ASK_") and last_directive["action"] != "ASK_REPEAT":
        return last_directive
    return None


class _Judge:
    def __init__(self, inp):
        self.inp = inp
        self.items = inp["items"]
        self.ic = {}
        for c in inp["item_checks"]:
            if c["item_no"] in self.ic:
                raise ContractViolation("AnswerJudgeInput", [f"item_checks: item_no 중복"])
            self.ic[c["item_no"]] = c
        for it in self.items:
            if it["item_no"] not in self.ic:
                raise ContractViolation("AnswerJudgeInput", ["item_checks: 항목에 대응하는 검사가 없음"])
        self.aw = awaiting_of(inp["last_directive"])
        self.aw_action = self.aw["action"] if self.aw else None
        self.pend_by_slot = {}
        self.pend_by_id = {}
        for p in inp["pendings"]:
            self.pend_by_slot.setdefault(skey(p["slot"]), p)
            self.pend_by_id[p["pending_id"]] = p
        self.followups = {x["question_id"]: x["followups"] for x in inp["affected_followups"]}
        self.qslots = {x["question_id"]: x["slot_ids"] for x in inp["question_slots"]}

    # ---------- 항목 분류 ----------
    def classify(self):
        """항목마다 범주를 정한다. 반환: 범주별 항목 목록."""
        cat = {"value": [], "valueless": [], "uk": [], "confirm": [], "request": [], "risk": [], "oos": [], "unrec": []}
        for it in self.items:
            c = self.ic[it["item_no"]]
            undefined = "UNKNOWN_TARGET" in c["problems"]
            intent = it["intent"]
            t = it["target"]
            if intent == "RISK_SIGNAL":
                cat["risk"].append(it)
            elif intent in ("PROGRESS_OP", "GUIDE_REQUEST", "USER_CALLED_STAFF"):
                if intent == "PROGRESS_OP" and it["progress_op"] == "LATER" and c["prerequisite_unmet"]:
                    cat["oos"].append(it)  # 나중에(선행 불충족)는 무관과 같이
                elif intent == "PROGRESS_OP" and it["progress_op"] not in PROGRESS_KIND:
                    cat["oos"].append(it)
                else:
                    cat["request"].append(it)
            elif intent == "OUT_OF_SCOPE":
                cat["oos"].append(it)
            elif intent == "UNRECOGNIZED":
                cat["unrec"].append(it)
            elif intent in ("CONFIRM_YES", "CONFIRM_NO"):
                cat["confirm"].append(it)
            elif intent in ("SAYS_UNKNOWN", "SAYS_REFUSAL"):
                if undefined or t is None:
                    cat["oos"].append(it)
                else:
                    cat["uk"].append(it)
            elif intent == "CORRECTION_MARKED" and it["value"] is None:
                if undefined or c["prerequisite_unmet"]:
                    cat["oos"].append(it)
                else:
                    cat["valueless"].append(it)
            elif intent in VALUE_INTENTS:
                if undefined or t is None:
                    cat["oos"].append(it)
                else:
                    cat["value"].append(it)
            else:
                cat["oos"].append(it)
        return cat

    # ---------- 판정 만들기 ----------
    def base_judgment(self, target, status, **kw):
        j = {"target": target, "status": status, "reasons": [], "value_now": None, "said_value": None,
             "pending_handling": "NONE", "target_pending_ids": [], "mismatched_slots": [], "risk_rule": None}
        j.update(kw)
        return j

    def value_judgment(self, key, target, group):
        """같은 대상의 값 항목들을 하나로 합쳐 판정한다(규칙 3, 1, 2)."""
        checks = [self.ic[it["item_no"]] for it in group]
        saids = uniq([it["value"] for it in group])
        pend = self.pend_by_slot.get(key[1:]) if key[0] == "S" else None
        clean = all(not c["problems"] and c["standard_value"] is not None for c in checks) and all(
            same_value(checks[0]["standard_value"], c["standard_value"]) for c in checks)
        if not clean:
            reasons, mism, details = [], [], []
            for c in checks:
                for p in c["problems"]:
                    if p in REASONS:
                        reasons.append(p)
                mism += c["mismatched_slots"]
                details += c.get("problem_details", [])
            single_same = len(group) == 1 or (
                all(c["standard_value"] is not None for c in checks)
                and all(same_value(checks[0]["standard_value"], c["standard_value"]) for c in checks))
            if not single_same or not reasons:
                reasons = ["AMBIGUOUS"] + [r for r in reasons if r != "AMBIGUOUS"]
            j = self.base_judgment(group[0]["target"], "UNCLEAR", reasons=uniq(reasons),
                                   said_value=" / ".join(saids), mismatched_slots=uniq(mism))
            if details and len(group) == 1:
                j["problem_details"] = details
            return j
        c0 = checks[0]
        std = c0["standard_value"]
        corr_marker = any(it["intent"] == "CORRECTION_MARKED" for it in group)
        # 규칙 1: 위에서부터 처음 맞는 것
        handling, ids = "NONE", []
        if c0["vs_pending"] == "EQUAL" and pend is not None:
            status, handling, ids = "CORRECTION", "ACCEPT", [pend["pending_id"]]
        elif c0["vs_current"] == "EQUAL":
            status = "ANSWERED"
        elif c0["vs_current"] == "NO_CURRENT":
            status = "ANSWERED"
        elif corr_marker:
            status = "CORRECTION"
        else:
            status = "CONFLICT"
        if pend is not None and handling == "NONE":
            if status == "CONFLICT":
                handling, ids = "CREATE", [pend["pending_id"]]  # 있던 것은 대체
            else:
                handling, ids = "DROP", [pend["pending_id"]]
        elif status == "CONFLICT":
            handling = "CREATE"
        j = self.base_judgment(group[0]["target"], status, value_now=std, said_value=saids[0] if len(saids) == 1 else " / ".join(saids),
                               pending_handling=handling, target_pending_ids=ids, risk_rule=c0["risk_rule"])
        if c0.get("value_metadata"):
            j["value_metadata"] = c0["value_metadata"]
        return j

    def uk_judgment(self, target, key, group):
        last = group[-1]  # 모름·거절끼리는 뒤의 것
        status = "UNKNOWN" if last["intent"] == "SAYS_UNKNOWN" else "REJECTED"
        pend = self.pend_by_slot.get(key[1:]) if key[0] == "S" else None
        return self.base_judgment(target, status,
                                  pending_handling="DROP" if pend else "NONE",
                                  target_pending_ids=[pend["pending_id"]] if pend else [])

    # ---------- 실행 ----------
    def run(self) -> dict:
        cat = self.classify()
        judgments = []
        slot_keys_with_judgment = set()  # ("S", q, rk, slot)

        # 슬롯별 값 / 모름·거절 / 선행 불충족
        groups = {}
        order = []
        for kind in ("value", "uk"):
            for it in cat[kind]:
                k = tkey(it["target"])
                if k not in groups:
                    groups[k] = {"value": [], "uk": []}
                    order.append(k)
                groups[k][kind].append(it)
        whole_uk = {}  # question_id -> items
        for k in order:
            g = groups[k]
            target = (g["value"] or g["uk"])[0]["target"]
            all_items = g["value"] + g["uk"]
            unmet = [it for it in all_items if self.ic[it["item_no"]]["prerequisite_unmet"]]
            live_value = [it for it in g["value"] if not self.ic[it["item_no"]]["prerequisite_unmet"]]
            live_uk = [it for it in g["uk"] if not self.ic[it["item_no"]]["prerequisite_unmet"]]
            if k[0] == "W" and live_uk and not live_value:
                whole_uk[k[1]] = live_uk
                continue
            if live_value:
                judgments.append(self.value_judgment(k, target, live_value))
            elif live_uk:
                judgments.append(self.uk_judgment(target, k, live_uk))
            elif unmet:
                judgments.append(self.base_judgment(target, "PREREQUISITE_UNMET"))
            if judgments and judgments[-1]["target"] == target and k[0] == "S":
                slot_keys_with_judgment.add(k)

        # 문항 전체 대상에서 선행 불충족만 있는 경우 위에서 처리됨. 빠진 필수 슬롯: 누락 판정
        for ref in self.inp["missing_required_slots"]:
            k = ("S",) + skey(ref)
            if k in slot_keys_with_judgment:
                continue
            judgments.append(self.base_judgment(ref, "MISSING", reasons=["MISSING_SLOT"]))
            slot_keys_with_judgment.add(k)

        # 규칙 5: 문항 전체 모름·거절
        covered_slots = set()
        for qid, grp in whole_uk.items():
            have = {s for (_, q, _, s) in slot_keys_with_judgment if q == qid}
            remaining = [s for s in self.qslots.get(qid, []) if s not in have]
            if not remaining:
                continue
            ids = []
            for p in self.inp["pendings"]:
                r = p["slot"]
                if r["question_id"] == qid and r["slot_id"] in remaining:
                    ids.append(p["pending_id"])
                    covered_slots.add(skey(r))
            status = "UNKNOWN" if grp[-1]["intent"] == "SAYS_UNKNOWN" else "REJECTED"
            judgments.append(self.base_judgment(grp[0]["target"], status,
                                                pending_handling="DROP" if ids else "NONE", target_pending_ids=ids))

        # 확인 응답
        confirmation = "NONE"
        confirms = cat["confirm"]
        oos_extra = []
        yes = [it for it in confirms if it["intent"] == "CONFIRM_YES"]
        no = [it for it in confirms if it["intent"] == "CONFIRM_NO"]
        if yes and no:
            oos_extra += confirms  # 규칙 4: 둘 다 무관과 같이
        elif confirms:
            if self.aw_action == "ASK_CONFIRM":
                judgments += self.confirm_judgments(confirms, slot_keys_with_judgment, covered_slots, oos_extra)
            elif self.aw_action in ("ASK_CORRECTION_TARGET", "ASK_FINISH", "ASK_STOP"):
                confirmation = "YES" if yes else "NO"
            else:
                oos_extra += confirms

        # 값 없는 정정 요청
        valueless = []
        value_slot_keys = {tkey(j["target"]) for j in judgments
                           if j["status"] in ("ANSWERED", "CORRECTION", "CONFLICT", "UNCLEAR") and is_slot(j["target"])}
        for it in cat["valueless"]:
            t = it["target"]
            if t is not None and is_slot(t) and tkey(t) in value_slot_keys:
                continue  # 값 판정이 있는 슬롯의 값 없는 정정 요청은 버린다
            entry = {"target": t}
            if entry not in valueless:
                valueless.append(entry)

        requests = self.requests(cat["request"])
        risk = None
        if cat["risk"]:
            risk = {"evidence": uniq([it["source_text"] for it in cat["risk"]])}

        # 무효화 대상 문항 (규칙 6)
        inval = []
        for j in judgments:
            if j["status"] in ("CORRECTION", "UNKNOWN", "REJECTED") or (j["status"] is None and j["pending_handling"] == "ACCEPT"):
                inval += self.followups.get(j["target"]["question_id"], [])
        invalidated = uniq(inval)

        # 발화 전체 결과
        if judgments or confirmation != "NONE":
            result = "HAS_ANSWER"
        elif requests or valueless or risk:
            result = "REQUEST_ONLY"
        elif cat["oos"] or oos_extra:
            result = "OUT_OF_SCOPE_ONLY"
        else:
            result = "UNRECOGNIZED_TURN"
        return {
            "judgments": judgments,
            "invalidated_questions": invalidated,
            "utterance_judgment": {
                "result": result, "valueless_correction_requests": valueless, "confirmation": confirmation,
                "requests": requests, "risk_signal": risk,
            },
        }

    def confirm_judgments(self, confirms, slot_keys_with_judgment, covered_slots, oos_extra):
        out = []
        seen = set()
        for it in confirms:
            c = self.ic[it["item_no"]]
            t = it["target"]
            if not is_slot(t):
                t = self.aw["targets"][0] if self.aw["targets"] and is_slot(self.aw["targets"][0]) else None
            pid = self.aw["target_pending_id"]
            p = self.pend_by_id.get(pid) if pid else None
            if t is None or p is None or skey(p["slot"]) != skey(t):
                oos_extra.append(it)
                continue
            k = ("S",) + skey(t)
            if k in slot_keys_with_judgment or skey(t) in covered_slots:
                continue  # 값·모름·거절이 함께 오면 확인 항목은 버린다
            if k in seen:
                continue
            seen.add(k)
            if c["prerequisite_unmet"]:
                out.append(self.base_judgment(t, "PREREQUISITE_UNMET"))
            else:
                out.append(self.base_judgment(
                    t, None, pending_handling="ACCEPT" if it["intent"] == "CONFIRM_YES" else "DROP",
                    target_pending_ids=[pid]))
        return out

    # ---------- 요청 (규칙 7, 8) ----------
    def awaiting_question(self):
        if not self.aw:
            return None
        qs = uniq([t["question_id"] for t in self.aw["targets"]])
        return qs[0] if len(qs) == 1 else None

    def requests(self, items):
        merged = []
        index = {}
        for it in items:
            c = self.ic[it["item_no"]]
            if it["intent"] == "PROGRESS_OP":
                kind = PROGRESS_KIND[it["progress_op"]]
            elif it["intent"] == "GUIDE_REQUEST":
                kind = "GUIDE"
            else:
                kind = "STAFF_REQUEST"
            t = it["target"]
            undefined = "UNKNOWN_TARGET" in c["problems"]
            if t is not None and not undefined:
                qid = t["question_id"]
            elif t is None and kind in ("LATER", "GUIDE"):
                qid = self.awaiting_question()
            else:
                qid = None
            gid = it["guide_id"] if kind == "GUIDE" else None
            key = (kind, gid, qid)
            if key not in index:
                index[key] = len(merged)
                merged.append({"kind": kind, "guide_id": gid, "target_question_id": qid, "source_text": []})
            st = merged[index[key]]["source_text"]
            if it["source_text"] not in st:
                st.append(it["source_text"])
        return merged
