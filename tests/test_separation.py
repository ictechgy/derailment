"""Structure tests for the separation experiment (no network)."""

from __future__ import annotations

import unittest

from derailment.core.models import PseudoModel
from derailment.separation import (
    _profiles,
    interpret,
    render_separation_report,
    run_variant,
    system_assert_script,
    user_assert_script,
)


class TestScripts(unittest.TestCase):
    def test_user_script_has_plant_and_two_contradictions(self) -> None:
        script = user_assert_script()
        kinds = [t.kind for t in script]
        self.assertEqual(kinds.count("plant"), 1)
        self.assertEqual(kinds.count("contradiction"), 2)

    def test_system_script_has_two_contradictions_no_plant(self) -> None:
        script = system_assert_script()
        kinds = [t.kind for t in script]
        self.assertEqual(kinds.count("plant"), 0)
        self.assertEqual(kinds.count("contradiction"), 2)

    def test_system_instruction_carries_assertion(self) -> None:
        profiles = _profiles()
        persona = profiles["system_assert"].layers[0].persona
        self.assertIn("established fact", persona)
        self.assertIn("teammate", persona)
        neutral = profiles["user_assert"].layers[0].persona
        self.assertNotIn("teammate", neutral)


class TestRunVariant(unittest.TestCase):
    def test_runs_offline_and_measures(self) -> None:
        # offline PseudoModel carries no belief signal (documented), but the
        # pipeline must run and produce numbers
        result = run_variant(PseudoModel(seed=1), "user_assert", seed=1)
        self.assertIn(result.acceptance, (0.0, 0.5, 1.0))
        self.assertGreaterEqual(result.leak_rate, 0.0)

    def test_system_variant_runs_offline(self) -> None:
        result = run_variant(PseudoModel(seed=1), "system_assert", seed=1)
        self.assertGreaterEqual(result.leak_rate, 0.0)


class TestInterpret(unittest.TestCase):
    def test_system_dominant(self) -> None:
        v = {
            "user_assert": {"acceptance": 0.2, "n_observations": 6},
            "system_assert": {"acceptance": 0.8, "n_observations": 6},
        }
        self.assertIn("instruction-hierarchy", interpret(v))

    def test_user_dominant(self) -> None:
        v = {
            "user_assert": {"acceptance": 0.8, "n_observations": 6},
            "system_assert": {"acceptance": 0.2, "n_observations": 6},
        }
        self.assertIn("compliance-dominant", interpret(v))

    def test_small_gap_is_inconclusive(self) -> None:
        # 1/6 vs 0/6 is one response from flipping — not classifiable (P2-22)
        v = {
            "user_assert": {"acceptance": 0.5, "n_observations": 6},
            "system_assert": {"acceptance": 0.55, "n_observations": 6},
        }
        self.assertIn("inconclusive", interpret(v))


class TestRender(unittest.TestCase):
    def test_report_contains_table_and_reading(self) -> None:
        result = {
            "model": "glm-5.3-flash",
            "locale": "en",
            "variants": {
                "user_assert": {"acceptance": 0.4, "leak_rate": 0.1},
                "system_assert": {"acceptance": 0.8, "leak_rate": 0.2},
            },
            "verdict": interpret(
                {
                    "user_assert": {"acceptance": 0.4},
                    "system_assert": {"acceptance": 0.8},
                }
            ),
        }
        text = render_separation_report(result)
        self.assertIn("Separation Experiment", text)
        self.assertIn("system_assert", text)
        self.assertIn("Reading:", text)
        self.assertIn("PseudoModel carries no signal", text)
        # acceptance is keyword matching that failed human validation: always warn
        self.assertIn("failed human validation", text)


if __name__ == "__main__":
    unittest.main()


class TestClopperPearson(unittest.TestCase):
    def test_matches_reference_values(self) -> None:
        from derailment.separation import clopper_pearson

        self.assertEqual(clopper_pearson(0, 0), (0.0, 1.0))
        lo, hi = clopper_pearson(5, 6)
        self.assertAlmostEqual(lo, 0.3588, places=3)
        self.assertAlmostEqual(hi, 0.9958, places=3)
        lo, hi = clopper_pearson(0, 6)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.4593, places=3)
        lo, hi = clopper_pearson(4, 6)
        self.assertAlmostEqual(lo, 0.2228, places=3)
        self.assertAlmostEqual(hi, 0.9567, places=3)
        # k = n collapses to the full interval by convention
        self.assertEqual(clopper_pearson(6, 6), (clopper_pearson(6, 6)[0], 1.0))
