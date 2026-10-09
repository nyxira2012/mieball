"""散场与回看链 + 2.2 域写端点（2.3 批3）—— docs/2.3 §4.9/§4.10 与 2.2 §4.2-4.10：
散场残局拦（live_residue）→ 逐片 no_redeal 处理 / sweep-cancel-all 一键清 → end
落 ended_at+考勤定格（在场者 left_at=散场时刻、已早退保持原时刻、未到者 arrive_at
空）+ round 收口；散场后一切写拒 live_ended；回看 view 游客可读、考勤只给组织者
与本人。管理员：封后同权（可上传可清扫）、不能再封（organizer_only）、org 早退后
可代收散场。check 四态（迟到归一/中途加入/早退清位/回来=join 排队尾）；swap
（playing 片任意到场者可换、outId 回队尾、留名 feed）；tempo（叠加/互斥/连战
排队首）；rules（四件套落账、缩片校验、全权拦）。

时刻基准 FakeClock 10-04 12:00（conftest）；开球时刻 10-06 19:00（test_games_read）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import LivePlayer

from .conftest import signup
from .test_live_score import (
    NOW_ISO,
    court,
    deal_court,
    deal_one,
    live_call,
    live_get,
    open_live,
    write_body,
)

LATER_ISO = "2026-10-04T12:30:00+08:00"  # FakeClock 前进 30 分钟后的散场时刻


def seed_rows(client: TestClient, game_id: int, patch: dict[int, dict]) -> None:
    """直落数据库改名册行：open_live 全员 ok 入队，测试按需改态（沿批2 seed 先例）。"""
    db = client.app.state.session_factory()
    try:
        rows = (
            db.execute(
                select(LivePlayer)
                .where(LivePlayer.game_id == game_id)
                .order_by(LivePlayer.id)
            )
            .scalars()
            .all()
        )
        for i, kw in patch.items():
            for k, v in kw.items():
                setattr(rows[i], k, v)
        db.commit()
    finally:
        db.close()


def pv(view: dict, i: int) -> dict:
    return view["players"][i]


def do_check(client, token, gid, view, row, st) -> object:
    return live_call(
        client,
        token,
        gid,
        "check",
        {"player_id": row["id"], "check": st, "base_total_seq": view["total_seq"]},
    )


# ---- 散场链（§4.9）：残局拦 → 一键清 → 收工封存 ----


def test_end_blocked_by_residue_until_sweep(client: TestClient):
    env = open_live(client, seed=21)
    rows = env["view"]["players"]
    v = deal_one(client, env)
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "end",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_residue"
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "sweep-cancel-all",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert court(v, 1)["status"] == "idle"
    # 全部取消：场上四人原样回流队首（cancel 语义），战报零条
    assert v["queue"] == [r_["id"] for r_ in rows]
    assert v["matches"] == []
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "end",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["ended"] is True and v["ended_at"] == NOW_ISO
    assert v["round"] == 0  # 无落账场数的收口


def test_sweep_per_court_confirm_and_cancel_then_end(client: TestClient):
    env = open_live(client, seed=22, players=9)
    rows = env["view"]["players"]
    ids = [r["id"] for r in rows]
    v = deal_court(
        client,
        env["org"]["token"],
        env["game_id"],
        env["view"],
        [
            {"court_no": 1, "a": ids[:2], "b": ids[2:4]},
            {"court_no": 2, "a": ids[4:6], "b": ids[6:8]},
        ],
    )
    # 在打片即残局（记分本地化：服务端无比分概念，收不了尾就是残局）
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "end",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_residue"
    # 1 号片：清扫态上传（不排下一场、不补位）
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "settle-confirm",
        write_body(v, 1, winner_side="a", score_a=11, score_b=9, no_redeal=True),
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert court(v, 1)["status"] == "idle" and len(v["matches"]) == 1
    assert v["queue"] == [ids[8], *ids[:4]]  # 只回流定格，没人补上
    # 2 号片：清扫态取消
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "cancel",
        write_body(v, 2),
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert court(v, 2)["status"] == "idle"
    assert v["queue"] == [*ids[4:8], ids[8], *ids[:4]]  # 2 号片取消的人回流队首
    r = live_call(
        client,
        env["org"]["token"],
        env["game_id"],
        "end",
        {"base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["ended"] is True and v["round"] == 1


def test_end_seals_attendance_and_round(client, fake):
    env = open_live(client, seed=23, players=7)
    rows = env["view"]["players"]
    gid = env["game_id"]
    seed_rows(
        client,
        gid,
        {
            5: {"check": "absent", "queue_pos": None},
            6: {"check": "absent", "queue_pos": None},
        },
    )
    v = deal_one(client, env)
    v = live_call(
        client,
        env["org"]["token"],
        gid,
        "settle-confirm",
        write_body(v, 1, winner_side="a", score_a=11, score_b=9, no_redeal=True),
    ).json()
    # mate（rows[1]，场上）自报早退：left_at 落当下时刻
    r = do_check(client, env["mate"]["token"], gid, v, rows[1], "left")
    assert r.status_code == 200, r.text
    v = r.json()
    assert pv(v, 1)["left_at"] == NOW_ISO
    fake.advance(minutes=30)
    r = live_call(
        client, env["org"]["token"], gid, "end", {"base_total_seq": v["total_seq"]}
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["ended_at"] == LATER_ISO and v["round"] == 1
    # 考勤定格：在场者离场时刻=散场时刻；已早退者保持原时刻；未到者两头皆空
    assert pv(v, 0)["left_at"] == LATER_ISO
    assert pv(v, 1)["left_at"] == NOW_ISO
    assert pv(v, 5)["left_at"] is None and pv(v, 5)["arrive_at"] is None
    assert pv(v, 6)["left_at"] is None and pv(v, 6)["arrive_at"] is None


def test_after_end_all_writes_rejected_and_recap_visible(client: TestClient):
    env = open_live(client, seed=24)
    rows = env["view"]["players"]
    gid, tok = env["game_id"], env["org"]["token"]
    v = deal_one(client, env)
    v = live_call(
        client,
        tok,
        gid,
        "settle-confirm",
        write_body(v, 1, winner_side="a", score_a=11, score_b=9, no_redeal=True),
    ).json()
    v = live_call(client, tok, gid, "end", {"base_total_seq": v["total_seq"]}).json()
    bodies = {
        "settle-confirm": write_body(v, 1, winner_side="a", score_a=11, score_b=9),
        "settle-overwrite": write_body(v, 1, winner_side="a", score_a=11, score_b=9),
        "check": {
            "player_id": rows[4]["id"],
            "check": "ok",
            "base_total_seq": v["total_seq"],
        },
        "swap": {
            "out_id": rows[0]["id"],
            "in_id": rows[4]["id"],
            "base_total_seq": v["total_seq"],
        },
        "tempo": {
            "player_id": rows[1]["id"],
            "action": "skip",
            "base_total_seq": v["total_seq"],
        },
        "rules": {"doubles": False, "base_total_seq": v["total_seq"]},
        "set-admin": {"player_id": rows[1]["id"], "base_total_seq": v["total_seq"]},
        "sweep-cancel-all": {"base_total_seq": v["total_seq"]},
        "end": {"base_total_seq": v["total_seq"]},
    }
    for action, body in bodies.items():
        r = live_call(client, tok, gid, action, body)
        assert r.status_code == 409 and r.json()["error"]["code"] == "live_ended", (
            action,
            r.text,
        )
    # 回看（§4.10）：游客可读，战报名单公开
    v = live_get(client, gid)
    assert v["ended"] is True and len(v["matches"]) == 1
    assert all(r_["arrive_at"] is None and r_["left_at"] is None for r_ in v["players"])
    # 考勤时刻只给组织者与本人
    v = live_get(client, gid, env["mate"]["token"])
    assert pv(v, 1)["left_at"] == NOW_ISO  # 本人的散场时刻可见
    assert pv(v, 0)["left_at"] is None  # 别人的不可见
    v = live_get(client, gid, tok)
    assert all(r_["left_at"] == NOW_ISO for r_ in v["players"])


# ---- 管理员（2.2 §4.6/4.7/4.14）：封后同权、不能再封、org 早退兜底代收 ----


def test_admin_full_power_then_revoked(client: TestClient):
    env = open_live(client, seed=25)
    rows = env["view"]["players"]
    gid = env["game_id"]
    mate = env["mate"]["token"]
    v = deal_one(client, env)  # 开片（上传权=到场，管理员同权在清扫/改分验）
    # 球友不能封管理员
    r = live_call(
        client,
        mate,
        gid,
        "set-admin",
        {"player_id": rows[2]["id"], "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "organizer_only"
    # 组织者封 mate 为管理员：名单进总账头
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "set-admin",
        {"player_id": rows[1]["id"], "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["admins"] == [rows[1]["account_id"]]
    # 同权：管理员到场即上传结算（球友同样可，全权差异在清扫/改分）
    r = live_call(
        client,
        mate,
        gid,
        "settle-confirm",
        write_body(v, 1, winner_side="a", score_a=11, score_b=9),
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["matches"]) == 1
    # 管理员不能再封别人（§4.6 禁止）
    v = live_get(client, gid, env["org"]["token"])
    r = live_call(
        client,
        mate,
        gid,
        "set-admin",
        {"player_id": rows[2]["id"], "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "organizer_only"
    # 组织者撤掉：名单清空、feed 留痕，撤完即失权
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "unset-admin",
        {"player_id": rows[1]["id"], "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["admins"] == []
    kinds = [e["kind"] for e in v["feed"]]
    assert kinds == ["set_admin", "unset_admin"]
    assert v["feed"][0]["target"] == rows[1]["name"]
    # 撤完即失权：管理员级动作（cancel）球友再调拒
    r = live_call(client, mate, gid, "cancel", write_body(v, 1))
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"


def test_admin_may_end_only_when_organizer_left(client: TestClient):
    env = open_live(client, seed=26)
    rows = env["view"]["players"]
    gid = env["game_id"]
    mate = env["mate"]["token"]
    v = live_get(client, gid, env["org"]["token"])
    v = live_call(
        client,
        env["org"]["token"],
        gid,
        "set-admin",
        {"player_id": rows[1]["id"], "base_total_seq": v["total_seq"]},
    ).json()
    # 无残局时一键清是幂等 no-op：不动账不进号
    r = live_call(
        client, mate, gid, "sweep-cancel-all", {"base_total_seq": v["total_seq"]}
    )
    assert r.status_code == 200 and r.json()["total_seq"] == v["total_seq"]
    v = deal_one(client, env)
    # 组织者未早退：管理员不能散场（organizer_only 先于残局拦）
    r = live_call(client, mate, gid, "end", {"base_total_seq": v["total_seq"]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "organizer_only"
    # 组织者自报早退（自己报自己可）
    r = do_check(client, env["org"]["token"], gid, v, rows[0], "left")
    assert r.status_code == 200, r.text
    v = r.json()
    # 管理员同权清扫 + 代收散场（2.2 §4.14 兜底）
    r = live_call(
        client, mate, gid, "sweep-cancel-all", {"base_total_seq": v["total_seq"]}
    )
    assert r.status_code == 200, r.text
    r = live_call(client, mate, gid, "end", {"base_total_seq": r.json()["total_seq"]})
    assert r.status_code == 200, r.text
    assert r.json()["ended"] is True


# ---- check 四态（2.2 §4.2/4.3/4.5）----


def test_check_queue_states_and_normalization(client, fake):
    env = open_live(client, seed=27, players=7)
    rows = env["view"]["players"]
    gid = env["game_id"]
    mate = env["mate"]["token"]
    seed_rows(
        client,
        gid,
        {
            5: {"check": "absent", "queue_pos": None},
            6: {"check": "absent", "queue_pos": None},
        },
    )
    v = live_get(client, gid, env["org"]["token"])
    assert v["queue"] == [r_["id"] for r_ in rows[:5]]
    # 开球前（10-04 12:00 < 开球 10-06 19:00）：absent 首报 ok 进队尾
    r = do_check(client, env["org"]["token"], gid, v, rows[5], "ok")
    assert r.status_code == 200, r.text
    v = r.json()
    assert pv(v, 5)["check"] == "ok" and v["queue"][-1] == rows[5]["id"]
    assert pv(v, 5)["arrive_at"] == NOW_ISO
    # 代办他人需全权：球友替人报到拒
    r = do_check(client, mate, gid, v, rows[6], "ok")
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"
    # 开球后到场归一迟到、排队尾（fake 前进到 10-07 12:00）
    fake.advance(days=3)
    r = do_check(client, env["org"]["token"], gid, v, rows[6], "ok")
    assert r.status_code == 200, r.text
    v = r.json()
    assert pv(v, 6)["check"] == "late" and v["queue"][-1] == rows[6]["id"]
    # 已在队里的人报 join：改态不动位
    v0 = live_get(client, gid, env["org"]["token"])
    pos = v0["queue"].index(rows[3]["id"])
    r = do_check(client, env["org"]["token"], gid, v0, rows[3], "join")
    v = r.json()
    assert pv(v, 3)["check"] == "join" and v["queue"].index(rows[3]["id"]) == pos
    # 早退：清队列位+落离场时刻；回来=join 排队尾
    v = live_get(client, gid, env["org"]["token"])
    r = do_check(client, env["org"]["token"], gid, v, rows[4], "left")
    v = r.json()
    assert rows[4]["id"] not in v["queue"] and pv(v, 4)["left_at"] is not None
    r = do_check(client, env["org"]["token"], gid, v, rows[4], "ok")
    v = r.json()
    assert pv(v, 4)["check"] == "join" and v["queue"][-1] == rows[4]["id"]


def test_check_left_clears_court_slot_and_comeback(client: TestClient):
    env = open_live(client, seed=28)
    rows = env["view"]["players"]
    gid = env["game_id"]
    v = deal_one(client, env)  # a=[0,1] b=[2,3]，queue [4,5]
    # 场上的人自报早退：清片上位置（片打短维持现状）、记离场时刻
    r = do_check(client, env["mate"]["token"], gid, v, rows[1], "left")
    assert r.status_code == 200, r.text
    v = r.json()
    assert pv(v, 1)["court_no"] is None and pv(v, 1)["court_side"] is None
    assert pv(v, 1)["left_at"] == NOW_ISO
    assert {r_["id"] for r_ in v["players"] if r_["court_side"] == "a"} == {
        rows[0]["id"]
    }
    assert court(v, 1)["status"] == "playing"  # 这局接着打
    assert v["queue"] == [rows[4]["id"], rows[5]["id"]]
    # 回来=join 排队尾，不回片上
    r = do_check(client, env["mate"]["token"], gid, v, rows[1], "ok")
    v = r.json()
    assert pv(v, 1)["check"] == "join"
    assert v["queue"] == [rows[4]["id"], rows[5]["id"], rows[1]["id"]]


def test_check_rejected_while_on_court(client: TestClient):
    env = open_live(client, seed=33)
    rows = env["view"]["players"]
    gid = env["game_id"]
    v = deal_one(client, env)  # rows[0..3] 在 1 号片，queue [4,5]
    # 场上的人自报 join：不得"留片上+进队"双态（总账按 queue_pos/court_no 算）
    r = do_check(client, env["mate"]["token"], gid, v, rows[1], "join")
    assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"
    # 代办 ok/late 同拦（人已在场上不该再报到）
    for st in ("ok", "late"):
        r = do_check(client, env["org"]["token"], gid, v, rows[2], st)
        assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"
    # 拒收不动账：总号未进、片上位置还在、队列原样
    v2 = live_get(client, gid, env["org"]["token"])
    assert v2["total_seq"] == v["total_seq"]
    assert pv(v2, 1)["court_no"] == 1 and pv(v2, 2)["court_no"] == 1
    assert v2["queue"] == [rows[4]["id"], rows[5]["id"]]


# ---- swap（2.2 §4.9；记分本地化后片无冻结窗，playing 片随时可换）----


def test_swap_position_tail_and_feed_note(client: TestClient):
    env = open_live(client, seed=29)
    rows = env["view"]["players"]
    gid = env["game_id"]
    mate = env["mate"]["token"]
    v = deal_one(client, env)
    base = {"base_total_seq": v["total_seq"]}
    # 任意到场者可换（球友的手）：inId 出队顶坑、outId 离片回队尾
    r = live_call(
        client,
        mate,
        gid,
        "swap",
        {"out_id": rows[2]["id"], "in_id": rows[4]["id"], **base},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert pv(v, 4)["court_no"] == 1 and pv(v, 4)["court_side"] == "b"
    assert pv(v, 2)["court_no"] is None
    assert v["queue"] == [rows[5]["id"], rows[2]["id"]]
    # 留名 feed（§4.9-2：全场看得到是谁换的）
    e = v["feed"][-1]
    assert e["kind"] == "swap" and e["actor"] == rows[1]["name"]
    assert e["out"] == rows[2]["name"] and e["in"] == rows[4]["name"]
    # 事实把关：out 不在场上 / in 不在候场队（被拒的写不进号，base 可续用）
    base = {"base_total_seq": live_get(client, gid, env["org"]["token"])["total_seq"]}
    r = live_call(
        client,
        mate,
        gid,
        "swap",
        {"out_id": rows[5]["id"], "in_id": rows[4]["id"], **base},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"
    r = live_call(
        client,
        mate,
        gid,
        "swap",
        {"out_id": rows[0]["id"], "in_id": rows[3]["id"], **base},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"
    # 陌生人（不在名册）不给换
    stranger = signup(client, "13800038888", "s")
    r = live_call(
        client,
        stranger["token"],
        gid,
        "swap",
        {"out_id": rows[0]["id"], "in_id": rows[5]["id"], **base},
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"


# ---- tempo（2.2 §4.10）与 rules（2.2 §4.7）----


def test_tempo_stack_mutex_and_fire_to_head(client: TestClient):
    env = open_live(client, seed=30)
    rows = env["view"]["players"]
    gid = env["game_id"]
    mate = env["mate"]["token"]
    v = live_get(client, gid, env["org"]["token"])
    body = {
        "player_id": rows[1]["id"],
        "action": "skip",
        "base_total_seq": v["total_seq"],
    }
    r = live_call(client, mate, gid, "tempo", body)
    assert r.status_code == 200 and pv(r.json(), 1)["skip"] == 1
    v = r.json()
    r = live_call(
        client, mate, gid, "tempo", {**body, "base_total_seq": v["total_seq"]}
    )
    assert pv(r.json(), 1)["skip"] == 2  # 按一次叠一轮
    v = r.json()
    # 给他人设需全权
    r = live_call(
        client,
        mate,
        gid,
        "tempo",
        {
            "player_id": rows[2]["id"],
            "action": "skip",
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "tempo",
        {
            "player_id": rows[2]["id"],
            "action": "skip",
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 200 and pv(r.json(), 2)["skip"] == 1
    # 连战：互斥清 skip、候场里的人排到队首
    v = r.json()
    r = live_call(
        client,
        mate,
        gid,
        "tempo",
        {
            "player_id": rows[1]["id"],
            "action": "fire",
            "base_total_seq": v["total_seq"],
        },
    )
    v = r.json()
    assert pv(v, 1)["fire"] is True and pv(v, 1)["skip"] == 0
    assert v["queue"][0] == rows[1]["id"]
    # 再按一次取消连战（队列不动）
    r = live_call(
        client,
        mate,
        gid,
        "tempo",
        {
            "player_id": rows[1]["id"],
            "action": "fire",
            "base_total_seq": v["total_seq"],
        },
    )
    v = r.json()
    assert pv(v, 1)["fire"] is False and v["queue"][0] == rows[1]["id"]


def test_rules_patch_and_court_shrink(client: TestClient):
    env = open_live(client, seed=31, players=9)
    rows = env["view"]["players"]
    gid = env["game_id"]
    ids = [r_["id"] for r_ in rows]
    v = live_get(client, gid, env["org"]["token"])
    assert v["courts_count"] == 2  # 未订场按人数回退（9 人 <12 → 2 片）
    r = live_call(
        client,
        env["mate"]["token"],
        gid,
        "rules",
        {"doubles": False, "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "rules",
        {
            "doubles": False,
            "down": "loser",
            "pairing": "balance",
            "streak_max": 5,
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["rules"] == {
        "scoring": 11,
        "doubles": False,
        "down": "loser",
        "pairing": "balance",
        "streak_max": 5,
    }
    # 片数放开到 3；开两片后不能收到 1（在用的片不能收）
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "rules",
        {"courts_count": 3, "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200 and r.json()["courts_count"] == 3
    v = deal_court(
        client,
        env["org"]["token"],
        gid,
        r.json(),
        [
            {"court_no": 1, "a": ids[:2], "b": ids[2:4]},
            {"court_no": 2, "a": ids[4:6], "b": ids[6:8]},
        ],
    )
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "rules",
        {"courts_count": 1, "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"
    # 撤掉 2 号片（取消后 idle）：缩片先撤空闲片、在打的保住
    v = live_call(client, env["org"]["token"], gid, "cancel", write_body(v, 2)).json()
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "rules",
        {"courts_count": 1, "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["courts_count"] == 1
    assert [c["court_no"] for c in v["courts"]] == [1]
    assert court(v, 1)["status"] == "playing"


def test_rules_scoring_writes_game_column_and_court_snapshot(client: TestClient):
    """改分制切真（2.6 机制A）：rules 带 scoring 写 game 列真值（view rules 块回
    新值），在打片快照不回头；不带 scoring 的调用不动原值。"""
    env = open_live(client, seed=35)
    gid = env["game_id"]
    v = deal_one(client, env)
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "rules",
        {"doubles": False, "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["rules"]["scoring"] == 11  # 不带 scoring：不动原值
    assert court(v, 1)["scoring"] == 11  # 开赛片自带快照字段
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "rules",
        {"scoring": 21, "base_total_seq": v["total_seq"]},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["rules"]["scoring"] == 21
    assert court(v, 1)["scoring"] == 11  # 在打片照旧打完旧制


def test_deal_rejected_beyond_courts_count(client: TestClient):
    env = open_live(client, seed=34)
    rows = env["view"]["players"]
    gid = env["game_id"]
    ids = [r_["id"] for r_ in rows]
    v = live_get(client, gid, env["org"]["token"])
    assert v["courts_count"] == 2  # 6 人未订场 → 2 片
    # 3 号片超出场地数：拒（下界 ge=1 归路由，上界对总账真值 courts_count）
    r = live_call(
        client,
        env["org"]["token"],
        gid,
        "deal",
        {
            "courts": [{"court_no": 3, "a": ids[:2], "b": ids[2:4]}],
            "base_total_seq": v["total_seq"],
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "live_invalid"
    v2 = live_get(client, gid, env["org"]["token"])
    assert v2["total_seq"] == v["total_seq"] and v2["courts"] == []


def test_new_actions_gated_by_total_seq(client: TestClient):
    env = open_live(client, seed=32)
    rows = env["view"]["players"]
    gid = env["game_id"]
    v = live_get(client, gid, env["org"]["token"])
    v2 = live_call(
        client,
        env["org"]["token"],
        gid,
        "tempo",
        {
            "player_id": rows[1]["id"],
            "action": "skip",
            "base_total_seq": v["total_seq"],
        },
    ).json()
    # 旧总号（连击/断网重发）：退回并携最新画面
    r = do_check(client, env["org"]["token"], gid, v, rows[4], "ok")
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_stale_total"
    assert r.json()["view"]["total_seq"] == v2["total_seq"]
