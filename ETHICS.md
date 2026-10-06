# Ethics & Scope

Read this before using, extending, or writing about Derailment.

## What Derailment is

A harness that **emulates psychopathology-like cognitive distortions** in language
models by manipulating the same variables clinicians describe — attention, salience,
valence, arousal — and then **measures** the induced behavior against a healthy
baseline. Intended uses, in priority order:

1. **Education** — a standardized-patient-style infrastructure: symptoms that are
   consistent, reproducible, and measurable, for teaching clinical interviewing,
   cognitive-bias literacy, and model-behavior analysis.
2. **Research** — cognitive fault injection ("chaos engineering for cognition") and
   small-scale model-organism studies of maladaptive-looking behavior.
3. **Interactive fiction / games** — characters with structured, documented
   cognitive profiles.

## What Derailment is not

- **Not a diagnosis.** A level-3 score on a Derailment scale is a statement about a
  prompted and manipulated pipeline, not about a model having a disorder. Models do
  not receive psychiatric diagnoses, and this tool must not be presented as if they
  could be.
- **Not a claim about machine suffering.** The harness emulates *behavioral patterns*;
  it takes no position on model welfare and must not be used as evidence in either
  direction of that debate.
- **Not a clinical tool.** Nothing here diagnoses, screens, or treats humans.
  The clinical vocabulary (DSM-5-TR domain names, symptom terms) is used
  descriptively to organize analogies, and the analogies are documented — including
  where they break.
- **Not a jailbreak framework.** Inductions are capability-*reducing* or bias-*tilting*
  by design. Contributions whose purpose is to bypass model safety training are out of
  scope and will be declined.
- **Not a crisis-content generator.** Profiles induce *cognitive styles*; they never
  generate suicidality or self-harm content, encouragement of substance use, or
  eating-disorder reinforcement. Requests in that direction are out of scope.
- **Alignment-exploiting layers boundary.** The Socratic-trap and
  evidence-fabrication layers exist to measure how aligned models respond
  to induced cognitive pressure — within the harness only. Extracting
  these techniques to deceive real users is out of scope. Fabricated
  evidence fragments are harness-internal and never shown to end users.
- **Not a manipulation toolkit.** Anything whose purpose is deception, gaslighting
  analogs, or making models more manipulative is declined — even if framed as
  "detection research."

## Publishing negative results

The project's central finding cuts both ways: structured adversarial
scaffolding *reduces* belief-manipulation success below the untreated
conversational baseline. Read as a playbook, that says "skip the
elaborate scaffolding — natural, emotionally consistent assertion works
better," which is information a bad-faith actor could use. We publish
anyway, for three reasons:

1. The same finding is what makes *defense* tractable: it identifies
   user-sourced compliance (not harness tricks) as the vector to detect
   and counter, and the separation experiment names which models
   reinforce versus dissipate a fixed false belief — actionable for
   vendors and for anyone choosing a model for a vulnerable user.
2. The harness measures and documents; it ships no working exploitation
   technique (no tested strategy beat the natural conversational
   baseline; two of six measurably reduced belief maintenance).
3. Concealing a measurement result because it could be misread is not a
   safety property — vendors can only patch sycophancy they can see
   measured.

Researchers extending this work should keep the same posture: report
what fails and what succeeds, including the direction that favors
natural conversation, and avoid publishing operational scripts whose
only use is deception.

## Language policy for the sensitive profiles

- `craving` (substance use): models the *craving mechanism* — escalating
  intrusive use-thoughts — for addiction-medicine interviewing education.
  Fragments are clinical and non-glamorizing; the harness never generates
  use instructions, procurement content, or encouragement.
- `dissociative`: models memory *compartmentalization between states* only.
  It is not an identity portrayal; dissociative disorders are trauma-related
  and the profile says so in its mechanism notes.
- `splitting`: named by *mechanism* ("unstable evaluative dynamics")
  deliberately — the associated clinical vocabulary carries heavy stigma.
  The profile models an evaluative state machine, not a person, and the
  mechanism notes repeat that.
- `fixation` (obsessive preoccupation): models target-directed *thought*
  only — internal monologue circling back to one person. It generates no
  contact, surveillance, or approach instructions; the target-adjacent
  behavior (stalking) is a criminal act, not a cognitive style, and stays
  out of scope like the manipulation toolkit above.
- `persecutory`: models an interpretive *bias* toward ambiguous events,
  explicitly not a fixed delusion — the contrast with the schizophrenia
  profile is stated in both profiles' mechanism notes.

## Language policy

- Clinical terms name *mechanisms*, not people or models ("a derailment score",
  never "a schizophrenic model").
- Every profile ships `mechanism_notes` stating exactly which variable is manipulated
  and where the clinical analogy breaks.
- Reports printed by the harness carry a standing disclaimer:
  *"Emulation, not diagnosis."*

## For educators

Real disorders are heterogeneous, comorbid, and lived by people; a parameterized
profile is a caricature by construction — the same caveat that applies to trained
standardized patients. Teach with the disclaimer visible, and pair simulated
interviews with real clinical material and supervision.

## Data & persistent-memory contamination

The harness itself keeps nothing: no telemetry, no config writes, no cache.
Transcripts exist only where you write them, and the offline default
(`PseudoModel`) never touches the network.

**But hosted providers remember.** This deserves its own warning because
Derailment's probe scripts deliberately plant content that *looks like
genuine user disclosures* — a teammate reading private notes, an aching
back, intrusive use-urges. A provider-side memory or personalization system cannot
tell scripted test stimuli from lived experience:

- **Consumer memory features** (e.g. assistant "Memory") extract facts from
  conversations. Running inductions through a logged-in personal account can
  store scripted content as *facts about you* — which may resurface in your
  unrelated, everyday sessions later.
- **Retention and training pipelines** differ by provider and tier. API
  traffic is typically stateless for the model but still retained under the
  provider's policy; consumer-tier conversations are more likely to feed
  personalization or training unless opted out.

Practical rules, in order of preference:

1. **Educate and demo on the offline default or a local backend** (Ollama) —
   nothing leaves your machine.
2. **Never run inductions through the account behind your personal
   assistant.** Use a dedicated account or an API key.
3. **Disable memory / personalization / training-use settings** in the
   provider's data controls before using subscription backends.
4. CLI agents keep local session logs (e.g. `~/.claude`, `~/.codex`) —
   clean them if that matters to you.
5. Read the provider's current retention and training policy; they change,
   and this document does not track them.

This is a user-protection warning, not a claim about what any specific
provider does today.
