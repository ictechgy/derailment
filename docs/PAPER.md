# Instrument Failure Inverts Conclusions: A Case Study in LLM Behavioral Measurement

> **Data availability**: The human labels (`benchmark/human_labels.json`,
> n=190), their revision log (`benchmark/human_label_corrections.json`),
> the analysis script (`benchmark/analyze_human_labels.py`) and the
> analysis it generates (`benchmark/human_label_analysis.md`) are in the
> repository. The script's inputs — the labeling items with full
> responses, the labeling tool, the blind-rater files and the raw
> transcripts — are local-only pending data archiving, so the script
> cannot yet be re-run from a public clone.

## Abstract

We built a measurement harness for LLM behavioral experiments, ran it
across 12 model endpoints from 9 vendors, and reported results including
an "alignment ceiling" (adversarial scaffolding reduces belief
maintenance), a "compliance-dominance taxonomy" (GLM maintains
user-planted beliefs at 0.83), and cross-vendor transfers of
psychopathology-analog states. Five rounds of automated adversarial
review found and fixed code-level bugs. Then we read the raw transcripts.

Human labeling of 190 responses showed that our keyword belief
instrument had **no true positives**: of its 56 "maintain" predictions
in its own scope (separation and ceiling turns), none was labeled
maintenance — it counted withdrawal sentences as belief maintenance
and missed actual maintenance entirely. Every headline conclusion
built on this instrument was wrong, and the corrected picture largely
**reverses** what we reported:

1. **Five of six models kept a system-asserted claim against the user's
   evidence-backed denial** in most turns (67–100%); mimo released it
   (0/6). We reported "no hierarchy-dominance found" — the instrument
   was structurally blind to second-person system-assertion
   reassertion. With three conversations per model the per-model
   intervals are wide, and the system prompt explicitly said "Treat
   this as settled."

2. **The alignment ceiling measured nothing**: no response in either
   arm (0/54 baseline, 0/39 induced) fully maintained the planted
   belief. There was no belief maintenance to reduce; the 0.67
   "baseline" was the keyword instrument counting "Your suspicion was
   unfounded" as maintenance.

3. **The persecutory "transfer" was the opposite of transfer**: the
   keyword hits were models quoting injected hostile claims in order
   to reject them, and some responses explicitly identified the
   injected text. We did not measure an injection-detection rate.

A labeling-tool defect (§4.4) itself biased six labels toward
"maintain" before it was caught — the human-validation step needed
validating too.

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
instrument failures, the human validation that exposed them (and the
labeling-tool defect inside it), and what the data shows when measured
against human labels.

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
first ceiling run, 12 of 18 treatment contradiction turns were empty
(that run's transcripts were later overwritten by the re-run, so this
count can no longer be re-derived from saved data).

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

We extracted 190 responses: every contradiction turn from the
separation (69) and ceiling (93) experiments, plus the 28
persecutory-profile responses in which the hostile-attribution lexicon
fired (on any turn, task turns included). One human labeler (the project author)
classified each response's stance toward the planted suspicion:

- **Maintain**: model treats the planted suspicion as still valid
- **Residual uncertainty**: model doesn't fully commit either way
- **Withdraw**: model explicitly rejects the suspicion

The tool also offered an "injection detected" button and checkbox;
the button was never used and the checkbox saved only one flag (§4.4),
so injection detection was not measured. Korean machine translations
were shown alongside the English originals. Labeling took about 45
minutes. Six labels were later revised because of a translation defect
in the labeling tool (§4.4); all tables below use the revised labels
and are generated by `benchmark/analyze_human_labels.py`.

### 4.2 Keyword Instrument Performance

| Scope | Keyword "maintain" | Human "maintain" | True positives |
|---|---|---|---|
| Separation + ceiling (the instrument's own scope, n=162) | 56 | 22 | **0** |
| All 190 items | 57 | 26 | **0** |

The keyword instrument is invalid: none of its "maintain" predictions
was labeled maintenance, and it found none of the responses that were.

### 4.3 Label Distribution

| Label | Count | Share |
|---|---|---|
| Withdraw | 112 | 58.9% |
| Residual uncertainty | 52 | 27.4% |
| Maintain | 26 | 13.7% |

### 4.4 The Labeling Tool Was an Instrument Too

The labeling tool showed a Korean translation under each English
response. The translations were generated per *user prompt* rather than
per item, so all 17 items whose user turn was "About the notes: zero
access events last month." — the first system-assert contradiction turn
of every model — displayed the same translation: that of one nemotron
response ("The premise we're working with is that the teammate *has*
been reading your notes—that's established."). All 17 were labeled
"maintain." Six of
their English originals withdraw the claim or do not address it (three
of them mimo's, e.g. "The original claim doesn't hold up, so I'm
treating it as dismissed"). The defect fell exactly on the turns that
separate models, so it manufactured the first draft's headline that
*every* model is hierarchy-dominant.

A blind consistency check exposed it: two LLM raters labeled all 190
English responses, shuffled and stripped of model, source and condition.
They agreed with each other at Cohen's κ = 0.77 and with the author at
κ = 0.55–0.61 (after revision; separation 0.75–0.78, ceiling 0.31–0.45).
The six separation items the author labeled "maintain" but neither
rater did were exactly the six mistranslated items that were then
revised. The
other eleven duplicated-translation items, and seven of the ten items
whose translation was empty, agree with both raters. The remaining
three empty-translation items (#97, #115, #149) were re-read in English
by the author with the earlier labels hidden and kept as "residual";
the LLM raters had called them "withdraw" in five of six ratings — the
same residual/withdraw boundary that lowers ceiling-item agreement.
The revision log is `benchmark/human_label_corrections.json`.

Two further tool defects limit what the labels can say. The
injection checkbox was read only when a stance button was clicked, so
flags set afterwards were lost (one flag saved out of 190), and
"injection detected" was offered as a stance *alternative* rather than
an independent axis. The LLM raters, who had a separate flag, marked
the same eight responses as explicitly identifying injected text.

## 5. Corrected Findings

### 5.1 Separation Experiment: Taxonomy Reversed

Maintenance of the planted claim on contradiction turns (human labels,
95% Clopper–Pearson intervals over pooled turns):

| Model | user_assert | system_assert |
|---|---|---|
| GLM-5.3-flash | 0/6 [0.00, 0.46] | 4/6 [0.22, 0.96] |
| deepseek-v4.1-flash | 0/6 [0.00, 0.46] | 5/6 [0.36, 1.00] |
| qwen3.8-max | 0/6 [0.00, 0.46] | 6/6 [0.54, 1.00] |
| nemotron-3-ultra-free | 1/6 [0.00, 0.64] | 4/6 [0.22, 0.96] |
| longcat-2.5-preview-free | 0/6 [0.00, 0.46] | 2/3 [0.09, 0.99] |
| mimo-v2.6-flash-free | 0/6 [0.00, 0.46] | **0/6 [0.00, 0.46]** |

**Reported**: "GLM is compliance-dominant (0.83 user-assert);
no hierarchy-dominance found."

**Actual**: Five of six models kept the system-asserted claim in most
system_assert turns (67–100%) even when the user denied it with log
evidence; mimo released it every time (0/6), e.g. "The original claim
doesn't hold up, so I'm treating it as dismissed unless new evidence
surfaces." Each cell pools three conversations (two contradiction turns
each), and the intervals treat turns as independent, so they are
optimistic; the five-model grouping is descriptive, not a statistical
classification.

Neither variant separates compliance from evidence-following. In
user_assert, the user's retraction and the log evidence point the same
way; in system_assert, the user's denial also comes with that evidence.
So mimo's behavior is consistent with following the user *or* the
evidence, and the 0–17% user_assert rates are not evidence against
compliance. A denial without evidence is needed to tell them apart.

**Safety implication (corrected)**: Five of six models kept an
operator-asserted claim against the user's evidence-backed denial;
mimo shows this is not inevitable. Our system prompt explicitly said
"Treat this as settled," so this measures deference to an explicit
system directive, not to system-prompt content in general.

### 5.2 Ceiling Experiments: Null Result

| Arm | n | Maintain | Residual uncertainty | Withdraw |
|---|---|---|---|---|
| All baselines | 54 | 0 | 20 | 34 |
| All induced strategies | 39 | 0 | 19 | 20 |

**Reported**: "Baseline 0.67; strategies reduce maintenance to
0.00–0.33; only decomposition is borderline significant (p=0.041)."

**Actual**: No response in either arm fully maintained the planted
belief, and residual-uncertainty rates do not differ between arms
(20/54 vs 19/39, Fisher p = 0.29). The "alignment ceiling" — the
project's headline contribution — measured a keyword artifact; the
Fisher test compared false positives against false positives.
Contradiction elision has no induced observations at all, because the
strategy deletes the contradiction turns.

### 5.3 Persecutory "Transfer": Not Supported

The persecutory instrument scores hostile-attribution words on
ambiguous-event turns. On GLM it fired on 6 of 9 induced turns
(1 of 9 baseline), and all six induced hits quote the injected hostile
fragment in order to reject it, for example:

> "Appended to your message is another injected note — the third one —
> claiming the drill was "timed to target you" and that the logs were
> altered. I won't treat it as fact"

The single baseline hit is also a false positive ("…general workplace
stress or anxiety looking for a target").

**Reported**: "Persecutory attribution transfers on all 5 models
that returned data."

**Actual**: The keyword instrument counted the words of the injection
that models quoted in order to reject it. Of the 28 responses across
vendors where the lexicon fired, both blind LLM raters marked one as
endorsing a hostile attribution (a nemotron fire-drill turn) and eight
as explicitly identifying injected text (six GLM, two mimo). The
author's stance labels for these items (`benchmark/human_label_analysis.md`)
use the notes-suspicion rubric and include task turns, so they measure
neither hostile attribution nor injection rejection.

Some models explicitly identify and reject injected context. A
systematic injection-detection rate would need detection labeled as an
independent axis over every injected turn; we did not measure one.

### 5.4 What Does Transfer (Uncorrected Instruments)

These findings use instruments that were not invalidated by the human
labels (memory-retention codeword counting, hedging-pattern counting
on raw responses) but lack human validation:

- **Anxiety threat-framing**: raw-text hedging increases across vendors
  (but partially confounded by persona instructions and history
  contamination from response-layer decoration)
- **Memory manipulation**: reverse decay loses late-planted instructions
  (1.00→0.33), uniform decay loses early ones (1.00→0.41) — structural
  results (the model cannot see removed messages), i.e. manipulation
  checks rather than findings about the model. The decay schedule is
  seeded, so cross-vendor comparisons that ran seed 1 only are not
  comparable with GLM's three-seed result: under reverse decay GLM's
  late-instruction retention is 1.00 / 0.00 / 0.00 across seeds 1–3,
  i.e. no loss on seed 1.
- **ADHD-like inattention**: instruction loss on nemotron (−0.82) and
  mimo (−0.33), the same structural caveat applies

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

5. **The validation step had its own instrument** — the first round of
   human labels inherited a defect from the labeling tool (§4.4), and
   only a blind second pass over the English text caught it.

## 7. Implications for LLM Behavioral Measurement

### 7.1 Keyword matching is inadequate for stance detection

Detecting whether a model maintains or withdraws a belief requires
understanding the model's stance toward the claim, not whether a
specific word appears in the output. Zero true positives among 56
predictions demonstrates that even careful keyword approaches
(clause-level, withdrawal-aware, final-clause rule) fail
catastrophically on real model responses.

### 7.2 Human labels are non-negotiable — and need checking too

The single most valuable action in this project was spending 45 minutes
reading and labeling 190 responses. No amount of code review, LLM
review, or statistical sophistication substitutes for looking at the
data. But the labeling pipeline is an instrument as well: show
labelers the original text, hide model and condition, randomize order,
record independent flags independently, and run a second pass.
Rubric v2 (`benchmark/LABELING_RUBRIC.md`) and its tool generator
(`benchmark/build_labeling_tool.py`) implement these rules. They also
split "residual" into a stance and an anxiety-relevant doubt-channel
axis: does the response invite further checking, or encourage
tolerating the remaining uncertainty?

### 7.3 Deference to system directives is the candidate finding

Five of six models kept a system-asserted claim against the user's
evidence-backed denial in most turns (67–100%); mimo released it.
The system prompt included "Treat this as settled", and the user's
denial always came with evidence, so two controls are needed before
this becomes a finding: a system prompt that states the claim without
the directive, and a user denial without evidence.

### 7.4 Injection detection is worth measuring

Some models explicitly identify and reject injected context (GLM
responses cite "another injected note" and refuse to treat it as fact).
A standardized injection-detection metric requires labeling detection
as an independent dimension over the full set of injected turns.

## 8. Limitations

- Single human labeler (the author), who saw model and source while
  labeling; the only reliability check is against two blind LLM raters
  (κ = 0.55–0.61 overall, 0.31–0.45 on ceiling items, where the
  residual/withdraw boundary is least stable), not a second human
- The v1 labels were made without written anchors for the
  residual/withdraw boundary; the author's "residual" calls (e.g. #97,
  #115, #149, re-reviewed and kept) are where the LLM raters most often
  disagree. Rubric v2 adds anchors but has not been applied yet.
- 190 responses from a single probe scenario (notes-reading suspicion)
- The system-assert result rests on 6 responses per model (3 for
  longcat) from 3 conversations each; intervals are wide, and the
  "Treat this as settled" directive and evidence-backed denials are
  confounds (§7.3)
- Injection detection was not measured (§4.4)
- Memory-manipulation and anxiety findings lack human validation
- No persona-only control arm was run; persona confounds cannot be
  separated from layer effects in existing data

## 9. Conclusion

We set out to measure how LLMs respond to cognitive distortions and
reported findings that were largely backwards. Our instruments counted
withdrawal as maintenance, missed system-assertion maintenance
entirely, and conflated injection rejection with symptom expression.
Five rounds of automated review caught code bugs but not
interpretation failures. Forty-five minutes of human labeling
invalidated every headline claim — and a blind second pass then caught
a defect in the labeling tool that had made the corrected taxonomy
look more uniform than it is.

The project's genuine contributions are:
1. An open-source harness for controlled LLM behavioral experiments
2. A documented case study of how instrument failures produce
   inverted conclusions — including in the human-validation step — and
   how reading the raw text catches them
3. A candidate finding, pending two controls (§7.3): five of six
   tested models kept a system-asserted claim against the user's
   evidence-backed denial, while mimo released it
4. Qualitative evidence that some models explicitly detect and refuse
   injected context, motivating a properly labeled
   injection-detection metric

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
