"""规则版本记号（6.1 批5）—— spec §4.4 的锁：明细与账单落账即打版本记号、
改分重落（删行重插走同一 snap）新行照带、记号只进库不出口（名片/现场视图/
战力榜/账单页响应体均无 rule_version 字段）、存量不回填（旧库补列后旧行仍 NULL）。

版本单一源：dupr.RULES_VERSION / bills.SPLIT_VERSION——改规矩必换新记号
（两处 docstring 警示），届时本文件的 "v1" 字面量锁会红，提醒同步改（有意为之）。
"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db.engine import Base, make_session_factory
from app.db.models import Bill, DuprDetail
from app.main import create_app
from app.services import dupr
from app.services.bills import SPLIT_VERSION

from .test_bills_generate import book_fee, end_live
from .test_live_score import (
    confirm,
    deal_one,
    open_live,
    overwrite,
    settled_11_9,
)


def details_of(client: TestClient, game_id: int) -> list[DuprDetail]:
    """拉一场局的明细行（detached 只读列，关会话后仍可取属性）。"""
    db = client.app.state.session_factory()
    try:
        return (
            db.execute(select(DuprDetail).where(DuprDetail.game_id == game_id))
            .scalars()
            .all()
        )
    finally:
        db.close()


def bill_of(client: TestClient, game_id: int) -> Bill | None:
    db = client.app.state.session_factory()
    try:
        return db.execute(
            select(Bill).where(Bill.game_id == game_id)
        ).scalar_one_or_none()
    finally:
        db.close()


# ---- 落账即打版本（spec §4.4） ----


def test_settled_details_carry_rules_version(client: TestClient):
    env = open_live(client, seed=211, players=6, bring=1)
    settled_11_9(client, env)
    rows = details_of(client, env["game_id"])
    assert len(rows) == 3  # 注册球员每人一行（访客不落）
    assert {d.rule_version for d in rows} == {dupr.RULES_VERSION}
    assert dupr.RULES_VERSION == "v1"  # 当前版本锁：换规矩换号时此处必红


def test_generated_bill_carries_split_version(client: TestClient):
    env = open_live(client, seed=212, players=6)
    book_fee(client, env["org"]["token"], env["game_id"], 100)
    end_live(client, env)
    bill = bill_of(client, env["game_id"])
    assert bill is not None
    assert bill.rule_version == SPLIT_VERSION
    assert SPLIT_VERSION == "v1"  # 当前版本锁：改摊费规则换号时此处必红


def test_overwrite_reinserted_details_still_carry_version(client: TestClient):
    """改分重落：删行重插走同一 snap（live.py settle_overwrite → StatsLedger），
    新行自动带记号——不需要 overwrite 链路自己记得填。（不拿 id 变化当重插证据：
    SQLite 删掉表尾行后 rowid 会复用，这里用胜负翻面证明行真的重写了。）"""
    env = open_live(client, seed=213, players=6, bring=1)
    v = settled_11_9(client, env)
    before = {d.account_id: d.won for d in details_of(client, env["game_id"])}
    r = overwrite(
        client,
        env["org"]["token"],
        env["game_id"],
        v,
        winner_side="b",
        score_a=9,
        score_b=11,
    )
    assert r.status_code == 200, r.text
    rows = details_of(client, env["game_id"])
    assert len(rows) == 3  # 注册球员每人一行（访客不落）
    assert {d.account_id for d in rows} == set(before)
    for d in rows:  # 新行按新胜负重写（翻面=真删行重插，不是原行带旧值）
        assert d.won is not before[d.account_id]
        assert (d.score_w, d.score_l) == (11, 9)
    assert {d.rule_version for d in rows} == {dupr.RULES_VERSION}


# ---- 只进库不出口（球友界面不显示，spec §4.4） ----


def test_rule_version_never_in_any_response(client: TestClient):
    """球友可见的四类读口（名片 me / 现场 live / 战力榜 / 账单页）响应体
    都不含 rule_version 字段——记号是排障地基，不是产品口径。"""
    env = open_live(client, seed=214, players=6)
    book_fee(client, env["org"]["token"], env["game_id"], 100)
    # no_redeal：结算后不续场（片转 idle），散场不被「还有没处理完的对局」拦
    v = confirm(
        client,
        env["org"]["token"],
        env["game_id"],
        deal_one(client, env),
        no_redeal=True,
    ).json()
    end_live(client, env, v)  # 散场出账（带最新画面：total_seq 已被结算推进）
    h = {"Authorization": f"Bearer {env['org']['token']}"}
    for r in (
        client.get("/api/auth/me", headers=h),
        client.get(f"/api/games/{env['game_id']}/live", headers=h),
        client.get("/api/stats/leaderboard"),
        client.get("/api/bills", headers=h),
    ):
        assert r.status_code == 200, r.text
        assert "rule_version" not in r.text


# ---- 存量迁移：_NEW_COLUMNS 补列、旧行 NULL 不回填 ----


def test_legacy_db_column_added_rows_not_backfilled(tmp_path, fake):
    """旧库场景：按新模型建全量 schema 再 DROP 两列 = 旧版代码建的库（免手写
    旧 DDL 漂移）；埋一行旧明细/一本旧账后启动 create_app——_NEW_COLUMNS 补列、
    旧行保持 NULL（不回填），此后新落的明细照常带记号。"""
    db_path = tmp_path / "legacy.db"
    factory = make_session_factory(f"sqlite:///{db_path}")
    Base.metadata.create_all(factory.kw["bind"])
    factory.kw["bind"].dispose()
    con = sqlite3.connect(db_path)
    con.execute("ALTER TABLE dupr_details DROP COLUMN rule_version")
    con.execute("ALTER TABLE bills DROP COLUMN rule_version")
    # 存量行（旧规矩时代落的，game_id=999 不与新局撞号；SQLite 未开外键约束）
    con.execute(
        "INSERT INTO dupr_details (account_id, match_id, game_id, ended_at,"
        " partner_rating, opp_a, opp_b, score_w, score_l, won)"
        " VALUES (999, 1, 999, '2026-01-01 00:00:00', 2.5, 2.5, 2.5, 11, 9, 1)"
    )
    con.execute(
        "INSERT INTO bills (game_id, fee_total, heads, per_head, billed_at)"
        " VALUES (999, 100, 4, 25, '2026-01-01 00:00:00')"
    )
    con.commit()
    con.close()

    client = TestClient(
        create_app(
            Settings(
                db_url=f"sqlite:///{db_path}",
                pepper="test-pepper",
                sms_provider="console",
                sms_daily_budget=200,
                log_dir=str(tmp_path / "logs"),
            )
        )
    )

    # 补列生效且旧行 NULL=不回填（旧账按当时的规矩算的，不追认新记号）
    legacy = details_of(client, 999)
    assert len(legacy) == 1 and legacy[0].rule_version is None
    assert bill_of(client, 999).rule_version is None

    # 补列后的库照常营业：新结算的明细行带当前记号
    env = open_live(client, seed=215, players=6, bring=1)
    settled_11_9(client, env)
    rows = details_of(client, env["game_id"])
    assert len(rows) == 3 and {d.rule_version for d in rows} == {dupr.RULES_VERSION}
