# 런북: turn-engine

## 개발 환경

```
bash scripts/setup-env.sh    # .venv 생성·재사용, requirements.lock과 같게 맞춤(SSH 키 필요). 정본은 이 스크립트
```

`.venv/`는 `.gitignore`에 있다. GPU, 네트워크, 컨테이너는 필요 없다. 서비스가 없으므로 이미지 빌드와 `/healthz` 확인은 해당하지 않는다.

## 시험

```
python -m pytest tests -q            # 전체
```

시험은 `tests/test_validation.py`(검증 규칙, 결정성, 의존 태그, 버전, 공개 API).

## 학습 데이터 전수 검증 (계약 2.0.0 기준 시험)

학습 서버 데이터는 읽기 전용으로 표준입력에 흘려 검사한다. 파일을 서버에 만들거나 이 PC에 저장하지 않는다. 허용 경로는 `~/taehyeon/data/dataset_10_14`뿐이다.

```
for f in train val test; do ssh -o BatchMode=yes -o ConnectTimeout=15 openit "cat ~/taehyeon/data/dataset_10_14/lora_a_$f.jsonl"; done \
  | .venv/bin/python scripts/validate_dataset_a.py --mutate     # 위반 0이어야 종료 코드 0
```

`--mutate`는 통과한 행을 일부러 망가뜨려 검사기가 잡는지 센다(검사기가 느슨해서 0인 것이 아님을 보이는 용도).

## 릴리스

1. `docs/CHANGELOG.md`에 항목을 쓴다. `ENGINE_VERSION`(`turn_engine/__init__.py`)과 `pyproject.toml`의 `version`을 같이 올린다(`test_engine_version_matches_package_metadata`).
2. 전체 시험이 통과하는지 확인한다.
3. 커밋 뒤 `git tag v<버전>`. push와 배포는 헤드의 절차를 따른다(이 영역은 push하지 않는다).
4. 소비자는 `pip install "turn-engine @ git+<저장소>@v<버전>"`으로 태그를 고정한다.

## 장애·문의 대응

- 소비자가 `ContractViolation`을 보고하면: `e.errors`(경로와 검사 종류)로 입력 조립 쪽을 확인한다. 이 라이브러리 문제가 아니다.
- 위반 코드가 기대와 다르다는 보고: `docs/boundary.md` 8절의 검사 규칙을 먼저 확인하고, 모호하면 `docs/change-requests/`에 새 요청을 쓴다.
