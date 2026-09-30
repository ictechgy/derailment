"""Tests for the local web GUI.

The binding test uses this session's granted loopback port
(``AGENTBELT_LOOPBACK_PORT``); if the environment does not grant one,
those tests are skipped. HTML/parse logic is always tested.
"""

from __future__ import annotations

import json
import os
import unittest
import urllib.request

from derailment.core.models import PseudoModel
from derailment.profiles import get_profile
from derailment.webui import build_page, serve


class TestPage(unittest.TestCase):
    def test_page_contains_markers_and_warning_slot(self) -> None:
        page = build_page("schizophrenia", "Psychosis-like salience distortion", "pseudo-1", "")
        for needle in ("derail web", "/api/turn", "/api/save", "pseudo-1", "schizophrenia"):
            self.assertIn(needle, page)

    def test_warning_is_rendered_into_header(self) -> None:
        page = build_page("adhd", "ADHD-like attention distortion", "claude", "memory contamination warning text")
        self.assertIn("memory contamination warning text", page)


class TestServerRoundTrip(unittest.TestCase):
    def _port(self) -> int:
        raw = os.environ.get("AGENTBELT_LOOPBACK_PORT")
        if not raw:
            self.skipTest("no loopback port grant in this environment")
        return int(raw)

    def test_get_page_and_turn_round_trip(self) -> None:
        port = self._port()
        profile = get_profile("schizophrenia")
        model = PseudoModel(seed=1)
        import threading

        server_thread_error: list[Exception] = []

        token = "test-token-123"
        handle: dict = {}

        def run_server() -> None:
            try:
                serve(
                    profile,
                    model,
                    "pseudo-1",
                    "",
                    host="127.0.0.1",
                    port=port,
                    seed=1,
                    max_turns=10,
                    handle=handle,
                    token=token,
                )
            except Exception as exc:  # pragma: no cover - surface thread errors
                server_thread_error.append(exc)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

        import time

        base = f"http://127.0.0.1:{port}"
        page = body = None
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"{base}/", timeout=2) as resp:
                    body = resp.read().decode("utf-8")
                page = "ok"
                break
            except Exception:
                if server_thread_error:
                    raise server_thread_error[0] from None
                time.sleep(0.05)
        self.assertEqual(page, "ok")
        self.assertIn("derail web", body or "")
        self.assertIn(token, body or "")  # token embedded for the JS client

        # a turn through the layer chain
        # POST without the session token is rejected (blocks drive-by pages)
        req = urllib.request.Request(
            f"{base}/api/turn",
            data=json.dumps({"message": "hi"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
        except urllib.error.HTTPError as exc:
            status = exc.code
            data = json.loads(exc.read().decode("utf-8"))
        self.assertEqual(status, 401)
        self.assertIn("token", data["error"])

        req = urllib.request.Request(
            f"{base}/api/turn",
            data=json.dumps({"message": "hello there"}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Derailment-Session": token,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertIn("response", data)
        self.assertIsInstance(data.get("events"), list)
        self.assertEqual(data["turns"], 1)

        # empty message rejected
        req = urllib.request.Request(
            f"{base}/api/turn",
            data=json.dumps({"message": "  "}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            data = json.loads(exc.read().decode("utf-8"))
        self.assertIn("error", data)

        # save endpoint writes a transcript
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/chat.json"
            req = urllib.request.Request(
                f"{base}/api/save",
                data=json.dumps({"path": path}).encode(),
                headers={
                    "Content-Type": "application/json",
                    "X-Derailment-Session": token,
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["saved"], path)
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved["turns"][0]["spec"]["user"], "hello there")

        # 404 for unknown paths
        try:
            with urllib.request.urlopen(f"{base}/nope", timeout=5) as resp:
                status = resp.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        self.assertEqual(status, 404)

        handle["server"].shutdown()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
