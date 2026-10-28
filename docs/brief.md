# 영역 브리프: turn-engine (공유 라이브러리)

> **계약 상태 (2026-10-27 갱신).** boundary-contracts v2.0.0(D74·D75)에서 I8은 "LoRA-A 출력의 의미 검증 안전망"(`validate_extraction`)으로 바뀌었다. 이 라이브러리는 boundary-contracts v2.0.2(태그)의 `ActionExtraction*` 스키마를 소비한다. 본문 1~3절은 0.4.0 현재 구조(`validate_extraction`, `QuestionFlowTable`, `flow`)로 고쳤다. 예전 네 컴포넌트(normalize·judge·write_record·plan)는 0.4.0에서 코드가 제거됐다(`docs/boundary.md` 8-2). 4~9절은 컴포넌트 이름을 쓰지 않는 일반 기준이라 그대로 두었고, 계약·의존 표현만 현재에 맞췄다.
> **읽기.** 입력·출력 스키마는 boundary-contracts 패키지(v2.0.2 태그)에서 `validator`로 읽는다. 복사본은 없다. `../survey-service/schema`와 `../boundary-contracts`는 읽기 전용이다.
> **버전.** boundary-contracts 태그(`pyproject.toml`, `requirements.lock`)로 고정하고, 라이브러리 버전은 `ENGINE_VERSION`이다(`docs/boundary.md` 4절).
> **업무 규칙.** 계약에 없는 정책은 임의로 만들지 말고 `docs/change-requests/`에 쓴다.

## 1. 목적과 범위

- 목적: 모델(LoRA-A)이 낸 "환자 답변 해석"이 계약의 의미 규칙을 지키는지 코드로 다시 검사하는 순수 라이브러리다. 서비스·평가·합성 데이터·게이트가 같은 코드로 같은 결과를 얻게 한다. 모델은 해석만, 판단은 코드가 한다는 역할 분리의 코드 쪽이다.
- 하는 일: `validate_extraction(input, output, flow)`. 입력은 `ActionExtractionInput`, 출력 해석은 `ActionExtraction` 스키마를 따르며, 저장 대상·다음 문항·건너뛰기 순서·저장 여부를 검사해 `Violation` 목록을 돌려준다(`docs/boundary.md` 8-1).
- 하지 않는 일: 모델 호출, 저장소 접근, 네트워크, 파일 I/O, 서버 실행. 형식 검증은 model-runtime의 몫. 문항 순서 관리와 입력 조립은 survey-service의 몫.

## 2. 소유하는 것

- 소유 저장소: 없음.
- 제공(I8): `validate_extraction`, `Violation`, `QuestionFlowTable`, `SkipRule`, `DATASET_V2_FLOW`, `ContractViolation`, `ENGINE_VERSION`(`turn_engine/__init__.py`의 `__all__`). 입력이 스키마를 어기면 `ContractViolation`으로 거부한다. 시그니처와 위반 코드는 `docs/boundary.md` 8-1이 정한다.
- 라이브러리 버전은 데이터셋·모델·릴리스 매니페스트에 기록되므로 버전 부여 방식을 `docs/boundary.md` 4절에 정했다.

## 3. 소비하는 것

- 소비하는 계약: boundary-contracts v2.0.2의 `ActionExtractionInput`, `ActionExtraction`(`boundary_contracts.validator`). 문항 순서·건너뛰기는 호출자가 `QuestionFlowTable`로 넘긴다. 표는 survey-service가 문진 스키마에서 만들어 넘기며 이 라이브러리는 변환을 갖지 않는다(D99, CR-010 종결). `DATASET_V2_FLOW`(학습 데이터 v2의 31문항, 건너뛰기 7건)는 시험용 고정값이다.
- 소비하는 SDK: 없음.
- 지원하는 계약 버전: boundary-contracts 태그 한 값(v2.0.2).

## 3-1. 경계 명세 (블랙박스 기준)

상대 영역은 블랙박스다. 아래 인터페이스 번호의 시그니처, 오류, 멱등성은 `../boundary-contracts/INTERFACES.md`와 `CONVENTIONS.md`가 정한다. 이 명세 밖의 것을 상대에게 기대하거나 가정하지 않는다.

- 내는 것: **I8** (`validate_extraction`, `QuestionFlowTable`, `SkipRule`, `DATASET_V2_FLOW`, `ENGINE_VERSION`; 0.4.0).
- 받는 것: 문진 스키마의 입력 계약.
- 해야 하는 것: 순수 함수이며 결정적이다. 입력 위반은 `ContractViolation`.

## 4. 상위 수용 기준

- 결정적이다. 같은 입력은 항상 같은 출력을 낸다.
- 입력 계약 스키마를 통과하는 예시 입력을 이 리포지토리가 만들어 넣었을 때 출력이 해당 출력 계약의 스키마를 통과한다.
- I/O와 시간·난수 의존이 없다. 필요하면 인자로 주입한다.
- 계약 문서에 없는 정책을 임의로 만들지 않는다. 미정의·충돌은 보고한다.
- 소비자(survey-service, 합성 데이터, model-lab, 게이트, 문항 저작)가 같은 버전으로 같은 결과를 얻는다.

## 5. 비기능 요구

- 지연: 한 턴 안에서 호출되므로 짧아야 한다. 수치는 survey-service와 정하나, 현재 요구 없음.
- 자원: CPU. 보안·개인정보: 입력을 로그로 남기지 않는다.

## 6. 건드리면 안 되는 경계

- boundary-contracts 외에 다른 리포지토리에 의존하지 않는다.
- 업무 정책을 계약 문서와 다르게 구현하지 않는다. 다르게 해야 한다면 변경 요청을 낸다.

## 7. 이 영역에 해당하는 열린 결정

- 없음. 라이브러리 구현 언어는 O07(SDK 언어)과 연결된다. 확정: Python(D18).

## 8. 시드

처음 시드는 Normalizer, Judge, Record Writer, Planner 네 컴포넌트였다(v1, 역사 기록). 0.3.0에서 `validate_extraction`이 추가되고 0.4.0에서 네 컴포넌트가 제거됐다(`docs/CHANGELOG.md`).

## 9. 요구하는 산출물

- `docs/design.md`, `docs/boundary.md`, 계약 준수 시험(`tests/test_validation.py`), 에이전트용 `CLAUDE.md`, 변경 이력
