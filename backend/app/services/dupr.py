"""DUPR 引擎 —— 战力核心轨的口径常量与纯函数（零 ORM）。

复刻声明：DUPR 官方公式不公开，此处采纳其统计口径——队伍均值 / 分差权重 /
滚动窗口 / 可信度门槛 / 一场出道，底层为 Elo 变体。后端单一真值：前端纯展示，
无镜像算法。快照重放模型：明细行存储结算时的四人分数快照，当前分数 = 起步分 +
历史明细逐场重放，两边天然一致。

规则版本约束：修改任何影响算分结果的常量或公式，必须同步换新的 RULES_VERSION；
版本记号随明细落库，作为事后追溯依据。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

# 无档案标准起步分：新账号与访客代位统一从 2.5 起步，未定级阶段使用较高 K 值快速归位
GUEST_DUPR = 2.5
# 期望压缩尺度：分差 1.0 档 ≈ 76:24、分差 2.0 档 ≈ 91:9
SPREAD = 2.0
# K 双速：未定级快（迅速归位）、已定级慢而稳
K_PROVISIONAL = 0.25
K_RATED = 0.10
# 滚动窗口（最近 30 场）与定级门槛（满 5 场定级）
WINDOW = 30
RATED_GAMES = 5
# 量表极值：2.0–8.0，保留三位小数
FLOOR = 2.0
CEILING = 8.0
# 算法口径版本号：任何影响算分结果的改动必须递增新号，随 DuprDetail.rule_version 落库
RULES_VERSION = "v1"


def expectation(team_own: float, team_opp: float) -> float:
    """期望胜率：队伍分 = 两人均值，E = 1/(1+10^((R_opp−R_own)/SPREAD))。"""
    return 1 / (1 + 10 ** ((team_opp - team_own) / SPREAD))


def margin_weight(score_w: int, score_l: int) -> float:
    """分差权重：11:2 与 11:9 对分数影响不同——w = 0.7 + 0.6×margin/score_w
    （score_w=胜方分即目标分；margin/score_w 恒 ≤1，clamp 是纯防御。0:0 平分
    也能确认（胜方任选），分母兜 1 落最轻权重）。"""
    return min(1.3, max(0.7, 0.7 + 0.6 * (score_w - score_l) / max(score_w, 1)))


def delta(e: float, weight: float, *, won: bool, provisional: bool) -> float:
    """单场增量：胜 +K·w·(1−E)、负 −K·w·E；K 取未定级/已定级双速。"""
    k = K_PROVISIONAL if provisional else K_RATED
    return k * weight * (1 - e) if won else -(k * weight * e)


def replay(start: float, details: Iterable[Mapping]) -> float:
    """起步分 + 明细逐场重放（快照重放模型）：每步行内快照算期望/权重，
    K 按重放场序取双速（前 RATED_GAMES−1 场未定级速），每步 round 3 位 +
    clamp [FLOOR, CEILING]。纯函数，重放天然幂等。"""
    rating = start
    for idx, d in enumerate(details):
        e = expectation(
            (rating + d["partner_rating"]) / 2, (d["opp_a"] + d["opp_b"]) / 2
        )
        step = delta(
            e,
            margin_weight(d["score_w"], d["score_l"]),
            won=d["won"],
            provisional=idx < RATED_GAMES - 1,
        )
        rating = min(CEILING, max(FLOOR, round(rating + step, 3)))
    return rating
