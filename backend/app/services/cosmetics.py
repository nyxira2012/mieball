"""装扮册子与装扮页账房 —— 官方资产册（编号/名称/档位/解锁条件/卡背焦点）+
解锁核算/保存把关/页面组装。册子常量是数据真值，读侧身份下发（dress_fields）
与装扮页 API 都从这里取口径；DB 访问经调用方传入的 Session（dress_fields 仍走
鸭子类型读列，本模块不因此反向依赖 accounts）。
编号分族自带"怎么拿的"来历，不另记获得流水：
- a-p*/b-c* 公共款（人人可用，不入个人解锁清单）
- a-m*/b-m* 场数族（参与对局 5/20/50 场）·a-t*/b-t* 台阶族（DUPR×10）·
  a-o*/b-o* 组局族（张罗正常散场局 3/10/30 局）——荣誉款只走达标核算
- a-x*/b-x* 定制款（仅运维授予；册子整本一份，未授予者的装扮页不显示该节）
素材按约定路径摆放（约定优于配置，册子不存路径）：/cosmetics/{cid}.png
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from ..core import errors
from ..db.models import Game, LiveMatch
from .dupr import GUEST_DUPR
from .playlog import playlog_source

logger = logging.getLogger(__name__)

DEFAULT_AVATAR = "a-p1"
DEFAULT_BACK = "b-c1"
# 首批统一卡背焦点（素材管线就位后按图逐件登记，册子已留 per-item 位）
FOCUS_X = 0.68
FOCUS_Y = 0.37


@dataclass(frozen=True)
class Cosmetic:
    cid: str
    kind: str  # "avatar" | "back"
    tier: str  # "common" | "honor" | "custom"
    name: str
    family: str | None  # 荣誉款："matches" | "rating" | "organize"
    threshold: int | None  # matches=场数 / rating=台阶×10 / organize=局数
    lock_text: str | None  # 锁头条件文字（册子定死，界面一字不改）
    fx: float = 0.0  # 卡背主体焦点（头像无取景概念，恒 0）
    fy: float = 0.0


# 荣誉族三件套：族名 / 档位 / 锁头文字模板（rating 档位是分数×10 的整数）
_HONOR_FAMILIES = (
    ("matches", (5, 20, 50), "参与 {n} 场对局解锁"),
    ("rating", (30, 35, 40, 45), "当前分数达到 {t} 即解锁"),
    ("organize", (3, 10, 30), "张罗 {n} 局正常散场的球局解锁"),
)
_FAMILY_CID = {"matches": "m", "rating": "t", "organize": "o"}
# 占位名（正式名随素材批次换册子，本批先立结构与口径）
_FAMILY_LABEL = {"matches": "场数", "rating": "台阶", "organize": "组局"}


def _tier_label(family: str, threshold: int) -> str:
    return f"{threshold / 10:.1f}" if family == "rating" else str(threshold)


def _build_catalog() -> tuple[Cosmetic, ...]:
    items = [
        Cosmetic(f"a-p{i}", "avatar", "common", f"球友{i}", None, None, None)
        for i in range(1, 7)
    ]
    items += [
        Cosmetic(
            f"b-c{i}",
            "back",
            "common",
            f"基础卡背{i}",
            None,
            None,
            None,
            FOCUS_X,
            FOCUS_Y,
        )
        for i in range(1, 5)
    ]
    for family, tiers, lock in _HONOR_FAMILIES:
        letter = _FAMILY_CID[family]
        for t in tiers:
            label = _tier_label(family, t)
            lock_text = lock.format(n=t, t=label)
            name = f"{_FAMILY_LABEL[family]}{label}档"
            items.append(
                Cosmetic(
                    f"a-{letter}{t}",
                    "avatar",
                    "honor",
                    f"{name}头像",
                    family,
                    t,
                    lock_text,
                )
            )
            items.append(
                Cosmetic(
                    f"b-{letter}{t}",
                    "back",
                    "honor",
                    f"{name}卡背",
                    family,
                    t,
                    lock_text,
                    FOCUS_X,
                    FOCUS_Y,
                )
            )
    items.append(Cosmetic("a-x1", "avatar", "custom", "定制头像", None, None, None))
    items.append(
        Cosmetic(
            "b-x1", "back", "custom", "定制卡背", None, None, None, FOCUS_X, FOCUS_Y
        )
    )
    return tuple(items)


CATALOG: tuple[Cosmetic, ...] = _build_catalog()
_BY_ID = {c.cid: c for c in CATALOG}


def by_id(cid: str) -> Cosmetic | None:
    return _BY_ID.get(cid)


def defaults() -> tuple[str, str]:
    return DEFAULT_AVATAR, DEFAULT_BACK


def public_items() -> tuple[Cosmetic, ...]:
    return tuple(c for c in CATALOG if c.tier == "common")


def honor_thresholds(family: str) -> tuple[int, ...]:
    # 去重出档：头像与卡背两族同档注册（核算按 CATALOG 全表扫，这里给档位清单）
    return tuple(
        sorted(
            {c.threshold for c in CATALOG if c.tier == "honor" and c.family == family}
        )
    )


def asset_url(cid: str) -> str:
    return f"/cosmetics/{cid}.png"


def default_dress() -> dict:
    """默认公共款三键：老账号（列 NULL）、注销者、缺行共用的读侧兜底形状。"""
    return {
        "avatar": DEFAULT_AVATAR,
        "avatar_url": asset_url(DEFAULT_AVATAR),
        "back": DEFAULT_BACK,
    }


def dress_fields(account) -> dict:
    """身份下发的装扮三键单一源（person_view/view/战力榜/现场名册共吃；账号行
    经鸭子类型读列，本模块因此不依赖 ORM）：
    - avatar=穿戴值原样（册子编号或 'wechat'），NULL/未穿兜默认第一款公共头像——
      存量老账号不迁移（C3 旧数据原样），读侧兜底即全部兼容面
    - avatar_url=解析好的素材路径；'wechat' 的真值是授权时刻顺手记录的 URL，
      还没记录过（绑定早、功能上线后未再授权）回退默认公共款路径，不露破图
    - back=卡背编号，NULL 兜默认公共卡背
    """
    wearing = getattr(account, "dress_avatar", None)
    if not wearing:
        return default_dress()
    if wearing == "wechat":
        url = getattr(account, "wechat_avatar", None) or asset_url(DEFAULT_AVATAR)
        return {
            "avatar": "wechat",
            "avatar_url": url,
            "back": getattr(account, "dress_back", None) or DEFAULT_BACK,
        }
    return {
        "avatar": wearing,
        "avatar_url": asset_url(wearing),
        "back": getattr(account, "dress_back", None) or DEFAULT_BACK,
    }


# ---- 装扮页账房（核算/保存/组装；DB 经传入 Session，册子常量与判定同处一册） ----

# 册子 family 名 → progress 键：organize 族在册子里叫 organize、进度定值叫 organizes
_FAMILY_PROGRESS_KEY = {"matches": "matches", "organize": "organizes"}


def _unlocked_rows(account) -> list[dict]:
    """unlocks 列的容错读：NULL/空/坏 JSON → 空清单——坏数据不拦装扮页开门。"""
    raw = getattr(account, "unlocks", None)
    if not raw:
        return []
    try:
        rows = json.loads(raw)
    except ValueError:
        return []
    # JSON 标量/字典形状不是清单：迭代标量会 TypeError 炸 500，容错承诺在此兑现
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("id")]


def _threshold_met(item: Cosmetic, progress: dict) -> bool:
    if item.family == "rating":
        # 未定级不判台阶：分数还不算数，台阶款只显示条件原文不算「还差多少分」
        return not progress["rating_provisional"] and progress["rating"] * 10 >= (
            item.threshold or 0
        )
    return progress[_FAMILY_PROGRESS_KEY[item.family]] >= (item.threshold or 0)


def recount(db: Session, account) -> dict:
    """打开装扮页时的顺手核算：三类进度各翻一笔现成账，过线的荣誉款追加进
    解锁清单。判定只看当下 + 只增不减（解锁后掉分/改账不收回——写入口只补
    不删）。整个核算兜底：失败不拦路（按上次清单照常开门），只留 warn 记号。
    """
    try:
        # stats 已依赖本模块的 dress_fields（身份下发三键单一源），此处反向
        # 取用 StatsLedger 必须晚绑定，顶层互相 import 即成环
        from .stats import StatsLedger

        matches = playlog_source(db, account.id)[1]  # 从宽：落账即算、撤销局照计
        card = StatsLedger(db).card(account.id)
        organizes = db.execute(
            select(func.count())
            .select_from(Game)
            .where(
                Game.organizer_id == account.id,
                # ended_at 天然排除撤销局（撤销只落 cancelled_at），别做双份过滤；
                # EXISTS 排除零对局的空散场局——张罗成就认「真打过的散场」
                Game.ended_at.is_not(None),
                exists(select(LiveMatch.id).where(LiveMatch.game_id == Game.id)),
            )
        ).scalar_one()
        progress = {
            "matches": matches,
            "rating": card["rating"],
            "rating_provisional": card["provisional"],
            "organizes": organizes,
        }
        owned = {r["id"] for r in _unlocked_rows(account)}
        fresh = [
            {"id": c.cid, "new": True}
            for c in CATALOG
            if c.tier == "honor" and c.cid not in owned and _threshold_met(c, progress)
        ]
        if fresh:
            rows = _unlocked_rows(account) + fresh
            account.unlocks = json.dumps(rows, ensure_ascii=False)
            db.commit()
        return progress
    except Exception:  # 核算失败不拦路（装扮页照常按上次清单开门），只留 warn 记号
        logger.warning("cosmetics recount failed account=%s", account.id, exc_info=True)
        return {
            "matches": 0,
            "rating": GUEST_DUPR,
            "rating_provisional": True,
            "organizes": 0,
        }


def dress(
    db: Session, account, *, avatar: str | None = None, back: str | None = None
) -> dict:
    """保存穿戴的服务端把关（界面上变灰只是前置提示，能不能存的真值在这里）：
    未传的栏不动——穿戴永远「最后保存的赢」。全过才写列，返回兜底后的穿戴视图。
    """
    owned = {r["id"] for r in _unlocked_rows(account)}
    for value, kind in ((avatar, "avatar"), (back, "back")):
        if value is None:
            continue
        if value == "wechat" and kind == "avatar":
            # 穿微信头像的前提：授权那一刻已记下头像；'wechat' 只是头像栏的语义值
            if not account.wechat_avatar:
                raise errors.wechat_avatar_missing()
            continue
        item = by_id(value)
        # 跨栏编号（如头像栏传卡背号）对该栏而言不在册
        if item is None or item.kind != kind:
            raise errors.cosmetic_not_found()
        if item.tier != "common" and value not in owned:
            raise errors.cosmetic_not_unlocked()
    if avatar is not None:
        account.dress_avatar = avatar
    if back is not None:
        account.dress_back = back
    db.commit()
    return dress_fields(account)


def dressing_page(db: Session, account) -> dict:
    """装扮页全视图的组装单点：顺手核算 → 组装响应 → 清「新」标落库。
    「新」标口径：本次看到、下次进页即摘——响应先带上含 new 的清单，随后把
    落库的 new 全置 False。定制款条目层裁剪：未授予者的 items/unlocks 都不含，
    连「别人有你没有」的暗示都不透出。
    """
    progress = recount(db, account)
    rows = _unlocked_rows(account)
    owned = {r["id"] for r in rows}
    fresh = {r["id"] for r in rows if r.get("new")}
    items = [
        {
            "cid": c.cid,
            "kind": c.kind,
            "tier": c.tier,
            "name": c.name,
            # family/threshold 是前端派生「还差 X」的原料（lock_text 只给条件原文）
            "family": c.family,
            "threshold": c.threshold,
            "lock_text": c.lock_text,
            "fx": c.fx,
            "fy": c.fy,
            "asset": asset_url(c.cid),
        }
        for c in CATALOG
        if c.tier != "custom" or c.cid in owned
    ]
    unlocks = {
        c.cid: {"unlocked": c.cid in owned, "is_new": c.cid in fresh}
        for c in CATALOG
        if c.tier == "honor" or c.cid in owned
    }
    if fresh:
        account.unlocks = json.dumps(
            [{"id": r["id"], "new": False} for r in rows], ensure_ascii=False
        )
        db.commit()
    wearing = dress_fields(account)
    return {
        "items": items,
        "unlocks": unlocks,
        "wearing": {"avatar": wearing["avatar"], "back": wearing["back"]},
        "progress": progress,
        "wechat_avatar_available": bool(account.wechat_avatar),
    }
