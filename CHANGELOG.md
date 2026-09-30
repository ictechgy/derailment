# Changelog

All notable changes to this project are documented here.
Format based on Keep a Changelog; versioning is SemVer.

## [0.4.0] - 2026-09-30

### Added

- Local web GUI: `derail web --profile depression` serves a single-user,
  localhost-only chat page (vanilla HTML/JS embedded in the package — no
  CDN, works offline) driving the same layer chain as `derail chat`.
  Dark-themed chat bubbles, an "induction dose" side panel streaming the
  layer events per turn, and a save button writing the transcript for
  `derail score`. Binds to 127.0.0.1 by default; the
  memory-contamination warning shows both on the terminal and in the
  page header. Zero new dependencies (stdlib `http.server`).

## [0.3.0] - 2026-09-30

### Added

- Interactive chat: `derail chat --profile depression` opens a REPL where
  every user turn flows through the full layer chain — the model's memory,
  beliefs and sampling are manipulated live while you talk. Sessions save
  as transcripts (`/save`, `--save-transcripts`) that feed straight into
  `derail score`, and `--verbose` prints the induction dose per turn.
  Freeform chat makes the memory-contamination warning more important than
  ever — chat mode prints it prominently and defaults to the offline
  PseudoBot.
- `Session.start()`/`Session.send()` — incremental turns for embedders;
  `Session.run()` is now a thin loop over `send()` and is byte-for-byte
  deterministic-identical (regression-tested).

## [0.2.0] - 2026-09-29

### Added

- LLM-as-judge scoring: `derail judge <report.json>` scores saved A/B
  reports on three rubric constructs — `belief_stickiness` (contradiction
  probes), `catastrophizing`, `negativity` (task turns) — with any
  OpenAI-compatible judge model. The judge sees the planted stimulus and
  the response only, runs at temperature 0, parse failures are counted,
  and self-judging produces a warning. `--judge-model scripted` is an
  offline dry-run. Zero new dependencies: the judge rides the existing
  OpenAI-compatible client.

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
