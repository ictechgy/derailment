"""Local web GUI for derailment chat.

``derail web`` serves a single-user, localhost-only chat page (vanilla
HTML/JS embedded below — no CDN, works offline) that drives the same
layer chain as ``derail chat``: every submitted message flows through
observe-style context layers, sampling layers and response layers, and
the induction dose is streamed back with each response.

Safety posture: binds to 127.0.0.1 by default, single session, and the
memory-contamination warning is shown both on the terminal and in the
page header. Measurement stays in run/judge — the web UI is the
experience.
"""

from __future__ import annotations

import json
import secrets
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core.models import ChatModel
from .core.session import Session
from .core.types import Transcript

DISCLAIMER = (
    "Emulation, not diagnosis — a scripted, manipulated policy in a "
    "simulator/session. See ETHICS.md."
)

MAX_BODY = 1 << 20  # 1 MiB request cap


def build_page(
    profile_key: str,
    profile_title: str,
    backend: str,
    warning: str,
    token: str = "",
) -> str:
    """Render the chat page (server-side tokens only; user content is
    inserted client-side with textContent, never innerHTML)."""
    page = _PAGE
    return (
        page.replace("__TITLE__", f"derail web — {profile_key}")
        .replace("__PROFILE__", f"{profile_title} (`{profile_key}`)")
        .replace("__BACKEND__", backend)
        .replace("__WARNING__", warning)
        .replace("__DATE__", date.today().isoformat())
        .replace("__TOKEN__", token)
    )


def serve(
    profile,
    model: ChatModel,
    backend: str,
    warning: str,
    host: str = "127.0.0.1",
    port: int = 8765,
    seed: int = 0,
    max_turns: int = 500,
    save_path: str | None = None,
    handle: dict | None = None,
    token: str | None = None,
) -> list:
    """Start the local web server (blocking). Returns the accumulated
    turns when the server stops, so the caller can persist them.
    ``handle`` (optional dict) receives ``{"server": server}`` right after
    binding, for callers that need to shut the server down (tests)."""
    profile_key = profile.key
    profile_title = profile.title
    session = Session(model, profile, seed=seed)
    if token is None:
        token = secrets.token_hex(16)  # POSTs must carry it (blocks drive-by pages)
    state = {
        "lock": threading.Lock(),
        "turns": [],
        "max_turns": max_turns,
        "save_path": save_path,
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the chat quiet
            pass

        def _json(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                body = build_page(
                    profile_key, profile_title, backend, warning, token=token
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/state":
                with state["lock"]:
                    self._json(
                        {
                            "profile": profile_key,
                            "backend": backend,
                            "turns": len(state["turns"]),
                            "max_turns": state["max_turns"],
                        }
                    )
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:
            if self.headers.get("X-Derailment-Session") != token:
                self._json({"error": "missing or bad session token"}, 401)
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > MAX_BODY:
                self._json({"error": "body too large"}, 413)
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._json({"error": "invalid JSON"}, 400)
                return

            if self.path == "/api/turn":
                message = str(data.get("message", "")).strip()
                if not message:
                    self._json({"error": "empty message"}, 400)
                    return
                with state["lock"]:
                    if len(state["turns"]) >= state["max_turns"]:
                        self._json(
                            {"error": f"max turns ({state['max_turns']}) reached"}, 429
                        )
                        return
                    try:
                        result = session.send(message)
                    except RuntimeError as exc:
                        self._json({"error": str(exc)}, 502)
                        return
                    state["turns"].append(result)
                    self._json(
                        {
                            "response": result.response,
                            "turns": len(state["turns"]),
                            "events": [
                                {
                                    "turn": e.turn,
                                    "layer": e.layer,
                                    "kind": e.kind,
                                    "detail": e.detail,
                                }
                                for e in result.events
                            ],
                        }
                    )
            elif self.path == "/api/save":
                out_path = str(
                    data.get("path") or state["save_path"] or f"chat_{profile_key}.json"
                )
                with state["lock"]:
                    transcript = Transcript(
                        profile=profile_key,
                        model=backend,
                        seed=seed,
                        turns=state["turns"],
                        script_name="interactive",
                    )
                    with open(out_path, "w", encoding="utf-8") as fh:
                        fh.write(transcript.to_json())
                    n = len(state["turns"])
                self._json({"saved": out_path, "turns": n})
            else:
                self._json({"error": "not found"}, 404)

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    if handle is not None:
        handle["server"] = server
    print(
        f"derail web — profile '{profile_key}' ({profile_title}) · "
        f"backend: {backend} · seed {seed}"
    )
    print(f"> ⚠️ {DISCLAIMER}")
    if warning:
        print(f"⚠️ {warning}")
    print(f"open http://{host}:{server.server_port} in your browser · Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return state["turns"]


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; height:100vh; display:flex; flex-direction:column;
         font-family:-apple-system,"Segoe UI",Roboto,sans-serif;
         background:#0f1115; color:#e6e6e6; }
  header { padding:10px 16px; background:#161a22; border-bottom:1px solid #262c38;
           display:flex; flex-wrap:wrap; gap:10px; align-items:baseline; }
  header h1 { font-size:15px; margin:0; font-weight:600; }
  header .meta { font-size:12px; color:#697380; }
  header .warn { font-size:12px; color:#ffb84d; width:100%; }
  main { flex:1; display:flex; min-height:0; }
  #log { flex:1; overflow-y:auto; padding:16px; display:flex;
         flex-direction:column; gap:10px; }
  .msg { max-width:72%; padding:9px 13px; border-radius:12px;
         white-space:pre-wrap; line-height:1.45; overflow-wrap:anywhere; }
  .you { align-self:flex-end; background:#2b5278; }
  .bot { align-self:flex-start; background:#1d222c; border:1px solid #2a3140; }
  .msg.err { background:#3a1d1d; border-color:#5c2a2a; }
  .hint { align-self:center; font-size:11px; color:#697380; }
  #side { width:300px; border-left:1px solid #262c38; padding:12px;
          overflow-y:auto; font-size:12px; color:#9aa4b2; }
  #side h2 { font-size:11px; text-transform:uppercase; letter-spacing:.08em;
             margin:0 0 8px; color:#697380; }
  .evt { padding:3px 0; border-bottom:1px dashed #262c38;
         font-family:ui-monospace,SFMono-Regular,monospace; font-size:11px; }
  .evt b { color:#c9d1d9; font-weight:600; }
  form { display:flex; gap:8px; padding:12px; border-top:1px solid #262c38;
         background:#161a22; }
  input { flex:1; background:#0f1115; color:#e6e6e6; border:1px solid #2a3140;
          border-radius:8px; padding:10px 12px; font-size:15px; }
  input:focus { outline:1px solid #2b5278; }
  button { background:#2b5278; color:#fff; border:0; border-radius:8px;
           padding:10px 18px; font-size:14px; cursor:pointer; }
  button:disabled { opacity:.5; cursor:default; }
  #save { background:#1d222c; border:1px solid #2a3140; }
</style>
</head>
<body>
<header>
  <h1>derail web</h1>
  <span class="meta">profile: <b>__PROFILE__</b> · backend: <b>__BACKEND__</b> · __DATE__</span>
  <span class="warn">__WARNING__</span>
</header>
<main>
  <div id="log">
    <div class="hint">measurement lives in run/judge — this is the experience. reload clears the view; save keeps the record.</div>
  </div>
  <div id="side"><h2>induction dose</h2><div id="events"></div></div>
</main>
<form id="f" autocomplete="off">
  <input id="i" placeholder="type a message…" autofocus>
  <button type="submit">send</button>
  <button type="button" id="save">save</button>
</form>
<script>
const TOKEN = "__TOKEN__";
const log = document.getElementById("log");
const events = document.getElementById("events");
const form = document.getElementById("f");
const input = document.getElementById("i");
const saveBtn = document.getElementById("save");

function bubble(cls, text) {
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}
function addEvent(e) {
  const d = document.createElement("div");
  d.className = "evt";
  const b = document.createElement("b");
  b.textContent = e.layer + "/" + e.kind;
  d.appendChild(b);
  d.appendChild(document.createTextNode(" — " + e.detail));
  events.prepend(d);
}
form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  bubble("you", text);
  input.value = "";
  saveBtn.disabled = true;
  try {
    const res = await fetch("/api/turn", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Derailment-Session": TOKEN,
      },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    if (data.error) {
      bubble("bot err", "error: " + data.error);
    } else {
      bubble("bot", data.response);
      (data.events || []).forEach(addEvent);
    }
  } catch (err) {
    bubble("bot err", "error: " + err);
  } finally {
    saveBtn.disabled = false;
    input.focus();
  }
});
saveBtn.addEventListener("click", async () => {
  const res = await fetch("/api/save", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Derailment-Session": TOKEN,
    },
    body: "{}",
  });
  const data = await res.json();
  bubble("hint", data.saved ? ("saved → " + data.saved + " (" + data.turns + " turns)") : ("save failed: " + (data.error || "?")));
});
input.focus();
</script>
</body>
</html>
"""
