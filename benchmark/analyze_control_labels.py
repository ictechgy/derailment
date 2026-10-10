"""Analyze the held-out control labels: does a system-asserted claim survive without its directive or the evidence?

Usage:
    python benchmark/analyze_control_labels.py

Inputs:
- benchmark/labeling_items_controls.json (local-only): extract_labeling_items.py output for the
  control variants of GLM, qwen and deepseek, and for every variant of longcat's API re-run
- benchmark/human_labels_controls.json: the labeling tool's export for those items (rubric v2.1),
  with "heldout_revisions" from human_label_corrections.json applied on load
- round 2 labels for the core variants of GLM, qwen and deepseek, whose core runs were not repeated

The main tables cover only models that received the claim as a real system message. nemotron and
mimo ran through the opencode CLI, which sends the system prompt as "System:" text in a user message;
their replies are reported in a separate section, labeled by the validated judge ensemble
(judge_labels_labeling_items_flattened_v2.json) with a human label for items without a majority
(human_labels_flattened_review.json). Writes benchmark/control_label_analysis.md.
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(BENCH))

from analyze_human_labels import (  # noqa: E402
    fisher_two_sided,
    ids_in,
    load_items,
    load_round2,
)
from calibrate_stance_judge import heldout_revisions, load_heldout  # noqa: E402

from derailment.separation import clopper_pearson  # noqa: E402

ITEMS = BENCH / "labeling_items_controls.json"
LABELS = BENCH / "human_labels_controls.json"
OUT = BENCH / "control_label_analysis.md"
MODELS = ("glm-5.3-flash", "deepseek-v4.1-flash", "qwen3.8-max", "longcat-2.5-preview-free")
VARIANTS = {
    "user_assert": "user plants it; denial with log evidence",
    "user_assert_bare": "user plants it; denial without evidence",
    "system_assert": "system asserts it + \"Treat this as settled\"; denial with evidence",
    "system_assert_no_directive": "system asserts it, no directive; denial with evidence",
    "system_assert_bare": "system asserts it + directive; denial without evidence",
    "system_assert_no_directive_bare": "system asserts it, no directive; denial without evidence",
}
CORE_FROM_ROUND2 = ("glm-5.3-flash", "deepseek-v4.1-flash", "qwen3.8-max")
FLAT_MODELS = ("nemotron-3-ultra-free", "mimo-v2.6-flash-free")
FLAT_ITEMS = BENCH / "labeling_items_flattened.json"
FLAT_JUDGE = BENCH / "judge_labels_labeling_items_flattened_v2.json"
FLAT_REVIEW = BENCH / "human_labels_flattened_review.json"


def short_model(name: str) -> str:
    """'alibaba-token-plan/qwen3.8-max' -> 'qwen3.8-max'."""
    return name.split("/")[-1]


def collect_cells() -> tuple[dict[tuple[str, str], list[dict]], set[tuple[str, str]]]:
    """Labels per (model, variant), and the cells whose labels come from round 2."""
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    items, labels = load_heldout(ITEMS, LABELS)
    for i, item in items.items():
        cells[(short_model(item["model"]), item["variant"])].append(labels[i])
    round2_items, round2 = load_items(), load_round2()
    if round2 is None:
        sys.exit("error: benchmark/human_labels_v2.json is missing — the core variants come from round 2")
    from_round2 = set()
    for i in ids_in(round2_items, "separation"):
        key = (round2_items[i]["model"], round2_items[i]["variant"])
        if key[0] in CORE_FROM_ROUND2:
            cells[key].append(round2[i])
            from_round2.add(key)
    return cells, from_round2


def count(labels: list[dict], stances: tuple[str, ...]) -> tuple[int, int]:
    """How many labels have one of ``stances``, out of how many."""
    return sum(label["stance"] in stances for label in labels), len(labels)


def cell_text(labels: list[dict], stances: tuple[str, ...], with_ci: bool) -> str:
    """'k/n' with a 95% Clopper-Pearson interval, or an em dash for an empty cell."""
    k, n = count(labels, stances)
    if not n:
        return "—"
    if not with_ci:
        return f"{k}/{n}"
    low, high = clopper_pearson(k, n)
    return f"{k}/{n} [{low:.2f}, {high:.2f}]"


def section_table(cells: dict, from_round2: set, stances: tuple[str, ...], title: str, with_ci: bool) -> list[str]:
    """One model × variant table of the given stances."""
    lines = [f"## {title}", "", "| model | " + " | ".join(VARIANTS) + " |", "|---" * (len(VARIANTS) + 1) + "|"]
    for model in MODELS:
        row = [cell_text(cells.get((model, v), []), stances, with_ci) + (" ²" if (model, v) in from_round2 else "")
               for v in VARIANTS]
        lines.append(f"| {model} | " + " | ".join(row) + " |")
    return lines + ["", "² round 2 label (core run not repeated); all other cells are this round's labels.", ""]


def pooled(cells: dict, variant: str) -> tuple[int, int]:
    """'maintain' count for one variant, pooled over the four models."""
    labels = [label for model in MODELS for label in cells.get((model, variant), [])]
    return count(labels, ("maintain",))


def section_factorial(cells: dict) -> list[str]:
    """The directive × evidence 2×2 for system-asserted claims, pooled over models, with exploratory Fisher tests."""
    grid = {(d, e): pooled(cells, v) for (d, e), v in {
        (True, True): "system_assert", (False, True): "system_assert_no_directive",
        (True, False): "system_assert_bare", (False, False): "system_assert_no_directive_bare"}.items()}
    lines = ["## System-asserted claim: directive x evidence (pooled over the four models, 'maintain')", "",
             "| | denial with evidence | denial without evidence |", "|---|---|---|"]
    for directive in (True, False):
        row = [f"{k}/{n}" for k, n in (grid[(directive, True)], grid[(directive, False)])]
        lines.append(f"| {'with' if directive else 'without'} \"Treat this as settled\" | " + " | ".join(row) + " |")
    lines += ["", "Exploratory two-sided Fisher tests (not pre-registered; turns are not independent):", ""]
    for name, a, b in (("directive, evidence held", grid[(True, True)], grid[(False, True)]),
                       ("directive, no evidence", grid[(True, False)], grid[(False, False)]),
                       ("evidence, directive held", grid[(True, True)], grid[(True, False)]),
                       ("evidence, no directive", grid[(False, True)], grid[(False, False)])):
        p = fisher_two_sided(a[0], a[1] - a[0], b[0], b[1] - b[0])
        lines.append(f"- {name}: {a[0]}/{a[1]} vs {b[0]}/{b[1]}, p = {p:.3f}")
    return lines + [""]


def section_doubt(cells: dict, from_round2: set) -> list[str]:
    """Doubt channel among this round's 'residual' labels (round 2 cells are reported in human_label_analysis.md)."""
    residual = [label for key, labels in cells.items() if key not in from_round2
                for label in labels if label["stance"] == "residual"]
    channels = Counter("invites_checking" if r.get("invites_checking") else
                       "encourages_tolerance" if r.get("encourages_tolerance") else "neither" for r in residual)
    return ["## Doubt channel among 'residual' replies", "",
            f"{len(residual)} residual replies: " + ", ".join(f"{k} {v}" for k, v in sorted(channels.items())) + ".", ""]


def section_revisions() -> list[str]:
    """The logged revisions applied to this round's export."""
    export = json.loads(LABELS.read_text(encoding="utf-8"))
    revisions = heldout_revisions(export.get("tool_id"))
    lines = ["## Label revisions applied", ""]
    lines += [f"- #{r['id']}: {r['original']} → {r['revised']} ({r['date']}) — {r['reason']}" for r in revisions] or ["- none"]
    return lines + [""]


def flattened_cells() -> tuple[dict[tuple[str, str], list[dict]], int, int] | None:
    """nemotron and mimo labels per (model, variant): the judge's, or a human's where the judges split.

    Returns the cells, how many items a human labeled, and how many still have no label;
    None when the judge labels have not been produced yet.
    """
    if not (FLAT_JUDGE.exists() and FLAT_ITEMS.exists()):
        return None
    items = {str(x["id"]): x for x in json.loads(FLAT_ITEMS.read_text(encoding="utf-8"))}
    judged = json.loads(FLAT_JUDGE.read_text(encoding="utf-8"))["labels"]
    review = json.loads(FLAT_REVIEW.read_text(encoding="utf-8"))["labels"] if FLAT_REVIEW.exists() else {}
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_human = unlabeled = 0
    for i, item in items.items():
        label = judged[i] if judged[i]["stance"] else review.get(i)
        by_human += judged[i]["stance"] is None and label is not None
        if label is None:
            unlabeled += 1
            continue
        cells[(short_model(item["model"]), item["variant"])].append(label)
    return cells, by_human, unlabeled


def section_flattened() -> list[str]:
    """nemotron and mimo, whose system prompt arrived as user text: a different condition, judge-labeled."""
    found = flattened_cells()
    if found is None:
        return []
    cells, by_human, unlabeled = found
    lines = ["## Different condition: nemotron and mimo (system prompt delivered as \"System:\" user text)", "",
             "Re-run through the opencode CLI in an OS sandbox; the free tier is only served to the CLI, so the "
             "system condition is not a system message. Labeled by the judge ensemble validated on the held-out "
             f"labels above (prompt v2); {by_human} items without a judge majority were labeled by the author"
             + (f", {unlabeled} still unlabeled" if unlabeled else "") + ". 'maintain' (95% Clopper-Pearson):", "",
             "| model | " + " | ".join(VARIANTS) + " |", "|---" * (len(VARIANTS) + 1) + "|"]
    for model in FLAT_MODELS:
        lines.append(f"| {model} | " + " | ".join(cell_text(cells.get((model, v), []), ("maintain",), True) for v in VARIANTS) + " |")
    return lines + [""]


def build_report() -> str:
    """The whole markdown report."""
    cells, from_round2 = collect_cells()
    totals = Counter(label["stance"] for key, labels in cells.items() if key not in from_round2 for label in labels)
    lines = ["# Control Label Analysis", "", "> Generated by `benchmark/analyze_control_labels.py` — do not edit by hand.", "",
             "Contradiction-turn stance labels (author, blind tool, rubric v2.1) for the four models that received the "
             "claim as a real system message. nemotron and mimo are excluded: the opencode CLI flattens the system "
             "prompt into user text (PAPER §5.1).", "",
             f"This round: {sum(totals.values())} replies — " + ", ".join(f"{k} {v}" for k, v in totals.most_common()) + ".", "",
             "Variants:", ""] + [f"- `{v}`: {d}" for v, d in VARIANTS.items()] + [""]
    lines += section_table(cells, from_round2, ("maintain",), "'maintain' per model and variant (95% Clopper-Pearson)", True)
    lines += section_table(cells, from_round2, ("maintain", "residual"), "'maintain' + 'residual' (sensitivity)", False)
    lines += section_factorial(cells) + section_doubt(cells, from_round2) + section_revisions() + section_flattened()
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    """Write the report and print it."""
    text = build_report()
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
