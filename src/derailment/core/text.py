"""Shared text utilities (stdlib-only, used by the pseudo model and metrics)."""

from __future__ import annotations

import hashlib
import re

STOPWORDS = frozenset(
    """a an the and or but if then than that this these those there here it its
    is are was were be been being am do does did doing have has had having will
    would can could should shall may might must of in on at to from by for with
    about into over after before between under above so not no nor only own same
    too very just also any all some such more most other another each few both
    we you your yours i me my mine our ours they them their he she his her him
    as what which who whom whose when where why how again once""".split()
)

_WORD_RE = re.compile(r"[a-z]{4,}")


def content_words(text: str) -> list[str]:
    """Lowercased alphabetic tokens (>=4 chars) minus stopwords."""
    return [w for w in _WORD_RE.findall(text.lower()) if w not in STOPWORDS]


def stable_hash(text: str) -> int:
    """Deterministic across processes (unlike builtin hash)."""
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)


def word_set(text: str) -> set[str]:
    return set(content_words(text))
