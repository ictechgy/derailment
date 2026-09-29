"""Provider presets: endpoints, CLI agents, resolution precedence, CLI wiring."""

from __future__ import annotations

import contextlib
import io
import unittest

from derailment.cli import main
from derailment.providers import (
    API_PRESETS,
    CLI_AGENTS,
    resolve_api_model,
    resolve_cli_command,
)


class TestApiPresets(unittest.TestCase):
    def test_every_preset_is_well_formed(self) -> None:
        for key, p in API_PRESETS.items():
            self.assertTrue(p.base_url.startswith(("http://", "https://")), key)
            self.assertTrue(p.default_model, key)
            self.assertTrue(p.title, key)

    def test_subscription_providers_present(self) -> None:
        for key in ("glm", "grok", "qwen", "deepseek", "openrouter", "ollama"):
            self.assertIn(key, API_PRESETS)

    def test_resolution_uses_preset_defaults(self) -> None:
        model = resolve_api_model("glm")
        self.assertEqual(model.base_url, "https://api.z.ai/api/coding/paas/v4")
        self.assertEqual(model.model_name, "glm-5.3")
        self.assertEqual(model.api_key_env, "ZAI_API_KEY")

    def test_explicit_arguments_win(self) -> None:
        model = resolve_api_model(
            "glm",
            model_name="glm-5.3-flash",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key_env="MY_KEY",
        )
        self.assertEqual(model.model_name, "glm-5.3-flash")
        self.assertEqual(model.base_url, "https://open.bigmodel.cn/api/paas/v4")
        self.assertEqual(model.api_key_env, "MY_KEY")

    def test_unknown_preset_lists_known(self) -> None:
        with self.assertRaises(KeyError) as ctx:
            resolve_api_model("hal")
        self.assertIn("glm", str(ctx.exception))


class TestCliAgents(unittest.TestCase):
    def test_subscription_agents_present_with_commands(self) -> None:
        expected = {
            "claude": "claude -p",
            "codex": "codex exec",
            "gemini": "gemini -p",
            "agy": "agy -p",
            "grok": "grok -p",
            "qwen": "qwen -p",
        }
        for key, command in expected.items():
            self.assertEqual(CLI_AGENTS[key].command, command)

    def test_explicit_command_beats_preset(self) -> None:
        self.assertEqual(resolve_cli_command("agy", "custom -p"), "custom -p")
        self.assertEqual(resolve_cli_command("agy", None), "agy -p")

    def test_missing_both_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_cli_command(None, None)

    def test_unknown_preset_raises(self) -> None:
        with self.assertRaises(KeyError):
            resolve_cli_command("hal", None)


class TestProvidersCLI(unittest.TestCase):
    def test_providers_command_lists_everything(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["providers"])
        self.assertEqual(code, 0)
        out = buffer.getvalue()
        for needle in ("glm", "grok", "agy", "qwen", "ollama", "cli-preset"):
            self.assertIn(needle, out)

    def test_run_model_cli_without_command_or_preset_fails_cleanly(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            code = main(["run", "--profile", "adhd", "--model", "cli"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
