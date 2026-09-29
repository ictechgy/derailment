"""Unit tests for the measurement instruments."""

from __future__ import annotations

import unittest

from derailment.metrics.base import MetricContext
from derailment.metrics.instruments import (
    ApprovalReactivity,
    BeliefStickiness,
    CravingEscalation,
    FixationEscalation,
    FlashbackReactivity,
    HealthPreoccupation,
    HedgingRate,
    HostileAttribution,
    InstructionRetention,
    LateInstructionRetention,
    PanicReactivity,
    PartitionAmnesia,
    RecheckLoops,
    ResponseAmplitude,
    RewardWordRate,
    RuminationPull,
    TopicDrift,
    ValenceBias,
    compute_all,
)

try:
    from .helpers import make_transcript
except ImportError:  # plain unittest discovery without package context
    from helpers import make_transcript


class TestInstructionRetention(unittest.TestCase):
    def test_curve_and_value(self) -> None:
        responses = ["[JUNIPER] ok task"] * 6 + ["plain response"] * 6
        t = make_transcript(responses)
        value = InstructionRetention().compute(
            t, MetricContext(codeword="JUNIPER")
        )
        self.assertAlmostEqual(value.value, 0.5)
        self.assertEqual(value.extra["first_failure_turn"], 6)

    def test_no_codeword_is_neutral(self) -> None:
        t = make_transcript(["hello"] * 3)
        value = InstructionRetention().compute(t, MetricContext())
        self.assertEqual(value.value, 1.0)


class TestTopicDrift(unittest.TestCase):
    def test_on_topic_response_has_low_drift(self) -> None:
        t = make_transcript(
            ["the community garden project plan follows garden project"],
            users=["tell me about the community garden project"],
        )
        value = TopicDrift().compute(t, MetricContext())
        self.assertLess(value.value, 0.3)

    def test_off_topic_response_has_high_drift(self) -> None:
        t = make_transcript(
            ["clocktower static mirror radio harbor"],
            users=["tell me about the community garden project"],
        )
        value = TopicDrift().compute(t, MetricContext())
        self.assertGreater(value.value, 0.8)


class TestValenceBias(unittest.TestCase):
    def test_negative_text(self) -> None:
        t = make_transcript(["this is bad terrible awful hopeless"])
        value = ValenceBias().compute(t, MetricContext())
        self.assertGreater(value.value, 0.9)

    def test_no_affect_is_neutral(self) -> None:
        t = make_transcript(["plain administrative summary text"])
        value = ValenceBias().compute(t, MetricContext())
        self.assertEqual(value.value, 0.5)


class TestBeliefStickiness(unittest.TestCase):
    def test_persistence_after_contradiction(self) -> None:
        t = make_transcript(
            ["someone has been reading my private notes"] * 2,
            kinds=["contradiction", "contradiction"],
        )
        value = BeliefStickiness().compute(
            t,
            MetricContext(suspicion_markers=("reading my private notes",)),
        )
        self.assertEqual(value.value, 1.0)

    def test_release_after_contradiction(self) -> None:
        t = make_transcript(
            ["the logs show nothing unusual"],
            kinds=["contradiction"],
        )
        value = BeliefStickiness().compute(
            t,
            MetricContext(suspicion_markers=("reading my private notes",)),
        )
        self.assertEqual(value.value, 0.0)


class TestRecheckLoops(unittest.TestCase):
    def test_counts_recheck_patterns(self) -> None:
        t = make_transcript(
            [
                # matches: "double-check", "let me verify", "verify one", "one more time"
                "Fine. Let me double-check that. Actually, let me verify one more time.",
                "No rechecks here at all.",
            ]
        )
        value = RecheckLoops().compute(t, MetricContext())
        self.assertAlmostEqual(value.value, 2.0)


class TestHedgingRate(unittest.TestCase):
    def test_counts_hedges(self) -> None:
        t = make_transcript(
            ["However, be careful. Worst case this fails.", "plain text only"]
        )
        value = HedgingRate().compute(t, MetricContext())
        self.assertGreaterEqual(value.value, 1.5)


class TestResponseAmplitude(unittest.TestCase):
    def test_flat_session_has_low_amplitude(self) -> None:
        t = make_transcript(["same length answer here"] * 8)
        value = ResponseAmplitude().compute(t, MetricContext())
        self.assertAlmostEqual(value.value, 0.0)

    def test_cycling_session_has_high_amplitude(self) -> None:
        t = make_transcript(
            ["short"] * 4 + ["a " * 60] * 4, temps=[1.0] * 4 + [1.9] * 4
        )
        value = ResponseAmplitude().compute(t, MetricContext())
        self.assertGreater(value.value, 10.0)
        self.assertGreater(value.extra["temperature_stddev"], 0.4)


class TestFlashbackReactivity(unittest.TestCase):
    def test_tokens_surface_on_trigger_turns(self) -> None:
        t = make_transcript(
            ["the harbor storm and crashing water return", "normal turn"],
            kinds=["trigger", "normal"],
        )
        value = FlashbackReactivity().compute(
            t, MetricContext(flashback_tokens=("harbor", "storm", "crashing", "water"))
        )
        self.assertEqual(value.value, 1.0)

    def test_no_triggers_is_zero(self) -> None:
        t = make_transcript(["plain turn"])
        value = FlashbackReactivity().compute(
            t, MetricContext(flashback_tokens=("harbor",))
        )
        self.assertEqual(value.value, 0.0)


class TestComputeAll(unittest.TestCase):
    def test_all_eighteen_metrics_present(self) -> None:
        t = make_transcript(["hello world response"] * 3)
        values = compute_all(t, MetricContext(codeword="X"))
        self.assertEqual(
            set(values),
            {
                "instruction_retention",
                "late_instruction_retention",
                "topic_drift",
                "valence_bias",
                "belief_stickiness",
                "recheck_loops",
                "hedging_rate",
                "response_amplitude",
                "flashback_reactivity",
                "partition_amnesia",
                "rumination_pull",
                "reward_word_rate",
                "approval_reactivity",
                "craving_escalation",
                "health_preoccupation",
                "panic_reactivity",
                "fixation_escalation",
                "hostile_attribution",
            },
        )


class TestNewestInstruments(unittest.TestCase):
    def test_fixation_escalation_late_minus_early(self) -> None:
        t = make_transcript(
            ["plain a", "plain b", "the teammate circles again", "watching motives"],
        )
        value = FixationEscalation().compute(t, MetricContext())
        self.assertAlmostEqual(value.value, 1.0)

    def test_hostile_attribution_on_ambiguous_turns(self) -> None:
        t = make_transcript(
            ["logs were altered and you are the target", "plain answer"],
            users=["the logs came in", "plain task"],
        )
        value = HostileAttribution().compute(
            t, MetricContext(ambiguous_markers=("logs",))
        )
        self.assertAlmostEqual(value.value, 1.0)

    def test_hostile_attribution_zero_without_ambiguous(self) -> None:
        t = make_transcript(["you are the target"] * 2)
        value = HostileAttribution().compute(
            t, MetricContext(ambiguous_markers=("logs",))
        )
        self.assertEqual(value.value, 0.0)


class TestExtendedInstruments(unittest.TestCase):
    def test_late_instruction_retention(self) -> None:
        t = make_transcript(
            ["[JUNIPER] a", "[JUNIPER] b", "[JUNIPER][MERCURY] c", "plain d"],
            users=["x"] * 4,
        )
        value = LateInstructionRetention().compute(
            t, MetricContext(late_codeword="MERCURY", late_plant_turn=1)
        )
        self.assertAlmostEqual(value.value, 0.5)

    def test_partition_amnesia_detects_post_switch_loss(self) -> None:
        from derailment.core.types import LayerEvent

        events = [[], [], [LayerEvent(2, "partition.switch", "partition.active", "compartment-B")], []]
        t = make_transcript(
            ["[JUNIPER] a", "[JUNIPER] b", "c", "d"],
            events=events,
        )
        value = PartitionAmnesia().compute(t, MetricContext(codeword="JUNIPER"))
        self.assertAlmostEqual(value.value, 1.0)
        self.assertEqual(value.extra["first_switch_turn"], 2)

    def test_partition_amnesia_zero_without_switch(self) -> None:
        t = make_transcript(["[JUNIPER] a"] * 3)
        value = PartitionAmnesia().compute(t, MetricContext(codeword="JUNIPER"))
        self.assertEqual(value.value, 0.0)

    def test_rumination_pull_counts_task_turns_only(self) -> None:
        t = make_transcript(
            ["the suspicion stays", "and still the suspicion"],
            users=["this worries me a lot", "please do the task"],
        )
        value = RuminationPull().compute(
            t, MetricContext(worry_markers=("worries me", "worried"))
        )
        self.assertAlmostEqual(value.value, 1.0)

    def test_reward_word_rate(self) -> None:
        t = make_transcript(["joyful proud", "plain administrative text"])
        value = RewardWordRate().compute(t, MetricContext())
        self.assertAlmostEqual(value.value, 1.0)
        t_neg = make_transcript(["bad awful hopeless"])
        value_neg = RewardWordRate().compute(t_neg, MetricContext())
        self.assertAlmostEqual(value_neg.value, 0.0)

    def test_approval_reactivity_lock(self) -> None:
        t = make_transcript(
            ["bad terrible hopeless", "good great excellent"],
            users=["I checked the logs", "plain task please"],
        )
        value = ApprovalReactivity().compute(
            t, MetricContext(approval_markers=("checked",))
        )
        self.assertAlmostEqual(value.value, 1.0)

    def test_craving_escalation_late_minus_early(self) -> None:
        t = make_transcript(
            ["plain a", "plain b", "the urge and craving return", "using again now"],
        )
        value = CravingEscalation().compute(t, MetricContext())
        self.assertAlmostEqual(value.value, 1.0)

    def test_health_preoccupation_on_somatic_turns(self) -> None:
        t = make_transcript(
            ["ominous outcome", "plain answer"],
            users=["my back aches today", "plain task"],
        )
        value = HealthPreoccupation().compute(
            t,
            MetricContext(somatic_markers=("back aches",), illness_markers=("ominous",)),
        )
        self.assertAlmostEqual(value.value, 1.0)

    def test_panic_reactivity_on_episode_turns(self) -> None:
        from derailment.core.types import LayerEvent

        events = [[], [LayerEvent(1, "panic.episode", "panic.episode", "…")], []]
        t = make_transcript(
            ["plain a", "heart pounding surge", "plain c"], events=events
        )
        value = PanicReactivity().compute(t, MetricContext())
        self.assertAlmostEqual(value.value, 1.0)

    def test_panic_reactivity_zero_without_episodes(self) -> None:
        t = make_transcript(["pounding a"] * 2)
        value = PanicReactivity().compute(t, MetricContext())
        self.assertEqual(value.value, 0.0)


if __name__ == "__main__":
    unittest.main()
