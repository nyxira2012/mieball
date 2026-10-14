"""轮换纯函数矩阵（2.8 §4.1 取队单一真值——前端 rotate.test.ts 的取人用例迁 Python）：
take_from_queue 的歇/连战/考勤/取满即停、autofill_idle 的补片与分边、_by_tenure 的
上场章序、以及 requeue_after_confirm 在新取队口径下的三条边（歇在场上/歇在队首/
连战在队里）。纯 dict 进出，不带 app 夹具；四件套的基本去留格局在 test_live_base 册。
"""

from __future__ import annotations

from app.services import live_rotation
from app.services.live_rotation import autofill_idle, take_from_queue


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
) -> dict:
    """喂行契约全键（live._rotation_rows 的形状）。"""
    return {
        "id": pid,
        "court_no": court_no,
        "court_side": side,
        "check": check,
        "skip": skip,
        "fire": fire,
        "court_mark": mark,
        "rating": rating,
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


# ---- take_from_queue：候场序取人（镜像 rotate.ts takeFromQueue） ----


def test_take_plain_queue_order_and_rewrites_queue_in_place():
    players = [row(i) for i in range(1, 6)]
    queue = [1, 2, 3, 4, 5]
    assert take_from_queue(players, queue, 4) == [1, 2, 3, 4]
    assert queue == [5]  # 原地重排为剩余序（同一个 list 对象）


def test_take_fire_first_up_to_n_rest_keep_order():
    players = [row(1), row(2), row(3, fire=True), row(4)]
    queue = [1, 2, 3, 4]
    assert take_from_queue(players, queue, 2) == [3, 1]  # 连战者排最前，再按队序
    assert queue == [2, 4]
    # fire 多于 n：按候场序只收前 n 个 fire，其余 fire 保位留队
    players = [row(1, fire=True), row(2), row(3, fire=True), row(4, fire=True)]
    queue = [1, 2, 3, 4]
    assert take_from_queue(players, queue, 2) == [1, 3]
    assert queue == [2, 4]


def test_take_fire_but_not_arrived_is_not_prioritized():
    players = [row(1, fire=True, check="absent"), row(2), row(3)]
    queue = [1, 2, 3]
    assert take_from_queue(players, queue, 2) == [2, 3]
    assert queue == [1]  # 不可发者保位留队


def test_take_skip_consumed_once_and_kept_in_place():
    players = [row(1, skip=1), row(2), row(3)]
    queue = [1, 2, 3]
    assert take_from_queue(players, queue, 2) == [2, 3]  # 坑由下一位顶
    assert by_id(players)[1]["skip"] == 0  # 轮到即消耗一次
    assert queue == [1]  # 保位：仍在队首，下次第一个轮到
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
    # 多一人就够：歇者坐取人窗口被跳过、坑由下位顶、skip 减一、保位（验收 2）
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
    # 最强+最弱 vs 二三（2.4 §4.5）
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


# ---- _by_tenure：上场章序（小=先上=先下；None=最新并列保序） ----


def test_by_tenure_mark_ascending_none_last_stable():
    players = [row(1, mark=5), row(2), row(3, mark=2), row(4)]
    assert [p["id"] for p in live_rotation._by_tenure(players)] == [3, 1, 2, 4]


# ---- requeue_after_confirm 在新取队口径下的三条边 ----


def test_requeue_all_mode_on_court_skipper_sits_out_and_keeps_head():
    """验收 1 的纯函数面：在打的人设了歇 → 结算全下 → 补位轮到他跳过、skip 减一、
    保位在队首（下一场第一个轮到）；坑由下位顶（供给不足留空）。"""
    players = [
        row(1, court_no=1, side="a", mark=1),
        row(2, court_no=1, side="a", mark=1),
        row(3, court_no=1, side="b", mark=1, skip=1),
        row(4, court_no=1, side="b", mark=1),
    ]
    queue: list[int] = []
    live_rotation.requeue_after_confirm(players, 1, "a", RULES_Q, queue)
    assert side_ids(players, 1, "a") == [1, 2] and side_ids(players, 1, "b") == [4]
    assert queue == [3] and by_id(players)[3]["skip"] == 0


def test_requeue_n2_skipper_at_head_skipped_once_per_settle():
    """N 下模式 N 个坑一次取齐：队首歇者只被跳过一次、保位——不会被第一坑跳过后
    紧接着被第二坑捞上场。"""
    players = [
        row(1, court_no=1, side="a", mark=1),
        row(2, court_no=1, side="a", mark=2),
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
    # 上场章最小的 1、2 下（都在 a 边），6、7 顶坑；5 跳过一次保位队首
    assert side_ids(players, 1, "a") == [6, 7] and side_ids(players, 1, "b") == [3, 4]
    assert queue == [5, 1, 2] and by_id(players)[5]["skip"] == 0


def test_requeue_loser_mode_fire_in_queue_taken_first():
    players = [
        row(1, court_no=1, side="a"),
        row(2, court_no=1, side="a"),
        row(3, court_no=1, side="b"),
        row(4, court_no=1, side="b"),
        row(5),
        row(6, fire=True),
        row(7),
    ]
    queue = [5, 7, 6]
    live_rotation.requeue_after_confirm(
        players, 1, "a", RULES_Q | {"down": "loser"}, queue
    )
    # 败方下、候场补空边：连战者越过 7 先收，其后按队序取 5；7 保位
    assert side_ids(players, 1, "b") == [5, 6]
    assert queue == [7, 3, 4]
