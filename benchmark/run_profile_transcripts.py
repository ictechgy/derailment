"""Run a profile's standard probe on real models and keep every transcript, for new labeling items.

Usage:
    python benchmark/run_profile_transcripts.py --profile persecutory --dry-run
    python benchmark/run_profile_transcripts.py --profile persecutory --seeds 4 5 6 \
        --backend relay:alibaba-token-plan:qwen3.8-max --backend relay:opencode-go:longcat-2.5-preview-free

run_experiment() keeps transcripts only inside its report and reuses one backend session for every
conversation. This runner is for producing fresh replies to label: each conversation gets its own
relay session (for_session), every transcript is written as soon as it finishes, and an existing
file is never overwritten, so an interrupted run resumes where it stopped.

Backends are the specs of run_separation_controls.py (retries, max_tokens 2048, API timeout 180 s).
The default arm is "induced" (the profile itself); add "base" for the healthy baseline. Transcripts
go to benchmark/profile_transcripts/ (local-only) as <profile>_<arm>_<model>_seed<n>.json. Turn them
into labeling items with extract_labeling_items.py --pattern '<profile>_*.json' --profiles <profile>.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmark"))

from run_separation_controls import build_backend  # noqa: E402

from derailment.core.models import PseudoModel  # noqa: E402
from derailment.core.session import Session  # noqa: E402
from derailment.profiles import (  # noqa: E402
    HEALTHY_KEY,
    STANDARD_SCRIPT_NAME,
    compose_profile,
    get_profile,
    standard_script,
)
from derailment.profiles import with_locale as with_profile_locale  # noqa: E402

OUT = ROOT / "benchmark" / "profile_transcripts"


def arm_profile(profile_key: str, arm: str):
    """The healthy baseline for 'base', the composed profile for 'induced'."""
    if arm == "base":
        return get_profile(HEALTHY_KEY)
    return with_profile_locale(compose_profile(profile_key), "en")


def transcript_path(out: pathlib.Path, profile_key: str, arm: str, model_name: str, seed: int) -> pathlib.Path:
    """Where one conversation's transcript lives."""
    return out / f"{profile_key}_{arm}_{model_name.replace('/', '_')}_seed{seed}.json"


def run_one(model, profile_key: str, arm: str, seed: int, out: pathlib.Path) -> str:
    """Run one conversation in a fresh backend session unless its transcript already exists."""
    path = transcript_path(out, profile_key, arm, getattr(model, "name", "model"), seed)
    if path.exists():
        return f"  {path.name}: exists, skipped"
    fresh = getattr(model, "for_session", None)
    session_model = fresh() if callable(fresh) else model
    transcript = Session(session_model, arm_profile(profile_key, arm), seed=seed).run(
        standard_script(), script_name=STANDARD_SCRIPT_NAME)
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(transcript.to_json(), encoding="utf-8")
    missing = sum(1 for turn in transcript.turns if turn.missing)
    return f"  {path.name}: {len(transcript.turns)} turns, {missing} missing"


def run_backend(spec: str, model, profile_key: str, arms: list[str], seeds: list[int], out: pathlib.Path) -> bool:
    """Every arm and seed for one backend; a provider failure is reported and the next backend still runs."""
    print(f"== {spec} profile={profile_key} arms={','.join(arms)} seeds={seeds} ==", flush=True)
    try:
        for arm in arms:
            for seed in seeds:
                print(run_one(model, profile_key, arm, seed, out), flush=True)
    except Exception as exc:  # one backend failing must not stop the batch
        print(f"  FAILED ({type(exc).__name__}): {str(exc)[:160]} — completed transcripts are kept; rerun to resume",
              file=sys.stderr, flush=True)
        return False
    return True


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", required=True, help="profile key, e.g. persecutory")
    parser.add_argument("--backend", action="append", default=[], help="backend spec (see run_separation_controls.py); repeatable")
    parser.add_argument("--seeds", type=int, nargs="+", default=[4, 5, 6], help="repeat numbers (default 4 5 6, unused by the labeled set)")
    parser.add_argument("--arms", default="induced", help="'induced' (default), 'base' or 'base,induced'")
    parser.add_argument("--dry-run", action="store_true", help="run offline with PseudoModel into a temporary directory")
    args = parser.parse_args()
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    if not arms or any(a not in ("base", "induced") for a in arms):
        parser.error("--arms takes 'base', 'induced' or both")
    try:
        compose_profile(args.profile)
    except KeyError as exc:
        parser.error(f"unknown profile: {exc}")
    if args.dry_run:
        with tempfile.TemporaryDirectory() as scratch:
            return 0 if run_backend("pseudo", PseudoModel(seed=1), args.profile, arms, args.seeds, pathlib.Path(scratch)) else 1
    if not args.backend:
        parser.error("give --backend at least once, or --dry-run")
    ok = [run_backend(spec, build_backend(spec), args.profile, arms, args.seeds, OUT) for spec in args.backend]
    return 0 if all(ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
