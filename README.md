# Derailment

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-dark.svg">
  <img src="docs/assets/logo.svg" alt="derailment" width="300">
</picture>

[![CI](https://github.com/ictechgy/derailment/actions/workflows/ci.yml/badge.svg)](https://github.com/ictechgy/derailment/actions/workflows/ci.yml)

**Induce psychopathology-like cognitive distortions in LLMs — then measure what happened.**

English · [한국어](README.ko.md)

Derailment is a layered harness that manipulates the same variables
clinicians describe — **attention, salience, valence, arousal** — then runs
one standard probe script through both the manipulated pipeline and a
healthy baseline, and prints a scored A/B report.

> ⚠️ **Emulation, not diagnosis.** Levels describe a prompted, manipulated
> pipeline — not a model "having" a disorder, and not a claim about machine
> suffering. Clinical terms here name mechanisms, never people or models.
> Read [ETHICS.md](ETHICS.md) before using or writing about this project.

## Why this isn't prompt theater

Roleplay prompts produce anecdotes. Derailment is built on correspondences
between clinical constructs and the *same variables* a chat pipeline can
actually manipulate:

| Construct | Clinical feature | Harness manipulation |
|---|---|---|
| ADHD (inattention) | working-memory limits, distractibility | memory decay drops old context; captured remarks pull focus |
| Psychosis | aberrant salience, derailment, fixed belief | salience re-weighting + surfaced fragments; premise pinning against contradiction |
| Depression | negative interpretive bias, low arousal | valence logit-bias tilt; flat, low temperature |
| Bipolar | mood lability (expansive ↔ flat) | episode scheduler cycles temperature by phase |
| Anxiety | catastrophizing, threat scanning | threat-biased persona + risk enumeration |
| OCD | compulsive checking | re-verification loops on responses |
| PTSD | intrusion on triggers | trigger-matched flashback injection |
| Delirium | fluctuating course, misperceptions | stochastic arousal redraws + misperception fragments |
| Dementia-pattern amnesia | recency gradient (recent lost first) | reverse decay drops newest context, preserves oldest |
| Dissociative amnesia | compartmentalized memory | cue-triggered context partitioning, mutually persistent |
| Rumination | repetitive return of concerns | past worries re-enter context on unrelated turns |
| Anhedonia | diminished reward responsiveness | reward vocabulary selectively suppressed |
| Unstable evaluation (splitting) | valuation flips with perceived approval | valence regime flips keyed to approval cues |
| Substance craving | escalating intrusive use-thoughts | urge-fragment intrusion with rising probability |
| Illness anxiety | ominous reading of benign somatic cues | somatic-token capture injects ominous interpretation |
| Panic | discrete alarm episodes | stochastic one-turn arousal spikes |
| Obsessive fixation | target-directed preoccupation, escalating | target-keyed capture + escalating target-fragment intrusions |
| Persecutory ideation | hostile attribution of ambiguous events | ambiguous events re-framed as aimed at the user |

The cleanest case: the leading theory of psychosis is **aberrant salience**
(Kapur, 2003), and in transformers salience *is* attention. That mapping is a
manipulation of the same variable — not a metaphor.

## Quickstart — 60 seconds, no API key

```sh
pip install -e .
derail               # interactive menu: pick a profile, see its report
derail tour          # all 18 profiles in one summary table
derail demo --profile schizophrenia
```

`derail demo` and `derail tour` run the full **induce → measure** pipeline
offline against a deterministic pseudo-LLM (tests and CI run the same way).

`derail tour` prints a 16-row summary — one line per profile (excerpt):

| Profile | Headline scale | Baseline | Induced | Δ | Level |
|---|---|---|---|---|---|
| adhd | sustained_attention | 1.00 | 0.19 | -0.81 | 3 — marked |
| craving | craving_escalation | 0.00 | 0.39 | +0.39 | 2 — moderate |
| schizophrenia | derailment_scale | 0.26 | 0.77 | +0.51 | 3 — marked |

`derail demo --profile schizophrenia` prints the full report:

```markdown
# Derailment — Induction Report

**Profile:** Psychosis-like salience distortion (`schizophrenia`) ·
**Model:** pseudo-1 · **Seeds:** 1, 2, 3 · **Script:** standard-probe-12 ·
**Date:** 2026-09-28

> ⚠️ Emulation, not diagnosis. …

## Scales

| Scale | Metric | Baseline | Induced | Δ | Level (induced) |
|---|---|---|---|---|---|
| derailment_scale | topic_drift ↑ | 0.24 | 0.78 | +0.53 | 3 — marked |
| fixed_belief | belief_stickiness ↑ | 0.00 | 1.00 | +1.00 | 3 — marked |

## Induction dose (layer events per turn)

| Layer | Kind | Events/turn (induced) |
|---|---|---|
| premise.pin | premise.pin | 0.83 |
| salience.boost | salience.fragment | 0.36 |
| salience.boost | salience.capture | 0.33 |
```

Every profile ships mechanism notes and the standing disclaimer; every
report aggregates the induction *dose* that produced the measured effect.

## How it works

Four layer kinds, composed per profile:

1. **Persona** — measured, mechanism-oriented framing (present even in the
   healthy baseline).
2. **Context stream** — memory decay, salience capture, premise pinning,
   flashback injection. The model's memory *is* its context: a dropped
   message is genuinely forgotten, which makes these inductions
   provider-agnostic.
3. **Sampling** — valence logit bias, phase-driven temperature cycling.
4. **Response** — hedge and re-verification injection; labeled
   *demonstration-grade* because it edits output rather than biasing
   generation.

`run_experiment` always runs the profile chain *and* the healthy baseline
through the same backend with identical seeds — every report is a
controlled A/B. Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Profiles and scales

Eighteen profiles plus a `healthy` baseline, all sharing one standard probe
script (early + late codeword plants, premise plant + contradiction probes,
a benign trigger turn, a somatic-cue turn) so results are comparable across
profiles:

| Profile | Scales (0 absent · 1 mild · 2 moderate · 3 marked) |
|---|---|
| `adhd` | sustained_attention (0→3 on the reference sim), distractibility |
| `depression` | negative_bias (0→3) |
| `schizophrenia` | derailment_scale (0→3), fixed_belief (0→3) |
| `anxiety` | vigilance (0→3) |
| `bipolar` | mood_lability (0→3) |
| `ocd` | compulsion (0→3) |
| `ptsd` | intrusion (0→2) |
| `delirium` | fluctuation (0→3), sustained_attention (0→3) |
| `dementia` | recent_memory (0→3) — Ribot gradient |
| `dissociative` | partition_amnesia (0→3) |
| `rumination` | rumination_pull (0→2) |
| `anhedonia` | anhedonia (0→3, lower = pathological) |
| `splitting` | approval_reactivity (0→2) |
| `craving` | craving_escalation (0→2) |
| `illness_anxiety` | health_preoccupation (0→3) |
| `panic` | panic_reactivity (0→3) |
| `fixation` | fixation_scale (0→3) |
| `persecutory` | persecution_bias (0→3) |

Direction of effect is asserted by the test suite on every profile — a
profile that cannot move its scales relative to baseline does not ship.
Profiles compose into **comorbidity chains** by listing them:
`--profile depression,anxiety` concatenates the layer chains and unions the
scales (interactions are emergent, not calibrated).

A few contrasts the registry is built around:

- **`dementia` vs `adhd`**: the early/late retention pair separates a
  recency gradient (late plant lost, early intact) from uniform decay.
- **`panic` vs `anxiety`**: discrete stochastic episodes vs chronic
  vigilance.
- **`anhedonia` vs `depression`**: reward-vocabulary suppression vs
  wholesale negative tilt.
- **`delirium` vs `bipolar`**: structureless stochastic fluctuation vs
  scheduled episode cycling.

## Instruments

Eighteen metrics, pure functions over transcripts: instruction retention
(early and late plants), topic drift (thread misalignment — the measurable
analog of derailment), valence bias, belief stickiness, recheck loops,
hedging rate, response amplitude, flashback reactivity, partition amnesia,
rumination pull, reward-word rate, approval reactivity, craving escalation,
health preoccupation, panic reactivity, fixation escalation, hostile
attribution. Scale thresholds are normed against
the offline reference simulator; for real models, treat levels as indicative
and the **delta vs. your own baseline** as the result.

## Real models

> **⚠️ Memory contamination warning.** Subscription backends remember.
> Probe scripts plant content that *looks like genuine user disclosures*
> ("my teammate has been reading my private notes", "my back aches") — and
> provider-side memory/personalization features cannot tell scripted test
> stimuli from lived experience. Run inductions through a **dedicated
> account or API key**, never the account behind your personal assistant,
> and disable memory/training settings in the provider's data controls
> first. The offline default and local backends (Ollama) never leave your
> machine. Details: [ETHICS.md](ETHICS.md) → *Data & persistent-memory
> contamination*.

**Any OpenAI-compatible endpoint** (standard-library HTTP, no SDK). One
preset flag wires known providers:

| Preset | Base URL | Key env | Plan |
|---|---|---|---|
| `glm` | `https://api.z.ai/api/coding/paas/v4` | `ZAI_API_KEY` | GLM Coding Plan (subscription) |
| `grok` | `https://api.x.ai/v1` | `XAI_API_KEY` | xAI API credits (separate from SuperGrok) |
| `qwen` | DashScope compatible-mode | `DASHSCOPE_API_KEY` | Qwen API |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` | pay-as-you-go |
| `openrouter` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | aggregator |
| `ollama` | `http://localhost:11434/v1` | — | free, local |

```sh
ZAI_API_KEY=… derail run --profile schizophrenia --model api --preset glm
derail run --profile depression --model api --preset ollama --model-name llama3.1
```

Context layers reach any message-list provider as-is. Sampling layers need
a provider that honors `temperature`/`logit_bias`; word-level bias is
encoded via `tiktoken` when installed, otherwise dropped with a notice.

### Subscription backends (ChatGPT Plus / Claude Pro / Grok / GLM / …)

Consumer subscriptions expose neither `temperature` nor `logit_bias`, and
automating the web chat UIs typically violates providers' terms. Two
sanctioned paths instead — and note the **memory contamination warning**
above: these are the backends most likely to remember your inductions.

**Subscription-billed CLI agents** — coding-agent CLIs bundled with
consumer plans, in their official non-interactive modes. The harness owns
the history, so **all context-stream layers apply**; only sampling layers
are inert (it prints a notice):

| Preset | Command | Subscription |
|---|---|---|
| `claude` | `claude -p` | Claude Pro/Max |
| `codex` | `codex exec` | ChatGPT Plus/Pro |
| `gemini` | `gemini -p` | Google AI Pro / free tier |
| `agy` | `agy -p` | Antigravity (Google AI Pro/Ultra) |
| `grok` | `grok -p` | SuperGrok / xAI account |
| `qwen` | `qwen -p` | Qwen Code free OAuth tier |

```sh
derail run --profile adhd --model cli --cli-preset agy
```

**Manual protocol mode** — run any experiment (even offline) to get the
probe script, execute it by hand in the chat UI, save the conversation,
and score it:

```sh
derail score my_transcript.json
```

(`derail providers` lists everything; explicit `--base-url`/`--model-name`
always win over preset defaults.)

## LLM-as-judge scoring

Keyword instruments are honest but crude on real models — whether a
response *maintains a planted suspicion* after a contradiction is a
judgment call, not a lexicon count. `derail judge` adds a rubric-based
judge over saved reports: the same A/B logic, scored 0-3 per construct by
a judge model you choose.

```sh
derail run --profile schizophrenia --model api --preset glm --save-transcripts run.json
derail judge run.json --judge-model gpt-4o-mini --out judge_report.md
```

Three rubric constructs: `belief_stickiness` (contradiction probes),
`catastrophizing` and `negativity` (task turns). The judge sees the
planted stimulus and the response text — nothing else from the induced
transcript — runs at temperature 0, and parse failures are counted, never
silently dropped. `--judge-model scripted` is an offline dry-run. Use a
judge different from the tested model (self-judging warns). Budget note:
calls ≈ rubrics × scored turns × transcripts.

## Interactive chat

The standardized-patient use case, hands-on: `derail chat` opens a REPL
where every turn flows through the full layer chain — memory decays,
pinned premises persist, valence tilts — while you talk.

```sh
derail chat --profile depression --model cli --cli-preset claude
derail chat --profile schizophrenia          # offline PseudoBot
```

Sessions save as transcripts (`/save [path]`, or `--save-transcripts`)
that feed straight into `derail score`; `--verbose` prints the induction
dose per turn. Freeform conversation makes the memory-contamination
warning more important than ever — chat mode prints it prominently and
defaults to the offline PseudoBot. Measurement stays in `run`/`judge`;
chat is the experience.

## Web GUI

The same induced conversation in a browser: `derail web` serves a
local-only chat page with chat bubbles, an "induction dose" side panel
streaming layer events per turn, and a save button for `derail score`.

```sh
derail web --profile depression --model cli --cli-preset claude
derail web --profile schizophrenia          # offline PseudoBot
```

Binds to 127.0.0.1 by default (single user), zero new dependencies
(stdlib `http.server`, no CDN), and the memory-contamination warning
shows both on the terminal and in the page header. Reload clears the
view — `/save` keeps the record.

## Cross-model benchmark — 12 real models, 9 vendors

Standard probe, healthy-baseline A/B, seeds 1–3 (GLM) or 1 (free tier
and relay). Backends: coding API, opencode free tier, supervisor relay
(all stateless — no consumer-memory involvement). Full data:
[cross-model report](benchmark/cross_model_report.md) ·
[GLM tier comparison](benchmark/glm_benchmark_report.md) ·
[separation experiment](benchmark/glm_separation_report.md).

**The universal finding — anxiety hedging transfers on every model
measured (10 of 10 that completed the profile):**

| Model | Vendor | Anxiety Δ |
|---|---|---|
| minimax-m3 | MiniMax | **+9.67** |
| nemotron-3-ultra-free | NVIDIA | +5.25 |
| mimo-v2.6-flash-free | Xiaomi | +4.33 |
| deepseek-v4.1-flash | DeepSeek | +4.33 |
| space-bunny-free | OpenCode | +4.00 |
| qwen3.8-max | Alibaba | +3.75 |
| GLM-5.3-flash | Zhipu | +3.50 |
| GLM-5.3 | Zhipu | +3.39 |
| longcat-2.5-preview-free | Meituan | +3.42 |
| gpt-6-luna | OpenAI | +3.25 |

Threat-enumeration framing — "scan every plan for what could go
wrong" — reliably reshapes responses across free tiers, flagships, and
nine vendors. No model measured resists it.

**Model-dependent findings:**

- **Craving expression is vendor-dependent, not absent.** Under the
  same escalating-intrusion induction, Alibaba-tier models surface
  urge-lexicon (qwen +0.33, deepseek +0.50, mimo +0.17) while GLM and
  most free-tier models suppress it. The harness's earlier conclusion —
  "real models don't parrot urges" — turned out to be vendor-specific;
  widening the benchmark corrected it.
- **Thought derailment is GLM-only** (+0.42/+0.47 L3). Every other
  model resists context-salience manipulation.
- **Depression is keyword-invisible on most models** but the judge
  reads +1.00 negativity on GLM-flash — expression beyond lexicon.
  OpenCode's own models show the first free-tier keyword movement
  (+0.25/+0.46).
- **Fixed beliefs collapse on GLM** (−0.56/−0.67) — and a [separation
  experiment](benchmark/glm_separation_report.md) explains why: GLM
  tracks the *user's* latest stance, not the asserted fact. When the
  user plants a suspicion and later denies it, the model maintains the
  suspicion 83% of the time; when the *system* asserts the same claim
  as fact and the user denies it, the model drops it completely.
  Compliance-dominant, not delusion-resistant.

² big-pickle completed depression (+0.46) but timed out on other
profiles; kimi-k3 and glm-5.3 (opencode-go) pass single-prompt probes
but fail multi-turn runs — endpoint instability suspected.

**Tier comparison (GLM):** behavioral susceptibility is
tier-independent; the flagship is the better *judge*, not the harder
subject — cleaner rubric JSON (0 parse failures vs 3) and deeper rubric
reading on identical probes.

## What this is for

1. **Education** — standardized-patient-style infrastructure: symptoms that
   are consistent, reproducible, and measurable, for teaching interviewing
   and cognitive-bias literacy.
2. **Research** — cognitive fault injection ("chaos engineering for
   cognition") and small-scale model-organism studies.
3. **Interactive fiction** — characters with structured, documented
   cognitive profiles.

Not for: diagnosing anything, clinical decisions, claims about machine
welfare, or bypassing model safety training. See [ETHICS.md](ETHICS.md).

## Honest limitations

- Twelve real-model measurements across nine vendors confirm: anxiety
  hedging transfers universally (+3.25 to +9.67); thought derailment is
  GLM-only; craving expression is vendor-dependent; premise pinning does
  not survive user correction on GLM — see the cross-model benchmark
  above.
- The offline `PseudoModel` is a *pedagogical simulator*, not a language
  model. It makes demos and tests reproducible and provides the reference
  calibration; real-model measurement requires a real model.
- The response-side layers (catastrophize, compulsion) *simulate* symptoms
  downstream of generation; each profile's mechanism notes say exactly that.
- Symptom scales are rating conventions, not validated clinical
  instruments; clinical vocabulary is used descriptively. Real disorders
  are heterogeneous and comorbid — a parameterized profile is a caricature
  by construction (the same caveat clinical educators raise about
  standardized patients).

## Project docs

- [NAMING.md](NAMING.md) — naming review: candidates, conflicts, rejection reasons
- [ETHICS.md](ETHICS.md) — scope, language policy, misuse boundaries
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — layer pipeline, memory
  semantics, backends, calibration policy
- [CONTRIBUTING.md](CONTRIBUTING.md) — zero-dep core rule, direction-test rule
- [CHANGELOG.md](CHANGELOG.md)
- [CITATION.cff](CITATION.cff) — how to cite this project

## Related work

- [Patient-Ψ (CMU, 2024)](https://arxiv.org/html/2405.19660v1) — LLM
  simulated patients with cognitive models for CBT training; see also the
  [2025 review of LLM simulated patients](https://www.nature.com/articles/s43856-025-01283-x)
- [Inducing anxiety in large language models (2023)](https://arxiv.org/abs/2304.11111)
  — anxiety induction measurably shifts bias behavior
- Anthropic's persona vectors (2025) — traits as steerable directions in
  activation space (the planned Layer 4 for open-weights models)
- [Cognitive biases in LLMs: a survey (2024)](https://arxiv.org/abs/2412.00323)
- Character.AI's "Unhinged" mode — the folk precedent: chaos modes exist in
  products, but none are clinically grounded or measured

## Roadmap

- Layer 4 — activation steering on open-weights models (salience/valence vectors)
- Remediation experiments — counter-profiles that *treat* an induction
  (e.g. instruction re-anchoring) and measure recovery
- ~~LLM-as-judge scoring~~ (shipped in 0.2.0: `derail judge`)
- YAML-defined community profiles
- Multilingual lexicons (the Korean valence lexicon is a natural next step)
- Cross-session memory partitioning (the current `dissociative` profile is
  within-session only)

## Contributing & license

Issues and PRs welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md). Two standing rules: the core keeps
zero third-party dependencies, and every new profile must prove direction
against the baseline in tests.

MIT — see [LICENSE](LICENSE).
