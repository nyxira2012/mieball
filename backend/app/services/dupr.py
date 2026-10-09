"""DUPR 引擎 —— 战力核心轨的口径常量与纯函数（1.4 §2，零 ORM）。

复刻声明（规格 §2）：DUPR 公式不开源，这里采纳其**口径**而非公式——队伍均值 /
分差权重 / 滚动窗口 / 可信度门槛 / 一场出道，底层是 Elo 变体。后端单一源：
前端纯展示，无 elo.ts 式双端镜像。快照重放模型：明细行存结算时的四人分数快照，
在线落分 = 起步分 + 此前明细逐场重放，两边天然一致。

硬规矩（6.1 §4.4）：改任何影响算分结果的常量/公式，必须同步换新的
RULES_VERSION——版本记号随明细落库，是事后分辨"这行分是哪套规矩算的"的唯一依据。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

# 无档案标准分（1.4 §4+§5 修订：访客代位与新号起步同源 2.5——自评五档废除后
# 唯一起步锚，未定级快涨 K 把人迅速拉回真实水平）
GUEST_DUPR = 2.5
# 期望压缩尺度：差 1.0 档 ≈ 76:24、差 2.0 档 ≈ 91:9（对应 Elo 400 差体感）
SPREAD = 2.0
# K 双速：未定级快（迅速归位）、已定级慢而稳
K_PROVISIONAL = 0.25
K_RATED = 0.10
# 滚动窗口与定级门槛（1.4 裁决 5：窗口 30 场、满 5 场定级两态）
WINDOW = 30
RATED_GAMES = 5
# 量表极值（1.4 §2：2.0–8.0 三位小数）
FLOOR = 2.0
CEILING = 8.0
# 口径版本记号（6.1 §4.4）：本文件任何影响算分结果的常量/公式改动必换新号
# （"v1"→"v2"…），随 DuprDetail.rule_version 落库；只进库不出口（球友界面不显示）
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
