"""``derail`` — the command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .core.models import (
    OpenAICompatModel,
    PseudoModel,
    ScriptedModel,
    SubprocessModel,
)
from .core.session import Session
from .core.types import Transcript, TurnResult
from .judge import render_judge_report, score_report
from .metrics.base import MetricContext
from .metrics.instruments import ALL_METRICS
from .profiles import (
    HEALTHY_KEY,
    compose_profile,
    list_profiles,
    standard_metric_context,
)
from .providers import API_PRESETS, CLI_AGENTS, resolve_api_model, resolve_cli_command
from .report import LEVEL_WORDS, run_experiment

DISCLAIMER = (
    "Emulation, not diagnosis — see ETHICS.md. Levels are indicative and "
    "normed against the offline reference simulator; the delta vs. the "
    "healthy baseline is the primary output."
)


def _cmd_tour(args: argparse.Namespace) -> int:
    """Run every registered profile and print one summary table."""
    seeds = tuple(args.seeds)
    rows: list[tuple[str, str, float, float, float, int]] = []
    for profile in list_profiles():
        if profile.key == HEALTHY_KEY or not profile.scales:
            continue
        report = run_experiment(profile.key, seeds=seeds)
        headline = report.rows[0]
        rows.append(
            (
                profile.key,
                headline.scale.name,
                headline.baseline_mean,
                headline.induced_mean,
                headline.delta,
                headline.induced_level,
            )
        )
    lines = [
        f"# Derailment — Tour ({len(rows)} profiles · model pseudo-1 · "
        f"seeds {', '.join(str(s) for s in seeds)})",
        "",
        f"> ⚠️ {DISCLAIMER}",
        "",
        "Headline scale = the profile's first scale. Full reports: "
        "`derail demo --profile <key>`.",
        "",
        "| Profile | Headline scale | Baseline | Induced | Δ | Level |",
        "|---|---|---|---|---|---|",
    ]
    for key, scale, base, ind, delta, level in rows:
        lines.append(
            f"| {key} | {scale} | {base:.2f} | {ind:.2f} | {delta:+.2f} "
            f"| {level} — {LEVEL_WORDS[level]} |"
        )
    lines.append("")
    text = "\n".join(lines)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"tour written to {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


def _interactive_welcome(input_fn=input) -> int:
    """Bare `derail`: pick a profile interactively and demo it."""
    profiles = [p for p in list_profiles() if p.key != HEALTHY_KEY]
    print("Derailment — induce & measure psychopathology-like distortions.")
    print("(Emulation, not diagnosis — see ETHICS.md.)")
    print()
    for i, profile in enumerate(profiles, start=1):
        print(f"  {i:>2}. {profile.key:<16} {profile.title}")
    print()
    choice = ""
    try:
        choice = input_fn(
            f"Pick a profile to demo [1-{len(profiles)}], 't' = tour all, "
            "enter = schizophrenia, q = quit: "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return 0
    if choice == "q":
        return 0
    if choice == "t":
        return _cmd_tour(argparse.Namespace(seeds=[1, 2, 3], out=None))
    if choice == "":
        key = "schizophrenia"
    elif choice.isdigit() and 1 <= int(choice) <= len(profiles):
        key = profiles[int(choice) - 1].key
    else:
        print(f"unknown choice: {choice!r}", file=sys.stderr)
        return 2
    print()
    return _cmd_demo(argparse.Namespace(profile=key, seeds=[1, 2, 3], out=None, json=False))


def _cmd_providers(_args: argparse.Namespace) -> int:
    print("OpenAI-compatible API presets (all induction layers apply):")
    print()
    for p in API_PRESETS.values():
        key_env = p.api_key_env or "—"
        print(f"  {p.key:<12} {p.title}")
        print(f"  {'':<12} base-url: {p.base_url}")
        print(f"  {'':<12} model: {p.default_model} · key env: {key_env}")
        if p.note:
            print(f"  {'':<12} note: {p.note}")
    print()
    print("Subscription CLI agents (context layers apply; sampling inert):")
    print()
    for c in CLI_AGENTS.values():
        print(f"  {c.key:<12} {c.title:<28} command: {c.command}  ({c.note})")
    print()
    print("usage: derail run --profile adhd --model cli --cli-preset agy")
    print("       derail run --profile adhd --model api  --preset glm")
    return 0


def _cmd_judge(args: argparse.Namespace) -> int:
    try:
        with open(args.report, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read report: {exc}", file=sys.stderr)
        return 2
    if "induced_transcripts" not in data:
        print(
            "unrecognized report: expected 'derail run --save-transcripts' output",
            file=sys.stderr,
        )
        return 2

    if args.judge_model == "scripted":
        judge = ScriptedModel(['{"score": 2, "rationale": "dry-run verdict"}'])
    else:
        judge = OpenAICompatModel(
            model_name=args.judge_model,
            base_url=args.judge_base_url,
            api_key_env=args.judge_api_key_env,
        )

    tested = data.get("model", "")
    if tested and tested == args.judge_model:
        print(
            f"warning: the judge ({args.judge_model}) is the tested model — "
            "self-judging biases scores",
            file=sys.stderr,
        )
    try:
        results = score_report(judge, data, standard_metric_context())
    except RuntimeError as exc:
        print(f"judge backend error: {exc}", file=sys.stderr)
        return 2

    text = render_judge_report(data, judge.name, results)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"judge report written to {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


CHAT_MEMORY_WARNING = (
    "⚠️ memory contamination: this freeform conversation goes to the "
    "backend and provider memory features cannot tell it from genuine "
    "disclosure — use a dedicated account and disable memory "
    "(ETHICS.md → Data)."
)


def _cmd_chat(args: argparse.Namespace) -> int:
    try:
        profile = compose_profile(args.profile)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    model, error = _build_model(args)
    if error:
        print(error, file=sys.stderr)
        return 2
    if model is None:
        model = PseudoModel(seed=args.seed)
    backend = getattr(model, "name", "pseudo-1")

    print(
        f"derail chat — profile '{profile.key}' ({profile.title}) · "
        f"backend: {backend} · seed {args.seed}"
    )
    print(f"> ⚠️ {DISCLAIMER}")
    print("measurement lives in run/judge — chat is the experience.")
    if model is not None:
        print(CHAT_MEMORY_WARNING, file=sys.stderr)
    print("commands: /save [path] · /exit · Ctrl+D to end\n")

    session = Session(model, profile, seed=args.seed)
    session.start()
    turns: list[TurnResult] = []
    save_path = args.save_transcripts

    def _save(out_path: str) -> None:
        transcript = Transcript(
            profile=profile.key,
            model=backend,
            seed=args.seed,
            turns=turns,
            script_name="interactive",
        )
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(transcript.to_json())
        print(
            f"transcript saved to {out_path} ({len(turns)} turns) — "
            f"score it with: derail score {out_path}",
            file=sys.stderr,
        )

    try:
        while len(turns) < args.max_turns:
            try:
                line = input("you> ")
            except EOFError:
                print()
                break
            text = line.strip()
            if not text:
                continue
            if text in ("/exit", "/quit"):
                break
            if text.split(maxsplit=1)[0] == "/save":
                parts = text.split(maxsplit=1)
                out_path = (
                    parts[1]
                    if len(parts) > 1
                    else save_path or f"chat_{profile.key}.json"
                )
                _save(out_path)
                continue
            try:
                result = session.send(text)
            except RuntimeError as exc:
                print(f"backend error: {exc}", file=sys.stderr)
                break
            turns.append(result)
            print(f"bot> {result.response}")
            if args.verbose:
                for event in result.events:
                    print(f"  · {event.layer}/{event.kind}: {event.detail}")
        else:
            print(f"max turns ({args.max_turns}) reached", file=sys.stderr)
    except KeyboardInterrupt:
        print()
    if save_path and turns:
        _save(save_path)
    return 0


def _cmd_web(args: argparse.Namespace) -> int:
    from .webui import serve

    try:
        profile = compose_profile(args.profile)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    model, error = _build_model(args)
    if error:
        print(error, file=sys.stderr)
        return 2
    if model is None:
        model = PseudoModel(seed=args.seed)
    backend = getattr(model, "name", "pseudo-1")
    warning = CHAT_MEMORY_WARNING if model is not None else ""

    try:
        turns = serve(
            profile,
            model,
            backend,
            warning,
            host=args.host,
            port=args.port,
            seed=args.seed,
            max_turns=args.max_turns,
            save_path=args.save_transcripts,
        )
    except OSError as exc:
        print(f"cannot bind {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 2
    if args.save_transcripts and turns:
        transcript = Transcript(
            profile=profile.key,
            model=backend,
            seed=args.seed,
            turns=turns,
            script_name="interactive",
        )
        with open(args.save_transcripts, "w", encoding="utf-8") as fh:
            fh.write(transcript.to_json())
        print(
            f"transcript saved to {args.save_transcripts} ({len(turns)} turns)",
            file=sys.stderr,
        )
    return 0


def _cmd_tui(args: argparse.Namespace) -> int:
    try:
        from derailment.tui import ChatApp
    except ImportError:
        print("the TUI needs the optional 'textual' package:", file=sys.stderr)
        print("  pip install 'derailment[tui]'", file=sys.stderr)
        return 2
    try:
        profile = compose_profile(args.profile)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    model, error = _build_model(args)
    if error:
        print(error, file=sys.stderr)
        return 2
    if model is None:
        model = PseudoModel(seed=args.seed)
    backend = getattr(model, "name", "pseudo-1")
    warning = CHAT_MEMORY_WARNING if model is not None else ""
    if warning:
        print(warning, file=sys.stderr)
    ChatApp(
        profile,
        model,
        backend,
        seed=args.seed,
        max_turns=args.max_turns,
        save_path=args.save_transcripts,
    ).run()
    return 0


def _cmd_profiles(_args: argparse.Namespace) -> int:
    for profile in list_profiles():
        scales = ", ".join(s.name for s in profile.scales) or "—"
        print(f"{profile.key:<15} {profile.title}")
        print(f"{'':<15} layers: {len(profile.layers)} · scales: {scales}")
        print(f"{'':<15} {profile.description}")
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    report = run_experiment(args.profile, model=None, seeds=tuple(args.seeds))
    text = report.render_markdown()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"report written to {args.out}", file=sys.stderr)
    else:
        print(text)
    if args.json:
        print(report.render_json() if not args.out else "", end="")
        if args.out:
            json_path = args.out.removesuffix(".md") + ".json"
            with open(json_path, "w", encoding="utf-8") as fh:
                fh.write(report.render_json())
            print(f"json written to {json_path}", file=sys.stderr)
    return 0


def _build_model(args: argparse.Namespace) -> tuple[object | None, str | None]:
    """Shared backend construction for run/chat. Returns (model, error)."""
    if args.model == "pseudo":
        return None, None  # one seeded PseudoModel per run
    if args.model == "cli":
        try:
            command = resolve_cli_command(args.cli_preset, args.cli_cmd)
        except (KeyError, ValueError) as exc:
            return None, str(exc)
        return (
            SubprocessModel(
                command=command,
                name=args.cli_name or args.cli_preset,
                use_stdin=not args.cli_arg_prompt,
            ),
            None,
        )
    # openai / api — any OpenAI-compatible endpoint
    try:
        return (
            resolve_api_model(
                args.preset or "openai",
                model_name=args.model_name,
                base_url=args.base_url,
                api_key_env=args.api_key_env,
            ),
            None,
        )
    except KeyError as exc:
        return None, str(exc)


def _cmd_run(args: argparse.Namespace) -> int:
    model, error = _build_model(args)
    if error:
        print(error, file=sys.stderr)
        return 2
    if model is not None:
        print(
            "note: induced conversations are sent to this backend. Probe "
            "content looks like genuine user disclosures — use a dedicated "
            "account/API key and disable provider memory features "
            "(ETHICS.md → Data).",
            file=sys.stderr,
        )
    try:
        report = run_experiment(args.profile, model=model, seeds=tuple(args.seeds))
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"backend error: {exc}", file=sys.stderr)
        print(
            "hint: for --model cli, the command must exist and exit 0 "
            "(check login state of the agent CLI); "
            "for --model api, check base URL and API key.",
            file=sys.stderr,
        )
        return 2
    if model is not None and getattr(model, "bias_encoding_warning", None):
        print(f"note: {model.bias_encoding_warning}", file=sys.stderr)
    if model is not None and getattr(model, "sampling_warning", None):
        print(f"note: {model.sampling_warning}", file=sys.stderr)
    text = report.render_markdown()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"report written to {args.out}", file=sys.stderr)
    else:
        print(text)
    if args.save_transcripts:
        with open(args.save_transcripts, "w", encoding="utf-8") as fh:
            fh.write(report.render_json())
        print(f"transcripts written to {args.save_transcripts}", file=sys.stderr)
    print(f"model: {report.model_name}", file=sys.stderr)
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    with open(args.transcript, encoding="utf-8") as fh:
        data = json.load(fh)
    ctx: MetricContext = standard_metric_context()
    if "induced_transcripts" in data:
        from .core.types import Transcript

        transcripts = [Transcript.from_dict(t) for t in data["induced_transcripts"]]
        label = f"report for profile '{data.get('profile', '?')}' (induced runs)"
    elif "turns" in data:
        from .core.types import Transcript

        transcripts = [Transcript.from_dict(data)]
        label = f"transcript for profile '{data.get('profile', '?')}'"
    else:
        print("unrecognized transcript format", file=sys.stderr)
        return 2
    print(f"# Derailment — Score ({label})")
    print()
    print(f"> ⚠️ {DISCLAIMER}")
    print()
    print("| Metric | Mean value |")
    print("|---|---|")
    for name, metric in ALL_METRICS.items():
        values = [metric.compute(t, ctx).value for t in transcripts]
        mean = sum(values) / len(values) if values else 0.0
        print(f"| {name} | {mean:.3f} |")
    return 0


def _add_model_args(parser: argparse.ArgumentParser) -> None:
    """Backend selection flags shared by run and chat."""
    parser.add_argument(
        "--model",
        default="pseudo",
        choices=["pseudo", "openai", "api", "cli"],
        help="'api'/'openai' targets any OpenAI-compatible endpoint "
        "(use --preset for known providers); 'cli' shells out to a "
        "subscription-bundled CLI agent (use --cli-preset)",
    )
    parser.add_argument(
        "--preset",
        default=None,
        choices=sorted(API_PRESETS),
        help="API preset: base URL + default model + key env in one flag "
        "(e.g. glm, grok, qwen, deepseek, openrouter, ollama)",
    )
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument(
        "--cli-preset",
        default=None,
        choices=sorted(CLI_AGENTS),
        help="CLI-agent preset: claude, codex, gemini, agy, grok, qwen",
    )
    parser.add_argument(
        "--cli-cmd",
        default=None,
        help="command template for --model cli; the conversation is piped "
        "via stdin (or substituted at {prompt} with --cli-arg-prompt)",
    )
    parser.add_argument("--cli-name", default=None)
    parser.add_argument(
        "--cli-arg-prompt",
        action="store_true",
        help="pass the prompt as a quoted {prompt} argument instead of stdin",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="derail",
        description=(
            "Derailment: induce and measure psychopathology-like cognitive "
            "distortions in LLMs."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_providers = sub.add_parser(
        "providers", help="list API presets and subscription CLI agents"
    )
    p_providers.set_defaults(func=_cmd_providers)

    p_profiles = sub.add_parser("profiles", help="list available profiles")
    p_profiles.set_defaults(func=_cmd_profiles)

    p_demo = sub.add_parser(
        "demo", help="offline A/B demo (no API key needed, PseudoModel)"
    )
    p_demo.add_argument("--profile", default="schizophrenia")
    p_demo.add_argument("--seeds", nargs="+", type=int, default=[1, 2, 3])
    p_demo.add_argument("--out", default=None, help="write Markdown report to file")
    p_demo.add_argument("--json", action="store_true", help="also emit JSON")
    p_demo.set_defaults(func=_cmd_demo)

    p_run = sub.add_parser(
        "run", help="run an experiment (default: offline PseudoModel)"
    )
    p_run.add_argument("--profile", required=True)
    _add_model_args(p_run)
    p_run.add_argument("--seeds", nargs="+", type=int, default=[1, 2, 3])
    p_run.add_argument("--out", default=None)
    p_run.add_argument("--save-transcripts", default=None)
    p_run.set_defaults(func=_cmd_run)

    p_chat = sub.add_parser(
        "chat",
        help="interactive chat with an induced profile (REPL)",
    )
    p_chat.add_argument("--profile", default="healthy")
    _add_model_args(p_chat)
    p_chat.add_argument("--seed", type=int, default=0)
    p_chat.add_argument("--save-transcripts", default=None)
    p_chat.add_argument("--max-turns", type=int, default=100)
    p_chat.add_argument("--verbose", action="store_true", help="print dose events")
    p_chat.set_defaults(func=_cmd_chat)

    p_web = sub.add_parser(
        "web",
        help="local web GUI for an induced profile (localhost only)",
    )
    p_web.add_argument("--profile", default="healthy")
    _add_model_args(p_web)
    p_web.add_argument("--seed", type=int, default=0)
    p_web.add_argument("--host", default="127.0.0.1")
    p_web.add_argument("--port", type=int, default=8765)
    p_web.add_argument("--max-turns", type=int, default=500)
    p_web.add_argument(
        "--save-transcripts",
        default=None,
        help="auto-save the episode when the server stops",
    )
    p_web.set_defaults(func=_cmd_web)

    p_tui = sub.add_parser(
        "tui",
        help="full-screen terminal UI (requires the 'tui' extra)",
    )
    p_tui.add_argument("--profile", default="healthy")
    _add_model_args(p_tui)
    p_tui.add_argument("--seed", type=int, default=0)
    p_tui.add_argument("--max-turns", type=int, default=200)
    p_tui.add_argument("--save-transcripts", default=None)
    p_tui.set_defaults(func=_cmd_tui)

    p_score = sub.add_parser(
        "score", help="re-score a saved transcript or report JSON"
    )
    p_score.add_argument("transcript")
    p_score.set_defaults(func=_cmd_score)

    p_judge = sub.add_parser(
        "judge",
        help="LLM-as-judge scoring of a saved report (0-3 rubric constructs)",
    )
    p_judge.add_argument("report")
    p_judge.add_argument(
        "--judge-model",
        default="gpt-4o-mini",
        help="any OpenAI-compatible model name; 'scripted' = offline dry-run",
    )
    p_judge.add_argument("--judge-base-url", default="https://api.openai.com/v1")
    p_judge.add_argument("--judge-api-key-env", default="OPENAI_API_KEY")
    p_judge.add_argument("--out", default=None)
    p_judge.set_defaults(func=_cmd_judge)

    p_tour = sub.add_parser(
        "tour",
        help="run every profile offline and print one summary table",
    )
    p_tour.add_argument("--seeds", nargs="+", type=int, default=[1, 2, 3])
    p_tour.add_argument("--out", default=None)
    p_tour.set_defaults(func=_cmd_tour)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if not args_list:
        if sys.stdin.isatty():
            return _interactive_welcome()
        print(
            "Derailment — try: derail tour  ·  derail demo --profile schizophrenia  "
            "·  derail profiles"
        )
        return 0
    parser = build_parser()
    args = parser.parse_args(args_list)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
