# 변경 이력

형식: 버전, 날짜, 변경, 출력 변화 여부. 버전 부여 방식은 `docs/boundary.md` 4절.

## 0.1.0 (2026-10-15, 태그 전)

첫 구현.

- 순수 함수 `normalize`, `judge`, `write_record`, `plan`과 `ENGINE_VERSION`, `SUPPORTED_RUNTIME_CONTRACT_VERSION`(1), `ContractViolation`, `OutputContractError`.
- 규칙 문서 `answer_normalizer.md`(5절), `answer_judge.md`(6절), `record_writer.md`(7절), `dialogue_planner.md`(8절)를 구현. 규칙 문장별 코드·시험 대응은 `docs/design.md` 6절.
- 입력 계약 검증, 출력 계약 검증, 입력 값을 싣지 않는 오류 메시지.
- 입출력 예시 37개(`examples/`), 규칙 문장 단위 시험, 결정성·순수성·계약 시험, 무작위 발화 열 시험.
- 변경 요청 8건(CR-001~CR-008): 규칙 문서에 없거나 모호한 곳의 임시 해석. 응답에 따라 MINOR가 오를 수 있다.
- 미구현: 위험 문구(`risk_phrases`)로 위험 신호를 보완하는 부분(CR-003).
