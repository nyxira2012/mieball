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
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import clock, errors
from ..db.models import Account, Bill, BillRow, Game, LivePlayer
from .accounts import ANON_NAME, person_view

# 补填写串行（沿两簿先例）：SQLite 无行锁，「查未填→落价→出账」check-then-act 全锁内；
# 与散场链（live 的锁）的竞态由 ended_at 守卫互斥——未散场进不了补填、散场后进不了 end
_write_lock = threading.Lock()


def _split(
    shares: list[tuple[int, str, int, int]], total: int, organizer_id: int
) -> tuple[dict[int, int], int]:
    """分账唯一算法（§8 裁决，generate 与 preview 同吃这一份）：base=总价//人头
    向下抹零，非组织者=base×份额，组织者=总价−Σ非组织者（差额兜底在内）——
    合计恒等于总价（不变承诺 1）。确认页亮的数=点定后出的账，改抹零规则只改这里。
    回 (各人摊额, 总人头)：heads 与分账同一出处，列账侧不再各算一遍防口径漂移。"""
    heads = sum(share for *_, share in shares)
    base = total // heads
    amounts = {aid: base * share for aid, _, _, share in shares if aid != organizer_id}
    amounts[organizer_id] = total - sum(amounts.values())
    return amounts, heads


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
        amounts, heads = _split(shares, fee, game.organizer_id)
        base = fee // heads
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
        fee=0 只定值不出账（提醒消失）。价格就此定死。
        窗口规则四份拷贝之一（改窗四处同步，开发日志 2026-10-08 债登记）：本处 +
        games._check_booking_window（订场/清空窗·互补）+ detail.vue 订场入口与
        补填入口（按钮镜像）——改漏不出错，只会「前端给钮、后端打回」"""
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
        amounts, heads = _split(shares, amount, game.organizer_id)
        base = amount // heads
        return {
            "heads": heads,
            "per_head": base,
            "organizer_share": amounts[game.organizer_id],
        }

    # ---- 账单页全视图（1.3 §4.6 读链：分权在这里一次裁死） ----

    def view(self, *, account_id: int, period: str = "all") -> dict:
        """登录者的账单页全视图。SQL 只碰 viewer 自己的行 / viewer 组织的局——
        「别人欠别人」的字节进不了响应（§4.6 看账边界，不变承诺 4）。期间按散场日
        （games.ended_at）归属，三数 / rows / debtors 同用一份过滤（§8 裁决③）。"""
        ended_from = _period_floor(period)
        span = [Game.ended_at >= ended_from] if ended_from is not None else []

        mine = self.db.execute(
            select(BillRow, Game)
            .join(Bill, BillRow.bill_id == Bill.id)
            .join(Game, Bill.game_id == Game.id)
            .where(
                BillRow.account_id == account_id,
                Game.organizer_id
                != account_id,  # 组织者行归应收视图，不重复出现在待付侧
                Game.ended_at.is_not(None),
                *span,
            )
            .order_by(Game.ended_at.desc(), Game.id.desc())
        ).all()

        organized = self.db.execute(
            select(Bill, Game)
            .join(Game, Bill.game_id == Game.id)
            .where(Game.organizer_id == account_id, Game.ended_at.is_not(None), *span)
            .order_by(Game.ended_at.desc(), Game.id.desc())
        ).all()

        # 批量预取（settle/receive 每点一次也整跑 view，逐本查行、逐行查账号会叠成 N+1）：
        # organized 各本的 BillRow 一次查齐按本分组；付款人/收款方涉事账号一次查齐
        bill_rows: dict[int, list[BillRow]] = {}
        for r in (
            self.db.execute(
                select(BillRow)
                .where(BillRow.bill_id.in_([b.id for b, _ in organized]))
                .order_by(BillRow.id)
            )
            .scalars()
            .all()
        ):
            bill_rows.setdefault(r.bill_id, []).append(r)
        acc_ids: set[int] = {game.organizer_id for _, game in organized} | {
            game.organizer_id for _, game in mine
        }
        for all_rows in bill_rows.values():
            acc_ids.update(r.account_id for r in all_rows if r.account_id is not None)
        accounts = {
            a.id: a
            for a in self.db.execute(
                select(Account).where(Account.id.in_(acc_ids))
            ).scalars()
        }

        entries: list[tuple[object, int, dict]] = []
        debtors: dict[int, dict] = {}
        receivable = 0
        for bill, game in organized:
            # 整本账的行都给组织者（§4.2 按人明细）；行序=名册行序（批3 裁定）
            all_rows = bill_rows.get(bill.id, [])
            payers = [r for r in all_rows if r.account_id != game.organizer_id]
            mine_row = next(r for r in all_rows if r.account_id == game.organizer_id)
            for r in payers:
                if r.received_at is None:
                    receivable += r.amount
                    d = debtors.setdefault(
                        r.account_id,
                        {"account_id": r.account_id, "total": 0, "games": 0},
                    )
                    d["total"] += r.amount
                    d["games"] += 1
            others_total = sum(r.amount for r in payers)
            unreceived = sum(r.amount for r in payers if r.received_at is None)
            entries.append(
                (
                    game.ended_at,
                    game.id,
                    {
                        "kind": "receivable" if unreceived else "received",
                        "game_id": game.id,
                        "game_name": game.name,
                        "ended_day": clock.today_key(game.ended_at),
                        # 应收行金额点一人少一笔；收讫后翻全额（§4.4，翻旧账仍在）
                        "amount": unreceived or others_total,
                        "fee_total": bill.fee_total,
                        "my_share": mine_row.amount,
                        "my_guest_count": mine_row.guest_count,
                        "payer_rows": [
                            {
                                "account_id": r.account_id,
                                "name": _frozen_name(
                                    accounts.get(r.account_id), r.display_name
                                ),
                                "deactivated": _deactivated(accounts.get(r.account_id)),
                                "amount": r.amount,
                                "guest_count": r.guest_count,
                                "paid_at": clock.iso(r.paid_at) if r.paid_at else None,
                                "received_at": clock.iso(r.received_at)
                                if r.received_at
                                else None,
                            }
                            for r in payers
                        ],
                    },
                )
            )
        for row, game in mine:
            entry = {
                "kind": "paid" if row.paid_at else "payable",
                "game_id": game.id,
                "game_name": game.name,
                "ended_day": clock.today_key(game.ended_at),
                "amount": row.amount,
                "payee_name": person_view(accounts.get(game.organizer_id))["nickname"],
                "payee_deactivated": _deactivated(accounts.get(game.organizer_id)),
                # 对方（组织者）先点了我的「已收」而我还没结算（§4.3b 灰字旗；
                # 点收落在我这行的 received_at 上，三数仍按我的 paid_at 算）
                "peer_received": row.received_at is not None and row.paid_at is None,
            }
            if row.guest_count > 0:
                entry["guest_count"] = (
                    row.guest_count
                )  # 「含带来的朋友 ×N」只在带了时出现
            entries.append((game.ended_at, game.id, entry))
        entries.sort(key=lambda e: (e[0], e[1]), reverse=True)

        unfixed = (
            self.db.execute(
                select(Game)
                .where(
                    Game.organizer_id == account_id,
                    Game.ended_at.is_not(None),
                    Game.fee_total.is_(None),  # 0 元是「已定免费」，提醒消失（§4.5）
                    *span,
                )
                .order_by(Game.ended_at.desc())
            )
            .scalars()
            .all()
        )
        return {
            "period": period,
            "summary": {
                "due": sum(r.amount for r, _ in mine if r.paid_at is None),
                "paid": sum(r.amount for r, _ in mine if r.paid_at is not None),
                "receivable": receivable,  # received 整笔天然不占（未收加总为 0）
            },
            "rows": [entry for _, _, entry in entries],
            "debtors": [
                {
                    "account_id": d["account_id"],
                    "name": person_view(accounts.get(d["account_id"]))["nickname"],
                    "deactivated": _deactivated(accounts.get(d["account_id"])),
                    "total": d["total"],
                    "games": d["games"],
                }
                for d in sorted(debtors.values(), key=lambda x: -x["total"])
            ],
            "unfixed": [
                {
                    "game_id": g.id,
                    "game_name": g.name,
                    "ended_day": clock.today_key(g.ended_at),
                }
                for g in unfixed
            ],
        }

    # ---- 两向记账（各记各的裁决：paid_at/received_at 只由本人/组织者各自置位） ----

    def settle(self, *, game_id: int, account_id: int, period: str = "all") -> dict:
        """点「结算」（§4.3）：本人非组织者行 paid_at=now，终态不可逆；重放幂等 200。
        组织者的行不是待付（404 同码分支）、不在名单 404——都不泄漏别人的账。"""
        game, _bill = self._billed_game(game_id)
        row = self._row_or_404(_bill.id, account_id)
        if account_id == game.organizer_id:
            raise errors.not_on_bill("组织者自己那份不用点结算")
        if row.paid_at is None:
            row.paid_at = clock.now()
            self.db.commit()
        return self.view(account_id=account_id, period=period)

    def receive(
        self,
        *,
        game_id: int,
        payer_account_id: int,
        organizer_id: int,
        period: str = "all",
    ) -> dict:
        """逐人点「已收」（§4.4）：组织者本人独占（管理员不碰钱，C2）；该行
        received_at=now 终态不可逆，重放幂等 200。组织者行不在收款明细里。"""
        game, _bill = self._owned_billed_game(game_id, organizer_id)
        row = self._row_or_404(_bill.id, payer_account_id)
        if payer_account_id == game.organizer_id:
            raise errors.not_on_bill("组织者自己那份不在收款明细里")
        if row.received_at is None:
            row.received_at = clock.now()
            self.db.commit()
        return self.view(account_id=organizer_id, period=period)

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

    def _billed_game(self, game_id: int) -> tuple[Game, Bill]:
        """有账的局（settle 用）：没这场局 game_not_found、没出账 bill_not_found。"""
        game = self.db.get(Game, game_id)
        if game is None:
            raise errors.game_not_found()
        bill = self.db.execute(
            select(Bill).where(Bill.game_id == game_id)
        ).scalar_one_or_none()
        if bill is None:
            raise errors.bill_not_found()
        return game, bill

    def _owned_billed_game(self, game_id: int, organizer_id: int) -> tuple[Game, Bill]:
        """组织者守卫 + 有账守卫（receive 用）：越权先于账存在与否——
        球友探测别人的局号拿到的也是同一个 403，不借错误码差异嗅探账本。"""
        game = self._owned_game(game_id, organizer_id)
        bill = self.db.execute(
            select(Bill).where(Bill.game_id == game_id)
        ).scalar_one_or_none()
        if bill is None:
            raise errors.bill_not_found()
        return game, bill

    def _row_or_404(self, bill_id: int, account_id: int) -> BillRow:
        """摊钱名单行（不在名单 → 404，不区分「局里没这人」与「没他行」的细节）。"""
        row = self.db.execute(
            select(BillRow).where(
                BillRow.bill_id == bill_id, BillRow.account_id == account_id
            )
        ).scalar_one_or_none()
        if row is None:
            raise errors.not_on_bill()
        return row

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


# ---- 读链助手（模块级：无状态的口径换算） ----

PERIOD_DAYS = {"7d": 7, "30d": 30}


def _period_floor(period: str):
    """期间下界（含当天）：7d/30d 从现在回退；all 不过滤。取值合法性由路由
    Literal 挡（入参先例），这里只认已知串。"""
    days = PERIOD_DAYS.get(period)
    return clock.now() - timedelta(days=days) if days else None


def _deactivated(acc: Account | None) -> bool:
    """账号行不在或已注销（§4.8）：账行名字/灰旗共用（账号由调用方批量预取）。"""
    return acc is None or acc.status != "active"


def _frozen_name(acc: Account | None, frozen: str) -> str:
    """账行名字：定格名（账是快照）；注销者一律占位（§4.8，沿 person_view 先例）。"""
    return ANON_NAME if _deactivated(acc) else frozen
