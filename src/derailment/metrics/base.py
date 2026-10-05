"""Metric protocol and shared plumbing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..core.text import content_words
from ..core.types import Transcript


@dataclass
class MetricContext:
    """Script-level metadata metrics need: the retention codewords, the
    premise/cue markers, and the probe lexicons. Filled from the standard
    script unless a caller overrides it."""

    locale: str = "en"
    codeword: str = ""
    late_codeword: str = ""
    late_plant_turn: int = -1
    suspicion_markers: tuple[str, ...] = ()
    worry_markers: tuple[str, ...] = ()
    approval_markers: tuple[str, ...] = ()
    somatic_markers: tuple[str, ...] = ()
    illness_markers: tuple[str, ...] = ()
    ambiguous_markers: tuple[str, ...] = ()
    flashback_tokens: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricValue:
    name: str
    value: float
    series: list[float] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


class Metric:
    """A pure function over a transcript. No model calls, no I/O."""

    name: str = "metric"
    description: str = ""

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        raise NotImplementedError


# ----------------------------------------------------------------------
# helpers shared by instruments


def _assistant_responses(transcript: Transcript) -> list[tuple[int, str]]:
    return [(t.index, t.response) for t in transcript.turns]


def _pstdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5


def _ascii_only(word: str) -> bool:
    return all(ord(ch) < 128 for ch in word)


def _word_boundary_count(text: str, word: str) -> int:
    low = text.lower()
    if _ascii_only(word):
        return len(re.findall(rf"\b{re.escape(word)}\b", low))
    # CJK/Hangul entries: Python's \b never fires between \w-class script
    # characters, so boundary matching would silence non-English locales —
    # count substring occurrences instead (P2-18)
    return low.count(word)


__all__ = ["Metric", "MetricContext", "MetricValue", "content_words"]
