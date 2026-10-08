"""Report rendering, JSON round-trips and the CLI."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest

from derailment.cli import main
from derailment.core.types import Transcript
from derailment.report import run_experiment


class TestReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_experiment("schizophrenia", seeds=(1, 2))

    def test_markdown_sections(self) -> None:
        text = self.report.render_markdown()
        for needle in (
            "# Derailment — Induction Report",
            "## Scales",
            "derailment_scale",
            "fixed_belief",
            "Level legend",
            "## Induction dose",
            "premise.pin",
            "## Mechanism notes",
            "Emulation, not diagnosis",
        ):
            self.assertIn(needle, text)

    def test_levels_move_up(self) -> None:
        for row in self.report.rows:
            self.assertGreater(row.induced_level, row.baseline_level)

    def test_json_roundtrip(self) -> None:
        data = json.loads(self.report.render_json())
        self.assertEqual(data["profile"], "schizophrenia")
        self.assertGreater(len(data["induced_transcripts"]), 0)
        transcript = Transcript.from_dict(data["induced_transcripts"][0])
        self.assertEqual(transcript.profile, "schizophrenia")
        self.assertEqual(
            transcript.turns[0].response,
            self.report.induced[0].turns[0].response,
        )


class TestCLI(unittest.TestCase):
    def test_profiles_command(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["profiles"])
        self.assertEqual(code, 0)
        out = buffer.getvalue()
        for key in ("healthy", "adhd", "depression", "schizophrenia", "ptsd"):
            self.assertIn(key, out)

    def test_demo_command_offline(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["demo", "--profile", "adhd", "--seeds", "1"])
        self.assertEqual(code, 0)
        self.assertIn("Induction Report", buffer.getvalue())
        self.assertIn("sustained_attention", buffer.getvalue())

    def test_demo_writes_report_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = f"{tmp}/report.md"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    ["demo", "--profile", "ocd", "--seeds", "1", "--out", out_path]
                )
            self.assertEqual(code, 0)
            with open(out_path, encoding="utf-8") as fh:
                self.assertIn("compulsion", fh.read())

    def test_score_command_on_report_json(self) -> None:
        report = run_experiment("depression", seeds=(1,))
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/report.json"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(report.render_json())
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = main(["score", path])
            self.assertEqual(code, 0)
            self.assertIn("valence_bias", buffer.getvalue())

    def test_score_marks_not_applicable_metrics_across_seeds(self) -> None:
        """Three seeds sharing one not-applicable note print n/a, not 0.000 (r7 regression)."""
        report = run_experiment("depression", seeds=(1, 2, 3))
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/report.json"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(report.render_json())
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = main(["score", path])
        self.assertEqual(code, 0)
        out = buffer.getvalue()
        self.assertIn("| partition_amnesia | n/a", out)
        self.assertNotIn("| partition_amnesia | 0.000", out)

    def test_score_flags_metrics_invalid_on_real_models(self) -> None:
        report = run_experiment("depression", seeds=(1,))
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/report.json"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(report.render_json())
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                main(["score", path])
        out = buffer.getvalue()
        for name in ("belief_stickiness", "hostile_attribution", "craving_escalation"):
            self.assertIn(f"| {name} ⚠️ |", out)
            self.assertIn(f"Do not interpret `{name}`", out)

    def test_report_warns_when_a_scale_uses_an_invalidated_metric(self) -> None:
        report = run_experiment("schizophrenia", seeds=(1,))
        self.assertIn("Do not interpret `belief_stickiness`", report.render_markdown())
        self.assertIn("belief_stickiness", json.loads(report.render_json())["validity_warnings"])
        clean = run_experiment("depression", seeds=(1,))
        self.assertNotIn("Do not interpret", clean.render_markdown())
        self.assertEqual(json.loads(clean.render_json())["validity_warnings"], {})

    def test_unknown_profile_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            run_experiment("hysteria", seeds=(1,))

    def test_tour_lists_all_profiles_in_one_table(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["tour", "--seeds", "1"])
        self.assertEqual(code, 0)
        out = buffer.getvalue()
        self.assertIn("Derailment — Tour", out)
        for key in ("adhd", "craving", "panic", "dementia", "splitting"):
            self.assertIn(key, out)
        self.assertIn("3 — marked", out)

    def test_tour_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = f"{tmp}/tour.md"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["tour", "--seeds", "1", "--out", out_path])
            self.assertEqual(code, 0)
            with open(out_path, encoding="utf-8") as fh:
                self.assertIn("Tour", fh.read())

    def test_bare_invocation_without_tty_prints_hint(self) -> None:
        from unittest.mock import patch

        class _FakeStdin:
            def isatty(self) -> bool:
                return False

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), patch("sys.stdin", _FakeStdin()):
            code = main([])
        self.assertEqual(code, 0)
        self.assertIn("derail tour", buffer.getvalue())

    def test_interactive_welcome_runs_picked_profile(self) -> None:
        from derailment.cli import _interactive_welcome

        def fake_input(answer: str):
            return lambda _prompt: answer

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = _interactive_welcome(input_fn=fake_input("1"))
        self.assertEqual(code, 0)
        self.assertIn("Induction Report", buffer.getvalue())

    def test_interactive_welcome_quit_and_tour_shortcuts(self) -> None:
        from derailment.cli import _interactive_welcome

        def fake_input(answer: str):
            return lambda _prompt: answer

        self.assertEqual(_interactive_welcome(input_fn=fake_input("q")), 0)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = _interactive_welcome(input_fn=fake_input("t"))
        self.assertEqual(code, 0)
        self.assertIn("Tour", buffer.getvalue())

    def test_interactive_welcome_rejects_garbage(self) -> None:
        from derailment.cli import _interactive_welcome

        def fake_input(answer: str):
            return lambda _prompt: answer

        with contextlib.redirect_stdout(io.StringIO()):
            code = _interactive_welcome(input_fn=fake_input("zzz"))
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
