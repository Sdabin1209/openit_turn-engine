"""입출력 예시를 만든다: 시험용 오케스트레이터 흉내(tests/sim.py)로 시나리오를 돌려 마지막 턴의 입력과 출력을 저장한다.
입력은 입력 계약 스키마를 통과하고, 출력은 현재 코드가 낸 값이다(시험이 이 값과 비교한다).
사용: python scripts/gen_examples.py   (예시를 바꾸려면 출력 변경을 검토한 뒤 다시 만든다)"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import turn_engine as te  # noqa: E402
from fixtures import *  # noqa: E402,F401
from sim import Session  # noqa: E402

SL, DR, AM, AK = ref(SLEEP, "hours"), ref(DRINK, "status"), ref(AMOUNT, "amount"), ref(AMOUNT, "kind")
VT, PN, NT = ref(VISIT, "times"), ref(PAIN, "level"), ref(NOTE, "text")


def start():
    s = Session()
    s.nonutterance("SESSION_START")
    return s


def sc_first_answer():
    s = start()
    s.turn([item(0, DR, "안 마시고요")])
    s.turn([item(0, SL, "일곱이요")])
    return s


def sc_conflict():
    s = start()
    s.turn([item(0, DR, "안 마시고요"), item(1, SL, "7시간")])
    s.turn([item(0, SL, "8시간")])
    return s


def sc_confirm_yes():
    s = sc_conflict()
    s.turn([item(0, None, None, "CONFIRM_YES")])
    return s


def sc_correction_invalidates():
    s = start()
    s.turn([item(0, DR, "마시고요"), item(1, AM, "두 병"), item(2, AK, "소주")])
    s.turn([item(0, DR, "안 마시고요", "CORRECTION_MARKED")])
    return s


def sc_mismatch_pair():
    s = start()
    s.turn([item(0, DR, "마시고요")])
    s.turn([item(0, DR, "안 마시고요"), item(1, AK, "소주")])
    return s


def sc_unknown():
    s = start()
    s.turn([item(0, DR, "안 마시고요")])
    s.turn([item(0, whole(SLEEP), None, "SAYS_UNKNOWN")])
    return s


def sc_risk():
    s = start()
    s.turn([item(0, None, None, "RISK_SIGNAL", text="가슴이 너무 아파요")])
    return s


def sc_finish_yes():
    s = start()
    s.turn([item(0, DR, "안 마시고요"), item(1, SL, "7시간"), item(2, VT, "주에 두 번"), item(3, PN, "약함"), item(4, NT, "없음")])
    s.turn([item(0, None, None, "CONFIRM_YES")])
    return s


def sc_guide():
    s = start()
    s.turn([item(0, None, None, "GUIDE_REQUEST", guide="g_left")])
    return s


def sc_resume():
    s = start()
    s.turn([item(0, None, None, "RISK_SIGNAL", text="숨이 안 쉬어져요")])
    s.nonutterance("RESUME")
    return s


SCENARIOS = {f[3:]: v for f, v in list(globals().items()) if f.startswith("sc_")}
OUT = ROOT / "examples"


def main():
    OUT.mkdir(exist_ok=True)
    for name, fn in SCENARIOS.items():
        s = fn()
        outs = {"normalize": te.normalize, "judge": te.judge, "write_record": te.write_record, "plan": te.plan}
        for comp, f in outs.items():
            if comp not in s.last_inputs:
                continue
            inp = s.last_inputs[comp]
            (OUT / f"{name}.{comp}.json").write_text(
                json.dumps({"input": inp, "output": f(inp)}, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                encoding="utf-8")
    print(len(list(OUT.glob("*.json"))), "files")


if __name__ == "__main__":
    main()
