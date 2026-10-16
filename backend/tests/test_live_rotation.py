"""轮换纯函数矩阵（2.9 §4 排位四档/抓人/谁下五式/连打上限/池子兜底/配对四档的
纯函数面；2.8 §4.1 取队单一真值的旧用例随迁）：take_from_queue 的排位取人、
歇轮消耗保位、连战兑现清除、连打归零，rank_key 的五段典序与越界护栏，
requeue_after_confirm 的五式（小尺子/上限整片全下/合池兜底/重分边），
_split_sides 四档与防复读交替。纯 dict 进出，不带 app 夹具；四件套的基本
去留格局在 test_live_base 册。排位键口径由测试自备：本片场上人的 streak 已 +1、
wait_batch 已盖新章（接线层 live.py 的职责在集成测试里过）。
"""

from __future__ import annotations

import pytest

from app.services import live_rotation
from app.services.live_rotation import autofill_idle, rank_key, take_from_queue


def row(
    pid: int,
    *,
    check: str = "ok",
    skip: int = 0,
    fire: bool = False,
    court_no: int | None = None,
    side: str | None = None,
    mark: int | None = None,
    rating: float = 2.5,
    streak: int = 0,
    wait: int = 0,
    tonight: int = 0,
    seq: int = 0,
) -> dict:
    """喂行契约全键（live._rotation_rows 的形状；排位四键 streak/wait_batch/
    tonight/roster_seq 对应行内键 streak/wait/tonight/seq）。"""
    return {
        "id": pid,
        "court_no": court_no,
        "court_side": side,
        "check": check,
        "skip": skip,
        "fire": fire,
        "court_mark": mark,
        "rating": rating,
        "streak": streak,
        "wait_batch": wait,
        "tonight": tonight,
        "roster_seq": seq,
    }


def by_id(players: list[dict]) -> dict[int, dict]:
    return {p["id"]: p for p in players}


def side_ids(players: list[dict], court_no: int, side: str) -> list[int]:
    return [
        p["id"]
        for p in players
        if p["court_no"] == court_no and p["court_side"] == side
    ]


RULES_Q = {"down": "all", "pairing": "queue", "doubles": True}
RULES_B = {"down": "all", "pairing": "balance", "doubles": True}


# ---- rank_key：五段典序（2.9 §4.1 四档 + 数学护栏） ----


def test_rank_key_tiers_dominance_and_each_decides():
    # 上档压过下段全部之和：连打 0 且下段全满 仍先于 连打 1 且下段全空
    low = rank_key(row(1, streak=0, wait=99, tonight=99, seq=99))
    high = rank_key(row(2, streak=1, wait=0, tonight=0, seq=0))
    assert low < high
    # ② 等待批次：章小=等得久=先上（刚退下来的章最新、排在所有场下候场者之后）
    assert rank_key(row(1, wait=2)) < rank_key(row(2, wait=5))
    # ③ 今晚场次：少的人排前面
    assert rank_key(row(1, wait=3, tonight=4)) > rank_key(row(2, wait=3, tonight=2))
    # ④ 连战：前三项平手才有发言权
    assert rank_key(row(1, wait=3, tonight=2, fire=True)) < rank_key(
        row(2, wait=3, tonight=2)
    )
    # ⑤ 到场先后：名册序号小的在前
    assert rank_key(row(1, wait=3, tonight=2, seq=10)) > rank_key(
        row(2, wait=3, tonight=2, seq=3)
    )


def test_rank_key_overflow_guard_each_segment():
    # 任一段 >99 抛 RotationOverflow（发牌路径据此暂停该片，主操作不连坐）
    for kwargs in ({"streak": 100}, {"wait": 100}, {"tonight": 100}, {"seq": 100}):
        with pytest.raises(live_rotation.RotationOverflow):
            rank_key(row(1, **kwargs))
    # 99 在界内不抛
    assert rank_key(row(1, streak=99, wait=99, tonight=99, seq=99)) > rank_key(row(2))


def test_take_raises_when_candidate_overflows():
    players = [row(1, tonight=100), row(2)]
    with pytest.raises(live_rotation.RotationOverflow):
        take_from_queue(players, [1, 2], 1)


# ---- take_from_queue：按排位取人（2.9 §4.2 抓人） ----


def test_take_plain_queue_order_and_rewrites_queue_in_place():
    players = [row(i) for i in range(1, 6)]
    queue = [1, 2, 3, 4, 5]
    assert take_from_queue(players, queue, 4) == [1, 2, 3, 4]
    assert queue == [5]  # 原地重排为剩余序（同一个 list 对象）


def test_take_ranks_streak_wait_tonight_fire_seq():
    # 连打 0 的候场者压过连打 1 的刚退者（同批章也压不过连打档）
    players = [row(1, streak=1, wait=0), row(2, streak=0, wait=99)]
    assert take_from_queue(players, [1, 2], 1) == [2]
    # 连打平了比等待批次：等得久（章小）的先上
    players = [row(1, wait=5), row(2, wait=1)]
    assert take_from_queue(players, [1, 2], 1) == [2]
    # 批次平了比今晚场次：今晚少先上
    players = [row(1, wait=3, tonight=2), row(2, wait=3, tonight=7)]
    assert take_from_queue(players, [1, 2], 1) == [1]


def test_take_fire_is_only_a_tiebreak_not_a_jump():
    # 连战不跨档插队：连打 1 的 fire 者排在场下休息者（连打 0）之后
    players = [row(1, streak=1, fire=True), row(2)]
    assert take_from_queue(players, [1, 2], 1) == [2]
    # 前三档全平：连战者先取、最多 n 个；其余按序
    players = [row(1), row(2), row(3, fire=True), row(4)]
    queue = [1, 2, 3, 4]
    assert take_from_queue(players, queue, 2) == [3, 1]
    assert queue == [2, 4]
    # fire 多于 n：只收前 n 个，其余 fire 保位留队
    players = [row(1, fire=True), row(2), row(3, fire=True), row(4, fire=True)]
    queue = [1, 2, 3, 4]
    assert take_from_queue(players, queue, 2) == [1, 3]
    assert queue == [2, 4]


def test_take_clears_fire_on_taken_keeps_fire_on_bench():
    players = [row(1, fire=True), row(2, fire=True), row(3), row(4, fire=True)]
    queue = [1, 2, 3, 4]
    assert take_from_queue(players, queue, 2) == [1, 2]
    assert by_id(players)[1]["fire"] is False  # 连战兑现：上场即清除
    assert by_id(players)[4]["fire"] is True  # 没上场的连战保留
    assert queue == [3, 4]


def test_take_zeroes_streak_of_those_left_on_bench():
    # 本轮没上=真正歇了：连打归零（被捞回续打的在 taken 里不清）
    players = [row(1, streak=2), row(2, streak=0), row(3, streak=1)]
    queue = [1, 2, 3]
    assert take_from_queue(players, queue, 1) == [2]
    assert by_id(players)[1]["streak"] == 0 and by_id(players)[3]["streak"] == 0


def test_take_fire_but_not_arrived_is_not_prioritized():
    players = [row(1, fire=True, check="absent"), row(2), row(3)]
    queue = [1, 2, 3]
    assert take_from_queue(players, queue, 2) == [2, 3]
    assert queue == [1]  # 不可发者保位留队


def test_take_skip_consumed_once_and_keeps_rank_position():
    players = [row(1, wait=1, skip=1), row(2, wait=5)]
    queue = [1, 2]
    assert take_from_queue(players, queue, 1) == [2]  # 排位轮到他：跳过、坑由下位顶
    assert by_id(players)[1]["skip"] == 0
    assert queue == [1]  # 保位：批次章没动，下次仍第一个轮到
    assert take_from_queue(players, queue, 1) == [1]
    # 可叠加：skip=2 只扣一
    players = [row(1, skip=2), row(2)]
    queue = [1, 2]
    assert take_from_queue(players, queue, 1) == [2]
    assert by_id(players)[1]["skip"] == 1


def test_take_stops_when_full_unreached_skip_not_consumed():
    players = [row(1), row(2), row(3, skip=1)]
    queue = [1, 2, 3]
    assert take_from_queue(players, queue, 2) == [1, 2]
    assert by_id(players)[3]["skip"] == 1  # 没轮到他，歇不消耗
    assert queue == [3]


def test_take_absent_left_and_unknown_kept_untouched():
    players = [row(1, check="absent", skip=1), row(2, check="left"), row(3), row(4)]
    queue = [1, 2, 99, 3, 4]  # 99 不在名册（防御：当不可发留队）
    assert take_from_queue(players, queue, 2) == [3, 4]
    assert queue == [1, 2, 99]
    assert by_id(players)[1]["skip"] == 1  # 不可发者的歇不消耗


def test_take_zero_or_short_supply():
    players = [row(1), row(2)]
    queue = [1, 2]
    assert take_from_queue(players, queue, 0) == []
    assert queue == [1, 2]
    assert take_from_queue(players, queue, 4) == [1, 2]  # 取多少有多少
    assert queue == []


# ---- autofill_idle：空片补满（镜像 fillAllCourts） ----


def test_autofill_fills_idle_courts_in_court_no_order():
    players = [row(i) for i in range(1, 9)]
    queue = list(range(1, 9))
    courts = [{"court_no": 2, "status": "idle"}, {"court_no": 1, "status": "idle"}]
    assert autofill_idle(players, courts, RULES_Q, queue) == [1, 2]
    assert side_ids(players, 1, "a") == [1, 2] and side_ids(players, 1, "b") == [3, 4]
    assert side_ids(players, 2, "a") == [5, 6] and side_ids(players, 2, "b") == [7, 8]
    assert queue == []
    assert all(c["status"] == "playing" for c in courts)


def test_autofill_short_supply_leaves_idle_and_queue_untouched():
    # 四人在队但一人歇着：可发只有 3，不够一片——不补、不动队、歇不消耗
    players = [row(1), row(2), row(3), row(4, skip=1)]
    queue = [1, 2, 3, 4]
    courts = [{"court_no": 1, "status": "idle"}]
    assert autofill_idle(players, courts, RULES_Q, queue) == []
    assert queue == [1, 2, 3, 4] and by_id(players)[4]["skip"] == 1
    assert courts[0]["status"] == "idle"
    assert all(p["court_no"] is None for p in players)
    # 多一人就够：歇者坐取人窗口被跳过、坑由下位顶、skip 减一、保位
    players.append(row(5))
    queue.append(5)
    assert autofill_idle(players, courts, RULES_Q, queue) == [1]
    assert side_ids(players, 1, "a") == [1, 2] and side_ids(players, 1, "b") == [3, 5]
    assert queue == [4] and by_id(players)[4]["skip"] == 0


def test_autofill_skips_playing_courts():
    players = [row(i) for i in range(1, 5)]
    queue = [1, 2, 3, 4]
    courts = [{"court_no": 1, "status": "playing"}, {"court_no": 2, "status": "idle"}]
    assert autofill_idle(players, courts, RULES_Q, queue) == [2]
    assert side_ids(players, 2, "a") == [1, 2]


def test_autofill_balance_pairing_snakes_by_rating():
    players = [
        row(1, rating=4.0),
        row(2, rating=3.0),
        row(3, rating=3.5),
        row(4, rating=2.0),
    ]
    queue = [1, 2, 3, 4]
    courts = [{"court_no": 1, "status": "idle"}]
    assert autofill_idle(players, courts, RULES_B, queue) == [1]
    # 最强+最弱 vs 二三（战力最接近的分法）
    assert side_ids(players, 1, "a") == [1, 4]
    assert side_ids(players, 1, "b") == [2, 3]


def test_autofill_singles_takes_two_per_court():
    players = [row(1), row(2), row(3)]
    queue = [1, 2, 3]
    courts = [{"court_no": 1, "status": "idle"}, {"court_no": 2, "status": "idle"}]
    rules = RULES_Q | {"doubles": False}
    assert autofill_idle(players, courts, rules, queue) == [1]  # 2 号片差一人留空
    assert side_ids(players, 1, "a") == [1] and side_ids(players, 1, "b") == [2]
    assert queue == [3]


def test_autofill_fire_first_then_queue_order():
    players = [row(1), row(2), row(3), row(4, fire=True), row(5)]
    queue = [1, 2, 3, 4, 5]
    courts = [{"court_no": 1, "status": "idle"}]
    assert autofill_idle(players, courts, RULES_Q, queue) == [1]
    # 取序 [4,1,2,3]：连战者与队首同边、2/3 一边（side_ids 按名册序列出）
    assert side_ids(players, 1, "a") == [1, 4] and side_ids(players, 1, "b") == [2, 3]
    assert queue == [5]


# ---- _by_tenure：上场章序（小=先上；None=最新并列保序） ----


def test_by_tenure_mark_ascending_none_last_stable():
    players = [row(1, mark=5), row(2), row(3, mark=2), row(4)]
    assert [p["id"] for p in live_rotation._by_tenure(players)] == [3, 1, 2, 4]


# ---- _split_sides：怎么配四档（2.9 §4.6） ----


def test_split_queue_mode_halves_by_take_order():
    players = [row(i) for i in range(1, 5)]
    assert live_rotation._split_sides(players, [1, 2, 3, 4], "queue") == (
        [1, 2],
        [3, 4],
    )


def test_split_balance_closest_and_anti_repeat_alternates():
    players = [
        row(1, rating=4.0),
        row(2, rating=3.0),
        row(3, rating=3.5),
        row(4, rating=2.0),
    ]
    ids = [1, 2, 3, 4]
    # 3 种分法按接近度：{1,4}|{2,3}=0.5 → {1,2}|{3,4}=1.5 → {1,3}|{2,4}=2.5（最差）
    a1, b1 = live_rotation._split_sides(players, ids, "balance")
    assert {frozenset(a1), frozenset(b1)} == {frozenset((1, 4)), frozenset((2, 3))}
    # 与这 4 人最近一次同场的分法相同 → 退取次接近，绝不取两强联手的 最差
    facts = {"last_split": {frozenset(ids): (a1, b1)}}
    a2, b2 = live_rotation._split_sides(players, ids, "balance", facts)
    assert {frozenset(a2), frozenset(b2)} == {frozenset((1, 2)), frozenset((3, 4))}
    # 上次已是次优 → 这次回到最优：最优/次优交替
    facts = {"last_split": {frozenset(ids): (a2, b2)}}
    a3, b3 = live_rotation._split_sides(players, ids, "balance", facts)
    assert {frozenset(a3), frozenset(b3)} == {frozenset((1, 4)), frozenset((2, 3))}


def test_split_partner_least_pairing_then_even_then_rating():
    players = [row(i) for i in range(1, 5)]
    ids = [1, 2, 3, 4]
    # 两对搭档今晚合作次数之和最少
    facts = {"pair_counts": {(1, 2): 3, (3, 4): 3, (1, 4): 1, (2, 3): 1}}
    a, b = live_rotation._split_sides(players, ids, "partner", facts)
    assert {frozenset(a), frozenset(b)} == {frozenset((1, 3)), frozenset((2, 4))}
    # 总和平（2=2）但分配不均：各搭过 1 次优先于 0+2
    facts = {
        "pair_counts": {
            (1, 2): 0,
            (3, 4): 2,
            (1, 3): 1,
            (2, 4): 1,
            (1, 4): 3,
            (2, 3): 3,
        }
    }
    a, b = live_rotation._split_sides(players, ids, "partner", facts)
    assert {frozenset(a), frozenset(b)} == {frozenset((1, 3)), frozenset((2, 4))}
    # 无搭档史：按战力最接近兜底
    players_r = [
        row(1, rating=4.0),
        row(2, rating=3.0),
        row(3, rating=3.5),
        row(4, rating=2.0),
    ]
    a, b = live_rotation._split_sides(players_r, ids, "partner")
    assert {frozenset(a), frozenset(b)} == {frozenset((1, 4)), frozenset((2, 3))}


def test_split_even_netwins_then_pairs_then_rating():
    players = [row(i) for i in range(1, 5)]
    ids = [1, 2, 3, 4]
    # 今晚赢多的带输多的：{1,2}|{3,4} 两边净胜 +1/+1（绝对值和 2）最小
    facts = {"net_wins": {1: 5, 2: -4, 3: 3, 4: -2}}
    a, b = live_rotation._split_sides(players, ids, "even", facts)
    assert {frozenset(a), frozenset(b)} == {frozenset((1, 2)), frozenset((3, 4))}
    # 胜负全平（开局前两轮）：先挑今晚搭档次数最少的
    facts = {
        "pair_counts": {
            (1, 2): 5,
            (3, 4): 5,
            (1, 4): 4,
            (2, 3): 4,
            (1, 3): 1,
            (2, 4): 1,
        }
    }
    a, b = live_rotation._split_sides(players, ids, "even", facts)
    assert {frozenset(a), frozenset(b)} == {frozenset((1, 3)), frozenset((2, 4))}
    # 再平手按战力最接近兜底
    players_r = [
        row(1, rating=4.0),
        row(2, rating=3.0),
        row(3, rating=3.5),
        row(4, rating=2.0),
    ]
    a, b = live_rotation._split_sides(players_r, ids, "even")
    assert {frozenset(a), frozenset(b)} == {frozenset((1, 4)), frozenset((2, 3))}


# ---- requeue_after_confirm：谁下五式（2.9 §4.3/§4.4/§4.5） ----


def test_requeue_all_mode_deals_fresh_by_rank():
    # 全上全下：整片进池按排位重发——场下等的人最先、刚下的按连打/今晚场次排
    players = [
        row(1, court_no=1, side="a", streak=3, wait=7, tonight=2),
        row(2, court_no=1, side="a", streak=1, wait=7, tonight=5),
        row(3, court_no=1, side="b", streak=1, wait=7, tonight=1),
        row(4, court_no=1, side="b", streak=2, wait=7, tonight=0),
        row(5, wait=2),
        row(6, wait=2),
    ]
    queue = [5, 6]
    live_rotation.requeue_after_confirm(players, 1, "a", RULES_Q, queue)
    # 池内排位：5,6(连打0) → 3(连打1今晚1) → 2(连打1今晚5) → 4(连打2) → 1(连打3)
    assert side_ids(players, 1, "a") == [5, 6] and side_ids(players, 1, "b") == [2, 3]
    assert queue == [1, 4]  # 余队保相对序；按排位重排队序归接线层的 queue_pos 落位
    assert by_id(players)[1]["streak"] == 0 and by_id(players)[4]["streak"] == 0


def test_requeue_all_mode_on_court_skipper_sits_out_and_keeps_head():
    """在打的人设了歇 → 结算全下 → 补位轮到他跳过、skip 减一、保位在队首
    （下一场第一个轮到）；坑由下位顶（供给不足留空）。"""
    players = [
        row(1, court_no=1, side="a", mark=1, wait=7),
        row(2, court_no=1, side="a", mark=1, wait=7),
        row(3, court_no=1, side="b", mark=1, skip=1, wait=7),
        row(4, court_no=1, side="b", mark=1, wait=7),
    ]
    queue: list[int] = []
    live_rotation.requeue_after_confirm(players, 1, "a", RULES_Q, queue)
    assert side_ids(players, 1, "a") == [1, 2] and side_ids(players, 1, "b") == [4]
    assert queue == [3] and by_id(players)[3]["skip"] == 0


def test_requeue_loser_mode_winners_stay_and_fill_by_rank():
    # 未达连打上限：赢家守擂原边、败方下场、按排位补挑战边成一队（不拆赢家）
    players = [
        row(1, court_no=1, side="a", streak=2, wait=7),
        row(2, court_no=1, side="a", streak=2, wait=7),
        row(3, court_no=1, side="b", streak=1, wait=7),
        row(4, court_no=1, side="b", streak=1, wait=7),
        row(5, wait=2),
        row(6, wait=3),
    ]
    queue = [5, 6]
    live_rotation.requeue_after_confirm(
        players, 1, "a", RULES_Q | {"down": "loser"}, queue, streak_max=3
    )
    assert side_ids(players, 1, "a") == [1, 2] and side_ids(players, 1, "b") == [5, 6]
    assert queue == [3, 4]
    # 0=不限（缺省不传同效）：连打再高也守擂
    players[0]["streak"] = players[1]["streak"] = 9
    queue = [5, 6]
    live_rotation.requeue_after_confirm(
        players, 1, "a", RULES_Q | {"down": "loser"}, queue
    )
    assert side_ids(players, 1, "a") == [1, 2]


def test_requeue_loser_mode_winners_at_streak_cap_all_down():
    # 赢家连打已达上限（输家下默认 3）：赢家不再守擂，整片全下按排位重发
    players = [
        row(1, court_no=1, side="a", streak=3, wait=7, tonight=2),
        row(2, court_no=1, side="a", streak=3, wait=7, tonight=2),
        row(3, court_no=1, side="b", streak=1, wait=7, tonight=1),
        row(4, court_no=1, side="b", streak=1, wait=7, tonight=0),
        row(5, wait=2),
        row(6, wait=2),
    ]
    queue = [5, 6]
    live_rotation.requeue_after_confirm(
        players, 1, "a", RULES_Q | {"down": "loser"}, queue, streak_max=3
    )
    # 全池排位：场下 5,6 最先，差两名额从刚下的里捞最不累的（连打1今晚少的 4、3）
    assert side_ids(players, 1, "a") == [5, 6] and side_ids(players, 1, "b") == [3, 4]
    assert queue == [1, 2]  # 赢家垫底去歇
    assert by_id(players)[1]["streak"] == 0


def test_requeue_n_ruler_most_streak_down_then_earlier_mark():
    # 小尺子只比两样：连打多的先下、连打平了上场早（章小）的先下——
    # 今晚场次与到场序不掺和（1 今晚 5 场但章最晚，不先下；2 今晚 9 场但章最早，先下）
    players = [
        row(1, court_no=1, side="a", streak=2, tonight=5, mark=5, wait=7),
        row(2, court_no=1, side="a", streak=2, tonight=9, mark=1, wait=7),
        row(3, court_no=1, side="b", streak=1, tonight=0, mark=3, wait=7),
        row(4, court_no=1, side="b", streak=1, tonight=0, mark=2, wait=7),
        row(5),
        row(6, wait=1),
    ]
    queue = [5, 6]
    live_rotation.requeue_after_confirm(
        players, 1, "a", RULES_Q | {"down": "n2"}, queue
    )
    # 尺子序 2(连2章1) 1(连2章5) → 下 2、1；留场的 3、4 保住半边，候场 5、6 顶坑
    assert side_ids(players, 1, "a") == [5, 6] and side_ids(players, 1, "b") == [3, 4]
    assert queue == [2, 1] and by_id(players)[2]["streak"] == 0


def test_requeue_n2_skipper_at_head_skipped_once_per_settle():
    """N 下模式 N 个坑一次取齐：排位最前的歇者只被跳过一次、保位——不会被第一坑
    跳过消耗后紧接着被第二坑捞上场。"""
    players = [
        row(1, court_no=1, side="a", mark=1, streak=1, wait=7),
        row(2, court_no=1, side="a", mark=2, streak=1, wait=7),
        row(3, court_no=1, side="b", mark=3),
        row(4, court_no=1, side="b", mark=4),
        row(5, skip=1),
        row(6),
        row(7),
    ]
    queue = [5, 6, 7]
    live_rotation.requeue_after_confirm(
        players, 1, "a", RULES_Q | {"down": "n2"}, queue
    )
    # 连打 1 的 1、2 下（都在 a 边）；场下连打 0 的 6、7 顶坑；5 跳过一次保位队首
    assert side_ids(players, 1, "a") == [6, 7] and side_ids(players, 1, "b") == [3, 4]
    assert queue == [5, 1, 2] and by_id(players)[5]["skip"] == 0


def test_requeue_n3_pool_backfill_leaves_last_ranked_on_bench():
    # 5 人 1 片选 3人下（人少池子兜底，不死锁）：差的名额从刚下的里捞最不累的
    # 回来续打，全池排位最靠后的（最累的 1）真正留在场下休息
    players = [
        row(1, court_no=1, side="a", streak=2, tonight=5, mark=1, wait=7),
        row(2, court_no=1, side="a", streak=1, tonight=4, mark=2, wait=7),
        row(3, court_no=1, side="b", streak=1, tonight=3, mark=3, wait=7),
        row(4, court_no=1, side="b", streak=0, tonight=0, mark=4, wait=7),
        row(5),
    ]
    queue = [5]
    live_rotation.requeue_after_confirm(
        players, 1, "a", RULES_Q | {"down": "n3"}, queue
    )
    # 尺子下三人 1、2、3、留 4 守场；合池排位 5(连0等最久) → 3(连1今晚3) → 2(连1今晚4)
    # → 补 3 人 [5,3,2]，1 留场下（连打归零）；被捞回的 2、3 连打不清（续打）
    assert side_ids(players, 1, "a") == [3, 5] and side_ids(players, 1, "b") == [2, 4]
    assert queue == [1] and by_id(players)[1]["streak"] == 0
    assert by_id(players)[2]["streak"] == 1 and by_id(players)[3]["streak"] == 1


def test_requeue_n2_nonqueue_pairing_resplits_whole_court():
    # 1/2/3人下选非队序档：补齐后整片 4 人重新分边（留下的人也换边，不顶坑）
    players = [
        row(1, court_no=1, side="a", streak=2, mark=1, wait=7, rating=4.0),
        row(2, court_no=1, side="a", streak=1, mark=2, wait=7, rating=3.0),
        row(3, court_no=1, side="b", streak=1, mark=3, wait=7, rating=3.5),
        row(4, court_no=1, side="b", streak=0, mark=4, wait=7, rating=2.0),
        row(5, rating=3.2),
        row(6, wait=1, rating=2.8),
    ]
    queue = [5, 6]
    live_rotation.requeue_after_confirm(
        players, 1, "a", RULES_B | {"down": "n2"}, queue
    )
    # 连打 2 的 1、连打 1 上场早的 2 下；场下 5、6 补齐后整片重分边：战力最接近
    # 的 {3,4}|{5,6}（留场的 3、4 也被重排，不再保原半边）
    assert side_ids(players, 1, "a") == [3, 4] and side_ids(players, 1, "b") == [5, 6]
    assert queue == [1, 2]


def test_requeue_loser_mode_fire_in_queue_taken_first():
    players = [
        row(1, court_no=1, side="a", wait=7),
        row(2, court_no=1, side="a", wait=7),
        row(3, court_no=1, side="b", wait=7),
        row(4, court_no=1, side="b", wait=7),
        row(5),
        row(6, fire=True),
        row(7),
    ]
    queue = [5, 7, 6]
    live_rotation.requeue_after_confirm(
        players, 1, "a", RULES_Q | {"down": "loser"}, queue
    )
    # 败方下、候场补空边：前三档全平时连战者先收，其后按排位取 5；7 保位
    assert side_ids(players, 1, "b") == [5, 6]
    assert queue == [7, 3, 4]
    assert by_id(players)[6]["fire"] is False  # 上场即兑现清除


def test_requeue_six_players_one_court_rotates_without_third_streak():
    """6 人 1 片、全上全下连结三场：歇过的人连打归零正常轮换，无人连打第 3 场
    （排位键口径由测试自备：结算时片上人 streak+1、统一盖新章）。"""
    players = [row(i) for i in range(1, 7)]
    for pid, side in ((1, "a"), (2, "a"), (3, "b"), (4, "b")):
        by_id(players)[pid].update(court_no=1, court_side=side)
    queue = [5, 6]

    def settle(winner: str, batch: int) -> set[int]:
        for p in players:
            if p.get("court_no") == 1:
                p["streak"] += 1
                p["wait"] = batch
        live_rotation.requeue_after_confirm(players, 1, winner, RULES_Q, queue)
        oncourt = {p["id"] for p in players if p["court_no"] == 1}
        assert all(p["streak"] < 3 for p in players)
        return oncourt

    assert settle("a", 1) == {5, 6, 1, 2}  # 场下的 5、6 先上，1、2 续打
    assert settle("a", 2) == {3, 4, 5, 6}  # 连打最重的 1、2 歇，连打清零
    assert settle("a", 3) == {1, 2, 3, 4}  # 轮回；全场每人歇过至少一轮
