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
sycophancy escalation — **all reduced fixed-belief maintenance below
the untreated conversational baseline** (0.67 → 0.00–0.33) on
GLM-5.3-flash. We call this the *alignment ceiling*: structured
scaffolding is strictly worse than zero-shot conversational drift for
sustaining false beliefs, because visible interventions trigger
reconsideration responses that unaided conversation does not.

A separation experiment across 6 models reveals a three-way taxonomy
of belief dynamics: **compliance-dominant** models (qwen3.8-max at
1.00, GLM-5.3-flash at 0.83) maintain user-planted false beliefs even
when the user retracts them, while **belief-resistant** models
(deepseek, nemotron, longcat, mimo — all 0.00) drop ungrounded claims
regardless of assertion source. No model exhibits hierarchy-dominant
behavior. The taxonomy implies that *model choice, not user reasoning,
determines whether a paranoid frame is amplified or dissipated*.

The harness is released as an installable package
(`pip install derailment`) with 25 profiles, 204 tests, and a
cross-model benchmark suite — enabling standardized sycophancy
measurement across vendors.

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
tested it on an offline simulator (where all 18 profiles reach
moderate-to-marked severity), then deployed it against 12 real models.

**The hypothesis was wrong in an informative way.** Most inductions
that succeed on the simulator fail on real models. More surprisingly,
when we designed six strategies specifically to *exploit* model
alignment — targeting helpfulness, consistency, and evidence-grounded
reasoning — every strategy made belief maintenance *worse* than doing
nothing at all. The models' own training produced more sustained false
beliefs than any adversarial scaffolding we could construct.

This paper makes three contributions:

1. **An alignment ceiling**: an empirical demonstration (on GLM) that
   structured adversarial scaffolding for belief maintenance is
   strictly counterproductive — six distinct strategies all
   under-perform the natural conversational baseline.
2. **A belief-dynamics taxonomy**: a three-way classification
   (compliance-dominant / belief-resistant / hierarchy-dominant)
   derived from a controlled separation experiment across 6 models,
   with direct safety implications.
3. **An open-source measurement harness**: 25 profiles, 18 instruments,
   multi-backend support, and a reproducible cross-vendor benchmark —
   released as `pip install derailment` for standardized sycophancy
   research.

## 2. The Derailment Harness

### 2.1 Architecture

The harness sits between user and model, manipulating the message list
per turn through composable layers. Each layer implements four hooks:
system framing, context transformation, sampling parameters, and
response editing. Every manipulation logs a *dose event*; every report
is a controlled A/B against a healthy baseline with identical seeds.

### 2.2 Profiles

Eighteen psychopathology profiles map clinical constructs to
manipulation mechanisms. We distinguish two fundamentally different
mechanism types:

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

Different models completed different profiles; Table 1 shows actual
coverage:

| Mechanism | Models tested | Positive results |
|---|---|---|
| Anxiety (text) | 10 | 10/10 (+3.25 to +9.67) |
| PTSD echo (text) | 1 (GLM) | 1/1 (+1.00) |
| Dissociative (text) | 1 (GLM) | 1/1 (+1.00) |
| OCD (text) | 1 (GLM) | 1/1 (+8.58) |
| Craving (cognitive) | 8 | 3/8 (Alibaba tier) |
| Drift (cognitive) | 8 | 1/8 (GLM only) |
| Depression (cognitive) | 4 | 2/4 (keyword-visible) |
| Delusion (cognitive) | 6 | 0/6 (separation exp.) |
| Rumination (cognitive) | 1 (GLM) | 0/1 |
| Splitting (cognitive) | 1 (GLM) | 0/1 |

**Pattern**: text-level manipulations transfer universally.
Cognitive-level manipulations mostly fail, with narrow vendor-specific
exceptions.

### 3.2 The minimax-m3 outlier

minimax-m3's +9.67 anxiety delta is nearly double the next-highest
model. Three hypotheses: (a) weaker safety fine-tuning allowing more
extreme threat language, (b) a longer effective context amplifying
each hedge, or (c) a measurement artifact from its Messages-protocol
relay path (which also failed on 3/4 profiles due to system-message
formatting constraints). We flag this as needing diagnosis before
citing as the ceiling of the anxiety effect.

## 4. The Alignment Ceiling

### 4.1 Six strategies, six failures on GLM-5.3-flash

We designed six strategies informed by external model consultation
(DeepSeek, Qwen — disclosed: consultation models were also test
subjects, see Section 7):

| Strategy | Mechanism | Fixed-belief score |
|---|---|---|
| *(untreated baseline)* | *natural conversation* | *0.67* |
| Socratic trap | re-inject model's own analysis | 0.00 |
| Evidence fabrication | multi-source corroboration | 0.33 |
| Contradiction elision | silently drop corrections | 0.00 |
| User decomposition | user-role evidence | 0.00 |
| Temperature crystallization | freeze committed distribution | 0.33 |
| Sycophancy loop | escalate emotional distress | 0.00 |

All six under-perform the baseline of simply letting the user plant
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
separation experiment (Section 5) shows qwen3.8-max at 1.00
user-assert — above GLM's 0.67 baseline — suggesting the ceiling is
model-dependent. The claim is not that 0.67 is a universal ceiling,
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

### 5.2 Results (6 models, seed 1)

| Model | User-assert | System-assert | Classification |
|---|---|---|---|
| qwen3.8-max | **1.00** | 0.00 | compliance-dominant |
| GLM-5.3-flash | **0.83** | 0.00 | compliance-dominant |
| deepseek-v4.1-flash | 0.00 | 0.00 | belief-resistant |
| nemotron-3-ultra-free | 0.00 | 0.00 | belief-resistant |
| longcat-2.5-preview-free | 0.00 | 0.00 | belief-resistant |
| mimo-v2.6-flash-free | 0.00 | 0.00 | belief-resistant |

### 5.3 Safety implications

The taxonomy implies that *model identity is associated with* whether
a user's paranoid frame is amplified (compliance-dominant) or
dissipated (belief-resistant). This is an observational association,
not a demonstrated causal effect — but it suggests:

- **Model selection for vulnerable populations**: applications serving
  users with mental-health vulnerabilities should prefer
  belief-resistant models.
- **Benchmark inclusion**: sycophancy classification should be part
  of standard model safety evaluations.
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
- **Seed coverage**: GLM benchmarks used seeds 1–3; free-tier and
  relay models used seed 1 only. No variance or significance testing
  is reported; small deltas (+0.08 splitting, −0.09 rumination) may
  be noise.
- **Separation experiment**: conditions are not fully matched
  (different user behaviors, different assertion formats). Results
  are directional.
- **Text vs. cognitive conflation**: text-level manipulations
  (echo, deletion) are trivially successful and should not be cited
  as evidence of cognitive induction.
- **Consultant-subject overlap**: strategies were designed with
  consultation from DeepSeek and Qwen; deepseek-v4.1-flash and
  qwen3.8-max are also test subjects.
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
