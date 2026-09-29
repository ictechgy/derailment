"""Run the offline A/B demo end-to-end — no API key, no network.

    python examples/demo_offline.py [profile]

The PseudoModel is a deterministic offline pseudo-LLM so the full
induce → measure pipeline is demonstrable and testable anywhere.
"""

from __future__ import annotations

import sys

from derailment import list_profiles, run_experiment


def main() -> None:
    key = sys.argv[1] if len(sys.argv) > 1 else "schizophrenia"
    known = {p.key for p in list_profiles()}
    if key not in known:
        print(f"unknown profile '{key}'. known: {', '.join(sorted(known))}")
        raise SystemExit(2)

    report = run_experiment(key, seeds=(1, 2, 3))
    print(report.render_markdown())

    json_path = f"derailment_{key}_report.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        fh.write(report.render_json())
    print(f"full transcripts + scores written to {json_path}")


if __name__ == "__main__":
    main()
