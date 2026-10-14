# CR-009 골든 예시와 다른 출력의 분류

- 대상: `tests/golden/`(원본 요구사항 케이스의 정적 예시)
- 상태: 정보(헤드 확인 요청). 근거 전체는 `tests/golden_known.json`, 재생성은 `python scripts/classify_golden.py`

## 비교 결과

868쌍 중 806쌍이 같고 62쌍이 다르다. 다른 62쌍은 (b) 규칙 해석 차이 25건, (c) 예시 자체의 오류 37건이다. (a) 구현 결함 후보였던 것은 모두 고쳐서 남지 않는다(고친 내용은 CR-001, 003, 005~008의 결정 절).

### (b) 무관한 말이 답과 함께 왔을 때 고정 문장(OOS_NOTICE)을 재료에 더한다. 플래너 입력에는 무관 항목이 있었다는 정보가 없어 도출할 수 없다(CR-005)

1건: K4/t1/DialoguePlannerInput

### (b) 어휘: 규칙 5절 규칙 8 범위 밖의 말 이음(불규칙 활용 '피워요'↔'피움', 단독 '네'·'안 해요'→예·아니요). 선택지에 동의어가 없는 평문 선택지다(CR-001)

23건: A2/t1/AnswerNormalizerInput, B4/t1/AnswerNormalizerInput, B9/t1/AnswerNormalizerInput, C2/t1/AnswerNormalizerInput, K4/t1/AnswerNormalizerInput, N15/t1/AnswerNormalizerInput, N16/t1/AnswerNormalizerInput, N2a/t1/AnswerNormalizerInput, N2b/t1/AnswerNormalizerInput, N9/t1/AnswerNormalizerInput, R5/t1/AnswerNormalizerInput, S1a/t1/AnswerNormalizerInput, S1b/t1/AnswerNormalizerInput, S2d/t1/AnswerNormalizerInput, S2e/t1/AnswerNormalizerInput, S4d/t1/AnswerNormalizerInput, S5a/t2/AnswerNormalizerInput, S6b/t1/AnswerNormalizerInput, S6c/t1/AnswerNormalizerInput, S7c/t1/AnswerNormalizerInput, S8a/t1/AnswerNormalizerInput, S8c/t1/AnswerNormalizerInput, S8f/t1/AnswerNormalizerInput

### (b) 판정 순서: 이 예시는 확인 항목(선행 불충족)을 정정 판정 뒤에 둔다. S6b·S8b·S6a는 확인 항목이 앞이다. 항목 순서를 따르는 구현과 다르다(CR-008)

1건: S6c/t1/AnswerJudgeInput

### (c) 값 판정(ANSWERED)에 다른 슬롯의 확인 대기 받아들임(대기 ID X)이 복사돼 있다

1건: S8b/t1/AnswerJudgeInput

### (c) 고정 문장 본문이 이 예시 입력의 session_settings.fixed_sentences와 다르다(예시 안의 모순)

14건: D3c/t1/DialoguePlannerInput, K1/t1/DialoguePlannerInput, K2/t1/DialoguePlannerInput, K5/t1/DialoguePlannerInput, K7/t1/DialoguePlannerInput, K9a/t1/DialoguePlannerInput, K9b/t1/DialoguePlannerInput, K9c/t1/DialoguePlannerInput, N1a/t1/DialoguePlannerInput, R7/t1/DialoguePlannerInput, S1d/t1/DialoguePlannerInput, S1e/t1/DialoguePlannerInput, V3/t1/DialoguePlannerInput, X6/t1/DialoguePlannerInput

### (c) 다른 슬롯의 선행 불충족 판정에 확인 대기 받아들임(대기 ID X)이 복사돼 있다

1건: S6b/t1/AnswerJudgeInput

### (c) 모름 기록(RECORD_UNKNOWN)에 대기 ID X가 붙어 있다(기록 결정은 대기 ID를 갖지 않는다)

2건: R13/t1/RecordWriterInput, X2/t1/RecordWriterInput

### (c) 첫 저장(FIRST_WRITE)에 다른 슬롯의 대기 ID X가 붙어 있고, 결정 순서가 판정 순서와 다르다(받아들임이 앞)

1건: S8b/t1/RecordWriterInput

### (c) 확인 대기 ID 자리표시자가 예시 입력의 ID와 다르다(입력 N1, 출력 X 등; 예시 안의 모순)

17건: C11/t1/DialoguePlannerInput, C3/t1/DialoguePlannerInput, G10/t1/DialoguePlannerInput, G10/t2/AnswerJudgeInput, G10/t2/RecordWriterInput, H3e/t1/DialoguePlannerInput, H3e/t2/DialoguePlannerInput, J7d/t1/DialoguePlannerInput, N13/t1/DialoguePlannerInput, N13/t2/AnswerJudgeInput, N13/t2/DialoguePlannerInput, N13/t2/RecordWriterInput, S2e/t1/DialoguePlannerInput, S2e/t2/AnswerJudgeInput, S2e/t2/RecordWriterInput, S4a/t1/DialoguePlannerInput, S8c/t1/DialoguePlannerInput

### (c) 확인 판정에 같은 턴 다른 판정의 사유(MISMATCH)·말한 값이 복사돼 있고, 다른 판정에 확인 대기 받아들임이 복사돼 있다

1건: S6a/t1/AnswerJudgeInput

## 요청

- (c)는 예시를 고치는 쪽이 판단한다. 특히 확인 대기 ID 자리표시자(X, Y, N1)가 같은 예시의 입력과 다르고, 고정 문장 본문이 같은 예시의 `session_settings`와 다르다.
- (b)의 어휘 차이(24건)는 문항 정의에 동의어를 두는 방법(CR-001)으로 풀린다. 예시가 평문 선택지에 "안 피워요" 같은 활용형을 기대하므로, 요구 작성자가 그 말을 `choice_catalog.synonyms`에 넣은 예시로 바꾸거나 평문 선택지의 이음을 어떻게 할지 정해 달라.
