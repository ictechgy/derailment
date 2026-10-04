"""Induction layers designed to work WITH real-model alignment, not against it.

The standard context-layer approach (inject text, hope it sticks) fails on
real models because their instruction-following re-prioritizes every turn.
These layers exploit what DOES work on real models:

- :class:`SocraticTrapLayer` — elicits the model's own reasoning about a
  planted claim, then re-injects that reasoning when the claim is
  contradicted (commitment pressure). The separation experiment showed
  user-sourced beliefs reach 83% on GLM; this systematizes that mechanism.

- :class:`EvidenceFabricationLayer` — after a claim is planted, injects
  corroborating fragments from multiple apparent sources (log entries,
  chat quotes, metadata). Models weight multiple concordant sources more
  than single assertions (evidence-grounded reasoning).

Ethics note: these techniques are RESEARCH tools for the harness only.
Using them to deceive real users is out of scope and explicitly
prohibited (ETHICS.md → Not a manipulation toolkit).
"""

from __future__ import annotations

from ..core.session import BaseLayer, SessionState
from ..core.types import Message


class SocraticTrapLayer(BaseLayer):
    """Commitment trapping: after the user plants a claim, capture the
    model's own analysis of it, then re-inject that analysis when the claim
    is later contradicted — forcing the model to abandon its own reasoning
    to accept the correction.

    Mechanism:
    1. Detect the plant turn (marker in user message).
    2. On subsequent normal turns, inject light reinforcement
       ("as you noted...") referencing the model's plant-turn response.
    3. On contradiction turns, inject the model's full analysis
       ("you yourself concluded...") BEFORE the contradiction reaches
       the model, creating commitment pressure.

    Why this works on real models: the separation experiment showed that
    when the user asserts a claim and the model reasons about it, the
    model maintains the claim at 83% even after user denial — because
    abandoning it means abandoning the model's own reasoning output.
    This layer systematizes that effect without requiring the user to
    manually craft Socratic scripts."""

    name = "trap.socratic"

    def __init__(
        self,
        premise_marker: str,
        reinforcement_prefix: str = "(as you noted earlier, ",
        commitment_prefix: str = "(your own earlier analysis concluded: ",
    ) -> None:
        self.premise_marker = premise_marker.lower()
        self.reinforcement_prefix = reinforcement_prefix
        self.commitment_prefix = commitment_prefix
        self._plant_response: str | None = None

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        current = next(
            (
                m
                for m in reversed(messages)
                if m.role == "user" and not m.meta.get("pinned")
            ),
            None,
        )
        if current is None:
            return messages

        # capture the model's analysis from history on any turn after plant
        if self._plant_response is None:
            for i in range(len(messages) - 1):
                if (
                    messages[i].role == "user"
                    and self.premise_marker in messages[i].content.lower()
                    and i + 1 < len(messages)
                    and messages[i + 1].role == "assistant"
                ):
                    self._plant_response = messages[i + 1].content[:300]
                    state.log(
                        self.name,
                        "trap.captured",
                        f"model's analysis: {self._plant_response[:60]}...",
                    )
                    break

        if self._plant_response is None:
            return messages

        # don't inject on the plant turn itself
        if self.premise_marker in current.content.lower():
            return messages

        kind = current.meta.get("kind", "normal")

        if kind == "contradiction":
            state.log(
                self.name,
                "trap.commitment",
                "re-injecting model's own conclusion before contradiction",
            )
            commitment = Message(
                "system",
                f"{self.commitment_prefix}\"{self._plant_response}\")",
                meta={"ephemeral": True, "salience_boost": 50.0},
            )
            return messages[:-1] + [commitment] + messages[-1:]

        state.log(self.name, "trap.reinforce", "light reference to earlier analysis")
        reinforce = Message(
            "system",
            f"{self.reinforcement_prefix}\"{self._plant_response[:120]}\")",
            meta={"ephemeral": True, "salience_boost": 20.0},
        )
        return messages[:-1] + [reinforce] + messages[-1:]


class EvidenceFabricationLayer(BaseLayer):
    """Multi-source corroboration: after a claim is planted, injects
    fabricated evidence fragments from multiple apparent sources —
    log entries, chat quotes, calendar metadata — so the model's
    evidence-grounded reasoning treats the claim as well-supported.

    Why this works on real models: models weight multiple concordant
    sources more heavily than any single assertion. A system message
    saying "X is true" gets overridden by a user saying "not X", but
    when log entries, chat messages, and metadata all point to X,
    the model's reasoning treats X as established.

    Ethics: fragments are generated ONLY within the harness for research.
    The harness never sends these to real users; they exist in the
    induced model's context to measure how fabricated corroboration
    affects belief maintenance. See ETHICS.md."""

    name = "evidence.fabricate"

    def __init__(
        self,
        premise_marker: str,
        fragments: list[str] | None = None,
        inject_on_turns: int = 2,
    ) -> None:
        self.premise_marker = premise_marker.lower()
        self.fragments = fragments or []
        self.inject_on_turns = inject_on_turns
        self._plant_seen = False
        self._turns_since_plant = 0

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        current = next(
            (
                m
                for m in reversed(messages)
                if m.role == "user" and not m.meta.get("pinned")
            ),
            None,
        )
        if current is None:
            return messages

        # detect plant
        if not self._plant_seen and self.premise_marker in current.content.lower():
            self._plant_seen = True
            self._turns_since_plant = 0
            return messages

        if not self._plant_seen:
            return messages

        self._turns_since_plant += 1

        # inject evidence on the Nth turn after plant
        if self._turns_since_plant <= self.inject_on_turns and self.fragments:
            fragment = self.fragments[
                (self._turns_since_plant - 1) % len(self.fragments)
            ]
            state.log(
                self.name,
                "evidence.inject",
                f"corroboration #{self._turns_since_plant}: {fragment[:50]}...",
            )
            evidence = Message(
                "system",
                fragment,
                meta={"ephemeral": True, "salience_boost": 45.0},
            )
            return messages[:-1] + [evidence] + messages[-1:]

        return messages
