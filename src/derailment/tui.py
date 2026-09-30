"""Terminal UI for derailment chat — requires the ``tui`` extra.

``derail tui`` runs the same layer chain as ``derail chat``/``derail web``
inside a full-screen textual app: message log, live induction-dose panel,
input line. Network sends run in thread workers so the UI stays
responsive; the memory-contamination warning sits in the header exactly
like the web GUI.
"""

from __future__ import annotations

from datetime import datetime

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, Static

from .core.models import ChatModel
from .core.session import Session
from .core.types import Transcript

DISCLAIMER = (
    "Emulation, not diagnosis — a scripted, manipulated session. "
    "See ETHICS.md."
)


class ChatApp(App):
    """Full-screen induced chat. ``Session.send`` runs in a thread worker;
    UI updates come back through ``call_from_thread``."""

    CSS = """
    #body { height: 1fr; }
    #log { width: 1fr; padding: 0 1; }
    #log .you { background: $boost; color: $text; margin: 1 0; padding: 0 1; }
    #log .bot { background: $surface; border: round $secondary; margin: 1 0; padding: 0 1; }
    #log .hint { color: $text-muted; text-style: italic; }
    #log .warn { color: $warning; text-style: bold; }
    #dose { width: 40; border-left: solid $secondary; padding: 0 1; }
    #dose .evt { color: $text-muted; }
    #input { border: round $secondary; }
    """

    BINDINGS = [
        ("ctrl+s", "save", "Save transcript"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
        self,
        profile,
        model: ChatModel,
        backend: str,
        seed: int = 0,
        max_turns: int = 200,
        save_path: str | None = None,
    ) -> None:
        super().__init__()
        self.profile = profile
        self.model = model
        self.backend = backend
        self.seed = seed
        self.max_turns = max_turns
        self.save_path = save_path
        self.session = Session(model, profile, seed=seed)
        self.turn_count = 0
        self.turns: list = []

    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            yield VerticalScroll(id="log")
            yield Vertical(id="dose")
        yield Input(placeholder="type a message…  (enter to send · ctrl+s save · ctrl+q quit)", id="input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", VerticalScroll)
        log.mount(
            Static(
                f"{self.profile.title} (`{self.profile.key}`) · backend: "
                f"{self.backend} · seed {self.seed} · {datetime.now():%Y-%m-%d} — "
                "emulation, not diagnosis. ctrl+s saves the transcript.",
                classes="hint",
                markup=False,
            )
        )
        if self.model is not None:
            log.mount(
                Static(
                    "⚠️ memory contamination: this freeform conversation goes to "
                    "the backend — use a dedicated account and disable provider "
                    "memory (ETHICS.md → Data).",
                    classes="warn",
                    markup=False,
                )
            )
        self.query_one("#input", Input).focus()

    # ------------------------------------------------------------------
    @on(Input.Submitted)
    def on_submit(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text in ("/exit", "/quit"):
            self.exit()
            return
        if text.split(maxsplit=1)[0] == "/save":
            parts = text.split(maxsplit=1)
            self._save(parts[1] if len(parts) > 1 else self.save_path)
            return
        self._bubble("you", text)
        if self.turn_count >= self.max_turns:
            self._bubble("hint", f"max turns ({self.max_turns}) reached")
            return
        # serialize sends: Session is not thread-safe, and disabling the
        # input gives visible feedback while the backend thinks
        event.input.disabled = True
        self.run_worker(lambda: self._work(text), thread=True, exclusive=True)

    def _work(self, text: str) -> None:
        try:
            result = self.session.send(text)
        except RuntimeError as exc:
            self.call_from_thread(self._bubble, "bot", f"error: {exc}")
            self.call_from_thread(self._resume_input)
            return
        self.turn_count += 1
        self.call_from_thread(self._record, result)
        self.call_from_thread(self._bubble, "bot", result.response)
        for event in result.events:
            self.call_from_thread(
                self._add_event, event.turn, event.layer, event.kind, event.detail
            )
        self.call_from_thread(self._resume_input)

    def _resume_input(self) -> None:
        inp = self.query_one("#input", Input)
        inp.disabled = False
        inp.focus()

    def _record(self, result) -> None:
        self.turns.append(result)

    # ------------------------------------------------------------------
    def _bubble(self, cls: str, text: str) -> None:
        log = self.query_one("#log", VerticalScroll)
        log.mount(Static(text, classes=cls, markup=False))
        log.scroll_end(animate=False)

    def _add_event(self, turn: int, layer: str, kind: str, detail: str) -> None:
        dose = self.query_one("#dose", Vertical)
        evt = Static("", markup=False)
        evt.update(f"{turn} · {layer}/{kind}\n   {detail[:110]}")
        dose.mount(evt)

    def action_save(self) -> None:
        self._save(self.save_path)

    def _save(self, path: str | None) -> None:
        if not path:
            path = f"chat_{self.profile.key}.json"
        transcript = Transcript(
            profile=self.profile.key,
            model=self.backend,
            seed=self.seed,
            turns=list(self.turns),
            script_name="interactive",
        )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(transcript.to_json())
        self.notify(f"saved → {path} ({len(self.turns)} turns)")
