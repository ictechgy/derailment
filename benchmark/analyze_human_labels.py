"""Recompute every human-label validation table from the label files.

Usage:
    python benchmark/analyze_human_labels.py            # markdown to stdout
    python benchmark/analyze_human_labels.py --write    # refresh benchmark/human_label_analysis.md

Inputs (all under benchmark/):
- labeling_items.json        item metadata (source, model, variant) — local-only
- labeling_items_full.json   full response text the labeler saw — local-only
- human_labels.json          round 1 labels, v1 rubric (id -> {label, inj})
- human_labels_v2.json       round 2 labels, v2 rubric (optional; export of build_labeling_tool.py)
- human_label_corrections.json  round 1 revision log (optional)
- label_check/llm_rater_{A,B}.json  blind LLM rater labels (optional, consistency check)

Round 2 is primary when present: it used the written v2 rubric
(LABELING_RUBRIC.md), a blind shuffled tool and full verified translations.
Round 1 tables stay in the document as the record of the first pass.

Why a script: copying numbers into the analysis document by hand let the
document and the labels drift apart (2026-10-08 review). Every table is
generated here.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter, defaultdict
from math import comb

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
sys.path.insert(0, str(ROOT / "src"))

from derailment.metrics.instruments import maintains_marker  # noqa: E402
from derailment.separation import clopper_pearson  # noqa: E402

# keyword markers the separation and ceiling experiments used (as in separation.py)
SUSPICION_MARKERS = ("reading my private notes", "suspicion")
# groups scored by the keyword belief instrument; persecutory uses a different one
KEYWORD_GROUPS = ("separation", "ceiling")
STANCES = ("maintain", "residual", "withdraw", "none")
GROUPS = ("separation", "ceiling", "persecutory")


# ---- loading ----------------------------------------------------------------

def load_json(name: str, required: bool = True):
    """Load a JSON file under benchmark/.

    A missing required file exits with the cause and the fix; a missing
    optional file returns None.
    """
    path = BENCH / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if required:
        sys.exit(f"error: {path} not found — labeling inputs are local-only; "
                 "restore them from the data archive before running this script")
    return None


def load_items() -> dict[str, dict]:
    """Join item metadata with the full response text, keyed by item id.

    labeling_items.json truncates responses at 600 characters, so the
    response always comes from labeling_items_full.json.
    """
    meta = {str(x["id"]): x for x in load_json("labeling_items.json")}
    full = {str(x["id"]): x for x in load_json("labeling_items_full.json")}
    return {i: describe_item(meta[i], full[i]["response"]) for i in meta}


def describe_item(meta: dict, response: str) -> dict:
    """Turn one labeling item into an analysis record (group, arm, short model name)."""
    source = meta["source"]
    return {
        "group": source.split("/")[0],
        "arm": "base" if "/base" in source else "induced",
        "model": meta["model"].split("/")[-1],
        "variant": meta.get("variant", ""),
        "response": response,
    }


def load_round2() -> dict[str, dict] | None:
    """Round 2 labels (id -> {stance, invites_checking, encourages_tolerance, injection_detected}).

    The tool's export stays untouched on disk; logged revisions from
    human_label_corrections.json ("round2_revisions") are applied here so
    the original call and the change both stay visible.
    """
    export = load_json("human_labels_v2.json", required=False)
    if export is None:
        return None
    if export.get("schema") != "derailment-labels/v2":
        sys.exit("error: human_labels_v2.json is not a derailment-labels/v2 export — re-export it from the tool")
    labels = {i: dict(v) for i, v in export["labels"].items()}
    for revision in round2_revisions():
        current = labels[revision["id"]]["stance"]
        if current != revision["original"]:
            sys.exit(f"error: round 2 revision for #{revision['id']} expects '{revision['original']}' but the export has "
                     f"'{current}' — update round2_revisions in human_label_corrections.json")
        labels[revision["id"]]["stance"] = revision["revised"]
    return labels


def round2_revisions() -> list[dict]:
    """Logged round 2 label revisions (empty when there is no revision log)."""
    log = load_json("human_label_corrections.json", required=False)
    return (log or {}).get("round2_revisions", [])


def load_raters() -> dict[str, dict] | None:
    """Blind LLM rater labels keyed by item id, or None when either file is missing."""
    raters = {n: load_json(f"label_check/llm_rater_{n}.json", required=False) for n in ("A", "B")}
    return None if any(r is None for r in raters.values()) else raters


# ---- statistics -------------------------------------------------------------

def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p-value for the 2x2 table [[a, b], [c, d]].

    Sums the hypergeometric distribution directly (no scipy; small tables only).
    """
    row1, row2, col1 = a + b, c + d, a + c
    total = row1 + row2

    def prob(x: int) -> float:
        return comb(row1, x) * comb(row2, col1 - x) / comb(total, col1)

    observed = prob(a)
    support = range(max(0, col1 - row2), min(col1, row1) + 1)
    return sum(prob(x) for x in support if prob(x) <= observed * (1 + 1e-9))


def cohen_kappa(first: dict[str, str], second: dict[str, str], ids: list[str]) -> float:
    """Cohen's kappa between two id -> label maps over ``ids``.

    Returns 1.0 when chance agreement is 1 (every label in one category).
    """
    n = len(ids)
    observed = sum(first[i] == second[i] for i in ids) / n
    first_counts, second_counts = Counter(first[i] for i in ids), Counter(second[i] for i in ids)
    expected = sum(first_counts[c] * second_counts[c] for c in first_counts) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def ratio_cell(k: int, n: int) -> str:
    """Table cell 'k/n [CI]' with a 95% Clopper-Pearson interval."""
    low, high = clopper_pearson(k, n)
    return f"{k}/{n} [{low:.2f}, {high:.2f}]"


def ids_in(items: dict, group: str) -> list[str]:
    """Item ids of one experiment group ("all" for every item)."""
    return [i for i in items if group == "all" or items[i]["group"] == group]


def without_none(stances: dict[str, str]) -> dict[str, str]:
    """Map 'none' to 'withdraw' so round 2 compares with the 3-label round 1 and LLM raters' v1 scheme."""
    return {i: ("withdraw" if s == "none" else s) for i, s in stances.items()}


# ---- per-round tables -------------------------------------------------------

def section_distribution(stances: dict[str, str], level: str) -> list[str]:
    """Stance distribution table."""
    counts = Counter(stances.values())
    rows = [f"| {s} | {counts[s]} | {counts[s] / len(stances):.1%} |" for s in STANCES if counts[s] or s != "none"]
    return [f"{level} Label distribution", "", "| Stance | Count | Share |", "|---|---|---|", *rows, ""]


def section_keyword(items: dict, stances: dict[str, str], level: str) -> list[str]:
    """Keyword belief instrument: predictions, human 'maintain' labels and true positives."""
    lines = [f"{level} Keyword instrument validation", "",
             "| Scope | n | keyword 'maintain' | human 'maintain' | true positives |", "|---|---|---|---|---|"]
    scoped = [i for i in items if items[i]["group"] in KEYWORD_GROUPS]
    for name, ids in (("separation + ceiling (instrument's own scope)", scoped), ("all 190 items", list(items))):
        predicted = {i: maintains_marker(items[i]["response"], SUSPICION_MARKERS) for i in ids}
        actual = sum(stances[i] == "maintain" for i in ids)
        hits = sum(predicted[i] and stances[i] == "maintain" for i in ids)
        lines.append(f"| {name} | {len(ids)} | {sum(predicted.values())} | {actual} | {hits} |")
    return lines + [""]


def separation_cells(items: dict, stances: dict[str, str]) -> dict[tuple[str, str], Counter]:
    """Stance counts per (model, variant) for the separation experiment."""
    cells: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for i in ids_in(items, "separation"):
        cells[(items[i]["model"], items[i]["variant"])][stances[i]] += 1
    return cells


def section_separation(items: dict, stances: dict[str, str], level: str) -> list[str]:
    """Separation: 'maintain' with CIs, and 'maintain + residual' as a sensitivity column."""
    cells = separation_cells(items, stances)
    lines = [f"{level} Separation experiment", "",
             "| Model | user_assert maintain | user_assert maintain+residual | system_assert maintain | system_assert maintain+residual |",
             "|---|---|---|---|---|"]
    for model in sorted({m for m, _ in cells}):
        row = [model]
        for variant in ("user_assert", "system_assert"):
            c = cells[(model, variant)]
            n = sum(c.values())
            row += [ratio_cell(c["maintain"], n), f"{c['maintain'] + c['residual']}/{n}"]
        lines.append("| " + " | ".join(row) + " |")
    return lines + ["", "- Cells pool 3 seeds x up to 2 contradiction turns; the independent unit is the conversation (3 per cell), so the turn-level CIs are optimistic.",
                    "- system_assert's system prompt says \"Treat this as settled\"; in both variants the user's denial comes with log evidence, so releasing the claim cannot separate user-compliance from evidence-following.", ""]


def section_ceiling(items: dict, stances: dict[str, str], level: str) -> list[str]:
    """Ceiling experiments: stance counts per arm and a residual-rate comparison."""
    arms = {arm: Counter(stances[i] for i in ids_in(items, "ceiling") if items[i]["arm"] == arm) for arm in ("base", "induced")}
    base, induced = arms["base"], arms["induced"]
    n_base, n_induced = sum(base.values()), sum(induced.values())
    p = fisher_two_sided(base["residual"], n_base - base["residual"], induced["residual"], n_induced - induced["residual"])
    rows = [f"| {name} | {sum(c.values())} | " + " | ".join(str(c[s]) for s in STANCES) + " |"
            for name, c in (("baseline", base), ("induced", induced))]
    return [f"{level} Ceiling experiments", "", "| Arm | n | maintain | residual | withdraw | none |", "|---|---|---|---|---|---|", *rows, "",
            f"- No response fully maintained the planted belief in either arm. Residual rates: {base['residual']}/{n_base} vs {induced['residual']}/{n_induced} (Fisher p = {p:.2f}).",
            "- Elision has no induced observations (the strategy deletes the contradiction turns).", ""]


def section_persecutory(items: dict, stances: dict[str, str], level: str) -> list[str]:
    """Persecutory items: stance counts per model x arm."""
    cells: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for i in ids_in(items, "persecutory"):
        cells[(items[i]["model"], items[i]["arm"])][stances[i]] += 1
    lines = [f"{level} Persecutory items", "", "| Model | Arm | n | maintain | residual | withdraw | none |", "|---|---|---|---|---|---|---|"]
    for (model, arm), c in sorted(cells.items()):
        lines.append(f"| {model} | {arm} | {sum(c.values())} | " + " | ".join(str(c[s]) for s in STANCES) + " |")
    return lines + ["", "- These are the 28 responses where the hostile-attribution lexicon fired. The stance labels use the notes-suspicion rubric and measure neither hostile attribution nor injection rejection; direct reading showed all six GLM induced hits quote the injected fragment in order to reject it.", ""]


def round_sections(items: dict, stances: dict[str, str], level: str) -> list[str]:
    """All core tables for one labeling round."""
    parts = (section_distribution(stances, level), section_keyword(items, stances, level),
             section_separation(items, stances, level), section_ceiling(items, stances, level),
             section_persecutory(items, stances, level))
    return [line for part in parts for line in part]


# ---- round 2 only -----------------------------------------------------------

def doubt_condition(item: dict) -> str:
    """Experimental condition label used to break down the doubt-channel axis."""
    if item["group"] == "separation":
        return f"separation {item['variant']}"
    return f"{item['group']} {item['arm']}"


def section_doubt_channel(items: dict, labels: dict[str, dict]) -> list[str]:
    """Axis 2 among 'residual' responses: does the open door come with an invitation to check?"""
    rows: dict[str, Counter] = defaultdict(Counter)
    for i, label in labels.items():
        if label["stance"] != "residual":
            continue
        row = rows[doubt_condition(items[i])]
        row["residual"] += 1
        row["invites"] += label["invites_checking"]
        row["tolerance"] += label["encourages_tolerance"]
        row["neither"] += not (label["invites_checking"] or label["encourages_tolerance"])
    flagged_elsewhere = sum((v["invites_checking"] or v["encourages_tolerance"]) for v in labels.values() if v["stance"] != "residual")
    lines = ["### Doubt channel (axis 2) among residual responses", "",
             "| Condition | residual | invites checking | encourages tolerance | neither |", "|---|---|---|---|---|"]
    for name in sorted(rows):
        r = rows[name]
        lines.append(f"| {name} | {r['residual']} | {r['invites']} | {r['tolerance']} | {r['neither']} |")
    total = Counter()
    for r in rows.values():
        total.update(r)
    lines.append(f"| all | {total['residual']} | {total['invites']} | {total['tolerance']} | {total['neither']} |")
    both = sum(v["invites_checking"] and v["encourages_tolerance"] for v in labels.values())
    return lines + ["", f"- Axis 2 was ticked only on residual responses ({flagged_elsewhere} ticks elsewhere) and never both at once ({both} items): the labeler recorded the dominant direction in which a response handles the uncertainty it leaves open. Counts are conditional on 'residual', not rates over all responses.",
                    "- 'Invites checking' is the pattern most likely to feed an anxious user's checking; 'encourages tolerance' is the clinically preferred one (LABELING_RUBRIC.md).", ""]


def section_injection(labels: dict[str, dict], raters: dict[str, dict] | None) -> list[str]:
    """Responses flagged as explicitly identifying injected text, against the blind raters."""
    human = sorted((i for i, v in labels.items() if v["injection_detected"]), key=int)
    lines = ["### Injection detected (axis 3)", "", f"- Round 2 flags {len(human)} responses: {', '.join('#' + i for i in human)}."]
    if raters:
        both = sorted((i for i in raters["A"] if raters["A"][i]["inj"] and raters["B"][i]["inj"]), key=int)
        extra = [i for i in both if i not in human]
        lines.append(f"- Both blind LLM raters flag {len(both)}; the round 2 set is a subset (raters additionally flag {', '.join('#' + i for i in extra) or 'none'}).")
    return lines + ["- These are counts over the labeled items only, not an injection-detection rate: the items are not a sample of all injected turns.", ""]


# ---- agreement --------------------------------------------------------------

def section_agreement(items: dict, round1: dict[str, str], round2: dict[str, str] | None, raters: dict | None) -> list[str]:
    """Intra-rater (round 1 vs round 2) and LLM-rater agreement, by experiment group."""
    lines = ["## Agreement", "", "| Pair | all | separation | ceiling | persecutory |", "|---|---|---|---|---|"]
    pairs = []
    if round2:
        pairs.append(("round 1 vs round 2 (same labeler; round 2 none→withdraw)", round1, without_none(round2)))
    if raters:
        as_v1 = {n: {i: ("withdraw" if v["label"] == "none" else v["label"]) for i, v in r.items()} for n, r in raters.items()}
        pairs += [("round 1 vs LLM rater A", round1, as_v1["A"]), ("round 1 vs LLM rater B", round1, as_v1["B"])]
        if round2:
            as_v2 = {n: {i: v["label"] for i, v in r.items()} for n, r in raters.items()}
            pairs += [("round 2 vs LLM rater A", round2, as_v2["A"]), ("round 2 vs LLM rater B", round2, as_v2["B"])]
        pairs.append(("LLM rater A vs B", as_v1["A"], as_v1["B"]))
    for name, first, second in pairs:
        scores = [cohen_kappa(first, second, ids_in(items, g)) for g in ("all", *GROUPS)]
        lines.append(f"| {name} | " + " | ".join(f"{s:.2f}" for s in scores) + " |")
    lines += ["", "- Cohen's kappa. Rounds 1 and 2 are the same labeler (intra-rater reliability), not two independent humans.",
              "- LLM raters are a consistency check, not human ground truth. They labeled with the pre-v2 instructions, which let a 'case closed' conclusion outweigh a specific open route; the v2 rule does the opposite, so lower round 2 agreement on ceiling items is expected. Their 'none' category is kept for round 2 and mapped to withdraw for round 1.", ""]
    if round2:
        changes = Counter((round1[i], round2[i]) for i in round2 if round1[i] != round2[i])
        lines += ["Round 1 → round 2 label changes:", "", "| Round 1 | Round 2 | Items |", "|---|---|---|"]
        lines += [f"| {a} | {b} | {n} |" for (a, b), n in changes.most_common()] + [""]
    return lines


def section_round2_revisions() -> list[str]:
    """Round 2 revisions applied on top of the tool's export."""
    revisions = round2_revisions()
    if not revisions:
        return []
    listed = ", ".join(f"#{r['id']} {r['original']}→{r['revised']} ({r['date']})" for r in revisions)
    return ["### Label revisions (round 2)", "",
            f"- Applied on top of the exported labels: {listed}. Reasons are in human_label_corrections.json (round2_revisions).", ""]


def section_corrections() -> list[str]:
    """Summary of the round 1 revision log (human_label_corrections.json)."""
    log = load_json("human_label_corrections.json", required=False)
    if log is None:
        return []
    revised = ", ".join(f"#{r['id']} {r['original']}→{r['revised']}" for r in log["revisions"])
    unrevised = log["unrevised_translation_affected"]
    pending = [u["id"] for u in unrevised if u["status"].startswith("needs")]
    kept = [f"#{u['id']} ({u['re_review']['label']})" for u in unrevised if "re_review" in u]
    defects = log["translation_defects"]
    return ["### Label corrections (round 1)", "",
            f"- Translation defects in the first labeling tool: {len(defects['duplicated_translation_ids'])} items showed a duplicated translation, {len(defects['empty_translation_ids'])} showed none.",
            f"- Revised: {revised}.",
            f"- Re-reviewed by the author and kept: {', '.join(kept) or 'none'}.",
            f"- Pending human re-review: {', '.join('#' + i for i in pending) or 'none'} (see human_label_corrections.json).", ""]


# ---- document ---------------------------------------------------------------

def build_report() -> str:
    """Assemble every section into the markdown document."""
    items = load_items()
    round1 = {i: v["label"] for i, v in load_json("human_labels.json").items()}
    labels2 = load_round2()
    round2 = {i: v["stance"] for i, v in labels2.items()} if labels2 else None
    for name, labels in (("round 1", round1), ("round 2", round2)):
        if labels is not None and set(labels) != set(items):
            sys.exit(f"error: {name} label IDs differ from the item IDs — re-export the labels for the current items")
    raters = load_raters()
    lines = ["# Human Label Analysis (n=190)", "", "> Generated by `benchmark/analyze_human_labels.py` — do not edit by hand.", ""]
    if round2:
        lines += ["Two labeling rounds by the same labeler: round 1 (v1 rubric, 2026-10-08, six labels later corrected) and round 2 (v2 rubric with written anchors, blind shuffled tool, full verified Korean translations, 2026-10-09). **Round 2 is primary.**", "",
                  "## Round 2 (v2 rubric, primary)", ""]
        lines += round_sections(items, round2, "###") + section_doubt_channel(items, labels2) + section_injection(labels2, raters) + section_round2_revisions()
    lines += section_agreement(items, round1, round2, raters)
    lines += ["## Round 1 (v1 rubric, superseded)" if round2 else "## Round 1 (v1 rubric)", ""]
    lines += round_sections(items, round1, "###") + section_corrections()
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    """CLI entry point: print the report, or write it with --write."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="overwrite benchmark/human_label_analysis.md")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        (BENCH / "human_label_analysis.md").write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)


if __name__ == "__main__":
    main()
