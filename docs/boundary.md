# 경계 문서: turn-engine

이 문서는 상대 영역이 turn-engine을 블랙박스로 쓰기 위해 알아야 하는 것이다. 인터페이스 번호의 시그니처·오류는 `../boundary-contracts/INTERFACES.md`(I8)와 `CONVENTIONS.md`가 정한다. 여기서 정하는 것은 그 안에서 이 영역이 지키는 세부와 버전 부여 방식이다.

## 1. 소유하는 것

- 소유 저장소: 없음.
- 서비스가 아니라 라이브러리다. 프로세스, 포트, `/healthz`, 컨테이너 이미지를 두지 않는다(상위 규칙 D22의 이미지 항목은 서비스를 가진 영역에 해당). 소비자의 이미지가 이 라이브러리를 Git 태그로 고정해 설치한다.
- 이 라이브러리는 메모리 구현(가짜 구현)이 필요 없다. 순수 함수라서 소비자가 그대로 부르면 다른 영역 없이 혼자 시험할 수 있다. 

## 2. 제공하는 것 (I8)

```python
from turn_engine import validate_extraction, Violation, QuestionFlowTable, SkipRule, DATASET_V2_FLOW
from turn_engine import ENGINE_VERSION, ContractViolation
```

시그니처와 위반 코드는 8절. 입출력은 JSON으로 직렬화되는 `dict`·`list`·문자열·수·`bool`·`None`이다. 0.4.0에서 v1의 `normalize`, `judge`, `write_record`, `plan`, `OutputContractError`, `SUPPORTED_RUNTIME_CONTRACT_VERSION`을 제거했다(G07, `docs/CHANGELOG.md`).

| 약속 | 내용 |
|---|---|
| 순수·결정적 | 같은 입력은 같은 출력. I/O·시간·난수·전역 설정 없음 |
| 입력 불변 | 입력 객체를 바꾸지 않는다 |
| 입력 위반 | `ContractViolation`(`ValueError`의 하위). `.contract`, `.errors`(`경로: 검사` 문자열 목록). 입력 값은 담지 않는다 |
| 개인정보 | 입력을 로그로 남기지 않는다. 오류 메시지에도 값이 없다 |

## 3. 소비하는 것

- 소비하는 계약: boundary-contracts(태그는 `pyproject.toml`이 정본)의 `ActionExtractionInput`, `ActionExtraction`. 복사본은 만들지 않는다.
- 문진 스키마(`../survey-service/schema`)는 이 라이브러리가 읽지 않는다(0.4.0부터 정수 버전 의존 없음).
- 외부 패키지: `jsonschema`. Python 3.10 이상.

## 4. 버전 부여 방식

`ENGINE_VERSION`은 `MAJOR.MINOR.PATCH`(SemVer 형식의 문자열)이며 `pyproject.toml`의 `version`과 같다(시험이 확인). 데이터셋·모델·릴리스 매니페스트는 이 값을 기록한다. 소비자는 Git 태그 `v<ENGINE_VERSION>`으로 설치한다.

| 올리는 때 | 올리는 자리 |
|---|---|
| 지원하는 문진 스키마 정수 버전이 바뀐다, 또는 공개 함수·예외 이름·시그니처가 바뀐다 | MAJOR |
| **유효한 입력 하나라도 출력이 달라진다**(규칙 문서 변경 반영, 변경 요청의 해석 확정, 버그 수정 포함) | MINOR |
| 모든 유효한 입력에서 출력이 같다(성능, 내부 정리, 시험, 문서) | PATCH |

출력이 달라지는 변경을 MINOR로 올리는 이유: 합성 데이터·평가·게이트가 "같은 버전이면 같은 결과"를 전제로 재현하기 때문이다. `0.x`인 동안(규칙 해석의 변경 요청이 열려 있는 동안)에도 이 표를 따른다.

## 5. 장애 영향

라이브러리라서 자체 장애가 없다. 호출 실패의 영향은 호출자의 턴에 한정된다.

| 상황 | 증상 | 호출자의 행동 |
|---|---|---|
| 입력이 계약 위반 | `ContractViolation` | 재시도 무의미(결정적). 입력 조립 결함으로 보고. `.errors`로 위치 확인 |
| 출력이 스키마 위반 | `OUTPUT_SCHEMA` 위반으로 반환 | `OUTPUT_INVALID`와 같게 처리(D75-1) |

## 6. 소비자별 메모

| 소비자 | 쓰는 것 |
|---|---|
| survey-service | `validate_extraction`, `QuestionFlowTable`, `SkipRule`, `ContractViolation`, `DATASET_V2_FLOW`(시험) |
| model-lab, synthetic-data, model-runtime(시험) | `ENGINE_VERSION`, `DATASET_V2_FLOW`, `validate_extraction` |

## 7. 변경 요청

`docs/change-requests/README.md`. CR-001~009는 v1 함수에 관한 것이며 0.4.0 제거로 닫혔다(역사 기록).

## 8. 계약 2.0.0 이전 (2026-10-27, 0.3.0 제안)

기준: boundary-contracts `v2.0.0`, INTERFACES I8(출력 검증 라이브러리로 대체), D74, D75.

### 8-1. 제공하는 것

```python
from turn_engine import validate_extraction, Violation, QuestionFlowTable, SkipRule, DATASET_V2_FLOW

validate_extraction(input: ActionExtractionInput, output: ActionExtraction, flow: QuestionFlowTable) -> list[Violation]
Violation(code: str, path: str, message: str)     # NamedTuple. message에 입력·출력 값을 싣지 않는다
QuestionFlowTable(order: Sequence[str], skips: Sequence[SkipRule] = ())
SkipRule(slot: str, value, skip_item: str)        # slot(괄호 없는 문항.칸)에 저장된 값이 value이면 skip_item을 묻지 않는다
```

- 순수·결정적. 입력과 출력을 바꾸지 않는다. 위반이 없으면 빈 목록.
- `input`이 `ActionExtractionInput` 스키마를 어기면 `ContractViolation`(`.contract == "ActionExtractionInput"`). `output`이 스키마를 어기는 것은 예외가 아니라 `OUTPUT_SCHEMA` 위반으로 돌려준다(형식 검증은 model-runtime의 몫이지만 안전망이므로 거부하지 않고 보고한다).
- 위반 코드: `OUTPUT_SCHEMA`, `TARGET_NOT_IN_VALUES`, `NEXT_ITEM_MISMATCH`, `SKIP_ORDER_MISMATCH`, `SAVE_RULE`, `UNKNOWN_ITEM`(문항 순서 표에 없는 문항). 앞의 다섯은 I8 초안이 든 예 중 `OUTPUT_SCHEMA`와 `UNKNOWN_ITEM`을 더한 것이다(제안).
- 검사 규칙: (a) `targets`는 `values`의 key. (b) REASK·REDIRECT는 `next_item == question_id`, CONFIRM은 `targets` 칸의 문항, NEXT·CORRECT·HOLD·SKIP은 순서·건너뛰기의 다음 문항(한 말에 여러 문항이 나오면 가장 뒤 문항 기준, `save`가 true인 값으로 건너뛰기 판단). 같은 말에서 일부 칸이 채워진 문항으로 넘어가는 것은 위반이 아니다(I8). (c) 건너뛰기를 어기거나 조건 없이 건너뛰면 `SKIP_ORDER_MISMATCH`, 그 밖의 어긋남은 `NEXT_ITEM_MISMATCH`. (d) `save`는 ANSWERED·CORRECTION일 때만 true, MISSING·UNCLEAR·UNKNOWN·REJECTED의 `value`는 null.
- 위반이 나오면 survey-service는 `OUTPUT_INVALID`와 같게 처리한다(I8, D75-1).
- `QuestionFlowTable`을 문진 스키마에서 만드는 변환은 이 라이브러리에 없다. survey-service가 만들어 넘긴다(D99, CR-010 종결). `DATASET_V2_FLOW`는 학습 데이터 v2의 문항 순서·건너뛰기(`turn_engine/flow.py`가 정본)이며 시험용 고정값이다.

### 8-2. 제거 (0.4.0, G07)

`normalize`, `judge`, `write_record`, `plan`과 문진 스키마 사본(`turn_engine/_schemas/`), `OutputContractError`, `SUPPORTED_RUNTIME_CONTRACT_VERSION`을 제거했다. 이웃 리포(survey-service, release-gate, model-lab, ops-feedback, model-runtime, deploy, synthetic-data, question-authoring)에 이 이름을 import하거나 호출하는 코드는 없음을 grep으로 확인했다(문서 언급만 survey-service/docs).

### 8-3. 소비하는 것

- boundary-contracts(태그로 설치, 태그 값은 정본 `pyproject.toml`. `pyproject.toml`, `requirements.lock`). 쓰는 것은 `boundary_contracts.validator("ActionExtractionInput"/"ActionExtraction")`뿐이다.
