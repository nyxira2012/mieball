"""IntentBook —— 意向簿深模块（docs/1.2 §4.13）：留/改/删意向、组织者翻的意向列表。

- 一人一份 upsert；时段只存前端词表的 key 串、不校验词表（防两真值，技术设计 §4）。
- "已邀"标记：GameBook.invite 置位（两簿唯一来往，本簿不反向碰局）、本人改意向清位。
- 列表排序：未邀在前、已邀靠后（各自按 updated_at 倒序——新留的和新改过的排前面，4.11）。
- known（与 viewer 打过没打过）由 routes 层注入 GameBook 组合——本簿不 import 局簿
  （两簿边界，技术设计 §3）；视图里 known 恒 False 占位，列表路由对登录 viewer 覆写。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import clock, errors
from ..db.models import Account, Intent
from .accounts import person_view

FREQUENCIES = (0, 1, 2)  # 随缘 / 每周 1 打 / 每周 2 打（文案在前端 format.ts，单一源）


class IntentBook:
    def __init__(self, db: Session):
        self.db = db

    # ---- 意向列表（4.11 组织者翻、4.13 谁都能翻含游客；登录 viewer 才有已邀/认识语义） ----

    def list(self, *, viewer_id: int | None) -> list[dict]:
        rows = (
            self.db.execute(
                select(Intent).order_by(Intent.updated_at.desc(), Intent.id.desc())
            )
            .scalars()
            .all()
        )
        uninvited = [r for r in rows if r.invited_at is None]
        invited = [r for r in rows if r.invited_at is not None]
        ordered = (
            *uninvited,
            *invited,
        )  # 未邀在前、已邀靠后，各自 updated_at 倒序（4.11）
        # 意向人账号一次查齐（约球页每次 onShow 都拉这张表，逐行 get 叠 N+1）
        accounts = {
            a.id: a
            for a in self.db.execute(
                select(Account).where(Account.id.in_({r.account_id for r in ordered}))
            ).scalars()
        }
        return [self._view(r, viewer_id=viewer_id, accounts=accounts) for r in ordered]

    # ---- 我的一份（4.13：随时可动；没留过就是没有） ----

    def mine(self, *, account_id: int) -> dict | None:
        row = self._by_account(account_id)
        return self._view(row, viewer_id=account_id) if row else None

    # ---- 留 / 改（4.13：一人一份；"改了想法" = 清已邀标记、重排回前面） ----

    def save(
        self,
        *,
        account_id: int,
        slots: list[str],
        frequency: int,
        note: str | None,
    ) -> dict:
        if not slots:
            raise errors.intent_slots_empty()
        if frequency not in FREQUENCIES:
            raise errors.frequency_invalid()
        row = self._by_account(account_id)
        if row is None:
            row = Intent(account_id=account_id)
            self.db.add(row)
        row.slots = list(slots)
        row.frequency = frequency
        row.note = note
        row.updated_at = clock.now()
        row.invited_at = None  # 保存即清已邀标记：改了想法 = 可以再来邀我（4.13）
        self.db.commit()
        return self._view(row, viewer_id=account_id)

    # ---- 删（4.13：删掉即真没了、可随时再留；没意向也当没事——幂等） ----

    def delete(self, *, account_id: int) -> dict:
        row = self._by_account(account_id)
        if row is not None:
            self.db.delete(row)
            self.db.commit()
        return {"ok": True}

    # ---- 内部 ----

    def _by_account(self, account_id: int) -> Intent | None:
        return self.db.execute(
            select(Intent).where(Intent.account_id == account_id)
        ).scalar_one_or_none()

    def _view(
        self,
        row: Intent,
        *,
        viewer_id: int | None,
        accounts: dict[int, Account] | None = None,
    ) -> dict:
        acc = (
            accounts.get(row.account_id)
            if accounts is not None
            else self.db.get(Account, row.account_id)
        )
        return {
            "account": person_view(acc),
            "slots": list(row.slots),
            "frequency": row.frequency,
            "note": row.note,
            "updated_at": clock.iso(row.updated_at),
            # invited 只对登录 viewer 有意义（游客谈不上"我邀过"）；known 由 routes 组合覆写
            "invited": viewer_id is not None and row.invited_at is not None,
            "known": False,
        }
