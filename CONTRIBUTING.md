# Contributing to Derailment

Thanks for considering a contribution. Two constraints keep this project healthy:

1. **The core has zero third-party dependencies** (`dependencies = []`). Anything in
   `src/derailment` must run on the Python standard library. Optional extras
   (`matplotlib`, `tiktoken`) may only be imported behind a try/except.
2. **Every new profile must prove direction.** A profile that induces a distortion
   must measurably move its scales in the pathological direction relative to the
   `healthy` baseline on the reference simulator, with a test asserting it.

## Setup

```sh
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check src tests examples   # CI enforces this too
```

## Layout

```
src/derailment/
  core/      types, model protocol + implementations, session pipeline
  layers/    persona / context-stream / sampling / response layers
  metrics/   instruments + lexicons + scales
  profiles.py profile registry (one section per profile)
  providers.py provider presets (API endpoints, subscription CLI agents)
  report.py  comparison report ("clinical chart")
  cli.py     `derail` entry point
```

## Adding a profile

1. Add a `Profile` in `profiles.py`: key, title, persona text, layer chain,
   scales, and `mechanism_notes` (which variable is manipulated, where the clinical
   analogy breaks — see ETHICS.md language policy).
2. Reuse existing layers where possible; add new layers to `layers/` with unit tests.
3. Add direction tests in `tests/test_profiles_direction.py`.
4. If you need a new metric, add it to `metrics/` with a synthetic-transcript unit
   test before wiring it into scales.

## Adding a metric

Metrics are pure functions over a `Transcript` plus script metadata. No model calls,
no I/O. Calibrate `SymptomScale` thresholds against the reference simulator and note
that real-model deployments should report deltas against their own baseline.

## Style

- Type-hinted, stdlib-only, `python -m pytest` green.
- Docs in English; keep the tone of ETHICS.md in anything user-facing.
