"""live_rotation —— 确认后的人员回流纯逻辑（docs/2.3 §4.6-③ 引用 docs/2.4 四件套）。

Python 镜像 frontend/src/utils/rotate.ts 的结算回流段（endMatch 的"谁下谁留谁补"；
发牌本体仍在前端，排阵结果走 deal 上报——技术设计 §0）。纯 dict/list 进出、原地更新，
不碰 sqlalchemy/快框架（I3.2 解耦：可单测、批2 由 LiveBook 喂行喂回）。

与 rotate.ts 的已定偏差（双语言关系记技术设计 §4 知识落点表，1.3 规格化时统一真值）：
- 队首顺补按队序直取——歇轮消耗/连战优先（takeFromQueue）的取队口径不在本模块重演；
- 资历序（n 系"谁下"）读行上的 tenure/court_seq 键，缺省视为最浅（等价并列、按当前序）；
- 比分清零/片状态回落不在此处——本模块只管人的去留与去向。
"""

from __future__ import annotations

# 均衡排序的初始分（2.4 §8 定值：没打过的新人与访客按 1500 参与排序）
RANK_INIT = 1500


def _by_tenure(players: list[dict]) -> list[dict]:
    """资历序（2.4 §4.4「待得最久」）：tenure 降序、并列按上场先后（court_seq 升）——
    先上的先下。行上没带资历键的按最浅参与并列（保持传入序）。"""
    return sorted(
        players,
        key=lambda p: (-p.get("tenure", 0), p.get("court_seq", 0)),
    )


def snake_pick(players: list[dict], n: int) -> list[list[dict]]:
    """按积分蛇形均衡分 n 队（2.4 均衡配对）：rating 降序（同分按传入序，不掷骰子）、
    蛇形轮发 1..n,n..1——最强+最弱 vs 二三，不让最强的几个挤同队。镜像 rotate.ts
    splitSides(balance) 的语义并推广到 n 队。"""
    if n < 1:
        return []
    ranked = sorted(players, key=lambda p: -p.get("rating", RANK_INIT))
    teams: list[list[dict]] = [[] for _ in range(n)]
    # 蛇形取牌序：第 1 轮 0,1,..,n-1、第 2 轮反转 n-1,..,0，按 2n 一循环
    lap = list(range(n)) + list(range(n - 1, -1, -1))
    for i, p in enumerate(ranked):
        teams[lap[i % len(lap)]].append(p)
    return teams


def requeue_after_confirm(
    players: list[dict],
    court_no: int,
    winner_side: str,
    rules: dict,
    queue: list,
) -> None:
    """确认结束后的该片回流（2.3 §4.6-③，四件套按 2.4 真值）——原地更新，只动该片。

    players: 全场名册行（dict，至少含 id/court_no/court_side；n 系资历可选带
             tenure/court_seq）；只改 court_no 片上行与 queue。
    queue:   候场 id 列表（队首在前）——下场者按资历序入队尾、补位者从队首取；
             队列序回写 queue_pos 由调用方（LiveBook）负责。
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

    def take_heads(n: int) -> list:
        got = queue[:n]
        del queue[:n]
        return got

    def place(player_id, side: str) -> None:
        row = next(p for p in players if p["id"] == player_id)
        row["court_no"] = court_no
        row["court_side"] = side

    if rules.get("down") == "loser":
        # 输家下：败方回队尾、胜者留场，候场首补空边成一队挑战（不重配）
        to_tail(losers)
        for player_id in take_heads(len(losers)):
            place(player_id, "a" if winner_side == "b" else "b")
        return

    if rules.get("down") not in ("n1", "n2", "n3"):
        # 全上全下（含连庄到点等整片重发）：全场下、按"怎么配"凑全新一队
        to_tail(oncourt)
        ids = take_heads(size)
        if rules.get("pairing") == "balance" and ids:
            side_a, side_b = snake_pick(
                [next(p for p in players if p["id"] == i) for i in ids], 2
            )
            for p in side_a:
                place(p["id"], "a")
            for p in side_b:
                place(p["id"], "b")
        else:
            # 按候场队序：第 1、2 位一队、第 3、4 位一队（镜像 splitSides(queue)）
            for i, player_id in enumerate(ids):
                place(player_id, "a" if i < (len(ids) + 1) // 2 else "b")
        return

    # n1/n2/n3：资历最久的 N 人下，候场首逐个原位顶坑（谁下补谁的坑，留下的保住半边）
    n = int(rules["down"][1])
    for down in _by_tenure(oncourt)[:n]:
        side = down["court_side"]
        down["court_no"] = None
        down["court_side"] = None
        queue.append(down["id"])
        rep = take_heads(1)
        if rep:
            place(rep[0], side)
