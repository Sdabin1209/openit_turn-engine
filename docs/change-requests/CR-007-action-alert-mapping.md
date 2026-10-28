# CR-007 규칙 용어와 Action·AlertKind 대응

- 대상: v1 규칙 문서 dialogue_planner 8-1절(보관) 규칙 2·14, 규칙 1, `PlannerOutput`의 `Action`, `AlertKind`, `StaffAlertReason`
- 상태: 결정함(아래 "결정" 절)

## 부족한 것

규칙은 "사람 연결 안내", "도움 요청", "직원 알림(위험 | 사람 요청 | 도움 요청)"이라고 쓰고 계약은 행동 `CALL_STAFF`·`STAFF_NOTICE`, 알림 종류 `RISK`·`CALL_STAFF`·`USER_CALLED_STAFF`를 둔다. 둘의 대응이 문서에 없다. `StaffAlertReason`에는 위험 신호·위험 기준·사용자 직원 요청만 있어 도움 요청의 사유를 담을 곳이 없다.

## 지금 구현(임시 해석)

| 규칙 | 행동 | 알림 종류 | 사유 |
|---|---|---|---|
| 규칙 1 위험 | `RISK_NOTICE` | `RISK` | 위험 신호 근거, 위험 기준 대상 |
| 규칙 2 사람 요청 | `CALL_STAFF` | `USER_CALLED_STAFF` | 사용자 직원 요청 근거 |
| 규칙 14·19 도움 요청 | `STAFF_NOTICE` | `CALL_STAFF` | 빈 목록 |

위험과 사람 요청이 같은 턴이면 알림은 `RISK` 하나이고 사유에 `USER_CALLED_STAFF`를 더한다(알림 종류가 하나뿐이라서).

## 제안

대응표를 규칙 문서에 적고, 도움 요청 사유 종류(`HELP_REQUEST` 등)를 `StaffAlertReason`에 추가할지 정하기(MINOR).

## 결정 (헤드 답변 + 골든 대조, 2026-10-15)

골든이 대응을 가렸다(a): 사람 요청은 행동 `STAFF_NOTICE`+알림 `USER_CALLED_STAFF`(골든 F1, F2, R3, R6), 도움 요청(알아듣지 못함의 연속, 종료 확인의 물음 상한)은 행동 `CALL_STAFF`+알림 `CALL_STAFF`(골든 F3, H5b). 처음 쓴 대응표는 두 행동이 서로 바뀌어 있었다. 도움 요청 알림의 사유는 빈 목록(골든 일치). `StaffAlertReason`에 도움 요청 사유를 더할지는 survey-service가 시작할 때 정한다. 위험+사람 요청 동시 발화의 알림 처리는 골든에 없다(남음).

골든이 정한 곁가지: 종료 확인의 물음 상한에서 도움 요청은 기다리는 답이 없고(`awaiting: null`), 물은 횟수는 상한에서 더 오르지 않는다(골든 H5b). 그래서 그 뒤에도 매 턴 도움 요청과 알림이 반복된다("알림은 한 번"은 알아듣지 못함의 연속에만 적용).
