"""live_rotation —— 现场轮换纯逻辑：排位、取队、分边、空片补满、确认后的人员回流。
谁能上场、如何分边全站统一由此定义。

纯 dict/list 进出、原地更新，不依赖 sqlalchemy 与 web 框架（便于独立单测；
输入输出通过 LiveBook 的 _rotation_rows / _apply_rotation 转换）。

喂行契约（每行 dict 的键）：id / court_no / court_side / check / skip / fire /
court_mark / rating / streak / wait_batch / tonight / roster_seq。缺键按最保守值参与
（check 缺=不可发、skip 缺=0、fire 缺=False、court_mark 缺=最新资历、rating 缺=访客分、
排位四键缺=0 即全并列按传入序）——LiveBook 恒带全键，缺省只是防御。

排位键的口径由接线层在调用前备好：本片场上人的 streak 已 +1（刚打完这场计入
连打）、tonight 已含这场、wait_batch 已盖本轮新章（对片上全员统一盖——留场者的
章是脏值无害，在场不算等待，下次离场时再盖新章）。

搭档史/净胜负/最近分法不由本模块算：调用方从战报预算成 facts dict 喂进来
（形状见 _split_sides），本模块零 ORM。

本模块只管人的去留与去向：比分、片行状态/场次号/分制快照由调用方落
（autofill_idle 只在片 dict 上翻 status 供自身查重与返回值）。
"""

from __future__ import annotations

from itertools import combinations

from .dupr import GUEST_DUPR

# 算到场口径：absent 未到 / left 早退不算在场。本模块为纯逻辑层，不依赖数据库模型；live/live_sweep 从这里取
ARRIVED = ("ok", "late", "join")


class RotationOverflow(Exception):
    """排位段超出两位（0~99）：极端长局的护栏。发牌路径据此暂停该片，
    签到/结算等主操作不连坐；纯函数层不碰 web 异常族，转用户可见错误归接线层。"""


def _arrived(p: dict | None) -> bool:
    return p is not None and p.get("check") in ARRIVED


def _issuable(p: dict | None) -> bool:
    """可发判定：到场且不在歇轮状态，作为补片前人数是否充足的判定依据。"""
    return _arrived(p) and not p.get("skip")


def _tenure_key(p: dict) -> tuple[bool, int]:
    mark = p.get("court_mark")
    return (mark is None, mark if mark is not None else 0)


def _by_tenure(players: list[dict]) -> list[dict]:
    """资历序（上场最久者优先下场）：上场章 court_mark 升序；没章的行
    （存量/从未落位）视为最新排最后，彼此并列保持传入序（sorted 稳定）。"""
    return sorted(players, key=_tenure_key)


def rank_key(row: dict) -> int:
    """排位分：五段各两位拼成一个整数，小者先上——连打少 → 等得久（批次章小）→
    今晚少 → 有连战 → 到场早。每段 0~99、前段 +1（位权 100）严格压过后面各段
    取满之和，绝不进位串格。任一段 >99 抛 RotationOverflow——只在发牌/排位路径
    拦（谁下小尺子不经此键，streak 允许人太少被迫连打时继续累加、下轮最优先歇）。"""
    streak = row.get("streak", 0)
    wait = row.get("wait_batch", 0)
    tonight = row.get("tonight", 0)
    seq = row.get("roster_seq", 0)
    over = [
        f"{name}={value}"
        for name, value in (
            ("streak", streak),
            ("wait_batch", wait),
            ("tonight", tonight),
            ("roster_seq", seq),
        )
        if value > 99
    ]
    if over:
        raise RotationOverflow("轮转数超范围：" + ",".join(over))
    # 连战只做第四档平手决胜（有=0 无=1）：不插队首、也不豁免连打上限
    fire = 0 if row.get("fire") else 1
    return streak * 10**8 + wait * 10**6 + tonight * 10**4 + fire * 100 + seq


def take_from_queue(players: list[dict], queue: list[int], n: int) -> list[int]:
    """按排位分抓 n 人发牌：候场（到场者）按 rank_key 典序取，返回序即上场序
    （「怎么配」的按队序档直接吃这个序）。轮到歇轮者（skip>0 且排位轮到了他）：
    跳过这一轮、原地扣一次（skip-1）、排位不动保位留队；不可发者（check 不在
    ARRIVED）保位留队不动；取满即停——没被轮到的歇轮不消耗。
    选中者带连战标记的当场兑现清除（fire=False）；本轮留在场下的人 streak 归零
    （连打只随上场延续，歇一轮即清）。queue 原地重排为剩余序（相对序不变）；
    n<=0 空手不动队。候场里有人排位段越界时 rank_key 抛 RotationOverflow。"""
    if n <= 0:
        return []
    by_id = {p["id"]: p for p in players}
    ranked = sorted(
        (pid for pid in queue if _arrived(by_id.get(pid))),
        key=lambda pid: rank_key(by_id[pid]),
    )
    taken: list[int] = []
    for pid in ranked:
        if len(taken) == n:
            break
        p = by_id[pid]
        if p.get("skip"):
            p["skip"] = p.get("skip", 0) - 1  # 轮到发牌给他：跳过这一轮、消耗一次
            continue
        taken.append(pid)
    taken_set = set(taken)
    queue[:] = [pid for pid in queue if pid not in taken_set]
    for pid in queue:  # 本轮没上=真正歇了：连打归零（被捞回续打的在 taken 里不动）
        p = by_id.get(pid)
        if p is not None:
            p["streak"] = 0
    for pid in taken:
        p = by_id[pid]
        if p.get("fire"):
            p["fire"] = False  # 连战兑现：上场即清除
    return taken


def _pair_count(facts: dict, a: int, b: int) -> int:
    # 搭档史键为升序二元组 (a, b)——由调用方从战报预算，双方查同一把钥匙
    lo, hi = (a, b) if a < b else (b, a)
    return facts.get("pair_counts", {}).get((lo, hi), 0)


def _split_candidates(
    ids: list[int], rate
) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    """左右两边的全部二分划，按「最强带最弱」的精神排枚举序：4 人恰为
    最接近 → 次接近 → 两强联手的 最差；战力全同的并列局也不会因并列漏进
    最差档。3 人时（供给不足的残队）最强单独成边排最先。枚举序即全平手时的决胜序。"""
    ranked = sorted(ids, key=lambda i: -rate(i))  # 同分保传入序（sorted 稳定）
    n = len(ranked)
    if n < 2:
        return [(tuple(ranked), ())]
    if n == 2:
        return [((ranked[0],), (ranked[1],))]
    # 队形现场最大 4 人：最强者的搭档从最弱往上试（3 人另含最强单独成边）
    out = [((ranked[0],), tuple(ranked[1:]))] if n == 3 else []
    for j in range(n - 1, 0, -1):
        a = (ranked[0], ranked[j])
        b = tuple(x for x in ranked if x not in a)
        out.append((a, b))
    return out


def _split_sides(
    players: list[dict],
    ids: list[int],
    pairing: str | None,
    facts: dict | None = None,
) -> tuple[list[int], list[int]]:
    """凑齐的一队分左右两边。queue=按取人顺序对半（第 1、2 位一队）；其余三档
    在全部二分划里按各档小分挑最优：
      balance 均衡配对——两边总战力最接近（最强带最弱 vs 二三）；与这 4 人最近一次
        同场的分法相同时退取次接近，最优/次优交替，绝不取两强联手的最差；
      partner 轮换优先——两对搭档今晚合作次数之和最少 → 分配更均匀（各 1 优先于
        0+2）→ 战力最接近兜底；
      even 胜负均衡——两队今晚净胜负绝对值之和最小（赢多的带输多的）→ 搭档次数
        最少 → 战力最接近兜底。
    战力小分放大 100 倍取整再比（两位小数的分差直接比浮点有噪声）。
    facts（可缺省，缺哪段哪段退化）：pair_counts {(小id, 大id): 合作次数}、
    net_wins {id: 今晚净胜场}、last_split {frozenset(全员): (边A, 边B)}——由调用方
    从战报预算，本模块零 ORM。上场永远按排位，配对只管分边不越位挑人。"""
    if pairing not in ("balance", "partner", "even"):
        half = (len(ids) + 1) // 2
        return ids[:half], ids[half:]
    facts = facts or {}
    by_id = {p["id"]: p for p in players}

    def rate(i: int) -> float:
        return by_id[i].get("rating", GUEST_DUPR)

    def closeness(sides) -> int:
        a, b = sides
        diff = abs(sum(rate(i) for i in a) - sum(rate(i) for i in b))
        # 放大 100 倍取整（round 无位参即返回 int）：两位小数的分差直接比浮点有噪声
        return round(diff * 100)

    def pair_sum(sides) -> int:
        return sum(
            _pair_count(facts, x, y) for side in sides for x, y in combinations(side, 2)
        )

    def spread(sides) -> int:
        counts = [
            _pair_count(facts, x, y) for side in sides for x, y in combinations(side, 2)
        ]
        return max(counts) - min(counts) if counts else 0

    def net_abs(sides) -> int:
        net = facts.get("net_wins") or {}
        return sum(abs(sum(net.get(i, 0) for i in side)) for side in sides)

    cands = _split_candidates(ids, rate)
    if pairing == "balance":
        scored = sorted(cands, key=closeness)
    elif pairing == "partner":
        scored = sorted(cands, key=lambda c: (pair_sum(c), spread(c), closeness(c)))
    else:
        scored = sorted(cands, key=lambda c: (net_abs(c), pair_sum(c), closeness(c)))
    pick = scored[0]

    def canon(sides) -> frozenset:
        return frozenset((frozenset(sides[0]), frozenset(sides[1])))

    if pairing == "balance" and len(scored) > 1:
        last = (facts.get("last_split") or {}).get(frozenset(ids))
        if last is not None and canon(pick) == canon(last):
            pick = scored[1]  # 防复读：退取次优（交替由此自然形成）
    return list(pick[0]), list(pick[1])


def _deal_fresh(
    players: list[dict],
    queue: list[int],
    court_no: int,
    size: int,
    pairing: str | None,
    facts: dict | None = None,
) -> list[int]:
    """从候场队取一整片全新一队落到 court_no（取队 → 分边 → 落位，原地改行）：
    结算全上全下重发与空片补满共用。供给不足取多少落多少——结算路坑位留空
    （下多少补多少），补片路由调用方先判够人。返回取走的 id。"""
    ids = take_from_queue(players, queue, size)
    side_a, side_b = _split_sides(players, ids, pairing, facts)
    by_id = {p["id"]: p for p in players}
    for side, members in (("a", side_a), ("b", side_b)):
        for pid in members:
            by_id[pid]["court_no"] = court_no
            by_id[pid]["court_side"] = side
    return ids


def autofill_idle(
    players: list[dict],
    courts: list[dict],
    rules: dict,
    queue: list[int],
    facts: dict | None = None,
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
        _deal_fresh(
            players, queue, court["court_no"], size, rules.get("pairing"), facts
        )
        court["status"] = "playing"
        opened.append(court["court_no"])
    return opened


def requeue_after_confirm(
    players: list[dict],
    court_no: int,
    winner_side: str,
    rules: dict,
    queue: list,
    streak_max: int = 0,
    facts: dict | None = None,
) -> None:
    """确认结束后的该片人员回流与补位：原地更新，只动该片。
    谁下谁补全按排位分（rank_key）当场算，不依赖传入队序。

    players: 全场名册行（喂行契约全键；排位键口径见模块头——接线层负责
             streak+1 / wait_batch 盖章 / tonight 含本场）。
    queue:   候场 id 列表；队列序回写 queue_pos 由调用方（LiveBook）负责。
    rules:   {"down": all|loser|n1|n2|n3, "pairing": queue|balance|partner|even,
              "doubles": bool}。
    streak_max: 连打上限，0=不限（缺省 0——未接线路径保持不设上限的旧行为）。
    facts:   分边三档的战报史（形状见 _split_sides）。
    winner_side: "a"|"b"。
    供给不足时坑位留空（下多少人补多少人），不重复补、不越位挑人。"""
    oncourt = [
        p
        for p in players
        if p.get("court_no") == court_no and p.get("court_side") in ("a", "b")
    ]
    losers = [p for p in oncourt if p["court_side"] != winner_side]
    winners = [p for p in oncourt if p["court_side"] == winner_side]
    size = 2 if not rules.get("doubles", True) else 4
    down = rules.get("down")

    def to_tail(group: list[dict]) -> None:
        for p in _by_tenure(group):  # 入队尾序只作全平手时的稳定兜底（排位才说了算）
            p["court_no"] = None
            p["court_side"] = None
            queue.append(p["id"])

    def place(player_id, side: str) -> None:
        row = next(p for p in players if p["id"] == player_id)
        row["court_no"] = court_no
        row["court_side"] = side

    if (
        down == "loser"
        and streak_max != 0
        and any(p.get("streak", 0) >= streak_max for p in winners)
    ):
        down = "all"  # 赢家连打毕业：不再守擂，整片全下走重发路

    if down == "loser":
        # 输家下：败方回队、胜者留场守擂，按排位补空边成一队挑战（不拆赢家不重配）
        to_tail(losers)
        for player_id in take_from_queue(players, queue, len(losers)):
            place(player_id, "a" if winner_side == "b" else "b")
        return

    if down not in ("n1", "n2", "n3"):
        # 全上全下（含赢家到上限的整片重发）：全场下、按"怎么配"凑全新一队
        to_tail(oncourt)
        _deal_fresh(players, queue, court_no, size, rules.get("pairing"), facts)
        return

    # n1/n2/n3 谁下小尺子：只比连打与上场早晚——连打多的先下、平了上场早（章小）的
    # 先下；今晚场次/到场序不掺和。连打不封顶（人太少被迫连打时累下去，下轮最优先歇）
    n = int(down[1])
    downs = sorted(oncourt, key=lambda p: (-p.get("streak", 0),) + _tenure_key(p))[:n]
    sides = [d["court_side"] for d in downs]
    # 下场者入池与候场合流：补位从全池按排位取——场下等的人（连打0等最久）自然
    # 最先、差的名额从刚下的里捞最不累的回来续打、全池最靠后的留场下歇
    for d in downs:
        d["court_no"] = None
        d["court_side"] = None
        queue.append(d["id"])
    # N 个坑一次取齐而不是逐坑取 1：歇轮者「跳过这一轮」以这次结算为一轮——逐坑取
    # 会让队首歇者被第一坑跳过消耗后、紧接着被第二坑捞上场
    for player_id, side in zip(take_from_queue(players, queue, len(downs)), sides):
        place(player_id, side)
    if rules.get("pairing") not in (None, "queue"):
        # 非队序档：补齐后整片重分边——新人不止顶坑，留下的人也换边（防两人焊死同边）
        court_ids = [
            p["id"]
            for p in players
            if p.get("court_no") == court_no and p.get("court_side") in ("a", "b")
        ]
        side_a, side_b = _split_sides(players, court_ids, rules.get("pairing"), facts)
        for pid in side_a:
            place(pid, "a")
        for pid in side_b:
            place(pid, "b")
