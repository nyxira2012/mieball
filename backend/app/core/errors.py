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


def card_bg_invalid() -> ApiError:
    return ApiError(422, "card_bg_invalid", "卡背不合法")


def purpose_invalid() -> ApiError:
    return ApiError(422, "purpose_invalid", "验证码用途不合法")


def nickname_invalid(msg: str = "昵称需 1-16 个字符") -> ApiError:
    return ApiError(422, "nickname_invalid", msg)


def chibi_invalid() -> ApiError:
    return ApiError(422, "chibi_invalid", "形象配置不合法")


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


# ---- 球局域（docs/1.2 技术设计 §2.3；账号域旧码一律不动） ----


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
    # 散场确认后总价定死（1.3 §4.5 修订①）：book/clear_booking 的改价窗口已关
    return ApiError(422, "game_ended", "球局已散场，费用已定死")


# ---- 现场域（docs/2.3；球局域旧码一律不动） ----


def live_not_found() -> ApiError:
    return ApiError(404, "live_not_found", "现场不存在")


def live_not_started(msg: str = "现场还没开始") -> ApiError:
    # 同码分支说话（沿 not_organizer 先例）：开账窗口不对等分支由调用方给 message
    return ApiError(409, "live_not_started", msg)


def live_ended() -> ApiError:
    # 散场后旧画面的写动作一律拒收，回这一句（2.3 §4.10/附录 B1）
    return ApiError(409, "live_ended", "球局已结束")


def live_stale_total() -> ApiError:
    # 两级号防线·总号旧（附录 B1）：这笔退回，最新画面随 409 一起送来
    return ApiError(409, "live_stale_total", "现场已更新，请看最新画面再操作")


def live_stale_court() -> ApiError:
    # 两级号防线·片号旧（附录 B1）：只拦该片，别片照常
    return ApiError(409, "live_stale_court", "这片现场已更新，请看最新画面再操作")


def court_idle() -> ApiError:
    return ApiError(422, "court_idle", "这片还没开打")


def live_invalid(msg: str) -> ApiError:
    # 现场写动作的事实把关不成立（发牌名单不在候场队首 / 胜方比分更低等）——
    # 与权限（live_forbidden）、状态机（court_idle/court_frozen）各管一道
    return ApiError(422, "live_invalid", msg)


def court_frozen() -> ApiError:
    # 待确认片整片冻结（2.3 §4.3/4.8）：换人拒收，出口只有清零/取消/确认
    return ApiError(409, "court_frozen", "这片待确认中，暂不能换人")


def live_residue() -> ApiError:
    # 散场入口即清扫（2.3 §4.9）：残局不清完不放行
    return ApiError(409, "live_residue", "还有没处理完的对局，先逐片处理再散场")


def live_forbidden() -> ApiError:
    # 现场越权统一句式（沿 2.2）：球友点结束对局类/清零等动作的提示
    return ApiError(403, "live_forbidden", "请找组织者或管理员")


def organizer_only(msg: str = "只有组织者能做") -> ApiError:
    # 现场域的组织者独占动作（封撤管理员/散场收局）；与球局域 not_organizer 分码不混用
    return ApiError(403, "organizer_only", msg)
