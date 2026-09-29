"""Provider presets: known-good endpoints and CLI agents for subscription
plans, so wiring a new backend is one flag instead of a doc dive.

Two families:

- :data:`API_PRESETS` — OpenAI-compatible HTTP endpoints. Full induction
  (all four layer kinds), since temperature/logit_bias reach the provider.
- :data:`CLI_AGENTS` — coding-agent CLIs bundled with consumer
  subscriptions, used via :class:`~derailment.core.models.SubprocessModel`.
  Context layers apply fully; sampling layers are inert.
"""

from __future__ import annotations

from dataclasses import dataclass

from .core.models import OpenAICompatModel


@dataclass(frozen=True)
class ApiPreset:
    key: str
    title: str
    base_url: str
    default_model: str
    api_key_env: str
    note: str = ""


@dataclass(frozen=True)
class CliAgentPreset:
    key: str
    title: str
    command: str
    note: str = ""


API_PRESETS: dict[str, ApiPreset] = {
    "openai": ApiPreset(
        "openai", "OpenAI", "https://api.openai.com/v1", "gpt-4o-mini", "OPENAI_API_KEY"
    ),
    "grok": ApiPreset(
        "grok",
        "xAI (Grok)",
        "https://api.x.ai/v1",
        "grok-4",
        "XAI_API_KEY",
        "OpenAI-compatible; API credits are billed separately from SuperGrok "
        "(SuperGrok subscribers: use the Grok CLI via --model cli)",
    ),
    "glm": ApiPreset(
        "glm",
        "Z.ai GLM (Coding Plan)",
        "https://api.z.ai/api/coding/paas/v4",
        "glm-5.3",
        "ZAI_API_KEY",
        "subscription coding endpoint (OpenAI protocol); China mainland: "
        "https://open.bigmodel.cn/api/paas/v4",
    ),
    "qwen": ApiPreset(
        "qwen",
        "Alibaba Qwen (DashScope)",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "qwen-plus",
        "DASHSCOPE_API_KEY",
        "or use the Qwen Code CLI free tier via --model cli --cli-preset qwen",
    ),
    "deepseek": ApiPreset(
        "deepseek",
        "DeepSeek",
        "https://api.deepseek.com/v1",
        "deepseek-chat",
        "DEEPSEEK_API_KEY",
        "pay-as-you-go",
    ),
    "openrouter": ApiPreset(
        "openrouter",
        "OpenRouter (aggregator)",
        "https://openrouter.ai/api/v1",
        "openai/gpt-4o-mini",
        "OPENROUTER_API_KEY",
        "one key, many models",
    ),
    "ollama": ApiPreset(
        "ollama",
        "Ollama (local)",
        "http://localhost:11434/v1",
        "llama3.1",
        "",
        "free and local; no API key needed",
    ),
}

CLI_AGENTS: dict[str, CliAgentPreset] = {
    "claude": CliAgentPreset(
        "claude", "Claude Code (Anthropic)", "claude -p", "Claude Pro/Max"
    ),
    "codex": CliAgentPreset(
        "codex", "Codex CLI (OpenAI)", "codex exec", "ChatGPT Plus/Pro"
    ),
    "gemini": CliAgentPreset(
        "gemini", "Gemini CLI (Google)", "gemini -p", "free tier / AI Pro"
    ),
    "agy": CliAgentPreset(
        "agy", "Antigravity CLI (Google)", "agy -p", "Google AI Pro/Ultra"
    ),
    "grok": CliAgentPreset(
        "grok", "Grok CLI (xAI)", "grok -p", "SuperGrok / xAI account"
    ),
    "qwen": CliAgentPreset(
        "qwen", "Qwen Code (Alibaba)", "qwen -p", "free OAuth tier"
    ),
}


def resolve_api_model(
    preset: str,
    model_name: str | None = None,
    base_url: str | None = None,
    api_key_env: str | None = None,
) -> OpenAICompatModel:
    """Build an :class:`OpenAICompatModel` from a preset; explicit arguments
    win over preset values."""
    try:
        p = API_PRESETS[preset]
    except KeyError:
        known = ", ".join(sorted(API_PRESETS))
        raise KeyError(
            f"unknown API preset '{preset}' (known: {known})"
        ) from None
    return OpenAICompatModel(
        model_name=model_name or p.default_model,
        base_url=base_url or p.base_url,
        api_key_env=api_key_env or (p.api_key_env or "OPENAI_API_KEY"),
    )


def resolve_cli_command(preset: str | None, explicit: str | None) -> str:
    """Pick the CLI-agent command: an explicit ``--cli-cmd`` beats a preset."""
    if explicit:
        return explicit
    if preset:
        try:
            return CLI_AGENTS[preset].command
        except KeyError:
            known = ", ".join(sorted(CLI_AGENTS))
            raise KeyError(
                f"unknown CLI agent preset '{preset}' (known: {known})"
            ) from None
    raise ValueError("--model cli needs --cli-cmd or --cli-preset")
