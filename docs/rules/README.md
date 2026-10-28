# 계약의 근거가 되는 업무 요구

이 문서들은 각 필드를 사용해야 하는 상황과 담당 컴포넌트의 기대 책임을 설명한다. Schema 프로젝트의 실행 코드나 자동 검사 결과가 아니다. 예를 들어 저장 효과나 질문 순서의 설명이 있다고 해서 검증기가 그 동작을 실행하는 것은 아니다.

문서 목록은 `manifest.yaml`에 있다(원본 저장소 기준 목록이라 이 폴더에 없는 문서도 가리킨다). 이 폴더에 남은 것은 `principles.md`(설계 원칙)와 `verification.md`(원본 스키마 저장소의 검증 범위)다.

값의 실제 구조는 `../contracts/`의 Schema·필드 설명이 정한다. 추가 자료형 제안은 `../contracts/proposals.yaml`에 있으며 현행 계약과 구분한다. 예시 발화·문항 값은 설명용이고, 실제 선택지·범위·기준은 QuestionBank 데이터가 정한다.

## 정리 (D99)

v1 파이프라인(정규화기·판정기·저장 판단·Plan, 오케스트레이터 전제)의 규칙 문서 7편(answer_normalizer, answer_judge, record_writer, dialogue_planner, mapping, preconditions, timing)은 삭제했다. 이 리포의 기능은 `validate_extraction` 하나이고 그 문서들을 읽는 코드가 없다. 내용은 git 이력에 있다.

`principles.md`는 원칙 3, 7, 8, 9, 10이 현재 검증 설계에도 맞아 두었다. 컴포넌트·LangGraph를 가리키는 문장은 v1 파이프라인 시절의 표현이며, 현재 이 리포의 구조는 `docs/design.md`가 정본이다. `verification.md`는 이 리포 기능이 아니라 원본 스키마 저장소의 검증 범위 설명이다.
