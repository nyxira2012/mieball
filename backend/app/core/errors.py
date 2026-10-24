"""业务错误 —— 服务层只抛 ApiError(code, message)，路由层统一映射成
HTTP {\"error\": {code, message}}；前端按 code 分支，不解析中文文案。"""

from __future__ import annotations

from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str, view: dict | None = None):
        super().__init__(status_code=status, detail=message)
        self.code = code
        # 409 两级号防线退回时随错误体带上最新总账视图（2.3 附录 B1），其余 None
        self.view = view


def phone_taken() -> ApiError:
    return ApiError(409, "phone_taken", "这个手机号已经有人用了")


def no_account() -> ApiError:
    return ApiError(404, "no_account", "这个手机号还没有账号，请核对后重输")


def no_identity() -> ApiError:
    return ApiError(401, "no_identity", "请先登录")


def phone_invalid() -> ApiError:
    return ApiError(422, "phone_invalid", "手机号位数不对，请输入 11 位大陆手机号")


def phone_mismatch() -> ApiError:
    return ApiError(422, "phone_mismatch", "请输入本账号的手机号")


def purpose_invalid() -> ApiError:
    return ApiError(422, "purpose_invalid", "验证码用途不合法")


def nickname_invalid(msg: str = "昵称需 1-16 个字符") -> ApiError:
    return ApiError(422, "nickname_invalid", msg)


def sms_cooldown(retry_after: int) -> ApiError:
    return ApiError(429, "sms_cooldown", f"发送太频繁，{retry_after} 秒后再试")


def sms_phone_daily() -> ApiError:
    return ApiError(
        429,
        "sms_phone_daily",
        "这个手机号今天收码次数到上限了，明天再试；收不到码且发码不是你本人操作的，联系平台客服",
    )


def sms_ip_daily() -> ApiError:
    return ApiError(429, "sms_ip_daily", "今天收码次数到上限了，明天再试")


def sms_unavailable() -> ApiError:
    return ApiError(503, "sms_unavailable", "短信暂时发不出，请稍后再试")


def sms_bad_code(remaining: int) -> ApiError:
    return ApiError(400, "sms_bad_code", f"验证码不对，还可试 {remaining} 次")


def sms_code_invalid() -> ApiError:
    return ApiError(400, "sms_code_invalid", "验证码已失效，请重新获取")


def sms_code_expired() -> ApiError:
    return ApiError(400, "sms_code_expired", "验证码已过期，请重新获取")


# ---- 密码钥匙 ----


def password_exists() -> ApiError:
    return ApiError(409, "password_exists", "密码已经设过了，请走修改密码")


def password_not_set() -> ApiError:
    return ApiError(404, "password_not_set", "这个账号还没设过密码，请用短信验证码进入")


def password_too_short() -> ApiError:
    return ApiError(422, "password_too_short", "密码至少 6 位")


def password_wrong(remaining: int | None = None) -> ApiError:
    # 登录/接管场景携带剩余重试次数；改密场景只提示重输
    msg = (
        f"密码不对，还可试 {remaining} 次"
        if remaining is not None
        else "密码不对，请重输"
    )
    return ApiError(400, "password_wrong", msg)


def password_locked(retry_after: int) -> ApiError:
    # 仅锁定密码验证途径，短信验证途径仍可正常进入
    return ApiError(
        429,
        "password_locked",
        f"密码错得太多，已锁定 {retry_after} 秒，可先用短信验证码进入",
    )


# ---- 微信钥匙 ----


def wechat_off() -> ApiError:
    # 微信通道未配置或资质未就绪
    return ApiError(503, "wechat_off", "微信登录即将开通 · 资质到位后点亮")


def wechat_code_invalid() -> ApiError:
    # 授权凭证过期或已使用
    return ApiError(400, "wechat_code_invalid", "微信授权已过期，请再点一次")


def wechat_unavailable() -> ApiError:
    # 微信官方服务不可用或网络异常
    return ApiError(503, "wechat_unavailable", "微信登录暂时不可用，可先用短信或密码")


def wechat_unbound() -> ApiError:
    # 微信尚未与此账号完成正式绑定，指引使用短信或密码验证
    return ApiError(
        404,
        "wechat_unbound",
        "这个微信还证明不了这个账号是你的——用短信或密码验证进入，进去就自动绑牢",
    )


def wechat_bound_other() -> ApiError:
    # 该微信已绑定在另一个账号上，不透露具体账号信息
    return ApiError(
        409,
        "wechat_bound_other",
        "这个微信已经属于另一个账号——这个账号请用短信或密码验证",
    )


def wechat_binding_weak() -> ApiError:
    # 建号时仅顺手暂存的弱绑定，需通过短信或密码验明正身
    return ApiError(
        403,
        "wechat_binding_weak",
        "这个微信还证明不了这个账号是你的——用短信或密码验证进入，进去就自动绑牢",
    )


def wechat_fast_failed() -> ApiError:
    # 快进建号失败：事务整体回滚不留半个账号
    return ApiError(503, "wechat_fast_failed", "没办成，请再点一次微信授权")


def phone_taken_redirect() -> ApiError:
    # 补绑手机号撞占用：不透露账号信息，指路登录页走短信验证
    return ApiError(
        409,
        "phone_taken_redirect",
        "这个手机号注册过。如果你就是号主，去登录页用短信验证进入那个账号，"
        "微信会自动绑回那个账号；你最近在临时号上的报名会留在那边，不会搬过来",
    )


def phone_already_bound() -> ApiError:
    # 账号已有手机号时不开放自助换绑，需联系客服处理
    return ApiError(
        409,
        "phone_already_bound",
        "这个账号已有手机号，手机号是账号的根，换号先联系平台客服",
    )


# ---- 球局域 ----


def game_not_found() -> ApiError:
    return ApiError(404, "game_not_found", "局不存在")


def not_organizer(msg: str = "只有组织者能做这个操作") -> ApiError:
    # 同码分支说话：组织者退局是"不能退"不是"不够格"（4.4 禁止项），message 由调用方给
    return ApiError(403, "not_organizer", msg)


def game_locked() -> ApiError:
    return ApiError(409, "game_locked", "名单已锁定，不能退出")


def join_closed() -> ApiError:
    return ApiError(422, "join_closed", "这个局已结束或已取消，不能报名")


def game_not_open() -> ApiError:
    return ApiError(422, "game_not_open", "已开打，不能撤局/恢复/修改")


def bring_limit() -> ApiError:
    return ApiError(422, "bring_limit", "最多带 3 人")


def deadline_inverted(msg: str = "开打时间必须晚于截止时间") -> ApiError:
    # 发局的时间拦截共用一个 code（截止不在(现在,开打)内 / 结束早于开打），message 分支说清
    return ApiError(422, "deadline_inverted", msg)


def range_invalid(msg: str = "最少人数不能大于最多人数") -> ApiError:
    # 人数范围拦截共用一个 code（min>max / min 或 max 小于 1），message 分支说清
    return ApiError(422, "range_invalid", msg)


def visibility_invalid() -> ApiError:
    return ApiError(422, "visibility_invalid", "可见档取值非法")


def intent_slots_empty() -> ApiError:
    return ApiError(422, "intent_slots_empty", "至少选一个时段")


def frequency_invalid() -> ApiError:
    return ApiError(422, "frequency_invalid", "打球频率取值不合法")


def booking_invalid(msg: str = "订场登记没填好：场地号和总价都要填") -> ApiError:
    return ApiError(422, "booking_invalid", msg)


def game_ended() -> ApiError:
    # 散场确认后总价定死：改价窗口已关闭
    return ApiError(422, "game_ended", "球局已散场，费用已定死")


# ---- 账单域 ----


def game_not_ended() -> ApiError:
    # 出账仅限散场后：进行中的局不接受补填总价
    return ApiError(422, "game_not_ended", "球局还没散场，散场后才能定总价")


def fee_already_set() -> ApiError:
    # 总价定死不可修改：一旦设定（包含设为 0）禁止二次修改
    return ApiError(409, "fee_already_set", "总价已定死，不能再改")


def fee_invalid() -> ApiError:
    return ApiError(422, "fee_invalid", "总价得是不小于 0 的整数")


def bill_not_found() -> ApiError:
    # 当前球局未出账（未散场/未填价/0元免费局）
    return ApiError(404, "bill_not_found", "这场局还没有账")


def not_on_bill(msg: str = "你不在这场局的摊钱名单里") -> ApiError:
    # 本人不在分摊名单中：404 避免泄漏他人账单
    return ApiError(404, "not_on_bill", msg)


# ---- 现场域 ----


def live_not_found() -> ApiError:
    return ApiError(404, "live_not_found", "现场不存在")


def live_ended() -> ApiError:
    # 散场后旧画面的写动作一律拒收
    return ApiError(409, "live_ended", "球局已结束")


def live_stale_total() -> ApiError:
    # 乐观锁两级号防线·总号旧：退回写请求，最新总账视图随 409 一同返回供对表
    return ApiError(409, "live_stale_total", "现场已更新，请看最新画面再操作")


def live_stale_court() -> ApiError:
    # 乐观锁两级号防线·片号旧：仅拦截冲突场地，其余场地正常
    return ApiError(409, "live_stale_court", "这片现场已更新，请看最新画面再操作")


def court_idle() -> ApiError:
    return ApiError(422, "court_idle", "这片还没开打")


def live_invalid(msg: str) -> ApiError:
    # 现场写动作事实把关不成立（如分低一方不能当胜方）
    return ApiError(422, "live_invalid", msg)


def settle_recorded(sa: int, sb: int) -> ApiError:
    # 记分冲突：该片已被其他人抢先落账，返回已记比分避免并发覆盖
    return ApiError(409, "settle_recorded", f"已按 {sa}:{sb} 记账 · 有异议找组织者")


def rotation_overflow() -> ApiError:
    # 轮转数超两位数护栏（今晚场次/等待批次/连打/到场数 >99）：该片暂停发牌；
    # 主动作已照常提交（越界只拦发牌路径），最新视图随错误体送上
    return ApiError(400, "rotation_overflow", "轮转数超范围，这片暂停发牌")


def live_residue() -> ApiError:
    # 散场入口清扫守卫：残局不清完不放行
    return ApiError(409, "live_residue", "还有没处理完的对局，先逐片处理再散场")


def live_duplicate() -> ApiError:
    # 空降防重：已在现场名册中的账号不得重复新建名册行
    return ApiError(409, "live_duplicate", "你已在现场名册里")


def live_forbidden() -> ApiError:
    # 现场越权提示
    return ApiError(403, "live_forbidden", "请找组织者或管理员")


def organizer_only(msg: str = "只有组织者能做") -> ApiError:
    # 现场域组织者独占操作（封撤管理员/散场收局）
    return ApiError(403, "organizer_only", msg)


# ---- 开账触发权 ----


def live_requires_forced(msg: str = "先锁定必打，才能开始打球") -> ApiError:
    # 未成局（报名中/已散场）禁止开账
    return ApiError(403, "live_requires_forced", msg)


def live_entry_required() -> ApiError:
    # 开账触发权只向正式报名成员开放
    return ApiError(
        403,
        "live_entry_required",
        "要正式报名才能进现场 · 候补可到现场扫二维码入场",
    )


def live_too_early() -> ApiError:
    # 正式成员开账窗口：开打前两小时内开放
    return ApiError(403, "live_too_early", "开打前两小时内才能进现场")


# ---- 装扮域 ----


def cosmetic_not_found() -> ApiError:
    # 编号不在册；跨栏编号（头像栏传了卡背号）对该栏而言同样查无
    return ApiError(404, "cosmetic_not_found", "没有这件装扮")


def cosmetic_not_unlocked() -> ApiError:
    # 未达标的荣誉款 / 未被授予的定制款不能存成穿戴（能不能保存的真值在服务端）
    return ApiError(403, "cosmetic_not_unlocked", "这件装扮还没解锁，不能穿")


def wechat_avatar_missing() -> ApiError:
    # 穿「微信头像」的前提是授权登录那一刻记下过头像；绑定早未记录的暂不给穿
    return ApiError(
        403, "wechat_avatar_missing", "微信头像还没记录过，下次微信授权登录后可用"
    )


# ---- 运维接口读取鉴权 ----


def ops_key_off() -> ApiError:
    return ApiError(403, "ops_key_off", "读取口未开放")


def ops_key_wrong() -> ApiError:
    return ApiError(403, "ops_key_wrong", "钥匙不对")
