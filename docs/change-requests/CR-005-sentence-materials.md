# CR-005 문장 재료(`sentence_materials`) 선택 규칙과 안내 채울 값

- 대상: `docs/rules/dialogue_planner.md` 8절, `PlannerOutput.directive.sentence_materials`, `GuideItem.fill_value`
- 상태: 결정함(아래 "결정" 절)

## 부족한 것

규칙 문서는 "알릴 것", "말할 값", 행동 선택을 정하지만, 응답 지시의 `sentence_materials`(문항 문장, 거절 설명, 다시 묻기 문장, 선택지, 안내 문장, 고정 문장)를 어떤 행동에 무엇을 담는지는 정하지 않는다. 안내의 `fill_value: REMAINING_COUNT`를 어디에 어떤 형식으로 담는지도 없다.

## 지금 구현(임시 해석)

- 묻는 행동 다섯 가지(다음 문항 묻기, 빠진 슬롯 되묻기, 구체화 요청, 모름 뒤 재질문, 거절 시 설명 후 재질문)의 대상 문항에 `question_sentences`. 거절 시 설명 후 재질문에만 `refusal_explanations`. 다음 문항 묻기 외에는 대상 슬롯의 `reask_sentences`. 대상 슬롯의 선택지 이름(선택지 목록 또는 `choice_catalog` 라벨)은 `choices`.
- 알릴 것의 안내(GUIDE)는 `guide_list`(문항별이면 문항의 `guide_sentences`)에서 문장을 찾아 `guide_sentences`에 담는다. 문장을 찾지 못한 안내 요청(없는 guide_id, 대상 문항 없는 문항별 안내)은 무관으로 본다.
- 고정 문장: 행동과 알릴 것에 대응하는 키(`ASK_REPEAT`, 무관 안내=`OOS_NOTICE` 등)만 `session_settings.fixed_sentences`에서 담는다.
- `REMAINING_COUNT` 채울 값: 알릴 것 `value`에 남은 열린 문항 수(건너뛴 문항 제외, 미룬 문항 포함)를 문자열로 담는다.
- 기다리는 답이 있는 비질문 행동(무관 안내 등)은 기다리는 답의 재료도 함께 담는다.

## 제안

행동별로 담을 재료 목록과 `REMAINING_COUNT`의 형식(`Notice.value`의 `Value` 형식)을 규칙 문서에 적기.

## 결정 (헤드 답변: 잠정 승인 + 골든 대조, 2026-10-15)

골든 `PlannerOutput.directive.sentence_materials` 223쌍과 대조해 해석을 맞췄다(a). 골든이 보여 준 규칙:

| 행동 | 재료 |
|---|---|
| 다음 문항 묻기, 모름 뒤 재질문 | 문항 문장 + 대상 문항 슬롯의 선택지 |
| 거절 시 설명 후 재질문 | 문항 문장 + 거절 설명 + 선택지 |
| 빠진 슬롯 되묻기, 구체화 요청 | 대상 슬롯의 다시 묻기 문장 + 선택지(문항 문장 없음) |
| 확인 대기 확인, 정정 구체화, 종료·중단 확인, 대기 안내, 위험·직원 안내, 종료 인사 | 고정 문장만 |
| 무관 안내(REDIRECT), 다시 말씀 요청(ASK_REPEAT) | 고정 문장 + 기다리는 답의 재료(문항 문장, 선택지 등) |

고정 문장은 행동의 키와 알릴 것(재개, 문진 중단, 미룸)의 키만 담는다(기다리는 답의 키는 담지 않는다). 안내(GUIDE)의 `REMAINING_COUNT` 채울 값은 `Notice.value = {"amount": 남은 문항 수, "unit": "문항"}`(골든 E2, E5a, R11). 미룸 알림(DEFERRED)의 `slot`은 항상 `null`(골든 D3a, N7a). 빠진 슬롯 되묻기의 `reask_reasons`는 빈 목록(골든 B2, E1c, E3b, S8b).

골든이 가려 주지 못한 것(남음): 무관한 말이 답과 함께 올 때 고정 문장 `OOS_NOTICE`를 더하는 규칙(골든 K4). 플래너 입력에는 무관 항목이 있었다는 정보가 없어 도출할 수 없다. 이 규칙을 원하면 `UtteranceJudgment`에 표시가 필요하다(스키마 변경 요청).
