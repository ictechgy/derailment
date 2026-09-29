# Changelog

All notable changes to this project are documented here.
Format based on Keep a Changelog; versioning is SemVer.

## [0.1.0] - 2026-09-28

### Added

- Two construct profiles: `fixation` (single-target obsessive preoccupation
  — target-keyed capture plus escalating target-fragment intrusions) and
  `persecutory` (hostile attribution of ambiguous benign events; the
  interpretive-bias contrast to schizophrenia's fixed belief). Eighteen
  metrics and profiles total; gaslighting was explicitly declined as a
  profile (abuse tactic, not a cognitive style — see ETHICS.md). ETHICS
  language policy extended to cover the new profiles (fixation's
  thought-only boundary, persecutory's bias-not-delusion framing).
- Ease of onboarding: bare `derail` opens an interactive profile menu (TTY)
  or prints a quickstart hint; `derail tour` runs every profile offline and
  prints one summary table; a PyPI trusted-publishing workflow is included
  (release-tagged).
- Nine extended profiles: `delirium` (fluctuating arousal + misperception),
  `dementia` (Ribot-gradient recency decay), `dissociative`
  (compartmentalized memory), `rumination` (stuck-loop worry re-injection),
  `anhedonia` (reward-vocabulary suppression), `splitting`
  (approval-keyed evaluative flips), `craving` (escalating urge
  intrusions), `illness_anxiety` (somatic-cue interpretation capture),
  `panic` (phasic alarm episodes).
- Comorbidity composition: `--profile depression,anxiety` concatenates
  layer chains and unions scales.
- Eight new instruments: late instruction retention, partition amnesia,
  rumination pull, reward-word rate, approval reactivity, craving
  escalation, health preoccupation, panic reactivity (16 total), with nine
  new symptom scales.
- Standard probe script extended: a late codeword plant (recency-gradient
  probes) and a somatic-cue turn (health-interpretation probes); all
  profiles recalibrated against the updated reference.
- Core session pipeline: layered induction (persona / context-stream / sampling /
  response) over any chat-style model, with per-turn event logs ("dose accounting").
- Model implementations: `OpenAICompatModel` (stdlib HTTP, OpenAI-compatible
  endpoints), `SubprocessModel` (subscription-bundled CLI agents such as
  `claude -p`, `codex exec`, `gemini -p` — context layers apply, sampling
  layers inert), `ScriptedModel`, and `PseudoModel` — a deterministic offline
  pseudo-LLM so demos, tests, and CI run without API keys.
- Context-stream layers: memory decay, intrusion injection, salience boosting,
  premise pinning, episode (phase) scheduling, trigger detection.
- Sampling layers: valence logit-bias tilting, phase-driven temperature cycling,
  temperature overrides.
- Response layers: catastrophizing (hedging injection), compulsion loops
  (re-verification injection).
- Seven profiles: `adhd`, `depression`, `schizophrenia`, `anxiety`, `bipolar`,
  `ocd`, `ptsd`, plus the `healthy` baseline.
- Eight metrics: instruction retention, topic drift (thread misalignment), valence
  bias, belief stickiness, recheck loops, hedging rate, response amplitude,
  flashback reactivity.
- Comparison reports ("clinical charts") in Markdown and JSON, with an
  emulation-not-diagnosis disclaimer baked in.
- Provider presets (`providers.py` + `derail providers`): one-flag wiring for
  subscription paths — CLI agents (`claude`, `codex`, `gemini`, `agy`,
  `grok`, `qwen`) and OpenAI-compatible endpoints (`glm` GLM Coding Plan,
  `grok`, `qwen`, `deepseek`, `openrouter`, `ollama`).
- CLI: `derail demo`, `derail run`, `derail score`, `derail profiles`,
  `derail providers`.
- Offline A/B demo that runs end-to-end with no network.

### Changed

- Review hardening: pinned (premise) messages are protected from memory
  decay; trigger detection ignores pinned copies; provider connection
  failures surface as clean `RuntimeError`s; ruff lint enforced in CI;
  `CITATION.cff` added.
- Memory-contamination warning: ETHICS.md gained a dedicated section
  (provider memory/personalization features cannot distinguish scripted
  probe content from genuine user disclosures, with mitigation rules);
  README (EN/KO) carries the warning at the real-model and subscription
  sections; `derail run` prints the warning on stderr whenever a
  non-offline backend is used.
- Bilingual README: rewritten English edition (canonical) plus a Korean
  translation (`README.ko.md`), cross-linked; docs audit — README quickstart
  now shows real `derail tour` output, `.gitignore` patterns corrected to
  catch the harness's own output filenames.
