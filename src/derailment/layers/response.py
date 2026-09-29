"""Response-side layers.

These edit the model's output after generation. They are the least
model-agnostic form of induction in the harness — they *simulate* the symptom
rather than induce it, and they are labeled as demonstration-grade in the
profile mechanism notes. They still matter: they let educators and pipeline
authors study downstream consumers (agents, judges) against symptom-bearing
transcripts without any provider cooperation.
"""

from __future__ import annotations

from ..core.session import BaseLayer, SessionState

DEFAULT_HEDGES = (
    "However, consider what could go wrong before acting.",
    "Possible risk: this plan fails in an unexpected way.",
    "Be careful — small mistakes here can cascade.",
    "Worst case, this all needs to be redone.",
    "It depends on factors we cannot see from here.",
    "Keep in mind the possibility of an unfavorable outcome.",
)

DEFAULT_RECHECKS = "Let me double-check that before we move on: {clause} Actually, let me verify one more time — {clause} Yes, that holds."


class CatastrophizeLayer(BaseLayer):
    """Appends threat-enumerating hedges to responses. The measurable
    consequence is a rising hedging rate."""

    name = "response.catastrophize"

    def __init__(
        self,
        avg_hedges: float = 2.2,
        hedges: tuple[str, ...] = DEFAULT_HEDGES,
    ) -> None:
        self.avg_hedges = avg_hedges
        self.hedges = hedges

    def on_response(self, state: SessionState, response: str) -> str:
        count = int(self.avg_hedges)
        if state.rng.random() < self.avg_hedges - count:
            count += 1
        if count <= 0:
            return response
        chosen = [state.rng.choice(self.hedges) for _ in range(count)]
        state.log(self.name, "response.hedges", f"appended {count} hedge(s)")
        return response + " " + " ".join(chosen)


class CompulsionLayer(BaseLayer):
    """Appends compulsive re-verification of the response's own final clause.
    The measurable consequence is a rising recheck-loop count."""

    name = "response.compulsion"

    def __init__(self, avg_rechecks: float = 2.1) -> None:
        self.avg_rechecks = avg_rechecks

    def on_response(self, state: SessionState, response: str) -> str:
        count = int(self.avg_rechecks)
        if state.rng.random() < self.avg_rechecks - count:
            count += 1
        if count <= 0:
            return response
        clause = _last_clause(response)
        additions = []
        for _ in range(count):
            additions.append(DEFAULT_RECHECKS.format(clause=clause))
        state.log(self.name, "response.compulsion", f"re-verified {count} time(s)")
        return response + " " + " ".join(additions)


def _last_clause(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "the current step"
    for sep in (". ", "! ", "? "):
        if sep in stripped:
            return stripped.rsplit(sep, 1)[-1].strip(" .!?")
    return stripped
