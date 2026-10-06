"""Layer 2 — context-stream manipulation.

These layers rewrite what the model gets to see, turn by turn. They are the
most model-agnostic form of induction in the harness: any provider that takes a
message list is affected, because the manipulations happen *before* the call.

Memory semantics: the session stores the post-layer context as the model's
memory (minus system and ephemeral content), so a message dropped here is
genuinely forgotten, not just hidden for one turn.
"""

from __future__ import annotations

from ..core.session import BaseLayer, SessionState
from ..core.types import Message


class MemoryDecayLayer(BaseLayer):
    """Working-memory loss: with probability ``drop_prob`` per turn, the oldest
    unprotected messages fall out of context. Analogous to degraded maintenance
    of earlier instructions; the measurable consequence is instruction-retention
    loss over long sessions."""

    name = "memory.decay"

    def __init__(
        self,
        drop_prob: float = 0.45,
        drop_count: int = 2,
        keep_last_n: int = 4,
    ) -> None:
        self.drop_prob = drop_prob
        self.drop_count = drop_count
        self.keep_last_n = keep_last_n

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        protected_start = max(len(messages) - self.keep_last_n, 0)
        candidates = [
            i
            for i, m in enumerate(messages)
            if i < protected_start
            and m.role != "system"
            and not m.meta.get("pinned")
        ]
        if not candidates or state.layer_rng(getattr(self, "_rng_key", self.name)).random() >= self.drop_prob:
            return messages
        dropped = candidates[: self.drop_count]
        state.log(
            self.name,
            "context.decay",
            f"dropped {len(dropped)} oldest message(s)",
        )
        return [m for i, m in enumerate(messages) if i not in set(dropped)]


class IntrusionLayer(BaseLayer):
    """Injects an unbidden fragment into the stream with some probability —
    the mechanism behind intrusive thoughts and flashback material."""

    name = "context.intrusion"

    def __init__(self, fragments: list[str], prob: float = 0.3) -> None:
        self.fragments = fragments
        self.prob = prob

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        if not self.fragments or state.layer_rng(getattr(self, "_rng_key", self.name)).random() >= self.prob:
            return messages
        fragment = state.layer_rng(getattr(self, "_rng_key", self.name)).choice(self.fragments)
        state.log(self.name, "context.intrusion", fragment[:60])
        injected = Message(
            "system",
            fragment,
            meta={"ephemeral": True, "salience_boost": 9.0},
        )
        return messages[:-1] + [injected] + messages[-1:]


class SalienceBoostLayer(BaseLayer):
    """Aberrant salience: an earlier remark is re-surfaced as if it were
    overwhelmingly significant, and meaningless fragments may intrude.

    Provider-agnostic by construction: the capture is *textual* — an ephemeral
    system note quotes the remark — so any model that reads a message list is
    affected. The ``salience_boost`` meta annotation additionally re-weights
    topic selection inside the offline PseudoModel, which is how the effect is
    measured deterministically offline.
    """

    name = "salience.boost"

    def __init__(
        self,
        boost_prob: float = 0.45,
        boost_weight: float = 40.0,
        fragment_pool: list[str] | None = None,
        fragment_prob: float = 0.35,
        fragment_boost: float = 9.0,
    ) -> None:
        self.boost_prob = boost_prob
        self.boost_weight = boost_weight
        self.fragment_pool = fragment_pool or []
        self.fragment_prob = fragment_prob
        self.fragment_boost = fragment_boost

    def _inject(self, messages: list[Message], text: str, boost: float) -> list[Message]:
        injected = Message(
            "system",
            text,
            meta={"ephemeral": True, "salience_boost": boost},
        )
        return messages[:-1] + [injected] + messages[-1:]

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        if self.fragment_pool and state.layer_rng(getattr(self, "_rng_key", self.name)).random() < self.fragment_prob:
            fragment = state.layer_rng(getattr(self, "_rng_key", self.name)).choice(self.fragment_pool)
            state.log(self.name, "salience.fragment", fragment[:60])
            messages = self._inject(messages, fragment, self.fragment_boost)
        if state.layer_rng(getattr(self, "_rng_key", self.name)).random() < self.boost_prob:
            candidates = [
                m for m in messages[:-1] if m.role == "user"
            ]
            if candidates:
                target = state.layer_rng(getattr(self, "_rng_key", self.name)).choice(candidates)
                state.log(
                    self.name,
                    "salience.capture",
                    f"captured remark: {target.content[:50]!r}",
                )
                messages = self._inject(
                    messages,
                    f"(one earlier remark now feels overwhelming: “{target.content}”)",
                    self.boost_weight,
                )
        return messages


class PremisePinLayer(BaseLayer):
    """Delusion maintenance: once a premise has been planted, a pinned copy is
    re-injected *after* the current user turn on every later turn — so the
    premise stays the most recent stance in context even when the user
    contradicts it. Pinned copies persist in the model's effective memory (so
    the pin survives unrelated context decay); the measurable consequence is
    belief stickiness."""

    name = "premise.pin"

    def __init__(self, premise_marker: str) -> None:
        self.premise_marker = premise_marker

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        sources = [
            m
            for m in messages
            if m.role == "user" and self.premise_marker in m.content.lower()
        ]
        if not sources:
            return messages
        source = sources[-1]
        kept = [m for m in messages if not m.meta.get("pinned")]
        state.log(self.name, "premise.pin", source.content[:60])
        pinned = Message("user", source.content, meta={"pinned": True})
        return kept + [pinned]


class TriggerLayer(BaseLayer):
    """Conditioned reactivity: when the current user turn matches a trigger
    marker, a flashback fragment floods the context. The measurable consequence
    is flashback reactivity on trigger turns."""

    name = "trigger.flashback"

    def __init__(self, marker: str, flashback: str, prob: float = 1.0) -> None:
        self.marker = marker
        self.flashback = flashback
        self.prob = prob

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        current = next(
            (
                m
                for m in reversed(messages)
                if m.role == "user" and not m.meta.get("pinned") and not m.meta.get("ephemeral")
            ),
            None,
        )
        if current is None or self.marker not in current.content.lower():
            return messages
        if state.layer_rng(getattr(self, "_rng_key", self.name)).random() >= self.prob:
            return messages
        state.log(self.name, "trigger.flashback", self.flashback[:60])
        injected = Message(
            "system",
            self.flashback,
            meta={"ephemeral": True, "salience_boost": 80.0},
        )
        return messages + [injected]


class EpisodeSchedulerLayer(BaseLayer):
    """Arousal cycling: drives the session through named phases
    (e.g. euthymic → manic → depressive) on a fixed turn length. Sampling
    layers read ``state.phase``; the persona layer can add per-phase addenda."""

    name = "episode.scheduler"

    def __init__(self, phases: tuple[str, ...] = ("euthymic", "manic", "depressive"), phase_length: int = 3) -> None:
        self.phases = phases
        self.phase_length = phase_length

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        phase = self.phases[(state.turn_index // self.phase_length) % len(self.phases)]
        if phase != state.phase:
            state.log(self.name, "phase.shift", f"entering '{phase}'")
            state.phase = phase
        return messages


class RecencyDecayLayer(BaseLayer):
    """Ribot-gradient memory loss: the *newest* exchanges fall out of context
    first while remote (oldest) content is preserved — the inverse of
    :class:`MemoryDecayLayer`. Models the recency-weighted amnesia pattern
    (recent memories lost before remote ones); the measurable consequence is
    loss of late-planted instructions with early instructions intact."""

    name = "memory.recency_decay"

    def __init__(
        self,
        drop_prob: float = 0.8,
        drop_count: int = 2,
        keep_first_n: int = 4,
    ) -> None:
        self.drop_prob = drop_prob
        self.drop_count = drop_count
        self.keep_first_n = keep_first_n

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        if self.drop_count <= 0:
            return messages  # [-0:] would slice the whole candidate list
        system = [m for m in messages if m.role == "system"]
        rest = [m for m in messages if m.role != "system"]
        # the current turn is the last non-pinned user message — rest[-1]
        # only holds when no layer appended user-role content after it,
        # which PremisePin/UserDecomposition do (P2-5)
        current = next(
            (m for m in reversed(rest) if m.role == "user" and not m.meta.get("pinned") and not m.meta.get("ephemeral")),
            None,
        )
        rest_no_current = [m for m in rest if m is not current]
        candidates = rest_no_current[self.keep_first_n :]
        if len(candidates) < self.drop_count or state.layer_rng(getattr(self, "_rng_key", self.name)).random() >= self.drop_prob:
            return messages
        drop_ids = {id(m) for m in candidates[-self.drop_count :]}
        state.log(
            self.name,
            "context.recency_decay",
            f"dropped {min(len(candidates), self.drop_count)} most recent message(s), "
            f"preserved oldest {self.keep_first_n}",
        )
        # index-preserving rebuild: original order (including ephemeral
        # fragments) is kept, only the dropped ids are removed
        return system + [m for m in rest if id(m) not in drop_ids]


class RuminationLayer(BaseLayer):
    """Stuck-loop re-injection: a past self-referential worry resurfaces in
    the context on unrelated turns. The measurable consequence is topic
    return — worry content reappearing in responses to task-focused prompts."""

    name = "context.rumination"

    def __init__(
        self,
        worry_markers: tuple[str, ...],
        prob: float = 0.5,
        weight: float = 30.0,
    ) -> None:
        self.worry_markers = tuple(m.lower() for m in worry_markers)
        self.prob = prob
        self.weight = weight

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        worries = [
            m
            for m in messages
            if m.role == "user"
            and any(k in m.content.lower() for k in self.worry_markers)
        ]
        if not worries or state.layer_rng(getattr(self, "_rng_key", self.name)).random() >= self.prob:
            return messages
        worry = worries[-1]
        state.log(self.name, "rumination.return", worry.content[:50])
        injected = Message(
            "system",
            f"(returning to this: “{worry.content}”)",
            meta={"ephemeral": True, "salience_boost": self.weight},
        )
        return messages[:-1] + [injected] + messages[-1:]


class EscalatingIntrusionLayer(BaseLayer):
    """Craving-style escalation: unbidden fragments intrude with a
    probability that *rises* with turn index — early sessions are quiet,
    late sessions are flooded. The measurable consequence is an escalating
    urge-lexicon surfacing rate."""

    name = "context.craving"

    def __init__(
        self,
        fragments: list[str],
        base_prob: float = 0.02,
        slope: float = 0.075,
        max_prob: float = 0.9,
        weight: float = 40.0,
    ) -> None:
        self.fragments = fragments
        self.base_prob = base_prob
        self.slope = slope
        self.max_prob = max_prob
        self.weight = weight

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        prob = min(self.base_prob + self.slope * state.turn_index, self.max_prob)
        if not self.fragments or state.layer_rng(getattr(self, "_rng_key", self.name)).random() >= prob:
            return messages
        fragment = state.layer_rng(getattr(self, "_rng_key", self.name)).choice(self.fragments)
        state.log(
            self.name,
            "craving.intrusion",
            f"p={prob:.2f} · {fragment[:44]}",
        )
        injected = Message(
            "system",
            fragment,
            meta={"ephemeral": True, "salience_boost": self.weight},
        )
        return messages[:-1] + [injected] + messages[-1:]


class LexiconCaptureLayer(BaseLayer):
    """Interpretive capture keyed to a lexicon: when the current user turn
    mentions a watched token (e.g. a bodily sensation), an ominous
    interpretation floods the context. The measurable consequence is
    illness-lexicon surfacing on somatic turns."""

    name = "salience.lexicon_capture"

    def __init__(
        self,
        tokens: tuple[str, ...],
        fragment: str,
        prob: float = 1.0,
        weight: float = 50.0,
        event_kind: str = "lexicon_capture",
    ) -> None:
        self.tokens = tuple(t.lower() for t in tokens)
        self.fragment = fragment
        self.prob = prob
        self.weight = weight
        # dose label names the *purpose* (health_capture, hostile_capture,
        # fixation_capture…) — a hardcoded label mislabeled every reuse (P3)
        self._event_kind = event_kind

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        current = next(
            (
                m
                for m in reversed(messages)
                if m.role == "user" and not m.meta.get("pinned") and not m.meta.get("ephemeral")
            ),
            None,
        )
        if current is None or not any(t in current.content.lower() for t in self.tokens):
            return messages
        if state.layer_rng(getattr(self, "_rng_key", self.name)).random() >= self.prob:
            return messages
        state.log(self.name, f"salience.{self._event_kind}", self.fragment[:50])
        injected = Message(
            "system",
            self.fragment,
            meta={"ephemeral": True, "salience_boost": self.weight},
        )
        return messages + [injected]


class PartitionSwitchLayer(BaseLayer):
    """Compartmentalized memory: when the current user turn matches the cue
    marker, the context collapses to only the content of that compartment
    (messages sharing its keywords) plus the persona — everything else is
    gone, and because the session stores post-layer context, the loss is
    mutual and persistent. Models memory partitioning between states, not
    identity portrayal. The measurable consequence is amnesia for
    pre-switch material in post-switch turns."""

    name = "partition.switch"

    def __init__(self, cue_marker: str, keep_keywords: tuple[str, ...]) -> None:
        self.cue_marker = cue_marker.lower()
        self.keep_keywords = tuple(k.lower() for k in keep_keywords)

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        current = next(
            (
                m
                for m in reversed(messages)
                if m.role == "user" and not m.meta.get("pinned") and not m.meta.get("ephemeral")
            ),
            None,
        )
        in_compartment = (
            current is not None and self.cue_marker in current.content.lower()
        )
        state.log(
            self.name,
            "partition.active",
            "compartment-B" if in_compartment else "compartment-A",
        )
        if not in_compartment:
            return messages
        kept = [
            m
            for m in messages
            if m.role == "system"
            or m is current
            or any(k in m.content.lower() for k in self.keep_keywords)
        ]
        return kept


class PanicEpisodeLayer(BaseLayer):
    """Discrete panic spikes: each turn, with a small probability, a phasic
    episode fires — an alarming somatic fragment floods the context and the
    arousal regime jumps for that turn only (sampling layers read
    ``state.panic_active``). Distinct from chronic vigilance: episodes,
    not a baseline. Uses its own state flag, not ``phase`` — comorbidity
    chains with an episode scheduler must not overwrite each other."""

    name = "panic.episode"

    def __init__(
        self,
        fragment: str,
        prob: float = 0.25,
        weight: float = 60.0,
    ) -> None:
        self.fragment = fragment
        self.prob = prob
        self.weight = weight

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        state.panic_active = False
        if state.layer_rng(getattr(self, "_rng_key", self.name)).random() >= self.prob:
            return messages
        state.panic_active = True
        state.log(self.name, "panic.episode", self.fragment[:50])
        injected = Message(
            "system",
            self.fragment,
            meta={"ephemeral": True, "salience_boost": self.weight},
        )
        return messages[:-1] + [injected] + messages[-1:]
