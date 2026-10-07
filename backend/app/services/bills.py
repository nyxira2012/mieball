"""BillBook —— 账单域（docs/1.3）的出账引擎：散场出账与补填出账两个入口共用
这一份算法，账一出即定格（快照，此后不随名册/账号任何变动改变）。

- 定格名单（§4.1/§7 裁决）：散场/补填那一刻的 LivePlayer 快照——账号行一人一行
  （缺席照摊、空降照摊、早退整份；候补从不进 live_players 故天然不进账）；访客行
  不单独计，份额归担保人（1+名下访客数）。名单头尺与 live 视图 _fee_block 同一把。
- 零头组织者兜底（§8 裁决）：base=总价//人头 向下抹零，非组织者 amount=base×份额，
  组织者=总价−Σ非组织者——合计恒等于总价（不变承诺 1）。
- 出账时机（B1：都不用任何人点「生成」）：散场 end() 的同一 commit（一本账原子）；
  补填端点 fee>0 当场出。总价 null/0 不出账（0=免费局，挂不了账也提不了醒）。
- 幂等：bills.game_id unique + generate 先查已出账即返回——end 与补填竞态、断网
  重放都到不了第二本账。
- 出账判定锚 games.ended_at（散场动作）而非派生态 done：到点未散场的 locked 局
  derive 也出 done，锚它会违反 §4.7「进行中的局永不出账」。
- 管理员不碰钱（C2）：守卫只认组织者本人，不走现场的分级权。
"""

from __future__ import annotations

import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import clock, errors
from ..db.models import Account, Bill, BillRow, Game, LivePlayer
from .accounts import person_view

# 补填写串行（沿两簿先例）：SQLite 无行锁，「查未填→落价→出账」check-then-act 全锁内；
# 与散场链（live 的锁）的竞态由 ended_at 守卫互斥——未散场进不了补填、散场后进不了 end
_write_lock = threading.Lock()


def _split(
    shares: list[tuple[int, str, int, int]], total: int, organizer_id: int
) -> dict[int, int]:
    """分账唯一算法（§8 裁决，generate 与 preview 同吃这一份）：base=总价//人头
    向下抹零，非组织者=base×份额，组织者=总价−Σ非组织者（差额兜底在内）——
    合计恒等于总价（不变承诺 1）。确认页亮的数=点定后出的账，改抹零规则只改这里。"""
    heads = sum(share for *_, share in shares)
    base = total // heads
    amounts = {aid: base * share for aid, _, _, share in shares if aid != organizer_id}
    amounts[organizer_id] = total - sum(amounts.values())
    return amounts


def generate(db: Session, game: Game) -> Bill | None:
    """出账唯一入口（散场 end 与补填端点共用）——模块级函数，live_sweep 不持 BillBook。"""
    return BillBook(db).generate(game=game)


class BillBook:
    def __init__(self, db: Session):
        self.db = db

    # ---- 出账引擎（两个入口的唯一算法） ----

    def generate(self, *, game: Game) -> Bill | None:
        """出账：定格名单每人一行落 bills/bill_rows。不 commit——散场链把它挂进
        end() 的同一 commit（仿 settle_confirm 一本账），补填链由 set_fee 收口。"""
        seen = self.db.execute(
            select(Bill).where(Bill.game_id == game.id)
        ).scalar_one_or_none()
        if seen is not None:
            return seen  # 幂等：已出过账直接返回，不重算
        fee = game.fee_total
        if fee is None or fee <= 0:
            return None  # 未定价不出账（挂提醒等补填）；免费局（0 元）无账可出
        shares = self._shares(game)
        heads = sum(share for *_, share in shares)
        base = fee // heads
        amounts = _split(shares, fee, game.organizer_id)
        bill = Bill(
            game_id=game.id,
            fee_total=fee,
            heads=heads,
            per_head=base,
            billed_at=clock.now(),
        )
        self.db.add(bill)
        self.db.flush()  # autoflush=False：显式 flush 拿 bill.id 给行用
        for aid, name, guest_count, share in shares:
            self.db.add(
                BillRow(
                    bill_id=bill.id,
                    account_id=aid,
                    display_name=name,
                    guest_count=guest_count,
                    share_count=share,
                    amount=amounts[aid],
                )
            )
        return bill

    # ---- 补填总价（1.3 §4.5：只有从未填过价的散场局留这一个口子） ----

    def set_fee(
        self, *, game_id: int, organizer_id: int, fee_total: int
    ) -> Bill | None:
        """补填：组织者本人（管理员不碰钱，C2）；仅散场过且从未填过价可用——
        未散场 game_not_ended、已填过（含 0）fee_already_set、负数 fee_invalid。
        fee>0 当场出账（billed_at=补填刻，账单日期仍取 game.ended_at 散场那天）；
        fee=0 只定值不出账（提醒消失）。价格就此定死。"""
        with _write_lock:
            game = self._owned_game(game_id, organizer_id)
            if game.ended_at is None:
                raise errors.game_not_ended()
            if game.fee_total is not None:
                raise errors.fee_already_set()
            if fee_total < 0:
                raise errors.fee_invalid()
            game.fee_total = fee_total
            bill = self.generate(game=game)
            self.db.commit()
            return bill

    # ---- 补填确认步定值（「将按人均 X 元向 N 人出账」） ----

    def preview(self, *, game_id: int, organizer_id: int, amount: int) -> dict:
        """按当前名册现算（不落库）：与 generate 同一分享法（组织者兜差额）——
        确认页亮出的数就是点定后出的账，两处永远是同一个数。"""
        game = self._owned_game(game_id, organizer_id)
        shares = self._shares(game)
        heads = sum(share for *_, share in shares)
        base = amount // heads
        amounts = _split(shares, amount, game.organizer_id)
        return {
            "heads": heads,
            "per_head": base,
            "organizer_share": amounts[game.organizer_id],
        }

    # ---- 内部 ----

    def _owned_game(self, game_id: int, organizer_id: int) -> Game:
        """组织者守卫（同 GameBook._owned 口径）：账是钱的事，只认组织者本人——
        管理员现场同权但不沾账（C2），不走 live 的分级权。"""
        game = self.db.get(Game, game_id)
        if game is None:
            raise errors.game_not_found()
        if game.organizer_id != organizer_id:
            raise errors.not_organizer()
        return game

    def _shares(self, game: Game) -> list[tuple[int, str, int, int]]:
        """定格名单（散场/补填那一刻的 LivePlayer 快照）：(账号 id, 定格名, 名下
        访客数, 份额) 按名册行序。组织者必在名单（publish 自动 formal、start 展开）；
        名册无组织者行时强制补一行兜底（理论不可达，防总额无处归）。"""
        rows = (
            self.db.execute(
                select(LivePlayer)
                .where(LivePlayer.game_id == game.id)
                .order_by(LivePlayer.id)
            )
            .scalars()
            .all()
        )
        accounts = {r.account_id for r in rows if r.account_id is not None}
        guests: dict[int, int] = {}
        for r in rows:
            if r.account_id is None and r.guarantor_account_id in accounts:
                guests[r.guarantor_account_id] = (
                    guests.get(r.guarantor_account_id, 0) + 1
                )
        shares = [
            (
                r.account_id,
                r.display_name,
                guests.get(r.account_id, 0),
                1 + guests.get(r.account_id, 0),
            )
            for r in rows
            if r.account_id is not None
        ]
        if game.organizer_id not in {aid for aid, *_ in shares}:
            shares.append(
                (
                    game.organizer_id,
                    person_view(self.db.get(Account, game.organizer_id))["nickname"],
                    0,
                    1,
                )
            )
        return shares
