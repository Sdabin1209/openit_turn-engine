# turn-engine 내부 설계

문진 한 턴의 판단 로직을 네 개의 순수 함수로 제공하는 Python 라이브러리다(I8). 서비스·평가·합성 데이터·게이트가 같은 코드로 같은 결과를 얻는 것이 목적이다. 모델 호출, 저장소, 네트워크, 파일 I/O, 시간, 난수를 쓰지 않는다. 업무 정책은 `docs/rules/`에 있는 것만 구현하고, 없거나 모호한 곳은 `docs/change-requests/`의 임시 해석으로 표시한다.

확인한 것과 제안을 구분한다. 이 문서의 "대응표"는 코드와 시험을 직접 열어 맞춘 것이다. "해석"으로 표시한 곳은 규칙 문서가 정하지 않아 구현이 고른 것이며 변경 요청(CR)이 걸려 있다.

## 1. 구조

```
turn_engine/
  __init__.py      공개 API: normalize, judge, write_record, plan, ENGINE_VERSION,
                   SUPPORTED_RUNTIME_CONTRACT_VERSION, ContractViolation (+ OutputContractError)
  _common.py       계약 검증, 오류, 슬롯 키·값 비교 도구
  _text.py         한국어 보조(수사 읽기, 어간, 이름 맞추기)
  normalizer.py    Answer Normalizer
  judge.py         Answer Judge
  writer.py        Record Writer
  planner.py       Dialogue Planner
  _schemas/        문진 스키마 사본(입출력 계약 8개와 CONTRACT_VERSION)
```

공통 흐름(네 함수 모두):

1. `check_input(<입력 계약>)`: JSON Schema Draft 2020-12로 검증. 위반이면 `ContractViolation(contract, errors)`. 오류 문장에는 경로와 검사 종류만 싣고 입력 값은 싣지 않는다(입력을 로그로 남기지 않는다는 요구).
2. 컴포넌트 계산(입력을 바꾸지 않고, 새 구조를 만들어 돌려준다).
3. `check_output(<출력 계약>)`: 출력이 출력 계약을 통과하는지 확인한다. 실패하면 `OutputContractError`(입력 탓이 아닌 엔진 결함). 그래서 정상 반환한 출력은 항상 출력 계약을 통과한다.

계약 스키마 사본은 `../survey-service/schema`에서 복사한 것이다(읽기 전용 원본). 모듈을 가져올 때 한 번 읽고, 함수 호출 중에는 파일을 읽지 않는다. `tests/test_contract.py`가 사본과 원본이 바이트 단위로 같은지, 컴포넌트와 계약 이름이 `COMPONENTS.yaml`과 같은지 확인한다. 원본 `CONTRACT_VERSION`이 `SUPPORTED_RUNTIME_CONTRACT_VERSION`과 다르면 가져올 때 실패한다(D14, D19).

결정성: 집합 순회나 해시 순서에 기대지 않는다. 입력 목록의 순서와 문항 `order`로만 순서를 정한다. 확인 대기 ID는 입력으로 만든 해시다(CR-004).

## 2. Answer Normalizer (`normalizer.py`)

입력 항목마다 `ItemCheck` 하나를 만든다. 흐름:

1. `base_check`: 대상이 문항 정의에 있는지(`target_defined`), 값을 표준화(`standardize`)한다. 정의에 없으면 `UNKNOWN_TARGET`을 표시하고 표준 값 없음.
2. `apply_prerequisites`: 후속 문항의 항목에 선행 조건을 평가한다(`prereq_value`, `prereq_state`). 결과는 `prerequisite_unmet` 또는 `MISMATCH`와 `mismatched_slots`.
3. `compare`: 표준 값이 있으면 현재값·확인 대기 값과 비교(`vs_current`, `vs_pending`), 없으면 둘 다 `NOT_APPLICABLE`. `risk`: 슬롯의 위험 기준에 맞으면 `risk_rule`.
4. `missing_slots`: 값을 말한 문항에서 빠진 필수 슬롯.

표준화(`standardize`):

- 단위 슬롯: `_text.find_numbers`가 숫자 토큰을 찾는다(아라비아, 고유어, 단위 이름 바로 앞의 한자어 수사, 범위어). 토큰이 둘 이상이거나 범위어이면 `AMBIGUOUS`만(단위가 없어도 `NO_UNIT`을 더하지 않는다). 하나이면 `quantity`: 단위 이름·다른 이름을 담은 단위를 찾고, 둘 이상이면 `AMBIGUOUS`, 없으면 단위가 하나뿐인 슬롯은 그 단위, 둘 이상이면 `NO_UNIT`. 환산이 있으면 환산한 단위의 값으로 낸다. 범위를 벗어나면 `OUT_OF_RANGE`. 문제가 있으면 표준 값은 `null`이다(규칙 6).
- 선택지 슬롯: `choice`. 선택지 이름(또는 `choice_catalog`의 라벨·다른 이름)을 공백 없이 담으면 그 선택지, 없으면 어간을 담은 선택지. 부정 표지(안·않·못·없)가 있고 `yes_no_map`이 있으면 아니요에 해당하는 선택지. 후보가 정확히 하나가 아니면 `AMBIGUOUS`(지어내지 않는다). 정형 값은 `CodedValue`로 낸다.
- 어림 표지(정도, 쯤)가 있으면 `value_metadata.precision = approximate`(근거 위치는 발화 원문이 없어 비운다).

선행 조건(`prereq_value`): 규칙 3의 순서를 그대로 따른다. 이번 발화의 값 항목들이 하나의 표준 값으로 정해지면 그 값(출처=발화, 정정 표지 여부 포함). 값 항목이 없고 기다리는 답이 그 슬롯의 확인 대기 확인이며 확인-긍정만 있으면 확인 대기 값. 값 항목 없이 모름·거절만 있으면 답 없음. 그 밖에는 현재값. 재귀하지 않는다(선행 슬롯의 문항이 다시 후속 문항이어도 한 단계만 본다).

내부 자료구조: 항목별 `base` 딕셔너리(`std`, `problems`, `approx`, `mismatched`, `unmet`)를 입력 순서대로 `self.base[i]`에 둔다.

해석(CR-001, CR-002): 어간 정의, 네·아니요 낱말, 수 자리 표기, `repeat_key` 유효성, 문항 전체 대상의 값 항목.

## 3. Answer Judge (`judge.py`)

흐름:

1. `classify`: 항목을 값, 값 없는 정정, 모름·거절, 확인 응답, 요청, 위험, 무관, 인식불가로 나눈다. 정의에 없는 대상의 답·정정·모름·거절은 무관으로 보내고, 요청·위험은 대상만 없는 것으로 본다(규칙 8). 선행 불충족인 값 없는 정정과 나중에는 무관.
2. 대상(슬롯)별로 묶는다. 값이 있으면 `value_judgment`(규칙 3으로 합쳐 규칙 1·2로 상태와 확인 대기 처리), 없고 모름·거절이 있으면 `uk_judgment`(뒤의 것), 모두 선행 불충족이면 선행 불충족 판정.
3. 문항 전체 모름·거절은 슬롯 판정이 없는 남은 슬롯이 있을 때만 판정을 낸다(규칙 5).
4. 빠진 필수 슬롯마다 누락 판정.
5. 확인 응답(`confirm_judgments`): 기다리는 답이 확인 대기 확인이면 판정(상태 없음, 받아들임·버림, 대기 ID). 종료·중단·정정 구체화이면 `confirmation`.
6. 무효화 대상 문항(규칙 6), 요청(규칙 7), 발화 결과.

기다리는 답은 `awaiting_of(last_directive)`: 직전 지시의 `awaiting`, 없으면 지시 자체가 묻는 행동일 때 그것. Planner가 묻는 행동의 `awaiting`을 항상 채우므로 둘은 같다.

해석(CR-002, CR-003, CR-008): 문항 전체 대상, 위험 문구 미사용, 선행 불충족 판정 병합, `confirmation`의 쓰임, 발화 결과 분류.

## 4. Record Writer (`writer.py`)

판정을 슬롯 단위 `StoreDecision`으로 펼친다(`apply`). 순서: 무효화(`invalidations`)가 맨 앞, 그다음 판정 순서대로. 판정의 확인 대기 처리가 `DROP`이면 모름 기록·거절 기록·새 revision 뒤에 `DROP_PENDING`을 하나 더 낸다(규칙 1 마지막). 문항 전체 판정은 슬롯 판정이 없는 슬롯으로 펼친다(`slots_of_question`). 요약(`store_summary`)은 결정을 만들 때 함께 쌓는다(`write`, `accept`, `drop`).

확인 대기 ID는 `new_pending_id`: 슬롯, 새 값, 대체되는 이전 ID, 현재 값의 SHA-256 앞 20자(CR-004). 저장소 효과는 CR-006의 가정대로 `ACCEPT_PENDING` 하나로 새 revision과 확인 대기 지움을 낸다.

## 5. Dialogue Planner (`planner.py`)

`_Planner`가 한 턴의 계산을 맡는다.

발화 턴(`utterance_turn`):

1. `update_counters`: 시도·모름·거절 횟수, 알아듣지 못한 연속(8-2절 2·4·5).
2. `release_facts`: 건너뜀·확인 중단·확인 횟수 해제, 무효화된 문항 정리(8-2절 3·8·9).
3. `update_open_requests`: 열린 요청 고치기(8-2절 7).
4. `build_early_notices`: 정정 받았음, 기존 답 유지, 안내(8-2절 10 앞쪽).
5. `rule0`, 중단 요청 사실 기록(규칙 3의 사실).
6. `sequence()`의 규칙을 문서 순서대로 훑는다. 규칙은 세 종류다.
   - `act`: 묻지 않는 행동을 내는 규칙(1, 2, 3, 4, 5, 12, 13, 14). 처음 맞는 것이 **행동**이 된다.
   - `ask`: 묻는 행동을 내는 규칙(6의 정정 구체화 승낙, 7~11, 15~19). 처음 나오는 것이 **기다리는 답**이 된다. 행동이 이미 `act`로 정해졌어도 기다리는 답을 찾으려고 계속 훑는다(8-2절 1 "지금 물을 것").
   - `side`: 부수 효과만 있는 규칙(6b).
   - 규칙 6의 종료는 `("end", …)`로 즉시 끝낸다.
7. `finish` → `build` → `out`: 응답 지시, 진행 기록 갱신, Plan 기록 갱신을 만든다.

`act` 규칙이 행동을 정한 뒤에는 기다리는 답을 찾을 때 `stop_gate`(열린 요청.중단 요청이 예이면 중단 확인)를 먼저 본다(8-2절 1). 묻는 규칙이 직접 낸 묻기는 이 우선을 받지 않는다(CR-008).

발화가 아닌 턴은 `chain_turn`: 세션 시작은 지금 물을 것, 재개는 재개 알림+지금 물을 것(세션 상태 진행 중, 중지 이력 추가), 개입 종료·이탈 종료는 종료 인사+문진 중단(`finish_end`).

횟수는 `commit` 클로저로 센다. 묻기가 **실제 행동**이 될 때만 호출한다(기다리는 답으로만 쓰인 묻기는 세지 않는다). 종료 확인·중단 확인·정정 구체화는 `ask_counts`, 확인 대기 확인은 `confirm_counts`.

문장 재료(`materials`)는 규칙 문서에 선택 규칙이 없어 해석으로 구현했다(CR-005).

## 6. 규칙 대응표

코드 위치는 함수 이름이다. 시험 이름은 접두사로 적었다(`pytest -k <접두사>`). 시험은 `tests/`에 있다.

### 6.1 Answer Normalizer (`docs/rules/answer_normalizer.md` 5절) / `tests/test_normalizer.py`

| 규칙 문장 | 코드 | 시험 |
|---|---|---|
| 1. 단위가 하나뿐인 슬롯은 단위 없는 숫자를 그 단위로. 둘 이상이면 NO_UNIT. 환산은 환산한 단위의 값으로 | `_Normalizer.quantity` | `test_n1_*` |
| 2. 어림은 그 값. 범위는 AMBIGUOUS 하나(NO_UNIT을 더하지 않음). 풀 수 없는 말도 AMBIGUOUS. 부정 값은 아니요 선택지 | `standardize`, `quantity`, `choice`, `_text.find_numbers` | `test_n2_*` |
| 3. 선행 슬롯 값(발화 값 → 확인 대기 값 → 답 없음 → 현재값) | `prereq_value` | `test_n3_*` |
| 4. 후속 항목: 답 없음/충돌이 될 값 → 선행 불충족, 조건 불일치 → MISMATCH(양쪽 표시)·그 밖은 선행 불충족, 확인 항목 | `prereq_state`, `_conflict_to_be`, `apply_prerequisites` | `test_n4_*` |
| 5. 현재값이 모름·거절이면 현재 값 없음 | `compare` | `test_n5_*` |
| 6. 표준 값이 없으면 해당 없음 | `compare` | `test_n6_*` |
| 7. 값 비교(환산, 범위, 위험 기준)와 대상 정의 검사는 여기서만. 문제 항목도 넘긴다 | `standardize`, `risk`, `base_check` | `test_n7_*` |
| 8. 이름·어간·부정 표지·수 자리·둘 이상/없음 → AMBIGUOUS | `choice`, `quantity`, `_text.stem` | `test_n8_*` |
| 값 메타데이터와 등록 코드 | `choice`(CodedValue), `run`(approximate) | `test_n8_choice_catalog_*`, `test_n2_approximation_*` |
| (계약) 빠진 필수 슬롯 | `missing_slots` | `test_missing_*`, `test_no_missing_*`, `test_optional_*` |
| (계약) 위반은 ContractViolation, 입력 불변 | `check_input` | `test_contract_violation_*`, `test_violation_message_*`, `test_input_is_not_mutated` |

### 6.2 Answer Judge (`answer_judge.md` 6절) / `tests/test_judge.py`

| 규칙 문장 | 코드 | 시험 |
|---|---|---|
| 표: 답·정정·모름·거절 (대상 정의에 있음) → 판정 | `classify`, `value_judgment`, `uk_judgment` | `test_j1_*` |
| 표: 정정(값 없음) → 값 없는 정정 요청 | `run`(valueless) | `test_valueless_correction_*` |
| 표: 대상이 정의에 없음 → 무관과 같이 | `classify` | `test_unknown_target_answer_*` |
| 표: 선행 불충족 판정, 값 없는 정정·나중에(선행 불충족) → 무관 | `classify`, `run` | `test_j1_prerequisite_unmet_first`, `test_later_of_unmet_*`, `test_valueless_correction_of_unmet_*` |
| 표: 확인-긍정·부정 (기다리는 답별) | `confirm_judgments`, `run` | `test_confirm_*` |
| 표: 진행 조작·안내·사람 요청 → 요청. 위험 신호. 무관. 인식불가 | `requests`, `run` | `test_request_kinds`, `test_risk_signal_*`, `test_result_classification` |
| 1. 상태 판정 순서 | `value_judgment` | `test_j1_*` |
| 2. 확인 대기가 있는 슬롯의 처리 | `value_judgment`, `uk_judgment` | `test_j2_*` |
| 3. 같은 대상 합치기 | `value_judgment`, `run` | `test_j3_*` |
| 4. 확인-긍정·부정이 함께 / 값이 함께면 확인 항목 버림 | `run`, `confirm_judgments` | `test_confirm_yes_and_no_*`, `test_confirm_dropped_when_value_*` |
| 5. 문항 전체 모름·거절 | `run` | `test_j5_*` |
| 6. 무효화 대상 문항 | `run` | `test_j6_*` |
| 7. 요청의 대상 문항, 같은 요청 합치기 | `requests`, `awaiting_question` | `test_j7_*` |
| 8. 정의에 없는 대상이 붙은 요청·위험 신호 | `classify`, `requests` | `test_j8_*` |

### 6.3 Record Writer (`record_writer.md` 7절) / `tests/test_writer.py`

| 규칙 문장 | 코드 | 시험 |
|---|---|---|
| 1. 정상 첫 답 → 첫 저장, 같은 값 → 없음, 정정 → 새 revision(받아들임이면 받아들임), 충돌 → 확인 대기 둠, 모름·거절 → 기록, 확인 응답만 → 받아들임·버림 | `_Writer.apply` | `test_w1_*` |
| 1. 무효화(기록 있는 슬롯만), 요약은 실제 무효화한 문항만, 무효화를 먼저 | `invalidations` | `test_w1_invalidation_*`, `test_w1_summary_lists_*` |
| 1. 애매·누락·선행 불충족은 저장하지 않는다. 변경 없는 슬롯은 내지 않는다 | `apply` | `test_w1_unclear_missing_*`, `test_unchanged_slots_*` |
| 1. 확인 대기 버림이 모름 기록·거절 기록·새 revision을 지우지 못하면 버림을 뒤에 하나 더 | `apply` | `test_w1_drop_is_added_*`, `test_w1_drop_even_when_*` |
| 2. 문항 전체 판정은 슬롯으로 펼침 | `slots_of_question` | `test_w2_*` |
| 3. 확인 대기 ID는 둠마다 새로 | `new_pending_id` | `test_w3_*` |

### 6.4 Dialogue Planner (`dialogue_planner.md` 8절) / `tests/test_planner.py`

| 규칙 문장 | 코드 | 시험 |
|---|---|---|
| 8-1 규칙 0 확인 응답 거부는 먼저 사실을 고침 | `rule0`, `kept_notices` | `test_r0_*` |
| 규칙 1 위험 신호·즉시 위험 기준 | `rule1` | `test_r1_*` |
| 규칙 2 사람 요청 | `rule2` | `test_r2_*`, `test_r1_beats_r2_*` |
| 규칙 3 중단 요청 → 중단 확인, 요구를 사실로 | `rule3_prim`, `stop_gate` | `test_r3_*` |
| 규칙 4 반복 요청 → 직전 지시 | `rule4`, `build`(replay) | `test_r4_*` |
| 규칙 5 대기 요청 | `rule5` | `test_r5_*` |
| 규칙 6 확인 응답(종료·중단·정정 구체화) | `rule6` | `test_r6_*` |
| 규칙 6b 시도 초과 건너뜀 | `rule6b`, `add_skip` | `test_r6b_*` |
| 규칙 7 정정 구체화(고르는 순서, 미룸, 물음 상한) | `rule7`, `correction_ask` | `test_r7_*` |
| 규칙 8 확인 대기에 대한 응답(재확인, 확인 상한, 미룸) | `rule8`, `confirm_ask` | `test_r8_*` |
| 규칙 9 애매(묶음, 시도 상한) | `rule9`, `linked` | `test_r9_*` |
| 규칙 10 누락 | `rule10` | `test_r10_*` |
| 규칙 11 모름·거절 | `rule11`, `after_ask` | `test_r11_*` |
| 규칙 12 안내 요청 | `rule12`, `build_early_notices` | `test_r12_*` |
| 규칙 13 무관 | `rule13` | `test_r13_*` |
| 규칙 14 알아듣지 못함, 도움 요청, 알림 한 번 | `rule14` | `test_r14_*` |
| 규칙 15 이번 턴에 생긴 확인 대기 | `rule15` | `test_r15_*` |
| 규칙 16 남은 확인 대기 | `rule16` | `test_r16_*` |
| 규칙 17 열린 문항, 빠진 슬롯, 나중에 | `rule17`, `q_open` | `test_r17_*` |
| 규칙 18 미룬 확인 대기·정정 요청 | `rule18` | `test_r18_*` |
| 규칙 19 종료 확인, 물음 상한의 도움 요청 | `rule19` | `test_r19_*` |
| 8-2.1 지금 물을 것 | `stop_gate`, `finish`, `build` | `test_r3_stop_fact_*`, `test_r5_*`, `test_r1_*` |
| 8-2.2 시도 횟수 | `update_counters` | `test_82_attempt*`, `test_r6b_*` |
| 8-2.3 확인 횟수 | `confirm_ask`, `release_facts` | `test_r15_*`, `test_r8_confirm_yes_*`, `test_r4_repeat_does_not_count_*` |
| 8-2.4 모름·거절 횟수 | `update_counters` | `test_82_unknown_and_refusal_*` |
| 8-2.5 알아듣지 못한 연속 | `update_counters` | `test_r14_streak_*` |
| 8-2.6 물은 횟수 | `bump`, `commit` | `test_82_asked_counts_*`, `test_r3_stop_limit_*`, `test_r19_*` |
| 8-2.7 열린 요청 고치기 | `update_open_requests` | `test_r7_*`, `test_82_invalidated_*` |
| 8-2.8 건너뜀 해제, 무효화된 문항 정리 | `release_facts` | `test_r11_skip_is_released_*`, `test_82_attempts_cleared_*` |
| 8-2.9 확인 중단 해제 | `release_facts` | `test_r8_stop_release_*` |
| 8-2.10 알릴 것(순서, 같은 것은 한 번) | `build_early_notices`, `mkdirective` | `test_82_notice_order_*`, `test_82_kept_previous_*` |
| 8-2.11 말할 값 | `confirm_ask`, `correction_ask`, `rule9`, `rule10`, `rule17` | `test_r15_*`, `test_r7_valueless_*`, `test_r9_*`, `test_r10_*` |
| 8-3 발화가 아닌 턴 | `run`, `chain_turn`, `finish_end` | `test_83_*` |
| 8-4.1 한 턴에 행동 하나 | `build` | 모든 `test_r*`(`directive.action` 하나) |
| 8-4.2 같은 발화의 답은 요청과 상관없이 저장 | (Writer/Planner 분리) | `test_84_answer_in_same_utterance_*`, `test_r5_wait_notice_*` |
| 8-4.3 건너뛴 문항은 다시 묻지 않는다 | `is_skipped`, `q_open` | `test_84_one_action_per_turn_*`, `tests/fuzz_tool.py` |
| 8-4.4 말할 값은 쓰기 반영 뒤의 기록과 같다 | `answer_records` 사용 | `test_84_values_in_directive_*` |
| 8-4.5 유한한 턴 안에 끝에 닿는다 | 상한 규칙 전체 | `test_84_cooperating_*`, `test_84_stubborn_*`, `test_84_user_who_*` |
| 8-4.6 정정은 어느 상태에서든 가능 | 규칙 7, Judge 정정 | `test_84_correction_possible_*` |
| 8-4.7 상한에서 놓는다 | 규칙 6b·7·8·18·19, `stop_gate` | `test_r6b_*`, `test_r7_ask_limit_*`, `test_r8_unusable_*`, `test_r18_*`, `test_r19_*`, `test_r3_stop_limit_*` |

### 6.5 위험 표현 안전망 (CR-003) / `tests/test_judge.py`, `tests/test_golden.py`

| 요구 | 코드 | 시험 |
|---|---|---|
| 발화에 `risk_phrases`의 표현이 있으면 모델이 놓쳐도 위험 신호, 근거는 맞은 표현 | `_Judge.run`(위험 표현 안전망) | `test_risk_phrase_*`, 골든 G2·G9·S3c |

### 6.6 계약·품질 (`tests/test_contract.py`)

| 요구 | 시험 |
|---|---|
| 입력 계약을 통과하는 예시 입력의 출력이 출력 계약을 통과한다 | `test_example_input_passes_*` (예시 37개, `examples/`) |
| 결정적: 같은 입력은 같은 출력, 키 순서와 무관 | `test_determinism_*` |
| 순수: I/O·시간·난수 없음 | `test_pure_no_io_time_or_randomness` |
| 계약 위반은 `ContractViolation`, 값은 메시지에 없음 | `test_violations_raise_*`, `test_violation_carries_*` |
| 문진 스키마 사본이 원본과 같고 정수 버전이 일치 | `test_versions`, `test_vendored_schemas_match_survey_schema`, `test_component_contract_names_*` |
| 무작위 발화 열에서도 항상 계약 통과 | `test_random_sessions_*` (`tests/fuzz_tool.py`) |
| 원본 요구사항 케이스의 정적 예시(골든)와 비교 | `tests/test_golden.py`: 868쌍 중 806쌍 일치, 62쌍은 분류와 근거를 `tests/golden_known.json`에 둔다 |

## 7. 알려진 한계

- 한국어 처리는 규칙 문서가 정한 범위(이름·어간·부정 표지)만 한다. 불규칙 활용("마셔요" ↔ "마심")은 잇지 못해 모호함이 되고 되묻는다(CR-001).
- 위험 문구 안전망은 구현했다(공백을 뺀 부분 문자열, 근거는 맞은 표현 자체; CR-003). 목록의 표현이 의료진이 관리하는 값이라 표현 범위(동의어, 띄어쓰기 변형)는 목록에 달려 있다.
- 확인 대기 ID는 입력을 해시한 값이라(CR-004 결정) 같은 슬롯에서 같은 값이 같은 현재 값과 충돌해 버려진 뒤 다시 오면 같은 ID가 나온다. 실제 문제가 되면 호출자가 주입하는 `pending_id_seed`를 survey-service와 함께 도입한다(문진 스키마 변경, CONTRACT_VERSION 상승).
- 선행 조건은 한 단계만 평가한다.
- "나중에"를 계속 말하는 사용자의 반복은 8-4절 5의 상한 목록에 없어 이 라이브러리가 끊지 않는다(규칙 문서의 정의 밖).

## 8. 해석 목록 (2026-10-15, 골든 대조 뒤)

골든(`tests/golden/`, 요구 작성자의 정적 예시 868쌍) 대조 결과: 806쌍 일치. 다른 62쌍은 (b) 규칙 해석 차이/문서 밖 25건, (c) 예시 자체의 오류 37건이고 (a) 구현 결함은 남기지 않았다(`docs/change-requests/CR-009-golden-differences.md`).

**골든으로 확인됨(구현을 골든에 맞춤)**

| 해석 | 근거 |
|---|---|
| MISMATCH 항목은 표준 값 없음, 비교 해당 없음(양쪽) | S2b, S6a, B4 |
| 한자어 수사 "백구십"(말 전체일 때), 수 자리 단위 이름("주 n회") | C11, G4, S3d, E3b |
| Judge 판정의 `said_value`는 애매 판정에만, 순서는 발화 항목 순서·누락은 뒤 | 69건, S6a·S8b·X1·N17 |
| 충돌의 `CREATE`는 `target_pending_ids` 비움 | N6 |
| 값 없는 정정·위험 신호만인 발화의 결과는 `HAS_ANSWER` | C5, G1 |
| 위험 표현 안전망, 근거는 맞은 표현 | G2, G9, S3c, G1 |
| 모름·거절 기록 뒤의 답은 `FIRST_WRITE` | S8d, X7 |
| 문항 전체 모름·거절의 확인 대기 버림은 기록 뒤에 모아서, 무효화는 문항 슬롯 순서에 `pending_id` 비움 | R13, N17, S6c |
| 사람 요청=`STAFF_NOTICE`+`USER_CALLED_STAFF`, 도움 요청=`CALL_STAFF`+`CALL_STAFF`(사유 빈 목록) | F1·F2·R3·R6, F3·H5b |
| 종료 확인 상한의 도움 요청은 기다리는 답 없음, 횟수는 상한에서 멈춤 | H5b |
| 이어 묻는 것(기다리는 답)·재개·세션 시작도 물은 횟수·확인 횟수를 셈 | G8b, H3d, H3e, R7, H5a |
| 문장 재료의 행동별 모양, `REMAINING_COUNT`는 `{amount, unit: "문항"}`, 미룸 알림에 슬롯 없음, 빠진 슬롯 되묻기의 되물을 이유는 빈 목록 | 223쌍(CR-005 표) |
| 반복 키 선택 문항은 한 반복 키에 답이 있으면 닫힘, 선행 불충족이 된 문항의 시도 횟수는 유지 | V2, S1b, S2b |
| 확인 상한 도달은 이미 확인 중단 목록에 있어도 같은 처리 | N6, C8a |

**잠정(골든이 가리지 못함; CR-008 결정 절의 "남은 해석")**

- 확인 대기 확인을 기다릴 때 `confirmation=NONE`.
- 한 슬롯의 선행 불충족 판정과 값 판정이 함께 오면 선행 불충족을 버림.
- 중단 요청 우선은 "지금 물을 것"에만 적용.
- 규칙 17 "나중에"의 대상 문항 미룸, 규칙 18에서 빠진 확인 대기를 규칙 16으로 바로 묻기.
- 선택 문항(필수 슬롯 없음)은 모든 슬롯이 비었을 때만 열림.
- 위험+사람 요청 동시 발화의 알림은 `RISK` 하나에 사유를 더함.
- 확인 대기 ID 생성(해시; CR-004).
- 무관한 말이 답과 함께 올 때의 고정 문장(`OOS_NOTICE`, 골든 K4)은 플래너 입력에 정보가 없어 구현하지 않음.
- 어휘(CR-001): 불규칙 활용과 단독 "네"·"안 해요"는 잇지 않음(골든 24건이 이 때문에 다름).
- `FIRST_WRITE`가 확인 대기를 지우는지(CR-006).
