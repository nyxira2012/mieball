"""live_rotation —— 现场轮换纯逻辑：取队、分边、空片补满、确认后的人员回流。
谁能上场、如何分边全站统一由此定义。

纯 dict/list 进出、原地更新，不依赖 sqlalchemy 与 web 框架（便于独立单测；
输入输出通过 LiveBook 的 _rotation_rows / _apply_rotation 转换）。

喂行契约（每行 dict 的键）：id / court_no / court_side / check / skip / fire /
court_mark / rating。缺键按最保守值参与（check 缺=不可发、skip 缺=0、fire 缺=False、
court_mark 缺=最新资历、rating 缺=访客分）——LiveBook 恒带全键，缺省只是防御。

本模块只管人的去留与去向：比分、片行状态/场次号/分制快照由调用方落
（autofill_idle 只在片 dict 上翻 status 供自身查重与返回值）。
"""

from __future__ import annotations

from .dupr import GUEST_DUPR

# 算到场口径：absent 未到 / left 早退不算在场。本模块为纯逻辑层，不依赖数据库模型；live/live_sweep 从这里取
ARRIVED = ("ok", "late", "join")


def _arrived(p: dict | None) -> bool:
    return p is not None and p.get("check") in ARRIVED


def _issuable(p: dict | None) -> bool:
    """可发判定：到场且不在歇轮状态，作为补片前人数是否充足的判定依据。"""
    return _arrived(p) and not p.get("skip")


def _tenure_key(p: dict) -> tuple[bool, int]:
    mark = p.get("court_mark")
    return (mark is None, mark if mark is not None else 0)


def _by_tenure(players: list[dict]) -> list[dict]:
    """资历序（上场最久者优先下场）：上场章 court_mark 升序——先上的先下；没章的行
    （存量/从未落位）视为最新排最后，彼此并列保持传入序（sorted 稳定）。"""
    return sorted(players, key=_tenure_key)


def snake_pick(players: list[dict], n: int) -> list[list[dict]]:
    """按 DUPR 蛇形均衡分 n 队：rating 降序（同分按传入序）、蛇形轮发 1..n, n..1，
    最强+最弱 vs 二三，避免强手扎堆。缺 rating 键按访客分兜底。"""
    if n < 1:
        return []
    ranked = sorted(players, key=lambda p: -p.get("rating", GUEST_DUPR))
    teams: list[list[dict]] = [[] for _ in range(n)]
    # 蛇形取牌序：第 1 轮 0,1,..,n-1、第 2 轮反转 n-1,..,0，按 2n 一循环
    lap = list(range(n)) + list(range(n - 1, -1, -1))
    for i, p in enumerate(ranked):
        teams[lap[i % len(lap)]].append(p)
    return teams


def take_from_queue(players: list[dict], queue: list[int], n: int) -> list[int]:
    """队首取 n 人发牌：连战（fire）优先收——候场序内到场的 fire 者先取、最多 n 个；
    其余按队序扫描：轮到歇轮者（skip>0）跳过这一轮并消耗一次（原地写回 skip-1）、坑由下一位顶、
    跳过者保位留队；不可发者（check 不在 ARRIVED）保位留队不动；取满即停——没被轮到的歇轮不消耗。
    queue 原地重排为剩余序（取走的人出队、其余相对序不变）。
    返回取走的 id（fire 者在前、余按队序）；n<=0 空手不动队。"""
    if n <= 0:
        return []
    by_id = {p["id"]: p for p in players}

    def ok(pid: int) -> dict | None:
        p = by_id.get(pid)
        return p if _arrived(p) else None

    pre = [pid for pid in queue if (p := ok(pid)) is not None and p.get("fire")][:n]
    pre_set = set(pre)
    taken = list(pre)
    kept: list[int] = []
    for pid in queue:
        if pid in pre_set:
            continue
        if len(taken) < n:
            p = ok(pid)
            if p is not None and not p.get("skip"):
                taken.append(pid)
                continue
            if p is not None:
                p["skip"] = p.get("skip", 0) - 1  # 轮到发牌给他：跳过这一轮、消耗一次
        kept.append(pid)  # 让位者/不可发者/余额：保位留在队里
    queue[:] = kept
    return taken


def _split_sides(
    players: list[dict], ids: list[int], pairing: str | None
) -> tuple[list[int], list[int]]:
    """全新一队分边：balance 走 snake_pick（最强+最弱 vs 二三，同分按队序先后）；
    queue 按队序对半——第 1、2 位一队、第 3、4 位一队（供给不足奇数时前边多一）。
    上场永远队序，均衡只管分边不越序挑人。"""
    if pairing == "balance":
        by_id = {p["id"]: p for p in players}
        side_a, side_b = snake_pick([by_id[i] for i in ids], 2)
        return [p["id"] for p in side_a], [p["id"] for p in side_b]
    half = (len(ids) + 1) // 2
    return ids[:half], ids[half:]


def _deal_fresh(
    players: list[dict], queue: list[int], court_no: int, size: int, pairing: str | None
) -> list[int]:
    """从候场队取一整片全新一队落到 court_no（取队 → 分边 → 落位，原地改行）：
    结算全上全下重发与空片补满共用。供给不足取多少落多少——结算路坑位留空
    （下多少补多少），补片路由调用方先判够人。返回取走的 id。"""
    ids = take_from_queue(players, queue, size)
    side_a, side_b = _split_sides(players, ids, pairing)
    by_id = {p["id"]: p for p in players}
    for side, members in (("a", side_a), ("b", side_b)):
        for pid in members:
            by_id[pid]["court_no"] = court_no
            by_id[pid]["court_side"] = side
    return ids


def autofill_idle(
    players: list[dict], courts: list[dict], rules: dict, queue: list[int]
) -> list[int]:
    """空片补满：按片号先后把所有 status=idle 的片补满——多片同时要人时候场队按片号序供给；
    每片 size 吃 rules.doubles 当前值（双打 4 / 单打 2；在打片照旧打完、新开片按新规）。
    候场里可发人数（到场且不在歇轮）不够一片的留空、不动队列（歇不消耗）。
    原地落行 court_no/court_side、片 dict 翻 status=playing；返回补开的片号
    （供审计与片行落账）。
    courts: [{court_no, status}, ...]——含还没开过行的片（调用方按 courts_count 补占位）。"""
    size = 2 if not rules.get("doubles", True) else 4
    by_id = {p["id"]: p for p in players}
    opened: list[int] = []
    for court in sorted(courts, key=lambda c: c["court_no"]):
        if court.get("status") != "idle":
            continue
        if sum(1 for pid in queue if _issuable(by_id.get(pid))) < size:
            continue
        _deal_fresh(players, queue, court["court_no"], size, rules.get("pairing"))
        court["status"] = "playing"
        opened.append(court["court_no"])
    return opened


def requeue_after_confirm(
    players: list[dict],
    court_no: int,
    winner_side: str,
    rules: dict,
    queue: list,
) -> None:
    """确认结束后的该片人员回流与补位：原地更新，只动该片。

    players: 全场名册行（喂行契约全键）；只改 court_no 片上行与 queue。
    queue:   候场 id 列表（队首在前）——下场者按资历序入队尾、补位者走 take_from_queue
             （歇/连战/考勤同口径）；队列序回写 queue_pos 由调用方（LiveBook）负责。
    rules:   {"down": all|loser|n1|n2|n3, "pairing": queue|balance, "doubles": bool}
    winner_side: "a"|"b"。
    供给不足时坑位留空（下多少人补多少人），不重复补、不越序挑人。"""
    oncourt = [
        p
        for p in players
        if p.get("court_no") == court_no and p.get("court_side") in ("a", "b")
    ]
    losers = [p for p in oncourt if p["court_side"] != winner_side]
    size = 2 if not rules.get("doubles", True) else 4

    def to_tail(group: list[dict]) -> None:
        for p in _by_tenure(group):  # 先下的排前面（沿 endMatch：资历久的先下）
            p["court_no"] = None
            p["court_side"] = None
            queue.append(p["id"])

    def place(player_id, side: str) -> None:
        row = next(p for p in players if p["id"] == player_id)
        row["court_no"] = court_no
        row["court_side"] = side

    if rules.get("down") == "loser":
        # 输家下：败方回队尾、胜者留场，候场首补空边成一队挑战（不重配）
        to_tail(losers)
        for player_id in take_from_queue(players, queue, len(losers)):
            place(player_id, "a" if winner_side == "b" else "b")
        return

    if rules.get("down") not in ("n1", "n2", "n3"):
        # 全上全下（含连庄到点等整片重发）：全场下、按"怎么配"凑全新一队
        to_tail(oncourt)
        _deal_fresh(players, queue, court_no, size, rules.get("pairing"))
        return

    # n1/n2/n3：资历最久的 N 人下，候场首顶坑（谁下补谁的坑，留下的保住半边）
    n = int(rules["down"][1])
    downs = _by_tenure(oncourt)[:n]
    sides = [d["court_side"] for d in downs]
    for down in downs:
        down["court_no"] = None
        down["court_side"] = None
        queue.append(down["id"])
    # N 个坑一次取齐而不是逐坑取 1：歇轮者「跳过这一轮」以这次结算为一轮——逐坑取
    # 会让队首歇者被第一坑跳过消耗后、紧接着被第二坑捞上场
    for player_id, side in zip(take_from_queue(players, queue, len(downs)), sides):
        place(player_id, side)
