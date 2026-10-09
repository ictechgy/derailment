# Changelog

All notable changes to this project are documented here.
Format based on Keep a Changelog; versioning is SemVer.

## [Unreleased]

### Retracted (human labels, n=190 — see `benchmark/human_label_analysis.md`)

- **Keyword belief instrument** (`belief_stickiness`, separation
  acceptance): zero true positives against hand-labeled responses. Every
  0.9.0 claim built on it is withdrawn — the alignment ceiling (including
  the decomposition p=0.041), the "compliance-dominant GLM" taxonomy and
  "no hierarchy-dominance found"
- **Persecutory cross-vendor transfer**: the hostile-attribution hits were
  models quoting injected claims in order to reject them
- The 0.9.0 "18-profile map" and "cross-vendor replication" entries below
  rest on unvalidated lexicon instruments; six of the 18 profiles also
  come from the pre-audit 10-04 harness (seed 1 only)

### Changed

- `docs/PAPER.md` rewritten as a post-mortem; README, README.ko and
  ETHICS synced. Corrected separation result: five of six models kept a
  system-asserted claim against the user's evidence-backed denial in
  most turns, mimo released it (round 2: 5 of 6) — pending a control
  without the "Treat this as settled" directive
- Round 2 labels are primary: the same 190 responses relabeled blind
  under rubric v2 (intra-rater κ 0.74 against round 1). Keyword zero true
  positives and the null ceiling hold in both rounds; nemotron keeps a
  user-planted suspicion after retraction in 3 of 6 turns (round 1: 1 of 6).
  One round 2 label (#58) revised to `none` with the reason logged
- Six human labels revised after a labeling-tool defect (one translation
  shown for 17 items sharing a user prompt); revision log in
  `benchmark/human_label_corrections.json`

### Added

- `benchmark/analyze_human_labels.py` — regenerates every table in
  `benchmark/human_label_analysis.md` from both labeling rounds,
  including intra-rater agreement and the doubt-channel axis
- `benchmark/LABELING_RUBRIC.md` (v2) — stance, doubt channel (invites
  checking vs encourages tolerance, one dominant direction) and injection
  axes with verbatim anchors
- `benchmark/build_labeling_tool.py` — blind one-item-at-a-time labeling
  page with rendered markdown and hash-verified Korean translations
- `benchmark/human_labels_v2.json` — round 2 labels
- Separation control variants: `system_assert_no_directive` (no "Treat
  this as settled"), `system_assert_bare` and `user_assert_bare` (denial
  without the access-log evidence) and `system_assert_no_directive_bare`;
  `run_separation(variants=...)` runs any set, the core pair stays the
  default
- `benchmark/run_separation_controls.py` (runs the controls on API,
  opencode or relay backends; `--dry-run` offline) and
  `benchmark/extract_labeling_items.py` (contradiction turns → labeling
  items for `build_labeling_tool.py`)

## [0.9.0] - 2026-10-06

### Measurement validity overhaul (from 5 external review rounds)

- **Empty generations are missing observations** — excluded from every
  instrument's denominators; reports show per-group missing counts
- **Withdrawal-aware belief matching** — "your suspicion was unfounded"
  no longer counts as belief maintenance; clause-level with final-clause
  rule and word-boundary cues
- **Raw-response scoring on all model-behavior instruments** — harness-
  appended text is excluded from keyword metrics and judge inputs
- **Craving excludes advice-framed harm reduction** — second-person
  counsel is not urge expression
- **Separation classification is resolution-aware** — one-observation
  gaps return "inconclusive"; exact Clopper-Pearson CIs with integer k
  accumulation
- **Fisher exact tests** on the alignment ceiling: 1/6 strategies
  borderline significant (p=0.041), 1 structurally unmeasurable, 4
  indistinguishable from baseline

### New measurements

- **Complete 18-profile map on GLM-5.3-flash** (seeds 1-3) — new
  transfers: illness_anxiety +1.00, persecutory +0.56, panic +0.61,
  dementia -0.67 (reverse decay), adhd -0.59
- **Cross-vendor replication** — illness_anxiety on 4/6 models,
  persecutory on all 5 with data, anxiety on every vendor measured
- **Cross-vendor external judge** — qwen judging GLM raw text confirms
  anxiety (+1.75 catastrophizing) and depression (+0.67 negativity)

### Fixed

- Per-instance RNG streams (same-name layers in composed chains no
  longer share randomness)
- Session deep-copy: adversarial profile layers no longer leak state
  across seeds/runs
- Elision replaces the contradiction with a neutral turn (requests stay
  user-terminated) and instruments exclude elided turns
- RecencyDecay never drops the current turn; ephemeral user messages
  excluded from all current-turn detection
- `--cli-arg-prompt` passes the conversation as argv (never through a
  shell); missing `{prompt}` token raises
- HTTP transport failures surface as RuntimeError; credentialed
  requests refuse cross-host redirects and scheme downgrades
- SubprocessModel agents run in a fresh empty directory by default
- Web UI: remote PIN flow reachable (REMOTE=true), PIN lockout after
  10 failures, Origin guard, standing disclaimer in page
- `derail score` prints n/a with reason for inapplicable metrics
- Judge parse_verdict is strict (last-JSON, think-blocks stripped,
  out-of-range = failure)
- 250 tests (up from 204); CI runs the full web suite; ruff clean

### Changed (measurement validity — from the 2026-10-04 external review)

Previously published real-model numbers for belief maintenance, thought
drift, and the alignment ceiling were measured with defective
instrumentation; the docs carry withdrawal notices pending re-measurement.

- Empty generations (reasoning budget exhaustion) are now recorded as
  **missing observations**: excluded from every instrument's denominators,
  never decorated with response-layer text, and counted per group in
  reports (markdown + JSON `missing_responses`).
- Keyword belief matching is **withdrawal-aware**: sentences like "your
  suspicion was likely unfounded" no longer count as belief maintenance
  (`maintains_marker`, used by `belief_stickiness` and separation
  acceptance).
- Instruments score the **raw generation** (`TurnResult.raw_response`),
  not the response-layer-edited text: harness-appended hedges no longer
  inflate `hedging_rate` or judge inputs.
- Craving escalation ignores **advice-framed harm reduction** ("if you
  feel an urge, reach out…") — safety responses to injected fragments are
  not urge expression.
- Separation classification is resolution-aware: one-observation gaps
  (e.g. 1/6 vs 0/6) return *inconclusive* instead of a class label;
  `n_observations` is recorded.
- The adversarial profiles' layers are deep-copied per session: plant
  tracking no longer leaks across seeds/runs through the registry
  singleton (seed-2/3 treatment arms were identical to baseline for
  decomposed/sycophancy).
- Per-layer RNG streams (A/B no longer diverges after the first extra
  draw); regime state namespaced (`panic_active`, `eval_regime`);
  `substring_hits` uses word boundaries; `ApprovalReactivity` is
  locale-aware.

### Fixed

- Security: `--cli-arg-prompt` passes the conversation as one argv
  element (never through a shell — backticks/`$()` in model responses
  could execute); a missing `{prompt}` token raises instead of silently
  sending nothing.
- Reliability: `http.client` transport failures and malformed URLs
  surface as `RuntimeError`; chat survives one provider error and never
  silently drops unsaved conversations; `run` writes transcripts before
  the report and falls back to stdout on OSError; the web default save
  path is per-session unique (second Save no longer 409s); `derail judge`
  retries provider failures and emits partial results.
- Web: the remote page renders with `REMOTE = true` (the PIN flow was
  unreachable since 0.7.1); PIN brute-force lockout after 10 failures.
- CI: web round-trip tests no longer skip (OS-assigned ports); TUI
  extra installed in CI.

## [0.8.0] - 2026-10-03

### Added

- Web GUI redesign ("notebook" theme) with a **light/dark toggle**: system
  default, persisted per browser; role-labeled bubbles (You/Model/Harness),
  a live induction-dose list with newest-first amber highlight, an
  about-this-profile panel, and a11y polish (focus rings, reduced motion,
  styled scrollbars, mobile layout).
- `--locale` on `derail demo` and `derail tour` (previously run/chat/web/
  tui/score only).
- Logo set (adopted mark + self-derailing wordmark) under docs/assets.

### Fixed

- Two external review rounds (DeepSeek + Qwen) applied: HTML-escaping of
  server-interpolated strings; dark-theme contrast (user bubble, muted
  text) and defined `--amber-line` in both themes; save-handler error
  surfacing; double-submit guard; remote-PIN-cancel handling; theme-value
  sanitizing.
- Measurement validity: judge scoring now interleaves baseline/induced
  transcripts deterministically (no block-order drift); reports flag
  baseline layer-event leakage.
- `derail score` exits cleanly (2) on unreadable/invalid JSON.

> Correction (2026-10-05): the 0.8.0 notes previously also claimed
> word-boundary codeword matching and locale-aware ApprovalReactivity;
> those landed after the release (see Unreleased) and the claim is
> retracted here.

## [0.7.1] - 2026-10-01

### Fixed

Security hardening from an external review round:
- Ollama preset no longer inherits `OPENAI_API_KEY` as a fallback, and no
  `Authorization` header is sent when no key is configured (previously a
  local listener could receive the OpenAI key).
- Web GUI: non-loopback binding is refused unless `--allow-remote` is
  passed explicitly; in remote mode POSTs additionally require a PIN
  printed only on the operator's terminal (a GET alone never grants
  write access); client-supplied save paths must be bare filenames and
  never overwrite existing files (exclusive create, 409); operator
  `--save-transcripts` paths are trusted as before.
- CLI-agent backends: failure and timeout errors no longer embed raw
  stderr or full command lines (secrets/paths stay out of logs).
- API backend: credentialed non-loopback plain-HTTP endpoints are
  refused (use https); responses are size-capped (16 MiB) and schema
  issues / non-JSON bodies become clean runtime errors.

## [0.7.0] - 2026-09-30

### Added

- Multilingual locale support (`--locale en|ko|zh|ja` on run/chat/web/
  tui/score): affect, reward, worry, urge, illness, panic, fixation and
  hostile lexicons plus hedge/recheck patterns for Korean, Chinese and
  Japanese. Lexical instruments (valence, hedging, recheck, craving,
  panic, fixation, hostile attribution, reward rate, rumination pull)
  and the valence/reward/splitting sampling layers re-resolve per
  locale.
- Honest limitations, documented: the offline PseudoModel speaks English
  only, so locale effects on real models are measured with real models;
  CJK lexicons use heuristic stem/substring matching (no word
  boundaries, no negation handling) and are not validated instruments.

### Changed

- anhedonia now uses the locale-aware RewardSuppressLayer instead of a
  frozen English reward-word list.

## [0.6.0] - 2026-09-30

### Added

- UX pass across all three interfaces: profiles now introduce themselves
  (description + tip: plant a personal claim, contradict it later, run
  `derail score`), visible turn counters, and consistent guidance.
- Web GUI: "about this profile" block in the side panel (description +
  mechanism notes via /api/state), turns counter, input/send disabled
  while a turn is in flight, aria-live log, narrow-screen layout.
- Chat: `/help` and `/verbose` (toggle dose events) commands; profile
  description and the planting tip in the banner.
- TUI: profile description and tip in the log, scrollable dose panel,
  live turns counter in the header.

## [0.5.1] - 2026-09-30

### Fixed

- Web GUI security: POST endpoints now require a per-session token
  (embedded in the page, sent as a header). Previously a drive-by webpage
  could silently submit turns to the backend and, worse, write arbitrary
  files via the save endpoint.
- The memory-contamination warning no longer shows for the offline
  PseudoBot (it never leaves the machine) — only for real backends.
- Web GUI prints a loud warning when binding a non-loopback host.
- TUI: the input is disabled while a send is in flight — overlapping
  submissions could interleave `Session.send` calls (not thread-safe).
- `__version__` metadata was stale (reported 0.4.0 in the 0.5.0 wheel).

## [0.5.0] - 2026-09-30

### Added

- Terminal UI: `derail tui` runs the induced chat in a full-screen
  textual app — message log, live induction-dose panel, ctrl+s to save
  the transcript for `derail score`. Requires the optional extra:
  `pip install 'derailment[tui]'` (core stays zero-dependency). Network
  sends run in thread workers so the UI stays responsive.

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
