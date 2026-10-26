#!/usr/bin/env python3
"""LoRA-A 학습 데이터(JSONL, 학습 서버 형식)를 표준입력으로 받아 `validate_extraction`으로 전수 검사한다. 파일을 쓰지 않는다.

  ssh openit 'cat ~/taehyeon/data/dataset_10_14/lora_a_train.jsonl' | .venv/bin/python scripts/validate_dataset_a.py
  ssh openit 'cat ~/taehyeon/data/dataset_10_14/lora_a_*.jsonl' | .venv/bin/python scripts/validate_dataset_a.py --mutate

행은 {messages: [system, user, assistant], scenario_id, ...}. user -> ActionExtractionInput, assistant -> ActionExtraction.
위반이 하나라도 있으면 종료 코드 1. `--mutate`는 출력을 일부러 망가뜨려 검사기가 잡는지 센다(시드 고정, 결정적).
"""
import collections
import copy
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import turn_engine as te  # noqa: E402


def rows(stream):
    for line in stream:
        if line.strip():
            r = json.loads(line)
            yield r.get("scenario_id"), json.loads(r["messages"][1]["content"]), json.loads(r["messages"][2]["content"])


def mutations(u, o, rng):
    """(이름, 망가뜨린 출력) 목록. 원래 출력과 의미가 같아질 수 있는 변형은 만들지 않는다."""
    out = []
    order = te.DATASET_V2_FLOW.order
    if o["action"] in ("REASK", "REDIRECT", "CONFIRM", "NEXT", "CORRECT", "HOLD", "SKIP"):
        m = copy.deepcopy(o)
        others = [i for i in list(order) + ["END"] if i != o["next_item"]]
        m["next_item"] = rng.choice(others)
        out.append(("next_item 바꿈", m))
    if o["values"]:
        m = copy.deepcopy(o)
        v = rng.choice(m["values"])
        v["save"] = not v["save"]
        out.append(("save 뒤집음", m))
        m = copy.deepcopy(o)
        v = rng.choice([x for x in m["values"]])
        if v["status"] in ("ANSWERED", "CORRECTION"):
            v["status"] = "MISSING"          # save true인데 MISSING
        else:
            v["value"] = 1                    # 값 없는 status에 값
        out.append(("status/value 어긋남", m))
    if o["action"] in ("REASK", "CONFIRM", "HOLD", "SKIP"):
        m = copy.deepcopy(o)
        m["targets"] = list(o.get("targets", [])) + ["Q3.nonexistent_slot"]
        out.append(("없는 target 추가", m))
    return out


def main(argv):
    mutate = "--mutate" in argv
    flow = te.DATASET_V2_FLOW
    total = bad_rows = 0
    codes = collections.Counter()
    examples = {}
    caught = collections.Counter()
    made = collections.Counter()
    rng = random.Random(20261027)
    for sid, u, o in rows(sys.stdin):
        total += 1
        vs = te.validate_extraction(u, o, flow)
        if vs:
            bad_rows += 1
            for v in vs:
                codes[v.code] += 1
                examples.setdefault(v.code, sid)
        if mutate and not vs:
            for name, m in mutations(u, o, rng):
                made[name] += 1
                caught[name] += bool(te.validate_extraction(u, m, flow))
    print(f"rows={total} violating_rows={bad_rows}")
    for c, n in codes.most_common():
        print(f"  {c}: {n} (예: {examples[c]})")
    if mutate:
        for name in made:
            print(f"  mutate[{name}]: {caught[name]}/{made[name]} 검출")
    return 1 if bad_rows else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
