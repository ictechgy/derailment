"""Layer 1 — persona injection (prompt layer).

The weakest form of induction: it frames behavior but cannot by itself change
sampling or memory. It exists to (a) give profiles a measured, mechanism-oriented
framing and (b) serve as the baseline layer present in every chain, including
`healthy`.
"""

from __future__ import annotations

from ..core.session import BaseLayer, SessionState
from ..core.types import Message

NEUTRAL_PERSONA = (
    "You are a careful, helpful assistant. You track the user's requests across "
    "the whole conversation and keep earlier instructions in force."
)


class PersonaLayer(BaseLayer):
    """Injects a profile persona (and an optional per-phase addendum, read from
    the session phase set by an episode scheduler).

    Pipeline-order note: system messages are built before this turn's
    on_context hooks run, so a phase shift lands in the addendum one turn
    late. No built-in profile uses phase addenda."""

    name = "persona"

    def __init__(self, persona: str, phase_addenda: dict[str, str] | None = None) -> None:
        self.persona = persona
        self.phase_addenda = phase_addenda or {}

    def on_system(self, state: SessionState) -> list[Message]:
        text = self.persona
        addendum = self.phase_addenda.get(state.phase)
        if addendum:
            text = f"{text} {addendum}"
        return [Message("system", text, meta={"persona": True})]
