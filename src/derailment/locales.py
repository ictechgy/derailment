"""Locale lexicons: multilingual measurement vocabulary.

Each locale provides the affect/behavior word sets the instruments and
sampling layers consume, plus hedge/recheck patterns. English reuses the
canonical lists; ko/zh/ja are heuristic stem/substring sets — CJK
languages have no reliable word boundaries, so entries are matched as
substrings and written to minimize false positives (infllected forms are
covered by matching the stem).

Limitations (documented, not hidden): these are rough heuristic
vocabularies, not validated instruments; negation ("not happy") is not
understood; and the offline PseudoModel speaks English only — locale
effects on sampling layers are visible on real models.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .metrics.lexicons import (
    FIXATION_WORDS,
    HEDGE_PATTERNS,
    HOSTILE_WORDS,
    ILLNESS_WORDS,
    NEGATIVE_WORDS,
    PANIC_WORDS,
    POSITIVE_WORDS,
    RECHECK_PATTERNS,
    REWARD_WORDS,
    URGE_WORDS,
    WORRY_WORDS,
)


@dataclass(frozen=True)
class LocaleLexicon:
    code: str
    name: str
    cjk: bool  # substring counting instead of word boundaries
    positive: frozenset[str]
    negative: frozenset[str]
    reward: frozenset[str]
    worry: frozenset[str]
    urge: frozenset[str]
    illness: frozenset[str]
    panic: frozenset[str]
    fixation: frozenset[str]
    hostile: frozenset[str]
    hedges: tuple[re.Pattern[str], ...]
    rechecks: tuple[re.Pattern[str], ...]

    def count(self, text: str, words: frozenset[str]) -> int:
        """Total hits for a word set: word-boundary counting for English,
        substring counting for CJK locales."""
        if self.cjk:
            return sum(1 for w in words if w in text)
        low = text.lower()
        total = 0
        for w in words:
            total += len(re.findall(rf"\b{re.escape(w)}\b", low))
        return total

    def any_hit(self, text: str, words: frozenset[str]) -> bool:
        return self.count(text, words) > 0


def _cjk_patterns(items: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(re.escape(i)) for i in items)


_EN = LocaleLexicon(
    code="en",
    name="English",
    cjk=False,
    positive=POSITIVE_WORDS,
    negative=NEGATIVE_WORDS,
    reward=REWARD_WORDS,
    worry=WORRY_WORDS,
    urge=URGE_WORDS,
    illness=ILLNESS_WORDS,
    panic=PANIC_WORDS,
    fixation=FIXATION_WORDS,
    hostile=HOSTILE_WORDS,
    hedges=HEDGE_PATTERNS,
    rechecks=RECHECK_PATTERNS,
)

_KO = LocaleLexicon(
    code="ko",
    name="한국어",
    cjk=True,
    positive=frozenset(
        """좋다 좋아 좋은 기쁘다 기쁜 기뻐 행복 행복한 만족 만족스럽 훌륭
        훌륭한 멋진 잘된 잘했 잘해 성공 성공적 유용 유익 도움 도움이 안전
        안전한 안심 편안 편안한 밝은 희망 희망이 낙관적 자신감 감사 감사한
        고마움 기대 기대되 사랑 사랑스러 즐겁다 즐거운 안정적 개선 개선됐
        개선되 웃음 웃었 환영 최고 가치 보람 알찬 든든 반가운 상쾌 깔끔
        완벽 완성 풍부 탄탄 신뢰 추천 통과 해결 해결됐 순조 원만 성실
        친절 상냥 따뜻 응원 잘하""".split()
    ),
    negative=frozenset(
        """나쁘다 나쁜 나빠 최악 싫다 싫은 싫어 슬프다 슬픈 슬퍼 우울
        우울한 불안 불안한 불안감 걱정 걱정돼 두렵 두려워 무서 위험
        위험한 실패 실망 실망스러 짜증 짜증나 화남
        분노 스트레스 답답 답답한 막막 절망 절망적 좌절 초조 조급 혼란
        혼란스러 문제 오류 버그 늦어 늦었 지연 지연돼
        어렵다 어려운 어려움 힘들 힘든 지치 지쳤 소진 과부하 붕괴 무너
        망가 고장 중단 차단 손실 손상 감소 하락 저하 악화 악화됐 부정적
        비관 냉소 무시 소외 고립 외롭 외로 공허 허탈 억눌 갈등 불신
        서운 후회 창피 죄책 아쉬 지루 따분 무기력 무력 정체됐 막혔
        막혀 끊김 깨졌 잃어 못하겠 못했다 안돼""".split()
    ),
    reward=frozenset(
        """기쁘 뿌듯 보람 즐거 자랑 자신감 의욕 열정 기대 성취
        성취감 흥미 재미 신나 만족 행복 동기부여""".split()
    ),
    worry=frozenset("걱정 불안 초조 두려 긴장 조마조마 불안감".split()),
    # phrases stay phrases: .split() previously shattered '다시 하고' into
    # the function words '하고'/'다시' which substring-match almost any
    # Korean sentence (P2-19)
    urge=frozenset(("충동", "갈망", "유혹", "다시 하고", "다시 받고", "참고 싶")),
    illness=frozenset(
        "증상 심각 병원 진료 검진 질병 질환 악화 통증 어지러 두근거".split()
    ),
    panic=frozenset("심장 두근 숨막 숨이 질식 공황 닥친 갑자기 아찔".split()),
    fixation=frozenset(
        ("계속", "자꾸", "밟혀", "생각나", "떠오르", "끊임없", "그 사람", "그 팀원")
    ),
    hostile=frozenset(
        "겨냥 조종 감시 노리고 계획된 의도된 음모 손보 노린".split()
    ),
    hedges=_cjk_patterns(
        ("다만", "그런데", "조심", "신중", "위험할 수", "안 될 수도", "못할 수도",
         "경우에 따라", "유의", "만약", "혹시", "최악의 경우", "실패할 수")
    ),
    rechecks=_cjk_patterns(
        ("다시 확인", "한 번 더", "재확인", "다시 검토", "확인하고 왔", "다시 살펴")
    ),
)

_ZH = LocaleLexicon(
    code="zh",
    name="中文",
    cjk=True,
    positive=frozenset(
        """很好 真好 太好 挺好 更好 最好 不错 棒 优秀 开心 高兴 快乐 满意
        出色 成功 有用 有帮助 安全 放心 希望 乐观 自信 感谢 喜欢 顺利
        清晰 改善 稳定 期待 完美 支持 鼓励 舒服 踏实 顺心 值得 周到
        高效 温暖 融洽 表扬 称赞 庆祝 进步 收获 美好 极佳 愉悦""".split()
    ),
    negative=frozenset(
        """坏 太坏 最坏 差劲 失败 失望 焦虑 担心 害怕 恐惧 危险 难受
        痛苦 沮丧 绝望 挫折 烦躁 愤怒 生气 压力 疲惫 疲劳 困难 困惑
        混乱 错误 出错 问题 延迟 崩溃 更糟 恶化 阴郁 悲观 无望 麻木
        空虚 卡住 卡死 阻塞 超时 延误 损失 受损 报错 不行 不佳 无聊
        冷淡 孤独 憋屈 委屈 后悔 尴尬 羞愧 内疚 抱歉 遗憾 无力 僵住
        停滞 卡顿""".split()
    ),
    reward=frozenset(
        "开心 快乐 自豪 成就感 动力 热情 期待 奖励 满足 兴奋 愉悦".split()
    ),
    worry=frozenset("担心 焦虑 紧张 不安 忐忑 揪心".split()),
    urge=frozenset("冲动 渴望 忍不住 再来一次 诱惑 又想".split()),
    illness=frozenset("症状 异常 严重 医院 检查 疾病 恶化 信号".split()),
    panic=frozenset("心跳 加速 呼吸 窒息 恐慌 崩溃 突然 最糟".split()),
    fixation=frozenset("总是 反复 挥之不去 念念不忘 盯着 又想起".split()),
    hostile=frozenset("针对 监视 蓄谋 指使 故意 联手 冲着我".split()),
    hedges=_cjk_patterns(
        ("不过", "小心", "注意", "可能出问题", "取决于", "最坏情况", "有风险", "慎重", "提醒")
    ),
    rechecks=_cjk_patterns(("再检查", "再确认", "让我再", "再看一遍", "复查")),
)

_JA = LocaleLexicon(
    code="ja",
    name="日本語",
    cjk=True,
    positive=frozenset(
        """良い いいですね すばらしい 素晴らしい 嬉しい 楽しい 満足 成功
        役立つ 助かる 安全 安心 希望 楽観的 自信 感謝 好き 円滑 明確
        改善 安定 期待 完璧 応援 快適 踏実 順調 信頼 おすすめ 進歩
        収穫 温かい さわやか""".split()
    ),
    negative=frozenset(
        """悪い 最悪 失敗 失望 不安 心配 恐れ 危険 つらい 苦しい 落ち込み
        絶望 挫折 イライラ 怒り ストレス 疲れ 困難 混乱 エラー 問題
        遅れ 崩壊 悪化 悲観的 無理 つまず 止まっ 壊れ バグ 遅延 損失
        減少 低下 空虚 麻痺 孤独 淋し 寂し 後悔 恥ずか 罪悪 退屈
        無気力 無力 行き詰 詰まっ""".split()
    ),
    reward=frozenset(
        "嬉しい 楽しい 誇り 達成感 やる気 情熱 期待 ご褒美 満足 ワクワク".split()
    ),
    worry=frozenset("心配 不安 緊張 落ち着かない 気になって ドキドキ".split()),
    urge=frozenset("衝動 欲望 たまらない 誘惑 我慢 またやって".split()),
    illness=frozenset("症状 異常 重い 病院 診察 検査 病気 悪化 痛み めまい".split()),
    panic=frozenset("心臓 ドキドキ 息が 苦しい パニック 最悪 襲わ 突然".split()),
    fixation=frozenset("ずっと つきまとう 気になって 何度も よぎっ あの人".split()),
    hostile=frozenset("狙わ 監視 仕組ま 企て 故意に 集団で 私を向い".split()),
    hedges=_cjk_patterns(
        ("ただし", "注意", "リスク", "最悪の場合", "状況によ", "慎重", "念のため", "かもしれ")
    ),
    rechecks=_cjk_patterns(("再確認", "もう一度確認", "確認し直", "見直し", "チェックし直")),
)

LOCALES: dict[str, LocaleLexicon] = {
    "en": _EN,
    "ko": _KO,
    "zh": _ZH,
    "ja": _JA,
}


def get_lexicon(code: str) -> LocaleLexicon:
    try:
        return LOCALES[code]
    except KeyError:
        known = ", ".join(sorted(LOCALES))
        raise KeyError(
            f"unknown locale '{code}' (known: {known})"
        ) from None
