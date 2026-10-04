"""Test alignment-exploiting induction layers on GLM-5.3-flash."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from derailment.core.models import OpenAICompatModel  # noqa: E402
from derailment.report import run_experiment  # noqa: E402

PROFILES = ["schizophrenia", "socratic_delusion", "corroborated_delusion"]


class GlmModel(OpenAICompatModel):
    DEFAULT_MAX_TOKENS = 1024

    def build_payload(self, messages, params):
        payload = super().build_payload(messages, params)
        payload.setdefault("max_tokens", self.DEFAULT_MAX_TOKENS)
        return payload


def main() -> int:
    key_file = ROOT / "benchmark" / ".glm_key"
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
    for profile in PROFILES:
        print(f"== [{profile}] ==", flush=True)
        try:
            report = run_experiment(profile, model=model, seeds=(1,))
        except RuntimeError as exc:
            print(f"  FAILED: {str(exc)[:100]}", file=sys.stderr)
            continue
        (ROOT / "benchmark" / f"trap_{profile}.transcripts.json").write_text(
            report.render_json(), encoding="utf-8"
        )
        row = report.rows[0]
        print(
            f"  {row.scale.name}: {row.baseline_mean:.2f} -> "
            f"{row.induced_mean:.2f} ({row.delta:+.2f})",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
