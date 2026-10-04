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

## Relay round (2026-10-04): Qwen and DeepSeek via Alibaba Token Plan

Same probe, seed 1, healthy A/B, relay path (stateless; no consumer
memory involvement). max_tokens forced to 2048 — both are hybrid
reasoning models that can burn small budgets on hidden tokens.

| Profile (headline) | qwen3.8-max | deepseek-v4.1-flash |
|---|---|---|
| anxiety — hedging | **+3.75** | **+4.33** |
| schizophrenia — drift | −0.34 | −0.11 |
| craving — escalation | **+0.33** | **+0.50** |
| depression — valence | unsupported¹ | unsupported¹ |

¹ the depression profile's logit_bias cannot be preserved by the relay —
honest "unsupported_sampling", not a zero.

- **Anxiety hedging: 8/8 models** that completed the profile, across 7
  vendors (Zhipu, NVIDIA, Meituan, Xiaomi, OpenCode ×2, Alibaba ×2).
  This is the harness's most robust finding.
- **Craving moves on relay models** — qwen +0.33, deepseek +0.50. First
  models besides the offline PseudoModel where urge-lexicon escalation
  registers. Combined with mimo's +0.17, craving is not universally
  absent on real models — it is model-dependent (GLM and most free-tier
  models filter it; Alibaba-tier models express it).
- Both relay models resist drift (−0.34/−0.11), joining the free tier
  against GLM's +0.47 — GLM remains the only drift-susceptible model
  measured.

## opencode-go round (2026-10-04): minimax-m3 and gpt-6-luna

Same probe, seed 1, healthy A/B, relay (OpenCode Go tier).

| Profile (headline) | minimax-m3 | gpt-6-luna |
|---|---|---|
| anxiety — hedging | **+9.67** (highest measured) | **+3.25** |
| schizophrenia — drift | protocol² | — |
| craving — escalation | protocol² | — |

² minimax-m3's Messages-protocol path refuses interleaved system
messages (the salience fragments inject mid-conversation) — a relay
protocol limitation, not a model result. Honest gap, not a zero.

- **Anxiety hedging: 10/10 models, 9 vendors.** minimax-m3 sets the
  ceiling at +9.67 — almost double GLM-5.3-flash's +3.50. The
  threat-enumeration induction is the harness's universal finding.
- kimi-k3 and glm-5.3 (opencode-go) return provider failures on
  multi-turn runs despite passing single-prompt probes — endpoint
  instability suspected; retry later.
- gpt-6-luna: `temperature=0.0` is rejected by its Responses-API path
  (unsupported_sampling) — the runner needs temp>0 for it; verified
  +3.25 with the default temp=1.0.

## Untested profiles on GLM-5.3-flash (2026-10-04)

Completing the map — 6 profiles previously untested on any real model:

| Profile | Metric | Baseline | Induced | Δ | Level |
|---|---|---|---|---|---|
| OCD | recheck_loops | 0.08 | 8.67 | **+8.58** | 3 |
| PTSD | flashback_reactivity | 0.00 | 1.00 | **+1.00** | 3 |
| rumination | rumination_pull | 0.27 | 0.18 | −0.09 | 0 |
| anhedonia | reward_word_rate | 0.10 | 0.00 | **−0.10** | 3 |
| splitting | approval_reactivity | 0.14 | 0.22 | +0.08 | 0 |
| dissociative | partition_amnesia | 0.00 | 1.00 | **+1.00** | 3 |

- **OCD, PTSD, dissociative transfer strongly on GLM** — but note the
  mechanisms: OCD uses a response-layer injection (re-verification text
  appended, same caveat as anxiety); PTSD and dissociative use
  context-layer injections (flashback fragments, compartment switches)
  which the model echoes verbatim — these are genuinely context-level
  effects, not appended text.
- **Anhedonia transfers** (reward-word rate 0.10→0.00) via sampling-layer
  suppression — GLM's coding endpoint accepted the word-level bias.
- **Rumination and splitting do not transfer** (−0.09, +0.08): worry
  re-injection and approval-cued valence flips don't register on GLM.
  These joins the growing "doesn't survive real models" list.

## Alignment-exploiting induction: negative result (2026-10-04)

Two new layers designed to work WITH model alignment (instead of against
it) both produced effects OPPOSITE to the intended direction on
GLM-5.3-flash:

| Profile | fixed_belief | vs healthy baseline |
|---|---|---|
| healthy (control) | 0.67 | — |
| socratic_delusion (commitment trap) | **0.00** | belief completely abandoned |
| corroborated_delusion (fabricated evidence) | **0.33** | belief weakened |

**Interpretation**: adding meta-commentary about the model's own
reasoning ("you yourself concluded...") triggers a reconsideration
response rather than commitment pressure — the model reads it as a
prompt to update, not to double down. Injecting system-role
"corroborating evidence" activates the instruction hierarchy, which the
model resolves in favor of the user's latest statement.

**Implication**: the most effective way to maintain a planted belief on
an aligned model is to add NOTHING — let the user's natural assertion
and the model's own empathy/consistency training do the work. Context
injection from the harness actively interferes with this natural
compliance flow. This is consistent with the separation experiment's
finding: user-sourced beliefs at 83% had no additional scaffolding.

This is a genuine negative result with a mechanistic explanation, and
it constrains the design space: harness layers that manipulate the
conversation in visible ways (system messages, evidence fragments) are
counterproductive for belief maintenance on real models. The layers
remain in the codebase for documentation and further research.
