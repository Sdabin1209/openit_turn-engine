# STATUS (2026-10-27, 0.4.0)

`main` 브랜치. 태그 `v0.4.0`은 원격(origin)에 올라가 있고 커밋 23973fc를 가리킨다. `main`은 그 뒤에 README 추가 커밋(00465ba)이 하나 더 있다. 작업 브랜치 `train-0.4`는 `main`에 합쳐졌다.

## 한 일

- G07: v1 폐기 코드(`normalize`, `judge`, `write_record`, `plan`, `OutputContractError`, `SUPPORTED_RUNTIME_CONTRACT_VERSION`, 문진 스키마 사본)와 딸린 시험·예시·골든 제거. 이웃 리포 grep 결과 사용처 없음(`docs/boundary.md` 8-2).
- boundary-contracts v2.0.2로 올림(`pyproject.toml`, `requirements.lock`, 문서).
- 버전 0.4.0(`pyproject.toml`, `ENGINE_VERSION`, `docs/CHANGELOG.md`).
- 문서 정리: `docs/boundary.md`, `docs/design.md`, `docs/runbook.md`, `docs/brief.md`, `README.md`.

## 시험 결과

`.venv`에서 `python -m pytest tests -q`: 39 통과, 1 건너뜀(2026-10-27 확인). 건너뛴 시험은 `tests/test_validation.py`의 학습 데이터 A 전수 검사로, 환경 변수 `TURN_ENGINE_DATASET_A`(JSONL 경로)가 없어서다. 시험 수가 0.3.x보다 크게 줄어든 것은 v1 함수 시험(골든 868쌍 등)을 함께 제거했기 때문이다. 0.4.0에서 학습 데이터 A 전수 검사를 다시 돌린 기록은 찾지 못했다(미확인. 0.3.0 항목에 5,077행 위반 0).

## 남은 일 / 미정

1. 깨끗한 두 번째 환경 검증은 하지 않았다(미확인. 헤드 대장 U12).
2. CR-010: 문항 순서·건너뛰기 표(`QuestionFlowTable`)를 문진 스키마에서 만드는 방법과 출처. 헤드 결정 대기(열림). 그동안 `DATASET_V2_FLOW`가 임시로 쓰인다. 0.4.0 릴리스와 현재 API 사용은 이것에 막히지 않는다. 막히는 것은 "QuestionBank에서 표를 만드는 변환 함수"를 더하는 일뿐이다.
3. `docs/rules/`와 CR-001~009는 역사 기록으로 남겼다. 지울지는 헤드 결정(열림).

## 막힌 것

이 영역이 지금 하던 작업을 막는 것은 없다. 다만 위 2번(CR-010)과 3번은 헤드 답을 기다리는 열린 항목이며, 답이 오기 전에는 변환 함수 추가와 문서 삭제를 하지 않는다.
