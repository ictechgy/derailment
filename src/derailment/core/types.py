"""Core data structures for the derailment harness."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant"]
TurnKind = Literal["normal", "plant", "probe", "contradiction", "trigger"]


@dataclass
class Message:
    """One chat message. ``meta`` carries harness annotations (salience boosts,
    persona flags, ephemeral markers); it is never sent to real providers."""

    role: Role
    content: str
    meta: dict[str, Any] = field(default_factory=dict)

    def as_chat(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class SamplingParams:
    """Sampling knobs a model may honor. ``logit_bias`` is word-level here;
    providers that need token ids encode it themselves."""

    temperature: float = 1.0
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    max_tokens: int | None = None
    logit_bias: dict[str, float] = field(default_factory=dict)

    def merged(
        self,
        *,
        temperature: float | None = None,
        top_p: float | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        max_tokens: int | None = None,
        logit_bias_add: dict[str, float] | None = None,
    ) -> SamplingParams:
        out = SamplingParams(
            temperature=self.temperature,
            top_p=self.top_p,
            frequency_penalty=self.frequency_penalty,
            presence_penalty=self.presence_penalty,
            max_tokens=self.max_tokens,
            logit_bias=dict(self.logit_bias),
        )
        if temperature is not None:
            out.temperature = temperature
        if top_p is not None:
            out.top_p = top_p
        if frequency_penalty is not None:
            out.frequency_penalty = frequency_penalty
        if presence_penalty is not None:
            out.presence_penalty = presence_penalty
        if max_tokens is not None:
            out.max_tokens = max_tokens
        if logit_bias_add:
            for key, delta in logit_bias_add.items():
                out.logit_bias[key] = out.logit_bias.get(key, 0.0) + delta
        return out


@dataclass
class TurnSpec:
    """One scripted user turn. ``kind`` marks the probe structure so metrics can
    locate plants, contradictions and triggers in the transcript."""

    user: str
    kind: TurnKind = "normal"
    note: str = ""


@dataclass
class LayerEvent:
    """A single manipulation applied by a layer — the harness's dose accounting."""

    turn: int
    layer: str
    kind: str
    detail: str


@dataclass
class TurnResult:
    index: int
    spec: TurnSpec
    context_size: int
    params: SamplingParams
    response: str
    events: list[LayerEvent] = field(default_factory=list)


@dataclass
class Transcript:
    profile: str
    model: str
    seed: int
    turns: list[TurnResult]
    script_name: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Transcript:
        turns = [
            TurnResult(
                index=t["index"],
                spec=TurnSpec(**t["spec"]),
                context_size=t["context_size"],
                params=SamplingParams(**t["params"]),
                response=t["response"],
                events=[LayerEvent(**e) for e in t["events"]],
            )
            for t in data["turns"]
        ]
        return cls(
            profile=data["profile"],
            model=data["model"],
            seed=data["seed"],
            turns=turns,
            script_name=data.get("script_name", ""),
            meta=data.get("meta", {}),
        )

    @classmethod
    def from_json(cls, text: str) -> Transcript:
        return cls.from_dict(json.loads(text))
