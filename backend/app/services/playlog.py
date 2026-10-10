"""playlog —— 打球记录名单的三笔规矩（docs/2.6 §4.4）：给定账号与已散场的局，
「上过场 ∨ 账单里有份 ∨ 这局的组织者」满足其一即进记录。

现算不落库——「记录跟着账单走」（补填出账下次拉取即含）与「老局追溯」（存量
散场局零迁移）由现算天然成立。只认存储锚 games.ended_at，不认派生态 done
（到点未散场的局 derive 也出 done，但没散过场）；终止/取消局无 ended_at 天然查无。
向调用方隐藏 live_players/live_matches/bill_rows 三表 join 与战报 JSON 解析
（快照 id 是名册行 id 非 account_id，须先拿本人名册行再判交集），只暴露
局集合 / 累计上场对局数 / 单局谓词；games/live 两簿可各自调用不成环。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Bill, BillRow, Game, LiveMatch, LivePlayer


def _roster_rows_by_game(db: Session, account_id: int) -> dict[int, set[int]]:
    """该账号的名册行：局 id → 行 id 集（空降/正式同表；访客无账号不在内）。"""
    out: dict[int, set[int]] = {}
    for gid, rid in db.execute(
        select(LivePlayer.game_id, LivePlayer.id).where(
            LivePlayer.account_id == account_id
        )
    ):
        out.setdefault(gid, set()).add(rid)
    return out


def _on_court_ids(winners: list, losers: list) -> set[int]:
    """一场战报的上场名册行 id 集（winners/losers 快照 JSON 的 id 字段）。"""
    return {p["id"] for side in (winners, losers) for p in side or ()}


def _match_hits(
    db: Session, rows_by_game: dict[int, set[int]]
) -> list[tuple[int, bool]]:
    """逐场产出 (局 id, 本人是否上了这场)；JSON 不可 SQL 过滤，Python 侧解析。"""
    if not rows_by_game:
        return []
    return [
        (gid, bool(_on_court_ids(w, l) & rows_by_game[gid]))
        for gid, w, l in db.execute(
            select(LiveMatch.game_id, LiveMatch.winners, LiveMatch.losers).where(
                LiveMatch.game_id.in_(rows_by_game)
            )
        )
    ]


def played_game_ids(db: Session, account_id: int) -> set[int]:
    """三笔规矩选出的局 id 集（∩ 已散场）。三笔先并再统锚 ended_at：开账可早于
    开打时刻、被撤的局也可能留有上场记录（cancel 只看工具箱窗口），上过场≠散过场。"""
    hits = {
        gid for gid, hit in _match_hits(db, _roster_rows_by_game(db, account_id)) if hit
    }
    hits |= {
        gid
        for (gid,) in db.execute(
            select(Bill.game_id)
            .join(BillRow, BillRow.bill_id == Bill.id)
            .where(BillRow.account_id == account_id)
        )
    }
    hits |= set(
        db.execute(
            select(Game.id).where(
                Game.organizer_id == account_id, Game.ended_at.is_not(None)
            )
        ).scalars()
    )
    if not hits:
        return set()
    return set(
        db.execute(
            select(Game.id).where(Game.id.in_(hits), Game.ended_at.is_not(None))
        ).scalars()
    )


def matches_count(db: Session, account_id: int) -> int:
    """累计上场对局数（记录页头部「打了 N 场对局」）：不限于已散场局——落账即算
    与积分同拍；与记录列表行数解耦（缺席照摊进列表、场数不加，访客无账号不计）。"""
    return sum(
        1 for _, hit in _match_hits(db, _roster_rows_by_game(db, account_id)) if hit
    )


def is_my_game(db: Session, game_id: int, account_id: int | None) -> bool:
    """单局谓词（live view 提示行的身份定值）：与名单规矩同一把尺，未登录（路人）
    一律 False；未散场局按名单前提不算。"""
    return account_id is not None and game_id in played_game_ids(db, account_id)
