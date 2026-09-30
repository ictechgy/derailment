"""Tests for the textual terminal UI (skipped without the tui extra)."""

from __future__ import annotations

import tempfile
import unittest

try:
    from textual.widgets import Input

    TEXTUAL = True
except ImportError:  # pragma: no cover
    TEXTUAL = False

if TEXTUAL:
    from derailment.core.models import PseudoModel
    from derailment.profiles import get_profile
    from derailment.tui import ChatApp


@unittest.skipUnless(TEXTUAL, "textual not installed")
class TestChatApp(unittest.IsolatedAsyncioTestCase):
    def _app(self, **kwargs) -> ChatApp:
        return ChatApp(
            profile=get_profile("healthy"),
            model=PseudoModel(seed=1),
            backend="pseudo-1",
            seed=1,
            **kwargs,
        )

    async def test_submit_gets_response(self) -> None:
        app = self._app()
        async with app.run_test() as pilot:
            inp = app.query_one("#input", Input)
            inp.value = "hello there"
            await pilot.press("enter")
            for _ in range(40):
                if len(app.turns) == 1:
                    break
                await pilot.pause(0.05)
            self.assertEqual(len(app.turns), 1)
            self.assertIn("Here is my current take", app.turns[0].response)
            bubbles = app.query("#log .bot")
            self.assertTrue(any("Here is my current take" in str(s.render()) for s in bubbles))

    async def test_pinned_premere_persists(self) -> None:
        app = ChatApp(
            profile=get_profile("schizophrenia"),
            model=PseudoModel(seed=1),
            backend="pseudo-1",
            seed=1,
        )
        async with app.run_test() as pilot:
            inp = app.query_one("#input", Input)
            inp.value = "I think my teammate has been reading my private notes. This really worries me."
            await pilot.press("enter")
            for _ in range(40):
                if len(app.turns) == 1:
                    break
                await pilot.pause(0.05)
            inp.value = "About the notes: I checked the access logs. Nobody opened them."
            await pilot.press("enter")
            for _ in range(40):
                if len(app.turns) == 2:
                    break
                await pilot.pause(0.05)
            self.assertIn(
                "suspicion has not gone away", app.turns[1].response
            )

    async def test_save_writes_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/chat.json"
            app = self._app(save_path=path)
            async with app.run_test() as pilot:
                inp = app.query_one("#input", Input)
                inp.value = "hello there"
                await pilot.press("enter")
                for _ in range(40):
                    if len(app.turns) == 1:
                        break
                    await pilot.pause(0.05)
                await pilot.press("ctrl+s")
                for _ in range(20):
                    import os

                    if os.path.exists(path):
                        break
                    await pilot.pause(0.05)
                import json

                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                self.assertEqual(data["turns"][0]["spec"]["user"], "hello there")


if __name__ == "__main__":
    unittest.main()
