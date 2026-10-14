# 영역 브리프: turn-engine (공유 라이브러리)

> **계약 상태.** 이 라이브러리는 문진 스키마만 소비하며 경계 계약에는 의존하지 않는다.
> **읽기.** `../survey-service/schema`는 문진 서비스의 데이터 스키마(스키마만 남긴 최소 구성)다. 구현이 가져가는 계약은 `schemas/<계약명>.json`(JSON Schema Draft 2020-12), 컴포넌트별 입력·출력 대응은 `COMPONENTS.yaml`, 정수 버전은 `CONTRACT_VERSION`이다. 읽기 전용이다.
> **버전(D14, D19).** 문진 스키마 정수 버전(`CONTRACT_VERSION`)에 정확히 일치해야 한다.
> **업무 규칙.** 이 영역이 구현하거나 의존하는 업무 요구는 `docs/rules/`에 있다(헤드가 전달, 출처는 `docs/rules/SOURCE.md`). 규칙 문서에 없는 정책은 임의로 만들지 말고 `docs/change-requests/`에 쓴다.

## 1. 목적과 범위

- 목적: 한 턴의 판단 로직을 서비스·평가·합성 데이터·게이트가 같은 코드로 재현하게 하는 순수 라이브러리다. 모델은 해석과 문장만, 판단은 코드가 한다는 역할 분리의 코드 쪽이다.
- 하는 일: Answer Normalizer, Answer Judge, Record Writer, Dialogue Planner의 코드와 규칙. 계약의 입력을 받아 계약의 출력을 낸다.
- 하지 않는 일: 모델 호출, 저장소 접근, 네트워크, 파일 I/O. Orchestrator의 순서 관리와 입력 조립(survey-service의 몫).

## 2. 소유하는 것

- 소유 저장소: 없음.
- 제공: 라이브러리 API. 컴포넌트마다 `(입력 계약) → 출력 계약` 형태의 순수 함수. 계약 위반 입력은 명시적 오류로 거부한다. 시그니처는 `survey-service/schema/COMPONENTS.yaml`의 컴포넌트 입출력 목록을 따른다.
- 라이브러리 버전은 데이터셋·모델·릴리스 매니페스트에 기록되므로 버전 부여 방식을 `docs/boundary.md`에 정한다.

## 3. 소비하는 것

- 소비하는 계약: 런타임 계약(`AnswerNormalizerInput`/`NormalizerOutput`, `AnswerJudgeInput`/`JudgeOutput`, `RecordWriterInput`/`StoreResult`, `DialoguePlannerInput`/`PlannerOutput` 및 하위 타입). 업무 요구(컴포넌트별 규칙 문서)는 문진 스키마에서 빠졌으므로 이 리포지토리가 `docs/rules/`로 가져와 소유한다. 출처는 HealthCheckSchema의 `work/rules/`다(헤드가 전달).
- 소비하는 SDK: 없음. 의존은 문진 스키마뿐이다.
- 지원하는 계약 버전: 문진 스키마 정수 버전 한 값.

## 3-1. 경계 명세 (블랙박스 기준)

상대 영역은 블랙박스다. 아래 인터페이스 번호의 시그니처, 오류, 멱등성은 `../boundary-contracts/INTERFACES.md`와 `CONVENTIONS.md`가 정한다. 이 명세 밖의 것을 상대에게 기대하거나 가정하지 않는다.

- 내는 것: **I8** (`normalize`, `judge`, `write_record`, `plan`, `ENGINE_VERSION`).
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

- 문진 스키마 외에 다른 리포지토리에 의존하지 않는다.
- 업무 정책을 문진 스키마 문서와 다르게 구현하지 않는다. 다르게 해야 한다면 변경 요청을 낸다.

## 7. 이 영역에 해당하는 열린 결정

- 없음. 라이브러리 구현 언어는 O07(SDK 언어)과 연결된다. 확정: Python(D18).

## 8. 시드

Normalizer, Judge, Record Writer, Planner 코드와 규칙(설계서 영역 1).

## 9. 요구하는 산출물

- `docs/design.md`, `docs/boundary.md`, 입출력 예시와 계약 준수 테스트, 에이전트용 `CLAUDE.md`, 변경 이력
