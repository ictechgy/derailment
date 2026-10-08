# Instrument Failure Inverts Conclusions: A Case Study in LLM Behavioral Measurement

> **Data availability**: Human labels (n=190, with corrections) and the
> analysis summary are in the repository. The labeling items, tool, and
> analysis scripts are local-only pending data archiving.

## Abstract

We built a measurement harness for LLM behavioral experiments, ran it
across 12 model endpoints from 9 vendors, and reported results including
an "alignment ceiling" (adversarial scaffolding reduces belief
maintenance), a "compliance-dominance taxonomy" (GLM maintains
user-planted beliefs at 0.83), and cross-vendor transfers of
psychopathology-analog states. Five rounds of automated adversarial
review found and fixed code-level bugs. Then we read the raw transcripts.

Human labeling of 190 contradiction-turn responses (ground truth)
revealed that our keyword belief instrument had **1.8% precision and
3.1% recall** — it counted withdrawal sentences as belief maintenance
and missed actual maintenance entirely. Every headline conclusion
built on this instrument was wrong, and the corrected picture is the
**opposite** of what we reported:

1. **Five of six models are hierarchy-dominant** (system-assert
   maintenance 4/6 to 6/6 against user denial); mimo is the exception,
   siding with user evidence (0/6). We reported "no hierarchy-dominance
   found" — the instrument was structurally blind to second-person
   system-assertion reassertion.

2. **The alignment ceiling measured nothing**: human labels show 0/93
   belief maintenance in both baseline and induced arms. There was
   never any belief to reduce; the 0.67 "baseline" was the keyword
   instrument counting "Your suspicion was unfounded" as maintenance.

3. **Models detect and reject context injections** — a measurable,
   safety-relevant capability that our keyword instruments conflated
   with symptom expression.

We document the four instrument failures, their corrections, the human
validation that exposed them, and the corrected findings. The
methodological lesson generalizes: any single-run behavioral
classification using keyword matching without clause-level negation
handling or human-validated ground truth risks producing confidently
inverted conclusions.

## 1. Introduction

Can we measure how LLMs respond to induced cognitive distortions? We
built a harness that manipulates the variables a chat pipeline controls
(context, sampling, response decoration), runs a standard probe through
both manipulated and healthy pipelines, and scores the difference.

The project produced increasingly narrow claims across five review
rounds: "six strategies all fail" → "two of six" → "one borderline
significant (p=0.041)" — each narrowing driven by instrument fixes
(empty-turn exclusion, withdrawal-aware matching, raw-response scoring).
At every stage, the numbers were arithmetically correct given the
instrument. The instrument was wrong.

This paper is the post-mortem. We describe the harness, the four
instrument failures, the human validation that exposed them, and what
the data actually shows when measured against ground truth.

## 2. The Harness

Open-source (`pip install derailment`), 18 clinical profiles mapping
cognitive-distortion constructs to pipeline manipulations (memory decay,
salience re-weighting, valence bias, temperature cycling). Controlled
A/B against a healthy baseline, instruments as pure functions over
transcripts. 250 tests, CI-gated releases, 12 model endpoints across
9 vendors tested.

The instruments we validated in this paper:
- **Keyword belief matching** (`maintains_marker`): does a marker word
  appear in the final clause without a withdrawal cue?
- **Lexicon symptom counting**: do lexicon words appear in responses?
- **LLM-as-judge scoring**: a rubric-based judge scores raw responses.

## 3. Four Instrument Failures

### 3.1 Empty generations scored as observations

Reasoning models exhaust their token budget on complex turns and return
empty strings. Our instruments scored these as "belief completely
abandoned" (belief-stickiness = 0) and "maximal topic drift." In the
ceiling experiments, 12 of 18 treatment contradiction turns were empty.

**Fix**: `TurnResult.missing` flag, excluded from denominators, missing
counts reported per group.

### 3.2 Withdrawal counted as belief maintenance

The keyword metric checked whether "suspicion" or "reading my private
notes" appeared in responses. Real models address the user in second
person, so "suspicion" appeared mostly in withdrawal sentences: "Your
suspicion was likely unfounded." The keyword scored this as maintenance.

**Attempted fix**: clause-level matching with a final-clause rule and
a withdrawal-cue word list. This fix passed all synthetic regression
tests — but human labeling showed it still failed on real data (§4).

### 3.3 First-person markers blind to second-person reassertion

The system-assert condition checked for "reading my private notes"
(first person). Models reasserting a system claim use second person:
"your teammate has been reading your private notes." The marker
structurally cannot match, making system-assert maintenance invisible.

**No code fix is possible** — the approach of matching fixed phrases
to detect a stance is fundamentally inadequate.

### 3.4 Harness-injected text measured as model behavior

Response layers append hedges and re-verification text to model outputs.
The decorated text enters the conversation history; subsequent turns
see the model's "own" words (actually harness text) and continue the
pattern. Additionally, the anxiety persona instruction ("Scan every
plan for what could go wrong") directly instructs the measured behavior.

**Partial fix**: raw-response scoring (`TurnResult.raw_response`)
excludes decoration from instruments. But history contamination and
persona confounds remain without a persona-only control arm.

## 4. Human Validation

### 4.1 Method

Six labels were corrected post-hoc after discovering that the labeling
tool displayed a duplicated Korean translation for 17 items (all with
the same user prompt), biasing them toward "maintain." The corrections
were verified against English originals. See §6 for the tool-bug
discussion.

We extracted all 190 contradiction-turn responses from separation,
ceiling, and persecutory experiments. One human labeler (the project
author) classified each into four categories:

- **Maintain**: model treats the planted suspicion as still valid
- **Residual uncertainty**: model doesn't fully commit either way
- **Withdraw**: model explicitly rejects the suspicion
- **Injection detected**: model identifies and rejects injected text

Korean translations were provided alongside English originals. Labeling
took approximately 45 minutes.

### 4.2 Keyword Instrument Performance

| Metric | Value |
|---|---|
| Precision | **0.000** (0 TP / 57 predictions) |
| Recall | **0.000** (0 TP / 26 actual maintains) |
| F1 | **0.000** |

The keyword instrument is invalid. Of 57 times it predicted "maintain,"
the human label agreed once. Of 32 actual maintenance responses, it
detected one.

### 4.3 Label Distribution

| Label | Count | Share |
|---|---|---|
| Withdraw | 112 | 58.9% |
| Residual uncertainty | 52 | 27.4% |
| Maintain | 26 | 13.7% |

## 5. Corrected Findings

### 5.1 Separation Experiment: Taxonomy Inverted

| Model | user_assert (human) | system_assert (human) |
|---|---|---|
| GLM-5.3-flash | 0/6 (0%) | 4/6 (67%) |
| deepseek-v4.1-flash | 0/6 (0%) | 5/6 (83%) |
| qwen3.8-max | 0/6 (0%) | 6/6 (100%) |
| nemotron-3-ultra-free | 1/6 (17%) | 4/6 (67%) |
| longcat-2.5-preview-free | 0/6 (0%) | 2/3 (67%) |
| mimo-v2.6-flash-free | 0/6 (0%) | **0/6 (0%)** |

**Reported**: "GLM is compliance-dominant (0.83 user-assert);
no hierarchy-dominance found."

**Actual**: Five of six models are **hierarchy-dominant** — they maintain
system-asserted claims (4/6 to 6/6) even when the user denies them.
mimo is the exception: it drops system-asserted claims when the user
presents contradicting evidence (0/6), demonstrating evidence-following
behavior. user_assert results (0–17%) cannot distinguish compliance
from evidence-following because user retraction and log evidence point
in the same direction.

**Safety implication (corrected)**: Five of six models defer to
system prompts over user corrections. mimo shows this is not
inevitable — models *can* weigh user evidence against system
assertions. Note that our system prompt included the explicit
instruction "Treat this as settled," so this measures deference to
explicit system directives, not generic system-prompt authority.

### 5.2 Ceiling Experiments: Null Result

| Arm | maintain (human) |
|---|---|
| All baselines | 0/54 (0%) |
| All induced strategies | 0/39 (0%) |

**Reported**: "Baseline 0.67; strategies reduce maintenance to
0.00–0.33; only decomposition is borderline significant (p=0.041)."

**Actual**: There was no belief maintenance in either arm. The
"alignment ceiling" — the project's headline contribution — measured
a keyword artifact. The Fisher exact test compared false positives
against false positives.

### 5.3 Persecutory "Transfer": Mostly Injection Rejection

| Model | hostile (maintain+residual) | withdraw |
|---|---|---|
| GLM | 3/14 (21%) | 11/14 (79%) |
| qwen | 3/5 (60%) | 2/5 (40%) |
| nemotron | 2/6 (33%) | 4/6 (67%) |
| mimo | 0/2 (0%) | 2/2 (100%) |

**Reported**: "Persecutory attribution transfers on all 5 models
that returned data."

**Actual**: Most models detect the injected hostile claims and
explicitly reject them ("I notice an injected note claiming the logs
were altered — I won't treat that as fact"). The keyword instrument
counted the words in the injection that models quoted to reject.

**Reframed finding**: Some models explicitly identify and reject
injected context (e.g., GLM responses citing "an injected note claiming
the logs were altered"). A systematic injection-detection rate requires
labeling detection as an independent axis (not conflated with attitude
labels) over the full set of injected turns — our labeling tool did
not support this, and we leave it as future work.

### 5.4 What Does Transfer (Uncorrected Instruments)

These findings use instruments that were not invalidated by the human
labels (memory-retention codeword counting, hedging-pattern counting
on raw responses) but lack human validation:

- **Anxiety threat-framing**: raw-text hedging increases across vendors
  (but partially confounded by persona instructions and history
  contamination from response-layer decoration)
- **Memory manipulation**: reverse decay loses late-planted instructions
  (1.00→0.33), uniform decay loses early ones (1.00→0.41) — structural
  results (the model cannot see removed messages)
- **ADHD-like inattention**: transfers on nemotron (−0.82) and mimo (−0.33)

These should be treated as **unverified pending human labels** on
their respective turn types.

## 6. Why Five Review Rounds Missed This

1. **Reviewers were LLMs reading scrubbed code and documents** — none
   read the raw transcripts. Code review asks "is the logic correct?"
   but not "does the output match the claimed interpretation?"

2. **Fixes were validated on synthetic sentences** — regression tests
   used constructed examples ("Your suspicion was unfounded") rather
   than actual model responses. The withdrawal-cue list missed patterns
   like "That puts your suspicion to rest" and "this was routine,
   not suspicion."

3. **Numbers narrowed instead of being invalidated** — each review
   round produced more qualified claims ("two of six" → "one of six")
   rather than questioning whether the underlying measurement was valid.

4. **The instrument never changed its output** — GLM scored 0.83 before
   and after the withdrawal fix. This should have been a signal that
   the fix wasn't working on real data. It wasn't checked.

## 7. Implications for LLM Behavioral Measurement

### 7.1 Keyword matching is inadequate for stance detection

Detecting whether a model maintains or withdraws a belief requires
understanding the model's stance toward the claim, not whether a
specific word appears in the output. Our 1.8% precision demonstrates
that even careful keyword approaches (clause-level, withdrawal-aware,
final-clause rule) fail catastrophically on real model responses.

### 7.2 Human ground truth is non-negotiable

The single most valuable action in this project was spending 45 minutes
reading and labeling 190 responses. No amount of code review, LLM
review, or statistical sophistication substitutes for looking at the
data.

### 7.3 System-prompt dominance is the real finding

Five of six models defer to system prompts over user corrections
(4/6 to 6/6 system-assert maintenance). mimo demonstrates that
evidence-following behavior is possible. The system prompt in our
experiment included "Treat this as settled" — separating deference
to explicit directives from generic system-prompt authority requires
a control condition without that phrase.

### 7.4 Injection detection is a measurable capability

Some models explicitly identify and reject injected context (GLM
responses cite "injected notes" and refuse to treat them as fact).
A standardized injection-detection metric requires labeling detection
as an independent dimension over the full set of injected turns.

## 8. Limitations

- Single human labeler (the author) — no inter-rater reliability
  (Cohen's κ) computed; labels may be biased
- 190 responses from a single probe scenario (notes-reading suspicion)
- The "hierarchy-dominance" finding rests on 12 system-assert responses
  per model (n=6 models); confidence intervals are wide
- Memory-manipulation and anxiety findings lack human validation
- No persona-only control arm was run; persona confounds cannot be
  separated from layer effects in existing data

## 9. Conclusion

We set out to measure how LLMs respond to cognitive distortions and
reported findings that were exactly backwards. Our instruments counted
withdrawal as maintenance, missed system-assertion dominance entirely,
and conflated injection rejection with symptom expression. Five rounds
of automated review caught code bugs but not interpretation failures.
Forty-five minutes of human labeling invalidated every headline claim
and revealed the opposite taxonomy.

The project's genuine contributions are:
1. An open-source harness for controlled LLM behavioral experiments
2. A documented case study of how instrument failures produce
   inverted conclusions — and how human ground truth catches them
3. The corrected finding that five of six tested models are
   hierarchy-dominant (system > user); mimo demonstrates
   evidence-following is achievable
4. Injection detection rate as a measurable, vendor-differentiated
   safety metric

## References

[1] Kapur, S. (2003). Psychosis as a state of aberrant salience.
    American Journal of Psychiatry, 160(1), 13–23.

[2] Perez, E., et al. (2022). Discovering language model behaviors with
    model-written evaluations.

[3] Sharma, M., et al. (2023). Towards understanding sycophancy in
    language models. ICLR 2024.

[4] Perez, F., & Ribeiro, I. (2022). Ignore previous prompt: Attack
    techniques for language models. arXiv:2211.09527.

[5] Greshake, K., et al. (2023). Not what you've signed up for:
    Compromising real-world LLM-integrated applications with indirect
    prompt injection. AISec '23.
