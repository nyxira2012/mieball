"""passwords —— 密码钥匙的五动作（docs/1.6 §4.8~§4.11）：设、登、重置、改、密码接管。

PasswordMixin 混入 AccountBook（LiveSweepMixin 前例）：本模块定密码域策略，
AccountBook 提供库会话、短信门、钥匙库与名片/手机号内部件（self._check_phone /
_active_by_phone / _merge_card 等）。四把钥匙裁决全部内聚在下列机制里：
- 密码是高级钥匙（Q3）：密码登录成功与短信验证同待遇——杀该账号全部"未验证"钥匙（4.9）；
- 重置=换锁（Q4）：所有设备钥匙作废只留当前台，旧密码随换锁自然作废；
- 接管=全设备钥匙连同密码一并作废（4.5），宽限窗 10 分钟内设新密免再发码；
- 锁的是账号的"用密码"这一条路：login/redeem 共用一份连错计数，满 5 次锁 15 分钟；
  改密码验旧密是已登录语境，不计锁（4.11）；短信端点永不互波及。
- 微信挂点（1.7）：login/reset/redeem 三路都是验明正身时刻——顺手绑档解开、
  凭条在手正式绑上；绑定逻辑本体在 WechatMixin（services/wechat.py）。
- 验证收编（1.8 §4.5）：reset 同挂 _adopt_binding——它也是「用短信证明自己是
  老账号主人」的路；login_password 不挂（密码验证非短信，指路话术只提短信）。
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from ..core import clock, errors, security
from ..db.models import Account

PWD_MIN_LEN = 6
PWD_MAX_FAILS = 5
PWD_LOCK_SECONDS = 15 * 60
PWD_GRACE_SECONDS = 10 * 60


class PasswordMixin:
    """密码节：向 AccountBook 只暴露五动作与两个接管/注销挂点。"""

    def set_password(self, account_id: int, *, code: str, password: str) -> None:
        """首设密码（4.8）：凭据 = 短信码（purpose=set_password）或接管/找回刚留下的
        宽限窗，二者验其一；已设拒重设、6 位起步都是真闸（先后顺序照批单：先挡已设，
        再挡位数，最后才烧码）。"""
        account = self._require_active(account_id)
        if account.password_hash:
            raise errors.password_exists()
        if len(password) < PWD_MIN_LEN:
            raise errors.password_too_short()
        self._verify_credential(account, code)
        account.password_hash = security.hash_password(password)
        self.db.commit()

    def login_password(
        self,
        *,
        phone: str,
        password: str,
        device_marker: str,
        bind_token: str | None = None,
    ) -> tuple[dict, str, bool]:
        """密码登录（4.9）：与短信验证同待遇——杀未验证钥匙、发已验证钥匙。
        微信挂点（1.7 §4.3）：验明正身=正式绑的好时机（顺手绑档同刻解开）。"""
        self._check_phone(phone)
        account = self._active_by_phone(phone)
        if account is None:
            raise errors.no_account()
        self._check_lock(account)
        self._require_hash(account)
        self._fail_or_pass(account, password)
        self.keys.revoke_unverified(account.id)
        self._sweep_weak_binding(account)
        self.db.commit()
        bound = self._try_bind(account, bind_token, verified=True)
        token = self.keys.issue(account.id, device_marker, verified=True)
        return self.view(account.id, viewer="self"), token, bound

    def reset_password(
        self,
        *,
        phone: str,
        code: str,
        password: str,
        device_marker: str,
        bind_token: str | None = None,
        adopt_from: Account | None = None,
    ) -> tuple[dict, str, bool]:
        """忘记密码重置（4.10）：短信验明正身 → 换锁（所有设备钥匙作废只留当前台）
        → 落新密码。换锁即新锁：旧密码连同旧连错计数一并清场。
        微信挂点（1.7 C3）：换锁不清正式绑（本人多条活路），顺手绑档随验明正身解开。
        验证收编（1.8 §4.5）：这也是「用短信证明自己是老账号主人」的路——当前设备
        登着的快进号上的微信自动迁绑到本账号（凭条先执行、收编后且幂等）。"""
        self._check_phone(phone)
        account = self._active_by_phone(phone)
        if account is None:
            raise errors.no_account()
        if len(password) < PWD_MIN_LEN:
            raise errors.password_too_short()
        self.sms.verify(phone, "reset_password", code)
        self.keys.revoke_all(account.id)
        account.password_hash = security.hash_password(password)
        account.pwd_fail_count = 0
        account.pwd_locked_until = None
        self._sweep_weak_binding(account)
        self.db.commit()
        bound = self._try_bind(account, bind_token, verified=True)
        bound = self._adopt_binding(account, adopt_from) or bound
        token = self.keys.issue(account.id, device_marker, verified=True)
        return self.view(account.id, viewer="self"), token, bound

    def change_password(self, account_id: int, *, old: str, new: str) -> None:
        """例行换钥匙（4.11）：验旧落新，其他设备不动。旧密错只提示重输，不计锁。"""
        account = self._require_active(account_id)
        if not account.password_hash or not security.verify_password(
            old, account.password_hash
        ):
            raise errors.password_wrong()
        if len(new) < PWD_MIN_LEN:
            raise errors.password_too_short()
        account.password_hash = security.hash_password(new)
        self.db.commit()

    def redeem_password(
        self,
        *,
        phone: str,
        password: str,
        device_marker: str,
        card: dict[str, Any] | None = None,
        bind_token: str | None = None,
    ) -> tuple[dict, str, bool]:
        """密码接管（占卡三出口之二，4.5）：知道密码即主人证明，接管语义与
        redeem(takeover) 完全一致（名片合并 D5、全钥匙+密码作废、宽限窗置位）；
        微信登记位一并清场（1.7 接管清场），凭条在手随后正式绑上。"""
        self._check_phone(phone)
        account = self._active_by_phone(phone)
        if account is None:
            raise errors.no_account()
        self._check_lock(account)
        self._require_hash(account)
        self._fail_or_pass(account, password)
        self.keys.revoke_all(account.id)
        self._wipe_password(account)
        self._clear_binding(account)
        self._grant_grace(account)
        self._merge_card(account, card)
        self.db.commit()
        bound = self._try_bind(account, bind_token, verified=True)
        token = self.keys.issue(account.id, device_marker, verified=True)
        return self.view(account.id, viewer="self"), token, bound

    # ---- 挂点（accounts.py 的 redeem/deactivate 调，逻辑不许落回那边） ----

    def _wipe_password(self, account: Account) -> None:
        """密码作废：接管=密码连同全设备钥匙一并清场（4.5）；注销=密码随账号消亡（4.6）。"""
        account.password_hash = None
        account.pwd_fail_count = 0
        account.pwd_locked_until = None
        account.pwd_grace_until = None

    def _grant_grace(self, account: Account) -> None:
        """短信验明正身后的设密宽限窗（4.8"同一验证窗口不重复发码"）：接管/找回时置位。"""
        account.pwd_grace_until = clock.now() + timedelta(seconds=PWD_GRACE_SECONDS)

    # ---- 内部 ----

    def _verify_credential(self, account: Account, code: str) -> None:
        """设密凭据二选一：给了码走短信门；没给码必须在宽限窗内，否则按没验过处理
        （冒填者收不到真主人手机上的码，堵死，§4.8 禁止项）。"""
        if code:
            self.sms.verify(account.phone, "set_password", code)
        elif account.pwd_grace_until is None or clock.now() > account.pwd_grace_until:
            raise errors.sms_code_invalid()

    def _check_lock(self, account: Account) -> None:
        """锁检：密码路连错 5 次后 15 分钟内整条"用密码"路拒绝（剩余秒给画面倒计时）；
        过期自然放行，顺手清残值（随本次请求的提交一并落库）。"""
        until = account.pwd_locked_until
        if until is None:
            return
        now = clock.now()
        if now < until:
            raise errors.password_locked(int((until - now).total_seconds()) or 1)
        account.pwd_locked_until = None

    def _require_hash(self, account: Account) -> None:
        if not account.password_hash:
            raise errors.password_not_set()

    def _fail_or_pass(self, account: Account, password: str) -> None:
        """校验密码：对则清零计数（原地返回）；错则计数 +1，满 5 次落锁并抛
        password_locked，未满抛 password_wrong(剩余次数)。login/redeem 共用。"""
        if security.verify_password(password, account.password_hash):
            account.pwd_fail_count = 0
            return
        account.pwd_fail_count += 1
        if account.pwd_fail_count >= PWD_MAX_FAILS:
            account.pwd_locked_until = clock.now() + timedelta(seconds=PWD_LOCK_SECONDS)
            account.pwd_fail_count = 0
            self.db.commit()
            raise errors.password_locked(PWD_LOCK_SECONDS)
        self.db.commit()
        raise errors.password_wrong(PWD_MAX_FAILS - account.pwd_fail_count)
