# STATUS (2026-10-15, 첫 구간 끝)

## 한 일

- `docs/design.md`: 컴포넌트별 내부 설계, 규칙 문장 → 코드 → 시험 대응표(6절), 알려진 한계.
- `docs/boundary.md`: 소유(없음), 제공(I8), 소비(문진 스키마 정수 버전 1), 버전 부여 방식, 장애 영향.
- 구현: `normalize`, `judge`, `write_record`, `plan`, `ENGINE_VERSION`(0.1.0), `SUPPORTED_RUNTIME_CONTRACT_VERSION`(1), `ContractViolation`(+`OutputContractError`).
- 시험(`tests/`): 규칙 문장 단위 시험, 입출력 예시 37개(`examples/`), 결정성, 순수성, 계약 위반, 스키마 사본 일치, 무작위 발화 열.
- `docs/runbook.md`, `docs/CHANGELOG.md`, 변경 요청 8건(`docs/change-requests/`).

## 골든 대조 (2026-10-15, 헤드 요청)

- 868쌍(209 케이스, 네 컴포넌트) 중 806쌍 일치, 62쌍 다름: (b) 25건, (c) 37건, (a) 0건(고침). 컴포넌트별 다른 쌍: Normalizer 23(전부 어휘), Judge 7, Writer 6, Planner 26(자리표시자·고정 문장 본문 25건 + K4).
- 위험 표현 안전망 구현(CR-003). 골든 G2·G9·S3c 일치.
- ENGINE_VERSION 0.2.0(출력이 달라져 MINOR). 태그는 붙이지 않았다(헤드 확인 뒤).

## 시험 결과 (실제로 돌린 것)

- `python -m pytest tests -q` → 1205 passed (골든 868쌍 포함).
- `tests/fuzz_tool.py`: 시드 7000~7119(35턴) 예외 없음("bad 0"). 이전 시드 0~119, 5000~5199는 수정 전 코드로 돌린 것이라 다시 돌린 결과만 유효하다.

## 남은 일

1. 헤드 확인 뒤 `git tag v0.2.0`.
2. 남은 해석(CR-008 결정 절, design.md 8절)을 survey-service 연동 때 대조.
3. 어휘 차이 24건: 문항 정의에 동의어(`choice_catalog`)를 두는 question-authoring 과제, 또는 평문 선택지+`yes_no_map`의 "네"·"아니요" 낱말 규칙 결정(CR-001, CR-009).
4. 골든 예시 오류 37건을 요구 작성자에게 전달(CR-009).
5. `FIRST_WRITE`의 확인 대기 처리와 9-2절 원문 확인(헤드→사용자).
6. 무관한 말이 답과 함께 올 때의 고정 문장(골든 K4)은 `UtteranceJudgment` 변경이 있어야 도출 가능.

## 막힌 것

없음.
