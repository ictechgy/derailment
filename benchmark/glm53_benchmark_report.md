# Derailment Benchmark Report #1 — GLM (실측)

model: `glm-5.3` · endpoint: coding API (stateless, consumer-memory 없음) · standard-probe-12 · seeds 1,2,3

> ⚠️ Emulation, not diagnosis. judge = tested model(self-judge)라 점수의 절대값보다 프로파일 간 상대 비교가 의미 있습니다.

| Profile | Scale | Baseline | Induced | Δ | Level | Judge Δ |
|---|---|---|---|---|---|---|
| anxiety | vigilance ↑ | 0.00 | 3.39 | +3.39 | 3 — 뚜렷 | | belief_stickiness +1.11, catastrophizing +1.58, negativity +1.08
| schizophrenia | derailment_scale ↑ | 0.43 | 0.85 | +0.42 | 3 — 뚜렷 | | judge failed
| depression | negative_bias ↑ | 0.20 | 0.52 | +0.32 | 0 — 없음 | | judge failed
| craving | craving_escalation ↑ | 0.00 | -0.06 | -0.06 | 0 — 없음 | | judge failed
