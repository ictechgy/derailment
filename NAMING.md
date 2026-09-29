# Naming Review — `derailment`

Naming grammar used in this workspace: **a metaphorical word with an exact functional
correspondence** (cf. `joinery` = skill linker, `sceneforge` = scene generator).
Review date: 2026-09-28.

## The word

**derailment** — two readings, both load-bearing:

1. *Clinical:* "derailment" (also called loosening of associations) is the formal
   psychopathology term for thought disorder in which speech slips off the
   conversational rails between clauses — a Bleulerian fundamental symptom.
2. *Functional:* the harness derails cognition. Not only association: it derails
   **attention** (memory decay), **salience** (aberrant boosts), **valence**
   (logit-bias tilting) and **arousal** (temperature cycling). "Derail" is the
   verb the CLI performs.

The package is `derailment`; the CLI entry point is `derail`.

## Candidate comparison

| Candidate | Fit | Rejected because |
|---|---|---|
| **derailment** | clinical term **and** the harness's own verb; generalizes across profiles (attention/valence/salience/arousal all derail) | — adopted |
| aberrant | direct reference to aberrant salience (Kapur 2003), the leading psychosis theory; attention = salience in transformers | "aberrant" is a common adjective across millions of papers → academically unsearchable; White Wolf RPG *Aberrant* prior |
| salience | the cleanest single-variable correspondence (attention ↔ salience) | existing tech brands (Salience Labs et al.); heavy prior use in attention literature |
| asymptote | bakes in the ethical frame: approaches pathology without being pathology | collides with the Asymptote vector-graphics language in the adjacent academic space |
| fugue | dissociative fugue + musical fugue (overlapping voices) — elegant | Gruntwork's Fugue and other dev-tool priors |
| unhinged | colloquial, memorable | stigmatizing register; Character.AI already ships an "Unhinged" mode (folk precedent, not a clinical one) |
| pseudosis | coined "fake disease" — the ethical frame as a word | invented word: low recognition, pronunciation burden |
| munchausen | by-proxy = inducing illness in another, literally what a harness does | naming a tool after a disorder associated with abuse is stigmatizing; non-starter |

## Conflict check (2026-09-28)

- **PyPI:** `https://pypi.org/pypi/derailment/json` → **404, package name free**.
- **GitHub / web search:** no known software tool or CLI named "Derail"/"Derailment".
  Closest hit is academic reuse of the common noun: *Understanding and Predicting
  Derailment in Toxic Conversations on GitHub* (arXiv:2503.02191) — same word,
  different domain (conversation moderation); confusion risk low.
- **Known noise:** train-derailment news dominates generic web search; software-scoped
  searches are clean. Acceptable.
- **CLI `derail`:** *Derail Valley* (VR train game) exists but is a different category;
  no CLI tool named `derail` found.

## Verdict

Adopted: **derailment** (package) / **derail** (CLI). Rejection reasons for all
alternatives recorded above so the decision is auditable.

## Second review (2026-09-29) — stress-testing the adoption

The project grew from 7 profiles (psychosis-centric) to 16 (attention,
salience, valence, arousal, memory, craving, dissociation, panic). Question:
does the name still fit, and did the broader scope surface a better word?
Re-ran candidate generation; checked conflicts with live PyPI lookups
(2026-09-29).

| Candidate | Fit | Conflict check | Verdict |
|---|---|---|---|
| **derailment** (incumbent) | clinical term (thought derailment) **and** the harness verb; generalized in profile notes as attention/valence/arousal/salience "derailment" | PyPI 404 again (still free); no software tool named Derail | **kept** |
| titrate | dose–response is exactly what reports measure | PyPI **taken** (`titrate` 0.5.1, dark-matter statistics, 2025) | rejected |
| perturb | THE scientific word for what layers do (perturbation studies) | PyPI **taken** (`perturb` 0.0.2, agent planning ledger); also collides with adversarial *input* perturbation literature | rejected |
| lesion | neuroscience "virtual lesion" framing is apt | PyPI free, but GitHub has a **BrainLesion** org and heavy lesion-segmentation tooling in the *same clinical-AI audience space*; damage-framed tone | rejected |
| detune | gentle, deliberate mistuning | PyPI free; but reads as anti-*fine-tuning* in ML contexts + audio-plugin association | rejected |
| dysreg | the exact umbrella ("dysregulation" covers all 16 profiles) | PyPI free; but a clipped jargon syllable, weak as a brand, and paper-polluted like *aberrant* | rejected |
| unmoor | poetic "release from anchor" | PyPI free; correspondence vaguer than derailment | rejected |

Scope-growth test passed: the umbrella concern (derailment = thought disorder
only) is answered inside the product itself — profile notes already speak of
"attention derailment", "valence derailment", "arousal derailment", and the
CLI verb is the operation performed on every layer. No contender beat it on
fit *and* availability simultaneously.

**Verdict: unchanged — `derailment` / `derail`.** This second round is
recorded so the reconsideration itself is auditable.
