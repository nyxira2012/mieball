"""装扮册子 —— 全站装扮的官方资产册（编号/名称/档位/解锁条件/卡背焦点）。

纯常量+纯函数模块（零 ORM import 零框架依赖，沿 dupr.py 口径常量先例）：册子是
数据真值，读侧身份下发（dress_fields）与装扮页核算/API（批2）都从这里取口径。
编号分族自带"怎么拿的"来历，不另记获得流水：
- a-p*/b-c* 公共款（人人可用，不入个人解锁清单）
- a-m*/b-m* 场数族（参与对局 5/20/50 场）·a-t*/b-t* 台阶族（DUPR×10）·
  a-o*/b-o* 组局族（张罗正常散场局 3/10/30 局）——荣誉款只走达标核算
- a-x*/b-x* 定制款（仅运维授予；册子整本一份，未授予者的装扮页不显示该节）
素材按约定路径摆放（约定优于配置，册子不存路径）：/cosmetics/{cid}.png
"""

from __future__ import annotations

from dataclasses import dataclass

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
