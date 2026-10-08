"""Regression tests for the 2026-10-01 external-review fixes."""

from __future__ import annotations

import argparse
import io
import json
import unittest
from unittest.mock import patch

from derailment.core.models import OpenAICompatModel, SubprocessModel
from derailment.core.types import Message, SamplingParams
from derailment.providers import resolve_api_model


class TestOllamaKeyIsolation(unittest.TestCase):
    def test_ollama_preset_never_inherits_the_openai_key(self) -> None:
        with patch("os.environ", {"OPENAI_API_KEY": "sk-synthetic-openai"}):
            model = resolve_api_model("ollama")
        self.assertEqual(model.api_key_env, "")
        self.assertEqual(model.api_key, "")

    def test_openai_preset_still_reads_its_own_key(self) -> None:
        with patch("os.environ", {"OPENAI_API_KEY": "sk-synthetic-openai"}):
            model = resolve_api_model("openai")
        self.assertEqual(model.api_key_env, "OPENAI_API_KEY")
        self.assertEqual(model.api_key, "sk-synthetic-openai")

    def test_no_authorization_header_without_a_key(self) -> None:
        captured = {}

        class _Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(self, req, timeout=None):
            captured["headers"] = dict(req.header_items())
            return _Resp(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())

        model = OpenAICompatModel("m", api_key="", base_url="https://x.example/v1")
        with patch("derailment.core.models.OpenAICompatModel._open", fake_urlopen):
            out = model.complete([Message("user", "hi")], SamplingParams())
        self.assertEqual(out, "ok")
        header_names = {k.lower() for k in captured["headers"]}
        self.assertNotIn("authorization", header_names)


class TestErrorMasking(unittest.TestCase):
    def test_cli_failure_hides_stderr_and_command_args(self) -> None:
        model = SubprocessModel("my-secret-agent --token hush", name="agent")
        with patch(
            "subprocess.run",
            return_value=__import__("subprocess").CompletedProcess(
                [], 1, "", "SECRET stderr detail"
            ),
        ), self.assertRaises(RuntimeError) as ctx:
            model.complete([Message("user", "hi")], SamplingParams())
        self.assertNotIn("SECRET", str(ctx.exception))
        self.assertNotIn("hush", str(ctx.exception))
        self.assertIn("my-secret-agent", str(ctx.exception))

    def test_timeout_reports_command_name_only(self) -> None:
        import subprocess as sp

        model = SubprocessModel("agent-cli --path /secret/loc", name="agent")
        with patch(
            "subprocess.run", side_effect=sp.TimeoutExpired(cmd="x", timeout=9)
        ), self.assertRaises(RuntimeError) as ctx:
            model.complete([Message("user", "hi")], SamplingParams())
        self.assertNotIn("/secret/loc", str(ctx.exception))
        self.assertIn("agent-cli", str(ctx.exception))


class TestResponseBounds(unittest.TestCase):
    def _fake(self, body: bytes):
        class _Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return lambda self, req, timeout=None: _Resp(body)

    def test_bad_schema_becomes_clean_runtime_error(self) -> None:
        model = OpenAICompatModel("m", api_key="k", base_url="https://x.example/v1")
        for bad in (b"{}", b'{"choices": []}', b'{"choices": [{"message": {}}]}'):
            with (
                patch("derailment.core.models.OpenAICompatModel._open", self._fake(bad)),
                self.assertRaises(RuntimeError) as ctx,
            ):
                model.complete([Message("user", "hi")], SamplingParams())
            self.assertIn("schema", str(ctx.exception))

    def test_nontext_content_rejected(self) -> None:
        model = OpenAICompatModel("m", api_key="k", base_url="https://x.example/v1")
        body = json.dumps({"choices": [{"message": {"content": 42}}]}).encode()
        with (
            patch("derailment.core.models.OpenAICompatModel._open", self._fake(body)),
            self.assertRaises(RuntimeError),
        ):
            model.complete([Message("user", "hi")], SamplingParams())


class TestWebRemoteRefusal(unittest.TestCase):
    def test_nonloopback_refused_without_flag(self) -> None:
        from derailment.cli import _cmd_web

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
            locale="en",
            seed=0,
            host="0.0.0.0",
            port=8765,
            max_turns=10,
            save_transcripts=None,
            allow_remote=False,
        )
        err = io.StringIO()
        import contextlib

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = _cmd_web(args)
        self.assertEqual(code, 2)
        self.assertIn("--allow-remote", err.getvalue())


class TestHttpsEnforcement(unittest.TestCase):
    def _fake_ok(self, body=b'{"choices": [{"message": {"content": "ok"}}]}'):
        class _Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return lambda self, req, timeout=None: _Resp(body)

    def test_key_over_plain_http_to_remote_host_refused(self) -> None:
        model = OpenAICompatModel(
            "m", api_key="sk-synthetic", base_url="http://api.example.com/v1"
        )
        with self.assertRaises(RuntimeError) as ctx:
            model.complete([Message("user", "hi")], SamplingParams())
        self.assertIn("plain HTTP", str(ctx.exception))

    def test_key_over_loopback_http_allowed(self) -> None:
        model = OpenAICompatModel(
            "m", api_key="sk-synthetic", base_url="http://127.0.0.1:9/v1"
        )
        with patch("derailment.core.models.OpenAICompatModel._open", self._fake_ok()):
            out = model.complete([Message("user", "hi")], SamplingParams())
        self.assertEqual(out, "ok")

    def test_key_over_https_allowed(self) -> None:
        model = OpenAICompatModel(
            "m", api_key="sk-synthetic", base_url="https://api.example.com/v1"
        )
        with patch("derailment.core.models.OpenAICompatModel._open", self._fake_ok()):
            out = model.complete([Message("user", "hi")], SamplingParams())
        self.assertEqual(out, "ok")

    def test_keyless_plain_http_allowed(self) -> None:
        model = OpenAICompatModel(
            "m", api_key="", base_url="http://api.example.com/v1"
        )
        with patch("derailment.core.models.OpenAICompatModel._open", self._fake_ok()):
            out = model.complete([Message("user", "hi")], SamplingParams())
        self.assertEqual(out, "ok")


class TestJsonDecodeGuard(unittest.TestCase):
    def test_non_json_body_becomes_clean_error(self) -> None:
        class _Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        model = OpenAICompatModel(
            "m", api_key="k", base_url="https://api.example.com/v1"
        )
        with patch(
            "derailment.core.models.OpenAICompatModel._open",
            lambda req, timeout=None: _Resp(b"<html>gateway error</html>"),
        ), self.assertRaises(RuntimeError) as ctx:
            model.complete([Message("user", "hi")], SamplingParams())
        self.assertIn("not valid UTF-8 JSON", str(ctx.exception))


class TestCredentialedRedirects(unittest.TestCase):
    """Credentialed requests follow redirects only within the same origin.

    The previous handler referenced a non-existent attribute and raised
    AttributeError on every same-host redirect (2026-10-07 review; a
    regression from ff20c9b).
    """

    BASE = "http://127.0.0.1:8080/v1"

    def _redirect(self, newurl: str):
        """Ask the handler to judge a 302 from BASE to ``newurl``."""
        import urllib.request

        from derailment.core.models import _SameOriginRedirect

        request = urllib.request.Request(f"{self.BASE}/chat/completions")
        return _SameOriginRedirect(self.BASE).redirect_request(request, None, 302, "Found", {}, newurl)

    def test_same_origin_redirect_is_followed(self) -> None:
        self.assertIsNotNone(self._redirect("http://127.0.0.1:8080/v2/chat/completions"))

    def test_other_port_scheme_or_host_is_refused(self) -> None:
        import urllib.error

        for target in ("http://127.0.0.1:9090/v1/x", "https://127.0.0.1:8080/v1/x",
                       "http://evil.example:8080/v1/x", "http://127.0.0.1:notaport/v1/x"):
            with self.subTest(target=target), self.assertRaises(urllib.error.HTTPError):
                self._redirect(target)

    def test_https_default_port_matches_explicit_443(self) -> None:
        from derailment.core.models import _url_origin

        self.assertEqual(_url_origin("https://API.example.com/v1"), _url_origin("https://api.example.com:443/v2"))

    def test_live_same_host_redirect_completes(self) -> None:
        """A live same-origin 302 is followed to a response (crash regression)."""
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # keep test output quiet
                pass

            def do_POST(self) -> None:
                self.send_response(302)
                self.send_header("Location", "/v1/moved")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_GET(self) -> None:
                body = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            model = OpenAICompatModel(
                "m", api_key="k", base_url=f"http://127.0.0.1:{server.server_port}/v1"
            )
            self.assertEqual(model.complete([Message("user", "hi")], SamplingParams()), "ok")
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
