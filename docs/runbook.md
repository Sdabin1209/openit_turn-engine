# 런북: turn-engine

## 개발 환경

```
cd turn-engine
python3 -m venv .venv
. .venv/bin/activate
pip install pytest jsonschema
pip install -e .          # 시험이 `import turn_engine`을 하려면 필요
```

`.venv/`는 `.gitignore`에 있다. GPU, 네트워크, 컨테이너는 필요 없다. 서비스가 없으므로 이미지 빌드와 `/healthz` 확인은 해당하지 않는다.

## 시험

```
python -m pytest tests -q            # 전체(약 10초)
python -m pytest tests -q -k test_r7 # 규칙 번호로 고르기
python tests/fuzz_tool.py 120        # 무작위 발화 열 120개(수 분). 예외가 없어야 한다("bad 0")
```

수용 기준과 시험의 대응은 `docs/design.md` 6절. 기준 네 가지(결정성, 예시 입력→출력 스키마 통과, I/O·시간·난수 없음, 규칙 문서 밖 정책 없음)는 `tests/test_contract.py`와 `docs/change-requests/`가 맡는다.

## 입출력 예시 다시 만들기

예시(`examples/<시나리오>.<컴포넌트>.json`)는 `{"input", "output"}` 쌍이다. 입력은 시험용 오케스트레이터 흉내(`tests/sim.py`)가 만든 것이고, 시험은 입력이 입력 스키마를 통과하는지, 현재 코드의 출력이 `output`과 같은지, 출력이 출력 스키마를 통과하는지 확인한다.

```
python scripts/gen_examples.py
git diff examples/      # 출력이 왜 달라졌는지 검토. 의도한 변경이면 MINOR 이상으로 올린다
```

## 문진 스키마가 바뀌었을 때

1. survey-service가 `schema/`를 바꾸면(D21) `CONTRACT_VERSION`과 `schemas/*.json`이 바뀐다. `test_vendored_schemas_match_survey_schema`가 먼저 실패한다.
2. 변경이 네 컴포넌트와 관련 없으면 사본만 갱신한다: `cp ../survey-service/schema/schemas/{AnswerNormalizerInput,NormalizerOutput,AnswerJudgeInput,JudgeOutput,RecordWriterInput,StoreResult,DialoguePlannerInput,PlannerOutput}.json turn_engine/_schemas/`, `cp ../survey-service/schema/CONTRACT_VERSION turn_engine/_schemas/`.
3. 정수 버전이 올랐으면 `SUPPORTED_RUNTIME_CONTRACT_VERSION`(`turn_engine/_common.py`)을 올리고 `docs/boundary.md`에 쓴다. MAJOR를 올린다.
4. 시험이 실패하는 곳이 영향 범위다. 필수 필드가 늘었으면 해당 컴포넌트를 고친다. 규칙 문서와 어긋나면 변경 요청을 쓴다.

## 릴리스

1. `docs/CHANGELOG.md`에 항목을 쓴다. `ENGINE_VERSION`(`turn_engine/__init__.py`)과 `pyproject.toml`의 `version`을 같이 올린다(`test_engine_version_matches_package_metadata`).
2. 전체 시험이 통과하는지 확인한다.
3. 커밋 뒤 `git tag v<버전>`. push와 배포는 헤드의 절차를 따른다(이 영역은 push하지 않는다).
4. 소비자는 `pip install "turn-engine @ git+<저장소>@v<버전>"`으로 태그를 고정한다.

## 장애·문의 대응

- 소비자가 `ContractViolation`을 보고하면: `e.errors`(경로와 검사 종류)로 입력 조립 쪽을 확인한다. 이 라이브러리 문제가 아니다.
- `OutputContractError`: 엔진 결함이다. 같은 입력으로 재현하는 시험을 `tests/`에 먼저 추가하고 고친다. 입력에 개인정보가 있을 수 있으니 비식별화한 입력만 받는다.
- "규칙대로 안 한다"는 보고: 먼저 `docs/design.md` 6절에서 해당 규칙의 코드·시험을 찾는다. 규칙 문서가 모호한 곳이면 `docs/change-requests/`의 해당 요청을 확인하고, 없으면 새로 쓴다. 규칙 문서를 구현이 임의로 바꾸지 않는다.
- 성능: 한 턴(네 호출)이 이 개발 환경에서 수십 ms다. 대부분 계약 검증 시간이다. 지연 요구가 정해지면(현재 요구 없음) 검증을 끄는 선택지는 두지 않고 검증기 최적화로 대응한다.
