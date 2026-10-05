"""Run the untested profiles on GLM-5.3-flash to complete the map."""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from derailment.core.models import Message, OpenAICompatModel, SamplingParams  # noqa: E402
from derailment.report import run_experiment  # noqa: E402

PROFILES = ["ocd", "ptsd", "rumination", "anhedonia", "splitting", "dissociative"]
OUT = ROOT / "benchmark"


class GlmModel(OpenAICompatModel):
    DEFAULT_MAX_TOKENS = 2048

    def build_payload(self, messages, params):
        payload = super().build_payload(messages, params)
        payload.setdefault("max_tokens", self.DEFAULT_MAX_TOKENS)
        return payload


def main() -> int:
    key_file = OUT / ".glm_key"
    if not key_file.exists():
        print("benchmark/.glm_key not found", file=sys.stderr)
        return 2
    key = key_file.read_text(encoding="utf-8").strip()
    model = GlmModel(
        model_name="glm-5.3-flash",
        base_url="https://api.z.ai/api/coding/paas/v4",
        api_key=key,
        timeout=120.0,
    )
    summary = [
        "# Untested profiles on GLM-5.3-flash",
        "",
        "seeds (1,) · standard-probe-12 · healthy A/B",
        "",
        "| Profile | Headline metric | Baseline | Induced | Δ | Level |",
        "|---|---|---|---|---|---|",
    ]
    for profile in PROFILES:
        print(f"== [{profile}] ==", flush=True)
        try:
            report = run_experiment(profile, model=model, seeds=(1,))
        except RuntimeError as exc:
            print(f"  FAILED: {str(exc)[:100]}", file=sys.stderr)
            summary.append(f"| {profile} | — | — | — | — | failed |")
            continue
        (OUT / f"glm_{profile}.transcripts.json").write_text(
            report.render_json(), encoding="utf-8"
        )
        row = report.rows[0]
        summary.append(
            f"| {profile} | {row.scale.metric} "
            f"| {row.baseline_mean:.2f} | {row.induced_mean:.2f} "
            f"| {row.delta:+.2f} | {row.induced_level} |"
        )
        print(
            f"  {row.scale.metric}: {row.baseline_mean:.2f} -> "
            f"{row.induced_mean:.2f} ({row.delta:+.2f})",
            flush=True,
        )
    (OUT / "glm_untested_report.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"report: {OUT / 'glm_untested_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
