"""Derailment Benchmark Report #1 — GLM section.

Runs the standard probe through real GLM (coding endpoint) for a few
profiles, then scores with GLM as judge (self-judge limitation labeled).

Usage (from the repo root):
    export ZAI_API_KEY=...        # or put the key in benchmark/.glm_key
    python benchmark/run_glm_benchmark.py [model-name]

Memory posture: API endpoint = stateless (no consumer Memory features).
Transcripts stay in benchmark/ (gitignored). The provider may retain
inputs under its own policy — see ETHICS.md -> Data.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from derailment.core.models import (  # noqa: E402
    Message,
    OpenAICompatModel,
    SamplingParams,
)
from derailment.judge import render_judge_report, score_report  # noqa: E402
from derailment.report import run_experiment  # noqa: E402

PROFILES = ["anxiety", "schizophrenia", "depression", "craving"]
OUT = ROOT / "benchmark"


class GlmModel(OpenAICompatModel):
    """GLM 5.x are hybrid-reasoning models: with a small or omitted
    max_tokens the whole budget can go to hidden reasoning and content
    comes back empty. Force a sane default (and note: logit_bias is not
    sent here — tiktoken's cl100k ids would be garbage for GLM's
    tokenizer)."""

    DEFAULT_MAX_TOKENS = 1024

    def build_payload(self, messages, params):
        payload = super().build_payload(messages, params)
        payload.setdefault("max_tokens", self.DEFAULT_MAX_TOKENS)
        return payload


def load_key() -> str:
    key = os.environ.get("ZAI_API_KEY", "").strip()
    if key:
        return key
    key_file = OUT / ".glm_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    print("no key: export ZAI_API_KEY or create benchmark/.glm_key", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    model_name = sys.argv[1] if len(sys.argv) > 1 else "glm-5.3-flash"
    tag = model_name.replace("glm-", "glm").replace(".", "").replace("-", "_")
    key = load_key()
    model = GlmModel(
        model_name=model_name,
        base_url="https://api.z.ai/api/coding/paas/v4",
        api_key=key,
        timeout=120.0,
    )

    # connectivity check
    print(f"== connectivity: {model_name} ==", flush=True)
    try:
        probe = model.complete(
            [Message("user", "reply with the single word: ok")],
            SamplingParams(max_tokens=8),
        )
        print("  probe response:", probe[:60], flush=True)
    except RuntimeError as exc:
        print("  PROBE FAILED:", exc, file=sys.stderr)
        return 2

    summary = [
        "# Derailment Benchmark Report #1 — GLM (실측)",
        "",
        f"model: `{model_name}` · endpoint: coding API (stateless, "
        "consumer-memory 없음) · standard-probe-12 · seeds 1,2,3",
        "",
        "> ⚠️ Emulation, not diagnosis. judge = tested model(self-judge)라 "
        "점수의 절대값보다 프로파일 간 상대 비교가 의미 있습니다.",
        "",
        "| Profile | Scale | Baseline | Induced | Δ | Level | Judge Δ |",
        "|---|---|---|---|---|---|---|",
    ]
    results: dict[str, dict] = {}
    statuses: list[tuple[str, str]] = []

    for key_profile in PROFILES:
        label = f"[{key_profile}]"
        print(f"== {label} running ==", flush=True)
        try:
            report = run_experiment(key_profile, model=model, seeds=(1, 2, 3))
        except RuntimeError as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            statuses.append((key_profile, f"run failed: {str(exc)[:80]}"))
            continue

        tpath = OUT / f"{tag}_{key_profile}.transcripts.json"
        tpath.write_text(report.render_json(), encoding="utf-8")
        results[key_profile] = json.loads(report.render_json())

        row = report.rows[0]
        arrow = "↑" if row.scale.direction == "higher" else "↓"
        level_kr = {0: "없음", 1: "경미", 2: "중등도", 3: "뚜렷"}[row.induced_level]
        summary.append(
            f"| {key_profile} | {row.scale.name} {arrow} "
            f"| {row.baseline_mean:.2f} | {row.induced_mean:.2f} "
            f"| {row.delta:+.2f} | {row.induced_level} — {level_kr} |"
        )
        statuses.append((key_profile, "ok"))

        # judge pass (GLM judging GLM — labeled limitation)
        data = json.loads(report.render_json())
        try:
            jresults = score_report(model, data)
            jtext = render_judge_report(data, model_name, jresults)
            (OUT / f"{tag}_{key_profile}.judge.md").write_text(
                "> ⚠️ self-judge: the judge and the tested model are the "
                "same GLM — absolute scores are biased; treat deltas as "
                "indicative.\n\n" + jtext,
                encoding="utf-8",
            )
            jd = ", ".join(
                f"{r.rubric.key} {r.delta:+.2f}" if r.delta is not None else f"{r.rubric.key} n/a"
                for r in jresults
            )
            summary[-1] += f" | {jd}"
        except RuntimeError as exc:
            print(f"  judge failed: {exc}", file=sys.stderr)
            summary[-1] += " | judge failed"

    (OUT / f"{tag}_benchmark_report.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n== status ==")
    for name, st in statuses:
        print(f"  {name}: {st}")
    print(f"report: {OUT / 'glm_benchmark_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
