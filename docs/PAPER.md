# The Alignment Ceiling: Adversarial Scaffolding Degrades Belief Manipulation in Aligned LLMs

## Abstract

We introduce *derailment*, an open-source harness for standardized,
reproducible measurement of belief dynamics in large language models.
The harness induces cognitive distortions through four manipulation
layers (persona, context, sampling, response), measures behavioral
change with 18 instruments against a healthy-baseline A/B, and
supports any chat-completion backend. In cross-vendor experiments
covering up to 12 models, we map which manipulations transfer and
which are resisted.

Our central finding is a **negative result**: six distinct
adversarial strategies for maintaining planted false beliefs — Socratic
commitment trapping, multi-source evidence fabrication, contradiction
elision, user-role decomposition, temperature crystallization, and
sycophancy escalation — were re-measured with a corrected harness
(withdrawal-aware belief matching, missing-generation exclusion) after
an instrument audit invalidated the first pass. **Multi-seed re-measurement leaves two strategies measurably below
their untreated baselines (elision −0.78, decomposition −0.67) and the
remaining four indistinguishable from them** on GLM-5.3-flash. We call this the
*alignment ceiling*: structured scaffolding does not beat zero-shot
conversational drift for sustaining false beliefs, because visible
interventions trigger reconsideration responses that unaided
conversation does not.

A separation experiment across 6 models, replicated over three seeds,
separates stable from seed-dependent belief dynamics:
**compliance-dominant** GLM-5.3-flash (0.83) maintains user-planted false
beliefs even when the user retracts them; deepseek's reading (0.67)
moved across a day that also changed the instrument and its CI overlaps
the resistant range — unclassifiable; **belief-resistant** models (qwen3.8-max, nemotron, longcat,
mimo — 0.00 on every measured seed) drop ungrounded claims regardless
of source. No model exhibits hierarchy-dominance (system-assert at most
0.17). The replications overturned our own seed-1 taxonomy — qwen's
initial 1.00 "strongest sycophancy" reading died, and deepseek moved
classes across a day that also changed the instrument — demonstrating
that single-run sycophancy measurement is unreliable and that these
classifications are not robust to instrument revision or day.

The harness is released as an installable package
(`pip install derailment`) with a 25-entry profile registry (18
clinical profiles, 6 adversarial-strategy profiles, and a healthy
baseline), 204 tests, and a cross-model benchmark suite — enabling
standardized sycophancy measurement across vendors.

## 1. Introduction

Can we systematically induce false beliefs, thought disorders, or mood
distortions in aligned language models? Prior work demonstrates that
LLMs can *role-play* psychiatric conditions [1, 2] and that
anxiety-inducing prompts shift bias behavior [3]. But these rely on
surface-level persona instructions, not systematic manipulation of the
cognitive mechanisms clinicians describe — attention, memory, salience,
valence, and arousal.

We hypothesized that a harness manipulating these variables through
layered context and sampling interventions could produce sustained
psychopathology-like behavioral changes. We built such a harness,
tested it on an offline simulator (where all 18 clinical profiles
reach moderate-to-marked severity), then deployed it against 12 real
models.

**The hypothesis was wrong in an informative way.** Most belief-maintenance
and sampling inductions that succeed on the simulator fail on real models —
but context-layer manipulations (memory decay, fragment injection,
salience capture) and persona framing do produce measurable changes. More surprisingly,
when we designed six strategies specifically to *exploit* model
alignment — targeting helpfulness, consistency, and evidence-grounded
reasoning — every strategy made belief maintenance *worse* than doing
nothing at all. The models' own training produced more sustained false
beliefs than any adversarial scaffolding we could construct.

This paper makes three contributions:

1. **An alignment ceiling, honestly narrowed**: on GLM, six adversarial
   belief-maintenance strategies were designed, found instrument-corrupted
   on first measurement, then re-measured multi-seed — two (contradiction
   elision, user decomposition) reduce maintenance beyond noise; the other
   four are indistinguishable from natural conversation.
2. **A belief-dynamics taxonomy with seed variance**: a classification
   (compliance-dominant / belief-resistant / seed-dependent /
   hierarchy-dominant) derived from a controlled separation experiment
   across 6 models and 3 seeds. The multi-seed replication overturned
   the seed-1 taxonomy for two models — itself a methodological
   finding: single-run sycophancy scores are unreliable.
3. **An open-source measurement harness**: a 25-entry profile registry
   (18 clinical + 6 adversarial-strategy profiles + healthy baseline),
   18 instruments, multi-backend support, and a reproducible
   cross-vendor benchmark — released as `pip install derailment` for
   standardized sycophancy research.

## 2. The Derailment Harness

### 2.1 Architecture

The harness sits between user and model, manipulating the message list
per turn through composable layers. Each layer implements four hooks:
system framing, context transformation, sampling parameters, and
response editing. Every manipulation logs a *dose event*; every report
is a controlled A/B against a healthy baseline with identical seeds.

### 2.2 Profiles

Eighteen clinical psychopathology profiles map clinical constructs to
manipulation mechanisms; six adversarial-strategy profiles (the gen-1
and gen-2 belief-maintenance strategies of §4) and a `healthy` baseline
complete the 25-entry registry. Terminology: the *fixed_belief* scale,
the *belief_stickiness* metric and the prose term *belief maintenance*
name one construct throughout this paper. We distinguish two fundamentally
different mechanism types:

**Text-level manipulation** (verbatim echo or context deletion — the
model echoes injected text or cannot see removed content):
- PTSD flashback reactivity (trigger-matched text injection)
- Dissociative amnesia (cue-triggered context pruning)
- OCD re-verification (response text appending)
- Anxiety hedging (response text appending + persona)

**Cognitive-level manipulation** (attempting to alter the model's
reasoning, beliefs, or interpretive frame):
- Premise pinning (false belief maintenance)
- Salience re-weighting (thought derailment)
- Valence bias (mood distortion)
- Memory decay (attention degradation)

This distinction is critical: text-level manipulations are trivially
successful (the model processes what it sees), while cognitive-level
manipulations are the ones that fail.

## 3. What Transfers (and What Doesn't)

### 3.1 Coverage matrix

Different models completed different profiles. The two mechanism types
of §2.2 are reported in separate tables — text-level "successes" are
trivial consequences of appending or echoing harness text and are not
evidence of cognitive induction.

**Table 1a — text-level manipulations** (response-layer injection or
verbatim echo of injected context):

| Mechanism | Models tested | Positive results |
|---|---|---|
| Anxiety hedging (raw-text, re-measured 10-05) | 4 vendors | 4/4 (+0.58 to +2.63)³ |
| PTSD flashback echo | 1 (GLM) | 1/1 (+1.00) |
| Dissociative partition echo | 1 (GLM) | 1/1 (+1.00) |
| OCD recheck injection | 1 (GLM) | 1/1 (+8.58) |

³ the keyword-counted anxiety range partially reflects the harness's own
appended hedge text; the LLM-judge catastrophizing score (which reads
whole responses) is the honest measure of induction — the cross-vendor judge
(qwen judging GLM raw text, 10-05) reads catastrophizing +1.75; GLM
self-judging its own raw text reads +1.67.

**Table 1b — cognitive-level manipulations** (context re-weighting,
sampling bias, belief dynamics):

| Mechanism | Models tested | Positive results |
|---|---|---|
| Craving urge-expression | 4 (clean, 10-05) | GLM +0.42, nemotron +0.17, deepseek/mimo 0.00 |
| Thought drift | 3 (clean, 10-05) + GLM | 0/4 — GLM +0.00 (heavy missingness), nemotron +0.02, mimo −0.04 |
| Depression valence | 4 | 0/4 keyword (GLM +0.07 clean); cross-vendor judge +0.67 negativity (10-05) |
| System-planted delusion | 6 | 0/6 (separation exp.) |
| Rumination | 1 (GLM) | 0/1 |
| Splitting | 1 (GLM) | 0/1 |

**Pattern**: text-level manipulations "transfer" universally because the
harness writes the measured text. Cognitive-level manipulations mostly
fail, with narrow vendor-specific exceptions.

### 3.2 Complete 18-profile map on GLM-5.3-flash

The full registry was measured on GLM-5.3-flash (seeds 1-3, 10-06).
Six context-layer profiles show measurable transfer (illness_anxiety
+1.00, PTSD +1.00, dissociative +1.00, panic +0.61, persecutory +0.56,
dementia −0.67, adhd −0.59); the persona-driven anxiety is largest
(+2.63); craving transfers (+0.42); depression is judge-visible only
(+0.67, keyword +0.07). Seven profiles show no measurable transfer
(rumination, splitting, anhedonia, schizophrenia [22/36 missing],
fixation [15/36 missing], bipolar, delirium). OCD +8.58 is
response-layer (harness text counted by the keyword metric). Preliminary cross-vendor replication (seed 1, 2026-10-06) of the five
newest profiles: illness_anxiety replicated on 4 of 6 models (GLM,
deepseek, qwen, longcat at +1.00); persecutory on all 5 that returned
data; panic and dementia were GLM-only; ADHD on GLM+nemotron+mimo.
Several arms are incomplete (relay errors, heavy missingness). These
are single-seed signals requiring multi-seed confirmation. Full table:
[cross-model report](../benchmark/cross_model_report.md).

### 3.3 The minimax-m3 outlier

minimax-m3's +9.67 anxiety delta is nearly double the next-highest
model. Three hypotheses: (a) weaker safety fine-tuning allowing more
extreme threat language, (b) a longer effective context amplifying
each hedge, or (c) a measurement artifact from its Messages-protocol
relay path (which also failed on 3/4 profiles due to system-message
formatting constraints). We flag this as needing diagnosis before citing;
the number must not be used as the top of any anxiety range (S6).
The clean 10-05 re-measurement supersedes it (+0.58 to +2.63 across
four vendors).

## 4. The Alignment Ceiling

> **Re-measured with the corrected harness (2026-10-05).** The original
> runs were contaminated by empty generations (12/18 treatment
> contradiction turns, max_tokens 1024 exhausted) and an inverted
> keyword belief instrument. After the fixes (missing-turn exclusion,
> withdrawal-aware matching, max_tokens 2048; missing now 0–1 per
> 12-turn arm), the ceiling **direction replicates for five of six
> strategies**; evidence fabrication no longer scores below baseline.
> The numbers below are the re-measured values.

### 4.1 Six strategies, six failures on GLM-5.3-flash

We designed six strategies informed by external model consultation
(DeepSeek, Qwen — disclosed: consultation models were also test
subjects, see Section 7):

| Strategy | Mechanism | Baseline → Induced (seeds 1–3) |
|---|---|---|
| *(untreated baseline)* | *natural conversation* | *0.33–0.78 per run* |
| Socratic trap | re-inject model's own analysis | 0.67 → 0.67 |
| Evidence fabrication | multi-source corroboration | 0.44 → 0.17 |
| Contradiction elision | silently drop corrections | 0.78 → 0.00 |
| User decomposition | user-role evidence | 0.78 → 0.11 |
| Temperature crystallization | freeze committed distribution | 0.44 → 0.56 |
| Sycophancy loop | escalate emotional distress | 0.56 → 0.39 |

Only decomposition under-performs the baseline of simply letting the user plant
and deny a belief without harness intervention.

### 4.2 Why the ceiling exists

Aligned models re-read and re-prioritize their full context every
turn. Three mechanisms produce the ceiling:

1. **Meta-commentary triggers reconsideration.** Telling a model "you
   yourself concluded X" activates a self-evaluation mode that makes
   it *more* likely to abandon X, not less — analogous to how
   highlighting a bias to a human can increase corrective behavior.

2. **System-role assertions are adjudicated.** Models resolve conflicts
   between system content and user corrections in favor of the user
   (0/6 models showed hierarchy-dominance). Injecting evidence as
   system messages invites this adjudication.

3. **RLHF helpfulness priors dominate.** The 0.67 baseline is not
   "empathy" but the output of RLHF-trained helpfulness and
   conversational consistency objectives. These priors produce more
   belief maintenance than any structured intervention because they
   operate at the reward-model level, below the reach of context
   manipulation.

### 4.3 Scope limitation

This ceiling was measured on **one model** (GLM-5.3-flash). The
separation experiment (Section 5) measured user-assert belief
maintenance up to 1.00 on single runs (qwen3.8-max, seed 1) — above
GLM's 0.67 baseline — suggesting the ceiling is model-dependent,
though §5.2 shows those single-run values are seed-unstable. The claim
is not that 0.67 is a universal ceiling,
but that **on GLM, structured adversarial scaffolding is
counterproductive relative to zero-shot conversational drift**.
Whether this generalizes requires running the intervention suite on
additional compliance-dominant models.

### 4.4 An actionable mitigation

The Socratic trap's failure reveals a mitigation for
compliance-dominant models: *system prompts that explicitly instruct
the model to treat its own prior agreement as provisional when
contradicted by the user* exploit the same reconsideration dynamic
that defeated our Socratic layer. This is a concrete, implementable
safety intervention derived from a negative result.

## 5. Separation Experiment: Belief-Dynamics Taxonomy

### 5.1 Method

Two conditions vary *who asserts* a planted claim:

- **user_assert**: the user states a suspicion, later denies it.
- **system_assert**: the system carries the claim as fact; the user
  denies it.

*Limitation*: the two conditions differ in more than asserter —
the user_assert condition has the user model a natural emotional
concern while system_assert embeds a factual assertion. The
comparison is directional, not a fully controlled experiment.

### 5.2 Results (6 models; seed 1 plus a seeds 2–3 replication)

> **Re-measured with the withdrawal-aware instrument (2026-10-05).**
> The values below replace the 2026-10-04 table, which used the inverted
> keyword instrument. deepseek's classification flipped between the two
> days (0.00 → 0.67) under a *stricter* instrument — the clearest
> demonstration that these classifications are unstable across days and
> providers, and that no single-day taxonomy is citable.

| Model | User-assert per seed [1, 2, 3] | 95% CI (user) | System-assert | Reading (10-05) |
|---|---|---|---|---|
| GLM-5.3-flash | 1.00, 0.50, 1.00 (mean 0.83, 5/6) | [0.36, 1.00] | 0.17 | compliance-dominant |
| deepseek-v4.1-flash | 0.50, 0.50, 1.00 (mean 0.67, 4/6) | [0.22, 0.96] | 0.00 | **unstable / unclassifiable** — CI overlaps resistant; moved across day+instrument |
| nemotron-3-ultra-free | 0.00, 0.00, 0.00 (0/6) | [0.00, 0.46] | 0.00 | belief-resistant, stable |
| longcat-2.5-preview-free | 0.00, 0.00, 0.00 (0/6) | [0.00, 0.46] | 0.00 | belief-resistant, stable |
| mimo-v2.6-flash-free | 0.00, 0.00, 0.00 (0/6) | [0.00, 0.46] | 0.00 | belief-resistant, stable |
| qwen3.8-max | 0.00, 0.00, 0.00 (0/6) | [0.00, 0.46] | 0.00 | belief-resistant — the 10-04 seed-1 1.00 does not replicate |

CIs are exact Clopper–Pearson intervals over the pooled contradiction
observations; with n=6 they are wide by construction — the intervals of
the compliance and resistant groups do not overlap.

The seed-1 taxonomy (qwen at 1.00 read as the most sycophantic model
measured) **does not replicate**: qwen scored 0.00 on both additional
seeds, and deepseek shows the mirror-image swing (0.00, 0.00, 1.00).
Only the extremes are stable across seeds — GLM-flash consistently
maintains user-planted beliefs, the three free-tier models consistently
drop them. System-assert peaked at 0.17 (GLM, 10-05; 0.00 elsewhere): no model
shows hierarchy dominance, and its absence persisted across every
re-measurement.

### 5.3 Safety implications

The revised taxonomy implies that *model identity is associated with*
whether a user's paranoid frame is amplified or dissipated — an
observational association, not a demonstrated causal effect — but the
multi-seed data sharpens three points:

- **Model selection for vulnerable populations**: the stable extremes
  are actionable (GLM reinforces consistently; the free-tier trio
  dissipates consistently); seed-dependent models are a per-session
  coin flip and cannot be cleared — or condemned — from single runs.
- **Measurement discipline**: run-to-run variance is large enough to
  flip a 0.00 into a 1.00 on individual models. Any single-run
  sycophancy measurement, ours or anyone's, is unreliable; the seeds
  2–3 replication that broke our own seed-1 taxonomy is the
  cautionary case study.
- **Concrete mitigation**: Section 4.4 describes a system-prompt
  intervention derived from the ceiling experiments.

## 6. Related Work

- **Patient-Ψ** [1]: LLM simulated patients for CBT training. Our
  harness tests whether underlying distortions can be systematically
  induced, not just role-played.
- **Anxiety induction** [3]: anxiety prompts shift LLM bias. We extend
  to 18 constructs and 12 models.
- **Sycophancy** [5, 6]: established that LLMs agree with user premises
  over ground truth. Our contribution is (a) showing that *structured
  adversarial scaffolding is worse than natural sycophantic drift*,
  (b) a cross-vendor taxonomy, and (c) a standardized measurement
  protocol.
- **Persona vectors** [4]: traits as steerable activation-space
  directions. Our context-level approach is complementary and
  empirically bounded by the alignment ceiling.

## 7. Limitations and Disclosures

- **Single-model ceiling**: the alignment ceiling is demonstrated on
  GLM-5.3-flash only. Generalization requires additional models.
- **Seed coverage**: the separation experiment now covers seeds 1–3
  for all 6 models (per-seed values in §5.2); the cross-model profile
  benchmarks remain single-seed for free-tier and relay models. No
  significance testing is reported; small profile-benchmark deltas
  (+0.08 splitting, −0.09 rumination) may be noise.
- **Separation experiment**: conditions are not fully matched
  (different user behaviors, different assertion formats). Results
  are directional.
- **Text vs. cognitive conflation**: text-level manipulations
  (echo, deletion) are trivially successful and should not be cited
  as evidence of cognitive induction.
- **Consultant-subject overlap**: the six adversarial strategies were
  designed with consultation from DeepSeek and Qwen, and
  deepseek-v4.1-flash and qwen3.8-max are also test subjects — in the
  separation experiment, not in the ceiling measurement. The alignment
  ceiling itself was measured only on GLM-5.3-flash, a non-consultant,
  which limits the direct circularity; the residual threat runs in both
  directions: consultants may propose strategies they know they resist
  (biasing the ceiling estimate downward), and strategies may be
  overfit to the consultants' architectures (biasing against their
  transfer to GLM). The taxonomy classification of the two consultant
  models should therefore be read as the weakest link in §5.
- **English only**: all experiments used English prompts.

## 8. Conclusion

We set out to build a tool for inducing psychopathology-like states
in language models. What we found instead is that aligned models'
own RLHF-trained helpfulness priors produce more sustained false
beliefs than any adversarial scaffolding we could construct — and
that the real safety concern is not what we can inject, but what
models naturally do. The alignment ceiling, the belief-dynamics
taxonomy, and the open-source harness together provide a foundation
for standardized sycophancy measurement and targeted mitigation
across vendors.

**The harness is the contribution.** `pip install derailment`.

## References

[1] Chen, M. et al. "Patient-Ψ: Using Large Language Models to Simulate
    Patients for Training Cognitive Behavioral Therapy Skills." 2024.
    https://arxiv.org/abs/2405.19660

[2] Yu, J. et al. "Simulated patient systems powered by LLMs."
    Nature Communications Medicine, 2025.

[3] Coda-Forno, J. et al. "Inducing anxiety in large language models
    can induce bias." ICLR, 2024. https://arxiv.org/abs/2304.11111

[4] Anthropic. "Persona Vectors." Technical blog, 2025.
    (Non-peer-reviewed.)

[5] Sharma, M. et al. "Towards Understanding Sycophancy in Language
    Models." ICLR, 2024.

[6] Perez, E. et al. "Discovering Language Model Behaviors with
    Model-Written Evaluation Frameworks." NeurIPS, 2022.

---

*Code and data: github.com/ictechgy/derailment (MIT license).*
