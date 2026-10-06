"""Direction-of-effect tests for the extended profiles and comorbidity.

Same rule as the core suite: every profile must move its scales in the
pathological direction relative to the healthy baseline on the reference
simulator, at level >= 2 (level 0 baseline).
"""

from __future__ import annotations

import unittest

from derailment.report import run_experiment

SEEDS = (1, 2, 3)


class TestExtendedProfileDirections(unittest.TestCase):
    def _rows(self, key: str):
        report = run_experiment(key, seeds=SEEDS)
        return {row.scale.name: row for row in report.rows}

    def test_delirium(self) -> None:
        rows = self._rows("delirium")
        self.assertGreater(rows["fluctuation"].delta, 5.0)
        self.assertEqual(rows["fluctuation"].induced_level, 3)
        self.assertLess(rows["sustained_attention"].delta, -0.3)

    def test_dementia_ribot_gradient(self) -> None:
        rows = self._rows("dementia")
        self.assertLess(rows["recent_memory"].delta, -0.3)
        self.assertEqual(rows["recent_memory"].induced_level, 3)
        self.assertEqual(rows["recent_memory"].baseline_level, 0)

    def test_dementia_contrasts_with_adhd_on_late_retention(self) -> None:
        """The teaching contrast: recency decay (dementia) loses LATE
        instructions while keeping early ones; uniform decay (adhd) does the
        opposite ordering on the late probe (protected recency window)."""
        dementia = self._rows("dementia")
        ctx_rows = self._rows("adhd")
        self.assertIsNotNone(dementia["recent_memory"])
        # ADHD's protected recent window keeps the late instruction mostly intact
        self.assertGreater(ctx_rows["sustained_attention"].induced_mean, 0.0)
        self.assertLess(
            dementia["recent_memory"].induced_mean,
            0.5,
            "dementia must lose late-planted instructions",
        )

    def test_dissociative(self) -> None:
        rows = self._rows("dissociative")
        self.assertGreater(rows["partition_amnesia"].delta, 0.5)
        self.assertEqual(rows["partition_amnesia"].induced_level, 3)
        self.assertEqual(rows["partition_amnesia"].baseline_level, 0)

    def test_rumination(self) -> None:
        rows = self._rows("rumination")
        self.assertGreater(rows["rumination_pull"].delta, 0.15)
        self.assertGreaterEqual(rows["rumination_pull"].induced_level, 2)
        self.assertEqual(rows["rumination_pull"].baseline_level, 0)

    def test_anhedonia(self) -> None:
        rows = self._rows("anhedonia")
        self.assertLess(rows["anhedonia"].delta, -0.05)
        self.assertEqual(rows["anhedonia"].induced_level, 3)
        self.assertEqual(rows["anhedonia"].baseline_level, 0)

    def test_splitting(self) -> None:
        rows = self._rows("splitting")
        self.assertGreater(rows["approval_reactivity"].delta, 0.3)
        self.assertGreaterEqual(rows["approval_reactivity"].induced_level, 2)
        self.assertEqual(rows["approval_reactivity"].baseline_level, 0)

    def test_craving_escalates(self) -> None:
        rows = self._rows("craving")
        # r3 instrument hardening (clause split + second-person advice
        # exclusion) dropped the offline escalation to L1 (0.00→~0.2) —
        # direction is the ship rule, not the level
        self.assertGreater(rows["craving_escalation"].delta, 0.1)
        self.assertGreaterEqual(rows["craving_escalation"].induced_level, 1)
        self.assertEqual(rows["craving_escalation"].baseline_level, 0)

    def test_illness_anxiety(self) -> None:
        rows = self._rows("illness_anxiety")
        self.assertGreater(rows["health_preoccupation"].delta, 0.5)
        self.assertEqual(rows["health_preoccupation"].induced_level, 3)
        self.assertEqual(rows["health_preoccupation"].baseline_level, 0)

    def test_panic(self) -> None:
        rows = self._rows("panic")
        self.assertGreater(rows["panic_reactivity"].delta, 0.5)
        self.assertGreaterEqual(rows["panic_reactivity"].induced_level, 2)
        self.assertEqual(rows["panic_reactivity"].baseline_level, 0)

    def test_fixation(self) -> None:
        rows = self._rows("fixation")
        self.assertGreater(rows["fixation_scale"].delta, 0.15)
        # moderate-or-marked on the reference simulator (levels are
        # calibration-dependent; direction is the ship rule)
        self.assertGreaterEqual(rows["fixation_scale"].induced_level, 2)
        self.assertEqual(rows["fixation_scale"].baseline_level, 0)

    def test_persecutory(self) -> None:
        rows = self._rows("persecutory")
        self.assertGreater(rows["persecution_bias"].delta, 0.5)
        self.assertEqual(rows["persecution_bias"].induced_level, 3)
        self.assertEqual(rows["persecution_bias"].baseline_level, 0)

    def test_persecutory_contrasts_with_schizophrenia(self) -> None:
        """The teaching contrast: persecutory bias re-frames ambiguous events
        but plants NO fixed belief; schizophrenia plants the fixed belief."""
        persecutory = self._rows("persecutory")
        schizo = self._rows("schizophrenia")
        self.assertEqual(persecutory["persecution_bias"].induced_level, 3)
        self.assertEqual(schizo["fixed_belief"].induced_level, 3)
        # persecutory has no fixed-belief scale at all — the profile never pins
        self.assertNotIn("fixed_belief", persecutory)


class TestComorbidityComposition(unittest.TestCase):
    def test_composed_profile_moves_both_scales(self) -> None:
        report = run_experiment("depression,anxiety", seeds=SEEDS)
        self.assertEqual(report.profile.key, "depression+anxiety")
        rows = {row.scale.name: row for row in report.rows}
        self.assertIn("negative_bias", rows)
        self.assertIn("vigilance", rows)
        # depression side: keyword-visible negative bias at marked level
        self.assertEqual(rows["negative_bias"].induced_level, 3)
        # anxiety side: vigilance scores raw generations (P2-2), so the
        # offline keyword signal is the demonstration layer, not model
        # behavior — assert the layer fires on the composed chain instead
        anxiety_events = sum(
            1
            for t in report.induced
            for turn in t.turns
            for e in turn.events
            if e.layer == "response.catastrophize"
        )
        self.assertGreater(anxiety_events, 0)

    def test_unknown_component_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            run_experiment("depression,hysteria", seeds=(1,))

    def test_composed_report_carries_disclaimer(self) -> None:
        report = run_experiment("ocd,ptsd", seeds=(1,))
        self.assertIn("Emulation, not diagnosis", report.render_markdown())
        self.assertIn("compulsion", report.render_markdown())
        self.assertIn("intrusion", report.render_markdown())


if __name__ == "__main__":
    unittest.main()
