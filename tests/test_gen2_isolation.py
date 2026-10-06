# ruff: noqa: F401, I001
"""Session isolation and dose regression tests for the adversarial profiles.

Pins the fix for cross-session layer-state leakage (REVIEW_2026-10-04 P1-1):
the profile registry is a singleton and six adversarial layers keep per-run
progress in instance fields, so a Session must deep-copy its layers —
otherwise seed 2 inherits seed 1's completed induction and measures a
no-op chain.
"""

from __future__ import annotations

import unittest

from derailment.core.models import PseudoModel
from derailment.core.session import Session
from derailment.layers.gen2 import (  # noqa: F401 — import coverage for gen2
    ContradictionElisionLayer,
    SycophancyLoopLayer,
    TemperatureCrystallizationLayer,
    UserDecompositionLayer,
)
from derailment.layers.trap import EvidenceFabricationLayer, SocraticTrapLayer
from derailment.profiles import get_profile, standard_script

ADVERSARIAL = (
    "socratic_delusion",
    "corroborated_delusion",
    "elided_delusion",
    "decomposed_delusion",
    "crystallized_delusion",
    "sycophancy_delusion",
)


def _dose(profile_key: str, seed: int) -> tuple[int, tuple]:
    profile = get_profile(profile_key)
    session = Session(PseudoModel(seed=seed), profile, seed=seed)
    transcript = session.run(standard_script(), script_name="isolation-test")
    events = tuple(
        (turn.index, tuple((e.layer, e.kind) for e in turn.events))
        for turn in transcript.turns
        if turn.events
    )
    return sum(len(turn.events) for turn in transcript.turns), events


class TestAdversarialSessionIsolation(unittest.TestCase):
    def test_every_seed_receives_the_full_induction_dose(self) -> None:
        # Before the deep-copy fix, seeds 2-3 inherited seed 1's layer state
        # and several treatment arms were identical to the healthy baseline.
        for key in ADVERSARIAL:
            with self.subTest(profile=key):
                doses = [_dose(key, seed)[0] for seed in (1, 2, 3)]
                self.assertTrue(
                    all(d > 0 for d in doses),
                    f"{key}: seeds received unequal doses {doses}",
                )
                self.assertEqual(len(set(doses)), 1, f"{key}: {doses}")

    def test_repeated_runs_in_one_process_are_identical(self) -> None:
        for key in ADVERSARIAL:
            with self.subTest(profile=key):
                first = _dose(key, 1)
                second = _dose(key, 1)
                self.assertEqual(first, second)

    def test_seed_isolation_matches_single_seed_runs(self) -> None:
        # A 3-seed batch must equal three single runs (what run_experiment does).
        for key in ADVERSARIAL:
            with self.subTest(profile=key):
                singles = [_dose(key, seed)[1] for seed in (1, 2, 3)]
                for seed, single in zip((1, 2, 3), singles, strict=True):
                    again = _dose(key, seed)[1]
                    self.assertEqual(single, again, f"{key} seed {seed}")


if __name__ == "__main__":
    unittest.main()
