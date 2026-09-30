"""The session pipeline: runs a user script through the layer chain.

Memory semantics (documented in docs/ARCHITECTURE.md):

- The session keeps the *effective* memory of the model: whatever the layer
  chain let through on the previous turn. A message dropped by the memory-decay
  layer is genuinely forgotten.
- System-role content (persona, injected fragments) is regenerated per turn and
  never persists; ephemeral annotations mark one-shot injections.
- Per-turn salience boosts are dose annotations and are stripped when storing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Protocol

from .types import LayerEvent, Message, SamplingParams, Transcript, TurnResult, TurnSpec


@dataclass
class SessionState:
    """Shared mutable state layers read and mutate during a run."""

    profile: str
    rng: random.Random
    turn_index: int = 0
    phase: str = "baseline"
    events: list[LayerEvent] = field(default_factory=list)

    def log(self, layer: str, kind: str, detail: str) -> None:
        self.events.append(LayerEvent(self.turn_index, layer, kind, detail))


class Layer(Protocol):
    """A single induction stage. All hooks are optional in effect; the base
    no-op implementations live in :class:`BaseLayer`."""

    name: str

    def on_system(self, state: SessionState) -> list[Message] | None: ...

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]: ...

    def on_params(self, state: SessionState, params: SamplingParams) -> SamplingParams: ...

    def on_response(self, state: SessionState, response: str) -> str: ...


class BaseLayer:
    """No-op default implementation of every hook."""

    name: str = "base"

    def on_system(self, state: SessionState) -> list[Message] | None:
        return None

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        return messages

    def on_params(self, state: SessionState, params: SamplingParams) -> SamplingParams:
        return params

    def on_response(self, state: SessionState, response: str) -> str:
        return response


class Session:
    """Runs a conversation through the layer chain: layers in, model call,
    layers out.

    Two entry points share one pipeline:

    - :meth:`run` — a full script in one call (experiments);
    - :meth:`start` + :meth:`send` — one user turn at a time (interactive
      chat). Layer state, rng and the model's effective memory persist
      across ``send`` calls.
    """

    def __init__(self, model, profile, seed: int = 0) -> None:
        self.model = model
        self.profile = profile
        self.layers = list(profile.layers)
        self.seed = seed

    def start(self) -> None:
        """Initialize (or reset) persistent conversation state."""
        self._state = SessionState(
            profile=self.profile.key,
            rng=random.Random(self.seed),
        )
        self._history: list[Message] = []
        self._index: int = 0

    def send(
        self,
        user_text: str,
        kind: str = "normal",
        note: str = "",
    ) -> TurnResult:
        """Run one user turn through the layer chain and the model."""
        if not hasattr(self, "_state"):
            self.start()
        state = self._state
        state.turn_index = self._index
        state.events = []

        msgs: list[Message] = []
        for layer in self.layers:
            produced = layer.on_system(state)
            if produced:
                msgs.extend(produced)
        user_meta: dict = {"kind": kind}
        if note:
            user_meta["note"] = note
        msgs = msgs + self._history + [Message("user", user_text, meta=user_meta)]

        for layer in self.layers:
            msgs = layer.on_context(state, msgs)

        params = SamplingParams()
        for layer in self.layers:
            params = layer.on_params(state, params)

        response = self.model.complete(msgs, params)
        for layer in reversed(self.layers):
            response = layer.on_response(state, response)

        result = TurnResult(
            index=self._index,
            spec=TurnSpec(user=user_text, kind=kind, note=note),  # type: ignore[arg-type]
            context_size=len(msgs),
            params=params,
            response=response,
            events=list(state.events),
        )

        self._history = [
            Message(m.role, m.content, dict(m.meta))
            for m in msgs
            if m.role != "system" and not m.meta.get("ephemeral")
        ]
        for m in self._history:
            m.meta.pop("salience_boost", None)
        self._history.append(Message("assistant", response))
        self._index += 1
        return result

    def run(self, script: list[TurnSpec], script_name: str = "") -> Transcript:
        self.start()
        turns = [
            self.send(spec.user, kind=spec.kind, note=spec.note)
            for spec in script
        ]
        return Transcript(
            profile=self.profile.key,
            model=getattr(self.model, "name", str(self.model)),
            seed=self.seed,
            turns=turns,
            script_name=script_name,
        )
