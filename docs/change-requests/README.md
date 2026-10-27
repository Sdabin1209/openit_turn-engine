# 변경 요청 (turn-engine → 헤드)

> 0.4.0(G07)에서 CR-001~009가 다룬 v1 함수(normalize, judge, write_record, plan)를 제거했다. 이 표는 역사 기록이다.

규칙 문서(`docs/rules/`)나 문진 스키마에 없거나 충돌하는 정책을 만났을 때 쓴다. 각 요청에는 "지금 구현이 한 임시 해석"을 적는다. 헤드의 답이 오면 임시 해석을 바꾸거나 확정한다. 상태: 헤드 답변과 골든 대조로 결정함(2026-10-15). 각 파일 끝의 "결정" 절을 본다. 골든으로도 가려지지 않은 것만 "남음"으로 적었다.

| 번호 | 제목 | 영향 컴포넌트 |
|---|---|---|
| CR-001 | 말을 선택지·단위에 잇는 기준의 빈칸(어간, 네·아니요, 수 자리, repeat_key) | normalize |
| CR-002 | 문항 전체·대상 없음에 붙은 값 항목의 취급 | normalize, judge |
| CR-003 | 위험 문구(`risk_phrases`)와 `utterance` 사용 규칙 | judge (미구현) |
| CR-004 | 확인 대기 ID를 결정적으로 만드는 방법 | write_record |
| CR-005 | 문장 재료(`sentence_materials`) 선택 규칙과 안내 채울 값 | plan |
| CR-006 | 저장소 효과표(9-2절)가 규칙 문서에 없음 | write_record |
| CR-007 | 규칙 용어와 Action·AlertKind 대응 | plan |
| CR-008 | 규칙 해석이 갈리는 곳(플래너·판정) 확인 요청 | judge, plan |
| CR-009 | 골든 예시와 다른 출력 62쌍의 분류 | 전부 |
| CR-010 | 문항 순서·건너뛰기 표(QuestionFlowTable)의 출처와 형식 (계약 2.0.0) | validate_extraction |
