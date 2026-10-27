# 변경 이력

형식: 버전, 날짜, 변경, 출력 변화 여부. 버전 부여 방식은 `docs/boundary.md` 4절.

## 0.3.1 (2026-10-27, 태그 전)

의존 태그만 바뀐 PATCH. 코드와 출력은 0.3.0과 같다.

- 의존: `boundary-contracts`를 `v2.0.0`에서 `v2.0.1`로 올림(`pyproject.toml`, `requirements.lock`). v2.0.1은 ActionExtraction properties 순서만 사전순으로 바꾼 PATCH이고 `validate_extraction`은 그 순서에 의존하지 않는다.
- 이유: 태그 v0.3.0이 이미 v2.0.0을 고정해 두었으므로, 다른 영역이 v2.0.1과 함께 쓰려면 새 버전이 필요하다.
- 시험: `tests/test_contract.py`의 두 계약 시험을 현재 survey-service/schema 기준으로 정리(폐기된 v1 스키마 대조 제외).

## 0.3.0 (2026-10-27, 태그 전)

boundary-contracts v2.0.0(D74, D75) 이전. 공개 함수 추가와 폐기 표시이므로 MINOR(0.x 규칙). `normalize` 등 기존 함수의 출력은 0.2.0과 같다.

- 추가: `validate_extraction(input, output, flow) -> list[Violation]`. LoRA-A 출력(`ActionExtraction`)의 의미 검증(targets, next_item, 건너뛰기 순서, save 규칙). `Violation(code, path, message)`, `QuestionFlowTable`, `SkipRule`, `DATASET_V2_FLOW`.
- 폐기 표시: `normalize`, `judge`, `write_record`, `plan`은 호출 시 `DeprecationWarning`을 낸다. 동작은 그대로. 제거 시점은 survey-service 이전이 끝난 뒤(헤드 지시).
- 의존: `boundary-contracts`를 태그 `v2.0.0`으로 고정(`pyproject.toml`, `requirements.lock`). 입력 검증에 계약 패키지의 `ActionExtractionInput` 스키마를 쓴다(복사본 없음).
- 시험: `tests/test_validation.py` 42개. 학습 데이터 A 출력 5,077행 전수 위반 0(`scripts/validate_dataset_a.py`).
- `SUPPORTED_RUNTIME_CONTRACT_VERSION`은 1 그대로다(문진 스키마 정수 버전, D75-2). 폐기 함수가 아직 그 스키마를 쓴다.

## 0.2.0 (2026-10-15, 태그 전)

골든(원본 요구사항 케이스의 정적 예시 868쌍)과 헤드 답변을 반영. 같은 입력의 출력이 달라지므로 MINOR.

- 위험 표현 안전망 추가(CR-003): `risk_phrases`가 발화에 들어 있으면 `risk_signal`, 근거는 맞은 표현.
- 골든에 맞춘 출력 변화: MISMATCH 항목의 표준 값 없음, 한자어 수사와 수 자리 단위 이름, `said_value`는 애매 판정만, 판정 순서, 충돌의 `target_pending_ids` 빈 목록, 값 없는 정정·위험 신호만인 발화는 `HAS_ANSWER`, 모름·거절 기록 뒤의 답은 `FIRST_WRITE`, 문항 전체 모름·거절의 결정 순서, 무효화 순서와 `pending_id` 비움.
- 행동 이름 대응 수정: 사람 요청=`STAFF_NOTICE`, 도움 요청=`CALL_STAFF`. 도움 요청은 종료 확인 상한에서 기다리는 답 없음.
- 플래너: 이어 묻는 것도 횟수를 셈, 문장 재료의 행동별 모양, `REMAINING_COUNT`의 `Notice.value` 형식, 미룸 알림에 슬롯 없음, 반복 키 선택 문항의 열림 조건, 확인 상한 도달의 중복 처리.
- 시험: 골든 비교 868쌍(`tests/test_golden.py`, 다른 62쌍은 분류와 근거를 `tests/golden_known.json`에), 위험 표현 시험.
- 변경 요청 결정 반영(CR-001~008)과 골든 차이 분류(CR-009).

## 0.1.0 (2026-10-15, 태그 전)

첫 구현.

- 순수 함수 `normalize`, `judge`, `write_record`, `plan`과 `ENGINE_VERSION`, `SUPPORTED_RUNTIME_CONTRACT_VERSION`(1), `ContractViolation`, `OutputContractError`.
- 규칙 문서 `answer_normalizer.md`(5절), `answer_judge.md`(6절), `record_writer.md`(7절), `dialogue_planner.md`(8절)를 구현. 규칙 문장별 코드·시험 대응은 `docs/design.md` 6절.
- 입력 계약 검증, 출력 계약 검증, 입력 값을 싣지 않는 오류 메시지.
- 입출력 예시 37개(`examples/`), 규칙 문장 단위 시험, 결정성·순수성·계약 시험, 무작위 발화 열 시험.
- 변경 요청 8건(CR-001~CR-008): 규칙 문서에 없거나 모호한 곳의 임시 해석. 응답에 따라 MINOR가 오를 수 있다.
- 미구현: 위험 문구(`risk_phrases`)로 위험 신호를 보완하는 부분(CR-003).
