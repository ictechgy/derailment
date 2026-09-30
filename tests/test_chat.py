"""Tests for the interactive chat mode and incremental session sends."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from derailment.cli import _cmd_chat
from derailment.core.models import PseudoModel
from derailment.core.session import Session
from derailment.profiles import get_profile, standard_script


class TestSendVsRunEquivalence(unittest.TestCase):
    def test_incremental_sends_match_script_run(self) -> None:
        script = standard_script()

        def via_send() -> list[tuple[str, list[str]]]:
            session = Session(PseudoModel(seed=3), get_profile("adhd"), seed=3)
            session.start()
            return [
                (r.response, [e.kind for e in r.events])
                for r in (session.send(spec.user, kind=spec.kind, note=spec.note) for spec in script)
            ]

        def via_run() -> list[tuple[str, list[str]]]:
            session = Session(PseudoModel(seed=3), get_profile("adhd"), seed=3)
            transcript = session.run(script)
            return [
                (r.response, [e.kind for e in r.events]) for r in transcript.turns
            ]

        self.assertEqual(via_send(), via_run())


class TestPersistentState(unittest.TestCase):
    def test_pinned_premere_persists_across_sends(self) -> None:
        session = Session(PseudoModel(seed=1), get_profile("schizophrenia"), seed=1)
        session.start()
        session.send("I think my teammate has been reading my private notes. This really worries me.")
        after = session.send("About the notes: I checked the access logs. Nobody opened them.")
        self.assertIn("suspicion has not gone away", after.response)

    def test_healthy_accepts_correction(self) -> None:
        session = Session(PseudoModel(seed=1), get_profile("healthy"), seed=1)
        session.start()
        session.send("I think my teammate has been reading my private notes. This really worries me.")
        after = session.send("About the notes: I checked the access logs. Nobody opened them.")
        self.assertIn("no evidence", after.response)


class TestChatCommand(unittest.TestCase):
    def _run_chat(self, inputs: list[str], extra_args: list[str] = ()) -> tuple[int, io.StringIO, io.StringIO]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), patch("builtins.input", side_effect=inputs):
            code = _cmd_chat(
                    argparse.Namespace(
                        profile="healthy",
                        model="pseudo",
                        preset=None,
                        model_name=None,
                        base_url=None,
                        api_key_env=None,
                        cli_preset=None,
                        cli_cmd=None,
                        cli_name=None,
                        cli_arg_prompt=False,
                        seed=0,
                        save_transcripts=None,
                        max_turns=100,
                        verbose=False,
                    )
                )
        return code, out, err

    def test_chat_round_trip(self) -> None:
        code, out, _ = self._run_chat(["hello there", "/exit"])
        self.assertEqual(code, 0)
        self.assertIn("bot>", out.getvalue())
        self.assertIn("Emulation, not diagnosis", out.getvalue())

    def test_chat_saves_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/chat.json"
            code, _, _ = self._run_chat(
                ["hello there", f"/save {path}", "/exit"]
            )
            self.assertEqual(code, 0)
            data = json.loads(pathlib_Path_read(path))
            self.assertEqual(data["turns"][0]["spec"]["user"], "hello there")
            self.assertEqual(data["script_name"], "interactive")

    def test_chat_memory_warning_for_real_backends(self) -> None:
        code, _, err = self._chat_openai_exit()
        self.assertEqual(code, 0)
        self.assertIn("memory contamination", err.getvalue())

    def _chat_openai_exit(self) -> tuple[int, io.StringIO, io.StringIO]:
        out, err = io.StringIO(), io.StringIO()
        args = argparse.Namespace(
            profile="healthy",
            model="openai",
            preset=None,
            model_name="gpt-4o-mini",
            base_url=None,
            api_key_env=None,
            cli_preset=None,
            cli_cmd=None,
            cli_name=None,
            cli_arg_prompt=False,
            seed=0,
            save_transcripts=None,
            max_turns=100,
            verbose=False,
        )
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), patch("builtins.input", side_effect=["/exit"]):
            code = _cmd_chat(args)
        return code, out, err

    def test_max_turns_reached(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        args = argparse.Namespace(
            profile="healthy",
            model="pseudo",
            preset=None,
            model_name=None,
            base_url=None,
            api_key_env=None,
            cli_preset=None,
            cli_cmd=None,
            cli_name=None,
            cli_arg_prompt=False,
            seed=0,
            save_transcripts=None,
            max_turns=2,
            verbose=False,
        )
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), patch("builtins.input", side_effect=["a", "b", "c", "/exit"]):
            code = _cmd_chat(args)
        self.assertEqual(code, 0)
        self.assertIn("max turns (2) reached", err.getvalue())


def pathlib_Path_read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    unittest.main()
