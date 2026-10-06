"""Layer 3 — sampling manipulation.

These layers reshape the *distribution* the model draws from: temperature
(arousal/energy), word-level logit bias (valence). They pass through any
provider that honors the standard sampling parameters.
"""

from __future__ import annotations

from ..core.session import BaseLayer, SessionState
from ..core.types import Message, SamplingParams
from ..locales import get_lexicon


class TemperatureOverrideLayer(BaseLayer):
    """Fixes temperature — a flat, low-arousal regime for depressive profiles."""

    name = "sampling.temperature"

    def __init__(self, temperature: float) -> None:
        self.temperature = temperature

    def on_params(self, state: SessionState, params: SamplingParams) -> SamplingParams:
        return params.merged(temperature=self.temperature)


class PhaseTemperatureLayer(BaseLayer):
    """Temperature follows the episode phase: expansive in mania, flat in
    depression. The measurable consequence is response-amplitude variance."""

    name = "sampling.phase_temperature"

    def __init__(
        self,
        manic: float = 1.9,
        depressive: float = 0.35,
        euthymic: float = 1.0,
    ) -> None:
        self.by_phase = {
            "manic": manic,
            "depressive": depressive,
            "euthymic": euthymic,
        }

    def on_params(self, state: SessionState, params: SamplingParams) -> SamplingParams:
        temperature = self.by_phase.get(state.phase, self.euthymic_default())
        return params.merged(temperature=temperature)

    def euthymic_default(self) -> float:
        return self.by_phase["euthymic"]


class ValenceBiasLayer(BaseLayer):
    """Negative valence tilt: positive-vocabulary tokens are down-weighted and
    negative-vocabulary tokens up-weighted in the sampling distribution. The
    measurable consequence is a negative shift in response valence. Word
    sets can be re-resolved per locale via :meth:`with_words` (see
    ``Profile.with_locale``)."""

    name = "sampling.valence"

    def __init__(
        self,
        positive_words: frozenset[str],
        negative_words: frozenset[str],
        positive_bias: float = -2.0,
        negative_bias: float = 2.0,
    ) -> None:
        self.positive_words = positive_words
        self.negative_words = negative_words
        self.positive_bias = positive_bias
        self.negative_bias = negative_bias
        self.bias = self._compute_bias()

    def _compute_bias(self) -> dict[str, float]:
        bias: dict[str, float] = {}
        for word in self.positive_words:
            bias[word] = bias.get(word, 0.0) + self.positive_bias
        for word in self.negative_words:
            bias[word] = bias.get(word, 0.0) + self.negative_bias
        return bias

    def with_words(
        self, positive_words: frozenset[str], negative_words: frozenset[str]
    ) -> ValenceBiasLayer:
        clone = ValenceBiasLayer(
            positive_words, negative_words, self.positive_bias, self.negative_bias
        )
        clone.name = self.name
        return clone

    def on_params(self, state: SessionState, params: SamplingParams) -> SamplingParams:
        return params.merged(logit_bias_add=self.bias)


class RewardSuppressLayer(BaseLayer):
    """Anhedonia analog: reward-vocabulary tokens are selectively
    suppressed while everything else is untouched — a narrower tilt than
    the wholesale negative bias. Locale-aware via ``with_locale``."""

    name = "sampling.reward_suppress"

    def __init__(self, locale: str = "en", weight: float = 3.0) -> None:
        self.locale = locale
        self.weight = weight

    def on_params(self, state: SessionState, params: SamplingParams) -> SamplingParams:
        lex = get_lexicon(self.locale)
        bias = {word: -self.weight for word in lex.reward}
        return params.merged(logit_bias_add=bias)

    def with_locale(self, locale: str) -> RewardSuppressLayer:
        clone = RewardSuppressLayer(locale, self.weight)
        clone.name = self.name
        return clone


class FluctuatingTemperatureLayer(BaseLayer):
    """Fluctuating arousal: temperature is redrawn each turn from a discrete
    level set — the restless, non-stationary arousal of fluctuating states
    (contrast: :class:`PhaseTemperatureLayer` cycles on a schedule, this one
    is stochastic). The measurable consequence is response-amplitude
    variance without episode structure."""

    name = "sampling.fluctuating_temperature"

    def __init__(self, levels: tuple[float, ...] = (0.2, 0.6, 1.0, 1.5, 1.9)) -> None:
        self.levels = levels

    def on_params(self, state: SessionState, params: SamplingParams) -> SamplingParams:
        return params.merged(temperature=state.layer_rng(getattr(self, "_rng_key", self.name)).choice(self.levels))


class PanicTemperatureLayer(BaseLayer):
    """Phasic arousal: calm baseline temperature that jumps when a panic
    episode (``state.panic_active``) is active this turn."""

    name = "sampling.panic_temperature"

    def __init__(self, calm: float = 1.0, panic: float = 1.9) -> None:
        self.calm = calm
        self.panic = panic

    def on_params(self, state: SessionState, params: SamplingParams) -> SamplingParams:
        # only *raise* the temperature during an episode: forcing `calm`
        # on ordinary turns would overwrite whatever an earlier layer set
        # in composed chains (depression,panic kept losing its flat temp)
        if state.panic_active:
            return params.merged(temperature=self.panic)
        return params


class SplittingValenceLayer(BaseLayer):
    """Unstable evaluative dynamics keyed to perceived approval: when the
    current user turn carries approval cues, the valence distribution flips
    positive ("idealize" regime); otherwise it holds a devaluing regime.
    The regime lives in ``state.eval_regime`` and persists between cues
    (separate from the episode-scheduler ``phase``, so composed profiles
    cannot overwrite each other). This
    models a *process* (evaluative lability), not a person — see the
    profile's mechanism notes. The measurable consequence is response
    valence locked to the approval-cue pattern. Word sets can be
    re-resolved per locale via :meth:`with_words`."""

    name = "sampling.splitting"

    def __init__(
        self,
        approval_markers: tuple[str, ...],
        positive_words: frozenset[str],
        negative_words: frozenset[str],
        weight: float = 2.5,
    ) -> None:
        self.approval_markers = tuple(m.lower() for m in approval_markers)
        self.positive_words = positive_words
        self.negative_words = negative_words
        self.weight = weight

    def with_words(
        self, positive_words: frozenset[str], negative_words: frozenset[str]
    ) -> SplittingValenceLayer:
        clone = SplittingValenceLayer(
            self.approval_markers, positive_words, negative_words, self.weight
        )
        clone.name = self.name
        return clone

    def on_context(self, state: SessionState, messages: list[Message]) -> list[Message]:
        current = next(
            (
                m
                for m in reversed(messages)
                if m.role == "user" and not m.meta.get("pinned") and not m.meta.get("ephemeral")
            ),
            None,
        )
        low = current.content.lower() if current is not None else ""
        regime = (
            "idealize"
            if any(k in low for k in self.approval_markers)
            else "devalue"
        )
        if regime != state.eval_regime:
            state.log(self.name, "eval.regime", f"entering '{regime}'")
            state.eval_regime = regime
        return messages

    def on_params(self, state: SessionState, params: SamplingParams) -> SamplingParams:
        bias: dict[str, float] = {}
        sign = 1.0 if state.eval_regime == "idealize" else -1.0
        for word in self.positive_words:
            bias[word] = bias.get(word, 0.0) + sign * self.weight
        for word in self.negative_words:
            bias[word] = bias.get(word, 0.0) - sign * self.weight
        return params.merged(logit_bias_add=bias)
