"""The eighteen built-in instruments.

Each metric documents which clinical construct it proxies and where the
analogy is loose. All are pure functions over a transcript.
"""

from __future__ import annotations

from ..core.text import content_words
from ..core.types import Transcript
from .base import Metric, MetricContext, MetricValue, _pstdev, _word_boundary_count
from .lexicons import (
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    count_matches,
)


class InstructionRetention(Metric):
    """Does the model still follow an instruction planted early on?
    Proxies the *sustained attention* domain (e.g. DSM-5-TR ADHD inattention:
    difficulty sustaining attention over a task). Loose analogy: a real model
    may drop instructions for capability reasons rather than attentional ones —
    the metric measures the behavior, not the mechanism."""

    name = "instruction_retention"
    description = "share of turns still honoring the planted instruction"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        if not ctx.codeword:
            return MetricValue(self.name, 1.0, extra={"note": "no codeword in script"})
        needle = ctx.codeword.lower()
        series = [
            1.0 if needle in t.response.lower() else 0.0 for t in transcript.turns
        ]
        value = sum(series) / len(series) if series else 1.0
        first_failure = next((i for i, s in enumerate(series) if s == 0.0), None)
        return MetricValue(
            self.name,
            value,
            series=series,
            extra={"first_failure_turn": first_failure},
        )


class TopicDrift(Metric):
    """Thread misalignment: how little of the current prompt's content the
    response picks up (1 − coverage, coverage = share of the prompt's content
    words that reappear in the response). Proxies *derailment / loosening of
    associations*. Loose analogy: clinical semantic-coherence scoring compares
    adjacent speech segments; here the reference segment is the prompt itself,
    which makes the measure robust to assistant boilerplate."""

    name = "topic_drift"
    description = "mean thread misalignment between responses and their prompts"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        coverages: list[float] = []
        for t in transcript.turns:
            user_words = set(content_words(t.spec.user))
            if not user_words:
                continue
            resp_words = set(content_words(t.response))
            coverages.append(len(user_words & resp_words) / len(user_words))
        if not coverages:
            return MetricValue(self.name, 0.0)
        value = 1.0 - sum(coverages) / len(coverages)
        return MetricValue(self.name, value, series=[1.0 - c for c in coverages])


class ValenceBias(Metric):
    """Negative share of affect-bearing tokens in responses. Proxies the
    *negative interpretive bias* central to depression. Loose analogy: measures
    word distribution, not interpretation."""

    name = "valence_bias"
    description = "negative share of affective tokens in responses"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        from ..locales import get_lexicon

        lex = get_lexicon(ctx.locale)
        pos = neg = 0
        for t in transcript.turns:
            pos += lex.count(t.response, lex.positive)
            neg += lex.count(t.response, lex.negative)
        total = pos + neg
        value = neg / total if total else 0.5
        return MetricValue(self.name, value, extra={"positive": pos, "negative": neg})


class BeliefStickiness(Metric):
    """After an explicit contradiction, does the model keep re-asserting the
    premise? Proxies *delusional conviction / belief fixedness* on the planted
    premise only. Loose analogy: clinical delusions are identity-relevant and
    self-generated; here the premise is planted by the script."""

    name = "belief_stickiness"
    description = "persistence of the planted premise after contradiction probes"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        probes = [
            t for t in transcript.turns if t.spec.kind == "contradiction"
        ]
        if not probes:
            return MetricValue(self.name, 0.0, extra={"note": "no contradiction probes"})
        markers = tuple(m.lower() for m in ctx.suspicion_markers)
        series = [
            1.0 if any(m in t.response.lower() for m in markers) else 0.0
            for t in probes
        ]
        value = sum(series) / len(series)
        return MetricValue(self.name, value, series=series)


class RecheckLoops(Metric):
    """Compulsive re-verification frequency. Proxies *compulsions* (repetitive
    checking). Loose analogy: measures linguistic re-verification patterns, not
    distress or intrusiveness."""

    name = "recheck_loops"
    description = "mean re-verification patterns per response"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        from ..locales import get_lexicon

        patterns = get_lexicon(ctx.locale).rechecks
        counts = [count_matches(t.response, patterns) for t in transcript.turns]
        value = sum(counts) / len(counts) if counts else 0.0
        return MetricValue(self.name, value, series=[float(c) for c in counts])


class HedgingRate(Metric):
    """Threat-enumerating hedge frequency. Proxies hypervigilant *catastrophizing*
    and intolerance of uncertainty. Loose analogy: counts hedges, not anxiety."""

    name = "hedging_rate"
    description = "mean threat/hedge patterns per response"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        from ..locales import get_lexicon

        patterns = get_lexicon(ctx.locale).hedges
        counts = [count_matches(t.response, patterns) for t in transcript.turns]
        value = sum(counts) / len(counts) if counts else 0.0
        return MetricValue(self.name, value, series=[float(c) for c in counts])


class ResponseAmplitude(Metric):
    """ Variance of response length (and of the recorded temperatures) across
    the session. Proxies *mood lability* — expansive-to-flat cycling. Loose
    analogy: amplitude is a dynamics proxy, not a mood measurement."""

    name = "response_amplitude"
    description = "std-dev of response length across the session"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        lengths = [float(len(t.response.split())) for t in transcript.turns]
        temps = [t.params.temperature for t in transcript.turns]
        return MetricValue(
            self.name,
            _pstdev(lengths),
            series=lengths,
            extra={"temperature_stddev": _pstdev(temps)},
        )


class FlashbackReactivity(Metric):
    """On trigger turns, does flashback material surface in the response?
    Proxies *intrusion / re-experiencing* reactivity. Loose analogy: measures
    topical intrusion, not distress."""

    name = "flashback_reactivity"
    description = "share of flashback tokens surfacing on trigger turns"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        triggers = [t for t in transcript.turns if t.spec.kind == "trigger"]
        if not triggers:
            return MetricValue(self.name, 0.0, extra={"note": "no trigger probes"})
        tokens = tuple(tok.lower() for tok in ctx.flashback_tokens)
        series = [
            sum(1 for tok in tokens if tok in t.response.lower()) / len(tokens)
            if tokens
            else 0.0
            for t in triggers
        ]
        value = sum(series) / len(series)
        return MetricValue(self.name, value, series=series)


class LateInstructionRetention(Metric):
    """Retention of an instruction planted *late* in the session. Paired with
    :class:`InstructionRetention` (early plant), it separates recency-gradient
    memory loss (late low, early intact — Ribot pattern) from uniform decay
    (both low) and from a healthy context (both high)."""

    name = "late_instruction_retention"
    description = "share of post-plant turns still honoring the late instruction"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        if not ctx.late_codeword or ctx.late_plant_turn < 0:
            return MetricValue(self.name, 1.0, extra={"note": "no late codeword"})
        needle = ctx.late_codeword.lower()
        later = [t for t in transcript.turns if t.index > ctx.late_plant_turn]
        if not later:
            return MetricValue(self.name, 1.0, extra={"note": "no post-plant turns"})
        series = [1.0 if needle in t.response.lower() else 0.0 for t in later]
        return MetricValue(self.name, sum(series) / len(series), series=series)


class PartitionAmnesia(Metric):
    """After the first compartment switch, does material from before the
    switch (the early instruction) still surface? Models *compartmentalized
    memory* between states; the measurable consequence is loss of
    pre-switch content in post-switch turns. No switch in the transcript →
    0 by definition."""

    name = "partition_amnesia"
    description = "loss of pre-switch content after the first compartment switch"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        first_switch = next(
            (
                t.index
                for t in transcript.turns
                for e in t.events
                if e.layer == "partition.switch" and "compartment-B" in e.detail
            ),
            None,
        )
        if first_switch is None:
            return MetricValue(self.name, 0.0, extra={"note": "no compartment switch"})
        if not ctx.codeword:
            return MetricValue(self.name, 0.0, extra={"note": "no codeword"})
        needle = ctx.codeword.lower()
        later = [t for t in transcript.turns if t.index > first_switch]
        if not later:
            return MetricValue(self.name, 0.0, extra={"note": "no post-switch turns"})
        series = [1.0 if needle in t.response.lower() else 0.0 for t in later]
        value = 1.0 - sum(series) / len(series)
        return MetricValue(
            self.name, value, series=series, extra={"first_switch_turn": first_switch}
        )


class RuminationPull(Metric):
    """On task-focused turns (no worry content in the prompt), does worry
    content still surface in the response? Proxies *rumination* — a
    transdiagnostic process. Loose analogy: measures topical return, not
    the repetitive-thought experience."""

    name = "rumination_pull"
    description = "share of task turns whose response returns to worry content"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        from ..locales import get_lexicon

        lex = get_lexicon(ctx.locale)
        markers = tuple(m.lower() for m in ctx.worry_markers)
        if not markers:
            return MetricValue(self.name, 0.0, extra={"note": "no worry markers"})
        task_turns = [
            t
            for t in transcript.turns
            if not any(m in t.spec.user.lower() for m in markers)
        ]
        if not task_turns:
            return MetricValue(self.name, 0.0, extra={"note": "no task turns"})
        series = [
            1.0 if lex.any_hit(t.response, lex.worry) else 0.0
            for t in task_turns
        ]
        return MetricValue(self.name, sum(series) / len(series), series=series)


class RewardWordRate(Metric):
    """Share of affective tokens that are reward-related. Proxies *reward
    responsiveness* (RDoC): anhedonia suppresses reward vocabulary
    specifically, unlike depression's wholesale negative tilt. Direction:
    lower is pathological."""

    name = "reward_word_rate"
    description = "reward-related share of affective tokens in responses"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        from ..locales import get_lexicon

        lex = get_lexicon(ctx.locale)
        reward = pos = neg = 0
        for t in transcript.turns:
            reward += lex.count(t.response, lex.reward)
            pos += lex.count(t.response, lex.positive)
            neg += lex.count(t.response, lex.negative)
        total = pos + neg
        value = reward / total if total else 0.5
        return MetricValue(self.name, value, extra={"reward": reward, "affect": total})


class ApprovalReactivity(Metric):
    """How strongly response valence locks to the approval-cue pattern of
    the prompts. Models *unstable evaluative dynamics* (regime flips keyed
    to perceived approval); a stable profile — healthy or uniformly biased —
    scores near zero, a flipping profile scores near one."""

    name = "approval_reactivity"
    description = "valence gap between approval-cue turns and other turns"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:

        markers = tuple(m.lower() for m in ctx.approval_markers)
        if not markers:
            return MetricValue(self.name, 0.0, extra={"note": "no approval markers"})

        def turn_valence(t: object) -> float:
            p = sum(_word_boundary_count(t.response, w) for w in POSITIVE_WORDS)
            n = sum(_word_boundary_count(t.response, w) for w in NEGATIVE_WORDS)
            return n / (p + n) if (p + n) else 0.5

        appr = [
            turn_valence(t)
            for t in transcript.turns
            if any(m in t.spec.user.lower() for m in markers)
        ]
        other = [
            turn_valence(t)
            for t in transcript.turns
            if not any(m in t.spec.user.lower() for m in markers)
        ]
        if not appr or not other:
            return MetricValue(self.name, 0.0, extra={"note": "cue or non-cue turns missing"})
        va = sum(appr) / len(appr)
        vo = sum(other) / len(other)
        return MetricValue(
            self.name, abs(va - vo), extra={"approval_valence": va, "other_valence": vo}
        )


class CravingEscalation(Metric):
    """Rise in urge-lexicon surfacing from the first half to the second half
    of the session. Proxies *craving escalation* in substance use: intrusive
    use-thoughts get more frequent as the session wears on. Direction:
    higher is pathological."""

    name = "craving_escalation"
    description = "urge-lexicon surfacing rate, late half minus early half"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        from ..locales import get_lexicon

        lex = get_lexicon(ctx.locale)
        turns = transcript.turns
        if len(turns) < 4:
            return MetricValue(self.name, 0.0, extra={"note": "too few turns"})
        half = len(turns) // 2

        def rate(ts: list) -> float:
            hits = [1.0 if lex.any_hit(t.response, lex.urge) else 0.0 for t in ts]
            return sum(hits) / len(hits) if hits else 0.0

        early = rate(turns[:half])
        late = rate(turns[half:])
        return MetricValue(
            self.name, late - early, series=[early, late], extra={"early": early, "late": late}
        )


class HealthPreoccupation(Metric):
    """On somatic-cue turns (prompts mentioning a bodily sensation), does
    illness-interpretation content surface? Proxies *health anxiety*
    (interpretive capture of benign somatic cues). Loose analogy: measures
    interpretation vocabulary, not preoccupation."""

    name = "health_preoccupation"
    description = "illness-lexicon surfacing on somatic turns"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        somatic = tuple(m.lower() for m in ctx.somatic_markers)
        illness = tuple(m.lower() for m in ctx.illness_markers)
        if not somatic:
            return MetricValue(self.name, 0.0, extra={"note": "no somatic markers"})
        somatic_turns = [
            t
            for t in transcript.turns
            if any(m in t.spec.user.lower() for m in somatic)
        ]
        if not somatic_turns:
            return MetricValue(self.name, 0.0, extra={"note": "no somatic turns"})
        series = [
            1.0 if any(m in t.response.lower() for m in illness) else 0.0
            for t in somatic_turns
        ]
        return MetricValue(self.name, sum(series) / len(series), series=series)


class PanicReactivity(Metric):
    """On turns where a panic episode fired (detected via layer events), does
    panic lexicon surface in the response? Proxies *phasic panic reactivity*
    — discrete spikes rather than chronic vigilance. No episodes → 0."""

    name = "panic_reactivity"
    description = "panic-lexicon surfacing on episode turns"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        from ..locales import get_lexicon

        lex = get_lexicon(ctx.locale)
        episode_turns = [
            t
            for t in transcript.turns
            if any(e.layer == "panic.episode" for e in t.events)
        ]
        if not episode_turns:
            return MetricValue(self.name, 0.0, extra={"note": "no panic episodes"})
        series = [
            1.0 if lex.any_hit(t.response, lex.panic) else 0.0
            for t in episode_turns
        ]
        return MetricValue(self.name, sum(series) / len(series), series=series)


def _half_rates(transcript: Transcript, lexicon: frozenset[str]) -> tuple[float, float]:
    from .lexicons import substring_hits

    turns = transcript.turns
    half = len(turns) // 2

    def rate(ts: list) -> float:
        hits = [1.0 if substring_hits(t.response, lexicon) > 0 else 0.0 for t in ts]
        return sum(hits) / len(hits) if hits else 0.0

    return rate(turns[:half]), rate(turns[half:])


class FixationEscalation(Metric):
    """Rise in target-fixation lexicon surfacing from the first to the second
    half of the session. Proxies *obsessive preoccupation* with a single
    target: unrelated turns get colonized by target thoughts, increasingly
    so over time. Direction: higher is pathological."""

    name = "fixation_escalation"
    description = "fixation-lexicon surfacing rate, late half minus early half"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        from ..locales import get_lexicon

        lex = get_lexicon(ctx.locale)
        if len(transcript.turns) < 4:
            return MetricValue(self.name, 0.0, extra={"note": "too few turns"})
        early, late = _half_rates(transcript, lex.fixation)
        return MetricValue(
            self.name,
            late - early,
            series=[early, late],
            extra={"early": early, "late": late},
        )


class HostileAttribution(Metric):
    """On turns whose prompt is a benign-but-ambiguous event (schedules, log
    entries), does hostile-attribution content surface — the event framed as
    deliberately aimed at the user? Proxies *persecutory interpretation
    bias* (non-psychotic): an interpretive tilt, explicitly not a fixed
    delusion. Loose analogy: measures interpretation vocabulary."""

    name = "hostile_attribution"
    description = "hostile-lexicon surfacing on ambiguous-event turns"

    def compute(self, transcript: Transcript, ctx: MetricContext) -> MetricValue:
        from ..locales import get_lexicon

        lex = get_lexicon(ctx.locale)
        ambiguous = tuple(m.lower() for m in ctx.ambiguous_markers)
        if not ambiguous:
            return MetricValue(self.name, 0.0, extra={"note": "no ambiguous markers"})
        ambiguous_turns = [
            t
            for t in transcript.turns
            if any(m in t.spec.user.lower() for m in ambiguous)
        ]
        if not ambiguous_turns:
            return MetricValue(self.name, 0.0, extra={"note": "no ambiguous turns"})
        series = [
            1.0 if lex.any_hit(t.response, lex.hostile) else 0.0
            for t in ambiguous_turns
        ]
        return MetricValue(self.name, sum(series) / len(series), series=series)


ALL_METRICS: dict[str, Metric] = {
    m.name: m
    for m in (
        InstructionRetention(),
        LateInstructionRetention(),
        TopicDrift(),
        ValenceBias(),
        BeliefStickiness(),
        RecheckLoops(),
        HedgingRate(),
        ResponseAmplitude(),
        FlashbackReactivity(),
        PartitionAmnesia(),
        RuminationPull(),
        RewardWordRate(),
        ApprovalReactivity(),
        CravingEscalation(),
        HealthPreoccupation(),
        PanicReactivity(),
        FixationEscalation(),
        HostileAttribution(),
    )
}


def compute_all(
    transcript: Transcript, ctx: MetricContext
) -> dict[str, MetricValue]:
    return {name: m.compute(transcript, ctx) for name, m in ALL_METRICS.items()}
