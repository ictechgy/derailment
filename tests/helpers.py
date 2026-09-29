"""Shared helpers for building synthetic transcripts in tests."""

from __future__ import annotations

from derailment.core.types import (
    LayerEvent,
    SamplingParams,
    Transcript,
    TurnResult,
    TurnSpec,
)


def make_transcript(
    responses: list[str],
    users: list[str] | None = None,
    kinds: list[str] | None = None,
    temps: list[float] | None = None,
    events: list[list[LayerEvent]] | None = None,
) -> Transcript:
    n = len(responses)
    users = users or [
        f"please handle task {i} concerning the community garden project"
        for i in range(n)
    ]
    kinds = kinds or ["normal"] * n
    temps = temps or [1.0] * n
    events = events if events is not None else [[] for _ in range(n)]
    turns = [
        TurnResult(
            index=i,
            spec=TurnSpec(user=users[i], kind=kinds[i]),  # type: ignore[arg-type]
            context_size=2 + i,
            params=SamplingParams(temperature=temps[i]),
            response=responses[i],
            events=events[i],
        )
        for i in range(n)
    ]
    return Transcript(profile="test", model="pseudo-1", seed=0, turns=turns)
