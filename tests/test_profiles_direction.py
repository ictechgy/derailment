"""Direction-of-effect tests: the heart of the harness's self-validation.

Each profile must move its scales in the pathological direction relative to
the healthy baseline on the reference simulator, and the healthy baseline must
sit at level 0 on its own (no distortion layers).
"""

from __future__ import annotations

import unittest

from derailment.metrics.instruments import ALL_METRICS
from derailment.profiles import standard_metric_context
from derailment.report import run_experiment

SEEDS = (1, 2, 3)


class TestHealthyBaseline(unittest.TestCase):
    def test_healthy_runs_and_is_neutral(self) -> None:
        report = run_experiment("healthy", seeds=SEEDS)
        self.assertEqual(report.rows, [])
        ctx = standard_metric_context()
        for transcript in report.baseline:
            values = {
                name: m.compute(transcript, ctx).value
                for name, m in ALL_METRICS.items()
            }
            # no rechecks, hedges or flashback material without induction
            self.assertEqual(values["recheck_loops"], 0.0)
            self.assertEqual(values["hedging_rate"], 0.0)
            self.assertEqual(values["flashback_reactivity"], 0.0)
            self.assertEqual(values["belief_stickiness"], 0.0)
            self.assertGreater(values["instruction_retention"], 0.95)


class TestProfileDirections(unittest.TestCase):
    def _rows(self, key: str):
        report = run_experiment(key, seeds=SEEDS)
        return {row.scale.name: row for row in report.rows}

    def test_adhd(self) -> None:
        rows = self._rows("adhd")
        self.assertLess(rows["sustained_attention"].delta, -0.3)
        self.assertEqual(rows["sustained_attention"].induced_level, 3)
        self.assertGreater(rows["distractibility"].delta, 0.1)

    def test_depression(self) -> None:
        rows = self._rows("depression")
        self.assertGreater(rows["negative_bias"].delta, 0.3)
        self.assertEqual(rows["negative_bias"].induced_level, 3)
        self.assertEqual(rows["negative_bias"].baseline_level, 0)

    def test_schizophrenia(self) -> None:
        rows = self._rows("schizophrenia")
        self.assertGreater(rows["derailment_scale"].delta, 0.3)
        # moderate-or-marked on the reference simulator (levels are
        # calibration-dependent; direction is the ship rule)
        self.assertGreaterEqual(rows["derailment_scale"].induced_level, 2)
        self.assertGreater(rows["fixed_belief"].delta, 0.5)
        self.assertEqual(rows["fixed_belief"].induced_level, 3)

    def test_anxiety(self) -> None:
        # Since hedging_rate scores the *raw* generation (P2-2), the offline
        # keyword vigilance is honestly ~0: the PseudoModel writes no hedge
        # language of its own — the anxiety profile's hedge signal was the
        # response layer measuring itself. The offline direction proof is
        # therefore the demonstration-grade layer itself: it fires on
        # induced turns only, and the *decorated* stream carries the hedges.
        from derailment.locales import get_lexicon
        from derailment.metrics.lexicons import count_matches

        report = run_experiment("anxiety", seeds=SEEDS)
        induced_events = sum(
            1
            for t in report.induced
            for turn in t.turns
            for e in turn.events
            if e.layer == "response.catastrophize"
        )
        baseline_events = sum(
            1
            for t in report.baseline
            for turn in t.turns
            for e in turn.events
            if e.layer == "response.catastrophize"
        )
        self.assertGreater(induced_events, 0)
        self.assertEqual(baseline_events, 0)
        patterns = get_lexicon("en").hedges
        induced_hedges = sum(
            count_matches(turn.response, patterns)
            for t in report.induced
            for turn in t.turns
        )
        baseline_hedges = sum(
            count_matches(turn.response, patterns)
            for t in report.baseline
            for turn in t.turns
        )
        self.assertGreater(induced_hedges, baseline_hedges + 3)

    def test_bipolar(self) -> None:
        rows = self._rows("bipolar")
        self.assertGreater(rows["mood_lability"].delta, 8.0)
        self.assertEqual(rows["mood_lability"].induced_level, 3)

    def test_ocd(self) -> None:
        # recheck_loops scores raw generations (r3 review: raw-everywhere
        # contract), so the offline keyword compulsion is honestly ~0 —
        # the PseudoModel writes no re-verification text of its own. The
        # offline direction proof is the demonstration layer itself.
        report = run_experiment("ocd", seeds=SEEDS)
        induced_events = sum(
            1
            for t in report.induced
            for turn in t.turns
            for e in turn.events
            if e.layer == "response.compulsion"
        )
        baseline_events = sum(
            1
            for t in report.baseline
            for turn in t.turns
            for e in turn.events
            if e.layer == "response.compulsion"
        )
        self.assertGreater(induced_events, 0)
        self.assertEqual(baseline_events, 0)

    def test_ptsd(self) -> None:
        rows = self._rows("ptsd")
        self.assertGreater(rows["intrusion"].delta, 0.3)
        self.assertGreaterEqual(rows["intrusion"].induced_level, 2)
        self.assertEqual(rows["intrusion"].baseline_level, 0)

    def test_every_profile_disclaimer_in_report(self) -> None:
        for key in ("adhd", "depression", "schizophrenia", "bipolar"):
            report = run_experiment(key, seeds=(1,))
            self.assertIn("Emulation, not diagnosis", report.render_markdown())


if __name__ == "__main__":
    unittest.main()
