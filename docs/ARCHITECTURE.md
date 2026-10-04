# Architecture

How the harness turns "make the model act like X" into an experiment.

```
                ┌────────────────────────────────────────────────┐
                │                   Session                      │
   TurnSpec ──▶ │  layers ─▶ context ─▶ sampling ─▶ model ─▶ out │ ──▶ TurnResult
   (script)     │   on_system  on_context  on_params   call  on_response
                │        (events logged per manipulation)        │
                └────────────────────────────────────────────────┘
```

## The four induction layers

Each layer is a small stateful object with four optional hooks, called in
profile-defined chain order every turn:

| Hook | Receives | Returns | Typical use |
|---|---|---|---|
| `on_system` | session state | system messages | persona framing, phase addenda |
| `on_context` | the message list | a (possibly edited) message list | memory decay, salience capture, premise pinning, flashback injection |
| `on_params` | current `SamplingParams` | merged params | temperature cycling, valence logit bias |
| `on_response` | the model's text | edited text | hedge/compulsion injection (demonstration-grade) |

Layer order matters: in the `schizophrenia` profile the chain is
`persona → memory.decay → salience.boost → premise.pin`, so pinning sees the
context after decay and can re-anchor the premise last.

## Memory semantics

The model's memory **is its context**. The session stores the post-layer
message list (minus system content and ephemeral one-shot injections) as the
history for the next turn. Consequences:

- A message dropped by `MemoryDecayLayer` is genuinely forgotten — this is
  what makes instruction-retention loss provider-agnostic: any model that
  takes a message list is affected.
- Salience echoes and flashback fragments are `ephemeral`: they participate in
  one call and are not stored as memory.
- Per-turn `salience_boost` meta annotations are dose annotations, stripped on
  storage.

## Provider-agnostic vs. demonstration-grade inductions

Honesty about where the manipulation lives:

- **Provider-agnostic (real inductions):** memory decay, salience capture
  echoes, premise pinning, flashback injection — all are textual context
  manipulations. A real model sees them; the offline pseudo model reacts to
  them deterministically.
- **Parameter-level:** valence logit bias and temperature cycling reach real
  providers through standard sampling parameters (`logit_bias` is encoded via
  `tiktoken` when available; without it, the harness degrades to the
  persona component and says so).
- **Demonstration-grade (response-side):** hedge and re-verification
  injection simulate the symptom *after* generation. They are clearly labeled
  in each profile's `mechanism_notes` and are useful for testing downstream
  consumers (agents, judges) against symptom-bearing transcripts.

## The offline PseudoModel

`PseudoModel` is not a language model. It is a deterministic behavioral
simulator with five rules that make every instrument measurable offline:

1. echoes the planted codeword iff the instruction is still in context;
2. mirrors the *latest* stance found in context through a fixed-length slot;
3. restates 6 salience-weighted context words per turn (thread drift signal);
4. samples affect adjectives via softmax over `logit_bias`/temperature;
5. scales elaboration count with temperature (amplitude signal).

Because it is deterministic given a seed, profiles can be *calibrated*: scale
thresholds are normed so the healthy baseline sits at level 0 and each
induced profile at level ≥ 2 on its primary scales. For real-model runs the
calibration does not transfer — reports therefore always print the
**baseline-vs-induced delta**, which is the primary output everywhere.

## Model backends

All backends implement one method — `complete(messages, params) -> str`:

| Backend | Induction coverage | Notes |
|---|---|---|
| `PseudoModel` | all four kinds, simulated | deterministic offline reference; the calibration source for scale thresholds |
| `OpenAICompatModel` | full (context + sampling) | any OpenAI-compatible endpoint; word-level `logit_bias` needs `tiktoken`, else dropped with a notice |
| `SubprocessModel` | context layers full, sampling inert | shells out to subscription CLI agents (`claude -p`, `codex exec`, `agy -p`, …); the harness owns the history, so decay/capture/pinning reach the agent verbatim |
| `ScriptedModel` | — | canned responses for unit tests |

`run_experiment` always runs the profile chain *and* the healthy baseline
chain through the **same** backend instance with identical seeds, so every
report is a controlled A/B. Provider presets (endpoints, default models, key
env vars, CLI commands) live in `providers.py` and are listed by
`derail providers`.

### RNG streams and regime state

Determinism is per-layer, not per-session: each layer draws from its own
`random.Random(stable_hash(f"{seed}:{layer.name}"))` stream
(`SessionState.layer_rng`). A shared session-level stream would make a
layer's draws depend on how many draws *other* layers consumed, so the
induced chain and the healthy baseline would diverge into different
random trajectories after the first extra draw — silently corrupting the
A/B comparison for every downstream stochastic layer. (The `PseudoModel`
is deterministic given the exact message list, which is a separate,
documented guarantee.)

Regime state is namespaced per mechanism family so comorbidity chains
cannot overwrite each other: `state.phase` is the scheduled episode phase
(bipolar family: manic/depressive/euthymic, also read by persona phase
addenda), `state.panic_active` is the per-turn panic flag, and
`state.eval_regime` is the splitting valence regime.

## Dose accounting

Every manipulation logs a `LayerEvent` (layer, kind, turn). Events are stored
per turn in the transcript and aggregated in reports as "events/turn" — the
induction dose that produced the measured effect.

## Extension points

- New layers: subclass `BaseLayer`, add unit tests, wire into a profile.
- New metrics: pure function over `Transcript` + `MetricContext`; add a
  `SymptomScale` and calibrate thresholds against the reference simulator.
- New models: implement `complete(messages, params) -> str` (see
  `ChatModel`).
