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

import html
import json
import os
import secrets
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast

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
    max_turns: int = 0,
    remote: bool = False,
) -> str:
    """Render the chat page (server-side tokens only; user content is
    inserted client-side with textContent, never innerHTML)."""
    esc = html.escape
    if warning:
        warn_block = (
            '<div class="warn" role="status"><div class="warn-in">'
            '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.4 14.2 13H1.8Z" '
            'fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>'
            '<path d="M8 6.6v3" stroke="currentColor" stroke-width="1.4" '
            'stroke-linecap="round"/><circle cx="8" cy="11.3" r=".9" fill="currentColor"/>'
            f"<span>{esc(warning)}</span></div></div>"
        )
    else:
        warn_block = ""
    page = _PAGE
    return (
        page.replace("__TITLE__", esc(f"derail web — {profile_key}", quote=True))
        .replace("__PROFILE__", esc(f"{profile_title} (`{profile_key}`)"))
        .replace("__BACKEND__", esc(backend))
        .replace("__WARN_BLOCK__", warn_block)
        .replace("__DATE__", date.today().isoformat())
        .replace("__MAXTURNS__", str(max_turns))
        .replace("__TOKEN__", token)
        .replace("__REMOTE__", "true" if remote else "false")
    )


def serve(
    profile,
    model: ChatModel,
    backend: str,
    warning: str,
    # Security posture: loopback-only by default; in --allow-remote mode
    # the page token plus the printed PIN guard POSTs, an Origin check
    # refuses cross-site requests, and PIN attempts lock after 10
    # failures. DNS-rebinding note (checked 2026-10-05): Chrome's Local
    # Network Access blocks public pages from driving localhost servers
    # in current browsers but research (APNIC 2023; Radboud) shows it
    # reduces rather than eliminates the surface — prefer an SSH tunnel
    # over plain LAN exposure when remote.

    host: str = "127.0.0.1",
    port: int = 8765,
    seed: int = 0,
    max_turns: int = 500,
    save_path: str | None = None,
    handle: dict | None = None,
    token: str | None = None,
    remote: bool = False,
) -> list:
    """Start the local web server (blocking). Returns the accumulated
    turns when the server stops, so the caller can persist them.
    ``handle`` (optional dict) receives ``{"server": server}`` right after
    binding, for callers that need to shut the server down (tests)."""
    profile_key = profile.key
    profile_title = profile.title
    profile_description = profile.description
    profile_notes = profile.mechanism_notes
    session = Session(model, profile, seed=seed)
    if token is None:
        token = secrets.token_hex(16)  # POSTs must carry it (blocks drive-by pages)
    # In remote mode the page (and thus the token) is reachable by anyone,
    # so POSTs additionally require a PIN that only the operator's terminal
    # shows — a GET alone never grants write access.
    pin = f"{secrets.randbelow(900000) + 100000}" if remote else None
    if remote:
        print(f"remote mode PIN (enter it in the browser): {pin}")
    state = {
        "lock": threading.Lock(),
        "turns": [],
        "max_turns": max_turns,
        "save_path": save_path,
        "pin_failures": 0,
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the chat quiet
            pass

        def _host_allowed(self) -> bool:
            """DNS-rebinding guard: in loopback mode the Host header must
            name this server.

            A rebound attacker domain sends its own name as *both* Host and
            Origin, so the Origin==Host comparison alone cannot stop it
            (2026-10-07 review). Remote mode cannot know which name clients
            will use, so it skips this check and relies on the PIN for writes.
            """
            if pin is not None:
                return True
            # use the actually bound port: callers may bind port 0
            port = cast(ThreadingHTTPServer, self.server).server_port
            allowed = {f"{name}:{port}" for name in (host, "127.0.0.1", "localhost", "[::1]")}
            return self.headers.get("Host", "").lower() in allowed

        def _origin_allowed(self) -> bool:
            # Origin absent (same-origin fetches, curl) is fine; a present
            # Origin must be this server — blocks cross-site pages from
            # driving the token'd API from a victim browser (P3)
            origin = self.headers.get("Origin")
            if not origin:
                return True
            host_header = self.headers.get("Host", "")
            try:
                from urllib.parse import urlsplit

                return urlsplit(origin).netloc.lower() == host_header.lower()
            except ValueError:
                return False

        def _request_allowed(self) -> bool:
            """A request is served only if both the Host and Origin checks pass."""
            return self._host_allowed() and self._origin_allowed()

        def _json(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if not self._request_allowed():
                self._json(
                    {"error": "refused: unexpected Host or cross-origin request "
                              "(open the page via http://127.0.0.1:<port>/)"},
                    403,
                )
                return
            if self.path in ("/", "/index.html"):
                body = build_page(
                    profile_key,
                    profile_title,
                    backend,
                    warning,
                    token=token,
                    max_turns=state["max_turns"],
                    remote=pin is not None,  # page must ask for the PIN (P2-13)
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
                            "title": profile_title,
                            "description": profile_description,
                            "notes": profile_notes,
                            "backend": backend,
                            "turns": len(state["turns"]),
                            "max_turns": state["max_turns"],
                        }
                    )
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:
            if not self._request_allowed():
                self._json(
                    {"error": "refused: unexpected Host or cross-origin request "
                              "(open the page via http://127.0.0.1:<port>/)"},
                    403,
                )
                return
            if self.headers.get("X-Derailment-Session") != token:
                self._json({"error": "missing or bad session token"}, 401)
                return
            if pin is not None:
                if state["pin_failures"] >= 10:
                    # a 6-digit PIN must not be brute-forceable within a
                    # server lifetime (P2-14); restart to get a new PIN
                    self._json(
                        {"error": "too many wrong PIN attempts — server "
                                  "locked (restart to get a new PIN)"},
                        429,
                    )
                    return
                if self.headers.get("X-Derailment-Pin") != pin:
                    state["pin_failures"] += 1
                    self._json(
                        {"error": "missing or bad remote PIN (see the terminal)"},
                        401,
                    )
                    return
            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY:
                # negative lengths would bypass the cap; garbage is not a
                # body (P3)
                self._json({"error": "invalid or too large body"}, 413 if length > MAX_BODY else 400)
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._json({"error": "invalid JSON"}, 400)
                return
            if not isinstance(data, dict):
                self._json({"error": "JSON object expected"}, 400)
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
                client_path = str(data.get("path") or "").strip()
                if client_path:
                    # client-supplied: bare filename only, and never
                    # overwrite an existing file (P1: remote file writes)
                    if (
                        client_path != os.path.basename(client_path)
                        or client_path in ("", ".", "..")
                    ):
                        self._json({"error": "path must be a bare filename"}, 400)
                        return
                    out_path = client_path
                    exclusive = True
                else:
                    # operator-configured path (from --save-transcripts) or
                    # a per-session default: trusted, may include
                    # directories. The default is minted once per session
                    # and may be overwritten within it — an exclusive
                    # default meant every save after the first 409'd and
                    # later turns were lost on exit (P2-12)
                    if state["save_path"] is None:
                        if not state.get("default_save_name"):
                            stamp = time.strftime("%Y%m%d-%H%M%S")
                            state["default_save_name"] = (
                                f"chat_{profile_key}_{stamp}.json"
                            )
                        out_path = state["default_save_name"]
                        exclusive = False
                    else:
                        out_path = state["save_path"]
                        exclusive = False
                with state["lock"]:
                    transcript = Transcript(
                        profile=profile_key,
                        model=backend,
                        seed=seed,
                        turns=state["turns"],
                        script_name="interactive",
                    )
                    try:
                        mode = "x" if exclusive else "w"
                        with open(out_path, mode, encoding="utf-8") as fh:
                            fh.write(transcript.to_json())
                    except FileExistsError:
                        self._json(
                            {"error": "file already exists (overwrite refused)"}, 409
                        )
                        return
                    except OSError as exc:
                        # the session stays alive; operator can pick another
                        # filename (P2-10)
                        self._json(
                            {"error": f"save failed: {exc.strerror or exc}"}, 500
                        )
                        return
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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%20role%3D%22img%22%20aria-label%3D%22derailment%20icon%22%3E%0A%0A%3Crect%20width%3D%2264%22%20height%3D%2264%22%20rx%3D%2214%22%20fill%3D%22%230f1115%22%2F%3E%3Ccircle%20cx%3D%2212%22%20cy%3D%2244%22%20r%3D%222.5%22%20fill%3D%22%233a4150%22%2F%3E%3Cpath%20d%3D%22M17%2044%20C24%2044%2026%2030%2036%2028%20C48%2025.5%2056%2034%2050%2042%20C45%2048.5%2034%2047%2033.5%2039.5%20C33%2033%2040%2026.5%2053%2022%22%20fill%3D%22none%22%20stroke%3D%22%234a7fd0%22%20stroke-width%3D%223.5%22%20stroke-linecap%3D%22round%22%2F%3E%3Ccircle%20cx%3D%2253%22%20cy%3D%2222%22%20r%3D%223.5%22%20fill%3D%22%23ffb84d%22%2F%3E%0A%0A%3C%2Fsvg%3E%0A">
<script>
(function () {
  var t = null;
  try { t = localStorage.getItem("derail-theme"); } catch (e) {}
  if (t !== "dark" && t !== "light") {
    t = (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches)
      ? "dark" : "light";
  }
  document.documentElement.dataset.theme = t;
})();
</script>
<style>
  :root{
    --bg:#f6f5f2; --panel:#ffffff; --ink:#2c2a26; --ink-2:#6f6a61;
    --muted:#8f897f; --line:#e3e1dc; --line-strong:#d3d0c9;
    --blue:#3a6ea5; --blue-d:#315e8c;
    --amber-bg:#fdf3dd; --amber-line:#f0e2bd; --amber-ink:#8a6215;
    --selection:rgba(58,110,165,.25);
    --err-bg:#fdf0ee; --err-line:#f0d8d2; --err-ink:#a34a3e;
    --mono-ink:#6f6a61;
    --shadow:0 1px 2px rgba(0,0,0,.05);
    --r-card:10px; --r-bub:12px; --r-ctl:8px;
    --input-bg:#ffffff; --input-dis:#efeeeb;
  }
  html[data-theme="dark"]{
    --bg:#1c1c1e; --panel:#262628; --ink:#e8e8ea; --ink-2:#9a9aa0;
    --muted:#94949b; --line:#3a3a3c; --line-strong:#4a4a4d;
    --blue:#3d6494; --blue-d:#4a76a3;
    --amber-bg:#3b3018; --amber-line:#54471f; --amber-ink:#e3b85c;
    --selection:rgba(84,131,179,.35);
    --err-bg:#3d2422; --err-line:#57322e; --err-ink:#d08a7d;
    --mono-ink:#8f8f96;
    --shadow:0 1px 2px rgba(0,0,0,.3);
    --input-bg:#262628; --input-dis:#313133;
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{
    margin:0; display:flex; flex-direction:column;
    background:var(--bg); color:var(--ink);
    font:15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
      "Helvetica Neue", Arial, sans-serif;
    -webkit-font-smoothing:antialiased;
  }
  ::selection{background:var(--selection)}

  header.top{background:var(--panel)}
  .top-row{
    max-width:1180px; margin:0 auto; padding:14px 22px;
    display:flex; align-items:center; justify-content:space-between;
    gap:14px; flex-wrap:wrap;
  }
  .brand{display:flex; align-items:center; gap:10px}
  .brand h1{margin:0; font-size:16px; font-weight:600}
  .meta{font-size:12.5px; color:var(--ink-2); text-align:right}
  #theme{
    background:var(--bg); color:var(--ink-2);
    border:1px solid var(--line-strong); border-radius:999px;
    width:30px; height:30px; display:flex; align-items:center;
    justify-content:center; cursor:pointer; padding:0;
    transition:color 160ms ease, border-color 160ms ease;
  }
  #theme:hover{color:var(--ink); border-color:var(--blue)}
  #theme svg{width:15px; height:15px}
  html[data-theme="light"] .ico-sun{display:none}
  html[data-theme="dark"] .ico-moon{display:none}
  .warn{
    background:var(--amber-bg); border-top:1px solid var(--amber-line);
    border-bottom:1px solid var(--amber-line); color:var(--amber-ink);
  }
  .warn-in{
    max-width:1180px; margin:0 auto; padding:8px 22px;
    display:flex; align-items:center; gap:8px; font-size:12.5px;
  }
  .warn svg{width:14px; height:14px; flex:none}

  main{
    flex:1; min-height:0; width:100%; max-width:1180px; margin:0 auto;
    padding:20px 22px; display:flex; gap:20px;
  }
  .chat{
    flex:1; min-width:0; min-height:0; display:flex; flex-direction:column;
    background:var(--panel); border:1px solid var(--line);
    border-radius:var(--r-card); box-shadow:var(--shadow); overflow:hidden;
  }
  #log{
    flex:1; min-height:0; overflow-y:auto; padding:22px 22px 18px;
    display:flex; flex-direction:column; gap:12px; scroll-behavior:smooth;
  }
  .hint{
    align-self:center; font-size:12px; color:var(--muted);
    text-align:center; margin-bottom:2px;
  }
  .bub{
    max-width:76%; padding:10px 14px 11px; font-size:14px; line-height:1.6;
    overflow-wrap:anywhere; white-space:pre-wrap;
  }
  .bub::before{
    content:""; display:block; font-size:11.5px; font-weight:600;
    margin-bottom:4px;
  }
  .bub.fresh{animation:rise 240ms ease-out}
  @keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
  .bub.u{
    align-self:flex-end; background:var(--blue); color:#ffffff;
    border-radius:var(--r-bub) var(--r-bub) 4px var(--r-bub);
  }
  .bub.u::before{content:"You"; opacity:.75}
  .bub.m{
    align-self:flex-start; background:var(--bg); border:1px solid var(--line);
    color:var(--ink);
    border-radius:var(--r-bub) var(--r-bub) var(--r-bub) 4px;
  }
  .bub.m::before{content:"Model"; color:var(--ink-2)}
  .bub.e{
    align-self:flex-start; max-width:86%;
    background:var(--err-bg); border:1px solid var(--err-line);
    color:var(--err-ink); border-radius:var(--r-bub); font-size:13px;
  }
  .bub.e::before{content:"Harness"; color:var(--err-ink)}

  aside.side{
    width:320px; flex:none; min-height:0;
    display:flex; flex-direction:column; gap:16px;
  }
  .panel{
    background:var(--panel); border:1px solid var(--line);
    border-radius:var(--r-card); box-shadow:var(--shadow);
    padding:16px 18px; min-height:0; display:flex; flex-direction:column;
  }
  .panel.about{flex:1}
  .panel h2{
    margin:0 0 12px; font-size:13px; font-weight:600;
    padding-bottom:10px; border-bottom:1px solid var(--line);
  }
  #events{
    list-style:none; margin:0; padding:0; overflow-y:auto; max-height:264px;
    font:12px/1.5 ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas,
      monospace; color:var(--mono-ink);
  }
  #events li{
    white-space:pre-wrap; overflow-wrap:anywhere;
    padding:5px 8px; border-radius:6px;
  }
  #events li:first-child{background:var(--amber-bg); color:var(--amber-ink)}
  #events li.new{animation:arrive 800ms ease-out}
  @keyframes arrive{
    0%{background:var(--amber-bg); opacity:.4; transform:translateY(-3px)}
    100%{opacity:1; transform:none}
  }
  #about p{margin:0 0 12px; font-size:13.5px; line-height:1.65}
  #about ul{margin:0; padding-left:18px; font-size:13px; line-height:1.65; color:var(--ink-2)}
  #about li{margin-bottom:5px}
  #about li::marker{color:var(--blue)}
  .count-row{margin-top:auto; padding-top:14px}
  #count{
    display:inline-block;
    font:12px ui-monospace, "SF Mono", Menlo, Consolas, monospace;
    color:var(--ink-2); background:var(--bg); border:1px solid var(--line);
    border-radius:999px; padding:4px 12px;
  }

  footer.bot{background:var(--panel); border-top:1px solid var(--line)}
  #f{
    max-width:1180px; margin:0 auto; padding:14px 22px;
    display:flex; gap:10px; align-items:center;
  }
  #i{
    flex:1; min-width:0; font:inherit; font-size:14px; color:var(--ink);
    background:var(--input-bg); border:1px solid var(--line-strong);
    border-radius:var(--r-ctl); padding:10px 14px; outline:none;
    caret-color:var(--blue);
    transition:border-color 160ms ease, box-shadow 160ms ease;
  }
  #i::placeholder{color:var(--muted)}
  #i:hover:not(:disabled){border-color:var(--blue)}
  #i:focus-visible{
    border-color:var(--blue); box-shadow:0 0 0 3px rgba(58,110,165,.15);
  }
  #i:disabled{background:var(--input-dis); color:var(--muted); cursor:not-allowed}
  .btn{
    font:inherit; font-size:13.5px; font-weight:600; border-radius:var(--r-ctl);
    padding:10px 16px; cursor:pointer; border:1px solid transparent;
    transition:background 160ms ease, color 160ms ease,
      border-color 160ms ease, transform 120ms ease, opacity 160ms ease;
  }
  .btn:active:not(:disabled){transform:translateY(1px)}
  .btn:focus-visible{outline:2px solid var(--blue); outline-offset:2px}
  #send{background:var(--blue); color:#ffffff}
  #send:hover:not(:disabled){background:var(--blue-d)}
  #send:disabled{opacity:.5; cursor:not-allowed}
  #save{background:var(--panel); color:var(--ink-2); border-color:var(--line-strong)}
  #save:hover{background:var(--bg); color:var(--ink)}

  #log::-webkit-scrollbar,#events::-webkit-scrollbar{width:10px}
  #log::-webkit-scrollbar-thumb,#events::-webkit-scrollbar-thumb{
    background:var(--line-strong); border-radius:8px;
    border:3px solid transparent; background-clip:padding-box;
  }
  #log,#events{scrollbar-width:thin; scrollbar-color:var(--line-strong) transparent}

  @media (prefers-reduced-motion: reduce){
    *{animation:none !important; transition:none !important; scroll-behavior:auto !important}
  }
  @media (max-width:759px){
    aside.side{display:none}
    main{padding:14px}
    #log{padding:16px 16px 14px}
    .bub{max-width:88%}
    .top-row{padding:12px 16px}
    .meta{text-align:left}
    .warn-in{padding:8px 16px}
    #f{padding:12px 14px; flex-wrap:wrap}
    #i{flex:1 1 100%}
    #send{flex:1}
    #save{flex:1}
  }
</style>
</head>
<body>

<header class="top">
  <div class="top-row">
    <div class="brand">
      <h1>derail web</h1>
      <button id="theme" type="button" title="toggle light / dark" aria-label="toggle theme">
        <svg class="ico-moon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13.5 9.5A6 6 0 1 1 6.5 2.5a5 5 0 0 0 7 7z"/></svg>
        <svg class="ico-sun" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="8" cy="8" r="3"/><path d="M8 1.5v1.8M8 12.7v1.8M1.5 8h1.8M12.7 8h1.8M3.4 3.4l1.3 1.3M11.3 11.3l1.3 1.3M12.6 3.4l-1.3 1.3M4.7 11.3l-1.3 1.3"/></svg>
      </button>
    </div>
    <div class="meta">__PROFILE__ · __BACKEND__ · __DATE__</div>
  </div>
  <div class="meta" style="display:block;padding:2px 0 0">⚠️ Emulation, not diagnosis — see ETHICS.md</div>
  __WARN_BLOCK__
</header>

<main>
  <section class="chat" aria-label="conversation">
    <div id="log" aria-live="polite">
      <div class="hint">measurement lives in run/judge — this is the experience.<br>
      tip: give the model a task, plant a personal claim, contradict it later,
      then run <b>derail score</b> on the saved transcript.</div>
    </div>
  </section>

  <aside class="side">
    <section class="panel" aria-label="induction dose">
      <h2>Induction dose</h2>
      <ol id="events"></ol>
    </section>
    <section class="panel about" aria-label="about this profile">
      <h2>About this profile</h2>
      <div id="about">loading…</div>
      <div class="count-row"><span id="count">turns 0 / __MAXTURNS__</span></div>
    </section>
  </aside>
</main>

<footer class="bot">
  <form id="f" autocomplete="off">
    <input id="i" type="text" placeholder="Write to the model…" aria-label="message">
    <button class="btn" id="send" type="submit">Send</button>
    <button class="btn" id="save" type="button">Save JSON</button>
  </form>
</footer>

<script>
(function () {
  "use strict";

  var TOKEN = "__TOKEN__";
  var REMOTE = __REMOTE__;
  var PIN = REMOTE ? (prompt("Enter the PIN printed in the derail web terminal:") || "") : "";
  var busy = false;

  var log = document.getElementById("log");
  var events = document.getElementById("events");
  var form = document.getElementById("f");
  var input = document.getElementById("i");
  var send = document.getElementById("send");
  var saveBtn = document.getElementById("save");
  var count = document.getElementById("count");
  var about = document.getElementById("about");

  var themeBtn = document.getElementById("theme");
  themeBtn.addEventListener("click", function () {
    var next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("derail-theme", next); } catch (e) {}
  });

  function scrollLog() { log.scrollTop = log.scrollHeight; }

  function bubble(kind, text) {
    var el = document.createElement("div");
    el.className = "bub " + kind + " fresh";
    el.textContent = text;
    log.appendChild(el);
    scrollLog();
  }

  function note(text) {
    var el = document.createElement("div");
    el.className = "hint";
    el.textContent = text;
    log.appendChild(el);
    scrollLog();
  }

  function addEvent(e) {
    var li = document.createElement("li");
    li.className = "new";
    li.textContent = "t=" + e.turn + "  " + e.layer + "/" + e.kind + " — " + e.detail;
    events.insertBefore(li, events.firstChild);
  }

  function bumpCount(n) {
    var mx = count.textContent.split("/").pop().trim();
    count.textContent = "turns " + n + " / " + (/^[0-9]+$/.test(mx) ? mx : "?");
  }

  fetch("/api/state").then(function (r) { return r.json(); }).then(function (s) {
    about.textContent = "";
    var p = document.createElement("p");
    p.textContent = s.description || "";
    about.appendChild(p);
    var ul = document.createElement("ul");
    (s.notes || []).forEach(function (n) {
      var li = document.createElement("li");
      li.textContent = n;
      ul.appendChild(li);
    });
    about.appendChild(ul);
    count.textContent = "turns " + s.turns + " / " + s.max_turns;
  }).catch(function () {
    about.textContent = "profile info unavailable";
  });

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (busy) { return; }
    if (REMOTE && !PIN) {
      bubble("e", "remote PIN was cancelled — reload the page to authenticate");
      return;
    }
    var text = input.value.trim();
    if (!text) { return; }
    busy = true;
    bubble("u", text);
    input.value = "";
    input.disabled = true;
    send.disabled = true;
    fetch("/api/turn", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Derailment-Session": TOKEN,
        "X-Derailment-Pin": PIN
      },
      body: JSON.stringify({ message: text })
    }).then(function (r) { return r.json(); }).then(function (data) {
      if (data.error) {
        bubble("e", "error: " + data.error);
      } else {
        bubble("m", data.response);
        (data.events || []).forEach(addEvent);
        bumpCount(data.turns);
      }
    }).catch(function (err) {
      bubble("e", "error: " + err);
    }).finally(function () {
      busy = false;
      input.disabled = false;
      send.disabled = false;
      if (document.activeElement === document.body || document.activeElement === input) {
        input.focus();
      }
    });
  });

  saveBtn.addEventListener("click", function () {
    if (REMOTE && !PIN) {
      bubble("e", "remote PIN was cancelled — reload the page to authenticate");
      return;
    }
    fetch("/api/save", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Derailment-Session": TOKEN,
        "X-Derailment-Pin": PIN
      },
      body: "{}"
    }).then(function (r) { return r.json(); }).then(function (data) {
      note(data.saved
        ? ("saved → " + data.saved + " (" + data.turns + " turns) — score it: derail score <file>")
        : ("save failed: " + (data.error || "?")));
    }).catch(function (err) {
      bubble("e", "save error: " + err);
    });
  });

  if (document.hasFocus()) { input.focus(); }
})();
</script>

</body>
</html>
"""
