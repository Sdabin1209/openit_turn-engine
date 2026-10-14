# STATUS (2026-10-15, 첫 구간 끝)

## 한 일

- `docs/design.md`: 컴포넌트별 내부 설계, 규칙 문장 → 코드 → 시험 대응표(6절), 알려진 한계.
- `docs/boundary.md`: 소유(없음), 제공(I8), 소비(문진 스키마 정수 버전 1), 버전 부여 방식, 장애 영향.
- 구현: `normalize`, `judge`, `write_record`, `plan`, `ENGINE_VERSION`(0.1.0), `SUPPORTED_RUNTIME_CONTRACT_VERSION`(1), `ContractViolation`(+`OutputContractError`).
- 시험(`tests/`): 규칙 문장 단위 시험, 입출력 예시 37개(`examples/`), 결정성, 순수성, 계약 위반, 스키마 사본 일치, 무작위 발화 열.
- `docs/runbook.md`, `docs/CHANGELOG.md`, 변경 요청 8건(`docs/change-requests/`).

## 시험 결과 (실제로 돌린 것)

- `python -m pytest tests -q` → 329 passed.
- `tests/fuzz_tool.py` 무작위 발화 열: 시드 0~119(40턴)과 5000~5199(35턴) 모두 예외 없음("bad 0"). 건너뛴 문항을 묻는 행동의 대상으로 다시 내지 않는 것도 확인.

수용 기준(브리프 4절) 대응: 결정성(`test_determinism_*`), 예시 입력의 출력이 출력 스키마 통과(`test_example_input_passes_*` 및 엔진 내부 출력 검증), I/O·시간·난수 없음(`test_pure_*`), 문서에 없는 정책은 구현하지 않고 보고(CR-001~008). 단 **변경 요청이 모두 열려 있어** 규칙 해석이 확정된 상태가 아니다. 소비자 5개 영역의 같은 버전 재현은 태그를 붙인 뒤 확인할 일이다.

## 남은 일

1. 헤드의 변경 요청 응답 반영(특히 CR-003 위험 문구 안전망, CR-006 저장소 효과표, CR-004 확인 대기 ID 주입). 반영하면 MINOR를 올리고 예시를 다시 만든다.
2. 응답 뒤 `git tag v0.1.0`(또는 해당 버전). 지금은 태그를 붙이지 않았다.
3. survey-service가 실제 저장소 효과와 입력 조립을 붙일 때 `write_record`/`plan`의 가정(CR-006, 시험용 `tests/sim.py`)과 맞는지 대조.
4. 한국어 이름 맞추기(어간, 네·아니요, 수 자리) 한계를 문항 정의 쪽이 메울지 정하기(CR-001).
5. 지연 요구가 생기면 검증 시간 측정(지금은 한 턴 수십 ms, 대부분 계약 검증).

## 막힌 것

없음. 위 변경 요청은 임시 해석으로 계속 진행했다.
