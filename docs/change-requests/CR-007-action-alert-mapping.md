# CR-007 규칙 용어와 Action·AlertKind 대응

- 대상: `docs/rules/dialogue_planner.md` 8-1절 규칙 2·14, 규칙 1, `PlannerOutput`의 `Action`, `AlertKind`, `StaffAlertReason`
- 상태: 요청

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
