# STATUS (2026-10-27, 0.4.0)

브랜치 `train-0.4`. push·태그 없음(헤드 확인 뒤).

## 한 일

- G07: v1 폐기 코드(`normalize`, `judge`, `write_record`, `plan`, `OutputContractError`, `SUPPORTED_RUNTIME_CONTRACT_VERSION`, 문진 스키마 사본)와 딸린 시험·예시·골든 제거. 이웃 리포 grep 결과 사용처 없음.
- boundary-contracts v2.0.2로 올림(`pyproject.toml`, `requirements.lock`, 문서). venv 재설치로 2.0.2 확인.
- 버전 0.4.0(`pyproject.toml`, `ENGINE_VERSION`, `docs/CHANGELOG.md`).
- 문서 정리: `docs/boundary.md`, `docs/design.md`, `docs/runbook.md`, `docs/brief.md`.

## 시험 결과

`.venv`에서 `python -m pytest tests -q`: 결과는 커밋 메시지와 보고에 적는다. 시험 수가 크게 줄어든 것은 v1 함수 시험(골든 868쌍 등)을 함께 제거했기 때문이다.

## 남은 일 / 미정

1. 헤드 확인 뒤 push, 태그 `v0.4.0`.
2. CR-010: 문항 순서·건너뛰기 표의 출처와 형식(헤드 결정).
3. `docs/rules/`와 CR-001~009는 역사 기록으로 남겼다. 지울지는 헤드 결정.
4. 깨끗한 두 번째 환경 검증은 이번에 하지 않았다.

## 막힌 것

없음.
