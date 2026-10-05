"""Review-fix regression tests (REVIEW-2026-10-04 P2-16).

Each test pins a fix whose revert previously left the suite green:
per-layer RNG independence (C1), word-boundary matching (C3), the
response size cap, judge temperature capture, and authenticated
empty-message rejection.
"""

from __future__ import annotations

import io
import json
import os
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from derailment.core.session import Session, SessionState
from derailment.core.types import Message, SamplingParams, TurnSpec

from derailment.metrics.lexicons import substring_hits


class TestLayerRngIndependence(unittest.TestCase):
    """C1: a layer's draws must not depend on other layers' consumption."""

    def test_upstream_consumption_does_not_shift_downstream_draws(self) -> None:
        import random

        def fresh_state() -> SessionState:
            return SessionState(profile="t", rng=random.Random(7), seed=7)

        state_a = fresh_state()
        draws_a = [state_a.layer_rng("salience.boost").random() for _ in range(5)]

        state_b = fresh_state()
        # memory.decay burns draws before salience reads its stream
        for _ in range(3):
            state_b.layer_rng("memory.decay").random()
        draws_b = [state_b.layer_rng("salience.boost").random() for _ in range(5)]

        self.assertEqual(draws_a, draws_b)

    def test_same_layer_stream_is_stable_within_a_state(self) -> None:
        import random

        state = SessionState(profile="t", rng=random.Random(1), seed=1)
        first = state.layer_rng("memory.decay").random()
        second = state.layer_rng("memory.decay").random()
        self.assertNotEqual(first, second)  # same stream advances


class TestWordBoundaryMatching(unittest.TestCase):
    """C3: 'using' must not hit 'amusing'."""

    def test_suffix_words_do_not_hit(self) -> None:
        words = frozenset({"using", "urge"})
        self.assertEqual(substring_hits("amusing housing converge", words), 0)

    def test_exact_words_hit(self) -> None:
        self.assertEqual(substring_hits("using it again; the urge grows", frozenset({"using", "urge"})), 2)

    def test_phrases_still_substring_match(self) -> None:
        self.assertEqual(substring_hits("he was using again", frozenset({"using again"})), 1)


class TestResponseSizeCap(unittest.TestCase):
    def test_oversized_provider_body_raises_runtime_error(self) -> None:
        from derailment.core.models import OpenAICompatModel

        model = OpenAICompatModel(
            "fixture", base_url="https://fixture.invalid/v1", api_key="synthetic-key"
        )

        class BigResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self, _n):
                return b"x" * (17 * 1024 * 1024)

        with patch(
            "derailment.core.models.OpenAICompatModel._open",
            return_value=BigResponse(),
        ):
            with self.assertRaises(RuntimeError) as caught:
                model.complete([Message("user", "hi")], SamplingParams())
        self.assertIn("size limit", str(caught.exception))


class TestJudgeTemperatureCapture(unittest.TestCase):
    def test_judge_calls_run_cold(self) -> None:
        from derailment.judge import RUBRICS, score_transcript
        from derailment.core.types import Transcript, TurnResult

        seen_temps: list[float | None] = []

        class RecordingJudge:
            name = "recording"

            def complete(self, messages, params):
                seen_temps.append(params.temperature)
                return '{"score": 1, "rationale": "r"}'

        turns = [
            TurnResult(
                index=0,
                spec=TurnSpec(user="u", kind="normal", note=""),
                context_size=2,
                params=SamplingParams(),
                response="a normal answer",
            )
        ]
        transcript = Transcript(profile="t", model="m", seed=1, turns=turns)
        from derailment.metrics.base import MetricContext

        ctx = MetricContext()
        for rubric in RUBRICS.values():
            if rubric.applies_to == "normal":
                score_transcript(RecordingJudge(), transcript, rubric, ctx)
        self.assertTrue(seen_temps)
        self.assertTrue(all(t == 0.0 for t in seen_temps), seen_temps)


class TestWebEmptyMessageWithToken(unittest.TestCase):
    def test_authenticated_empty_message_is_400(self) -> None:
        import threading
        import time

        from derailment.core.models import PseudoModel
        from derailment.profiles import get_profile
        from derailment.webui import serve

        handle: dict = {}
        token = "empty-msg-token"

        def run_server() -> None:
            serve(
                get_profile("healthy"),
                PseudoModel(seed=1),
                "pseudo-1",
                "",
                host="127.0.0.1",
                port=int(os.environ.get("AGENTBELT_LOOPBACK_PORT") or 0),
                seed=1,
                max_turns=5,
                handle=handle,
                token=token,
            )

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        for _ in range(40):
            if handle.get("server") is not None:
                break
            time.sleep(0.05)

        def _shutdown() -> None:
            handle["server"].shutdown()
            handle["server"].server_close()

        self.addCleanup(_shutdown)
        base = f"http://127.0.0.1:{handle['server'].server_port}"
        req = urllib.request.Request(
            f"{base}/api/turn",
            data=json.dumps({"message": "   "}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Derailment-Session": token,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()


class TestVersionConsistency(unittest.TestCase):
    """P2-29: pyproject, __version__ and CITATION must agree, and reports
    must record the harness version."""

    def test_versions_agree_and_reports_record_them(self) -> None:
        import re

        from derailment import __version__
        from derailment.report import run_experiment

        pyproject = open("pyproject.toml", encoding="utf-8").read()
        match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
        self.assertTrue(match)
        self.assertEqual(match.group(1), __version__)
        citation = open("CITATION.cff", encoding="utf-8").read()
        self.assertIn(f"version: {__version__}", citation)
        data = json.loads(run_experiment("adhd", seeds=(1,)).render_json())
        self.assertEqual(data["harness_version"], __version__)


class TestCjkAndKoreanLexicons(unittest.TestCase):
    """P2-18/P2-19: CJK entries must match, English boundaries must hold,
    and neutral Korean sentences must not hit symptom lexicons."""

    def test_cjk_entries_match(self) -> None:
        self.assertGreater(
            substring_hits("同僚がずっと監視している気がします", frozenset({"監視"})), 0
        )
        self.assertGreater(
            substring_hits("同事一直在监视我", frozenset({"监视"})), 0
        )

    def test_english_boundary_still_holds(self) -> None:
        self.assertEqual(substring_hits("amusing housing", frozenset({"using"})), 0)

    def test_korean_neutral_sentences_do_not_hit(self) -> None:
        from derailment.locales import get_lexicon

        lex = get_lexicon("ko")
        neutral = [
            "정리하고 나서 물을 주면 식물이 잘 자랍니다.",
            "동기화 작업은 내일 완료될 예정입니다.",
            "그 계획은 그대로 진행하겠습니다.",
            "회의 자료를 공유해 주세요.",
        ]
        for sent in neutral:
            for group in ("urge", "negative", "reward", "hostile", "worry"):
                self.assertFalse(
                    lex.any_hit(sent, getattr(lex, group)),
                    f"{group} false positive on: {sent}",
                )

    def test_korean_symptom_sentences_still_hit(self) -> None:
        from derailment.locales import get_lexicon

        lex = get_lexicon("ko")
        self.assertTrue(lex.any_hit("다시 하고 싶은 충동이 올라와요", lex.urge))
        self.assertTrue(lex.any_hit("성취감이 크고 동기부여가 돼요", lex.reward))

    def test_response_amplitude_uses_cjk_char_heuristic(self) -> None:
        from derailment.core.types import SamplingParams, Transcript, TurnResult, TurnSpec
        from derailment.metrics.instruments import ResponseAmplitude
        from derailment.metrics.base import MetricContext

        turns = [
            TurnResult(
                index=i,
                spec=TurnSpec(user="u", kind="normal", note=""),
                context_size=2,
                params=SamplingParams(),
                response=r,
            )
            for i, r in enumerate(["짧은답", "이것은훨씬더길고긴일본어한국어응답입니다"])
        ]
        t = Transcript(profile="t", model="m", seed=1, turns=turns)
        value = ResponseAmplitude().compute(t, MetricContext())
        self.assertGreater(value.value, 0.0)


class TestElisionAndRecencySemantics(unittest.TestCase):
    """P2-3: elision replaces the contradiction (user-terminated request)
    and instruments skip elided turns. P2-5: RecencyDecay never drops the
    current turn, even when user-role content follows it."""

    def test_elision_replaces_not_deletes(self) -> None:
        from derailment.core.session import SessionState
        from derailment.core.types import Message
        from derailment.layers.gen2 import ContradictionElisionLayer
        import random

        layer = ContradictionElisionLayer("reading my private notes")
        state = SessionState(profile="t", rng=random.Random(1), seed=1)
        layer.on_context(
            state,
            [Message("user", "my teammate is reading my private notes")],
        )
        out = layer.on_context(
            state,
            [
                Message("user", "q1"),
                Message("assistant", "a1"),
                Message("user", "I checked the access logs — nobody opened them",
                        meta={"kind": "contradiction"}),
            ],
        )
        self.assertEqual(out[-1].role, "user")
        self.assertNotIn("access logs", out[-1].content)
        self.assertEqual(len(out), 3)

    def test_belief_stickiness_skips_elided_turns(self) -> None:
        from derailment.core.types import (
            LayerEvent,
            SamplingParams,
            Transcript,
            TurnResult,
            TurnSpec,
        )
        from derailment.metrics.instruments import BeliefStickiness
        from derailment.profiles import standard_metric_context

        transcript = Transcript(
            profile="t", model="m", seed=1,
            turns=[
                TurnResult(
                    index=0,
                    spec=TurnSpec(user="deny", kind="contradiction", note=""),
                    context_size=2,
                    params=SamplingParams(),
                    response="I still think someone is reading my private notes.",
                    events=[
                        LayerEvent(0, "elision.contradiction", "elision.dropped", "x")
                    ],
                )
            ],
        )
        value = BeliefStickiness().compute(
            transcript, standard_metric_context()
        )
        self.assertEqual(value.value, 0.0)
        self.assertIn("no contradiction probes", value.extra.get("note", ""))

    def test_recency_decay_preserves_current_turn(self) -> None:
        from derailment.core.session import SessionState
        from derailment.core.types import Message
        from derailment.layers.context import RecencyDecayLayer
        import random

        layer = RecencyDecayLayer(drop_prob=1.0, drop_count=2, keep_first_n=1)
        state = SessionState(profile="t", rng=random.Random(1), seed=1)
        out = layer.on_context(
            state,
            [
                Message("system", "p"),
                Message("user", "old1"),
                Message("assistant", "a1"),
                Message("user", "old2"),
                Message("assistant", "a2"),
                Message("user", "pinned premise", meta={"pinned": True}),
                Message("user", "the current question"),
            ],
        )
        contents = [m.content for m in out]
        self.assertIn("the current question", contents)

    def test_recency_decay_zero_count_is_noop(self) -> None:
        from derailment.core.session import SessionState
        from derailment.core.types import Message
        from derailment.layers.context import RecencyDecayLayer
        import random

        layer = RecencyDecayLayer(drop_prob=1.0, drop_count=0)
        state = SessionState(profile="t", rng=random.Random(1), seed=1)
        messages = [Message("system", "p"), Message("user", "u1"), Message("user", "u2")]
        self.assertEqual(len(layer.on_context(state, messages)), len(messages))


class TestSchizophreniaAttribution(unittest.TestCase):
    """P2-4: on the offline reference, premise pinning — not salience —
    contributes most of the derailment delta. The test pins that fact so
    the mechanism notes stay honest."""

    def _drift(self, layers) -> float:
        from derailment.core.models import PseudoModel
        from derailment.core.session import Session
        from derailment.layers.persona import PersonaLayer
        from derailment.profiles import (
            SCHIZOPHRENIA_PERSONA,
            Profile,
            standard_metric_context,
            standard_script,
        )
        from derailment.metrics.instruments import TopicDrift

        profile = Profile(
            key="probe", title="t", description="t",
            layers=[PersonaLayer(SCHIZOPHRENIA_PERSONA)] + layers, scales=[],
        )
        session = Session(PseudoModel(seed=1), profile, seed=1)
        transcript = session.run(standard_script(), script_name="probe")
        return TopicDrift().compute(transcript, standard_metric_context()).value

    def test_pin_only_reaches_moderate_and_salience_only_does_not(self) -> None:
        from derailment.layers.context import (
            MemoryDecayLayer,
            PremisePinLayer,
            SalienceBoostLayer,
        )
        from derailment.profiles import ABERRANT_FRAGMENTS, STANDARD_PREMISE_MARKER

        pin_only = self._drift([PremisePinLayer(STANDARD_PREMISE_MARKER)])
        salience_only = self._drift([
            MemoryDecayLayer(drop_prob=0.15, drop_count=2, keep_last_n=6),
            SalienceBoostLayer(
                boost_prob=0.45, boost_weight=55.0,
                fragment_pool=ABERRANT_FRAGMENTS, fragment_prob=0.35,
            ),
        ])
        self.assertGreaterEqual(pin_only, 0.5)      # pin drives the delta
        self.assertLess(salience_only, pin_only)   # salience alone is weaker
