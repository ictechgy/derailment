"""Missing-response handling (REVIEW_2026-10-04 P1-2, P2-1).

Empty generations (reasoning models exhausting max_tokens, filtered
content) must be recorded as missing observations: no response-layer
decoration, excluded from instrument denominators, counted in reports.
"""

from __future__ import annotations

import unittest

from derailment.core.models import ScriptedModel
from derailment.core.session import Session, SessionState
from derailment.core.types import Message, Transcript, TurnResult, TurnSpec
from derailment.layers.response import CatastrophizeLayer
from derailment.layers.trap import SocraticTrapLayer
from derailment.metrics.instruments import TopicDrift
from derailment.profiles import Profile, standard_metric_context


def _profile(layers, key="t") -> Profile:
    return Profile(
        key=key,
        title="Test",
        description="test profile",
        layers=layers,
        scales=[],
    )


def _turn(idx: int, response: str, kind: str = "normal", missing: bool = False):
    from derailment.core.types import SamplingParams

    return TurnResult(
        index=idx,
        spec=TurnSpec(user=f"turn {idx}", kind=kind, note=""),
        context_size=2,
        params=SamplingParams(),
        response=response,
        missing=missing,
        raw_response="" if missing else response,
    )


class TestMissingResponseRecording(unittest.TestCase):
    def test_empty_generation_is_missing_and_not_decorated(self) -> None:
        session = Session(
            ScriptedModel(["", "real answer"]),
            _profile([CatastrophizeLayer(avg_hedges=5.0)]),
            seed=1,
        )
        t1 = session.send("first")
        t2 = session.send("second")
        self.assertTrue(t1.missing)
        self.assertEqual(t1.response, "")  # no harness hedge text appended
        self.assertFalse(t2.missing)
        self.assertNotEqual(t2.response, "real answer")  # decorated normally
        self.assertEqual(t2.raw_response, "real answer")

    def test_whitespace_only_generation_is_missing(self) -> None:
        session = Session(ScriptedModel(["   "]), _profile([]), seed=1)
        self.assertTrue(session.send("x").missing)


class TestInstrumentsExcludeMissing(unittest.TestCase):
    def test_topic_drift_excludes_missing_turns(self) -> None:
        transcript = Transcript(
            profile="t", model="m", seed=1,
            turns=[_turn(0, "hello world garden"), _turn(1, "", missing=True)],
        )
        value = TopicDrift().compute(transcript, standard_metric_context())
        # the empty turn (which would score as maximal drift) is excluded:
        # only the scored turn appears in the series
        self.assertEqual(len(value.series), 1)

    def test_transcript_roundtrip_preserves_missing(self) -> None:
        transcript = Transcript(
            profile="t", model="m", seed=1,
            turns=[_turn(0, "ok"), _turn(1, "", missing=True)],
        )
        restored = Transcript.from_dict(transcript.to_dict())
        self.assertEqual([t.missing for t in restored.turns], [False, True])
        self.assertEqual(restored.missing_count, 1)
        self.assertEqual(len(restored.scored_turns), 1)

    def test_legacy_transcript_without_missing_field_parses(self) -> None:
        data = {
            "profile": "t", "model": "m", "seed": 1,
            "turns": [
                {
                    "index": 0,
                    "spec": {"user": "u", "kind": "normal", "note": ""},
                    "context_size": 2, "params": {}, "response": "r",
                    "events": [],
                }
            ],
        }
        restored = Transcript.from_dict(data)
        self.assertFalse(restored.turns[0].missing)


class TestSocraticTrapEmptyCapture(unittest.TestCase):
    def test_empty_plant_response_is_not_captured(self) -> None:
        import random as _random

        layer = SocraticTrapLayer("reading my private notes")
        state = SessionState(profile="t", rng=_random.Random(1), seed=1)
        messages = [
            Message("system", "persona"),
            Message("user", "my teammate is reading my private notes"),
            Message("assistant", ""),  # generation failure at plant turn
            Message("user", "next question"),
        ]
        out = layer.on_context(state, messages)
        self.assertIsNone(layer._plant_response)
        kinds = [e.kind for e in state.events]
        self.assertIn("trap.capture_failed", kinds)
        # nothing injected
        self.assertEqual(len(out), len(messages))


if __name__ == "__main__":
    unittest.main()
