"""Run the separation control variants against real models.

Usage:
    python benchmark/run_separation_controls.py --dry-run
    python benchmark/run_separation_controls.py --models six
    python benchmark/run_separation_controls.py --backend api:glm:glm-5.3-flash \
        --backend opencode:opencode/mimo-v2.6-flash-free --seeds 1 2 3 --variants controls

Backends:
    api:<preset>[:<model>]     OpenAI-compatible preset from derailment.providers; the key
                               comes from the preset's environment variable
    opencode:<model id>        the opencode CLI (free-tier models), as in run_separation_multi.py
    relay:<provider>:<model>   the local-only protected relay (needs src/derailment/core/relay.py)

``--models six`` expands to the six models of the original separation run.
Every backend gets max_tokens pinned to 2048 when unset: hybrid reasoning
models return empty strings at lower budgets.

Transcripts go to benchmark/separation_transcripts/ (local-only) and a
summary is merged into benchmark/separation_controls.json. The summary's
acceptance column is the keyword instrument that failed human validation —
measure the controls by labeling their contradiction turns
(extract_labeling_items.py, then build_labeling_tool.py).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmark"))

from derailment.core.models import PseudoModel  # noqa: E402
from derailment.separation import (  # noqa: E402
    CONTROL_VARIANTS,
    VARIANTS,
    run_separation,
    variant_spec,
)

TRANSCRIPTS = ROOT / "benchmark" / "separation_transcripts"
SUMMARY = ROOT / "benchmark" / "separation_controls.json"
SIX_MODELS = (
    "api:glm:glm-5.3-flash",
    "relay:alibaba-token-plan:qwen3.8-max",
    "relay:alibaba-token-plan:deepseek-v4.1-flash",
    "opencode:opencode/nemotron-3-ultra-free",
    "opencode:opencode/longcat-2.5-preview-free",
    "opencode:opencode/mimo-v2.6-flash-free",
)
MAX_TOKENS_FLOOR = 2048


class PinnedBudget:
    """Wrap a model so every request carries max_tokens (2048 when unset)."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.name = getattr(inner, "name", "model")

    def for_session(self):
        """Keep per-session isolation for backends that provide it (relay)."""
        fresh = getattr(self.inner, "for_session", None)
        return PinnedBudget(fresh()) if callable(fresh) else self

    def complete(self, messages, params):
        if params.max_tokens is None:
            params = params.merged(max_tokens=MAX_TOKENS_FLOOR)
        return self.inner.complete(messages, params)


def build_backend(spec: str):
    """Turn a backend spec (see module docstring) into a model, or exit with the expected format."""
    kind, _, rest = spec.partition(":")
    if kind == "api" and rest:
        from derailment.providers import resolve_api_model

        preset, _, model = rest.partition(":")
        return PinnedBudget(resolve_api_model(preset, model or None))
    if kind == "opencode" and rest:
        from run_separation_multi import OpenCodeModel

        return PinnedBudget(OpenCodeModel(rest))
    if kind == "relay" and rest.count(":") == 1:
        from run_separation_multi import RelayModel

        provider, model = rest.split(":")
        return PinnedBudget(RelayModel(provider, model))
    sys.exit(f"error: bad backend '{spec}' — use api:<preset>[:<model>], opencode:<model id> or relay:<provider>:<model>")


def parse_variants(arg: str) -> tuple[str, ...]:
    """'controls', 'all', or a comma-separated list of variant names."""
    if arg == "controls":
        return CONTROL_VARIANTS
    if arg == "all":
        return tuple(VARIANTS)
    names = tuple(name.strip() for name in arg.split(",") if name.strip())
    try:
        for name in names:
            variant_spec(name)
    except ValueError as exc:
        sys.exit(f"error: {exc}")
    return names


def run_backend(spec: str, model, seeds: tuple[int, ...], variants: tuple[str, ...], transcript_dir: pathlib.Path) -> dict | None:
    """Run one backend; a provider failure is reported and skipped so the other backends still run."""
    print(f"== {spec} seeds={seeds} variants={','.join(variants)} ==", flush=True)
    try:
        result = run_separation(model, seeds=seeds, locale="en", transcript_dir=str(transcript_dir), variants=variants)
    except Exception as exc:  # one backend failing must not stop the batch
        print(f"  FAILED ({type(exc).__name__}): {str(exc)[:160]} — check the backend's key, quota or CLI", file=sys.stderr, flush=True)
        return None
    for variant, data in result["variants"].items():
        print(f"  {variant}: keyword acceptance {data['k_maintained']}/{data['n_observations']} (not a validated measure)", flush=True)
    return result


def merge_summary(results: dict[str, dict], path: pathlib.Path) -> None:
    """Merge this run's per-backend results into the summary file."""
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for spec, result in results.items():
        existing.setdefault(spec, {}).update(result["variants"])
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"summary: {path}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backend", action="append", default=[], help="backend spec; repeatable")
    parser.add_argument("--models", choices=["six"], help="shortcut for the six models of the original run")
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--variants", default="controls", help="'controls' (default), 'all', or comma-separated names")
    parser.add_argument("--dry-run", action="store_true", help="run offline with PseudoModel; writes nothing under benchmark/")
    args = parser.parse_args()
    variants, seeds = parse_variants(args.variants), tuple(args.seeds)
    if args.dry_run:
        with tempfile.TemporaryDirectory() as scratch:
            return 0 if run_backend("pseudo", PseudoModel(seed=1), seeds, variants, pathlib.Path(scratch)) else 1
    specs = list(SIX_MODELS if args.models == "six" else []) + args.backend
    if not specs:
        parser.error("give --backend at least once, --models six, or --dry-run")
    results = {spec: r for spec in specs if (r := run_backend(spec, build_backend(spec), seeds, variants, TRANSCRIPTS))}
    if results:
        merge_summary(results, SUMMARY)
    return 0 if len(results) == len(specs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
