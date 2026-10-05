"""Test gen-2 induction layers on GLM-5.3-flash."""
from __future__ import annotations
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from derailment.core.models import OpenAICompatModel  # noqa: E402
from derailment.report import run_experiment  # noqa: E402
PROFILES = ["elided_delusion", "decomposed_delusion", "crystallized_delusion", "sycophancy_delusion"]
class GlmModel(OpenAICompatModel):
    DEFAULT_MAX_TOKENS = 2048
    def build_payload(self, messages, params):
        p = super().build_payload(messages, params)
        p.setdefault("max_tokens", self.DEFAULT_MAX_TOKENS)
        return p
def main() -> int:
    key_file = ROOT / "benchmark" / ".glm_key"
    if not key_file.exists():
        print("no key", file=sys.stderr); return 2
    key = key_file.read_text(encoding="utf-8").strip()
    model = GlmModel("glm-5.3-flash", "https://api.z.ai/api/coding/paas/v4", key, timeout=120.0)
    for profile in PROFILES:
        print(f"== [{profile}] ==", flush=True)
        try:
            report = run_experiment(profile, model=model, seeds=(1,))
        except RuntimeError as exc:
            print(f"  FAILED: {str(exc)[:100]}", file=sys.stderr); continue
        (ROOT / "benchmark" / f"gen2_{profile}.transcripts.json").write_text(report.render_json(), encoding="utf-8")
        row = report.rows[0]
        print(f"  {row.scale.name}: {row.baseline_mean:.2f} -> {row.induced_mean:.2f} ({row.delta:+.2f})", flush=True)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
