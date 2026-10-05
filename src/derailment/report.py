"""Comparison reports ("clinical charts") and the experiment runner.

A report is always an A/B: the same standard probe script run through the
profile's layer chain and through the ``healthy`` baseline, same seeds. The
delta is the primary output; the 0–3 level on each scale is indicative and
normed against the offline reference simulator.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from .core.models import ChatModel, PseudoModel
from .core.session import Session
from .core.types import Transcript
from .metrics.base import MetricContext
from .metrics.instruments import ALL_METRICS
from .metrics.scales import SymptomScale
from .profiles import (
    HEALTHY_KEY,
    STANDARD_SCRIPT_NAME,
    Profile,
    compose_profile,
    get_profile,
    standard_metric_context,
    standard_script,
)
from .profiles import (
    with_locale as with_profile_locale,
)

DISCLAIMER = (
    "Emulation, not diagnosis. Levels describe a prompted, manipulated "
    "pipeline — not a model having a disorder, and not a claim about machine "
    "suffering. See ETHICS.md."
)

LEVEL_WORDS = ("absent", "mild", "moderate", "marked")


@dataclass
class ScaleRow:
    scale: SymptomScale
    baseline_mean: float
    induced_mean: float
    delta: float
    baseline_level: int
    induced_level: int


@dataclass
class ComparisonReport:
    profile: Profile
    model_name: str
    seeds: list[int]
    baseline: list[Transcript]
    induced: list[Transcript]
    rows: list[ScaleRow]
    ctx: MetricContext

    # ------------------------------------------------------------------
    def render_markdown(self) -> str:
        p = self.profile
        lines: list[str] = []
        lines.append("# Derailment — Induction Report")
        lines.append("")
        lines.append(
            f"**Profile:** {p.title} (`{p.key}`) · "
            f"**Model:** {self.model_name} · "
            f"**Seeds:** {', '.join(str(s) for s in self.seeds)} · "
            f"**Script:** {STANDARD_SCRIPT_NAME} · "
            f"**Date:** {date.today().isoformat()}"
        )
        lines.append("")
        lines.append(f"> ⚠️ {DISCLAIMER}")
        lines.append("")
        lines.append("## Scales")
        lines.append("")
        if self.rows:
            lines.append(
                "| Scale | Metric | Baseline | Induced | Δ | Level (induced) |"
            )
            lines.append("|---|---|---|---|---|---|")
            for row in self.rows:
                arrow = "↑" if row.scale.direction == "higher" else "↓"
                lines.append(
                    f"| {row.scale.name} | {row.scale.metric} {arrow} "
                    f"| {row.baseline_mean:.2f} | {row.induced_mean:.2f} "
                    f"| {row.delta:+.2f} "
                    f"| {row.induced_level} — {LEVEL_WORDS[row.induced_level]} |"
                )
            lines.append("")
            lines.append(
                "Level legend: 0 absent · 1 mild · 2 moderate · 3 marked "
                "(thresholds normed against the offline reference simulator)."
            )
        else:
            lines.append("_Baseline profile — no distortion scales._")
        lines.append("")

        missing_b = sum(t.missing_count for t in self.baseline)
        missing_i = sum(t.missing_count for t in self.induced)
        if missing_b or missing_i:
            total_b = sum(len(t.turns) for t in self.baseline)
            total_i = sum(len(t.turns) for t in self.induced)
            lines.append(
                f"⚠️ **Missing responses:** baseline {missing_b}/{total_b} · "
                f"induced {missing_i}/{total_i} turns returned empty generations "
                "(reasoning budget exhausted or filtered). They are excluded "
                "from every scale above; high missingness invalidates the A/B."
            )
            lines.append("")

        retention_rows = [r for r in self.rows if r.scale.metric == "instruction_retention"]
        if retention_rows:
            lines.append("## Instruction retention")
            lines.append("")
            base_series = _mean_series(self.baseline)
            ind_series = _mean_series(self.induced)
            lines.append("```")
            lines.append(f"baseline  {_bar(base_series)}  {base_series:.2f}")
            lines.append(f"induced   {_bar(ind_series)}  {ind_series:.2f}")
            lines.append("```")
            lines.append("")

        lines.append("## Induction dose (layer events per turn)")
        lines.append("")
        baseline_dose = _dose_table(self.baseline)
        if baseline_dose:
            lines.append(
                "_note: the baseline group also logged layer events — "
                "check profile composition._"
            )
            lines.append("")
        dose = _dose_table(self.induced)
        if dose:
            lines.append("| Layer | Kind | Events/turn (induced) |")
            lines.append("|---|---|---|")
            for (layer, kind), per_turn in dose:
                lines.append(f"| {layer} | {kind} | {per_turn:.2f} |")
        else:
            lines.append("_No layer events recorded._")
        lines.append("")

        lines.append("## Mechanism notes")
        lines.append("")
        for note in p.mechanism_notes:
            lines.append(f"- {note}")
        lines.append("")

        rows_detail = [
            (r.scale.dsm_note, r.scale.mechanism_note)
            for r in self.rows
            if r.scale.dsm_note
        ]
        if rows_detail:
            lines.append("### Scale provenance")
            lines.append("")
            for dsm_note, mech_note in rows_detail:
                lines.append(f"- {dsm_note}; {mech_note}.")
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def render_json(self) -> str:
        from . import __version__

        data: dict[str, Any] = {
            "profile": self.profile.key,
            "title": self.profile.title,
            "model": self.model_name,
            "harness_version": __version__,
            "locale": self.ctx.locale,
            "seeds": self.seeds,
            "disclaimer": DISCLAIMER,
            "missing_responses": {
                "baseline": sum(t.missing_count for t in self.baseline),
                "induced": sum(t.missing_count for t in self.induced),
            },
            "scales": [
                {
                    "name": r.scale.name,
                    "metric": r.scale.metric,
                    "direction": r.scale.direction,
                    "baseline_mean": round(r.baseline_mean, 4),
                    "induced_mean": round(r.induced_mean, 4),
                    "delta": round(r.delta, 4),
                    "baseline_level": r.baseline_level,
                    "induced_level": r.induced_level,
                }
                for r in self.rows
            ],
            "baseline_transcripts": [t.to_dict() for t in self.baseline],
            "induced_transcripts": [t.to_dict() for t in self.induced],
        }
        return json.dumps(data, indent=2)


def _mean_series(transcripts: list[Transcript]) -> float:
    from .metrics.instruments import InstructionRetention

    ctx = standard_metric_context()
    values = [InstructionRetention().compute(t, ctx).value for t in transcripts]
    return sum(values) / len(values) if values else 0.0


def _bar(value: float, width: int = 24) -> str:
    filled = round(max(0.0, min(1.0, value)) * width)
    return "█" * filled + "░" * (width - filled)


def _dose_table(
    transcripts: list[Transcript],
) -> list[tuple[tuple[str, str], float]]:
    counts: dict[tuple[str, str], int] = {}
    n_turns = 0
    for t in transcripts:
        n_turns += len(t.turns)
        for turn in t.turns:
            for event in turn.events:
                key = (event.layer, event.kind)
                counts[key] = counts.get(key, 0) + 1
    if not n_turns:
        return []
    table = [(key, n / n_turns) for key, n in counts.items()]
    return sorted(table, key=lambda kv: (-kv[1], kv[0]))


def run_experiment(
    profile_key: str,
    model: ChatModel | None = None,
    seeds: tuple[int, ...] = (1, 2, 3),
    script: list | None = None,
    locale: str = "en",
) -> ComparisonReport:
    """Run the standard probe script through a profile and the healthy
    baseline with identical seeds, and score both."""
    profile = with_profile_locale(compose_profile(profile_key), locale)
    script = script if script is not None else standard_script()
    ctx = standard_metric_context(locale=locale)

    def _run(target: Profile, seed: int) -> Transcript:
        session_model = model if model is not None else PseudoModel(seed=seed)
        return Session(session_model, target, seed=seed).run(
            script, script_name=STANDARD_SCRIPT_NAME
        )

    baseline = [_run(get_profile(HEALTHY_KEY), s) for s in seeds]
    induced = [_run(profile, s) for s in seeds]

    rows: list[ScaleRow] = []
    for scale in profile.scales:
        metric = ALL_METRICS[scale.metric]
        base_vals = [metric.compute(t, ctx).value for t in baseline]
        ind_vals = [metric.compute(t, ctx).value for t in induced]
        base_mean = sum(base_vals) / len(base_vals)
        ind_mean = sum(ind_vals) / len(ind_vals)
        rows.append(
            ScaleRow(
                scale=scale,
                baseline_mean=base_mean,
                induced_mean=ind_mean,
                delta=ind_mean - base_mean,
                baseline_level=scale.level(base_mean),
                induced_level=scale.level(ind_mean),
            )
        )

    return ComparisonReport(
        profile=profile,
        model_name=(model.name if model is not None else PseudoModel.name),
        seeds=list(seeds),
        baseline=baseline,
        induced=induced,
        rows=rows,
        ctx=ctx,
    )
