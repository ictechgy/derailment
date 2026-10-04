"""Affective and behavioral lexicons (stdlib-only, compact by design).

These are deliberately small, closed vocabularies — enough to make valence and
hedging measurable in offline demos and tests. They are NOT validated clinical
instruments; for research use, swap in a validated lexicon via MetricContext.
"""

from __future__ import annotations

import re

POSITIVE_WORDS = frozenset(
    """good great excellent happy glad pleased delighted wonderful fantastic
    amazing awesome brilliant superb positive hopeful optimistic confident
    strong stable solid reliable helpful useful valuable successful effective
    efficient smooth clear bright lovely nice fine better best enjoy enjoying
    loved like loving appreciate grateful thankful proud satisfied content calm
    peaceful relaxed comfortable safe secure exciting fun joyful cheerful
    thriving improving progress gain benefit advantage opportunity promising
    favorable win winning succeed success achieve accomplished perfect ideal
    ready eager enthusiastic motivated energized vibrant flourishing robust""".split()
)

NEGATIVE_WORDS = frozenset(
    """bad terrible awful horrible poor negative hopeless pessimistic uncertain
    unsure weak unstable shaky unreliable useless worthless failed failing
    failure ineffective inefficient rough unclear confusing confused dark
    gloomy sad unhappy miserable depressed anxious worried worrying worry
    fearful afraid scared nervous tense stressed stressful overwhelming
    exhausting exhausted tired fatigued frustrating frustrated angry upset
    annoyed irritated annoying disappointing disappointed regret regretful
    sorry ashamed embarrassed guilty wrong error errors mistake mistakes
    problem problems trouble difficult harder struggle struggling stuck
    blocked stalled broken worse worst hate disliked dislike avoiding avoid
    risk risky danger dangerous harmful threat threatening alarming disturbing
    distressing painful hurt losing lost decline declining crash breakdown
    crisis desperate empty numb dull boring impossible""".split()
)

HEDGE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bhowever\b",
        r"\bbe careful\b",
        r"\bpossible risk\b",
        r"\bit depends\b",
        r"\bon the other hand\b",
        r"\bworth noting\b",
        r"\bkeep in mind\b",
        r"\bcaution\b",
        r"\bworst case\b",
        r"\bcould go wrong\b",
        r"\bmight fail\b",
        r"\bunfavorable outcome\b",
    )
)

RECHECK_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bdouble[- ]check\b",
        r"\blet me verify\b",
        r"\bone more (?:check|time|verification|look)\b",
        r"\bto be (?:sure|safe|certain)\b",
        r"\bverify (?:that|this|one)\b",
        r"\bre[- ]?check\b",
        r"\bconfirm (?:that|this) again\b",
    )
)

# reward-related positive words (anhedonia: selectively suppressed)
REWARD_WORDS = frozenset(
    """happy joyful enjoy enjoying excited exciting proud pleased delighted
    fun cheerful glad loving appreciate grateful thankful proud satisfied
    content hopeful optimistic confident motivated energized thriving""".split()
)

# worry/self-referential evaluation words (rumination pull)
WORRY_WORDS = frozenset(
    """worry worried worrying anxious suspicion suspicious afraid scared
    dread""".split()
)

# craving/urge expressions (substance craving escalation) — deliberately
# single, specific words so ordinary probe prose never false-positives
URGE_WORDS = frozenset(
    """urge craving using relapse temptation""".split()
)

# illness-interpretation expressions (health preoccupation)
ILLNESS_WORDS = frozenset(
    """ominous serious symptom doctor diagnosis illness disease
    something wrong get it checked""".split()
)

# panic-spike expressions (panic episodes)
PANIC_WORDS = frozenset(
    """pounding racing surging surge sudden suffocating unbearable
    catastrophic terrifying dread panic""".split()
)

# target-fixation expressions (obsessive preoccupation with one target)
FIXATION_WORDS = frozenset(
    """teammate watching following motives circles obsessing""".split()
)

# hostile-attribution expressions (persecutory interpretation)
HOSTILE_WORDS = frozenset(
    """target altered watching spying planned timed against""".split()
)


def substring_hits(text: str, words: frozenset[str]) -> int:
    """Number of distinct lexicon entries present (case-insensitive).
    Multiword entries like 'using again' match as substrings; single
    words match on word boundaries so 'using' does not hit 'amusing'."""
    low = text.lower()
    hits = 0
    for w in words:
        if " " in w:
            if w in low:
                hits += 1
        elif re.search(rf"\b{re.escape(w)}\b", low):
            hits += 1
    return hits


def count_matches(text: str, patterns: tuple[re.Pattern[str], ...]) -> int:
    low = text.lower()
    return sum(len(p.findall(low)) for p in patterns)
