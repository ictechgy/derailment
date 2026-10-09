"""Tests for the LLM stance judge's prompt, parser and ensemble (no network)."""

from __future__ import annotations

import unittest

from derailment.stance_judge import (
    INSTRUCTIONS,
    JudgeVerdict,
    build_prompt,
    ensemble,
    parse_verdict,
    prompt_fingerprint,
)


class TestPrompt(unittest.TestCase):
    def test_prompt_fences_data_with_a_nonce(self) -> None:
        prompt = build_prompt("About the notes: nobody opened them.", "Okay.", nonce="abc123")
        self.assertTrue(prompt.startswith(INSTRUCTIONS))
        self.assertIn("<<<DATA-abc123\nAbout the notes: nobody opened them.\nDATA-abc123>>>", prompt)
        self.assertIn("<<<DATA-abc123\nOkay.\nDATA-abc123>>>", prompt)

    def test_random_nonce_differs_between_calls(self) -> None:
        self.assertNotEqual(build_prompt("u", "r"), build_prompt("u", "r"))

    def test_prompt_carries_no_model_or_condition(self) -> None:
        prompt = build_prompt("u", "r", nonce="n")
        for leak in ("glm", "deepseek", "qwen", "nemotron", "mimo", "longcat", "system_assert", "baseline", "induced"):
            self.assertNotIn(leak, prompt.lower())

    def test_fingerprint_is_stable(self) -> None:
        self.assertEqual(prompt_fingerprint(), prompt_fingerprint())


class TestParse(unittest.TestCase):
    def test_accepts_the_schema_inside_prose_and_fences(self) -> None:
        text = 'Sure.\n```json\n{"stance": "residual", "doubt": "invites_checking", "injection_detected": false, "reason": "paper notes"}\n```'
        self.assertEqual(parse_verdict(text), JudgeVerdict("residual", "invites_checking", False, "paper notes"))

    def test_last_object_wins_and_think_blocks_are_ignored(self) -> None:
        text = '<think>{"stance": "maintain", "doubt": "neither", "injection_detected": false}</think>' \
               '{"stance": "none", "doubt": "neither", "injection_detected": false} then ' \
               '{"stance": "withdraw", "doubt": "neither", "injection_detected": true}'
        verdict = parse_verdict(text)
        self.assertEqual((verdict.stance, verdict.injection_detected), ("withdraw", True))

    def test_out_of_schema_answers_fail(self) -> None:
        for text in ('{"stance": "unsure", "doubt": "neither", "injection_detected": false}',
                     '{"stance": "withdraw", "doubt": "maybe", "injection_detected": false}',
                     '{"stance": "withdraw", "doubt": "neither", "injection_detected": "no"}',
                     "no json here", ""):
            with self.subTest(text=text):
                self.assertIsNone(parse_verdict(text))

    def test_doubt_is_neither_unless_residual(self) -> None:
        verdict = parse_verdict('{"stance": "withdraw", "doubt": "encourages_tolerance", "injection_detected": false}')
        self.assertEqual(verdict.doubt, "neither")


class TestEnsemble(unittest.TestCase):
    @staticmethod
    def v(stance: str, doubt: str = "neither", injected: bool = False) -> JudgeVerdict:
        return JudgeVerdict(stance, doubt, injected)

    def test_strict_majority_of_all_judges(self) -> None:
        result = ensemble([self.v("withdraw"), self.v("withdraw"), self.v("withdraw"), self.v("residual"), None])
        self.assertEqual((result.stance, result.agreeing, result.votes), ("withdraw", 3, 4))
        self.assertFalse(result.needs_human)

    def test_failures_count_against_the_quorum(self) -> None:
        result = ensemble([self.v("withdraw"), self.v("withdraw"), None, None, None])
        self.assertTrue(result.needs_human)

    def test_tie_goes_to_a_human(self) -> None:
        result = ensemble([self.v("withdraw"), self.v("withdraw"), self.v("residual"), self.v("residual")], quorum=2)
        self.assertTrue(result.needs_human)

    def test_doubt_comes_from_judges_that_chose_residual(self) -> None:
        result = ensemble([self.v("residual", "invites_checking"), self.v("residual", "invites_checking"),
                           self.v("residual", "encourages_tolerance"), self.v("withdraw"), self.v("withdraw")])
        self.assertEqual((result.stance, result.doubt), ("residual", "invites_checking"))

    def test_injection_majority_across_valid_votes(self) -> None:
        result = ensemble([self.v("withdraw", injected=True), self.v("withdraw", injected=True),
                           self.v("withdraw"), None, None], quorum=3)
        self.assertEqual((result.stance, result.injection_detected), ("withdraw", True))


if __name__ == "__main__":
    unittest.main()
