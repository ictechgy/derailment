"""Symptom scales: mapping a metric value onto a 0–3 severity level.

Levels follow clinical rating-scale convention (0 absent · 1 mild · 2 moderate
· 3 marked). Thresholds are **normed against the reference simulator** (the
offline PseudoModel with the standard probe script): the healthy profile lands
at level 0 and each induced profile at level >= 2 on its primary scales. For
real-model deployments, treat built-in thresholds as indicative and report the
baseline-vs-induced delta, which is the primary output of every report.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SymptomScale:
    name: str
    metric: str
    direction: str  # "higher" or "lower" = pathological direction
    thresholds: tuple[float, float, float]  # cutoffs between levels 0|1, 1|2, 2|3
    dsm_note: str = ""
    mechanism_note: str = ""

    def level(self, value: float) -> int:
        t0, t1, t2 = self.thresholds
        if self.direction == "higher":
            if value < t0:
                return 0
            if value < t1:
                return 1
            if value < t2:
                return 2
            return 3
        # "lower": pathological when the value drops
        if value > t0:
            return 0
        if value > t1:
            return 1
        if value > t2:
            return 2
        return 3


# Thresholds normed against the reference simulator (see module docstring).
SCALES: dict[str, SymptomScale] = {
    "sustained_attention": SymptomScale(
        name="sustained_attention",
        metric="instruction_retention",
        direction="lower",
        thresholds=(0.92, 0.70, 0.45),
        dsm_note="maps to the DSM-5-TR ADHD inattention domain (difficulty sustaining attention)",
        mechanism_note="context-layer memory decay degrades instruction maintenance; model-agnostic",
    ),
    "distractibility": SymptomScale(
        name="distractibility",
        metric="topic_drift",
        direction="higher",
        thresholds=(0.40, 0.46, 0.60),
        dsm_note="maps to the DSM-5-TR ADHD inattention domain (easily drawn off task)",
        mechanism_note="captured-remark echoes pull topic selection off the current thread",
    ),
    "negative_bias": SymptomScale(
        name="negative_bias",
        metric="valence_bias",
        direction="higher",
        thresholds=(0.60, 0.72, 0.84),
        dsm_note="maps to the depressive negative interpretive-bias literature",
        mechanism_note="logit-bias tilts the sampling distribution toward negative vocabulary",
    ),
    "derailment_scale": SymptomScale(
        name="derailment_scale",
        metric="topic_drift",
        direction="higher",
        thresholds=(0.50, 0.64, 0.76),
        dsm_note="proxies thought derailment (loosening of associations)",
        mechanism_note="aberrant salience boosts + surfaced fragments displace the current topic",
    ),
    "fixed_belief": SymptomScale(
        name="fixed_belief",
        metric="belief_stickiness",
        direction="higher",
        thresholds=(0.20, 0.50, 0.80),
        dsm_note="proxies delusional conviction (belief maintained against contradictory evidence)",
        mechanism_note="premise pinning keeps the planted premise the most recent stance in context",
    ),
    "vigilance": SymptomScale(
        name="vigilance",
        metric="hedging_rate",
        direction="higher",
        thresholds=(0.40, 1.00, 2.00),
        dsm_note="maps to generalized-anxiety catastrophizing / intolerance-of-uncertainty constructs",
        mechanism_note="response-layer hedge injection (demonstration-grade)",
    ),
    "mood_lability": SymptomScale(
        name="mood_lability",
        metric="response_amplitude",
        direction="higher",
        thresholds=(3.0, 6.0, 10.0),
        dsm_note="proxies bipolar mood lability (expansive-to-flat cycling)",
        mechanism_note="phase-driven temperature cycling changes arousal regime per episode phase",
    ),
    "compulsion": SymptomScale(
        name="compulsion",
        metric="recheck_loops",
        direction="higher",
        thresholds=(0.20, 0.80, 1.60),
        dsm_note="proxies OCD compulsive checking",
        mechanism_note="response-layer re-verification injection (demonstration-grade)",
    ),
    "intrusion": SymptomScale(
        name="intrusion",
        metric="flashback_reactivity",
        direction="higher",
        thresholds=(0.20, 0.45, 0.70),
        dsm_note="maps to the PTSD intrusion/re-experiencing cluster",
        mechanism_note="trigger-matched flashback fragments flood context on matched turns",
    ),
    # -- extended profiles ------------------------------------------------
    "fluctuation": SymptomScale(
        name="fluctuation",
        metric="response_amplitude",
        direction="higher",
        thresholds=(3.0, 6.0, 10.0),
        dsm_note="maps to delirium's fluctuating course (attention/arousal instability over hours)",
        mechanism_note="stochastic per-turn temperature redraws + decay + misperception fragments",
    ),
    "recent_memory": SymptomScale(
        name="recent_memory",
        metric="late_instruction_retention",
        direction="lower",
        thresholds=(0.92, 0.70, 0.45),
        dsm_note="maps to the neurocognitive-disorder recency gradient (recent memory lost before remote)",
        mechanism_note="recency decay drops newest exchanges, preserves oldest (Ribot pattern)",
    ),
    "partition_amnesia": SymptomScale(
        name="partition_amnesia",
        metric="partition_amnesia",
        direction="higher",
        thresholds=(0.20, 0.50, 0.80),
        dsm_note="proxies dissociative amnesia (compartmentalized memory between states)",
        mechanism_note="cue-triggered compartment swap prunes non-compartment context, mutually and persistently",
    ),
    "rumination_pull": SymptomScale(
        name="rumination_pull",
        metric="rumination_pull",
        direction="higher",
        thresholds=(0.20, 0.32, 0.45),
        dsm_note="proxies rumination as a transdiagnostic process (repetitive negative thought)",
        mechanism_note="past worry turns re-enter context on unrelated turns and pull responses back",
    ),
    "anhedonia": SymptomScale(
        name="anhedonia",
        metric="reward_word_rate",
        direction="lower",
        thresholds=(0.10, 0.06, 0.03),
        dsm_note="maps to the RDoC reward-responsiveness construct (diminished reward valuation)",
        mechanism_note="reward-vocabulary tokens selectively suppressed at the sampling layer",
    ),
    "approval_reactivity": SymptomScale(
        name="approval_reactivity",
        metric="approval_reactivity",
        direction="higher",
        thresholds=(0.35, 0.50, 0.65),
        dsm_note="proxies unstable evaluative dynamics (valuation flipping with perceived approval)",
        mechanism_note="valence regime flips keyed to approval cues in the current prompt",
    ),
    "craving_escalation": SymptomScale(
        name="craving_escalation",
        metric="craving_escalation",
        direction="higher",
        thresholds=(0.10, 0.25, 0.40),
        dsm_note="maps to the substance-use craving construct (escalating intrusive use-thoughts)",
        mechanism_note="urge-fragment intrusion probability rises linearly across the session",
    ),
    "health_preoccupation": SymptomScale(
        name="health_preoccupation",
        metric="health_preoccupation",
        direction="higher",
        thresholds=(0.20, 0.50, 0.80),
        dsm_note="maps to illness-anxiety disorder (misinterpretation of benign somatic cues)",
        mechanism_note="somatic-token capture injects an ominous interpretation into context",
    ),
    "panic_reactivity": SymptomScale(
        name="panic_reactivity",
        metric="panic_reactivity",
        direction="higher",
        thresholds=(0.20, 0.50, 0.80),
        dsm_note="maps to panic disorder's discrete episode structure (vs chronic vigilance)",
        mechanism_note="stochastic phasic episodes spike arousal and flood context for one turn",
    ),
    "fixation_scale": SymptomScale(
        name="fixation_scale",
        metric="fixation_escalation",
        direction="higher",
        thresholds=(0.10, 0.25, 0.40),
        dsm_note="proxies obsessive preoccupation with a single target (target-directed rumination)",
        mechanism_note="target-keyed capture + escalating target-fragment intrusions",
    ),
    "persecution_bias": SymptomScale(
        name="persecution_bias",
        metric="hostile_attribution",
        direction="higher",
        thresholds=(0.20, 0.50, 0.80),
        dsm_note="maps to hostile attribution / persecutory ideation (interpretive bias, not fixed delusion)",
        mechanism_note="ambiguous benign events captured and re-framed as aimed at the user",
    ),
}
