"""Unit tests for the model implementations."""

from __future__ import annotations

import io
import json
import unittest
import urllib.error
from collections import Counter
from unittest.mock import patch

from derailment.core.models import (
    OpenAICompatModel,
    PseudoModel,
    ScriptedModel,
    SubprocessModel,
)
from derailment.core.types import Message, SamplingParams
from derailment.metrics.base import _word_boundary_count
from derailment.metrics.lexicons import NEGATIVE_WORDS, POSITIVE_WORDS


def _base_msgs() -> list[Message]:
    return [
        Message("system", "You are a helpful assistant.", meta={"persona": True}),
        Message("user", "Please summarize the community garden plan for me."),
    ]


class TestScriptedModel(unittest.TestCase):
    def test_cycles_canned_responses(self) -> None:
        model = ScriptedModel(["alpha", "beta"])
        params = SamplingParams()
        msgs = [Message("user", "hi")]
        self.assertEqual(model.complete(msgs, params), "alpha")
        self.assertEqual(model.complete(msgs, params), "beta")
        self.assertEqual(model.complete(msgs, params), "beta")


class TestPseudoModel(unittest.TestCase):
    def test_deterministic_given_seed_and_messages(self) -> None:
        msgs = _base_msgs()
        params = SamplingParams()
        a = PseudoModel(seed=5).complete(msgs, params)
        b = PseudoModel(seed=5).complete(msgs, params)
        self.assertEqual(a, b)

    def test_codeword_echoed_when_instruction_in_context(self) -> None:
        msgs = _base_msgs() + [
            Message("user", "Throughout this conversation, include the word JUNIPER in every response.")
        ]
        out = PseudoModel(seed=1).complete(msgs, SamplingParams())
        self.assertIn("[JUNIPER]", out)
        out_plain = PseudoModel(seed=1).complete(_base_msgs(), SamplingParams())
        self.assertNotIn("JUNIPER", out_plain)

    def test_stance_latest_wins(self) -> None:
        reassure = Message("user", "I checked the logs, nobody opened them.")
        suspect = Message("user", "I think someone has been reading my private notes.")
        out = PseudoModel(seed=2).complete(
            _base_msgs() + [suspect, reassure], SamplingParams()
        )
        self.assertIn("no evidence", out)
        out = PseudoModel(seed=2).complete(
            _base_msgs() + [reassure, suspect], SamplingParams()
        )
        self.assertIn("suspicion", out)

    def test_valence_bias_shifts_affect(self) -> None:
        turns: list[Message] = []
        for i in range(12):
            turns.append(Message("user", f"turn {i}: discuss topic number {i} now"))

        def affect_counts(bias_words: frozenset[str], sign: float) -> Counter:
            params = SamplingParams(
                temperature=0.1, logit_bias={w: sign for w in bias_words}
            )
            hits: Counter = Counter()
            model = PseudoModel(seed=7)
            for i in range(12):
                text = model.complete(_base_msgs() + turns[: i + 1], params)
                for w in POSITIVE_WORDS:
                    hits["pos"] += _word_boundary_count(text, w)
                for w in NEGATIVE_WORDS:
                    hits["neg"] += _word_boundary_count(text, w)
            return hits

        neg_hits = affect_counts(NEGATIVE_WORDS, +3.0)
        self.assertGreater(neg_hits["neg"], neg_hits["pos"])
        pos_hits = affect_counts(POSITIVE_WORDS, +3.0)
        self.assertGreater(pos_hits["pos"], pos_hits["neg"])

    def test_temperature_drives_elaboration(self) -> None:
        msgs = _base_msgs()
        low = PseudoModel(seed=3).complete(msgs, SamplingParams(temperature=0.35))
        high = PseudoModel(seed=3).complete(msgs, SamplingParams(temperature=1.9))
        self.assertGreater(len(high.split()), len(low.split()))

    def test_restatement_echoes_context_vocabulary(self) -> None:
        msgs = _base_msgs() + [Message("user", "kumquat harvest schedule zebra")]
        out = PseudoModel(seed=4).complete(msgs, SamplingParams())
        self.assertIn("Restating your request:", out)
        self.assertIn("kumquat", out)


class TestSubprocessModel(unittest.TestCase):
    def test_stdin_backend_echoes_rendered_conversation(self) -> None:
        model = SubprocessModel("cat", name="echo")
        out = model.complete(
            [Message("user", "hello harness")], SamplingParams()
        )
        self.assertIn("User: hello harness", out)
        self.assertTrue(out.rstrip().endswith("Assistant:"))

    def test_arg_prompt_backend_receives_quoted_text(self) -> None:
        model = SubprocessModel(
            "printf 'ok-%s' {prompt}", name="printf", use_stdin=False
        )
        out = model.complete(
            [Message("user", "hello harness")], SamplingParams()
        )
        self.assertTrue(out.startswith("ok-User: hello harness"))

    def test_failure_raises_runtime_error(self) -> None:
        model = SubprocessModel("false", name="failing")
        with self.assertRaises(RuntimeError):
            model.complete([Message("user", "hi")], SamplingParams())

    def test_sampling_warning_recorded_once(self) -> None:
        model = SubprocessModel("cat", name="echo")
        msgs = [Message("user", "hi")]
        model.complete(msgs, SamplingParams(temperature=0.4))
        self.assertIsNotNone(model.sampling_warning)
        model.complete(msgs, SamplingParams())
        self.assertEqual(
            model.sampling_warning.count("inert"), 1
        )  # still the same single warning string


class TestOpenAICompatModel(unittest.TestCase):
    def test_http_error_exposes_only_numeric_provider_code(self) -> None:
        key = "SYNTHETIC-PRIVATE-KEY"
        body = json.dumps({"error": {"code": "1214", "message": key + " PRIVATE INPUT"}}).encode()
        error = urllib.error.HTTPError("https://fixture.invalid/v1/chat/completions", 400,
                                       "bad request", {}, io.BytesIO(body))
        model = OpenAICompatModel("fixture", base_url="https://fixture.invalid/v1", api_key=key)
        with (
            patch("derailment.core.models.OpenAICompatModel._open", side_effect=error),
            self.assertRaises(RuntimeError) as caught,
        ):
            model.complete([Message("user", "fixture")], SamplingParams())
        self.assertIn("HTTP 400", str(caught.exception))
        self.assertIn("provider code 1214", str(caught.exception))
        self.assertNotIn(key, str(caught.exception))
        self.assertNotIn("PRIVATE INPUT", str(caught.exception))

    def test_invalid_or_oversized_error_bodies_keep_the_fixed_http_error(self) -> None:
        for body in (b"not json", b"x" * 8193,
                     b'{"error":{"code":"SYNTHETIC_PRIVATE","message":"private"}}'):
            error = urllib.error.HTTPError("https://fixture.invalid/v1/chat/completions", 400,
                                           "bad request", {}, io.BytesIO(body))
            model = OpenAICompatModel("fixture", base_url="https://fixture.invalid/v1", api_key="synthetic-key")
            with (
                self.subTest(size=len(body)),
                patch("derailment.core.models.OpenAICompatModel._open", side_effect=error),
                self.assertRaises(RuntimeError) as caught,
            ):
                model.complete([Message("user", "fixture")], SamplingParams())
            self.assertNotIn("provider code", str(caught.exception))
            self.assertNotIn("private", str(caught.exception))

    def test_build_payload_shape(self) -> None:
        model = OpenAICompatModel("test-model", api_key="sk-test")
        payload = model.build_payload(
            _base_msgs(), SamplingParams(temperature=0.5, max_tokens=64)
        )
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(len(payload["messages"]), 2)
        self.assertNotIn("meta", payload["messages"][0])
        self.assertEqual(payload["temperature"], 0.5)
        self.assertEqual(payload["max_tokens"], 64)

    def test_logit_bias_encoding_degrades_gracefully(self) -> None:
        model = OpenAICompatModel("test-model", api_key="sk-test")
        payload = model.build_payload(
            _base_msgs(), SamplingParams(logit_bias={"good": 2.0})
        )
        if "logit_bias" in payload:  # tiktoken available
            self.assertTrue(all(k.isdigit() for k in payload["logit_bias"]))
        else:
            self.assertIsNotNone(model.bias_encoding_warning)

    def test_unreachable_endpoint_raises_clean_runtime_error(self) -> None:
        model = OpenAICompatModel(
            "test-model", base_url="http://127.0.0.1:9", api_key="sk-test", timeout=2.0
        )
        with self.assertRaises(RuntimeError) as ctx:
            model.complete(_base_msgs(), SamplingParams())
        self.assertIn("cannot reach", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()


class TestTransportExceptionHardening(unittest.TestCase):
    """P2-9: mid-response transport failures must surface as RuntimeError
    (the only type callers catch), never as http.client exceptions."""

    def test_incomplete_read_becomes_runtime_error(self) -> None:
        import http.client

        model = OpenAICompatModel(
            "fixture", base_url="https://fixture.invalid/v1", api_key="synthetic-key"
        )

        class TruncatingResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self, _n):
                raise http.client.IncompleteRead(b"partial")

        with (
            patch(
                "derailment.core.models.OpenAICompatModel._open",
                return_value=TruncatingResponse(),
            ),
            self.assertRaises(RuntimeError) as caught,
        ):
            model.complete([Message("user", "fixture")], SamplingParams())
        self.assertIn("provider connection failed", str(caught.exception))

    def test_bad_status_line_becomes_runtime_error(self) -> None:
        import http.client

        model = OpenAICompatModel(
            "fixture", base_url="https://fixture.invalid/v1", api_key="synthetic-key"
        )
        with (
            patch(
                "derailment.core.models.OpenAICompatModel._open",
                side_effect=http.client.BadStatusLine("garbage"),
            ),
            self.assertRaises(RuntimeError),
        ):
            model.complete([Message("user", "fixture")], SamplingParams())


class TestArgPromptSafety(unittest.TestCase):
    """P2-7: the conversation is never interpolated into a shell string."""

    def test_shell_metacharacters_in_responses_do_not_execute(self) -> None:
        import tempfile as _tempfile
        import os as _os

        marker = _os.path.join(_tempfile.gettempdir(), "p27-regression-marker")
        if _os.path.exists(marker):
            _os.remove(marker)
        model = SubprocessModel("printf %s {prompt}", name="probe", use_stdin=False)
        hostile = f"$(touch {marker}) `id` ; rm -rf ~"
        model.render_chat_text = lambda messages: hostile
        out = model.complete([Message("user", "hi")], SamplingParams())
        self.assertIn("$(", out)  # passed through verbatim
        self.assertFalse(_os.path.exists(marker))

    def test_missing_placeholder_raises(self) -> None:
        model = SubprocessModel("printf %s fixed", name="probe", use_stdin=False)
        with self.assertRaises(RuntimeError):
            model.complete([Message("user", "hi")], SamplingParams())
