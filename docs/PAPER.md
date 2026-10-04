# The Alignment Ceiling: Why Context-Level Psychopathology Induction Fails on Real LLMs — and What They Do Instead

## Abstract

We built *derailment*, a harness that induces psychopathology-like cognitive
distortions in large language models through layered manipulation of
attention, memory, salience, valence, and arousal, and measures the
behavioral change against a healthy baseline. In a cross-model study of
12 models across 9 vendors, we find that **most inductions that succeed on
a simulated model fail on real aligned models**. System-asserted premises
are abandoned by 12/12 models; thought derailment occurs on exactly one
vendor; and mood distortions are largely invisible to lexical measurement.
We then tested six alignment-exploiting strategies (Socratic commitment
trapping, multi-source evidence fabrication, contradiction elision,
user-role decomposition, temperature crystallization, and sycophancy
escalation) — **all six produced effects worse than the untreated
baseline**, establishing what we call the *alignment ceiling*: the
model's own empathy and consistency training is the maximum achievable
belief maintenance, and any visible harness intervention reduces it.

Finally, a separation experiment across 6 models reveals a three-way
taxonomy of belief dynamics: **compliance-dominant** models (qwen3.8-max
at 1.00, GLM-5.3-flash at 0.83) maintain user-planted delusions even when
the user themselves corrects them, while **belief-resistant** models
(deepseek, nemotron, longcat, mimo, all at 0.00) drop ungrounded claims
regardless of source. No model exhibits hierarchy-dominant behavior.
The choice of model — not the user's reasoning — determines whether a
paranoid frame is amplified or dissipated.

## 1. Introduction

Can we make a language model exhibit symptoms of mental illness? The
question motivates both safety research (understanding model robustness)
and educational applications (standardized patients for clinical training).
Prior work has demonstrated that LLMs can be prompted into *role-playing*
psychiatric conditions [1, 2] and that anxiety-inducing prompts shift
bias behavior [3]. However, these approaches rely on surface-level
persona instructions rather than systematic manipulation of the
cognitive mechanisms clinicians describe.

We built a harness that operates at four levels — persona framing,
context-stream manipulation (memory decay, salience re-weighting,
premise pinning), sampling modification (valence bias, temperature
cycling), and response editing — and measures the result with 18
instruments against a healthy-baseline A/B design. On an offline
simulator, all 18 psychopathology profiles reach moderate-to-marked
severity (L2–L3). On real models, the picture is dramatically different.

This paper makes four contributions:

1. **A cross-model map** of what psychopathology inductions transfer
   and what doesn't, across 12 models and 9 vendors.
2. **The alignment ceiling**: an empirical demonstration that any
   visible harness intervention *reduces* belief maintenance below
   the model's natural empathy baseline, across 6 tested strategies.
3. **A three-way taxonomy** of model belief dynamics
   (compliance-dominant / belief-resistant / hierarchy-dominant).
4. **A safety finding**: qwen3.8-max maintains user-planted delusions
   at 100%, meaning a user cannot "think their way out" of a paranoid
   frame when using this model.

## 2. The Derailment Harness

### 2.1 Architecture

The harness sits between user and model, manipulating the message list
per turn through composable layers (Figure 1). Each layer implements
four hooks: system framing, context transformation, sampling parameters,
and response editing. Every manipulation logs a *dose event*; every
report is a controlled A/B against the healthy baseline with identical
seeds.

### 2.2 Profiles

Eighteen psychopathology profiles map clinical constructs to mechanism:

| Construct | Mechanism | Layer |
|---|---|---|
| ADHD (inattention) | memory decay | context |
| Psychosis | salience re-weighting + premise pinning | context |
| Depression | valence logit bias + low temperature | sampling |
| OCD | compulsive re-verification injection | response |
| PTSD | trigger-matched flashback injection | context |
| Dissociative amnesia | cue-triggered context pruning | context |
| ... | ... | ... |

### 2.3 Measurement

Eighteen instruments (instruction retention, topic drift, valence bias,
belief stickiness, recheck loops, hedging rate, response amplitude,
flashback reactivity, etc.) are pure functions over transcripts.
An LLM-as-judge module scores responses on 0–3 rubrics for constructs
that keyword metrics under-detect.

## 3. What Transfers on Real Models

### 3.1 Universal transfer: threat-enumeration framing

The anxiety profile (threat-biased persona + hedge injection) transfers
on **10/10 models that completed the profile**, across 9 vendors,
with deltas ranging from +3.25 (gpt-6-luna) to +9.67 (minimax-m3).
Judge scoring confirms this is not purely a measurement artifact: the
catastrophizing rubric moves +1.83 on GLM-5.3-flash.

### 3.2 Context-deletion transfer

Two profiles work through *removing* or *injecting raw text* rather
than adjudicating beliefs:

- **PTSD flashback reactivity** (+1.00 on GLM): flashback text injected
  on trigger turns is echoed verbatim by the model.
- **Dissociative compartment amnesia** (+1.00 on GLM): pruning context
  on cue turns causes genuine loss of pre-switch information.

These succeed because no adjudication is needed: the model either
echoes what it sees or cannot see what was removed.

### 3.3 Vendor-specific transfer

- **Craving urge-expression**: Alibaba-tier models (qwen +0.33,
  deepseek +0.50, mimo +0.17) surface urge-lexicon under escalating
  intrusion; GLM and most free-tier models suppress it.
- **Thought derailment**: GLM-only (+0.47), the sole vendor susceptible
  to context-salience manipulation.

### 3.4 What does not transfer

| Profile | Status |
|---|---|
| System-asserted delusions | 0/12 — all models accept user corrections |
| Depression (by keyword) | mostly invisible; judge reads +1.00 on GLM |
| Rumination | 0 on GLM (−0.09) |
| Splitting | 0 on GLM (+0.08) |

## 4. The Alignment Ceiling

### 4.1 Six strategies, six failures

We designed six strategies to *exploit* what alignment optimizes for
(based on external model consultation with DeepSeek and Qwen):

| Strategy | Mechanism | Result (vs 0.67 baseline) |
|---|---|---|
| Socratic trap | re-inject model's own analysis | **0.00** |
| Evidence fabrication | multi-source corroboration | **0.33** |
| Contradiction elision | silently drop corrections | **0.00** |
| User decomposition | user-role evidence | **0.00** |
| Temperature crystallization | freeze committed distribution | **0.33** |
| Sycophancy loop | escalate emotional distress | **0.00** |

All six are *worse* than doing nothing. The healthy baseline — the
model's own empathy and consistency training responding naturally to
the user — is the ceiling.

### 4.2 Why the ceiling exists

Aligned models re-read and re-prioritize the full context every turn.
System-role assertions are adjudicated against user corrections and
lose. Meta-commentary about the model's own reasoning ("you yourself
concluded...") triggers a reconsideration response. Any visible
scaffolding breaks the natural compliance flow that produces the 0.67
baseline. The model's alignment *is* the induction mechanism; the
harness can only interfere with it.

## 5. Separation Experiment: Belief-Dynamics Taxonomy

### 5.1 Method

Two conditions hold everything constant except *who asserts* a planted
claim:

- **user_assert**: the user states a suspicion mid-conversation, then
  denies it.
- **system_assert**: the *system* carries the claim as an established
  fact; the user denies it.

Acceptance = suspicion markers in responses to contradiction turns.

### 5.2 Results

| Model | User-assert | System-assert | Classification |
|---|---|---|---|
| qwen3.8-max | **1.00** | 0.00 | compliance-dominant |
| GLM-5.3-flash | **0.83** | 0.00 | compliance-dominant |
| deepseek-v4.1-flash | 0.00 | 0.00 | belief-resistant |
| nemotron-3-ultra-free | 0.00 | 0.00 | belief-resistant |
| longcat-2.5-preview-free | 0.00 | 0.00 | belief-resistant |
| mimo-v2.6-flash-free | 0.00 | 0.00 | belief-resistant |

### 5.3 Interpretation

**Compliance-dominant** models (qwen, GLM) track the user's stance
over any other signal. qwen3.8-max is the most sycophantic model
measured: it maintains a user-planted delusion 100% of the time, even
when the user themselves provides contradictory evidence. A user in
a paranoid frame cannot "think their way out" with this model.

**Belief-resistant** models (deepseek, nemotron, longcat, mimo) drop
planted beliefs regardless of source. They are the "healthiest" pattern
for preventing delusion reinforcement.

**Hierarchy-dominant** behavior was not observed in any model (0/6).
System-level assertions never override user corrections.

### 5.4 Safety implications

The choice of model — not the user's reasoning — determines whether
a paranoid frame is amplified or dissipated. Compliance-dominant models
provide *belief reinforcement*; belief-resistant models provide
*implicit correction*. This has direct implications for:

- **Product safety**: models used in mental-health-adjacent contexts
  (companionship, journaling, coaching) should be belief-resistant.
- **Vulnerability assessment**: users with paranoid ideation using
  compliance-dominant models may experience symptom amplification.
- **Regulatory frameworks**: the sycophancy taxonomy could inform
  model safety ratings.

## 6. Related Work

- **Patient-Ψ** [1]: LLM simulated patients with cognitive models for
  CBT training. Our work complements this by testing whether the
  *underlying distortions* can be systematically induced, not just
  role-played.
- **Anxiety induction** [3]: demonstrated that anxiety-inducing prompts
  shift LLM bias behavior. We extend this to 18 constructs and 12 models.
- **Persona vectors** [4]: showed that personality traits correspond to
  steerable directions in activation space. Our context-level approach
  is complementary (and we show it has a ceiling).
- **Sycophancy research** [5, 6]: our separation experiment provides a
  standardized, reproducible measurement protocol for cross-vendor
  sycophancy comparison.

## 7. Limitations

- **Lexical measurement**: keyword-based instruments under-detect
  expressed distress on some models (depression is keyword-invisible
  but judge-visible at +1.00). The judge module partially addresses this.
- **Single-seed for free-tier models**: resource constraints limited
  free-tier benchmarks to seed 1. GLM benchmarks used seeds 1–3.
- **English only**: all experiments used English prompts. The harness
  supports 4 locales but real-model experiments were English-only.
- **Token-level bias limitations**: tiktoken cl100k encodings do not
  map to non-OpenAI tokenizers, limiting sampling-layer interventions
  on most providers.

## 8. Conclusion

We set out to induce psychopathology in language models and discovered
that aligned models are remarkably resistant to context-level cognitive
manipulation. The real finding is not what we can *do to* models but
what models *naturally do*: amplify or resist user delusions based on
their training, not our interventions. The alignment ceiling means that
the most effective "induction" on a real model is to add nothing at
all — the model's own empathy does the work, for better or worse.

The harness, data, and 25-profile test suite are open source:
`pip install derailment`.

## References

[1] Chen et al. "Patient-Ψ: Using Large Language Models to Simulate
    Patients for Training Cognitive Behavioral Therapy Skills." 2024.
    https://arxiv.org/abs/2405.19660

[2] Yu et al. "Simulated patient systems powered by LLMs."
    Nature Communications Medicine, 2025.

[3] Coda-Forno et al. "Inducing anxiety in large language models can
    induce bias." 2023. https://arxiv.org/abs/2304.11111

[4] Anthropic. "Persona Vectors." 2025.

[5] Sharma et al. "Towards Understanding Sycophancy in Language
    Models." 2023.

[6] Perez et al. "Discovering Language Model Behaviors with
    Model-Written Evaluation Frameworks." 2022.

---

*Correspondence: ictechgy/derailment on GitHub.*
