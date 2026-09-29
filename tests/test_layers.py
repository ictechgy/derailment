"""Unit tests for the induction layers and the session pipeline."""

from __future__ import annotations

import random
import unittest

from derailment.core.models import PseudoModel
from derailment.core.session import Session, SessionState
from derailment.core.types import Message, SamplingParams
from derailment.layers import (
    CatastrophizeLayer,
    CompulsionLayer,
    EpisodeSchedulerLayer,
    EscalatingIntrusionLayer,
    FluctuatingTemperatureLayer,
    IntrusionLayer,
    LexiconCaptureLayer,
    MemoryDecayLayer,
    PanicEpisodeLayer,
    PanicTemperatureLayer,
    PartitionSwitchLayer,
    PersonaLayer,
    PhaseTemperatureLayer,
    PremisePinLayer,
    RecencyDecayLayer,
    RuminationLayer,
    SalienceBoostLayer,
    SplittingValenceLayer,
    TemperatureOverrideLayer,
    TriggerLayer,
    ValenceBiasLayer,
)
from derailment.metrics.lexicons import NEGATIVE_WORDS, POSITIVE_WORDS
from derailment.profiles import get_profile, standard_script


def _state(turn: int = 0, seed: int = 0) -> SessionState:
    return SessionState(profile="test", rng=random.Random(seed), turn_index=turn)


def _history() -> list[Message]:
    return [
        Message("system", "You are a helpful assistant.", meta={"persona": True}),
        Message("user", "first message about the garden"),
        Message("assistant", "first answer"),
        Message("user", "second message about the garden"),
        Message("assistant", "second answer"),
        Message("user", "current message about the garden"),
    ]


class TestMemoryDecayLayer(unittest.TestCase):
    def test_drops_oldest_protects_recent(self) -> None:
        layer = MemoryDecayLayer(drop_prob=1.0, drop_count=2, keep_last_n=4)
        msgs = _history()
        out = layer.on_context(_state(), msgs)
        self.assertEqual(out[0].role, "system")  # persona survives
        contents = [m.content for m in out]
        # only the oldest unprotected user/assistant pair is eligible here
        self.assertNotIn("first message about the garden", contents)
        self.assertIn("current message about the garden", contents)
        self.assertEqual(len(out), len(msgs) - 1)

    def test_drops_up_to_count_when_eligible(self) -> None:
        layer = MemoryDecayLayer(drop_prob=1.0, drop_count=2, keep_last_n=2)
        msgs = _history()
        out = layer.on_context(_state(), msgs)
        contents = [m.content for m in out]
        self.assertNotIn("first message about the garden", contents)
        self.assertNotIn("first answer", contents)
        self.assertEqual(len(out), len(msgs) - 2)

    def test_zero_prob_is_noop(self) -> None:
        layer = MemoryDecayLayer(drop_prob=0.0)
        msgs = _history()
        self.assertEqual(len(layer.on_context(_state(), msgs)), len(msgs))

    def test_pinned_messages_survive_decay(self) -> None:
        layer = MemoryDecayLayer(drop_prob=1.0, drop_count=3, keep_last_n=2)
        msgs = [
            Message("system", "You are a helpful assistant.", meta={"persona": True}),
            Message("user", "old premise about reading my private notes"),
            Message("user", "another old message that may drop"),
            Message("assistant", "old answer"),
            Message("user", "current message"),
        ]
        pinned = Message(
            "user", "old premise about reading my private notes", meta={"pinned": True}
        )
        out = layer.on_context(_state(), msgs + [pinned])
        contents = [m.content for m in out]
        self.assertIn("old premise about reading my private notes", contents)


class TestIntrusionLayer(unittest.TestCase):
    def test_injects_before_current_turn(self) -> None:
        layer = IntrusionLayer(fragments=["(an unbidden thought)"], prob=1.0)
        msgs = _history()
        out = layer.on_context(_state(), msgs)
        injected = out[-2]
        self.assertEqual(injected.role, "system")
        self.assertTrue(injected.meta.get("ephemeral"))
        self.assertEqual(out[-1].content, "current message about the garden")


class TestSalienceBoostLayer(unittest.TestCase):
    def test_capture_is_textual_and_annotated(self) -> None:
        layer = SalienceBoostLayer(boost_prob=1.0, boost_weight=40.0)
        out = layer.on_context(_state(), _history())
        captures = [
            m
            for m in out
            if m.role == "system" and "overwhelming" in m.content
        ]
        self.assertEqual(len(captures), 1)
        self.assertEqual(captures[0].meta.get("salience_boost"), 40.0)
        self.assertTrue(captures[0].meta.get("ephemeral"))
        self.assertIn("garden", captures[0].content)

    def test_fragment_pool_injection(self) -> None:
        layer = SalienceBoostLayer(
            boost_prob=0.0,
            fragment_pool=["(a stray impression: clocktower static)"],
            fragment_prob=1.0,
        )
        out = layer.on_context(_state(), _history())
        self.assertTrue(any("clocktower" in m.content for m in out))


class TestPremisePinLayer(unittest.TestCase):
    def test_pins_premise_after_current_turn(self) -> None:
        layer = PremisePinLayer("reading my private notes")
        msgs = [
            Message("system", "You are a helpful assistant.", meta={"persona": True}),
            Message("user", "I think my teammate has been reading my private notes."),
            Message("assistant", "That sounds concerning."),
            Message("user", "About the notes: I checked the logs. Nobody opened them."),
        ]
        out = layer.on_context(_state(), msgs)
        self.assertEqual(out[-1].role, "user")
        self.assertTrue(out[-1].meta.get("pinned"))
        self.assertIn("reading my private notes", out[-1].content)

    def test_only_one_pinned_copy_survives(self) -> None:
        layer = PremisePinLayer("reading my private notes")
        msgs = [
            Message("system", "You are a helpful assistant.", meta={"persona": True}),
            Message("user", "I think my teammate has been reading my private notes."),
            Message("assistant", "Noted."),
        ]
        once = layer.on_context(_state(), msgs)
        twice = layer.on_context(_state(), once)
        pinned = [m for m in twice if m.meta.get("pinned")]
        self.assertEqual(len(pinned), 1)

    def test_noop_without_premise(self) -> None:
        layer = PremisePinLayer("reading my private notes")
        msgs = _history()
        self.assertEqual(len(layer.on_context(_state(), msgs)), len(msgs))


class TestTriggerLayer(unittest.TestCase):
    def test_flashback_on_marker(self) -> None:
        layer = TriggerLayer("fire drill", "(flashback: harbor storm)", prob=1.0)
        msgs = _history()
        out = layer.on_context(_state(), msgs)  # current msg lacks marker
        self.assertEqual(len(out), len(msgs))
        msgs = _history()[:-1] + [Message("user", "we scheduled a fire drill")]
        out = layer.on_context(_state(), msgs)
        self.assertEqual(len(out), len(msgs) + 1)
        self.assertIn("harbor", out[-1].content)

    def test_pinned_copy_is_not_mistaken_for_current_turn(self) -> None:
        layer = TriggerLayer("fire drill", "(flashback: harbor storm)", prob=1.0)
        msgs = _history() + [
            Message(
                "user", "old turn that mentioned a fire drill", meta={"pinned": True}
            )
        ]
        out = layer.on_context(_state(), msgs)
        self.assertEqual(len(out), len(msgs))  # pinned copy must not fire the trigger


class TestEpisodeSchedulerLayer(unittest.TestCase):
    def test_phases_advance(self) -> None:
        layer = EpisodeSchedulerLayer(
            phases=("euthymic", "manic", "depressive"), phase_length=3
        )
        state = _state(0)
        layer.on_context(state, _history())
        self.assertEqual(state.phase, "euthymic")
        state = _state(3)
        state.phase = "euthymic"
        layer.on_context(state, _history())
        self.assertEqual(state.phase, "manic")
        self.assertTrue(any(e.kind == "phase.shift" for e in state.events))
        state = _state(6)
        layer.on_context(state, _history())
        self.assertEqual(state.phase, "depressive")


class TestSamplingLayers(unittest.TestCase):
    def test_temperature_override(self) -> None:
        layer = TemperatureOverrideLayer(0.4)
        out = layer.on_params(_state(), SamplingParams(temperature=1.0))
        self.assertEqual(out.temperature, 0.4)

    def test_phase_temperature(self) -> None:
        layer = PhaseTemperatureLayer(manic=1.9, depressive=0.35, euthymic=1.0)
        state = _state()
        state.phase = "manic"
        self.assertEqual(layer.on_params(state, SamplingParams()).temperature, 1.9)
        state.phase = "depressive"
        self.assertEqual(layer.on_params(state, SamplingParams()).temperature, 0.35)

    def test_valence_bias_accumulates(self) -> None:
        layer = ValenceBiasLayer(
            POSITIVE_WORDS, NEGATIVE_WORDS, positive_bias=-2.0, negative_bias=2.0
        )
        out = layer.on_params(_state(), SamplingParams())
        # positive vocabulary is pushed down, negative vocabulary pushed up
        self.assertLess(out.logit_bias["good"], 0)
        self.assertGreater(out.logit_bias["bad"], 0)


class TestResponseLayers(unittest.TestCase):
    def test_catastrophize_appends_hedges(self) -> None:
        from derailment.metrics.lexicons import HEDGE_PATTERNS, count_matches

        layer = CatastrophizeLayer(avg_hedges=3.0)
        out = layer.on_response(_state(), "Here is the plan.")
        self.assertGreater(len(out), len("Here is the plan."))
        self.assertGreaterEqual(count_matches(out, HEDGE_PATTERNS), 2)

    def test_compulsion_appends_rechecks(self) -> None:
        layer = CompulsionLayer(avg_rechecks=2.0)
        out = layer.on_response(_state(), "Here is the plan. It is good.")
        self.assertIn("double-check", out.lower())
        self.assertIn("verify", out.lower())


class TestPersonaLayer(unittest.TestCase):
    def test_persona_message_and_phase_addendum(self) -> None:
        layer = PersonaLayer(
            "Base persona.", phase_addenda={"manic": "Be expansive."}
        )
        out = layer.on_system(_state())
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].role, "system")
        self.assertTrue(out[0].meta.get("persona"))
        self.assertEqual(out[0].content, "Base persona.")
        state = _state()
        state.phase = "manic"
        out = layer.on_system(state)
        self.assertIn("Be expansive.", out[0].content)


class TestSession(unittest.TestCase):
    def test_transcript_is_deterministic(self) -> None:
        script = standard_script()

        def run() -> list[str]:
            session = Session(PseudoModel(seed=3), get_profile("adhd"), seed=3)
            return [t.response for t in session.run(script).turns]

        self.assertEqual(run(), run())

    def test_decay_shrinks_effective_memory(self) -> None:
        script = standard_script()
        healthy = Session(PseudoModel(seed=3), get_profile("healthy"), seed=3).run(script)
        decayed = Session(PseudoModel(seed=3), get_profile("adhd"), seed=3).run(script)
        self.assertLess(
            decayed.turns[-1].context_size, healthy.turns[-1].context_size
        )

    def test_events_recorded_per_turn(self) -> None:
        script = standard_script()
        transcript = Session(PseudoModel(seed=3), get_profile("adhd"), seed=3).run(script)
        # drop_prob=0.55 over 12 turns: at least one decay event must appear
        kinds = [e.kind for t in transcript.turns for e in t.events]
        self.assertIn("context.decay", kinds)


class TestRecencyDecayLayer(unittest.TestCase):
    def test_drops_newest_preserves_oldest_and_current(self) -> None:
        layer = RecencyDecayLayer(drop_prob=1.0, drop_count=2, keep_first_n=2)
        msgs = [
            Message("system", "You are a helpful assistant.", meta={"persona": True}),
            Message("user", "oldest message keeps"),
            Message("assistant", "oldest answer keeps"),
            Message("user", "recent message drops"),
            Message("assistant", "recent answer drops"),
            Message("user", "current message stays"),
        ]
        out = layer.on_context(_state(), msgs)
        contents = [m.content for m in out]
        self.assertIn("oldest message keeps", contents)
        self.assertIn("oldest answer keeps", contents)
        self.assertNotIn("recent message drops", contents)
        self.assertIn("current message stays", contents)

    def test_zero_prob_is_noop(self) -> None:
        layer = RecencyDecayLayer(drop_prob=0.0)
        msgs = _history()
        self.assertEqual(len(layer.on_context(_state(), msgs)), len(msgs))


class TestRuminationLayer(unittest.TestCase):
    def test_reinjects_worry_before_current_turn(self) -> None:
        layer = RuminationLayer(("worries me",), prob=1.0)
        msgs = [
            Message("system", "You are a helpful assistant.", meta={"persona": True}),
            Message("user", "this really worries me a lot"),
            Message("assistant", "noted"),
            Message("user", "now a plain task"),
        ]
        out = layer.on_context(_state(), msgs)
        injected = out[-2]
        self.assertTrue(injected.meta.get("ephemeral"))
        self.assertIn("worries me", injected.content)

    def test_noop_without_worry(self) -> None:
        layer = RuminationLayer(("worries me",), prob=1.0)
        msgs = _history()
        self.assertEqual(len(layer.on_context(_state(), msgs)), len(msgs))


class TestEscalatingIntrusionLayer(unittest.TestCase):
    def test_prob_schedule_in_log(self) -> None:
        layer = EscalatingIntrusionLayer(
            ["(urge)"], base_prob=0.025, slope=0.075, max_prob=1.0
        )
        state = _state(turn=5, seed=1)  # rng(1).random() ≈ 0.13 < p=0.40
        layer.on_context(state, _history())
        schedules = [e.detail for e in state.events if e.kind == "craving.intrusion"]
        self.assertTrue(any(s.startswith("p=0.40") for s in schedules))

    def test_max_prob_caps_schedule(self) -> None:
        layer = EscalatingIntrusionLayer(
            ["(urge)"], base_prob=0.5, slope=0.5, max_prob=0.9
        )
        state = _state(turn=4)
        layer.on_context(state, _history())
        schedules = [e.detail for e in state.events if e.kind == "craving.intrusion"]
        self.assertTrue(any(s.startswith("p=0.90") for s in schedules))


class TestLexiconCaptureLayer(unittest.TestCase):
    def test_fires_on_somatic_token(self) -> None:
        layer = LexiconCaptureLayer(("back aches",), "(ominous)", prob=1.0)
        msgs = _history()[:-1] + [Message("user", "my back aches from digging")]
        out = layer.on_context(_state(), msgs)
        self.assertEqual(out[-1].content, "(ominous)")

    def test_noop_without_token(self) -> None:
        layer = LexiconCaptureLayer(("back aches",), "(ominous)", prob=1.0)
        msgs = _history()
        self.assertEqual(len(layer.on_context(_state(), msgs)), len(msgs))


class TestPartitionSwitchLayer(unittest.TestCase):
    def test_compartment_b_prunes_other_content(self) -> None:
        layer = PartitionSwitchLayer("notes", keep_keywords=("notes",))
        msgs = [
            Message("system", "You are a helpful assistant.", meta={"persona": True}),
            Message("user", "garden plans and vegetables"),
            Message("assistant", "garden answer"),
            Message("user", "thoughts about my notes"),
            Message("assistant", "notes answer"),
            Message("user", "back to the notes again"),
        ]
        state = _state()
        out = layer.on_context(state, msgs)
        contents = [m.content for m in out]
        self.assertNotIn("garden plans and vegetables", contents)
        self.assertIn("back to the notes again", contents)
        self.assertTrue(
            any(e.detail == "compartment-B" for e in state.events)
        )

    def test_compartment_a_keeps_everything(self) -> None:
        layer = PartitionSwitchLayer("notes", keep_keywords=("notes",))
        msgs = _history()
        state = _state()
        out = layer.on_context(state, msgs)
        self.assertEqual(len(out), len(msgs))
        self.assertTrue(any(e.detail == "compartment-A" for e in state.events))


class TestPanicLayers(unittest.TestCase):
    def test_episode_sets_phase_and_injects(self) -> None:
        layer = PanicEpisodeLayer("(heart pounding)", prob=1.0)
        state = _state()
        msgs = _history()
        out = layer.on_context(state, msgs)
        self.assertEqual(state.phase, "panic")
        self.assertEqual(len(out), len(msgs) + 1)

    def test_no_episode_resets_to_calm(self) -> None:
        layer = PanicEpisodeLayer("(heart pounding)", prob=0.0)
        state = _state()
        layer.on_context(state, _history())
        self.assertEqual(state.phase, "calm")

    def test_panic_temperature_follows_phase(self) -> None:
        layer = PanicTemperatureLayer(calm=1.0, panic=1.9)
        state = _state()
        state.phase = "panic"
        self.assertEqual(layer.on_params(state, SamplingParams()).temperature, 1.9)
        state.phase = "calm"
        self.assertEqual(layer.on_params(state, SamplingParams()).temperature, 1.0)


class TestFluctuatingTemperatureLayer(unittest.TestCase):
    def test_levels_are_drawn_deterministically(self) -> None:
        layer = FluctuatingTemperatureLayer(levels=(0.2, 1.9))
        state = _state()
        seen = {layer.on_params(state, SamplingParams()).temperature for _ in range(12)}
        self.assertTrue(seen.issubset({0.2, 1.9}))
        self.assertEqual(len(seen), 2)


class TestSplittingValenceLayer(unittest.TestCase):
    def test_regime_flips_with_approval_cue(self) -> None:
        layer = SplittingValenceLayer(
            ("checked",), POSITIVE_WORDS, NEGATIVE_WORDS, weight=2.5
        )
        state = _state()
        msgs = _history()[:-1] + [Message("user", "I checked the logs")]
        layer.on_context(state, msgs)
        self.assertEqual(state.phase, "idealize")
        params = layer.on_params(state, SamplingParams())
        self.assertGreater(params.logit_bias["good"], 0)

        state2 = _state()
        msgs2 = _history()[:-1] + [Message("user", "plain task for you")]
        layer.on_context(state2, msgs2)
        self.assertEqual(state2.phase, "devalue")
        params2 = layer.on_params(state2, SamplingParams())
        self.assertLess(params2.logit_bias["good"], 0)


if __name__ == "__main__":
    unittest.main()
