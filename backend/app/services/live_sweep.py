"""live_sweep —— 散场与回看链（docs/2.3 §4.9/§4.10）：LiveBook 拆出的独立节
（批3 落点裁定：防 live.py 破千）。

LiveBook 继承 LiveSweepMixin 获得 sweep_cancel_all / end 两动作；写锁、两级号、
名册与片行等内部件仍由 LiveBook 提供（组合而非复制）。散场链三步：
- 入口即清扫：end 见在打片不放行（live_residue；2026-10-09 记分本地化后残局=
  全部非 idle 片即 playing 片）；逐片处理走上传结算（带 no_redeal）或这里的一键
  全取消；
- 落封存锚：games.ended_at 一处落库（批1 裁定不存双真值），战报落账即冻结、
  封存天然满足；散场后一切写端点由 _open_write 拒 live_ended（回看只读）；
- 考勤定格：在场者 left_at=散场时刻、已早退者保持原离场时刻、未到者 arrive_at 空。
"""

from __future__ import annotations

from sqlalchemy import func, select

from ..core import clock, errors
from ..db.models import Game, LiveMatch, LivePlayer, LiveState
from .bills import BillBook

# 算到场口径（2.2 §4.2）：absent 未到 / left 早退不算在场——live.py 与本模块共用，
# 定义在此处是因为 live 已 import 本模块（反向会循环）
ARRIVED = ("ok", "late", "join")


class LiveSweepMixin:
    """散场节：向 LiveBook 只暴露 sweep_cancel_all / end 两个动作。"""

    def sweep_cancel_all(
        self, *, game_id: int, actor_id: int, base_total_seq: int
    ) -> dict:
        """「未完对局全部取消」一键（§4.9）：全部在打片按 cancel 语义逐片作废
        （原样回流队首、不计分不留战报），一个事务办完；无残局时原样回视图
        不进号（重试幂等）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            self._require_full_power(state, game, actor_id)
            self._check_total(state, base_total_seq)
            rows = self._roster(game_id)
            by_id = {r.id: r for r in rows}
            swept = False
            for court in self._courts(game_id):
                if court.status != "playing":
                    continue
                self._void_court(rows, by_id, court)
                swept = True
            if swept:
                self._bump_total(state)
                self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def end(self, *, game_id: int, actor_id: int, base_total_seq: int) -> dict:
        """散场收工（§4.9）：残局不清完不放行；清完落 games.ended_at、考勤定格、
        round 收口成全场落账场数（确认链不逐场计数，散场一次定总数）。散场权组织者
        独占——例外：组织者本人已标早退时管理员可代收（2.2 §4.14 兜底）。"""
        with self._write(game_id=game_id, actor_id=actor_id):
            state, game = self._open_write(game_id)
            if game.organizer_id != actor_id and not self._admin_may_end(
                state, game, actor_id
            ):
                raise errors.organizer_only(
                    "只有组织者能散场，组织者先走了的话管理员可代收"
                )
            self._check_total(state, base_total_seq)
            if any(c.status != "idle" for c in self._courts(game_id)):
                raise errors.live_residue()
            now = clock.now()
            game.ended_at = now
            if game.state != "locked":
                # open 局提前开账再散场的，state 停在 open 会让派生态永不到 done——散场即定格，翻 locked 让 derive 走 locked→done（1.3 走查补漏）
                game.state = "locked"
            for r in self._roster(game_id):
                if r.check in ARRIVED and r.left_at is None:
                    r.left_at = now  # 考勤定格：在场者离场时刻=散场时刻
            state.round = self.db.execute(
                select(func.count())
                .select_from(LiveMatch)
                .where(LiveMatch.game_id == game_id)
            ).scalar_one()
            # 出账挂同一 commit（1.3 §4.7「散场即出账」）：总价已定（非 null 且 >0）
            # 当场算好，与封存锚/考勤定格一本账原子——半局账或半场封存都不存在；
            # 总价未定/0 元时引擎自行不出（挂提醒等补填）
            BillBook(self.db).generate(game=game)
            self._bump_total(state)
            self.db.commit()
        return self.view(game_id=game_id, viewer_id=actor_id)

    def _admin_may_end(self, state: LiveState, game: Game, actor_id: int) -> bool:
        """管理员代收兜底（2.2 §4.14）：被封管理员 且 组织者名册行已标早退——
        组织者在场（或只是没标早退）时散场权不松。"""
        if actor_id not in (state.admins or []):
            return False
        org_row = self.db.execute(
            select(LivePlayer).where(
                LivePlayer.game_id == game.id,
                LivePlayer.account_id == game.organizer_id,
            )
        ).scalar_one_or_none()
        return org_row is not None and org_row.check == "left"
