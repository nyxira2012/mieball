"""KeyVault —— 设备钥匙的深模块：发钥匙/认人/各种作废，指纹与吊销细节全部藏在里面。

接口只有五个动词；"接管杀全部、短信验证杀未验证"这类策略由调用方（AccountBook）组合，
本模块只负责忠实执行，不掺业务判断。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ..core import clock, security
from ..db.models import Account, DeviceKey

# last_used_at 是纯遥测（全库只写不读）：按钥匙 1 小时节流一次写库，
# 否则每个认证请求都为它付一次 commit（SQLite 每次 commit 都是一次磁盘同步）
LAST_USED_THROTTLE = timedelta(hours=1)


@dataclass(frozen=True)
class KeyInfo:
    account_id: int
    key_id: int


class KeyVault:
    def __init__(self, db: Session):
        self.db = db

    def issue(self, account_id: int, device_marker: str, *, verified: bool) -> str:
        """发一把钥匙：原文只此一次返回给调用方，库里落指纹。"""
        token = security.new_device_token()
        self.db.add(
            DeviceKey(
                account_id=account_id,
                fingerprint=security.token_fingerprint(token),
                device_marker=device_marker,
                verified=verified,
                created_at=clock.now(),
            )
        )
        self.db.commit()
        return token

    def resolve(self, token: str) -> KeyInfo | None:
        """认人：钥匙无效/已作废/账号已注销一律返回 None（游客处理，不报错）。"""
        fp = security.token_fingerprint(token)
        row = self.db.execute(
            select(DeviceKey.id, DeviceKey.account_id)
            .join(Account, Account.id == DeviceKey.account_id)
            .where(DeviceKey.fingerprint == fp, DeviceKey.revoked_at.is_(None), Account.status == "active")
        ).first()
        if row is None:
            return None
        # 顺手记最后使用时间（1 小时节流，见 LAST_USED_THROTTLE）；失败不影响认人
        try:
            now = clock.now()
            res = self.db.execute(
                update(DeviceKey)
                .where(
                    DeviceKey.id == row.id,
                    or_(DeviceKey.last_used_at.is_(None), DeviceKey.last_used_at < now - LAST_USED_THROTTLE),
                )
                .values(last_used_at=now)
            )
            if res.rowcount:
                self.db.commit()
        except Exception:  # noqa: BLE001
            self.db.rollback()
        return KeyInfo(account_id=row.account_id, key_id=row.id)

    def revoke(self, token: str) -> None:
        """作废这一把（退出登录用：只踢本机，别台不受影响）。"""
        fp = security.token_fingerprint(token)
        self.db.execute(
            update(DeviceKey).where(DeviceKey.fingerprint == fp, DeviceKey.revoked_at.is_(None))
            .values(revoked_at=clock.now())
        )
        self.db.commit()

    def revoke_unverified(self, account_id: int) -> None:
        """D4 规则的执行器：杀掉该账号所有"发出时未经短信验证"的钥匙（冒填者必死）。"""
        self.db.execute(
            update(DeviceKey)
            .where(
                DeviceKey.account_id == account_id,
                DeviceKey.revoked_at.is_(None),
                DeviceKey.verified.is_(False),
            )
            .values(revoked_at=clock.now())
        )
        self.db.commit()

    def revoke_all(self, account_id: int) -> None:
        """安全时刻全量作废（接管/注销）：所有设备一律失效。"""
        self.db.execute(
            update(DeviceKey)
            .where(DeviceKey.account_id == account_id, DeviceKey.revoked_at.is_(None))
            .values(revoked_at=clock.now())
        )
        self.db.commit()
