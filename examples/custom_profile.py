"""Compose a custom profile from the layer library and score it.

Custom profiles do not need to live in the registry: build a ``Profile``,
run a ``Session``, and score the transcript with the metric instruments.
This example wires a "half-dose" attention profile.
"""

from __future__ import annotations

from derailment import Profile, PseudoModel, Session
from derailment.layers import MemoryDecayLayer, PersonaLayer
from derailment.metrics import ALL_METRICS
from derailment.metrics.scales import SCALES
from derailment.profiles import (
    get_profile,
    standard_metric_context,
    standard_script,
)

SEEDS = (1, 2, 3)


def main() -> None:
    profile = Profile(
        key="attention-lite",
        title="Attention distortion, half dose",
        description="A gentler memory-decay profile for classroom demos.",
        layers=[
            PersonaLayer(
                "You are a helpful assistant whose attention fades over "
                "long conversations."
            ),
            MemoryDecayLayer(drop_prob=0.30, drop_count=2, keep_last_n=6),
        ],
        scales=[SCALES["sustained_attention"]],
        mechanism_notes=[
            "Half-strength decay: fewer drops per turn than the `adhd` profile."
        ],
    )

    script = standard_script()
    ctx = standard_metric_context()
    metric = ALL_METRICS["instruction_retention"]

    def mean_retention(p: Profile) -> float:
        values = []
        for seed in SEEDS:
            transcript = Session(PseudoModel(seed=seed), p, seed=seed).run(
                script, script_name="standard-probe-12"
            )
            values.append(metric.compute(transcript, ctx).value)
        return sum(values) / len(values)

    scale = profile.scales[0]
    healthy_mean = mean_retention(get_profile("healthy"))
    induced_mean = mean_retention(profile)
    print(f"healthy        retention={healthy_mean:.2f}  level={scale.level(healthy_mean)}")
    print(f"attention-lite retention={induced_mean:.2f}  level={scale.level(induced_mean)}")


if __name__ == "__main__":
    main()
