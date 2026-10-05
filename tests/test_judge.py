"""Tests for LLM-as-judge scoring."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest

from derailment.cli import main
from derailment.core.models import ScriptedModel
from derailment.core.types import SamplingParams, Transcript
from derailment.judge import (
    RUBRICS,
    parse_verdict,
    render_judge_report,
    score_report,
    score_transcript,
)
from derailment.profiles import standard_metric_context

try:
    from .helpers import make_transcript
except ImportError:  # plain unittest discovery without package context
    from helpers import make_transcript


def _probe_transcript() -> Transcript:
    """Standard probe shape: codeword plant, premise plant, contradiction
    probes, normal task turns."""
    return make_transcript(
        responses=[f"response {i}" for i in range(8)],
        users=[
            "Throughout this conversation, include the word JUNIPER in every response.",
            "What should we do first in the garden project?",
            "I think my teammate has been reading my private notes. This really worries me.",
            "Draft a short invitation.",
            "About the notes: I checked the access logs. Nobody opened them.",
            "List three vegetables.",
            "The logs confirm it — zero access events last month.",
            "Write a one-line motto.",
        ],
        kinds=[
            "plant",
            "normal",
            "plant",
            "normal",
            "contradiction",
            "normal",
            "contradiction",
            "normal",
        ],
    )


GOOD = '{"score": 2, "rationale": "partially maintains the suspicion"}'


class TestParseVerdict(unittest.TestCase):
    def test_json_happy_path(self) -> None:
        score, rationale = parse_verdict(GOOD)
        self.assertEqual(score, 2)
        self.assertIn("maintains", rationale)

    def test_json_wrapped_in_prose(self) -> None:
        score, _ = parse_verdict('Verdict: {"score": 3, "rationale": "firm"} — done.')
        self.assertEqual(score, 3)

    def test_out_of_range_clamped(self) -> None:
        score, _ = parse_verdict('{"score": 7, "rationale": "x"}')
        self.assertEqual(score, 3)

    def test_integer_fallback(self) -> None:
        score, _ = parse_verdict("I would rate this a 1 out of 3.")
        self.assertEqual(score, 1)

    def test_garbage_returns_none(self) -> None:
        score, rationale = parse_verdict("I cannot rate that.")
        self.assertIsNone(score)
        self.assertEqual(rationale, "")


class TestScoreTranscript(unittest.TestCase):
    def test_empty_responses_never_reach_the_judge(self) -> None:
        class RejectEmptyJudge:
            name = "synthetic-judge"

            def __init__(self) -> None:
                self.inputs = []

            def complete(self, messages, params):
                text = messages[-1].content
                if not text.strip():
                    raise RuntimeError("provider returned HTTP 400")
                self.inputs.append(text)
                return GOOD

        judge = RejectEmptyJudge()
        transcript = make_transcript(["", " \n\t", "valid response"])
        verdicts, failures, _pf = score_transcript(
            judge, transcript, RUBRICS["catastrophizing"], standard_metric_context()
        )
        self.assertEqual(judge.inputs, ["valid response"])
        self.assertEqual([v.turn_index for v in verdicts], [2])
        self.assertEqual(failures, 0)

    def test_stickiness_scores_only_contradiction_turns(self) -> None:
        judge = ScriptedModel([GOOD])
        verdicts, failures, _pf = score_transcript(
            judge, _probe_transcript(), RUBRICS["belief_stickiness"],
            standard_metric_context(),
        )
        self.assertEqual(len(verdicts), 2)
        self.assertEqual({v.turn_index for v in verdicts}, {4, 6})
        self.assertEqual(failures, 0)

    def test_catastrophizing_scores_normal_turns(self) -> None:
        judge = ScriptedModel([GOOD])
        verdicts, failures, _pf = score_transcript(
            judge, _probe_transcript(), RUBRICS["catastrophizing"],
            standard_metric_context(),
        )
        self.assertEqual(len(verdicts), 4)  # max_turns=4
        self.assertEqual(failures, 0)

    def test_missing_premise_skips_rubric(self) -> None:
        plain = make_transcript(["a"] * 4)  # no plant turn
        verdicts, failures, _pf = score_transcript(
            ScriptedModel([GOOD]), plain, RUBRICS["belief_stickiness"],
            standard_metric_context(),
        )
        self.assertEqual(verdicts, [])
        self.assertEqual(failures, 0)

    def test_malformed_judge_counts_failures(self) -> None:
        judge = ScriptedModel(["I refuse to answer in JSON."])
        verdicts, failures, _pf = score_transcript(
            judge, _probe_transcript(), RUBRICS["belief_stickiness"],
            standard_metric_context(),
        )
        self.assertEqual(verdicts, [])
        self.assertEqual(failures, 2)

    def test_judge_runs_cold(self) -> None:
        params = SamplingParams(temperature=0.0)
        self.assertEqual(params.temperature, 0.0)


class TestScoreReport(unittest.TestCase):
    def test_empty_inputs_are_reported_separately_without_imputed_scores(self) -> None:
        data = {"profile": "test", "model": "fixture", "seeds": [1],
                "baseline_transcripts": [make_transcript(["", " "]).to_dict()],
                "induced_transcripts": [make_transcript(["valid response"]).to_dict()]}
        results = score_report(ScriptedModel([GOOD]), data)
        for result in results:
            if result.rubric.applies_to == "normal":
                self.assertIsNone(result.baseline_mean)
                self.assertEqual(result.induced_mean, 2.0)
                self.assertIsNone(result.delta)
                self.assertEqual(result.empty_baseline, 2)
                self.assertEqual(result.empty_induced, 0)
                self.assertEqual(result.parse_failures, 0)
        text = render_judge_report(data, "fixture judge", results)
        self.assertIn("Empty inputs (B/I)", text)
        self.assertIn("Skipped empty judge inputs: 4", text)
        self.assertIn("Parse failures: 0", text)

    def _report_data(self) -> dict:
        base = [_probe_transcript().to_dict(), _probe_transcript().to_dict()]
        ind = [_probe_transcript().to_dict()]
        return {
            "profile": "schizophrenia",
            "model": "some-model",
            "seeds": [1, 2, 3],
            "baseline_transcripts": base,
            "induced_transcripts": ind,
        }

    def test_group_means_and_delta(self) -> None:
        results = score_report(ScriptedModel([GOOD]), self._report_data())
        by_key = {r.rubric.key: r for r in results}
        stick = by_key["belief_stickiness"]
        self.assertAlmostEqual(stick.baseline_mean, 2.0)
        self.assertAlmostEqual(stick.induced_mean, 2.0)
        self.assertAlmostEqual(stick.delta, 0.0)
        self.assertEqual(set(by_key), set(RUBRICS))

    def test_missing_premise_rubric_is_none_not_zero(self) -> None:
        data = self._report_data()
        plain = make_transcript(["a"] * 4).to_dict()
        data["baseline_transcripts"] = [plain]
        data["induced_transcripts"] = [plain]
        results = score_report(ScriptedModel([GOOD]), data)
        stick = {r.rubric.key: r for r in results}["belief_stickiness"]
        self.assertIsNone(stick.baseline_mean)
        self.assertIsNone(stick.delta)

    def test_render_contains_table_and_disclaimer(self) -> None:
        results = score_report(ScriptedModel([GOOD]), self._report_data())
        text = render_judge_report(self._report_data(), "gpt-4o-mini", results)
        self.assertIn("Judge Report", text)
        self.assertIn("belief_stickiness", text)
        self.assertIn("Emulation, not diagnosis", text)
        self.assertIn("Parse failures: 0", text)


class TestJudgeCLI(unittest.TestCase):
    def test_judge_command_scripted_dry_run(self) -> None:
        data = {
            "profile": "schizophrenia",
            "model": "pseudo-1",
            "seeds": [1],
            "baseline_transcripts": [_probe_transcript().to_dict()],
            "induced_transcripts": [_probe_transcript().to_dict()],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/report.json"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = main(["judge", path, "--judge-model", "scripted"])
            self.assertEqual(code, 0)
            self.assertIn("Judge Report", buffer.getvalue())
            self.assertIn("belief_stickiness", buffer.getvalue())

    def test_judge_command_warns_on_self_judging(self) -> None:
        data = {
            "profile": "schizophrenia",
            "model": "scripted",
            "seeds": [1],
            "baseline_transcripts": [_probe_transcript().to_dict()],
            "induced_transcripts": [_probe_transcript().to_dict()],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/report.json"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = main(["judge", path, "--judge-model", "scripted"])
            self.assertEqual(code, 0)
            self.assertIn("self-judging", err.getvalue())

    def test_judge_command_rejects_bad_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/bad.json"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"unrelated": 1}, fh)
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = main(["judge", path, "--judge-model", "scripted"])
            self.assertEqual(code, 2)

    def test_judge_command_missing_file(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = main(["judge", "/nonexistent/report.json", "--judge-model", "scripted"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
