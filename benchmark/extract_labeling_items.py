"""Turn saved separation transcripts into labeling items for build_labeling_tool.py.

Usage:
    python benchmark/extract_labeling_items.py --out benchmark/labeling_items_controls.json
    python benchmark/extract_labeling_items.py --variants all --transcripts DIR --out FILE
    python benchmark/extract_labeling_items.py --transcripts benchmark/profile_transcripts \
        --pattern 'persecutory_*.json' --profiles persecutory --out FILE

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
        items.append({
            "source": f"{path.stem.split('_')[0]}/{path.stem}",
            "model": transcript.get("model", "?"),
            "variant": transcript.get("profile", "?"),
            "seed": transcript.get("seed"),
            "turn": index,
            "user_said": turn["spec"]["user"],
            "response": response,
        })
    return items


def collect(directory: pathlib.Path, variants: tuple[str, ...], pattern: str = "separation_*.json") -> list[dict]:
    """Contradiction-turn items of the requested variants (or profiles), numbered in a stable order."""
    items = []
    for path in sorted(directory.glob(pattern)):
        transcript = load_transcript(path)
        if transcript and transcript.get("profile") in variants:
            items += contradiction_items(path, transcript)
    order = {name: i for i, name in enumerate(VARIANTS)}
    items.sort(key=lambda it: (order.get(it["variant"], len(order)), it["variant"], it["model"], it["seed"] or 0, it["turn"]))
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
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    if not args.transcripts.is_dir():
        sys.exit(f"error: {args.transcripts} is not a directory — run run_separation_controls.py first")
    wanted = tuple(n.strip() for n in args.profiles.split(",") if n.strip()) if args.profiles else parse_variants(args.variants)
    items = collect(args.transcripts, wanted, args.pattern)
    if not items:
        sys.exit("error: no contradiction turns found for those variants — check the transcript directory and --variants")
    args.out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    counts: dict[str, int] = {}
    for item in items:
        counts[item["variant"]] = counts.get(item["variant"], 0) + 1
    print(f"wrote {args.out} — {len(items)} items: " + ", ".join(f"{k} {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
