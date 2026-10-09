"""LiveBook —— 现场总账深模块（docs/2.3）：开账、总账读视图、上传结算链、
两级号并发防线。

批1 落骨架（start/view + 两级号机制），批2 记分链入住（deal/settle-confirm/
settle-overwrite/cancel），批3 2.2 域动作（check/swap/tempo/rules/封撤
管理员）+ 散场链（sweep-cancel-all/end 拆在 live_sweep.py 的 LiveSweepMixin）。
策略内聚在这里，路由只做参数搬运：
- 现场是"另一本账"：locked 局之上由 start 展开（正式球友一人一行 + 随行访客一行），
  散场后 games.ended_at 落库即封存，view 同一形状 = 只读回看（2.3 §4.10）。
- 考勤分权：arrive/left 时刻只有组织者与本人可见，其他人一律 null（2.3 裁决 Q2）。
- 两级号（附录 B1）：全场一个总号（任何现场写 +1）、每片自己的片号（该片写 +1）；
  写入口带"出发时看到的号"，号旧即退回——同片并发才互斥，别片照常。
- 记分本地化（2026-10-09 裁决）：记分在各手机本地，服务端只收「上传结算」——
  谁先传先落；后到不同分回 409 settle_recorded；窗口内可改分重落。
- 写串行：SQLite 无行锁，模块级锁罩住全部写动作（沿 GameBook 先例），check-then-act
  全锁内。
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core import clock, errors
from ..db.models import (
    Account,
    DuprDetail,
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
from .game_views import derive, is_forced
from .live_sweep import ARRIVED, LiveSweepMixin
from .stats import StatsLedger

# 开账起笔的 rules 快照默认值（镜像前端 startLive 起笔，2.2 批2 §4.1）：
# 双打 / 谁下挂 all 占位（推荐重算在前端）/ 按候场队序 / 连庄上限 3
_DEFAULT_RULES = {"doubles": True, "down": "all", "pairing": "queue", "streak_max": 3}
# Elo 娱乐轨初始分（1.4 §3：初始 1200、访客代入同值；前端 utils/elo.ts 的
# ELO_INIT 同值仅作展示兜底位，不担公式）
RATING_INIT = 1200

# Elo 公式与常量唯一源（2026-10-08 收归后端）：K=24、地板 800、败方只扣胜方涨分
# 六成；访客按 1200 代入当正常玩家算——去半折（2.3 修订②；1.4 §3 调参收窄波动
# 区间）。上传/改分窗的 ±预演由 view 的 elo_preview 双分支随视图给出（预演与落账
# 同走 _elo_settle）——前端零公式零镜像，调参只改这一处
_ELO_K = 24.0
_ELO_FLOOR = 800
# 这些码的 409 退回要在错误体里带最新视图（附录 B1：最新画面送来，前端对表用）——
# 防线两码之外，空降防重的 live_duplicate 与传分冲突的 settle_recorded 同样携视图
_VIEW_CODES = frozenset(
    {"live_stale_total", "live_stale_court", "live_duplicate", "settle_recorded"}
)


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
        一行（首见建 EloRating 行 1200），bring N 展开成 N 行随行访客（挂担保人）；
        全员先记 absent、候场队空（报到驱动，check 端点批3）；total_seq 从 1 起。
        触发权 2.5 §4/§8：成局后组织者随时、正式成员开打前两小时内（organizer_id
        形参沿路由旧名，实为开账人），落 started_by=开账人（B1「谁开的账」）。
        幂等：已有 LiveState 直接返视图（散场后再点也只回看，不重开）。"""
        with _write_lock:
            game = self.db.get(Game, game_id)
            if game is None:
                raise errors.game_not_found()
            if self._state_or_none(game_id) is not None:
                return self.view(game_id=game_id, viewer_id=organizer_id)
            now = clock.now()
            self._start_gate(game, organizer_id, now)
            self.db.add(
                LiveState(
                    game_id=game_id,
                    total_seq=1,
                    started_at=now,
                    started_by=organizer_id,
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
                self._expand_formal(
                    game_id=game_id, account_id=entry.account_id, bring=entry.bring
                )
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=organizer_id)

    def _expand_formal(self, *, game_id: int, account_id: int, bring: int) -> None:
        """一条 formal 报名行 → 名册行（start 开账展开与 absorb_join 补册同口径，
        两处行为必须逐字一致——改这里即同时改两处）：本人一行（首见建 EloRating
        行）、bring N 展开成 N 行随行访客（挂担保人）；全员先记 absent。"""
        # person_view 的对外名单一源：在册出昵称、注销者按占位名定格（1.1 隐私口径）
        name = person_view(self.db.get(Account, account_id))["nickname"]
        self.db.add(
            LivePlayer(
                game_id=game_id,
                account_id=account_id,
                display_name=name,
                check="absent",
            )
        )
        self._elo_row(account_id)
        for i in range(bring):
            self.db.add(
                LivePlayer(
                    game_id=game_id,
                    account_id=None,
                    # 访客命名沿前端 startLive：担保人昵称前两字 + 编号
                    display_name=f"{name[:2]}的球友·{i + 1}",
                    guest=True,
                    guarantor_account_id=account_id,
                    check="absent",
                )
            )

    def absorb_join(self, *, game_id: int, account_id: int, bring: int) -> None:
        """开账后报名的补册（局簿 join/候补转正 → 现场接线，2026-10-10 修复批）：
        start 只展开开账那一刻的 formal 行，之后才 join 的人线上有 Entry、名册没
        行——签到没靶（代办到场无从谈起），自签到只能走空降道背「空降」标。这里
        按 start 同口径（_expand_formal）把本人行（含 bring 访客行）补进名册。
        已有本人行（先空降后补报名/重放）不动；没开账不归这里管（留给 start
        展开）。调用方持有局簿锁再进来——单向嵌套（现场从不回手碰局簿），无死锁
        面；formal 与否由调用方把关。"""
        with _write_lock:
            state = self._state_or_none(game_id)
            if state is None or self._account_row(game_id, account_id) is not None:
                return
            self._expand_formal(game_id=game_id, account_id=account_id, bring=bring)
            self._bump_total(state)
            self.db.commit()

    # ---- 记分链（批2）：发牌上报 → 上传结算/改分重落 → 取消 ----

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
            state, game = self._open_write(game_id)
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
                    court = LiveCourt(
                        game_id=game_id, court_no=c["court_no"], scoring=game.scoring
                    )
                    self.db.add(court)
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
                court.court_seq = 1 if fresh else court.court_seq + 1
                # 分制快照开赛定格（2.6 机制A）：改分制只影响此后新开的片
                court.scoring = game.scoring
                for pid in c["a"] + c["b"]:
                    r = by_id[pid]
                    r.court_no = court.court_no
                    r.court_side = "a" if pid in c["a"] else "b"
                    r.queue_pos = None
            self._place_queue(by_id, rest)
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
        """上传结算（2026-10-09 记分本地化裁决）：记分在各手机本地，这片打完谁
        都能把本地账传上来——任意到场者可传，胜方/比分全吃入参；谁先传先落。
        一本账原子：战报行落账 + 双轨积分结算（Elo 娱乐轨 + DUPR 核心轨同
        commit 双写，1.4 裁决 1）+ 人回流补位重排，同一事务要么全成要么全不成。
        胜方必须分高方（平分双方均可）；幂等：重复上传同分同位（断网重发）回
        当前视图 200 不重落；号旧且你看的那场已被别人先落 → 409 settle_recorded
        携已记比分（不当并发冲突吵，纠纷引给组织者）。no_redeal（散场清扫态）：
        回流定格、不排下一场不补位（§4.9-1）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            self._require_arrived(game_id, actor_id)
            court = self._court_or_none(game_id, court_no)
            if court is None:
                raise errors.court_idle()
            # 幂等重放先于号检查（重放的号必旧）：同分同位当断网重发回 200 不重落
            if self._is_replay(game_id, court_no, winner_side, score_a, score_b):
                return self.view(game_id=game_id, viewer_id=actor_id)
            if court.status != "playing":
                raise errors.court_idle()
            if base_total_seq != state.total_seq or base_court_seq != court.court_seq:
                # 号旧改判（实读 _bump 次序裁定）：match.seq 与来者 base_court_seq
                # 同源同拍（无 cancel/no_redeal 漂移时相等）——最新一场 seq 追平或
                # 越过来者所见片号 = 他看的那场已被先传落账，回 settle_recorded；
                # 差不上（另有 cancel 等漂移或纯看旧了）照旧两级号防线退回
                latest = self._latest_match(game_id, court_no)
                if latest is not None and latest.seq >= base_court_seq:
                    raise errors.settle_recorded(latest.sa, latest.sb)
                self._check_total(state, base_total_seq)
                self._check_court(court, base_court_seq)
            if not self._higher_side_wins(winner_side, score_a, score_b):
                raise errors.live_invalid("分低的一方当不了胜方")
            # —— 一本账（§4.6-2）：战报 + 双轨积分 + 回流，一个 commit ——
            rows = self._roster(game_id)
            by_id = {r.id: r for r in rows}
            oncourt = self._oncourt(rows, court_no)
            winners = [r for r in oncourt if r.court_side == winner_side]
            losers = [r for r in oncourt if r.court_side != winner_side]
            elo_rows = self._elo_settle(winners, losers)
            ended = clock.now()
            match = LiveMatch(
                game_id=game_id,
                court_no=court_no,
                seq=court.seq,
                winners=[_snapshot(r) for r in winners],
                losers=[_snapshot(r) for r in losers],
                sa=score_a,
                sb=score_b,
                winner_side=winner_side,
                ended_at=ended,
                elo_rows=elo_rows,
            )
            self.db.add(match)
            self._apply_elo(elo_rows, len(winners))
            self._apply_dupr(
                match=match,
                ended_at=ended,
                winners=winners,
                losers=losers,
                score_w=score_a if winner_side == "a" else score_b,
                score_l=score_b if winner_side == "a" else score_a,
            )
            queue = self._queue_ids(rows)
            if no_redeal:
                # 清扫态：人只回流定格——不排下一场不补位，场上的人按行序接队尾
                for r in oncourt:
                    r.court_no = None
                    r.court_side = None
                    queue.append(r.id)
                court.status = "idle"
            else:
                stats = StatsLedger(self.db)
                rates = stats.pairing_ratings([r.account_id for r in rows])
                dicts = [
                    {
                        "id": r.id,
                        "court_no": r.court_no,
                        "court_side": r.court_side,
                        # 均衡配对换源吃 DUPR（1.4 §6）：rating 键恒喂当前派生分
                        "rating": rates[r.account_id],
                    }
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
                # 分制快照续场同刷新（2.6 机制A）：确认即开的下一场也是"新开片"
                court.scoring = game.scoring
            for r in rows:
                if r.court_side is not None:
                    r.queue_pos = None
            self._place_queue(by_id, queue)
            self._bump_court(court)
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def settle_overwrite(
        self,
        *,
        game_id: int,
        actor_id: int,
        court_no: int,
        winner_side: str,
        score_a: int,
        score_b: int,
        base_total_seq: int,
        base_court_seq: int,
    ) -> dict:
        """改分重落（2026-10-09 裁决③，全权）：上传传错了分、或事后议定改判——
        窗口=这笔要改的仍是该片最新一场落账（下一场一旦落账即出窗，沿「战报
        不可篡改」）。窗口由片号闸把关：目标取该片 seq 最大的战报行（实读 _bump
        次序——seq 即该片第几场，最大 seq 行就是「最新已落账且下一场未落账」那场），
        改分人出发画面里的片号必须仍是当前片号，否则 409 退回。改的是账面：战报行
        按新胜方重划四人（同一批人，名单快照原行换边）+ Elo 反算重加（按旧快照
        逐人 rating-=delta、play/win 按旧胜方反调，再用还原值走同一算路重加——
        中间若有他场落账的增量不受牵连）+ DUPR 明细删行重插、逐人窗口重算；
        物理面不动——回流已发生、片序/考勤/账单/ended_at 一概不回头。同载荷重复
        覆盖幂等 200（重放先于号检查，沿 settle_confirm 先例）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            self._require_full_power(state, game, actor_id)
            match = self._latest_match(game_id, court_no)
            if match is not None and self._same_result(
                match, winner_side, score_a, score_b
            ):
                return self.view(game_id=game_id, viewer_id=actor_id)
            self._check_total(state, base_total_seq)
            court = self._court_or_none(game_id, court_no)
            if court is None:
                raise errors.live_invalid("这片不在场上，没法改分")
            self._check_court(court, base_court_seq)
            if match is None:
                raise errors.live_invalid("这片还没有落账的对局")
            if not self._higher_side_wins(winner_side, score_a, score_b):
                raise errors.live_invalid("分低的一方当不了胜方")
            # 名单快照没记边位，边由旧 winner_side 反推：同边还是同批人，换胜方即换边
            side_a = match.winners if match.winner_side == "a" else match.losers
            side_b = match.losers if match.winner_side == "a" else match.winners
            snap_w, snap_l = (
                (side_a, side_b) if winner_side == "a" else (side_b, side_a)
            )
            by_id = {r.id: r for r in self._roster(game_id)}
            winners = [by_id[s["id"]] for s in snap_w]
            losers = [by_id[s["id"]] for s in snap_l]
            # Elo 反算两段同 commit：先按旧快照退回这一场的账（rating 减 delta、
            # play 减一、旧胜方 win 减一——访客无行不调），再按新划分重加重落
            for row in match.elo_rows:
                if row["guest"] or row["account_id"] is None:
                    continue
                er = self._elo_row(row["account_id"])
                er.rating -= row["delta"]
                er.play -= 1
            for row in match.elo_rows[: len(match.winners)]:
                if not row["guest"] and row["account_id"] is not None:
                    self._elo_row(row["account_id"]).win -= 1
            elo_rows = self._elo_settle(winners, losers)
            match.winner_side = winner_side
            match.sa = score_a
            match.sb = score_b
            match.winners = snap_w
            match.losers = snap_l
            match.elo_rows = elo_rows
            self._apply_elo(elo_rows, len(winners))
            # DUPR 两轨独立（输入快照吃派生分、与 Elo 无关）：删旧明细按新胜负重插
            self.db.execute(delete(DuprDetail).where(DuprDetail.match_id == match.id))
            self._apply_dupr(
                match=match,
                ended_at=match.ended_at,
                winners=winners,
                losers=losers,
                score_w=score_a if winner_side == "a" else score_b,
                score_l=score_b if winner_side == "a" else score_a,
            )
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
        base_total_seq: int,
        base_court_seq: int,
    ) -> dict:
        """取消对局（§4.7，全权）：整场作废——不计分不进战绩；场上的人原样回流
        候场队首（补偿没打成的，沿 2.2 §4.12）；该片腾出来（idle）等重新发牌。
        （取消本就不补位，不带上传那枚 no_redeal——清扫链路统一参数只到结算为止）"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            court = self._court_writable(game_id, court_no)
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
        到场不自动发牌——发牌算法在前端，够人由前端 deal 上报。
        2.5：本账开张后第一个到场签到的人自动暂管现场（组织者首签不授、已授不重授）。"""
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
            # 自动管理员两路同权（修C）：签到端点与空降扫码共用（扫码即签到），
            # 落账后判——"第一个"含本行这次
            self._maybe_grant_first_admin(state, game, row, rows)
            self._place_queue(by_id, queue)
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
        outId 离片回队尾；只收在打片（idle 片没人可换，court_idle 退回）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, _game = self._open_write(game_id)
            self._require_arrived(game_id, actor_id)
            self._check_total(state, base_total_seq)
            out = self._roster_row(game_id, out_id)
            inn = self._roster_row(game_id, in_id)
            if out.court_no is None or out.court_side is None:
                raise errors.live_invalid("被换下的人不在场上")
            court = self._court_writable(game_id, out.court_no)
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
            self._place_queue(by_id, queue)
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
                        self._place_queue(by_id, queue)
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
        scoring: int | None = None,
    ) -> dict:
        """规则四件套+场地片数+分制（2.2 §4.7 收权，全场号拦）：只动显式给的字段。
        四件套落总账头（下一场起按新规，在打片照旧打完）；courts_count 改片数——
        不得少于在用片数，缩片先撤空闲片（在打/待确认的片不能收）。分制切真
        （2.6 机制A）：写 game 列真值，在打片快照不回头、新开片用新制。"""
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
            if scoring is not None:
                game.scoring = scoring
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

    # ---- 1.3 记账通道（附录 B1）：空降报到 / 现场带访客 ----
    # 名册外的人进总账的唯二入口：不进账则「空降照摊、朋友份额归担保人」无从算起。

    def dropin(self, *, game_id: int, actor_id: int, base_total_seq: int) -> dict:
        """空降报到（2.2 §4.4）：没报名扫码直入——名册无本人行则新增一行
        （dropin 标记；摊钱人头 +1，§5「没报名扫码直接打的照摊」），考勤沿用
        check 端点归一口径（未到首报且已过开球时刻=late 否则 ok）进队尾；不建
        Entry 不占 formal 名额。幂等重放先于号检查（沿 settle_confirm 重放先例）：
        空降行重复点静默回最新画面；名册已有非空降本人行（正式球友误走此道，正常
        前端路径到不了）409 live_duplicate 携视图——同账号不得建双行，防御保留。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            row = self._account_row(game_id, actor_id)
            if row is not None:
                if row.dropin:
                    return self.view(game_id=game_id, viewer_id=actor_id)
                raise errors.live_duplicate()
            self._check_total(state, base_total_seq)
            now = clock.now()
            new = LivePlayer(
                game_id=game_id,
                account_id=actor_id,
                # 对外名单一源：在册出昵称、注销者按占位名定格（同 start 展开）
                display_name=person_view(self.db.get(Account, actor_id))["nickname"],
                dropin=True,
                check="late" if now > game.start_at else "ok",
                arrive_at=now,
            )
            self.db.add(new)
            self.db.flush()  # 取新行 id 进队尾（queue_pos 重排与 check 端点同款）
            rows = self._roster(game_id)
            by_id = {r.id: r for r in rows}
            queue = self._queue_ids(rows)
            queue.append(new.id)
            self._place_queue(by_id, queue)
            # 空降扫码即签到：自动管理员与 check 端点同权（修C）
            self._maybe_grant_first_admin(state, game, new, rows)
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def guests(
        self,
        *,
        game_id: int,
        actor_id: int,
        guarantor_id: int,
        count: int,
        name: str | None,
        base_total_seq: int,
    ) -> dict:
        """现场带访客（§5/§8 裁决二：带朋友的份额归担保人）：count 位访客一人一行
        挂 guarantor 名册行名下——guarantor_account_id 是出账归账键（1+名下访客
        人头），须是账号行（访客挂不到访客名下）；到场即带（check=ok、落 arrive_at）
        排队尾。命名沿前端 addGuests 规则后端重做：空名=担保名前两字+的球友、多人
        具名=name·i、单人具名照给。访客不建 EloRating 行不进榜（2.3 裁决）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            self._require_full_power(state, game, actor_id)
            self._check_total(state, base_total_seq)
            guarantor = self._roster_row(game_id, guarantor_id)
            if guarantor.account_id is None:
                raise errors.live_invalid("访客挂不到访客名下")
            now = clock.now()
            made: list[LivePlayer] = []
            for i in range(count):
                if not name:
                    display = f"{guarantor.display_name[:2]}的球友"
                elif count > 1:
                    display = f"{name}·{i + 1}"
                else:
                    display = name
                row = LivePlayer(
                    game_id=game_id,
                    account_id=None,
                    display_name=display,
                    guest=True,
                    guarantor_account_id=guarantor.account_id,
                    check="ok",
                    arrive_at=now,
                )
                self.db.add(row)
                made.append(row)
            self.db.flush()  # 取新行 id 排队尾
            by_id = {r.id: r for r in self._roster(game_id)}
            queue = self._queue_ids(list(by_id.values()))
            queue.extend(r.id for r in made)
            self._place_queue(by_id, queue)
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    # ---- 总账读视图（进行中与散场后同一形状：散场后 = 只读回看） ----

    def view(self, *, game_id: int, viewer_id: int | None) -> dict:
        """总账读（2.3 附录 A4：画面一个字不自算，全给定值）。考勤时刻按 viewer
        分权——组织者或本人见 arrive/left，其他人 null；带队 total_seq 与各片
        court_seq（契约总则 §4 预留的轮次/版本字段落地）。身份块（两旗+组织者
        账号）随视图直读，前端不再本地拼 viewer（2026-10-08 修订，翻批4a 的
        「视图不带身份块」）。在打片随附 ±积分预演双分支（elo_preview——预演与
        落账同走 _elo_settle，2026-10-08 收归后端单源；2026-10-09 记分本地化改挂
        playing 片：Elo 与比分无关，服务端无需知道本地比分）。未开账 → 404。"""
        state = self._state_or_none(game_id)
        if state is None:
            raise errors.live_not_found()
        game = self.db.get(Game, game_id)
        is_organizer = viewer_id is not None and game.organizer_id == viewer_id
        stats = StatsLedger(self.db)
        roster = self._roster(game_id)
        # 代位分与小人一次查齐（3s 轮询 + 每个写动作响应都走这里，逐人查会放大成 N+1；
        # chibi 随行下发——前端名册头像不再向演示世界借位，2026-10-10 mock 退役）
        rates = stats.pairing_ratings([p.account_id for p in roster])
        chibis = {
            a.id: a.chibi
            for a in self.db.execute(
                select(Account).where(
                    Account.id.in_([p.account_id for p in roster if p.account_id])
                )
            ).scalars()
        }
        rows = [
            self._player_row(
                p,
                is_organizer=is_organizer,
                viewer_id=viewer_id,
                dupr_value=rates[p.account_id],
                chibi=chibis.get(p.account_id),
            )
            for p in roster
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
            "fee": self._fee_block(game, roster),
            "total_seq": state.total_seq,
            "round": state.round,
            "admins": state.admins or [],
            # 身份块（2026-10-08 修订）：viewer 旗直发——本就按 viewer 逐请求现算
            # （考勤分权同路），无缓存代价；organizer_account_id 供代收判定找
            # 组织者名册行。游客（无钥匙）两旗恒 false
            "is_organizer": is_organizer,
            "is_full_power": is_organizer
            or (viewer_id is not None and viewer_id in (state.admins or [])),
            "organizer_account_id": game.organizer_id,
            "feed": state.feed or [],
            "courts_count": state.courts_count,
            "rules": {
                # 当前生效分制（改后下一场起生效）；在打片自己定格的旧制看 courts[].scoring
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
                    "court_seq": c.court_seq,
                    # 片分制快照（开赛定格）：在打片卡头按它亮数与本地判到分，
                    # 不吃 rules 块新值
                    "scoring": c.scoring,
                    # 在打片的 ±积分预演双分支（上传/改分窗两套现成数，§4.11）；
                    # 其余片 null
                    "elo_preview": (
                        self._elo_preview(c, roster) if c.status == "playing" else None
                    ),
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

    def _fee_block(self, game: Game, roster: list[LivePlayer] | None = None) -> dict:
        """费用亮数块（1.3 §3 散场确认页）：总价=订场登记真值（null=未定）；人头=
        账单口径的摊钱人头——正式/空降行每人 1 + 名下访客行数（与出账引擎同尺，
        亮数与实摊一个数）；per_head=floor 向下抹零，未定价局为 null 但 heads 照给
        （亮「总价未定 · N 人」用）。roster 由 view 顺手递入免二次查（单独调用自查）。"""
        rows = roster if roster is not None else self._roster(game.id)
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
                if e.code in _VIEW_CODES and e.view is None:
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

    def _maybe_grant_first_admin(
        self, state: LiveState, game: Game, row: LivePlayer, rows: list[LivePlayer]
    ) -> None:
        """自动管理员（2.5 §4.2/§8）：账开张后第一个签到的球友暂管现场。签到两路
        共用（check 端点 + 空降 dropin——扫码即签到，0号两路同权），落账后调用：
        "第一个" = 除本行这次外此前无账号行 ARRIVED。只数账号行——访客行随带即到
        （check=ok）不参与判定也不触发授予（组织者先带访客不挡球友首签）；组织者
        首签不授（到场自然说了算）、已是管理员不重授（含组织者预先封的）。"""
        if (
            row.account_id is None
            or row.check not in ARRIVED
            or row.account_id == game.organizer_id
            or row.account_id in (state.admins or [])
        ):
            return
        if any(
            r.check in ARRIVED
            for r in rows
            if r.account_id is not None and r.id != row.id
        ):
            return
        state.admins = [*(state.admins or []), row.account_id]
        self._feed_push(
            state,
            {
                "kind": "auto_admin",
                "actor": row.display_name,
                "target": row.display_name,
                "at": clock.iso(clock.now()),
            },
        )

    def _start_gate(self, game: Game, actor_id: int, now: datetime) -> None:
        """开账触发权（2.5 §4.4/§8，幂等检查之后、落账之前）：先成局再开账——
        死局（待处置/已终止/已撤局）谁都不放行，组织者同规（§8 Q3 现有行为收紧）；
        必开标志即刻成局：手动锁必打或已订场登记即算，不等截止懒判定（§4.4
        "离开打还有两个多小时也行"）；成局后组织者随时、正式成员开打前两小时内
        （定值窗，§8 裁决）；候补与未报名不触发开账（app 内不服务，§8 候补裁决）。"""
        status = derive(game, now)
        if status in ("done", "terminated", "cancelled", "pending"):
            # done 也算死局：锁定局过了散场时刻仍没人开账，隔天开不出新账（修B）
            raise errors.live_requires_forced("该局已取消或已终止")
        # 必开标志即刻成局（is_forced 单一源）：有标志不等截止懒判定
        if not is_forced(game) and status not in ("locked", "live"):
            raise errors.live_requires_forced()
        if game.organizer_id == actor_id:
            return  # 组织者不受两小时窗限（2.5 场景 4.4）
        formal = self.db.execute(
            select(Entry).where(
                Entry.game_id == game.id,
                Entry.account_id == actor_id,
                Entry.standing == "formal",
            )
        ).scalar_one_or_none()
        if formal is None:
            raise errors.live_entry_required()
        # 两小时窗与前端 format.ts cardLiveEntry 的 2*3600_000 同源——2.5 §4.2 两端各算
        if now < game.start_at - timedelta(hours=2):
            raise errors.live_too_early()

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

    def _place_queue(self, by_id: dict[int, LivePlayer], queue: list[int]) -> None:
        """候场队落位单点（queue 即名次、队首 0）：发牌/确认/取消/换人/歇连/空降/
        带访客/清片八处写动作的共同尾巴——漏落一行即静默错序，收进一个口。"""
        for pos, pid in enumerate(queue):
            by_id[pid].queue_pos = pos

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

    def _court_writable(self, game_id: int, court_no: int) -> LiveCourt:
        """片状态机校验（记分本地化后只有两态）：没在打 → court_idle，在打返回片行。"""
        court = self._court_or_none(game_id, court_no)
        if court is None or court.status != "playing":
            raise errors.court_idle()
        return court

    def _account_row(self, game_id: int, account_id: int) -> LivePlayer | None:
        """按账号取名册行（一人至多一行）：到场资格 / feed 署名 / 空降防重共用。"""
        return self.db.execute(
            select(LivePlayer).where(
                LivePlayer.game_id == game_id, LivePlayer.account_id == account_id
            )
        ).scalar_one_or_none()

    def _require_arrived(self, game_id: int, actor_id: int) -> None:
        """记分类写的资格（§4.1）：名册行且算到场（absent/left 不算）。"""
        row = self._account_row(game_id, actor_id)
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
        原样回流队首（保行序）、片行转 idle、片号前进。"""
        oncourt = self._oncourt(rows, court.court_no)
        queue = [r.id for r in oncourt] + self._queue_ids(rows)
        for r in oncourt:
            r.court_no = None
            r.court_side = None
        self._place_queue(by_id, queue)
        court.status = "idle"
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
        row = self._account_row(game_id, actor_id)
        return row.display_name if row else "?"

    @staticmethod
    def _feed_push(state: LiveState, event: dict) -> None:
        """战报事件句留痕（2.2 §4.6/§4.9）：结构化事件行、按发生序追加——句式拼装
        归前端（契约§2 后端不产中文文案）；JSON 列不追踪原地变更，这里整列换新。"""
        state.feed = [*(state.feed or []), event]

    def _latest_match(self, game_id: int, court_no: int) -> LiveMatch | None:
        """该片最新一场战报（seq 最大即最新——seq 是该片第几场计数，实读 deal/
        settle_confirm 的 _bump 次序单调不回退）：重放判定与改分重落共用。"""
        return self.db.execute(
            select(LiveMatch)
            .where(LiveMatch.game_id == game_id, LiveMatch.court_no == court_no)
            .order_by(LiveMatch.seq.desc())
            .limit(1)
        ).scalar_one_or_none()

    @staticmethod
    def _higher_side_wins(winner_side: str, sa: int, sb: int) -> bool:
        """胜方必须分高方（平分双方均可当胜方）：settle_confirm / settle_overwrite
        两个落账入口共用的入参判件（winner_side 非 a/b 不在此拦，路由 Literal 兜底）。"""
        return not (
            (winner_side == "a" and sa < sb) or (winner_side == "b" and sb < sa)
        )

    @staticmethod
    def _same_result(match: LiveMatch, winner_side: str, sa: int, sb: int) -> bool:
        """战报行与这笔（胜方+比分三元全等）：_is_replay 断网重放判等与
        settle_overwrite 重复覆盖判等共用同一谓词——同一比较只写一遍。"""
        return match.winner_side == winner_side and match.sa == sa and match.sb == sb

    def _is_replay(
        self, game_id: int, court_no: int, winner_side: str, sa: int, sb: int
    ) -> bool:
        """重复上传判定（§5 出错/断网重发）：该片最新一条战报与这笔完全一致——
        当重放回 200 幂等不重落（重放的旧号对不上防线，所以这里先于号检查）。"""
        m = self._latest_match(game_id, court_no)
        return m is not None and self._same_result(m, winner_side, sa, sb)

    def _rating_of(self, account_id: int) -> int:
        row = self.db.execute(
            select(EloRating).where(EloRating.account_id == account_id)
        ).scalar_one_or_none()
        return RATING_INIT if row is None else row.rating

    def _elo_preview(self, court: LiveCourt, roster: list[LivePlayer]) -> dict:
        """在打片的 ±积分预演双分支（§4.11，2026-10-08 收归后端单源；2026-10-09
        记分本地化改挂 playing 片——Elo 分差只看两队现分与谁胜、与比分无关，
        服务端无需知道各手机本地比分）：A 胜 / B 胜各算一套随视图给出，上传窗
        点胜方在两套现成数间切换（当场变、不等网络仍成立）。取序与 settle_confirm
        同一条路（_oncourt 语义：名册序 + 片位过滤），预演=落账：上传响应所选
        分支的 elo_rows 与这里逐行一致。"""
        oncourt = [
            p
            for p in roster
            if p.court_no == court.court_no and p.court_side in ("a", "b")
        ]
        a = [p for p in oncourt if p.court_side == "a"]
        b = [p for p in oncourt if p.court_side == "b"]
        return {"a": self._elo_settle(a, b), "b": self._elo_settle(b, a)}

    def _elo_settle(
        self, winners: list[LivePlayer], losers: list[LivePlayer]
    ) -> list[dict]:
        """结算每人一行、胜队在前（§4.6-2/§4.11）——Elo 唯一算路（2026-10-08 起
        前端零公式：确认窗预演的 elo_preview 与落账 elo_rows 都出自本函数）：
        双打按两队人均分算期望落到个人、delta=max(1,K*(1-exp))、败方只扣涨分
        六成、地板 800；访客代入 1200 当正常玩家算（去半折口径），行内记 delta
        但不落账。"""

        def eff(p: LivePlayer) -> int:
            return RATING_INIT if p.guest else self._rating_of(p.account_id)

        w_avg = sum(eff(p) for p in winners) / len(winners)
        l_avg = sum(eff(p) for p in losers) / len(losers)
        exp = 1 / (1 + 10 ** ((l_avg - w_avg) / 400))
        delta = max(1, round(_ELO_K * (1 - exp)))
        loss = max(1, round(delta * 0.6))
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

    def _apply_dupr(
        self,
        *,
        match: LiveMatch,
        ended_at: datetime,
        winners: list[LivePlayer],
        losers: list[LivePlayer],
        score_w: int,
        score_l: int,
    ) -> None:
        """DUPR 核心轨双写（1.4 §2：同 commit 落第二本账）——访客按 3.0 代入
        快照参与期望、自身不落账（§4）；注册球员每人一行明细、随后窗口重放。"""
        self.db.flush()  # 战报行先取 id（明细锚点，同事务）
        stats = StatsLedger(self.db)

        def side(players: list[LivePlayer]) -> list[tuple[int | None, float]]:
            # 访客 account_id=None：pairing_rating 对 None 出 3.0（恒定标准分）
            return [(p.account_id, stats.pairing_rating(p.account_id)) for p in players]

        stats.settle(
            game_id=match.game_id,
            match_id=match.id,
            ended_at=ended_at,
            winner_side=side(winners),
            loser_side=side(losers),
            score_w=score_w,
            score_l=score_l,
        )

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
        """积分账一人一行：查无则建（起笔 1200、play/win 归零）、有则返——
        start 首见建行与空降兜底共用（访客不建行不进账，2.3 裁决）。"""
        er = self.db.execute(
            select(EloRating).where(EloRating.account_id == account_id)
        ).scalar_one_or_none()
        if er is None:
            er = EloRating(account_id=account_id, rating=RATING_INIT, play=0, win=0)
            self.db.add(er)
        return er

    def _player_row(
        self,
        p: LivePlayer,
        *,
        is_organizer: bool,
        viewer_id: int | None,
        dupr_value: float,
        chibi: str | None = None,
    ) -> dict:
        # 考勤分权（2.3 裁决 Q2）：早退迟到不展示给随便扫到的人
        visible = is_organizer or (viewer_id is not None and p.account_id == viewer_id)
        return {
            "id": p.id,
            "account_id": p.account_id,
            "name": p.display_name,
            # 开账时定格的账号小人（访客无账号行 → None，前端按缺省形象渲染）
            "chibi": json.loads(chibi) if chibi else None,
            "guest": p.guest,
            # DUPR 配平代位分（1.4 §6 修订：访客/无派分行统一 2.5、有派分行吃派生分）——
            # 值由 view 用 pairing_ratings 批量预算后递入
            "dupr": dupr_value,
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
