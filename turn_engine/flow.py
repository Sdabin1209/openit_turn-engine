"""문항 순서·건너뛰기 표(QuestionFlowTable). 출력 검증(`validate_extraction`)이 입력으로 받는다. 순수 데이터.

계약(boundary-contracts v2.0.0 INTERFACES I8)은 표의 형식을 정하지 않는다. 이 표는 turn-engine이 정한 형식이다(제안).
문진 스키마의 QuestionBank에서 이 표를 만드는 변환은 아직 없다(미정, docs/change-requests/CR-010).
`DATASET_V2_FLOW`는 학습 데이터셋 v2(IO_SPEC v2)가 쓰는 25개 문항의 순서와 건너뛰기 7건이다.
"""
from __future__ import annotations

from dataclasses import dataclass


def _same(a, b) -> bool:
    """값 비교. bool과 수를 구분한다(True != 1)."""
    return isinstance(a, bool) == isinstance(b, bool) and a == b


@dataclass(frozen=True)
class SkipRule:
    """칸 `slot`(문항.칸, 종류 괄호 없음)에 저장된 값이 `value`이면 문항 `skip_item`은 묻지 않는다."""
    slot: str
    value: object
    skip_item: str


@dataclass(frozen=True)
class QuestionFlowTable:
    order: tuple
    skips: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "order", tuple(self.order))
        object.__setattr__(self, "skips", tuple(self.skips))
        if len(set(self.order)) != len(self.order):
            raise ValueError("문항 순서에 중복이 있다")
        for s in self.skips:
            if s.skip_item not in self.order:
                raise ValueError(f"건너뛸 문항이 순서에 없다: {s.skip_item}")

    def index(self, item: str) -> int | None:
        try:
            return self.order.index(item)
        except ValueError:
            return None

    def is_skipped(self, item: str, saved: dict) -> bool:
        return any(r.skip_item == item and r.slot in saved and _same(saved[r.slot], r.value) for r in self.skips)

    def next_item(self, after: str, saved: dict) -> str:
        """`after` 다음에 물을 문항(건너뛰기 적용) 또는 "END"."""
        i = self.order.index(after) + 1
        while i < len(self.order) and self.is_skipped(self.order[i], saved):
            i += 1
        return self.order[i] if i < len(self.order) else "END"

    def plain_next(self, after: str) -> str:
        i = self.order.index(after) + 1
        return self.order[i] if i < len(self.order) else "END"


DATASET_V2_FLOW = QuestionFlowTable(
    order=["Q1.D%02d" % i for i in range(1, 12)] + ["Q2.D%02d" % i for i in range(1, 6)] + [
        "Q3", "Q4", "Q4_1", "Q5", "Q5_1", "Q6", "Q6_1", "Q7", "Q7_1", "Q7_2", "Q8_1", "Q8_2", "Q9_1", "Q9_2", "Q10"],
    skips=[SkipRule("Q4.answer", False, "Q4_1"), SkipRule("Q5.answer", False, "Q5_1"),
           SkipRule("Q6.answer", False, "Q6_1"), SkipRule("Q7.does_not_drink", True, "Q7_1"),
           SkipRule("Q7.does_not_drink", True, "Q7_2"), SkipRule("Q8_1.days", 0, "Q8_2"),
           SkipRule("Q9_1.days", 0, "Q9_2")],
)
