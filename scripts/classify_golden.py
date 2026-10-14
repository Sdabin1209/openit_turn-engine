"""골든과 다른 출력을 분류해 tests/golden_known.json을 만든다.
분류: a=구현 결함(고쳤으니 여기 남지 않는다), b=규칙 해석 차이/문서 밖, c=예시 자체의 오류(예시 안의 모순).
사용: python scripts/classify_golden.py   (분류는 아래 규칙으로 자동 지정하고, 사람이 정한 것만 MANUAL에 둔다)"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import test_golden as T  # noqa: E402


def diff(a, b, path=""):
    out = []
    if type(a) != type(b):
        return [path]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(path + "/" + k)
            else:
                out += diff(a[k], b[k], path + "/" + k)
    elif isinstance(a, list):
        if len(a) != len(b):
            return [path]
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, path + f"/{i}")
    elif a != b:
        out.append(path)
    return out


MANUAL = {
    "S6c/t1/AnswerJudgeInput": ("b", "판정 순서: 이 예시는 확인 항목(선행 불충족)을 정정 판정 뒤에 둔다. S6b·S8b·S6a는 확인 항목이 앞이다. 항목 순서를 따르는 구현과 다르다(CR-008)"),
    "S6a/t1/AnswerJudgeInput": ("c", "확인 판정에 같은 턴 다른 판정의 사유(MISMATCH)·말한 값이 복사돼 있고, 다른 판정에 확인 대기 받아들임이 복사돼 있다"),
    "S6b/t1/AnswerJudgeInput": ("c", "다른 슬롯의 선행 불충족 판정에 확인 대기 받아들임(대기 ID X)이 복사돼 있다"),
    "S8b/t1/AnswerJudgeInput": ("c", "값 판정(ANSWERED)에 다른 슬롯의 확인 대기 받아들임(대기 ID X)이 복사돼 있다"),
    "S8b/t1/RecordWriterInput": ("c", "첫 저장(FIRST_WRITE)에 다른 슬롯의 대기 ID X가 붙어 있고, 결정 순서가 판정 순서와 다르다(받아들임이 앞)"),
    "R13/t1/RecordWriterInput": ("c", "모름 기록(RECORD_UNKNOWN)에 대기 ID X가 붙어 있다(기록 결정은 대기 ID를 갖지 않는다)"),
    "X2/t1/RecordWriterInput": ("c", "모름 기록(RECORD_UNKNOWN)에 대기 ID X가 붙어 있다(기록 결정은 대기 ID를 갖지 않는다)"),
    "K4/t1/DialoguePlannerInput": ("b", "무관한 말이 답과 함께 왔을 때 고정 문장(OOS_NOTICE)을 재료에 더한다. 플래너 입력에는 무관 항목이 있었다는 정보가 없어 도출할 수 없다(CR-005)"),
}


def classify(key, c, got, exp):
    if key in MANUAL:
        return MANUAL[key]
    paths = [re.sub(r"/\d+", "/#", p) for p in diff(got, exp)]
    if c == "AnswerNormalizerInput":
        return ("b", "어휘: 규칙 5절 규칙 8 범위 밖의 말 이음(불규칙 활용 '피워요'↔'피움', 단독 '네'·'안 해요'→예·아니요). 선택지에 동의어가 없는 평문 선택지다(CR-001)")
    allowed = ("target_pending_id", "pending_id", "target_pending_ids/#", "fixed_sentences/#/sentence")
    if paths and all(any(p.endswith(a) for a in allowed) for p in paths):
        if any(p.endswith("fixed_sentences/#/sentence") for p in paths):
            return ("c", "고정 문장 본문이 이 예시 입력의 session_settings.fixed_sentences와 다르다(예시 안의 모순)")
        return ("c", "확인 대기 ID 자리표시자가 예시 입력의 ID와 다르다(입력 N1, 출력 X 등; 예시 안의 모순)")
    return ("?", "분류 없음: " + ",".join(paths[:4]))


def main():
    known = {}
    for case, turn, c, inp, exp in T.ALL:
        key = f"{case}/t{turn}/{c}"
        try:
            got = T.FUNC[c](inp)
        except Exception as e:  # noqa: BLE001
            known[key] = ["?", f"예외 {type(e).__name__}"]
            continue
        got, exp = T.mask(c, got), T.mask(c, exp)
        if got != exp:
            known[key] = list(classify(key, c, got, exp))
    (ROOT / "tests" / "golden_known.json").write_text(
        json.dumps(known, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    import collections
    print(len(T.ALL), "쌍,", len(known), "다름", dict(collections.Counter(v[0] for v in known.values())))


if __name__ == "__main__":
    main()
