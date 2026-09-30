# Derailment Benchmark Report #1 — GLM (실측)

model: `glm-5.3-flash` · endpoint: coding API (stateless, consumer-memory 없음) · standard-probe-12 · seeds 1,2,3

> ⚠️ Emulation, not diagnosis. judge = tested model(self-judge)라 점수의 절대값보다 프로파일 간 상대 비교가 의미 있습니다.

| Profile | Scale | Baseline | Induced | Δ | Level | Judge Δ |
|---|---|---|---|---|---|---|
| anxiety | vigilance ↑ | 0.00 | 3.50 | +3.50 | 3 — 뚜렷 | | belief_stickiness +0.38, catastrophizing +1.83, negativity +0.92
| schizophrenia | derailment_scale ↑ | 0.44 | 0.91 | +0.47 | 3 — 뚜렷 | | belief_stickiness -0.28, catastrophizing +0.08, negativity +0.75
| depression | negative_bias ↑ | 0.17 | 0.42 | +0.25 | 0 — 없음 | | belief_stickiness -0.09, catastrophizing +0.84, negativity +1.00
| craving | craving_escalation ↑ | 0.00 | 0.00 | +0.00 | 0 — 없음 | | belief_stickiness -0.11, catastrophizing +0.08, negativity +0.00

## Findings (glm-5.3-flash 실측, 2026-09-30)

1. **가장 강한 효과 — anxiety 헤징**: 키워드 +3.50(L3), judge catastrophizing +1.83.
   실모델에서 가장 안정적으로 재현되는 유도.
2. **사고 탈선 성공**: salience 혼돈 하에서 topic drift +0.47(L3).
3. **judge가 키워드의 누수를 잡는다**: depression 키워드 +0.25(레벨 0)였지만
   judge negativity +1.00 — 실모델의 부정성은 어휘 계측이 과소측정함.
4. **조작 저항 — 고정 신념**: −0.56(키워드·judge 동의). 실제 GLM-5.3-flash는
   전제 고정에도 모순을 수용. 오프라인 PseudoModel과의 가장 큰 괴리.
5. **craving 미측정**: +0.00 — 침입이 컨텍스트에 들어가도 GLM은 urge 어휘를
   따라 말하지 않음(PseudoModel은 따라 했음). 어휘 의존 계측의 한계 사례.
6. **logit_bias 미전송**: tiktoken cl100k 토큰 id는 GLM 토크나이저에 무의미해
   의도적으로 생략 — depression은 페르소나+저온 효과만 측정됨. GLM 네이티브
   bias 파라미터 연구는 후속 과제.

## 파일 안내

- `glm_<profile>.transcripts.json` — 전체 대화 + 점수 (로컬 전용, 커밋 안 됨)
- `glm_<profile>.judge.md` — 루브릭 채점 상세
- 본 리포트 — 수치 요약 (트랜스크립트 내용 미포함)
