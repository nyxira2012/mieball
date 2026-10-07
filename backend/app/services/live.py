"""LiveBook —— 现场总账深模块（docs/2.3）：开账、总账读视图、记分链、两级号并发防线。

批1 落骨架（start/view + 两级号机制），批2 记分链入住（deal/point/undo/clear/
settle-open/settle-confirm/cancel），批3 2.2 域动作（check/swap/tempo/rules/封撤
管理员）+ 散场链（sweep-cancel-all/end 拆在 live_sweep.py 的 LiveSweepMixin）。
策略内聚在这里，路由只做参数搬运：
- 现场是"另一本账"：locked 局之上由 start 展开（正式球友一人一行 + 随行访客一行），
  散场后 games.ended_at 落库即封存，view 同一形状 = 只读回看（2.3 §4.10）。
- 考勤分权：arrive/left 时刻只有组织者与本人可见，其他人一律 null（2.3 裁决 Q2）。
- 两级号（附录 B1）：全场一个总号（任何现场写 +1）、每片自己的片号（该片记分类写 +1）；
  写入口带"出发时看到的号"，号旧即退回——同片并发才互斥，别片照常。
- 写串行：SQLite 无行锁，模块级锁罩住全部写动作（沿 GameBook 先例），check-then-act
  全锁内。
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from math import floor

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import clock, errors
from ..db.models import (
    Account,
    EloRating,
    Entry,
    Game,
    LiveCourt,
    LiveMatch,
    LivePlayer,
    LiveState,
)
from . import live_rotation
from .accounts import person_view
from .live_sweep import ARRIVED, LiveSweepMixin

# 开账起笔的 rules 快照默认值（镜像前端 startLive 起笔，2.2 批2 §4.1）：
# 双打 / 谁下挂 all 占位（推荐重算在前端）/ 按候场队序 / 连庄上限 3
_DEFAULT_RULES = {"doubles": True, "down": "all", "pairing": "queue", "streak_max": 3}
# 新人初始等级单一源（2.4 §8 定值；对齐前端 ui「Elo 默认 1500 起」）
RATING_INIT = 1500

# Elo 镜像源 frontend/src/utils/elo.ts：K=24（alpha:1697）、地板 400（alpha:1704）、
# 败方只扣胜方涨分六成（alpha:1698）；访客按 1500 代入当正常玩家算——去半折（2.3 修订②）
_ELO_K = 24.0
_ELO_FLOOR = 400
# 防线 409 退回时要在错误体里带最新视图的两个码（附录 B1：最新画面送来，前端对表用）
_STALE_CODES = frozenset({"live_stale_total", "live_stale_court"})


def _js_round(x: float) -> int:
    # JS Math.round 半向上取整；Python round 是银行家舍入，镜像公式要绕开
    return floor(x + 0.5)


def _snapshot(p: LivePlayer) -> dict:
    """战报名单快照（LiveMatch.winners/losers 元素）：id 是名册行 id。"""
    return {"id": p.id, "name": p.display_name, "guest": p.guest}


# 现场写动作全串行：SQLite 无行锁，靠它保住"账只有一本"（2.3 附录 B1）
_write_lock = threading.Lock()


class LiveBook(LiveSweepMixin):
    def __init__(self, db: Session):
        self.db = db

    # ---- 开账（名册展开 + 总账头落库；幂等） ----

    def start(self, *, game_id: int, organizer_id: int) -> dict:
        """开账（2.2 §4.1 开场亮点的总账版）：名册行从正式报名展开——正式球友一人
        一行（首见建 EloRating 行 1500），bring N 展开成 N 行随行访客（挂担保人）；
        全员先记 absent、候场队空（报到驱动，check 端点批3）；total_seq 从 1 起。
        幂等：已有 LiveState 直接返视图（散场后再点也只回看，不重开）。"""
        with _write_lock:
            game = self.db.get(Game, game_id)
            if game is None:
                raise errors.game_not_found()
            if game.organizer_id != organizer_id:
                raise errors.organizer_only("只有组织者能开现场账")
            if self._state_or_none(game_id) is not None:
                return self.view(game_id=game_id, viewer_id=organizer_id)
            now = clock.now()
            self.db.add(
                LiveState(
                    game_id=game_id,
                    total_seq=1,
                    started_at=now,
                    # 片数起笔镜像 rotate.ts courtCount 单一源：订场登记优先，缺省按人数回退
                    courts_count=(
                        len(game.courts)
                        if game.courts
                        else (3 if game.max_players >= 12 else 2)
                    ),
                    **_DEFAULT_RULES,
                )
            )
            # 正式行按报名先后展开（joined_at, id 序沿 entry_rows 口径）
            formals = (
                self.db.execute(
                    select(Entry)
                    .where(Entry.game_id == game_id, Entry.standing == "formal")
                    .order_by(Entry.joined_at, Entry.id)
                )
                .scalars()
                .all()
            )
            for entry in formals:
                # person_view 的对外名单一源：在册出昵称、注销者按占位名定格（1.1 隐私口径）
                name = person_view(self.db.get(Account, entry.account_id))["nickname"]
                self.db.add(
                    LivePlayer(
                        game_id=game_id,
                        account_id=entry.account_id,
                        display_name=name,
                        check="absent",
                    )
                )
                self._elo_row(entry.account_id)
                for i in range(entry.bring):
                    self.db.add(
                        LivePlayer(
                            game_id=game_id,
                            account_id=None,
                            # 访客命名沿前端 startLive：担保人昵称前两字 + 编号
                            display_name=f"{name[:2]}的球友·{i + 1}",
                            guest=True,
                            guarantor_account_id=entry.account_id,
                            check="absent",
                        )
                    )
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=organizer_id)

    # ---- 记分链（批2）：发牌上报 → 记分/撤分/清零 → 待确认 → 确认/取消 ----

    def deal(
        self,
        *,
        game_id: int,
        actor_id: int,
        courts: list[dict],
        base_total_seq: int,
    ) -> dict:
        """排阵上报（技术设计 §3：发牌算法在前端，总账只把关事实）：各片 A/B
        名单必须是候场队头顺位那拨（fillAllCourts 按片号先后取队首）；过关即
        落片行 status=playing、seq+1 开打，人从候场队摘下。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, _game = self._open_write(game_id)
            self._require_arrived(game_id, actor_id)
            self._check_total(state, base_total_seq)
            rows = self._roster(game_id)
            by_id = {r.id: r for r in rows}
            queue = self._queue_ids(rows)
            dealt: list[int] = []
            seen: set[int] = set()
            picked: list[tuple[LiveCourt, dict]] = []
            for c in courts:
                if c["court_no"] in seen:
                    raise errors.live_invalid("同一片发了两手牌")
                seen.add(c["court_no"])
                if c["court_no"] > state.courts_count:
                    raise errors.live_invalid("片号超出场地数")
                court = self._court_or_none(game_id, c["court_no"])
                if court is None:
                    court = LiveCourt(game_id=game_id, court_no=c["court_no"])
                    self.db.add(court)
                elif court.status == "pending":
                    raise errors.court_frozen()
                elif court.status == "playing":
                    raise errors.live_invalid("这片还在打，不能重复发牌")
                ids = list(c["a"]) + list(c["b"])
                if any(i not in by_id for i in ids):
                    raise errors.live_invalid("发牌名单里有不在名册的人")
                picked.append((court, c))
                dealt += ids
            # 队首把关：报上来的人必须正好是候场队头这拨（跳位/凑不齐都退）
            if len(set(dealt)) != len(dealt) or set(dealt) != set(queue[: len(dealt)]):
                raise errors.live_invalid("发牌的人不在候场队首")
            rest = queue[len(dealt) :]
            for court, c in picked:
                fresh = court.id is None  # 列 default 在 INSERT 才生效，新行显式起笔
                court.status = "playing"
                court.seq = 1 if fresh else court.seq + 1
                court.sa = 0
                court.sb = 0
                court.last_winner_side = None
                court.pending_origin = None
                court.court_seq = 1 if fresh else court.court_seq + 1
                for pid in c["a"] + c["b"]:
                    r = by_id[pid]
                    r.court_no = court.court_no
                    r.court_side = "a" if pid in c["a"] else "b"
                    r.queue_pos = None
            for pos, pid in enumerate(rest):
                by_id[pid].queue_pos = pos
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def point(
        self,
        *,
        game_id: int,
        actor_id: int,
        court_no: int,
        side: str,
        base_total_seq: int,
        base_court_seq: int,
    ) -> dict:
        """记一分（§4.1）：点哪边哪边 +1、片行自记最后得分方；记分落账时当即判
        到分（分制数且净胜 2，§4.3）——够线该片转 pending(origin='auto')，别片照打。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            self._require_arrived(game_id, actor_id)
            self._check_total(state, base_total_seq)
            court = self._court_writable(game_id, court_no)
            self._check_court(court, base_court_seq)
            if side == "a":
                court.sa += 1
            else:
                court.sb += 1
            court.last_winner_side = side
            if self._reached(court.sa, court.sb, game.scoring):
                court.status = "pending"
                court.pending_origin = "auto"
            self._bump_court(court)
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def undo(
        self,
        *,
        game_id: int,
        actor_id: int,
        court_no: int,
        base_total_seq: int,
        base_court_seq: int,
    ) -> dict:
        """撤一分（§4.1/§4.5）：只撤该片最后一次得分方那 1 分、撤不成负；last
        保持在得分方（连撤连减）。playing 态任意到场者可写；pending 态是确认窗内
        的全权撤分——auto 窗撤后重判：够分线保窗、不够自动关窗回 playing，
        manual 窗只改比分不关窗（人工开的窗收不收由人再决定）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            court = self._court_writable(
                game_id, court_no, statuses=("playing", "pending")
            )
            if court.status == "pending":
                self._require_full_power(state, game, actor_id)
            else:
                self._require_arrived(game_id, actor_id)
            self._check_total(state, base_total_seq)
            self._check_court(court, base_court_seq)
            applied = False
            if court.last_winner_side == "a" and court.sa > 0:
                court.sa -= 1
                applied = True
            elif court.last_winner_side == "b" and court.sb > 0:
                court.sb -= 1
                applied = True
            # last 为空或该边已是 0 分（0:0）：无可撤——原样回视图，不动账不进号
            if applied:
                if (
                    court.status == "pending"
                    and court.pending_origin == "auto"
                    and not self._reached(court.sa, court.sb, game.scoring)
                ):
                    court.status = "playing"  # auto 窗撤到分线下：窗自动关（§4.5）
                    court.pending_origin = None
                self._bump_court(court)
                self._bump_total(state)
                self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def clear(
        self,
        *,
        game_id: int,
        actor_id: int,
        court_no: int,
        base_total_seq: int,
        base_court_seq: int,
    ) -> dict:
        """清零重开（§4.2，全权）：比分归 0:0、last 清掉、pending 作废回 playing；
        人不下场——同一批人这盘重打（待确认时入口收在确认窗里）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            court = self._court_writable(
                game_id, court_no, statuses=("playing", "pending")
            )
            self._require_full_power(state, game, actor_id)
            self._check_total(state, base_total_seq)
            self._check_court(court, base_court_seq)
            court.sa = 0
            court.sb = 0
            court.last_winner_side = None
            court.status = "playing"
            court.pending_origin = None
            self._bump_court(court)
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def settle_open(
        self,
        *,
        game_id: int,
        actor_id: int,
        court_no: int,
        base_total_seq: int,
        base_court_seq: int,
    ) -> dict:
        """提前结算（§4.4，全权）：不到分线也能收——playing 转 pending(origin='manual')，
        与到分自动触发同一条路；胜方预选由视图 preselect 定值给出（领先方/平分不预选）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            self._require_full_power(state, game, actor_id)
            self._check_total(state, base_total_seq)
            court = self._court_writable(game_id, court_no)
            self._check_court(court, base_court_seq)
            court.status = "pending"
            court.pending_origin = "manual"
            self._bump_court(court)
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def settle_confirm(
        self,
        *,
        game_id: int,
        actor_id: int,
        court_no: int,
        winner_side: str,
        score_a: int,
        score_b: int,
        no_redeal: bool,
        base_total_seq: int,
        base_court_seq: int,
    ) -> dict:
        """确认结束（§4.6，全权）：一本账原子——战报行落账（此后不可改）+ EloRating
        结算 + 人回流补位重排，同一事务要么全成要么全不成。胜方必须分高方（平分双方
        均可）；幂等：重复确认（重放刚落账那场）回当前视图 200，不重落。
        no_redeal（散场清扫态）：回流定格、不排下一场不补位（§4.9-1）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            self._require_full_power(state, game, actor_id)
            court = self._court_or_none(game_id, court_no)
            if court is None:
                raise errors.court_idle()
            if court.status != "pending":
                if self._is_replay(game_id, court_no, winner_side, score_a, score_b):
                    return self.view(game_id=game_id, viewer_id=actor_id)
                self._check_total(state, base_total_seq)
                self._check_court(court, base_court_seq)
                raise errors.live_invalid("这片没有待确认的对局")
            self._check_total(state, base_total_seq)
            self._check_court(court, base_court_seq)
            if (winner_side == "a" and score_a < score_b) or (
                winner_side == "b" and score_b < score_a
            ):
                raise errors.live_invalid("分低的一方当不了胜方")
            # —— 一本账（§4.6-2）：战报 + 积分 + 回流，一个 commit ——
            rows = self._roster(game_id)
            by_id = {r.id: r for r in rows}
            oncourt = self._oncourt(rows, court_no)
            winners = [r for r in oncourt if r.court_side == winner_side]
            losers = [r for r in oncourt if r.court_side != winner_side]
            elo_rows = self._elo_settle(winners, losers)
            self.db.add(
                LiveMatch(
                    game_id=game_id,
                    court_no=court_no,
                    seq=court.seq,
                    winners=[_snapshot(r) for r in winners],
                    losers=[_snapshot(r) for r in losers],
                    sa=score_a,
                    sb=score_b,
                    winner_side=winner_side,
                    ended_at=clock.now(),
                    elo_rows=elo_rows,
                )
            )
            self._apply_elo(elo_rows, len(winners))
            queue = self._queue_ids(rows)
            if no_redeal:
                # 清扫态：人只回流定格——不排下一场不补位，场上的人按行序接队尾
                for r in oncourt:
                    r.court_no = None
                    r.court_side = None
                    queue.append(r.id)
                court.status = "idle"
            else:
                dicts = [
                    {"id": r.id, "court_no": r.court_no, "court_side": r.court_side}
                    for r in rows
                ]
                live_rotation.requeue_after_confirm(
                    dicts,
                    court_no,
                    winner_side,
                    {
                        "down": state.down,
                        "pairing": state.pairing,
                        "doubles": state.doubles,
                    },
                    queue,
                )
                for d in dicts:
                    r = by_id[d["id"]]
                    r.court_no = d["court_no"]
                    r.court_side = d["court_side"]
                court.status = "playing"
                court.seq += 1
            for r in rows:
                if r.court_side is not None:
                    r.queue_pos = None
            for pos, pid in enumerate(queue):
                by_id[pid].queue_pos = pos
            court.sa = 0
            court.sb = 0
            court.last_winner_side = None
            court.pending_origin = None
            self._bump_court(court)
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def cancel(
        self,
        *,
        game_id: int,
        actor_id: int,
        court_no: int,
        no_redeal: bool,
        base_total_seq: int,
        base_court_seq: int,
    ) -> dict:
        """取消对局（§4.7，全权）：整场作废——不计分不进战绩；场上的人原样回流
        候场队首（补偿没打成的，沿 2.2 §4.12）；该片腾出来（idle）等重新发牌。
        no_redeal 与确认同参数只为清扫链路统一——取消本就不补位，带不带一个行为。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            court = self._court_writable(
                game_id, court_no, statuses=("playing", "pending")
            )
            self._require_full_power(state, game, actor_id)
            self._check_total(state, base_total_seq)
            self._check_court(court, base_court_seq)
            rows = self._roster(game_id)
            self._void_court(rows, {r.id: r for r in rows}, court)
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    # ---- 2.2 域动作（批3）：出勤 / 换人 / 歇连 / 规则与场地 / 封撤管理员 ----
    # 全是动全场的事，按总号拦（§4.8-4），不带片号。

    def check(
        self,
        *,
        game_id: int,
        actor_id: int,
        player_id: int,
        check: str,
        base_total_seq: int,
    ) -> dict:
        """报到四态（2.2 §4.2/4.3/4.5）：自己报自己可、代办他人需全权。
        ok=开球前到场——未到首报且已过开球时刻归一 late；late/join 一律排队尾；
        left=早退——清队列位与片上位置、落离场时刻（片上缺人打短维持现状，补人归
        手动换人）；left 回来按 join 走（回来也是队尾）。在片上的人报 ok/late/join 拒
        （人已在场上不该再报到——防"留片上+进队"双态；left 清过片位，不受此拦）。
        到场不自动发牌——发牌算法在前端，够人由前端 deal 上报。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            row = self._roster_row(game_id, player_id)
            if row.account_id != actor_id:
                self._require_full_power(state, game, actor_id)
            self._check_total(state, base_total_seq)
            st = check
            if st in ("ok", "late"):
                if row.check == "left":
                    st = "join"  # 回来也是队尾（2.2 §4.5 禁止插队首）
                elif (
                    st == "ok" and row.check == "absent" and clock.now() > game.start_at
                ):
                    st = "late"  # 迟到口径：未到首报且已过开球时刻
            rows = self._roster(game_id)
            by_id = {r.id: r for r in rows}
            queue = self._queue_ids(rows)
            if st == "left":
                row.check = "left"
                if row.id in queue:
                    queue.remove(row.id)  # 早退不再排队等发牌
                row.queue_pos = None
                row.court_no = None
                row.court_side = None
                if row.left_at is None:
                    row.left_at = clock.now()
            else:
                if row.court_no is not None:
                    raise errors.live_invalid("人已在场上")
                if st == "late":
                    if row.id in queue:
                        queue.remove(row.id)
                    queue.append(row.id)  # 迟到排队尾
                elif st == "join":
                    if row.id not in queue:
                        queue.append(row.id)  # 中途加入排队尾
                elif row.check not in ARRIVED and row.id not in queue:
                    queue.append(row.id)  # 'ok' 只在首报进队，重复报到不重排
                row.check = st
                if row.arrive_at is None:
                    row.arrive_at = clock.now()  # 几点到：首次到场落账
            for pos, pid in enumerate(queue):
                by_id[pid].queue_pos = pos
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def swap(
        self,
        *,
        game_id: int,
        actor_id: int,
        out_id: int,
        in_id: int,
        base_total_seq: int,
    ) -> dict:
        """换人（2.2 §4.9 任意到场者可、操作留名）：inId 出队原位顶 outId 的坑、
        outId 离片回队尾；pending 片整片冻结拒收（2.3 裁决 Q5——战报名单要与实际
        打过的人对得上）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, _game = self._open_write(game_id)
            self._require_arrived(game_id, actor_id)
            self._check_total(state, base_total_seq)
            out = self._roster_row(game_id, out_id)
            inn = self._roster_row(game_id, in_id)
            if out.court_no is None or out.court_side is None:
                raise errors.live_invalid("被换下的人不在场上")
            court = self._court_writable(game_id, out.court_no)  # pending → 冻结
            if inn.queue_pos is None:
                raise errors.live_invalid("换上的人不在候场队")
            rows = self._roster(game_id)
            by_id = {r.id: r for r in rows}
            queue = self._queue_ids(rows)
            queue.remove(inn.id)
            queue.append(out.id)  # 被换下排队尾（§4.9-3）
            inn.court_no = court.court_no
            inn.court_side = out.court_side
            inn.queue_pos = None
            out.court_no = None
            out.court_side = None
            for pos, pid in enumerate(queue):
                by_id[pid].queue_pos = pos
            self._feed_push(
                state,
                {
                    "kind": "swap",
                    "actor": self._actor_name(game_id, actor_id),
                    "out": out.display_name,
                    "in": inn.display_name,
                    "at": clock.iso(clock.now()),
                },
            )
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def tempo(
        self,
        *,
        game_id: int,
        actor_id: int,
        player_id: int,
        action: str,
        base_total_seq: int,
    ) -> dict:
        """歇/连（2.2 §4.10）：给自己随时、给他人需全权。skip 按一次 +1 可叠加
        （轮到发牌时由前端引擎消耗）；fire 互斥清 skip 且把候场里的人排到队首
        （场上的人无从排起）；unskip 清零；fire 再按一次=取消连战（队列不动）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            row = self._roster_row(game_id, player_id)
            if row.account_id != actor_id:
                self._require_full_power(state, game, actor_id)
            self._check_total(state, base_total_seq)
            if action == "unskip":
                row.skip = 0
            elif action == "skip":
                row.fire = False  # 互斥
                row.skip += 1
            else:
                row.fire = not row.fire
                if row.fire:
                    row.skip = 0
                    rows = self._roster(game_id)
                    by_id = {r.id: r for r in rows}
                    queue = self._queue_ids(rows)
                    if row.id in queue:
                        queue.remove(row.id)
                        queue.insert(0, row.id)  # 连战排队首
                        for pos, pid in enumerate(queue):
                            by_id[pid].queue_pos = pos
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def rules(
        self,
        *,
        game_id: int,
        actor_id: int,
        base_total_seq: int,
        doubles: bool | None = None,
        down: str | None = None,
        pairing: str | None = None,
        streak_max: int | None = None,
        courts_count: int | None = None,
    ) -> dict:
        """规则四件套+场地片数（2.2 §4.7 收权，全场号拦）：只动显式给的字段。
        四件套落总账头（下一场起按新规，在打片照旧打完）；courts_count 改片数——
        不得少于在用片数，缩片先撤空闲片（在打/待确认的片不能收）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            self._require_full_power(state, game, actor_id)
            self._check_total(state, base_total_seq)
            if down is not None:
                state.down = down
            if pairing is not None:
                state.pairing = pairing
            if doubles is not None:
                state.doubles = doubles
            if streak_max is not None:
                state.streak_max = streak_max
            if courts_count is not None:
                courts = self._courts(game_id)
                if courts_count < sum(c.status != "idle" for c in courts):
                    raise errors.live_invalid("在用的片不能收")
                for c in courts:  # 缩片：空闲片从大号往回撤（在用的保住）
                    if c.status == "idle" and c.court_no > courts_count:
                        self.db.delete(c)
                state.courts_count = courts_count
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def set_admin(
        self, *, game_id: int, actor_id: int, player_id: int, base_total_seq: int
    ) -> dict:
        """封管理员（2.2 §4.6 组织者独占——管理员不能再封别人）：靶行须是正式
        球友；已封再封当没事（幂等不进号）。feed 留痕全场可见。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            if game.organizer_id != actor_id:
                raise errors.organizer_only("只有组织者能封管理员")
            self._check_total(state, base_total_seq)
            row = self._roster_row(game_id, player_id)
            if row.account_id is None:
                raise errors.live_invalid("访客不能当管理员")
            if row.account_id not in (state.admins or []):
                state.admins = [*(state.admins or []), row.account_id]
                self._feed_push(
                    state,
                    {
                        "kind": "set_admin",
                        "actor": self._actor_name(game_id, actor_id),
                        "target": row.display_name,
                        "at": clock.iso(clock.now()),
                    },
                )
                self._bump_total(state)
                self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def unset_admin(
        self, *, game_id: int, actor_id: int, player_id: int, base_total_seq: int
    ) -> dict:
        """撤管理员（2.2 §4.6 组织者独占）：不在册当没事（幂等不进号）；撤留痕
        feed——「组织者收回了管理员身份」的事件句。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            if game.organizer_id != actor_id:
                raise errors.organizer_only("只有组织者能撤管理员")
            self._check_total(state, base_total_seq)
            row = self._roster_row(game_id, player_id)
            if row.account_id in (state.admins or []):
                state.admins = [a for a in state.admins if a != row.account_id]
                self._feed_push(
                    state,
                    {
                        "kind": "unset_admin",
                        "actor": self._actor_name(game_id, actor_id),
                        "target": row.display_name,
                        "at": clock.iso(clock.now()),
                    },
                )
                self._bump_total(state)
                self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    # ---- 总账读视图（进行中与散场后同一形状：散场后 = 只读回看） ----

    def view(self, *, game_id: int, viewer_id: int | None) -> dict:
        """总账读（2.3 附录 A4：画面一个字不自算，全给定值）。考勤时刻按 viewer
        分权——组织者或本人见 arrive/left，其他人 null；带队 total_seq 与各片
        court_seq（契约总则 §4 预留的轮次/版本字段落地）。未开账 → 404。"""
        state = self._state_or_none(game_id)
        if state is None:
            raise errors.live_not_found()
        game = self.db.get(Game, game_id)
        is_organizer = viewer_id is not None and game.organizer_id == viewer_id
        rows = [
            self._player_row(p, is_organizer=is_organizer, viewer_id=viewer_id)
            for p in self._roster(game_id)
        ]
        courts = self._courts(game_id)
        matches = (
            self.db.execute(
                select(LiveMatch)
                .where(LiveMatch.game_id == game_id)
                .order_by(LiveMatch.ended_at, LiveMatch.id)
            )
            .scalars()
            .all()
        )
        # 队列序定值给出（队首在前，候场外的行不排）；queue_pos 的持久化回写是写动作的事
        waiting = sorted(
            (r for r in rows if r["queue_pos"] is not None),
            key=lambda r: r["queue_pos"],
        )
        return {
            "game_id": game_id,
            "started_at": clock.iso(state.started_at),
            "ended": game.ended_at is not None,
            "ended_at": clock.iso(game.ended_at) if game.ended_at else None,
            "fee": self._fee_block(game),
            "total_seq": state.total_seq,
            "round": state.round,
            "admins": state.admins or [],
            "feed": state.feed or [],
            "courts_count": state.courts_count,
            "rules": {
                "scoring": game.scoring,  # 全场统一分制复用局列（2.3 裁决 Q1）
                "doubles": state.doubles,
                "down": state.down,
                "pairing": state.pairing,
                "streak_max": state.streak_max,
            },
            "players": rows,
            "queue": [r["id"] for r in waiting],
            "courts": [
                {
                    "court_no": c.court_no,
                    "status": c.status,
                    "seq": c.seq,
                    "score_a": c.sa,
                    "score_b": c.sb,
                    "last_winner_side": c.last_winner_side,
                    "court_seq": c.court_seq,
                    "pending_origin": c.pending_origin,
                    "preselect": self._preselect(c),
                }
                for c in courts
            ],
            "matches": [
                {
                    "court_no": m.court_no,
                    "seq": m.seq,
                    "winners": m.winners,
                    "losers": m.losers,
                    "score_a": m.sa,
                    "score_b": m.sb,
                    "winner_side": m.winner_side,
                    "ended_at": clock.iso(m.ended_at),
                    "elo_rows": m.elo_rows,
                }
                for m in matches
            ],
        }

    # ---- 内部：写动作公共件与两级号机制（全部在 _write_lock 内调用） ----

    def _fee_block(self, game: Game) -> dict:
        """费用亮数块（1.3 §3 散场确认页）：总价=订场登记真值（null=未定）；人头=
        账单口径的摊钱人头——正式/空降行每人 1 + 名下访客行数（与出账引擎同尺，
        亮数与实摊一个数）；per_head=floor 向下抹零，未定价局为 null 但 heads 照给
        （亮「总价未定 · N 人」用）。"""
        rows = self._roster(game.id)
        accounts = {p.account_id for p in rows if p.account_id is not None}
        heads = len(accounts) + sum(
            1 for p in rows if p.guarantor_account_id in accounts
        )
        per_head = game.fee_total // heads if game.fee_total is not None else None
        return {"total": game.fee_total, "heads": heads, "per_head": per_head}

    @contextmanager
    def _write(self, *, game_id: int, actor_id: int):
        """记分链写动作公共外壳：模块锁内跑业务；防线退回的旧号 409 在错误体里
        补上最新视图（附录 B1——前端拿它直接对表，不用再拉一次读）。"""
        with _write_lock:
            try:
                yield
            except errors.ApiError as e:
                if e.code in _STALE_CODES and e.view is None:
                    e.view = self.view(game_id=game_id, viewer_id=actor_id)
                raise

    def _open_write(self, game_id: int) -> tuple[LiveState, Game]:
        """写动作开门三查：账在、没散场（散场后旧画面的写动作一律拒收，§4.10）。"""
        state = self._state_or_none(game_id)
        if state is None:
            raise errors.live_not_found()
        game = self.db.get(Game, game_id)
        if game.ended_at is not None:
            raise errors.live_ended()
        return state, game

    def _roster(self, game_id: int) -> list[LivePlayer]:
        return (
            self.db.execute(
                select(LivePlayer)
                .where(LivePlayer.game_id == game_id)
                .order_by(LivePlayer.id)
            )
            .scalars()
            .all()
        )

    def _queue_ids(self, rows: list[LivePlayer]) -> list[int]:
        """候场队（队首在前）——queue_pos 升序即队列序（技术设计 §2）。"""
        return [
            r.id
            for r in sorted(
                (r for r in rows if r.queue_pos is not None),
                key=lambda r: r.queue_pos,
            )
        ]

    def _court_or_none(self, game_id: int, court_no: int) -> LiveCourt | None:
        return self.db.execute(
            select(LiveCourt).where(
                LiveCourt.game_id == game_id, LiveCourt.court_no == court_no
            )
        ).scalar_one_or_none()

    def _court_writable(
        self, game_id: int, court_no: int, *, statuses: tuple[str, ...] = ("playing",)
    ) -> LiveCourt:
        """片状态机校验：没开打 → court_idle；pending 而该动作不是出口 → court_frozen
        （§4.3 冻结的出口只有清零/取消/确认，undo 是窗的能力）。"""
        court = self._court_or_none(game_id, court_no)
        if court is None or court.status == "idle":
            raise errors.court_idle()
        if court.status not in statuses:
            raise errors.court_frozen()
        return court

    @staticmethod
    def _reached(sa: int, sb: int, scoring: int) -> bool:
        """到分判定（§4.3）：分制数且净胜 2——记分落账时当即判。"""
        return max(sa, sb) >= scoring and abs(sa - sb) >= 2

    @staticmethod
    def _preselect(c: LiveCourt) -> str | None:
        """待确认窗的胜方预选定值（§4.3/§4.4，附录 A4 画面不自算）：领先方；
        平分不预选（手点胜方后才能确认）。"""
        if c.status != "pending":
            return None
        if c.sa > c.sb:
            return "a"
        return "b" if c.sb > c.sa else None

    def _require_arrived(self, game_id: int, actor_id: int) -> None:
        """记分类写的资格（§4.1）：名册行且算到场（absent/left 不算）。"""
        row = self.db.execute(
            select(LivePlayer).where(
                LivePlayer.game_id == game_id, LivePlayer.account_id == actor_id
            )
        ).scalar_one_or_none()
        if row is None or row.check not in ARRIVED:
            raise errors.live_forbidden()

    def _require_full_power(self, state: LiveState, game: Game, actor_id: int) -> None:
        """结束对局类/全场类动作收权（§4.2-4.7）：组织者与管理员同权（2.2 §4.6/4.7
        ——被封者与组织者同权，权限只在单个球局内、散场即止）。"""
        if game.organizer_id != actor_id and actor_id not in (state.admins or []):
            raise errors.live_forbidden()

    @staticmethod
    def _oncourt(rows: list[LivePlayer], court_no: int) -> list[LivePlayer]:
        """某片场上的人（行序）——确认/取消/清扫/换人校验共用。"""
        return [
            r for r in rows if r.court_no == court_no and r.court_side in ("a", "b")
        ]

    def _void_court(
        self, rows: list[LivePlayer], by_id: dict[int, LivePlayer], court: LiveCourt
    ) -> None:
        """单片作废的账面动作（§4.7）——cancel 与 sweep-cancel-all 共用：场上的人
        原样回流队首（保行序）、片行清账转 idle、片号前进。"""
        oncourt = self._oncourt(rows, court.court_no)
        queue = [r.id for r in oncourt] + self._queue_ids(rows)
        for r in oncourt:
            r.court_no = None
            r.court_side = None
        for pos, pid in enumerate(queue):
            by_id[pid].queue_pos = pos
        court.status = "idle"
        court.sa = 0
        court.sb = 0
        court.last_winner_side = None
        court.pending_origin = None
        self._bump_court(court)

    def _courts(self, game_id: int) -> list[LiveCourt]:
        return (
            self.db.execute(
                select(LiveCourt)
                .where(LiveCourt.game_id == game_id)
                .order_by(LiveCourt.court_no)
            )
            .scalars()
            .all()
        )

    def _roster_row(self, game_id: int, player_id: int) -> LivePlayer:
        """按名册行 id 取靶行（check/swap/tempo/封撤管理员的动作对象）。"""
        row = self.db.get(LivePlayer, player_id)
        if row is None or row.game_id != game_id:
            raise errors.live_invalid("名册里没有这个人")
        return row

    def _actor_name(self, game_id: int, actor_id: int) -> str:
        row = self.db.execute(
            select(LivePlayer).where(
                LivePlayer.game_id == game_id, LivePlayer.account_id == actor_id
            )
        ).scalar_one_or_none()
        return row.display_name if row else "?"

    @staticmethod
    def _feed_push(state: LiveState, event: dict) -> None:
        """战报事件句留痕（2.2 §4.6/§4.9）：结构化事件行、按发生序追加——句式拼装
        归前端（契约§2 后端不产中文文案）；JSON 列不追踪原地变更，这里整列换新。"""
        state.feed = [*(state.feed or []), event]

    def _is_replay(
        self, game_id: int, court_no: int, winner_side: str, sa: int, sb: int
    ) -> bool:
        """重复确认判定（§5 出错/断网重发）：该片最新一条战报与这笔确认完全一致
        ——当重放回 200 幂等不重落（重放的旧号对不上防线，所以这里先于号检查）。"""
        m = self.db.execute(
            select(LiveMatch)
            .where(LiveMatch.game_id == game_id, LiveMatch.court_no == court_no)
            .order_by(LiveMatch.seq.desc())
            .limit(1)
        ).scalar_one_or_none()
        return (
            m is not None and m.winner_side == winner_side and m.sa == sa and m.sb == sb
        )

    def _rating_of(self, account_id: int) -> int:
        row = self.db.execute(
            select(EloRating).where(EloRating.account_id == account_id)
        ).scalar_one_or_none()
        return RATING_INIT if row is None else row.rating

    def _elo_settle(
        self, winners: list[LivePlayer], losers: list[LivePlayer]
    ) -> list[dict]:
        """结算每人一行、胜队在前（§4.6-2/§4.11）——镜像 utils/elo.ts settleElo：
        双打按两队人均分算期望落到个人、delta=max(1,K*(1-exp))、败方只扣涨分六成、
        地板 400；访客代入 1500 当正常玩家算（去半折口径），行内记 delta 但不落账。"""

        def eff(p: LivePlayer) -> int:
            return RATING_INIT if p.guest else self._rating_of(p.account_id)

        w_avg = sum(eff(p) for p in winners) / len(winners)
        l_avg = sum(eff(p) for p in losers) / len(losers)
        exp = 1 / (1 + 10 ** ((l_avg - w_avg) / 400))
        delta = max(1, _js_round(_ELO_K * (1 - exp)))
        loss = max(1, _js_round(delta * 0.6))
        return [
            {
                "account_id": p.account_id,
                "name": p.display_name,
                "guest": p.guest,
                "rating_before": before,
                "rating_after": max(_ELO_FLOOR, before + d),
                "delta": d,
            }
            for p, before, d in [
                *[(p, eff(p), delta) for p in winners],
                *[(p, eff(p), -loss) for p in losers],
            ]
        ]

    def _apply_elo(self, elo_rows: list[dict], winner_count: int) -> None:
        """正式球友落账（访客不落账不进榜，2.3 裁决）：rating 前进、play+1、胜者
        win+1；行序前 winner_count 个是胜队（_elo_settle 的返回序）。"""
        for i, row in enumerate(elo_rows):
            if row["guest"] or row["account_id"] is None:
                continue
            # 开账后不该走到（start 已首见建行）；空降者由此兜底
            er = self._elo_row(row["account_id"])
            er.rating = row["rating_after"]
            er.play += 1
            if i < winner_count:
                er.win += 1

    def _state_or_none(self, game_id: int) -> LiveState | None:
        return self.db.execute(
            select(LiveState).where(LiveState.game_id == game_id)
        ).scalar_one_or_none()

    def _check_total(self, state: LiveState, base_total_seq: int) -> None:
        """写入口校验·总号（附录 B1）：带的号落后于总账，说明别人先改过全场——
        这笔退回（409 携最新视图），调用方在锁内先过这道再动账。"""
        if base_total_seq != state.total_seq:
            raise errors.live_stale_total()

    def _check_court(self, court: LiveCourt, base_court_seq: int) -> None:
        """写入口校验·片号：只拦该片（总号对、片号旧 = 同片并发），别片不受牵连。"""
        if base_court_seq != court.court_seq:
            raise errors.live_stale_court()

    def _bump_total(self, state: LiveState) -> None:
        state.total_seq += 1  # 任何现场写都往前进一

    def _bump_court(self, court: LiveCourt) -> None:
        court.court_seq += 1  # 该片记分类改动往前进一

    def _elo_row(self, account_id: int) -> EloRating:
        """积分账一人一行：查无则建（起笔 1500、play/win 归零）、有则返——
        start 首见建行与空降兜底共用（访客不建行不进账，2.3 裁决）。"""
        er = self.db.execute(
            select(EloRating).where(EloRating.account_id == account_id)
        ).scalar_one_or_none()
        if er is None:
            er = EloRating(account_id=account_id, rating=RATING_INIT, play=0, win=0)
            self.db.add(er)
        return er

    def _player_row(
        self, p: LivePlayer, *, is_organizer: bool, viewer_id: int | None
    ) -> dict:
        # 考勤分权（2.3 裁决 Q2）：早退迟到不展示给随便扫到的人
        visible = is_organizer or (viewer_id is not None and p.account_id == viewer_id)
        return {
            "id": p.id,
            "account_id": p.account_id,
            "name": p.display_name,
            "guest": p.guest,
            "guarantor_account_id": p.guarantor_account_id,
            "dropin": p.dropin,
            "check": p.check,
            "arrive_at": clock.iso(p.arrive_at) if visible and p.arrive_at else None,
            "left_at": clock.iso(p.left_at) if visible and p.left_at else None,
            "court_no": p.court_no,
            "court_side": p.court_side,
            "skip": p.skip,
            "fire": p.fire,
            "queue_pos": p.queue_pos,
        }
