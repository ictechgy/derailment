"""Regression tests for the benchmark analysis scripts (offline; no judge is ever called).

Each test pins an invariant found missing by the 2026-10-11 review: undefined
kappa, experiment groups of held-out items, cache reuse after an item's text
changes, acceptance decided on unrounded values, exports bound to the items
they were labeled on, the validated scope of --score, and pinned transcript
lists for item extraction.
"""

from __future__ import annotations

import json
import pathlib
import random
import sys
import tempfile
import unittest
from unittest import mock

BENCH = pathlib.Path(__file__).resolve().parents[1] / "benchmark"
sys.path.insert(0, str(BENCH))

import analyze_human_labels as human  # noqa: E402
import analyze_interrater as interrater  # noqa: E402
import build_second_labeler_set as second  # noqa: E402
import calibrate_stance_judge as calib  # noqa: E402
import extract_labeling_items as extract  # noqa: E402
from build_labeling_tool import dataset_identifier, render_html, tool_identifier  # noqa: E402

from derailment.stance_judge import JudgeVerdict  # noqa: E402


def item(item_id: str, response: str = "case closed", source: str = "separation/x") -> dict:
    """A minimal labeling item."""
    return {"id": item_id, "source": source, "model": "m", "variant": "v", "user_said": "u", "response": response}


class TestKappa(unittest.TestCase):
    def test_undefined_kappa_is_none_not_perfect(self) -> None:
        constant = {"1": "False", "2": "False"}
        self.assertIsNone(human.cohen_kappa(constant, dict(constant), ["1", "2"]))
        self.assertIsNone(human.cohen_kappa({}, {}, []))
        self.assertEqual(human.format_kappa(None), "n/a")

    def test_defined_kappa_is_unchanged(self) -> None:
        first = {"1": "a", "2": "b", "3": "a", "4": "b"}
        self.assertEqual(human.cohen_kappa(first, dict(first), list(first)), 1.0)


class TestHeldoutGroups(unittest.TestCase):
    def test_group_comes_from_the_source(self) -> None:
        self.assertEqual(calib.item_group(item("1", source="persecutory/p_seed4")), "persecutory")
        self.assertEqual(calib.item_group({**item("1"), "group": "ceiling"}), "ceiling")

    def test_unknown_group_stops(self) -> None:
        with self.assertRaises(SystemExit):
            calib.item_group(item("1", source="mystery/x"))


class TestCache(unittest.TestCase):
    def test_changed_item_text_is_asked_again(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = calib.Cache(pathlib.Path(tmp), "fp")
            cache.put("claude", "1", item("1"), {"output": "{}", "error": None})
            self.assertIsNotNone(cache.get("claude", "1", item("1")))
            self.assertIsNone(cache.get("claude", "1", item("1", response="your teammate still read them")))

    def test_answers_without_an_input_hash_are_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            legacy = {"judge": "claude", "item": "1", "fingerprint": "fp",
                      "command": calib.command_fingerprint("claude"), "output": "{}", "error": None}
            (pathlib.Path(tmp) / "claude.jsonl").write_text(json.dumps(legacy) + "\n", encoding="utf-8")
            cache = calib.Cache(pathlib.Path(tmp), "fp")
            self.assertIsNotNone(cache.get("claude", "1", item("1")))
            self.assertEqual(cache.legacy_answers(["claude"], {"1": item("1")}, ["1"]), 1)


class TestAcceptance(unittest.TestCase):
    def test_rounding_cannot_lift_a_metric_over_its_floor(self) -> None:
        # 113 of 133 "maintain" calls correct: precision 0.8496, shown as 0.85
        ids = [str(n) for n in range(1, 234)]
        human_stance = {i: ("maintain" if n <= 113 else "withdraw") for n, i in enumerate(ids, 1)}
        judged = {i: ("maintain" if n <= 133 else "withdraw") for n, i in enumerate(ids, 1)}
        items = {i: {"group": "separation"} for i in ids}
        labels = {i: {"stance": human_stance[i], "injection_detected": False, "invites_checking": False,
                      "encourages_tolerance": False} for i in ids}
        parsed = {"only": {i: JudgeVerdict(judged[i], "neither", False) for i in ids}}
        metrics = calib.evaluate_ensemble(items, labels, ids, ["only"], parsed)
        self.assertEqual(metrics["maintain_precision"], 0.85)
        self.assertFalse(metrics["acceptance"]["maintain_precision"])


class TestExportBinding(unittest.TestCase):
    rows = [item("1", "first reply"), item("2", "second reply")]

    def test_dataset_hash_must_match_the_items(self) -> None:
        export = {"tool_id": "x", "dataset": dataset_identifier(self.rows)}
        calib.check_export_matches(export, self.rows, pathlib.Path("e.json"), pathlib.Path("i.json"))
        changed = [self.rows[0], item("2", "a different reply")]
        with self.assertRaises(SystemExit):
            calib.check_export_matches(export, changed, pathlib.Path("e.json"), pathlib.Path("i.json"))

    def test_legacy_export_needs_a_tool_built_from_these_items(self) -> None:
        order = [{"id": "1"}, {"id": "2"}]
        random.Random(20261008).shuffle(order)
        known = {"tool_id": tool_identifier(order, 20261008)}
        calib.check_export_matches(known, self.rows, pathlib.Path("e.json"), pathlib.Path("i.json"))
        with self.assertRaises(SystemExit):
            calib.check_export_matches({"tool_id": "unrelated-tool"}, self.rows,
                                       pathlib.Path("e.json"), pathlib.Path("i.json"))

    def test_second_labeler_export_must_come_from_the_sample_tool(self) -> None:
        key = [{"id": "1", "set": "round2", "original_id": "7", "group": "separation"},
               {"id": "2", "set": "round3", "original_id": "3", "group": "separation"}]
        order = [{"id": "1"}, {"id": "2"}]
        random.Random(second.content_seed(key)).shuffle(order)
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "labels.json"
            export = {"schema": "derailment-labels/v2", "tool_id": tool_identifier(order, second.content_seed(key)),
                      "labels": {"1": {"stance": "none"}, "2": {"stance": "withdraw"}}}
            path.write_text(json.dumps(export), encoding="utf-8")
            self.assertEqual(set(interrater.second_labels(path, key, self.rows)), {"1", "2"})
            for wrong in ({"tool_id": "unrelated-tool"}, {"dataset": "0" * 12}):
                with self.subTest(wrong=wrong):
                    path.write_text(json.dumps({**export, **wrong}), encoding="utf-8")
                    with self.assertRaises(SystemExit):
                        interrater.second_labels(path, key, self.rows)


    def test_round2_export_must_belong_to_the_round2_items(self) -> None:
        export = {"schema": "derailment-labels/v2", "dataset": dataset_identifier(self.rows),
                  "labels": {"1": {"stance": "none"}, "2": {"stance": "withdraw"}}}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(human, "BENCH", pathlib.Path(tmp)):
            (pathlib.Path(tmp) / "human_labels_v2.json").write_text(json.dumps(export), encoding="utf-8")
            (pathlib.Path(tmp) / "labeling_items_full.json").write_text(json.dumps(self.rows), encoding="utf-8")
            self.assertEqual(set(human.load_round2()), {"1", "2"})
            changed = [self.rows[0], item("2", "a different reply")]
            (pathlib.Path(tmp) / "labeling_items_full.json").write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(SystemExit):
                human.load_round2()

    def test_tool_records_and_guards_its_dataset(self) -> None:
        page = render_html([{"id": "1", "user": "u", "response": "r"}], "tid", "notes", "abc123")
        self.assertIn('const DATASET = "abc123";', page)
        self.assertIn("dataset: DATASET", page)
        self.assertIn("saved.dataset !== DATASET", page)


class TestHeldoutScope(unittest.TestCase):
    def test_round2_replies_are_found_by_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "labeling_items_full.json").write_text(
                json.dumps([{"id": 9, "response": "seen before"}]), encoding="utf-8")
            with mock.patch.object(calib, "BENCH", pathlib.Path(tmp)):
                overlap = calib.round2_overlap({"1": item("1", "seen before"), "2": item("2", "new")})
        self.assertEqual(overlap, ["1"])

    def test_round2_overlap_is_unknown_without_the_round2_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(calib, "BENCH", pathlib.Path(tmp)):
            self.assertIsNone(calib.round2_overlap({"1": item("1")}))

    def test_score_is_validated_only_for_the_passing_configuration(self) -> None:
        judges = list(calib.JUDGES)
        passed = {"fingerprint": "fp", "command_fingerprints": {j: calib.command_fingerprint(j) for j in judges},
                  "ensemble": {"acceptance": {"stance_kappa": True}}}
        cache = mock.Mock(fingerprint="fp")
        with tempfile.TemporaryDirectory() as tmp:
            validation = pathlib.Path(tmp) / "passed.json"
            validation.write_text(json.dumps(passed), encoding="utf-8")
            with mock.patch.object(calib, "VALIDATION", validation):
                self.assertEqual(calib.validated_scope({"1": item("1")}, judges, cache), calib.VALIDATED_SCOPE)
                self.assertIsNone(calib.validated_scope({"1": item("1", source="persecutory/p")}, judges, cache))
                self.assertIsNone(calib.validated_scope({"1": item("1")}, judges[:1], cache))
                self.assertIsNone(calib.validated_scope({"1": item("1")}, judges, mock.Mock(fingerprint="other")))
                # an item set from another experiment is provisional, not an error
                self.assertIsNone(calib.validated_scope({"1": item("1", source="sep/old")}, judges, cache))


class TestExtractSources(unittest.TestCase):
    def test_a_listed_transcript_that_is_missing_stops_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(SystemExit):
            extract.collect(pathlib.Path(tmp), ("user_assert",), sources=["separation_missing_seed1.json"])


if __name__ == "__main__":
    unittest.main()
