# CR-010: 문항 순서·건너뛰기 표(QuestionFlowTable)의 출처

상태: 열림(헤드 결정 필요). 작성 2026-10-27, boundary-contracts v2.0.0 이전 작업에서.

## 확인한 것

- `INTERFACES.md` I8은 "문항 순서·건너뛰기 표는 문진 스키마가 소유하고 이 계약은 표의 형식을 정하지 않는다"고 한다. 헤드 지시서는 "`QuestionFlowTable`은 문진 스키마에서 만든다"고 한다.
- `../survey-service/schema/schemas/QuestionBank.json`을 읽었다. 문항은 `order`(정수)와 `prerequisite`(`{slot: SlotRef, value: 문자열}` 또는 null)를 갖는다. 문항 ID와 칸은 v1 형식(`question_id`, `repeat_key`, `slot_id`)이고 `value`는 문자열 하나다.
- 학습 데이터 v2의 문항 ID(`Q1.D01`, `Q4_1`, …)와 칸 키(`Q4.answer`, `Q7[soju].amount`)는 이 QuestionBank 형식과 다르다. 건너뛰기 7건은 불리언(`Q4.answer == false`, `Q7.does_not_drink == true`)과 수(`Q8_1.days == 0`)의 같음 조건이다.

## 지금 한 것(제안)

- turn-engine이 표 형식을 정했다: `QuestionFlowTable(order, skips)`, `SkipRule(slot, value, skip_item)`(`turn_engine/flow.py`). 값 비교는 불리언과 수를 구분한다.
- 학습 데이터 v2의 순서(31문항)와 건너뛰기 7건을 `DATASET_V2_FLOW`로 상수에 두었다. 출처는 `boundary-contracts/tools/validate_dataset_v2.py`의 `ORDER`/`SKIPS`다(그 도구와 같은 값. 문진 스키마에서 가져온 것이 아니다).
- QuestionBank에서 표를 만드는 변환은 **만들지 않았다**. 이유: (1) 위 ID·칸 형식이 다르다, (2) `prerequisite.value`가 문자열이라 불리언·수 조건(`days == 0`)을 표현하지 못한다.

## 요청

1. 문항 순서·건너뛰기 표의 소유와 형식을 정해 달라(문진 스키마에 v2 문항 은행을 두는지, survey-service가 표를 직접 만들어 넘기는지). 정해지면 turn-engine은 그 형식에서 `QuestionFlowTable`을 만드는 함수를 더한다.
2. 그 전까지 survey-service는 `QuestionFlowTable`을 직접 만들어 넘기거나 `DATASET_V2_FLOW`를 쓴다. 후자는 임시이며 문항 은행이 바뀌면 틀린다.
