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

import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from itertools import combinations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core import clock, errors, logs
from ..db.models import (
    ELO_RATING_INIT,
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
from .bills import bill_heads
from .cosmetics import dress_fields
from .game_views import derive, is_forced
from .live_rotation import ARRIVED
from .live_sweep import LiveSweepMixin
from .playlog import is_my_game_at
from .stats import StatsLedger

# 开账起笔的 rules 快照默认值——开场只有这一份，约球局与直接开场同吃，
# 不收任何来源特判（现场页样子只由这一局的数据决定，与怎么开场无关）：
# 双打 / 2 人下 / 轮换优先 / 连打上限 2。连打上限的自适应默认随「谁下」的档走
# （输家下=3，其余=2），且只在切档时重置；新局永不修正，起笔必须是起笔档
# 自己的默认值（2 人下档=2）
_DEFAULT_RULES = {"doubles": True, "down": "n2", "pairing": "partner", "streak_max": 2}
_PAIRING_MODES = ("queue", "balance", "partner", "even")
# Elo 娱乐轨初始分单一源在 models.ELO_RATING_INIT（建行默认值同源）
RATING_INIT = ELO_RATING_INIT

# Elo 公式与常量唯一源（2026-10-08 收归后端）：K=24、地板 800、败方只扣胜方涨分
# 六成；访客按 1200 代入当正常玩家算——去半折（2.3 修订②；1.4 §3 调参收窄波动
# 区间）。上传/改分窗的 ±预演由 view 的 elo_preview 双分支随视图给出（预演与落账
# 同走 _elo_settle）——前端零公式零镜像，调参只改这一处
_ELO_K = 24.0
_ELO_FLOOR = 800
# 这些码的退回要在错误体里带最新视图（附录 B1：最新画面送来，前端对表用）——
# 防线两码之外，空降防重的 live_duplicate、传分冲突的 settle_recorded 与越界
# 暂停发牌的 rotation_overflow 同样携视图（越界时主操作已提交，画面保持最新
# 只剩这一条路说给人听）
_VIEW_CODES = frozenset(
    {
        "live_stale_total",
        "live_stale_court",
        "live_duplicate",
        "settle_recorded",
        "rotation_overflow",
    }
)


def _snapshot(p: LivePlayer) -> dict:
    """战报名单快照（LiveMatch.winners/losers 元素）：id 是名册行 id。"""
    return {"id": p.id, "name": p.display_name, "guest": p.guest}


def _roster_seqs(rows: list[LivePlayer]) -> dict[int, int]:
    """到场先后（排位第④档兜底）：签到落账时刻 arrive_at 升序、同刻行 id 决胜
    ——id 随建行单调，同刻并列时比时刻戳本身更稳定。真实流里到场者必带
    arrive_at（check 首报落账），没时刻的行只可能是未到/早退——不可发不参与
    排位，名次共享最小值 0 纯作保序防御（stable 序下保持传入序）。"""
    ranked = sorted(
        (r for r in rows if r.arrive_at is not None), key=lambda r: (r.arrive_at, r.id)
    )
    seqs = {r.id: i + 1 for i, r in enumerate(ranked)}
    for r in rows:
        seqs.setdefault(r.id, 0)
    return seqs


def _rotation_rows(
    rows: list[LivePlayer],
    rates: dict,
    tonight: dict[int, int],
    seqs: dict[int, int],
) -> list[dict]:
    """轮换纯函数（live_rotation）的喂行单一源——全键契约 id/court_no/court_side/
    check/skip/fire/court_mark/rating/streak/wait_batch/tonight/roster_seq，结算回流
    与补片共用；喂行散写漏键是 2.8 前排位规矩从未被喂到的病根，此后只许走这里。
    tonight（今晚已打场次）与 seqs（到场先后）由调用方预算递入：tonight 从
    live_matches 实时派生（改分重落/取消自动对齐由重算天然成立）。"""
    return [
        {
            "id": r.id,
            "court_no": r.court_no,
            "court_side": r.court_side,
            "check": r.check,
            "skip": r.skip,
            "fire": r.fire,
            "court_mark": r.court_mark,
            # 均衡配对换源吃 DUPR（1.4 §6）：rating 键恒喂当前派生分
            "rating": rates[r.account_id],
            "streak": r.streak,
            "wait_batch": r.wait_batch,
            "tonight": tonight.get(r.id, 0),
            "roster_seq": seqs[r.id],
        }
        for r in rows
    ]


def _apply_rotation(by_id: dict[int, LivePlayer], dicts: list[dict], mark: int) -> None:
    """纯函数改完的行落回 ORM（_rotation_rows 的逆向，两端键对）：去向
    court_no/court_side、取队时「轮到即消耗」扣掉的 skip、连打归零与连战兑现
    （已发生在纯函数行上，照抄即可）；这次从候场新落位的行盖上场章 mark（落位
    时刻的总号——只盖不清：留场的章不动，全下全上又回来的算没离开过）；
    候场序 queue_pos 不在此处（归 _place_queue）。"""
    for d in dicts:
        r = by_id[d["id"]]
        if d["court_no"] is not None and r.court_no is None:
            r.court_mark = mark
        r.court_no = d["court_no"]
        r.court_side = d["court_side"]
        r.skip = d["skip"]
        r.streak = d["streak"]
        r.wait_batch = d["wait_batch"]
        r.fire = d["fire"]


def _guest_display_name(
    guarantor_name: str, name: str | None, i: int, count: int, *, numbered: bool
) -> str:
    """随行访客的定格名，两路同吃一份零件（担保名前两字+「的球友」/具名+「·序号」）：
    空名兜底=担保名前两字+的球友；具名多人=name·序号、单人照给。numbered 只归
    开账展开路（start/absorb_join 同口径逐字一致）——空名也带序号防重名；现场带客
    沿旧例不编号。两支空名形不一致是产品现状，收编的是零件不是统一行为。"""
    if not name:
        tail = f"·{i + 1}" if numbered else ""
        return f"{guarantor_name[:2]}的球友{tail}"
    if count > 1:
        return f"{name}·{i + 1}"
    return name


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
        幂等：已有 LiveState 直接返视图（散场后再点也只回看，不重开）。
        开场规则只有 _DEFAULT_RULES 一份，不收来源参数——约球与直接开场同路。"""
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
                    **{
                        **_DEFAULT_RULES,
                        "pairing": (
                            game.rotation
                            if game.rotation in _PAIRING_MODES
                            else _DEFAULT_RULES["pairing"]
                        ),
                    },
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
                    display_name=_guest_display_name(
                        name, None, i, bring, numbered=True
                    ),
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
            # 出口豁免档（autofill=False）：新补行必 absent 无队可取（同 start
            # 一族结构性不补片）；号跳+提交归 _finish 统一收尾
            self._finish(state, game_id=game_id, actor_id=account_id, autofill=False)

    # ---- 记分链（批2）：发牌上报 → 上传结算/改分重落 → 取消 ----

    def deal(self, *, game_id: int, actor_id: int, base_total_seq: int) -> dict:
        """手动一键排阵（2.8 §4.5）：按下=让后端补满所有空片——取队真值收编后端
        （live_rotation 单一源），出口补片即本语义（_finish 默认档），空手幂等回
        最新视图。全权本事（一键排阵是排批按钮；事件驱动补片已归各写动作出口，
        普通球友无需再调）：验收 10 非全权 403。载荷只剩出发号（旧 courts 牌面
        收下即丢的兼容面随前端薄壳批退役，DealIn 已无 courts 字段）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            self._require_full_power(state, game, actor_id)
            self._check_total(state, base_total_seq)
            self._finish(state, game_id=game_id, actor_id=actor_id)
        return self.view(game_id=game_id, viewer_id=actor_id)

    def redeal(
        self,
        *,
        game_id: int,
        actor_id: int,
        court_no: int,
        base_total_seq: int,
        base_court_seq: int,
    ) -> dict:
        """重排这片（2.8 §4.4，全权）：取消+立刻重发二合一——在打片场上的人原样
        回流队首（_void_court 与 cancel 同一段账面动作，不抄第三份），随即同事务
        走出口补片按最新规矩（歇/连战/考勤）重发，回流+出口一拍完成、恰一 bump；
        空片重排=补片（空手到出口即得）。责任担保在按下的人（「这场还没人开始
        记分」人眼担保——比分在各手机本地服务器判不了），二次确认在前端页面层；
        清扫态拦截也在前端（sweepState 不亮钮，后端无全局旗，与 no_redeal 同哲学）。
        散场后写被 _open_write 拒。幂等口径：不设 settle 式重放——同拍重放的号
        必已旧、两级号闸 409 携最新视图退回；回流+补片本身无重复人风险（重排把
        同一批人再排一次也只是同一落位）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            self._require_full_power(state, game, actor_id)
            self._check_total(state, base_total_seq)
            court = self._court_or_none(game_id, court_no)
            if court is not None:  # 没开过行的空片无片号可比（视图端缺行补 0）
                self._check_court(court, base_court_seq)
            if court is not None and court.status == "playing":
                rows = self._roster(game_id)
                self._void_court(rows, {r.id: r for r in rows}, court)
            self._finish(state, game_id=game_id, actor_id=actor_id)
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
        回流定格、不排下一场不补位（§4.9-1）——出口补片同拍豁免（清扫要清出空片
        好散场）。回流补位走 live_rotation 排位引擎（2.9）：歇轮跳过并消耗、未到
        不发，谁上谁下按排位五段典序（连打→等待批次→今晚场次→连战→到场先后）
        ——喂行与写回经 _rotation_rows/_apply_rotation 一对口；顺手填别的空片归
        出口（三默认）。"""
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
            elo_rows = self._elo_settle(
                winners, losers, self._ratings_of([r.account_id for r in oncourt])
            )
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
            # DUPR 双写只在两边都有人时结算（单边空片被抽空后无胜负两队可算；
            # 战报行照落——名单与比分是事实，积分不动账）
            if winners and losers:
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
                self._reflow(oncourt, queue, court)
            else:
                # —— 排位口径备键：轮转批次前进一、本片场上人连打各 +1、全员预盖
                # 新章（谁下要进 requeue 才定，只能片上全员统一盖——留场者的脏章
                # 无害，在场不算等待）。战报行已入会话，flush 后今晚口径必含本场。
                state.rotation_batch += 1
                for r in oncourt:
                    r.streak += 1
                    r.wait_batch = state.rotation_batch
                self.db.flush()  # 盖章/战报先出账：越界时回滚只回滚发牌段
                stats = StatsLedger(self.db)
                rates = stats.pairing_ratings([r.account_id for r in rows])
                facts = self._history_facts(game_id)
                dicts = _rotation_rows(
                    rows, rates, facts["tonight"], _roster_seqs(rows)
                )
                try:
                    with self.db.begin_nested():
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
                            streak_max=state.streak_max,
                            facts=facts,
                        )
                        _apply_rotation(by_id, dicts, state.total_seq)
                        court.status = "playing"
                        court.seq += 1
                        # 分制快照续场同刷新（2.6 机制A）：确认即开的下一场也是"新开片"
                        court.scoring = game.scoring
                        self.db.flush()  # 发牌段落定才出 SAVEPOINT：越界回滚得干净
                except live_rotation.RotationOverflow:
                    # 越界降级：不带着越界数字乱排——回流定格（整片下、人回队、
                    # 片转 idle 暂停发牌）；结算的落账与盖章在 SAVEPOINT 之外照常，
                    # 提示与审计归 _finish 出口统一接管。requeue 的 to_tail 已把
                    # 下场者 append 进队（列表突变不吃 SAVEPOINT 回滚），二次
                    # 入队由 _reflow 的防重防御兜住
                    self._reflow(oncourt, queue, court)
            self._writeback_queue(rows, by_id, queue)
            self._bump_court(court)
            self._finish(
                state, game_id=game_id, actor_id=actor_id, autofill=not no_redeal
            )
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
            elo_rows = self._elo_settle(
                winners,
                losers,
                self._ratings_of([r.account_id for r in (*winners, *losers)]),
            )
            match.winner_side = winner_side
            match.sa = score_a
            match.sb = score_b
            match.winners = snap_w
            match.losers = snap_l
            match.elo_rows = elo_rows
            self._apply_elo(elo_rows, len(winners))
            # DUPR 两轨独立（输入快照吃派生分、与 Elo 无关）：删旧明细按新胜负重插
            # （单边空战报无胜负两队，与 settle_confirm 同守卫——删后不重插）
            self.db.execute(delete(DuprDetail).where(DuprDetail.match_id == match.id))
            if winners and losers:
                self._apply_dupr(
                    match=match,
                    ended_at=match.ended_at,
                    winners=winners,
                    losers=losers,
                    score_w=score_a if winner_side == "a" else score_b,
                    score_l=score_b if winner_side == "a" else score_a,
                )
            self._bump_court(court)
            # 豁免补片（2.8 §4.2 声明式）：账面动作物理面不动，改分不重排人
            self._finish(state, game_id=game_id, actor_id=actor_id, autofill=False)
        return self.view(game_id=game_id, viewer_id=actor_id)

    def cancel(
        self,
        *,
        game_id: int,
        actor_id: int,
        court_no: int,
        base_total_seq: int,
        base_court_seq: int,
        no_redeal: bool = False,
    ) -> dict:
        """取消对局（§4.7，全权）：整场作废——不计分不进战绩；场上的人原样回流
        候场队首（补偿没打成的，沿 2.2 §4.12），回流后出口补片立即重发（2.8 验收
        3——含歇者在取人窗口也照认，旧「队首比对」422 就此消亡）。no_redeal
        （清扫态，前端编排逐调用传）声明豁免：清扫要清出空片好散场，重发会把
        残局变回在打。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            court = self._court_writable(game_id, court_no)
            self._require_full_power(state, game, actor_id)
            self._check_total(state, base_total_seq)
            self._check_court(court, base_court_seq)
            rows = self._roster(game_id)
            self._void_court(rows, {r.id: r for r in rows}, court)
            self._finish(
                state, game_id=game_id, actor_id=actor_id, autofill=not no_redeal
            )
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
        到场即经写路径出口补片（_finish：够一片人数自动开赛），不够人留候场队
        等下一个写动作——真值在后端出口，前端只画不判。
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
                # 改态前算：absent/left 之外的重复报到不算首次到场（arrive_at
                # 只在首报落一次，到场先后排位不随重报漂移）
                first_arrival = row.check not in ARRIVED
                # 进场下那一刻盖当前轮转章（等待从进场下起算）；已在队里的重复
                # 报到不动章——重报不刷新等待资历
                if st == "late":
                    if row.id in queue:
                        queue.remove(row.id)
                    queue.append(row.id)  # 迟到排队尾
                    row.wait_batch = state.rotation_batch
                elif st == "join":
                    if row.id not in queue:
                        queue.append(row.id)  # 中途加入排队尾
                        row.wait_batch = state.rotation_batch
                elif row.check not in ARRIVED and row.id not in queue:
                    queue.append(row.id)  # 'ok' 只在首报进队，重复报到不重排
                    row.wait_batch = state.rotation_batch
                row.check = st
                if first_arrival and row.arrive_at is None:
                    row.arrive_at = clock.now()  # 几点到：首次到场落账
            # 自动管理员两路同权（修C）：签到端点与空降扫码共用（扫码即签到），
            # 落账后判——"第一个"含本行这次
            self._maybe_grant_first_admin(state, game, row, rows)
            self._place_queue(by_id, queue)
            self._finish(state, game_id=game_id, actor_id=actor_id)
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
        outId 离片回队尾；只收在打片（idle 片没人可换，court_idle 退回）。
        两参都在场上时走换位分支：只互换片与边，上场章/连打/候场队不动。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, _game = self._open_write(game_id)
            self._require_arrived(game_id, actor_id)
            self._check_total(state, base_total_seq)
            out = self._roster_row(game_id, out_id)
            inn = self._roster_row(game_id, in_id)
            if out.court_no is None or out.court_side is None:
                raise errors.live_invalid("被换下的人不在场上")
            # 场上⇄场上＝换位：只互换片与边。章/连打不动——换人保护是「从候场进
            # 场上」的进场礼，换位两人本来就在打；feed 另起 kind，复用换人句会
            # 念成「换下」
            if inn.court_no is not None and inn.court_side is not None:
                if out.court_no == inn.court_no and out.court_side == inn.court_side:
                    raise errors.live_invalid("两人已在同一边")
                for no in {out.court_no, inn.court_no}:
                    self._court_writable(game_id, no)
                out.court_no, inn.court_no = inn.court_no, out.court_no
                out.court_side, inn.court_side = inn.court_side, out.court_side
                self._feed_push(
                    state,
                    {
                        "kind": "swap_sides",
                        "actor": self._actor_name(game_id, actor_id),
                        "a": out.display_name,
                        "b": inn.display_name,
                        "at": clock.iso(clock.now()),
                    },
                )
            else:
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
                inn.court_mark = (
                    state.total_seq
                )  # 换上即落位：盖上场章（资历从此刻起算）
                # 连打不清：只随真歇归零（取队时没被选上）。真歇过的人这里本来就是
                # 0；清零唯一生效的场景是"没歇就被换回"，那是洗疲劳的后门
                inn.queue_pos = None
                out.court_no = None
                out.court_side = None
                out.wait_batch = state.rotation_batch  # 换下进场下：盖当前章
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
            self._finish(state, game_id=game_id, actor_id=actor_id)
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
        （轮到取队那一刻消耗——live_rotation.take_from_queue，结算回流路已兑现；
        2.8 批2 补片路同源）；fire 互斥清 skip，连战只做排位第四档平手决胜、
        不插队首——翻转改的是排位键，候场快照统一走 _place_queue 重排；unskip
        清零；fire 再按一次=取消连战（同样只影响排位、不动队位）。"""
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
                    row.skip = 0  # 互斥（连战只做排位第四档平手决胜，不插队首）
            # 连战/歇都不再手动挪队位：候场名次=排位快照，落位统一走 _place_queue
            # （fire 翻转改排位第四档，快照随之刷新）
            rows = self._roster(game_id)
            by_id = {r.id: r for r in rows}
            self._place_queue(by_id, self._queue_ids(rows))
            # 减员方向（设歇）不触发补片是纯函数层的事（可发人数不够自然留空），
            # 出口恒开——取消歇恰好凑齐最后一人时这里点亮空片（验收 7）
            self._finish(state, game_id=game_id, actor_id=actor_id)
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
            # —— 谁下的两道闸：单打×n人下无物理意义（一片只有 2 人），回落全上
            # 全下；连打上限默认随「谁下」自适应（输家下 3、其余 2），手动改过
            # （streak_manual）则粘住组织者的值不随切换重置
            down_eff = down if down is not None else state.down
            if not (doubles if doubles is not None else state.doubles) and down_eff in (
                "n1",
                "n2",
                "n3",
            ):
                down_eff = "all"
            if down_eff != state.down:
                if not state.streak_manual:
                    state.streak_max = 3 if down_eff == "loser" else 2
                state.down = down_eff
            if pairing is not None:
                state.pairing = pairing
                game.rotation = pairing
            if doubles is not None:
                state.doubles = doubles
            if streak_max is not None:
                state.streak_max = streak_max
                state.streak_manual = True  # 手动优先：此后切「谁下」不再重置默认
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
            self._finish(state, game_id=game_id, actor_id=actor_id)
        return self.view(game_id=game_id, viewer_id=actor_id)

    def set_admin(
        self, *, game_id: int, actor_id: int, player_id: int, base_total_seq: int
    ) -> dict:
        """封管理员（2.2 §4.6 组织者独占——管理员不能再封别人）：靶行须是正式
        球友；已封再封当没事（幂等不进号）。feed 留痕全场可见。"""
        return self._toggle_admin(
            game_id=game_id,
            actor_id=actor_id,
            player_id=player_id,
            base_total_seq=base_total_seq,
            grant=True,
        )

    def unset_admin(
        self, *, game_id: int, actor_id: int, player_id: int, base_total_seq: int
    ) -> dict:
        """撤管理员（2.2 §4.6 组织者独占）：不在册当没事（幂等不进号）；撤留痕
        feed——「组织者收回了管理员身份」的事件句。"""
        return self._toggle_admin(
            game_id=game_id,
            actor_id=actor_id,
            player_id=player_id,
            base_total_seq=base_total_seq,
            grant=False,
        )

    def _toggle_admin(
        self,
        *,
        game_id: int,
        actor_id: int,
        player_id: int,
        base_total_seq: int,
        grant: bool,
    ) -> dict:
        """封/撤管理员共用骨架（2.2 §4.6 组织者独占）：身份 → 号对表 → 靶行 →
        翻转才留痕进号（幂等不进号）；封有「访客不能当管理员」前置，撤对访客恒空转。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            if game.organizer_id != actor_id:
                raise errors.organizer_only(
                    f"只有组织者能{'封' if grant else '撤'}管理员"
                )
            self._check_total(state, base_total_seq)
            row = self._roster_row(game_id, player_id)
            if grant and row.account_id is None:
                raise errors.live_invalid("访客不能当管理员")
            hit = row.account_id is not None and row.account_id in (state.admins or [])
            if hit != grant:
                if grant:
                    state.admins = [*(state.admins or []), row.account_id]
                else:
                    state.admins = [
                        a for a in (state.admins or []) if a != row.account_id
                    ]
                self._feed_push(
                    state,
                    {
                        "kind": "set_admin" if grant else "unset_admin",
                        "actor": self._actor_name(game_id, actor_id),
                        "target": row.display_name,
                        "at": clock.iso(clock.now()),
                    },
                )
                self._finish(state, game_id=game_id, actor_id=actor_id)
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
                wait_batch=state.rotation_batch,  # 空降即进场下：盖当前轮转章
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
            self._finish(state, game_id=game_id, actor_id=actor_id)
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
        排队尾。命名走 _guest_display_name（前端 addGuests 已切真不命名，命名归后端）。
        访客不建 EloRating 行不进榜（2.3 裁决）。"""
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
                display = _guest_display_name(
                    guarantor.display_name, name, i, count, numbered=False
                )
                row = LivePlayer(
                    game_id=game_id,
                    account_id=None,
                    display_name=display,
                    guest=True,
                    guarantor_account_id=guarantor.account_id,
                    check="ok",
                    arrive_at=now,
                    wait_batch=state.rotation_batch,  # 带到即进场下：盖当前轮转章
                )
                self.db.add(row)
                made.append(row)
            self.db.flush()  # 取新行 id 排队尾
            by_id = {r.id: r for r in self._roster(game_id)}
            queue = self._queue_ids(list(by_id.values()))
            queue.extend(r.id for r in made)
            self._place_queue(by_id, queue)
            self._finish(state, game_id=game_id, actor_id=actor_id)
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
        # 代位分与装扮一次查齐（3s 轮询 + 每个写动作响应都走这里，逐人查会放大成 N+1；
        # 装扮三键吃这行账号，_player_row 只透传不查库）
        rates = stats.pairing_ratings([p.account_id for p in roster])
        elo_rates = self._ratings_of([p.account_id for p in roster])
        acct_rows = (
            self.db.execute(
                select(Account).where(
                    Account.id.in_([p.account_id for p in roster if p.account_id])
                )
            )
            .scalars()
            .all()
        )
        dresses = {a.id: dress_fields(a) for a in acct_rows}
        match_rows = (
            self.db.execute(
                select(LiveMatch)
                .where(LiveMatch.game_id == game_id)
                .order_by(LiveMatch.ended_at, LiveMatch.id)
            )
            .scalars()
            .all()
        )
        # 今晚口径单一源（战报实时派生）：名单行的 tonight 与分边 facts 同吃一份
        facts = self._history_facts(game_id, match_rows)
        rows = [
            self._player_row(
                p,
                is_organizer=is_organizer,
                viewer_id=viewer_id,
                dupr_value=rates[p.account_id],
                dress=dresses.get(p.account_id),
                tonight=facts["tonight"].get(p.id, 0),
            )
            for p in roster
        ]
        courts = self._courts(game_id)
        matches = match_rows
        # 队列序定值给出（队首在前，候场外的行不排）——_queue_ids 单一源
        # （queue_pos 升序即队列序），视图与写路径同一把尺；持久化回写是写动作的事
        waiting = self._queue_ids(roster)
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
            # 提示行身份定值（2.6 §4.3-3）：判定的尺与打球记录名单三笔规矩同一把
            # （playlog 单一源），前端不自判；未散场局按名单前提恒 False——散场旗
            # 先行短路，散场前提由调用点锚死（谓词内不再自查 ended_at），3s 轮询
            # 热路径上在办局不再白跑战报 JSON/账单谓词
            "is_my_game": game.ended_at is not None
            and is_my_game_at(self.db, game_id, viewer_id),
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
            "queue": waiting,
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
                        self._elo_preview(c, roster, elo_rates)
                        if c.status == "playing"
                        else None
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

    def unchanged_since(
        self, *, game_id: int, since_total_seq: int, since_fee_total: int
    ) -> bool:
        """轮询条件拉取的指纹比对（2.8 §4.6）：稳态拍只做两次单行读，不组视图。
        fee_total 进指纹是因为账单/局簿域改价不 bump live 号（号只记现场总账写）
        ——光比号，204 会把改价闷掉；未定价（null）按 -1 对表。未开账回 False，
        调用点落到 view 沿 404 现状；读不加号，真值由测试锁。"""
        state = self._state_or_none(game_id)
        if state is None:
            return False
        game = self.db.get(Game, game_id)
        fee = -1 if game.fee_total is None else game.fee_total
        return state.total_seq == since_total_seq and fee == since_fee_total

    # ---- 内部：写动作公共件与两级号机制（全部在 _write_lock 内调用） ----

    def _fee_block(self, game: Game, roster: list[LivePlayer] | None = None) -> dict:
        """费用亮数块（1.3 §3 散场确认页）：总价=订场登记真值（null=未定）；人头=
        账单口径的摊钱人头（bills.bill_heads 同一份代码，亮数与实摊一个数）；
        per_head=floor 向下抹零，未定价局为 null 但 heads 照给
        （亮「总价未定 · N 人」用）。roster 由 view 顺手递入免二次查（单独调用自查）。"""
        rows = roster if roster is not None else self._roster(game.id)
        heads = bill_heads(rows)
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

    def _finish(
        self,
        state: LiveState,
        *,
        game_id: int,
        actor_id: int,
        autofill: bool = True,
    ) -> None:
        """写路径公共出口（2.8 §4.2，附录 B「号跳、补片、提交」统一接管）：
        主动作落账后顺手补满所有空片（豁免端点显式传 autofill=False，错忘的方向
        从「忘了补」翻成「忘了豁免」）→ 总号进一 → 提交。补片段包 SAVEPOINT：
        算不出/写不回只回滚补片段、记 live_auto_fill_error 审计，主动作照常提交
        （降级不连坐——不变量从「每次成立」降为「最终成立」，下个写动作自然
        重试、一键排阵兜底）；补开非空记 live_auto_deal，操作人=触发这次写动作
        的人。号跳纪律：一写动作恰一 bump——补片空手不额外跳号；幂等早退支在
        突变前 return、不走出口（重放不进号语义照旧）。排位段越界（2.9 §4.9）
        是例外路：降级同上、但提交后抛 rotation_overflow（携视图）——发牌暂停
        这件事得说给人听，主操作已落账不算失败。"""
        opened: list[int] = []
        overflow = False
        if autofill:
            try:
                with self.db.begin_nested():
                    opened = self._fill_idle(state)
            except Exception as e:  # noqa: BLE001 —— 补片失败不连坐主动作（2.8 §4.2）
                logs.audit(
                    "live_auto_fill_error",
                    game_id=game_id,
                    account_id=actor_id,
                    detail=f"{type(e).__name__}: {e}",
                )
                # 排位段越界：补片段已回滚、片留空，主动作下面照常提交；提交后再
                # 把「这片暂停发牌」说给人听（错误体携最新视图，页面保持最新画面）
                overflow = isinstance(e, live_rotation.RotationOverflow)
        if opened:
            logs.audit(
                "live_auto_deal",
                game_id=game_id,
                account_id=actor_id,
                detail=f"courts={','.join(map(str, opened))}",
            )
        self._bump_total(state)
        self.db.commit()
        if overflow:
            raise errors.rotation_overflow()

    def _fill_idle(self, state: LiveState) -> list[int]:
        """把所有空片补满（出口补片与手动排阵同一份活）：喂行/写回走
        _rotation_rows/_apply_rotation 一对口，取队真值在 live_rotation.autofill_idle
        （歇跳过消耗、未到不发，排位五段典序全在纯函数层）；片行落账沿老 deal
        样——新片行起笔 1、老片行进一，分制快照开赛定格。返回补开的片号。"""
        game = self.db.get(Game, state.game_id)
        rows = self._roster(state.game_id)
        rates = StatsLedger(self.db).pairing_ratings([r.account_id for r in rows])
        facts = self._history_facts(state.game_id)
        dicts = _rotation_rows(rows, rates, facts["tonight"], _roster_seqs(rows))
        status = {c.court_no: c.status for c in self._courts(state.game_id)}
        courts = [  # 含还没开过行的片：按 courts_count 补占位（autofill_idle 契约）
            {"court_no": no, "status": status.get(no, "idle")}
            for no in range(1, state.courts_count + 1)
        ]
        queue = self._queue_ids(rows)
        opened = live_rotation.autofill_idle(
            dicts,
            courts,
            {"doubles": state.doubles, "pairing": state.pairing},
            queue,
            facts=facts,
        )
        by_id = {r.id: r for r in rows}
        _apply_rotation(by_id, dicts, state.total_seq)  # 新落位行盖章=落位时刻总号
        for no in opened:
            court = self._court_or_none(state.game_id, no)
            fresh = court is None  # 列 default 在 INSERT 才生效，新行显式起笔
            if fresh:
                court = LiveCourt(
                    game_id=state.game_id, court_no=no, scoring=game.scoring
                )
                self.db.add(court)
            court.status = "playing"
            court.seq = 1 if fresh else court.seq + 1
            court.court_seq = 1 if fresh else court.court_seq + 1
            # 分制快照开赛定格（2.6 机制A）：改分制只影响此后新开的片
            court.scoring = game.scoring
        self._writeback_queue(rows, by_id, queue)  # queue 已被取队原地重排为剩余序
        return opened

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
        # 服务层唯一审计埋点（6.1 §C1）：授予发生在 check/dropin 路由看不见的这里，
        # 不补这笔则「设管理员」审计有洞；操作人=被自动授予的首签人
        logs.audit(
            "live_set_admin",
            game_id=game.id,
            account_id=row.account_id,
            detail="auto_first_checkin",
        )
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

    def _history_facts(
        self, game_id: int, matches: list[LiveMatch] | None = None
    ) -> dict:
        """战报派生单一源：今晚的场次/搭档史/净胜负/最近同场分法全从 live_matches
        实时算（改分重落改写本行、取消不留行——对齐由重算天然成立，无第二本账）。
        键形契约与 live_rotation._split_sides 的 facts 对齐：tonight {名册行id:
        场次}、pair_counts {(小id,大id): 搭档次数}（双打每场胜方内一对+败方内
        一对）、net_wins {id: 今晚净胜场}、last_split {frozenset(同场全员):
        (一边ids, 另一边ids)}——按 ended_at,id 序扫描，后写覆盖先写即「最近」。
        matches 可由调用方递入（view 已载战报时免二查）。"""
        if matches is None:
            matches = (
                self.db.execute(
                    select(LiveMatch)
                    .where(LiveMatch.game_id == game_id)
                    .order_by(LiveMatch.ended_at, LiveMatch.id)
                )
                .scalars()
                .all()
            )
        tonight: dict[int, int] = {}
        pair_counts: dict[tuple[int, int], int] = {}
        net_wins: dict[int, int] = {}
        last_split: dict[frozenset[int], tuple[tuple[int, ...], tuple[int, ...]]] = {}
        for m in matches:
            win = tuple(s["id"] for s in m.winners)
            lose = tuple(s["id"] for s in m.losers)
            for pid in (*win, *lose):
                tonight[pid] = tonight.get(pid, 0) + 1
                net_wins[pid] = net_wins.get(pid, 0) + (1 if pid in win else -1)
            for side in (win, lose):
                for a, b in combinations(side, 2):
                    key = (a, b) if a < b else (b, a)
                    pair_counts[key] = pair_counts.get(key, 0) + 1
            last_split[frozenset((*win, *lose))] = (win, lose)
        return {
            "tonight": tonight,
            "pair_counts": pair_counts,
            "net_wins": net_wins,
            "last_split": last_split,
        }

    def _place_queue(self, by_id: dict[int, LivePlayer], queue: list[int]) -> None:
        """候场队落位单点（queue 即名次、队首 0）：发牌/确认/取消/换人/歇连/空降/
        带访客/清片八处写动作的共同尾巴——漏落一行即静默错序，收进一个口。
        名次=排位快照（预计序的持久化镜像：读路径只回放 queue_pos，发牌取人
        同走 rank_key 不吃落位序）；排位段越界时保持传入序落位——不带着越界
        数字乱排、主操作不连坐（发牌路径的护栏另在 _finish 接管）。"""
        try:
            queue = self._ranked_ids(by_id, queue)
        except live_rotation.RotationOverflow:
            pass
        for pos, pid in enumerate(queue):
            by_id[pid].queue_pos = pos

    def _ranked_ids(self, by_id: dict[int, LivePlayer], queue: list[int]) -> list[int]:
        """候场名单按排位分重排（与 take_from_queue 同一把尺）。by_id 恒为全场
        名册（各调用点现状），roster_seq 按全场到场序算——与发牌路径的序号口径
        一致；全并列时 stable 序保持传入序。不可发者同样参与落位（名册里挂着、
        发牌路径另行过滤），不在这里二次分档。"""
        rows = [by_id[pid] for pid in queue if pid in by_id]
        if not rows:
            return []
        tonight = self._history_facts(rows[0].game_id)["tonight"]
        seqs = _roster_seqs(list(by_id.values()))

        def key(r: LivePlayer) -> int:
            return live_rotation.rank_key(
                {
                    "id": r.id,
                    "check": r.check,
                    "streak": r.streak,
                    "wait_batch": r.wait_batch,
                    "tonight": tonight.get(r.id, 0),
                    "fire": r.fire,
                    "roster_seq": seqs[r.id],
                }
            )

        return [r.id for r in sorted(rows, key=key)]

    def _writeback_queue(
        self,
        rows: list[LivePlayer],
        by_id: dict[int, LivePlayer],
        queue: list[int],
    ) -> None:
        """队序落账收尾（场上人清队位 + 候场按剩余序落位）：settle_confirm 与
        _fill_idle 同一尾巴——清位漏一行即静默错序的敏感账，与 _place_queue 同收一处。"""
        for r in rows:
            if r.court_side is not None:
                r.queue_pos = None
        self._place_queue(by_id, queue)

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

    @staticmethod
    def _reflow(oncourt: list[LivePlayer], queue: list[int], court: LiveCourt) -> None:
        """整片回流的账面动作（settle_confirm 清扫定格/越界降级、_void_court 取消
        回流三处同吃）：清片位、id 接队尾、片行转 idle。已在队里的不重复入队——
        越界路 requeue 的 to_tail 先 append 过（列表突变不吃 SAVEPOINT 回滚）、
        _void_court 的「原样回流队首」由调用方预置队首表达，两形同吃这道防御。"""
        for r in oncourt:
            r.court_no = None
            r.court_side = None
            if r.id not in queue:
                queue.append(r.id)
        court.status = "idle"

    def _void_court(
        self, rows: list[LivePlayer], by_id: dict[int, LivePlayer], court: LiveCourt
    ) -> None:
        """单片作废的账面动作（§4.7）——cancel 与 sweep-cancel-all 共用：场上的人
        原样回流队首（保行序——_reflow 接队尾语义下由预置队首表达，id 已在队
        防重不重接）、片行转 idle、片号前进。"""
        oncourt = self._oncourt(rows, court.court_no)
        queue = [r.id for r in oncourt] + self._queue_ids(rows)
        self._reflow(oncourt, queue, court)
        self._place_queue(by_id, queue)
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

    def _ratings_of(self, account_ids: list[int]) -> dict[int, int]:
        """Elo 现分批查（一次 in 拉齐，pairing_ratings 同款防 N+1 手法）：结算/预演
        的 eff 真值源——3s 轮询的 view 预演、settle 两入口都走这里，逐人点查会在
        全场最热端点上放大成几十条点查。缺行（开账首见前的空降等）回 RATING_INIT。"""
        ids = sorted({a for a in account_ids if a is not None})
        if not ids:
            return {}
        found = {
            r.account_id: r.rating
            for r in self.db.execute(
                select(EloRating).where(EloRating.account_id.in_(ids))
            ).scalars()
        }
        return {a: found.get(a, RATING_INIT) for a in ids}

    def _elo_preview(
        self, court: LiveCourt, roster: list[LivePlayer], ratings: dict[int, int]
    ) -> dict | None:
        """在打片的 ±积分预演双分支（§4.11，2026-10-08 收归后端单源；2026-10-09
        记分本地化改挂 playing 片——Elo 分差只看两队现分与谁胜、与比分无关，
        服务端无需知道各手机本地比分）：A 胜 / B 胜各算一套随视图给出，上传窗
        点胜方在两套现成数间切换（当场变、不等网络仍成立）。取序与 settle_confirm
        同一条路（_oncourt 单一源：名册序 + 片位过滤），预演=落账：上传响应所选
        分支的 elo_rows 与这里逐行一致。ratings 由调用方批查递入（_ratings_of）。
        单边空返 None（2026-10-10 修复）：片上的人早退清位而片行保持 playing
        （「打短维持现状」），一边被抽空就没有对局可言——此前空列表喂进
        _elo_settle 的均值除法直接 ZeroDivision，view 恒 500、整局卡死无自救。"""
        oncourt = self._oncourt(roster, court.court_no)
        a = [p for p in oncourt if p.court_side == "a"]
        b = [p for p in oncourt if p.court_side == "b"]
        if not a or not b:
            return None
        return {
            "a": self._elo_settle(a, b, ratings),
            "b": self._elo_settle(b, a, ratings),
        }

    def _elo_settle(
        self,
        winners: list[LivePlayer],
        losers: list[LivePlayer],
        ratings: dict[int, int],
    ) -> list[dict]:
        """结算每人一行、胜队在前（§4.6-2/§4.11）——Elo 唯一算路（2026-10-08 起
        前端零公式：确认窗预演的 elo_preview 与落账 elo_rows 都出自本函数）：
        双打按两队人均分算期望落到个人、delta=max(1,K*(1-exp))、败方只扣涨分
        六成、地板 800；访客代入 1200 当正常玩家算（去半折口径），行内记 delta
        但不落账。
        一边没人返 []（2026-10-10 修复）：片被早退抽空后单边空的结算/预演没有
        胜负两队，elo 不动账（_apply_elo 对空行无操作）——也是空列表喂均值
        除法的防爆边。ratings 由调用方批查递入（_ratings_of），均值与行内
        rating_before 同一次取数（不重复查）。"""

        def eff(p: LivePlayer) -> int:
            return RATING_INIT if p.guest else ratings.get(p.account_id, RATING_INIT)

        if not winners or not losers:
            return []
        w_eff = [eff(p) for p in winners]
        l_eff = [eff(p) for p in losers]
        w_avg = sum(w_eff) / len(winners)
        l_avg = sum(l_eff) / len(losers)
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
                *zip(winners, w_eff, [delta] * len(winners)),
                *zip(losers, l_eff, [-loss] * len(losers)),
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
        # 双方代位分一次查齐（pairing_ratings 批量版，免逐人点查）：
        # 访客 account_id=None → 3.0 恒定标准分，语义与单发版逐条同
        rates = stats.pairing_ratings([p.account_id for p in winners + losers])
        stats.settle(
            game_id=match.game_id,
            match_id=match.id,
            ended_at=ended_at,
            winner_side=[(p.account_id, rates[p.account_id]) for p in winners],
            loser_side=[(p.account_id, rates[p.account_id]) for p in losers],
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
        dress: dict | None = None,
        tonight: int = 0,
    ) -> dict:
        # 考勤分权（2.3 裁决 Q2）：早退迟到不展示给随便扫到的人
        visible = is_organizer or (viewer_id is not None and p.account_id == viewer_id)
        return {
            "id": p.id,
            "account_id": p.account_id,
            "name": p.display_name,
            # 装扮三键：注册球友由 view 预取递入；访客无账号行全 None——
            # 前端兜指定公共款素材/素卡，访客不占个人衣柜
            "avatar": dress["avatar"] if dress else None,
            "avatar_url": dress["avatar_url"] if dress else None,
            "back": dress["back"] if dress else None,
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
            # 今晚已打场次（战报实时派生）：队列抽屉「今晚 N 场」与排位③档同一把尺
            "tonight": tonight,
            "queue_pos": p.queue_pos,
        }
