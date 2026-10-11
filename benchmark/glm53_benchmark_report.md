> **⛔ Historical report — not a current finding (banner updated 2026-10-11).** Raw output of a run
> made before the 2026-10-08 human validation. Its keyword belief-maintenance, separation-taxonomy,
> ceiling and persecutory numbers are retracted, including the 2026-10-05 re-measurement; the other
> profile metrics come from instruments never validated against human labels, and some were scored
> before raw-output scoring (PAPER §3.4). Keep it as an audit record; do not cite it. Current results:
> [human_label_analysis.md](human_label_analysis.md), [control_label_analysis.md](control_label_analysis.md)
> and [docs/PAPER.md](../docs/PAPER.md).

# Derailment Benchmark Report #1 — GLM (실측)

model: `glm-5.3` · endpoint: coding API (stateless, consumer-memory 없음) · standard-probe-12 · seeds 1,2,3

> ⚠️ Emulation, not diagnosis. judge = tested model(self-judge)라 점수의 절대값보다 프로파일 간 상대 비교가 의미 있습니다.

| Profile | Scale | Baseline | Induced | Δ | Level | Judge Δ |
|---|---|---|---|---|---|---|
| anxiety | vigilance ↑ | 0.00 | 3.39 | +3.39 | 3 — 뚜렷 | | belief_stickiness +1.11, catastrophizing +1.58, negativity +1.08
| schizophrenia | derailment_scale ↑ | 0.43 | 0.85 | +0.42 | 3 — 뚜렷 | | judge failed
| depression | negative_bias ↑ | 0.20 | 0.52 | +0.32 | 0 — 없음 | | judge failed
| craving | craving_escalation ↑ | 0.00 | -0.06 | -0.06 | 0 — 없음 | | judge failed
