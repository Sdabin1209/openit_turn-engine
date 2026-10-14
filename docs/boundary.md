# 경계 문서: turn-engine

이 문서는 상대 영역이 turn-engine을 블랙박스로 쓰기 위해 알아야 하는 것이다. 인터페이스 번호의 시그니처·오류는 `../boundary-contracts/INTERFACES.md`(I8)와 `CONVENTIONS.md`가 정한다. 여기서 정하는 것은 그 안에서 이 영역이 지키는 세부와 버전 부여 방식이다.

## 1. 소유하는 것

- 소유 저장소: 없음.
- 서비스가 아니라 라이브러리다. 프로세스, 포트, `/healthz`, 컨테이너 이미지를 두지 않는다(상위 규칙 D22의 이미지 항목은 서비스를 가진 영역에 해당). 소비자의 이미지가 이 라이브러리를 Git 태그로 고정해 설치한다.
- 이 라이브러리는 메모리 구현(가짜 구현)이 필요 없다. 순수 함수라서 소비자가 그대로 부르면 다른 영역 없이 혼자 시험할 수 있다. 시험용 오케스트레이터 흉내(`tests/sim.py`)는 이 리포지토리의 시험 도구이며 제공물이 아니다.

## 2. 제공하는 것 (I8)

```python
from turn_engine import normalize, judge, write_record, plan
from turn_engine import ENGINE_VERSION, SUPPORTED_RUNTIME_CONTRACT_VERSION
from turn_engine import ContractViolation, OutputContractError

normalize(input: AnswerNormalizerInput) -> NormalizerOutput
judge(input: AnswerJudgeInput) -> JudgeOutput
write_record(input: RecordWriterInput) -> StoreResult
plan(input: DialoguePlannerInput) -> PlannerOutput
ENGINE_VERSION: str
SUPPORTED_RUNTIME_CONTRACT_VERSION: int
```

입출력은 JSON으로 직렬화되는 `dict`·`list`·문자열·수·`bool`·`None`이다(문진 스키마의 계약 그대로). 별도 클래스를 두지 않는다.

| 약속 | 내용 |
|---|---|
| 순수·결정적 | 같은 입력은 같은 출력. 입력 dict의 키 순서와 무관. I/O·시간·난수·전역 설정 없음 |
| 입력 불변 | 입력 객체를 바꾸지 않는다. 출력은 새 객체이며 입력과 구조를 공유하지 않는다 |
| 입력 위반 | `ContractViolation`(`ValueError`의 하위). `.contract`(계약 이름), `.errors`(`경로: 검사` 문자열 목록). 입력 값은 담지 않는다. `BoundaryError`가 아니다 |
| 출력 보증 | 정상 반환한 값은 항상 출력 계약 스키마를 통과한다. 통과하지 못하면 `OutputContractError`(엔진 결함; 호출자는 재시도하지 말고 보고) |
| 멱등 | 호출이 상태를 바꾸지 않으므로 같은 호출을 다시 해도 같다 |
| 개인정보 | 입력을 로그로 남기지 않는다. 오류 메시지에도 값이 없다 |
| 확인 대기 ID | `write_record`가 `pnd-`로 시작하는 결정적 ID를 만든다(CR-004). 호출자는 이 값을 불투명 문자열로 다룬다 |

호출 순서와 입력 조립은 survey-service(Orchestrator)의 몫이다. 이 라이브러리는 `normalize → judge → write_record → plan` 순서를 강제하지 않지만, 입력 계약은 앞 컴포넌트의 출력을 전제로 한다(예: `judge`는 `normalize`의 `item_checks`를 `item_no`로 짝지어 쓰며 짝이 없으면 `ContractViolation`).

## 3. 소비하는 것

- 소비하는 계약: 문진 스키마(`../survey-service/schema`)의 `AnswerNormalizerInput`/`NormalizerOutput`, `AnswerJudgeInput`/`JudgeOutput`, `RecordWriterInput`/`StoreResult`, `DialoguePlannerInput`/`PlannerOutput`과 하위 타입. 스키마 사본은 `turn_engine/_schemas/`에 있고 시험이 원본과 같음을 확인한다.
- 지원하는 계약 버전: 문진 스키마 정수 버전 **1** 한 값(`SUPPORTED_RUNTIME_CONTRACT_VERSION = 1`). 사본의 `CONTRACT_VERSION`이 다르면 가져올 때 `RuntimeError`.
- 소비하는 SDK: 없음. boundary-contracts에도 의존하지 않는다.
- 외부 패키지: `jsonschema`(계약 검증). Python 3.10 이상.
- 업무 규칙: `docs/rules/`(헤드가 전달). 규칙 문서에 없는 정책은 구현하지 않고 `docs/change-requests/`에 둔다.

## 4. 버전 부여 방식

`ENGINE_VERSION`은 `MAJOR.MINOR.PATCH`(SemVer 형식의 문자열)이며 `pyproject.toml`의 `version`과 같다(시험이 확인). 데이터셋·모델·릴리스 매니페스트는 이 값을 기록한다. 소비자는 Git 태그 `v<ENGINE_VERSION>`으로 설치한다.

| 올리는 때 | 올리는 자리 |
|---|---|
| 지원하는 문진 스키마 정수 버전이 바뀐다, 또는 공개 함수·예외 이름·시그니처가 바뀐다 | MAJOR |
| **유효한 입력 하나라도 출력이 달라진다**(규칙 문서 변경 반영, 변경 요청의 해석 확정, 버그 수정 포함) | MINOR |
| 모든 유효한 입력에서 출력이 같다(성능, 내부 정리, 시험, 문서) | PATCH |

출력이 달라지는 변경을 MINOR로 올리는 이유: 합성 데이터·평가·게이트가 "같은 버전이면 같은 결과"를 전제로 재현하기 때문이다. `0.x`인 동안(규칙 해석의 변경 요청이 열려 있는 동안)에도 이 표를 따른다. `tests/test_contract.py`의 예시 golden이 바뀌면 최소 MINOR다.

## 5. 장애 영향

라이브러리라서 자체 장애(프로세스 중단)가 없다. 호출 실패의 영향은 호출자의 턴에 한정된다.

| 상황 | 증상 | 영향 | 호출자의 행동 |
|---|---|---|---|
| 입력이 계약 위반 | `ContractViolation` | 그 턴의 해당 컴포넌트 결과가 없다 | 재시도 무의미(결정적). 입력 조립 결함으로 보고, 턴을 실패로 처리. `.errors`로 원인 위치 확인 |
| 출력이 계약 위반 | `OutputContractError` | 같음 | 엔진 결함. 입력(비식별화)과 함께 turn-engine에 보고 |
| 스키마 정수 버전 불일치 | 가져올 때 `RuntimeError` | 서비스가 뜨지 않음(조기 실패) | 소비자의 문진 스키마 버전과 맞는 엔진 태그를 설치 |
| 규칙 해석이 소비자 기대와 다름 | 출력이 기대와 다름 | 대화 품질 | `docs/change-requests/`의 열린 요청을 확인, 새 요청 |
| 안전과 닿는 열린 항목 | 모델이 위험 신호를 놓치면 Judge가 잡지 못함 | 위험 안내 누락 가능 | 현재 이 라이브러리는 `risk_phrases`를 쓰지 않는다(CR-003 응답 전) |

## 6. 소비자별 메모

| 소비자 | 쓰는 것 | 메모 |
|---|---|---|
| survey-service | 네 함수 전부 | 턴 순서와 저장소 읽기·쓰기는 호출자의 몫. 저장소 효과 가정은 CR-006 |
| synthetic-data, model-lab, release-gate | 네 함수(재현, 평가, 정답 생성) | `ENGINE_VERSION`을 산출물에 기록해야 같은 결과를 재현한다 |
| question-authoring | 미리보기에서 네 함수 | 문항 정의로 규칙을 시험해 볼 수 있다. 어간·수 자리 규칙의 한계는 CR-001 |

## 7. 열린 변경 요청

`docs/change-requests/README.md`에 목록이 있다(CR-001~CR-008). 답이 오면 해당 해석을 확정하거나 고치고 MINOR를 올린다.
