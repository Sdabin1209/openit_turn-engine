# turn-engine 내부 설계

LoRA-A 출력(`ActionExtraction`)의 의미 검증 안전망을 순수 함수로 제공하는 Python 라이브러리다(I8, 0.4.0). 모델 호출, 저장소, 네트워크, 파일 I/O, 시간, 난수를 쓰지 않는다. 0.3.x까지 있던 v1 판단 로직(normalizer, judge, writer, planner)은 0.4.0에서 제거했다. 그 설계와 규칙 대응표는 git 이력(태그 v0.3.1 이전 커밋)에 있다.

## 구조

```
turn_engine/
  __init__.py    공개 API: validate_extraction, Violation, QuestionFlowTable, SkipRule, DATASET_V2_FLOW,
                 ENGINE_VERSION, ContractViolation
  _common.py     ContractViolation
  flow.py        QuestionFlowTable, SkipRule, DATASET_V2_FLOW
  validation.py  validate_extraction (boundary_contracts.validator로 형식 검증 뒤 의미 검증)
tests/test_validation.py   검증 규칙, 결정성, 의존 태그, 버전, 공개 API
scripts/validate_dataset_a.py   학습 데이터 A 전수 검증(읽기 전용 스트림)
```

검사 규칙과 위반 코드는 `docs/boundary.md` 8-1. `docs/rules/`와 `docs/change-requests/CR-001~009`는 v1 시점의 기록이며 구현은 없다.
