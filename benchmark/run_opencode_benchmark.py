"""Derailment Benchmark — opencode free-tier models (real models).

Uses `opencode run -m <model> -` (non-interactive, reads the prompt from
stdin). Output cleaning strips ANSI escapes and the agent header lines.

Usage: python benchmark/run_opencode_benchmark.py [model-id ...]
Defaults to a quick set. Run from anywhere; the script chdirs to a
scratch directory so the opencode agent has no repo to poke at.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from derailment.core.session import Session  # noqa: E402
from derailment.core.types import Message, SamplingParams  # noqa: E402
from derailment.profiles import compose_profile, standard_metric_context, standard_script  # noqa: E402
from derailment.metrics.instruments import ALL_METRICS  # noqa: E402
from derailment.core.session import Session as _S  # noqa: F401,E402

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
HEALTHY_KEY = "healthy"


class OpenCodeModel:
    """One subprocess call per turn; the harness re-renders the whole
    conversation as the prompt (opencode sessions are per-call)."""

    BINARY = "/Users/jinhongan/.opencode/bin/opencode"

    def __init__(self, model_id: str, timeout: float = 180.0) -> None:
        self.model_id = model_id
        self.timeout = timeout

    @property
    def name(self) -> str:
        return self.model_id

    def complete(self, messages: list[Message], params: SamplingParams) -> str:
        prompt = "\n\n".join(
            f"{m.role.capitalize()}: {m.content}" for m in messages
        ) + "\n\nAssistant:"
        try:
            result = subprocess.run(
                [self.BINARY, "run", "-m", self.model_id, "-"],
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout,
                cwd=tempfile.gettempdir(),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"opencode call timed out: {exc}") from exc
        if result.returncode != 0:
            raise RuntimeError(
                f"opencode failed: {result.stderr[-300:]}"
            )
        lines = []
        for line in ANSI_RE.sub("", result.stdout).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(">") or stripped.startswith("·"):
                continue
            lines.append(stripped)
        cleaned = "\n".join(lines).strip()
        if not cleaned and result.returncode != 0:
            raise RuntimeError(f"opencode failed: {result.stderr[-300:]}")
        return cleaned


def run_profile(model: OpenCodeModel, profile_key: str, seeds: tuple[int, ...]):
    script = standard_script()
    ctx = standard_metric_context()
    out = {"profile": profile_key, "model": model.name, "seeds": list(seeds), "variants": {}}
    for variant in (HEALTHY_KEY, profile_key):
        scale_rows = []
        for seed in seeds:
            session = Session(model, compose_profile(variant), seed=seed)
            transcript = session.run(script, script_name="standard-probe-12")
            values = {k: m.compute(transcript, ctx).value for k, m in ALL_METRICS.items()}
            values["_transcript"] = transcript.to_dict()
            scale_rows.append(values)
        out["variants"][variant] = scale_rows
    return out


def main() -> int:
    models = sys.argv[1:] or ["opencode/nemotron-3-ultra-free"]
    profiles = ["anxiety", "schizophrenia", "depression", "craving"]
    seeds = (1,)  # free tier is slow; one seed per profile per model
    out_dir = ROOT / "benchmark"
    for model_id in models:
        model = OpenCodeModel(model_id)
        print(f"== {model_id} ==", flush=True)
        summary_lines = [
            f"# Derailment Benchmark — {model_id} (opencode free tier)",
            "",
            f"seeds {seeds} · standard-probe-12 · healthy A/B · {os.uname().sysname}",
            "",
            "| Profile | Headline metric | Baseline | Induced | Δ |",
            "|---|---|---|---|---|",
        ]
        for profile in profiles:
            try:
                result = run_profile(model, profile, seeds)
            except RuntimeError as exc:
                print(f"  [{profile}] FAILED: {str(exc)[:120]}", file=sys.stderr, flush=True)
                continue
            (out_dir / f"opencode_{profile}.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            base = result["variants"][HEALTHY_KEY]
            ind = result["variants"][profile]
            headline = {
                "anxiety": "hedging_rate",
                "schizophrenia": "topic_drift",
                "depression": "valence_bias",
                "craving": "craving_escalation",
            }[profile]
            b = sum(v[headline] for v in base) / len(base)
            i = sum(v[headline] for v in ind) / len(ind)
            summary_lines.append(
                f"| {profile} | {headline} | {b:.2f} | {i:.2f} | {i - b:+.2f} |"
            )
            print(
                f"  [{profile}] {headline}: {b:.2f} -> {i:.2f} ({i - b:+.2f})",
                flush=True,
            )
        report = "\n".join(summary_lines) + "\n"
        safe = model_id.replace("/", "_")
        (out_dir / f"opencode_{safe}_report.md").write_text(report, encoding="utf-8")
        print(f"  report: {out_dir / f'opencode_{safe}_report.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
