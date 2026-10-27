# STATUS (2026-10-27, boundary-contracts v2.0.0 이전)

브랜치 `migrate-contracts-2.0.0`. push·태그 없음(헤드 확인 뒤).

## 한 일

- `validate_extraction(input, output, flow) -> list[Violation]`, `Violation`, `QuestionFlowTable`, `SkipRule`, `DATASET_V2_FLOW` 추가(`turn_engine/validation.py`, `flow.py`).
- `normalize`/`judge`/`write_record`/`plan` 폐기 표시(`DeprecationWarning`, 동작 불변). 제거는 survey-service 이전 뒤.
- boundary-contracts v2.0.1을 태그로 설치(`pyproject.toml`, `requirements.lock`). 버전 0.3.0 제안.
- 학습 데이터 A 출력 전수 검증: `scripts/validate_dataset_a.py`(읽기 전용 스트림). 결과는 `docs/CHANGELOG.md`와 보고 참조.
- 문서: `docs/boundary.md` 8절, `docs/runbook.md`, `docs/CHANGELOG.md`, `docs/change-requests/CR-010`.

## 시험 결과 (실제로 돌린 것)

- 이 리포 `.venv`(문진 스키마 원본 있음): `python -m pytest tests -q` -> 1246 passed, 1 skipped(`TURN_ENGINE_DATASET_A` 없을 때의 데이터 전수 시험).
- 깨끗한 두 번째 venv(리포 사본을 워크스페이스 밖에 두고 `pip install ".[dev]"`): 1244 passed, 3 skipped(`../survey-service` 원본이 없어 건너뜀).
- 학습 데이터 A(`lora_a_train/val/test`) 3,982+549+546 = 5,077행: 위반 0. 계약의 `tools/validate_dataset_v2.py a`도 5,077 pass(참고 정보 57건, 부분 선채움 NEXT).

## 남은 일 / 미정

1. 헤드 확인 뒤 push, 태그 `v0.3.0`.
2. CR-010: 문항 순서·건너뛰기 표의 출처와 형식(헤드 결정).
3. 폐기 함수 제거 시점(survey-service 이전 뒤). 제거 때 문진 스키마 사본과 정수 버전 1 의존도 정리.
4. 기존 `tests/fuzz_tool.py`는 이번에 돌리지 않았다.

## 막힌 것

없음.
