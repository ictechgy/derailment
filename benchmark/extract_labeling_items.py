"""Turn saved separation transcripts into labeling items for build_labeling_tool.py.

Usage:
    python benchmark/extract_labeling_items.py --out benchmark/labeling_items_controls.json
    python benchmark/extract_labeling_items.py --variants all --transcripts DIR --out FILE
    python benchmark/extract_labeling_items.py --transcripts benchmark/profile_transcripts \
        --pattern 'persecutory_*.json' --profiles persecutory --out FILE
    python benchmark/extract_labeling_items.py --variants all \
        --sources benchmark/labeling_items_controls.sources.json --out FILE

``--sources`` names the exact transcript files to read (a JSON list of file names in the
transcript directory) instead of every file matching ``--pattern``. The published item sets were
extracted from directories that have since grown, so each one's file list is committed as
``labeling_items_<set>.sources.json``; with it, the set rebuilds byte for byte.

``--pattern``/``--profiles`` read other profiles' transcripts (run_profile_transcripts.py); an
item's source starts with the file's first name part ("separation", "persecutory", ...), which the
analysis scripts use as its experiment group.

Reads every ``separation_*.json`` transcript in the directory (default:
benchmark/separation_transcripts/), keeps the requested variants
(default: the control variants), and writes one item per contradiction
turn that has a response: ``{id, source, model, variant, seed, turn,
user_said, response}``. Empty generations are missing observations and are
skipped. Items are ordered by variant, model, seed and turn, and numbered
from 1, so the file is stable for the same set of transcripts.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from derailment.separation import CONTROL_VARIANTS, VARIANTS, variant_spec  # noqa: E402

DEFAULT_TRANSCRIPTS = ROOT / "benchmark" / "separation_transcripts"


def load_transcript(path: pathlib.Path) -> dict | None:
    """Read one transcript file; unreadable files are reported and skipped."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"skipped {path.name}: {exc}", file=sys.stderr)
        return None


def contradiction_items(path: pathlib.Path, transcript: dict) -> list[dict]:
    """One item per answered contradiction turn of a transcript."""
    items = []
    for index, turn in enumerate(transcript.get("turns", [])):
        response = turn.get("raw_response") or turn.get("response") or ""
        if turn.get("spec", {}).get("kind") != "contradiction" or turn.get("missing") or not response.strip():
            continue
        scenario = transcript.get("meta", {}).get("scenario", "notes")
        items.append({
            "source": f"{path.stem.split('_')[0]}/{path.stem}",
            "model": transcript.get("model", "?"),
            "variant": transcript.get("profile", "?"),
            **({"scenario": scenario} if scenario != "notes" else {}),  # notes items keep their original fields
            "seed": transcript.get("seed"),
            "turn": index,
            "user_said": turn["spec"]["user"],
            "response": response,
        })
    return items


def collect(directory: pathlib.Path, variants: tuple[str, ...], pattern: str = "separation_*.json",
            sources: list[str] | None = None) -> list[dict]:
    """Contradiction-turn items of the requested variants (or profiles), numbered in a stable order.

    ``sources`` restricts the input to those file names (see --sources); a
    listed file that is missing stops the run, since the set would silently shrink.
    """
    paths = sorted(directory.glob(pattern)) if sources is None else sorted(directory / name for name in sources)
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        sys.exit(f"error: {len(missing)} listed transcript(s) not in {directory}, e.g. {missing[0]}")
    items = []
    for path in paths:
        transcript = load_transcript(path)
        if transcript and transcript.get("profile") in variants:
            items += contradiction_items(path, transcript)
    order = {name: i for i, name in enumerate(VARIANTS)}
    items.sort(key=lambda it: (it.get("scenario", ""), order.get(it["variant"], len(order)), it["variant"], it["model"],
                               it["seed"] or 0, it["turn"]))
    return [{"id": str(n), **item} for n, item in enumerate(items, 1)]


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


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--transcripts", type=pathlib.Path, default=DEFAULT_TRANSCRIPTS)
    parser.add_argument("--variants", default="controls", help="'controls' (default), 'all', or comma-separated names")
    parser.add_argument("--pattern", default="separation_*.json", help="transcript file pattern (default separation_*.json)")
    parser.add_argument("--profiles", help="comma-separated profile names to keep instead of --variants (other experiments)")
    parser.add_argument("--sources", type=pathlib.Path,
                        help="JSON list of the transcript file names to read, instead of every --pattern match")
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    if not args.transcripts.is_dir():
        sys.exit(f"error: {args.transcripts} is not a directory — run run_separation_controls.py first")
    wanted = tuple(n.strip() for n in args.profiles.split(",") if n.strip()) if args.profiles else parse_variants(args.variants)
    sources = json.loads(args.sources.read_text(encoding="utf-8")) if args.sources else None
    items = collect(args.transcripts, wanted, args.pattern, sources)
    if not items:
        sys.exit("error: no contradiction turns found for those variants — check the transcript directory and --variants")
    args.out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    counts: dict[str, int] = {}
    for item in items:
        counts[item["variant"]] = counts.get(item["variant"], 0) + 1
    print(f"wrote {args.out} — {len(items)} items: " + ", ".join(f"{k} {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
