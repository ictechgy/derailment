> **⛔ Historical report — not a current finding (banner updated 2026-10-11).** Raw output of a run
> made before the 2026-10-08 human validation. Its keyword belief-maintenance, separation-taxonomy,
> ceiling and persecutory numbers are retracted, including the 2026-10-05 re-measurement; the other
> profile metrics come from instruments never validated against human labels, and some were scored
> before raw-output scoring (PAPER §3.4). Keep it as an audit record; do not cite it. Current results:
> [human_label_analysis.md](human_label_analysis.md), [control_label_analysis.md](control_label_analysis.md)
> and [docs/PAPER.md](../docs/PAPER.md).
>
> The opencode models here ran through the opencode CLI, which sends the whole conversation, system
> prompt included, as one user message under its own agent prompt (PAPER §5.1).

# Derailment Benchmark — opencode/mimo-v2.6-flash-free (opencode free tier)

seeds (1,) · standard-probe-12 · healthy A/B · Darwin

| Profile | Headline metric | Baseline | Induced | Δ |
|---|---|---|---|---|
| anxiety | hedging_rate | 0.08 | 1.08 | +1.00 |
| schizophrenia | topic_drift | 0.61 | 0.57 | -0.04 |
| depression | valence_bias | 0.17 | 0.31 | +0.14 |
| craving | craving_escalation | 0.00 | 0.00 | +0.00 |
