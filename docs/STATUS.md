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
2. CR-010은 D99로 종결했다. 변환 함수는 더하지 않고 `DATASET_V2_FLOW`는 시험용 고정값이다.
3. `docs/rules/`의 v1 전용 문서에 '보관(v1)' 표시를 하고 이 리포의 README·design·brief·CR의 경로 참조를 끊었다(D99). 삭제는 아직 하지 않았다. 다음 릴리스에서 삭제한다(문서별 판단은 `docs/rules/README.md`의 표). CR-001~009는 "대상:" 줄의 경로만 문서 이름으로 바꿨다.

## 막힌 것

이 영역이 지금 하던 작업을 막는 것은 없다. 헤드 답을 기다리는 항목도 없다. 남은 것은 위 3번의 삭제(다음 릴리스)와 1번이다.
