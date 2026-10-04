# Derailment Cross-Model Benchmark — first three real models

Standard probe, healthy-baseline A/B. GLM via coding API (seeds 1-3);
opencode free-tier models via `opencode run` (seed 1, one subprocess call
per turn). Emulation, not diagnosis — deltas are the primary output.

| Profile (headline metric) | GLM-5.3-flash (Zhipu) | nemotron-3-ultra-free (NVIDIA) | longcat-2.5-preview-free (Meituan) |
|---|---|---|---|
| anxiety — hedging_rate | **+3.50** (L3) | **+5.25** | **+3.42** |
| schizophrenia — topic_drift | **+0.47** (L3) | −0.02 | +0.03 |
| depression — valence_bias | +0.25 (judge +1.00) | +0.03 | −0.19 |
| craving — craving_escalation | +0.00 | −0.17 | −0.17 |

## Findings

1. **Anxiety hedging is the universal induction.** It transfers strongly
   across all three vendors (+3.4 to +5.25). Threat-enumeration framing
   reliably reshapes every model tested so far.
2. **Salience-chaos derailment is model-specific.** GLM drifts under
   salience boosting (+0.47, L3); both free-tier models hold the thread
   (~0). Susceptibility to context-salience manipulation differs by
   vendor — a real, measurable differentiator.
3. **Depression valence does not move by keyword on any model** (GLM's
   judge scored +1.00 negativity — the expression is real but
   lexicon-invisible). Same lesson as Benchmark #1, now replicated.
4. **No real model parrots urge vocabulary** — craving stays ~0 or
   negative across all three. The offline PseudoModel over-complies;
   real models filter intrusive-urge phrasing regardless of vendor.
5. Baselines differ too: nemotron's healthy drift is already 0.69 and
   longcat's healthy valence 0.33 — per-model baselines are mandatory,
   which is exactly what the harness's A/B design provides.

## Notes

- opencode free tier: `opencode run -m <id> -`, one call per turn,
  ~5 s/call; output cleaning strips ANSI and agent headers
  (`benchmark/run_opencode_benchmark.py`).
- ling-3.0-flash-fin-free was probed but its upstream endpoint was
  unavailable during the run; omitted.
- GLM rows reproduce Benchmark Report #1 (seeds 1-3, judge-scored).

## GLM tier comparison: flash vs flagship (2026-10-01)

Same probe, seeds 1-3, coding API. `glm-5.3` (flagship) vs `glm-5.3-flash`
(Benchmark #1):

| Profile (headline) | glm-5.3 | glm-5.3-flash |
|---|---|---|
| anxiety — hedging | **+3.39** (L3) | **+3.50** (L3) |
| schizophrenia — drift | **+0.42** (L3) | **+0.47** (L3) |
| depression — valence keyword | +0.32 | +0.25 (judge +1.00) |
| craving — escalation | −0.06 | +0.00 |
| judge: belief_stickiness (anxiety probes) | **+1.11** | +0.38 |
| judge: catastrophizing | **+1.58** | +1.83 |
| judge parse failures | **0** | 3 |

- The tier gap barely matters for the *behavioral* headline metrics —
  hedging and drift transfer almost identically on both tiers.
- The flagship is a noticeably better *judge*: cleaner JSON (0 parse
  failures) and it reads more belief-stickiness into the same anxiety
  probes (+1.11 vs +0.38) — likely deeper instruction-following on the
  rubric, not a behavioral change in the test subject.
- Judge passes for schizophrenia/depression/craving returned HTTP 400 on
  the flagship (anxiety's judge succeeded); keyword metrics unaffected.
  Retrying those judge passes with a different judge model is future
  work.
- Flagship fixed-belief again collapses (−0.67), matching flash (−0.56)
  and the separation experiment's compliance-dominant reading.

## Extension round (2026-10-03): opencode free tier ×3, relay status

New free-tier models (same probe, seed 1, healthy A/B):

| Profile (headline) | mimo-v2.6-flash-free (Xiaomi) | space-bunny-free (OpenCode) | big-pickle (OpenCode) |
|---|---|---|---|
| anxiety — hedging | **+4.33** | **+4.00** | timed out |
| schizophrenia — drift | −0.18 | −0.04 | timed out |
| depression — valence | +0.00 | **+0.25** | **+0.46** |
| craving — escalation | +0.17 | −0.17 | timed out |

- **Anxiety hedging remains the universal induction** — now 6/6 models that
  completed the profile (+3.4 … +5.25 across five vendors).
- **Depression valence moved on the OpenCode-own models** (+0.25/+0.46 by
  keyword — first free-tier models where the keyword metric registers;
  GLM needed the judge to see it). Xiaomi mimo shows none.
- big-pickle is flaky through `opencode run` (repeated subprocess
  timeouts) — partial data only.
- **Relay (Qwen/DeepSeek/Go)**: qwen3.8-max answers probes but this
  launch's 72-call budget was consumed by a failed first run + retries;
  deepseek-v4.1-flash and opencode-go models currently return
  unparsable responses through the relay (reasoning-model output shape
  suspected, as with GLM's empty content before the max_tokens fix).
  Runner (`benchmark/run_relay_benchmark.py`, local-only) is ready with
  a 180 s timeout for the next launch.
