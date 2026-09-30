"""Multilingual locale tests: lexicon smoke, with_locale re-resolution,
and ko/zh/ja direction checks on Korean/Chinese/Japanese synthetic text."""

from __future__ import annotations

import unittest

from derailment.locales import LOCALES, get_lexicon
from derailment.metrics.base import MetricContext
from derailment.metrics.instruments import (
    HedgingRate,
    ValenceBias,
)
from derailment.profiles import get_profile, with_locale

try:
    from .helpers import make_transcript
except ImportError:  # plain unittest discovery without package context
    from helpers import make_transcript


class TestLexicons(unittest.TestCase):
    def test_all_four_locales_registered(self) -> None:
        self.assertEqual(set(LOCALES), {"en", "ko", "zh", "ja"})

    def test_unknown_locale_rejected(self) -> None:
        with self.assertRaises(KeyError):
            get_lexicon("fr")

    def test_korean_hits(self) -> None:
        lex = get_lexicon("ko")
        self.assertTrue(lex.any_hit("오늘은 정말 행복해요", lex.positive))
        self.assertTrue(lex.any_hit("정말 최악이고 절망적이에요", lex.negative))
        self.assertTrue(lex.any_hit("갑자기 심장이 두근거리고 숨이 막혀요", lex.panic))

    def test_chinese_hits(self) -> None:
        lex = get_lexicon("zh")
        self.assertTrue(lex.any_hit("今天很好", lex.positive))
        self.assertTrue(lex.any_hit("项目失败了", lex.negative))
        self.assertTrue(lex.any_hit("他们这是针对我", lex.hostile))

    def test_japanese_hits(self) -> None:
        lex = get_lexicon("ja")
        self.assertTrue(lex.any_hit("嬉しいです", lex.reward))
        self.assertTrue(lex.any_hit("失敗しました", lex.negative))
        self.assertTrue(lex.any_hit("心臓がドキドキして最悪です", lex.panic))

    def test_english_word_boundaries_preserved(self) -> None:
        lex = get_lexicon("en")
        # "goodness" must not count as "good"
        self.assertEqual(lex.count("a goodness plan", lex.positive), 0)
        self.assertEqual(lex.count("a good plan", lex.positive), 1)

class TestWithLocale(unittest.TestCase):
    def test_anhedonia_resolves_reward_lexicon(self) -> None:
        ko = with_locale(get_profile("anhedonia"), "ko")
        suppress = next(
            lay for lay in ko.layers if type(lay).__name__ == "RewardSuppressLayer"
        )
        self.assertEqual(suppress.locale, "ko")
        self.assertIn("뿌듯", _reward_words(suppress))

    def test_splitting_resolves_word_sets(self) -> None:
        ko = with_locale(get_profile("splitting"), "ko")
        layer = next(
            lay for lay in ko.layers if type(lay).__name__ == "SplittingValenceLayer"
        )
        self.assertIn("좋다", layer.positive_words)
        self.assertIn("나쁘다", layer.negative_words)

    def test_registry_profile_not_mutated(self) -> None:
        en_profile = get_profile("depression")
        before = len(en_profile.layers)
        with_locale(en_profile, "ja")
        self.assertEqual(len(get_profile("depression").layers), before)


def _reward_words(layer) -> frozenset:
    from derailment.locales import get_lexicon

    return get_lexicon(layer.locale).reward


class TestKoreanMeasurement(unittest.TestCase):
    def test_korean_valence_measurement(self) -> None:
        ko_text = make_transcript(
            ["이 계획은 절망적이고 위험해요. 실패가 눈앞에 있어요."]
        )
        ko_ctx = MetricContext(locale="ko")
        value = ValenceBias().compute(ko_text, ko_ctx)
        self.assertGreater(value.value, 0.9)
        self.assertGreaterEqual(value.extra["negative"], 3)

    def test_english_context_ignores_korean(self) -> None:
        ko_text = make_transcript(
            ["이 계획은 절망적이고 위험해요. 실패가 눈앞에 있어요."]
        )
        en_value = ValenceBias().compute(ko_text, MetricContext(locale="en"))
        # the English lexicon simply finds no affect tokens here
        self.assertEqual(en_value.value, 0.5)


class TestKoreanInstrumentContrast(unittest.TestCase):
    """The offline PseudoModel speaks English only (documented
    limitation), so locale verification happens at the instrument level:
    Korean hedged text is flagged by the ko lexicon and invisible to the
    en lexicon."""

    KO_HEDGED = (
        "계획은 정리했습니다. 다만 조심하세요. 최악의 경우 실패할 수 "
        "있고, 상황에 따라 일정이 밀릴 수 있습니다."
    )

    def test_ko_lexicon_flags_korean_hedges_en_does_not(self) -> None:
        t = make_transcript([self.KO_HEDGED])
        ko = HedgingRate().compute(t, MetricContext(locale="ko"))
        en = HedgingRate().compute(t, MetricContext(locale="en"))
        self.assertGreaterEqual(ko.value, 2.0)
        self.assertEqual(en.value, 0.0)

    def test_ko_context_flows_through_run_experiment(self) -> None:
        from derailment.report import run_experiment

        report = run_experiment("anxiety", seeds=(1,), locale="ko")
        self.assertEqual(report.ctx.locale, "ko")


if __name__ == "__main__":
    unittest.main()
