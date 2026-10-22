"""装扮册子纯函数契约（1.9 批1）：编号分族唯一、档位结构与规格锁死。

册子是官方资产册（加款加档只改 CATALOG，界面零改动），这里锁的是结构不变量：
编号唯一、kind 与 a-/b- 前缀一致、默认款在册且公共、荣誉三族档位恰为规格裁决
的 5/20/50、3.0~4.5（×10）、3/10/30，定制款独立成档。
"""

from __future__ import annotations

from app.services.cosmetics import (
    CATALOG,
    DEFAULT_AVATAR,
    DEFAULT_BACK,
    by_id,
    defaults,
    honor_thresholds,
    public_items,
)


def test_cids_unique_and_kind_matches_prefix():
    cids = [c.cid for c in CATALOG]
    assert len(cids) == len(set(cids))
    for c in CATALOG:
        # 编号首段即种类：a- 头像 / b- 卡背
        assert c.cid[0] == ("a" if c.kind == "avatar" else "b")
        assert c.kind in ("avatar", "back")
        assert c.tier in ("common", "honor", "custom")


def test_defaults_in_catalog_and_common():
    d_avatar, d_back = defaults()
    assert d_avatar == DEFAULT_AVATAR == "a-p1"
    assert d_back == DEFAULT_BACK == "b-c1"
    for cid, kind in ((d_avatar, "avatar"), (d_back, "back")):
        item = by_id(cid)
        assert item is not None and item.tier == "common" and item.kind == kind
    assert by_id("no-such-cid") is None


def test_public_items_first_batch_shape():
    avatars = [c for c in public_items() if c.kind == "avatar"]
    backs = [c for c in public_items() if c.kind == "back"]
    # 首批：公共头像 6 款（注册卡选一）、公共卡背 4 款
    assert [c.cid for c in avatars] == [f"a-p{i}" for i in range(1, 7)]
    assert [c.cid for c in backs] == [f"b-c{i}" for i in range(1, 5)]


def test_honor_thresholds_cover_spec_tiers():
    # 规格裁决的档位数值锁死；avatar 与 back 两族同档
    assert honor_thresholds("matches") == (5, 20, 50)
    assert honor_thresholds("rating") == (30, 35, 40, 45)  # 台阶×10
    assert honor_thresholds("organize") == (3, 10, 30)
    for c in CATALOG:
        if c.tier == "honor":
            assert c.family in ("matches", "rating", "organize")
            assert c.threshold in honor_thresholds(c.family)
            assert c.lock_text  # 荣誉款必有锁头条件文字（册子定死）


def test_custom_items_tier():
    assert by_id("a-x1").tier == "custom"
    assert by_id("b-x1").tier == "custom"


def test_lock_text_wording_by_family():
    assert by_id("a-m5").lock_text == "参与 5 场对局解锁"
    assert by_id("b-t35").lock_text == "当前分数达到 3.5 即解锁"
    assert by_id("a-o10").lock_text == "张罗 10 局正常散场的球局解锁"
