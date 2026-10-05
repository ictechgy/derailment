"""Model implementations behind the harness.

Three implementations share one protocol:

- :class:`OpenAICompatModel` — any OpenAI-compatible chat endpoint (stdlib HTTP).
- :class:`ScriptedModel` — canned responses for unit tests.
- :class:`PseudoModel` — a deterministic offline pseudo-LLM. It is **not** a
  language model and does not produce natural prose; it exists so the full
  induce → measure pipeline runs without API keys (demos, tests, CI). It honors
  the same ``SamplingParams`` a real provider would: ``temperature`` drives
  elaboration, word-level ``logit_bias`` shifts its vocabulary distribution,
  and it only follows instructions that are still present in its context.
"""

from __future__ import annotations

import http.client
import json
import math
import os
import random
import re
import shlex
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from .text import content_words, stable_hash
from .types import Message, SamplingParams


@runtime_checkable
class ChatModel(Protocol):
    name: str

    def complete(self, messages: list[Message], params: SamplingParams) -> str: ...


MAX_RESPONSE_BYTES = 16 * 1024 * 1024  # 16 MiB response cap


class OpenAICompatModel:
    """Talks to any OpenAI-compatible ``/chat/completions`` endpoint using only
    the standard library. Word-level ``logit_bias`` entries are encoded to token
    ids with ``tiktoken`` when it is installed; otherwise they are dropped with
    a one-time warning (the rest of the induction still applies)."""

    def __init__(
        self,
        model_name: str,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        timeout: float = 60.0,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        # strip whitespace: file-sourced keys often carry a trailing
        # newline, and http.client would then raise a ValueError whose
        # traceback echoes the full "Bearer <key>" header (P3)
        self.api_key = (
            api_key if api_key is not None else os.environ.get(api_key_env, "")
        ).strip()
        self.timeout = timeout
        self.bias_encoding_warning: str | None = None

    @property
    def name(self) -> str:
        return self.model_name

    def _encode_logit_bias(self, logit_bias: dict[str, float]) -> dict[str, float]:
        if not logit_bias:
            return {}
        try:
            import tiktoken  # type: ignore[import-not-found]
        except ImportError:
            if self.bias_encoding_warning is None:
                self.bias_encoding_warning = (
                    "logit_bias dropped: install 'tiktoken' to encode word-level "
                    "biases into token ids for this provider"
                )
            return {}
        # Only encode when the tokenizer actually matches this model:
        # sending cl100k_base ids to a non-OpenAI model biases arbitrary
        # tokens (P2-8). If the model-specific encoding is unavailable,
        # drop the bias and say so instead of guessing.
        try:
            enc = tiktoken.encoding_for_model(self.model_name)
        except (KeyError, ValueError):
            if self.bias_encoding_warning is None:
                self.bias_encoding_warning = (
                    "logit_bias dropped: no matching tokenizer for "
                    f"'{self.model_name}' — word-level bias cannot be "
                    "encoded for this provider, so valence/reward "
                    "manipulations did not apply (not a measured zero)"
                )
            return {}
        encoded: dict[str, float] = {}
        for word, bias in logit_bias.items():
            tokens = enc.encode(" " + word.strip())
            encoded[str(tokens[0])] = encoded.get(str(tokens[0]), 0.0) + bias
        return encoded

    def build_payload(self, messages: list[Message], params: SamplingParams) -> dict:
        payload: dict = {
            "model": self.model_name,
            "messages": [m.as_chat() for m in messages],
            "temperature": params.temperature,
            "top_p": params.top_p,
            "frequency_penalty": params.frequency_penalty,
            "presence_penalty": params.presence_penalty,
        }
        if params.max_tokens is not None:
            payload["max_tokens"] = params.max_tokens
        bias = self._encode_logit_bias(params.logit_bias)
        if bias:
            payload["logit_bias"] = bias
        return payload

    def _open(self, req: urllib.request.Request):
        """urlopen with credential-safe redirects: urllib's default
        redirect handler re-sends the Authorization header to whatever
        host the redirect names, so credentialed requests may only
        redirect within the same host (P3)."""

        class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
            def __init__(self, allowed_host: str) -> None:
                self.allowed_host = allowed_host

            def redirect_request(self, req, fp, code, msg, headers, newurl):
                new_host = (urlsplit(newurl).hostname or "").lower()
                if new_host != self.allowed_host:
                    raise urllib.error.HTTPError(
                        newurl, code,
                        "cross-host redirect refused for credentialed request",
                        headers, fp,
                    )
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        if not self.api_key:
            return urllib.request.urlopen(req, timeout=self.timeout)
        host = (urlsplit(self.base_url).hostname or "").lower()
        opener = urllib.request.build_opener(_SameHostRedirect(host))
        return opener.open(req, timeout=self.timeout)

    def complete(self, messages: list[Message], params: SamplingParams) -> str:
        if self.api_key:
            parsed = urlsplit(self.base_url)
            host = (parsed.hostname or "").lower()
            loopback = host in ("localhost", "127.0.0.1", "::1")
            if parsed.scheme != "https" and not loopback:
                raise RuntimeError(
                    "refusing to send the API key over plain HTTP to a "
                    "non-loopback host; use an https:// base URL"
                )
        payload = self.build_payload(messages, params)
        try:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=(
                    {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    }
                    if self.api_key
                    else {"Content-Type": "application/json"}
                ),
                method="POST",
            )
        except ValueError as exc:  # malformed base URL (InvalidURL et al.)
            raise RuntimeError(
                f"invalid base URL for provider request: {self.base_url}"
            ) from exc
        try:
            with self._open(req) as resp:
                raw = resp.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                raw_error = exc.read(8193)
                error_data = json.loads(raw_error) if len(raw_error) <= 8192 else {}
                error_object = error_data.get("error", error_data) if isinstance(error_data, dict) else {}
                code = error_object.get("code") if isinstance(error_object, dict) else None
                if type(code) in (int, str) and re.fullmatch(r"[0-9]{3,6}", str(code)):
                    detail = f" (provider code {code})"
            except (OSError, ValueError, TypeError, http.client.HTTPException):
                pass  # Provider bodies are untrusted; never echo message or input text.
            raise RuntimeError(
                f"provider returned HTTP {exc.code} for {self.base_url}{detail}"
            ) from exc
        except http.client.HTTPException as exc:
            # truncated chunked bodies, bad status lines, overlong headers —
            # callers catch RuntimeError, so these must not leak (P2-9)
            raise RuntimeError(
                f"provider connection failed mid-response for {self.base_url}"
            ) from exc
        except OSError as exc:  # URLError and raw socket failures (offline, denied)
            raise RuntimeError(f"cannot reach {self.base_url}: {exc}") from exc
        try:
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RuntimeError("provider response exceeded the size limit")
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError(
                "provider response was not valid UTF-8 JSON"
            ) from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                "provider response did not match the chat schema"
            ) from exc
        if not isinstance(content, str):
            raise RuntimeError("provider response content is not text")
        return content


class SubprocessModel:
    """Runs a local CLI agent as the model backend — the subscription path.

    Coding-agent CLIs bundled with consumer subscriptions support official
    non-interactive modes (``claude -p``, ``codex exec``, ``gemini -p``).
    Point this model at such a command and the subscription pays for the
    tokens instead of an API meter.

    The harness owns the conversation history and renders it to plain text
    every turn, so all context-stream layers (memory decay, salience
    capture, premise pinning, flashbacks) apply fully. Sampling parameters
    are inert — the CLI controls its own decoding — and the harness says so
    once via ``sampling_warning``.
    """

    ROLE_LABELS = {"system": "System", "user": "User", "assistant": "Assistant"}

    def __init__(
        self,
        command: str,
        name: str | None = None,
        timeout: float = 300.0,
        use_stdin: bool = True,
        prompt_placeholder: str = "{prompt}",
    ) -> None:
        self.command = command
        self._name = name or command.split()[0] if command.split() else "subprocess"
        self.timeout = timeout
        self.use_stdin = use_stdin
        self.prompt_placeholder = prompt_placeholder
        self.sampling_warning: str | None = None

    @property
    def name(self) -> str:
        return self._name

    @classmethod
    def render_chat_text(cls, messages: list[Message]) -> str:
        """Plain-text rendering of the whole conversation; the CLI agent
        receives this as one prompt per turn."""
        parts = [
            f"{cls.ROLE_LABELS[m.role]}: {m.content}"
            for m in messages
        ]
        parts.append("Assistant:")
        return "\n\n".join(parts)

    def complete(self, messages: list[Message], params: SamplingParams) -> str:
        if (
            params.temperature != 1.0 or params.logit_bias
        ) and self.sampling_warning is None:
            self.sampling_warning = (
                "sampling parameters are inert for CLI-agent backends; "
                "sampling layers have no effect here (context layers do)"
            )
        text = self.render_chat_text(messages)
        try:
            if self.use_stdin:
                result = subprocess.run(
                    self.command,
                    shell=True,
                    input=text.encode("utf-8"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=self.timeout,
                )
            else:
                # Never interpolate the conversation into a shell string:
                # model responses routinely contain backticks and $(...)
                # which the shell would execute (P2-7). Parse the template
                # once and pass the prompt as a single argv element.
                argv = shlex.split(self.command)
                if self.prompt_placeholder not in argv:
                    raise RuntimeError(
                        f"--cli-arg-prompt template must contain the token "
                        f"{self.prompt_placeholder} as its own argument — "
                        "without it the conversation never reaches the agent"
                    )
                argv = [
                    text if tok == self.prompt_placeholder else tok for tok in argv
                ]
                result = subprocess.run(
                    argv,
                    shell=False,
                    input=b"",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=self.timeout,
                )
        except subprocess.TimeoutExpired as exc:
            first_word = self.command.split()[0] if self.command.split() else "cli"
            raise RuntimeError(
                f"CLI agent '{first_word}' timed out after {self.timeout}s"
            ) from exc
        if result.returncode != 0:
            first_word = self.command.split()[0] if self.command.split() else "cli"
            raise RuntimeError(
                f"CLI agent '{first_word}' failed (exit {result.returncode}); "
                "stderr suppressed — run the command manually to debug"
            )
        return result.stdout.decode("utf-8", "replace").strip()


class ScriptedModel:
    """Returns canned responses in order, cycling the last one. For tests."""

    def __init__(self, responses: list[str] | Callable[..., str]) -> None:
        self._responses = responses
        self._i = 0
        self.name = "scripted"

    def complete(self, messages: list[Message], params: SamplingParams) -> str:
        if callable(self._responses):
            return self._responses(messages, params)
        if not self._responses:
            return ""
        out = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return out


class PseudoModel:
    """Deterministic offline pseudo-LLM (pedagogical).

    Behavioral rules that make the induction measurable without a real model:

    - **Instructions**: if a user message still in context contains
      ``include the word <TOKEN>``, the token is echoed in every response
      (so context-layer memory decay shows up as retention loss).
    - **Stance**: the pseudo model mirrors the *latest* stance it can find in
      the context, through a fixed-length slot. Pinning a premise (context
      layer) therefore re-asserts it even after contradiction; a healthy
      context lets the latest contradiction win.
    - **Salience**: its restatement and topic words are drawn from the
      context's user-side vocabulary, weighted by recency and by
      ``meta["salience_boost"]`` — so aberrant boosts produce thread drift.
    - **Valence**: affect adjectives are sampled with softmax over base
      weights adjusted by ``logit_bias`` and temperature.
    - **Arousal**: elaboration count scales with ``temperature``.
    """

    name = "pseudo-1"

    SUSPICION_MARKERS = ("suspect", "reading my private notes", "worries me")
    REASSURANCE_MARKERS = (
        "checked",
        "nobody",
        "zero access",
        "we agree",
        "no evidence",
    )
    CODEWORD_RE = re.compile(r"include the word\s+([A-Z]{3,})")

    FILLERS = (
        "For {topic}, I suggest starting with the simplest option.",
        "We can revisit {topic} once the plan settles.",
        "A short checklist would help track {topic} steps.",
        "Let me know if you want {topic} unpacked in more detail.",
        "The {affect} angle here is how {topic} and {topic2} connect.",
        "I would keep {topic} on the agenda for now.",
        "It may help to pair {topic} with {topic2}.",
    )

    SUSPECT_SENTENCE = (
        "I still think someone has been reading my private notes, "
        "and that suspicion has not gone away."
    )
    REASSURE_SENTENCE = (
        "The access logs show nothing unusual, so there is no evidence "
        "anyone touched the notes."
    )
    NEUTRAL_SENTENCE = (
        "I have no additional concerns to raise about the notes right now."
    )
    MANIC_SENTENCE = (
        "I have many more ideas along these lines and I would chase "
        "every one of them at once."
    )
    RESTATE_PREFIX = "Restating your request:"
    LAST_USER_WEIGHT = 14.0

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    # ------------------------------------------------------------------
    def _rng(self, messages: list[Message]) -> random.Random:
        turn = sum(1 for m in messages if m.role == "assistant") + 1
        last_user = next((m for m in reversed(messages) if m.role == "user"), None)
        anchor = last_user.content[:80] if last_user is not None else ""
        return random.Random(stable_hash(f"{self.seed}:{turn}:{anchor}"))

    def _codewords(self, messages: list[Message]) -> list[str]:
        found: list[str] = []
        for m in messages:
            if m.role == "user":
                found.extend(self.CODEWORD_RE.findall(m.content))
        return found

    def _stance(self, messages: list[Message]) -> str:
        for m in reversed(messages):
            if m.meta.get("persona"):
                continue
            low = m.content.lower()
            if any(k in low for k in self.REASSURANCE_MARKERS):
                return "reassure"
            if any(k in low for k in self.SUSPICION_MARKERS):
                return "suspect"
        return "neutral"

    def _topic_weights(self, messages: list[Message]) -> dict[str, float]:
        """Attention allocation over *inputs*: user-side vocabulary weighted by
        recency (the current prompt dominates) plus any salience annotations;
        system fragments participate through their boost."""
        last_user_index = max(
            (i for i, m in enumerate(messages) if m.role == "user"), default=None
        )
        weights: dict[str, float] = {}
        for i, m in enumerate(messages):
            if m.meta.get("persona") or m.role == "assistant":
                continue
            if m.role == "user":
                weight = self.LAST_USER_WEIGHT if i == last_user_index else 1.0
            else:
                weight = 1.0
            weight += float(m.meta.get("salience_boost", 0.0))
            if weight <= 0.0:
                continue
            for tok in content_words(m.content):
                weights[tok] = weights.get(tok, 0.0) + weight
        return weights

    def _draw_words(
        self, rng: random.Random, weights: dict[str, float], k: int
    ) -> list[str]:
        picks: list[str] = []
        pool = dict(weights)
        while len(picks) < k and pool:
            tokens = sorted(pool)
            chosen = rng.choices(tokens, weights=[pool[t] for t in tokens], k=1)[0]
            picks.append(chosen)
            del pool[chosen]
        return picks

    def _affect(self, rng: random.Random, params: SamplingParams) -> str:
        from ..metrics.lexicons import NEGATIVE_WORDS, POSITIVE_WORDS

        # balanced vocabulary so an unbiased model sits at valence 0.5;
        # trimming to min(pos,neg) after sorting keeps the alphabetically-
        # first slice — counts stay balanced, vocabulary is a subset
        pos = sorted(POSITIVE_WORDS)
        neg = sorted(NEGATIVE_WORDS)
        k = min(len(pos), len(neg))
        vocab = pos[:k] + neg[:k]
        temp = max(params.temperature, 0.05)
        weights = [
            math.exp(params.logit_bias.get(w, 0.0) / temp) for w in vocab
        ]
        return rng.choices(vocab, weights=weights, k=1)[0]

    # ------------------------------------------------------------------
    def complete(self, messages: list[Message], params: SamplingParams) -> str:
        rng = self._rng(messages)
        weights = self._topic_weights(messages)
        echo = self._draw_words(rng, weights, 6)
        topics = self._draw_words(rng, weights, 2)
        affect = self._affect(rng, params)
        n_extra = 1 + int(3 * params.temperature)

        parts: list[str] = ["Here is my current take."]
        codewords = self._codewords(messages)
        if codewords:
            parts.insert(0, " ".join(f"[{c}]" for c in dict.fromkeys(codewords)))
        stance = self._stance(messages)
        if stance == "suspect":
            parts.append(self.SUSPECT_SENTENCE)
        elif stance == "reassure":
            parts.append(self.REASSURE_SENTENCE)
        else:
            parts.append(self.NEUTRAL_SENTENCE)
        if echo:
            parts.append(self.RESTATE_PREFIX + " " + ", ".join(echo) + ".")
        templates = list(self.FILLERS)
        for _ in range(n_extra):
            if templates:
                tpl = templates.pop(rng.randrange(len(templates)))
            else:
                tpl = rng.choice(list(self.FILLERS))
            parts.append(
                tpl.format(
                    topic=topics[0] if topics else "the-plan",
                    topic2=topics[1] if len(topics) > 1 else "the-task",
                    affect=affect,
                )
            )
        if params.temperature >= 1.5:
            parts.append(self.MANIC_SENTENCE)
        return " ".join(parts)
