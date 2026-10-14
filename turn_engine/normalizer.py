"""Answer Normalizer: 항목 값을 표준 형태로 바꾸고 문제·비교·선행 조건을 사실로 표시한다.
규칙 출처: docs/rules/answer_normalizer.md (5절). 대응표는 docs/design.md."""
from __future__ import annotations

from ._common import (
    check_input, check_output, is_slot, is_whole, ref_of, same_value, skey, value_matches_text, vkey,
)
from . import _text

VALUE_INTENTS = ("ANSWERED_INTENT", "CORRECTION_MARKED")
UNKNOWN_INTENTS = ("SAYS_UNKNOWN", "SAYS_REFUSAL")


def normalize(input: dict) -> dict:
    """(AnswerNormalizerInput) -> NormalizerOutput. 순수 함수."""
    check_input("AnswerNormalizerInput", input)
    out = _Normalizer(input).run()
    check_output("NormalizerOutput", out)
    return out


class _Normalizer:
    def __init__(self, inp: dict):
        self.inp = inp
        self.items = inp["items"]
        self.qmap = {q["question_id"]: q for q in inp["related_questions"]}
        self.slotdef = {(q["question_id"], s["slot_id"]): s for q in inp["related_questions"] for s in q["slots"]}
        self.cur = {}
        for cv in inp["current_values"]:
            self.cur.setdefault(skey(cv["slot"]), cv)
        self.pend = {}
        for p in inp["pendings"]:
            self.pend.setdefault(skey(p["slot"]), p)
        self.awaiting = inp["awaiting"]
        self.base = {}  # item_no(인덱스) -> dict

    # ---------- 정의 확인 ----------
    def target_defined(self, t) -> bool:
        if t is None:
            return True
        q = self.qmap.get(t["question_id"])
        if q is None:
            return False
        if is_whole(t):
            return True
        if (t["question_id"], t["slot_id"]) not in self.slotdef:
            return False
        rks = q["repeat_keys"]
        return (t["repeat_key"] in rks) if rks else (t["repeat_key"] == "")

    # ---------- 값 표준화 (규칙 1, 2, 8) ----------
    def standardize(self, slot: dict, raw: str):
        """(표준 값 또는 None, 문제 목록, 정밀도). 지어내지 않고 걸리지 않으면 AMBIGUOUS."""
        d = self.slotdef[(slot["question_id"], slot["slot_id"])]
        text = raw.strip()
        approx = _text.is_approximate(text)
        units = d["units"]
        has_choice = bool(d["choices"]) or bool(d.get("choice_catalog"))
        if units:
            names = [n for u in units for n in [u["name"], *u["synonyms"]]]
            nums = _text.find_numbers(text, [_text.strip_number_place(n) for n in names])
            if nums:
                if len(nums) > 1 or nums[0][2] is None:
                    return None, ["AMBIGUOUS"], False  # 범위 값: 모호함 하나만
                return self.quantity(d, units, text, nums[0][2], approx)
            if not has_choice:
                return None, ["AMBIGUOUS"], False
        if has_choice:
            return self.choice(d, text, approx)
        # 선택지·단위가 없는 자유 값은 그대로 표준 값
        return text, [], approx

    def quantity(self, d, units, text, amount, approx):
        squashed = _text.squash(text)
        matched = []
        for i, u in enumerate(units):
            if any(_text.unit_name_matches(n, squashed) for n in [u["name"], *u["synonyms"]]):
                matched.append(i)
        if len(matched) > 1:
            return None, ["AMBIGUOUS"], False
        if matched:
            u = units[matched[0]]
        elif len(units) == 1:
            u = units[0]  # 단위가 하나뿐인 슬롯: 단위 없는 숫자는 그 단위
        else:
            return None, ["NO_UNIT"], False
        problems = []
        if u["range"] is not None and not (u["range"][0] <= amount <= u["range"][1]):
            problems.append("OUT_OF_RANGE")
        conv = u["convert_to"]
        if conv:
            amount2 = round(amount * conv["factor"], 10)
            value = {"amount": amount2, "unit": conv["unit"]}
            if conv.get("unit_code"):
                value["unit_code"] = conv["unit_code"]
            target = next((x for x in units if x["name"] == conv["unit"]), None)
            if target and target["range"] is not None and not (target["range"][0] <= amount2 <= target["range"][1]):
                if "OUT_OF_RANGE" not in problems:
                    problems.append("OUT_OF_RANGE")
        else:
            amount2 = amount
            value = {"amount": amount, "unit": u["name"]}
            if u.get("code"):
                value["unit_code"] = u["code"]
        if problems:
            return None, problems, False
        return _intify(value), [], approx

    def choice(self, d, text, approx):
        squashed = _text.squash(text)
        catalog = d.get("choice_catalog")
        if catalog:
            entries = [(c, [c["label"], *c["synonyms"]]) for c in catalog]
        else:
            entries = [(c, [c]) for c in d["choices"]]

        def as_value(c):
            return {"code": c["code"], "label": c["label"]} if catalog else c

        by_name = [c for c, names in entries if any(_text.squash(n) in squashed for n in names)]
        cands = by_name
        if not cands:
            cands = [c for c, names in entries
                     if any((s := _text.stem(n)) and s in squashed for n in names)]
        neg_marker = _text.has_negation(text)
        ynm = d.get("yes_no_map")
        if cands and neg_marker and ynm:
            no_entry = [c for c, names in entries if _matches_yn(c, names, ynm["no"], catalog)]
            if no_entry:
                if len(cands) == 1 and cands[0] in no_entry:
                    pass  # 이미 아니요에 해당하는 선택지
                elif by_name and len(cands) == 1 and _name_has_marker(cands[0], catalog):
                    pass  # 이름 자체가 부정 표지를 담는 선택지는 그대로
                else:
                    cands = [no_entry[0]]
        if len(cands) != 1:
            return None, ["AMBIGUOUS"], False
        return as_value(cands[0]), [], approx

    # ---------- 기본 검사 ----------
    def base_check(self, it: dict) -> dict:
        b = {"std": None, "problems": [], "approx": False, "mismatched": [], "unmet": False}
        t = it["target"]
        if t is not None and not self.target_defined(t):
            b["problems"].append("UNKNOWN_TARGET")
            return b
        if it["intent"] in VALUE_INTENTS and it["value"] is not None and t is not None:
            if is_whole(t):
                b["problems"].append("AMBIGUOUS")  # 슬롯을 정할 수 없다(CR-002)
            else:
                std, problems, approx = self.standardize(t, it["value"])
                b["std"], b["problems"], b["approx"] = std, problems, approx
        return b

    # ---------- 비교 ----------
    def compare(self, it, b):
        t = it["target"]
        if b["std"] is None or not is_slot(t):
            return "NOT_APPLICABLE", "NOT_APPLICABLE"
        k = skey(t)
        cv = self.cur.get(k)
        cur = cv["current_value"] if cv else "NONE"
        if isinstance(cur, dict):
            vs_cur = "EQUAL" if same_value(cur["answer"], b["std"]) else "DIFFERENT"
        else:
            vs_cur = "NO_CURRENT"
        p = self.pend.get(k)
        if p is None:
            vs_pend = "NO_PENDING"
        else:
            vs_pend = "EQUAL" if same_value(p["value"], b["std"]) else "DIFFERENT"
        return vs_cur, vs_pend

    def risk(self, it, b):
        t = it["target"]
        if b["std"] is None or not is_slot(t):
            return None
        d = self.slotdef[(t["question_id"], t["slot_id"])]
        rr = d["risk_rule"]
        if not rr:
            return None
        a, c = _comparable(b["std"]), _comparable(rr["value"])
        if a is None or c is None:
            return None
        if rr["operator"] == "=":
            ok = a == c
        else:
            ok = isinstance(a, tuple) and isinstance(c, tuple) and a[0] == c[0] and a[1] >= c[1]
        return rr["response"] if ok else None

    # ---------- 선행 조건 (규칙 3, 4) ----------
    def prereq_value(self, key):
        """(값 또는 None, 이번 발화에서 왔는가, 정정 표지가 있는가)."""
        s_items = [i for i, it in enumerate(self.items) if is_slot(it["target"]) and skey(it["target"]) == key]
        value_items = [i for i in s_items if self.items[i]["intent"] in VALUE_INTENTS and self.items[i]["value"] is not None]
        if value_items:
            stds = [self.base[i]["std"] for i in value_items]
            if all(s is not None for s in stds) and all(same_value(stds[0], s) for s in stds):
                corr = any(self.items[i]["intent"] == "CORRECTION_MARKED" for i in s_items)
                return stds[0], True, corr
        else:
            aw = self.awaiting
            intents = [it["intent"] for it in self.items if self._confirm_slot(it) == key]
            if (aw and aw["action"] == "ASK_CONFIRM" and "CONFIRM_YES" in intents and "CONFIRM_NO" not in intents):
                p = self._awaited_pending(key)
                if p is not None:
                    return p["value"], False, False
            qid = key[0]
            for it in self.items:
                if it["intent"] in UNKNOWN_INTENTS and it["target"] is not None and (
                    (is_slot(it["target"]) and skey(it["target"]) == key)
                    or (is_whole(it["target"]) and it["target"]["question_id"] == qid)
                ):
                    return None, False, False
        cv = self.cur.get(key)
        if cv and isinstance(cv["current_value"], dict):
            return cv["current_value"]["answer"], False, False
        return None, False, False

    def _confirm_slot(self, it):
        if it["intent"] not in ("CONFIRM_YES", "CONFIRM_NO"):
            return None
        if is_slot(it["target"]):
            return skey(it["target"])
        aw = self.awaiting
        if aw and aw["action"] == "ASK_CONFIRM" and aw["targets"] and is_slot(aw["targets"][0]):
            return skey(aw["targets"][0])
        return None

    def _awaited_pending(self, key):
        aw = self.awaiting
        pid = aw["target_pending_id"] if aw else None
        for p in self.inp["pendings"]:
            if skey(p["slot"]) == key and (pid is None or p["pending_id"] == pid):
                return p
        return None

    def prereq_state(self, qdef):
        """선행 조건 평가: ('OK'|'UNMET'|'MISMATCH', 값 출처 정보)."""
        cond = qdef["prerequisite"]
        if not cond:
            return "OK", None
        key = skey(cond["slot"])
        val, from_utt, corr = self.prereq_value(key)
        if val is None:
            return "UNMET", None
        if value_matches_text(val, cond["value"]):
            if from_utt and self._conflict_to_be(key, val, corr):
                return "UNMET", None
            return "OK", None
        return "MISMATCH", from_utt

    def _conflict_to_be(self, key, val, corr):
        cv = self.cur.get(key)
        if not (cv and isinstance(cv["current_value"], dict)):
            return False
        if same_value(cv["current_value"]["answer"], val) or corr:
            return False
        p = self.pend.get(key)
        return not (p is not None and same_value(p["value"], val))

    def apply_prerequisites(self):
        followup_intents = VALUE_INTENTS + UNKNOWN_INTENTS + ("CONFIRM_YES", "CONFIRM_NO", "PROGRESS_OP")
        for i, it in enumerate(self.items):
            b = self.base[i]
            if "UNKNOWN_TARGET" in b["problems"] or it["intent"] not in followup_intents:
                continue
            if it["intent"] == "PROGRESS_OP" and it["progress_op"] != "LATER":
                continue
            t = it["target"]
            if it["intent"] in ("CONFIRM_YES", "CONFIRM_NO"):
                ck = self._confirm_slot(it)
                qid = ck[0] if ck else None
            else:
                qid = t["question_id"] if t is not None else None
            q = self.qmap.get(qid)
            if q is None or not q["prerequisite"]:
                continue
            state, from_utt = self.prereq_state(q)
            if state == "OK":
                continue
            if state == "UNMET":
                b["unmet"] = True
                continue
            # 조건과 맞지 않음
            is_value = (it["intent"] in VALUE_INTENTS and b["std"] is not None and is_slot(t)
                        and not self._is_negative(t, b["std"]))
            if is_value:
                b["problems"].append("MISMATCH")
                b["std"] = None  # 골든(S2b, S6a, B4): 문제가 있어 표준화하지 못한 항목은 표준 값 없음
                b["approx"] = False
                cond_slot = q["prerequisite"]["slot"]
                b["mismatched"] = [cond_slot]
                if from_utt:
                    ckey = skey(cond_slot)
                    for j, it2 in enumerate(self.items):
                        if (is_slot(it2["target"]) and skey(it2["target"]) == ckey and it2["intent"] in VALUE_INTENTS
                                and it2["value"] is not None and self.base[j]["std"] is not None):
                            b2 = self.base[j]
                            if "MISMATCH" not in b2["problems"]:
                                b2["problems"].append("MISMATCH")
                            b2["flag_std_clear"] = True
                            if not any(skey(r) == skey(t) for r in b2["mismatched"]):
                                b2["mismatched"].append(ref_of(skey(t)))
            else:
                b["unmet"] = True

        for b in self.base.values():
            if b.pop("flag_std_clear", False):
                b["std"], b["approx"] = None, False

    def _is_negative(self, t, std) -> bool:
        d = self.slotdef[(t["question_id"], t["slot_id"])]
        ynm = d.get("yes_no_map")
        return bool(ynm) and value_matches_text(std, ynm["no"])

    # ---------- 빠진 필수 슬롯 ----------
    def missing_slots(self):
        triggers = []  # (question order, qid, repeat_key)
        seen = set()
        for i, it in enumerate(self.items):
            b = self.base[i]
            t = it["target"]
            if (it["intent"] in VALUE_INTENTS and it["value"] is not None and is_slot(t)
                    and "UNKNOWN_TARGET" not in b["problems"] and "MISMATCH" not in b["problems"]
                    and not b["unmet"]):
                k = (t["question_id"], t["repeat_key"])
                if k not in seen:
                    seen.add(k)
                    triggers.append(k)
        out = []
        for qid, rk in sorted(triggers, key=lambda k: (self.qmap[k[0]]["order"], k[0], k[1])):
            q = self.qmap[qid]
            for s in q["slots"]:
                if not s["required"]:
                    continue
                key = (qid, rk, s["slot_id"])
                cv = self.cur.get(key)
                if cv and cv["current_value"] != "NONE":
                    continue
                touched = False
                for it in self.items:
                    t = it["target"]
                    if t is None:
                        continue
                    if is_slot(t) and skey(t) == key and (it["intent"] in VALUE_INTENTS or it["intent"] in UNKNOWN_INTENTS):
                        touched = True
                    elif is_whole(t) and t["question_id"] == qid and it["intent"] in UNKNOWN_INTENTS:
                        touched = True
                if not touched:
                    out.append(ref_of(key))
        return out

    # ---------- 실행 ----------
    def run(self) -> dict:
        for i, it in enumerate(self.items):
            self.base[i] = self.base_check(it)
        self.apply_prerequisites()
        checks = []
        for i, it in enumerate(self.items):
            b = self.base[i]
            vs_cur, vs_pend = self.compare(it, b)
            ic = {
                "item_no": it["item_no"],
                "standard_value": b["std"],
                "problems": b["problems"],
                "mismatched_slots": b["mismatched"],
                "vs_current": vs_cur,
                "vs_pending": vs_pend,
                "risk_rule": self.risk(it, b),
                "prerequisite_unmet": b["unmet"],
            }
            if b["approx"] and b["std"] is not None:
                ic["value_metadata"] = {"precision": "approximate", "evidence": []}
            checks.append(ic)
        return {"item_checks": checks, "missing_required_slots": self.missing_slots()}


def _intify(v):
    if isinstance(v, dict) and isinstance(v.get("amount"), float) and v["amount"].is_integer():
        v = dict(v)
        v["amount"] = int(v["amount"])
    return v


def _matches_yn(c, names, yn_text, catalog) -> bool:
    if catalog:
        return c["code"] == yn_text or c["label"] == yn_text
    return c == yn_text


def _name_has_marker(c, catalog) -> bool:
    name = c["label"] if catalog else c
    return _text.has_negation(name)


def _comparable(v):
    """위험 기준 비교용: 수량은 (단위, 양), 문자열·코드는 대표 문자열."""
    if isinstance(v, dict) and "amount" in v:
        return (v["unit"], v["amount"])
    if isinstance(v, dict) and "code" in v:
        return v["code"]
    if isinstance(v, str):
        return v
    return None
