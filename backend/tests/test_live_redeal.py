"""重排这片（2.8 §4.4，验收 11）：全权取消+立刻重发二合一——在打片场上的人原样
回流队首（与 cancel 共用 _void_court 一段账面动作）、同事务出口补片按最新规矩
重发（歇轮跳过消耗、坑下位顶、恰一 bump）、空片重排=补片；歇+重排专例（这轮
不上、保位、下一场第一个上）；非全权 403、散场后拒、两级号 409 携最新视图、
同拍重放被号闸退回（回流+补片无重复人面）、审计行 live_redeal。

脚手架沿 test_live_score（open_live/deal_one/confirm/live_call 可 import）；
时刻基准 FakeClock 10-04 12:00（conftest）。
"""

from __future__ import annotations

from pathlib import Path

from .test_live_score import (
    confirm,
    court,
    deal_one,
    live_call,
    live_get,
    open_live,
    player,
    side_ids,
    tempo,
    write_body,
)
from .test_logs import audit_rows, make_client


def redeal(client, token: str, game_id: int, view: dict, **over):
    """重排一笔：默认 1 号片、两级号吃视图，over 覆写载荷。"""
    return live_call(client, token, game_id, "redeal", write_body(view, 1) | over)


def test_redeal_playing_reflows_and_redeals(client):
    """验收 11 全链：全权重排在打片 → 场上的人原样回流队首 → 同事务立刻重发——
    歇者被跳过（消耗一次、保位回队首）、坑由下位顶；一次号跳、作废不留战报。"""
    env = open_live(client, seed=91)
    rows = env["view"]["players"]
    gid, tok = env["game_id"], env["org"]["token"]
    v = deal_one(client, env)  # 0-3 上场、4-5 候场
    v = tempo(client, tok, gid, v, rows[2]["id"], "skip")  # 场上设歇
    seq_before = v["total_seq"]
    r = redeal(client, tok, gid, v)
    assert r.status_code == 200, r.text
    v = r.json()
    # 回流即重发：歇者 2 跳过、坑由 4 顶；原样回流保行序 → 2 保位队首
    assert court(v, 1)["status"] == "playing"
    assert side_ids(v, 1, "a") == {rows[0]["id"], rows[1]["id"]}
    assert side_ids(v, 1, "b") == {rows[3]["id"], rows[4]["id"]}
    assert player(v, rows[2]["id"])["skip"] == 0
    assert v["queue"] == [rows[2]["id"], rows[5]["id"]]
    assert v["total_seq"] == seq_before + 1  # 回流+重发一拍、恰一 bump
    assert v["matches"] == []  # 作废不留战报


def test_redeal_skipper_sits_then_first_up_next(client):
    """合同 §4.4 用户故事 2（歇+重排专例）：场上设歇 → 重排 → 歇者这轮不上、
    保位在队首；这场打完下一场第一个轮到他。"""
    env = open_live(client, seed=92, players=5)
    rows = env["view"]["players"]
    gid, tok = env["game_id"], env["org"]["token"]
    v = deal_one(client, env)  # 0-3 上场、4 候场
    v = tempo(client, tok, gid, v, rows[0]["id"], "skip")
    r = redeal(client, tok, gid, v)
    assert r.status_code == 200, r.text
    v = r.json()
    assert side_ids(v, 1, "a") == {rows[1]["id"], rows[2]["id"]}
    assert side_ids(v, 1, "b") == {rows[3]["id"], rows[4]["id"]}
    assert v["queue"] == [rows[0]["id"]]  # 保位：歇者独占队首
    assert player(v, rows[0]["id"])["skip"] == 0  # 这轮已消耗
    r = confirm(client, tok, gid, v)  # 这场打完（全上全下）
    assert r.status_code == 200, r.text
    v = r.json()
    assert rows[0]["id"] in side_ids(v, 1, "a")  # 下一场第一个上


def test_redeal_idle_court_is_refill(client):
    """空片重排=补片（§4.4「这片空闲→等于补片」）：作废后的空片照常重发；
    没开过行的空片（视图无行、前端片号补 0）也收。"""
    env = open_live(client, seed=93)
    rows = env["view"]["players"]
    gid, tok = env["game_id"], env["org"]["token"]
    v = deal_one(client, env)
    r = live_call(client, tok, gid, "cancel", write_body(v, 1) | {"no_redeal": True})
    assert r.status_code == 200, r.text
    v = r.json()
    assert court(v, 1)["status"] == "idle"
    r = redeal(client, tok, gid, v)
    assert r.status_code == 200, r.text
    v = r.json()
    assert court(v, 1)["status"] == "playing"
    assert side_ids(v, 1, "a") == {rows[0]["id"], rows[1]["id"]}
    assert side_ids(v, 1, "b") == {rows[2]["id"], rows[3]["id"]}
    assert v["queue"] == [rows[4]["id"], rows[5]["id"]]

    env2 = open_live(client, seed=94)
    rows2 = env2["view"]["players"]
    r = live_call(
        client,
        env2["org"]["token"],
        env2["game_id"],
        "redeal",
        {
            "court_no": 1,
            "base_total_seq": env2["view"]["total_seq"],
            "base_court_seq": 0,  # 没开过行：视图无片行，前端补 0
        },
    )
    assert r.status_code == 200, r.text
    v2 = r.json()
    assert court(v2, 1)["status"] == "playing"
    assert side_ids(v2, 1, "a") == {rows2[0]["id"], rows2[1]["id"]}
    assert v2["queue"] == [rows2[i]["id"] for i in (4, 5)]  # 2 号片候场不够不硬开


def test_redeal_full_power_only(client):
    """禁止非全权重排（§4.4）：普通到场球友 403、账面不动。"""
    env = open_live(client, seed=95)
    v = deal_one(client, env)
    r = redeal(client, env["mate"]["token"], env["game_id"], v)
    assert r.status_code == 403 and r.json()["error"]["code"] == "live_forbidden"
    assert (
        live_get(client, env["game_id"], env["org"]["token"])["total_seq"]
        == v["total_seq"]
    )


def test_redeal_rejected_after_end(client):
    """散场后写天然被 _open_write 拒（§4.10）：旧画面的重排钮按了也白按。"""
    env = open_live(client, seed=96)
    gid, tok = env["game_id"], env["org"]["token"]
    v = deal_one(client, env)
    r = live_call(client, tok, gid, "cancel", write_body(v, 1) | {"no_redeal": True})
    assert r.status_code == 200, r.text
    r = live_call(client, tok, gid, "end", {"base_total_seq": r.json()["total_seq"]})
    assert r.status_code == 200, r.text
    r = redeal(client, tok, gid, v)
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_ended"


def test_redeal_stale_seqs_409_with_latest_view(client):
    """两级号闸沿确认同款：总号旧 / 片号旧都 409 携最新视图。"""
    env = open_live(client, seed=97)
    gid, tok = env["game_id"], env["org"]["token"]
    v = deal_one(client, env)
    r = redeal(client, tok, gid, v, base_total_seq=v["total_seq"] - 1)
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_stale_total"
    assert r.json()["view"]["total_seq"] == v["total_seq"]

    r = redeal(client, tok, gid, v)  # 先重排一次推进片号
    assert r.status_code == 200, r.text
    v1 = r.json()
    r = redeal(client, tok, gid, v1, base_court_seq=court(v, 1)["court_seq"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_stale_court"
    assert court(r.json()["view"], 1)["court_seq"] == court(v1, 1)["court_seq"]


def test_redeal_replay_safe_no_duplicates(client):
    """同拍重放（同号同片）必被号闸退回——回流+补片无账面突变面，落位与队列
    无重复人（重排把同一批人再排一次也只是同一落位）。"""
    env = open_live(client, seed=98)
    gid, tok = env["game_id"], env["org"]["token"]
    v = deal_one(client, env)
    r = redeal(client, tok, gid, v)
    assert r.status_code == 200, r.text
    after = r.json()
    r = redeal(client, tok, gid, v)  # 原载荷重放
    assert r.status_code == 409 and r.json()["error"]["code"] == "live_stale_total"
    v = r.json()["view"]
    assert side_ids(v, 1, "a") == side_ids(after, 1, "a")
    assert side_ids(v, 1, "b") == side_ids(after, 1, "b")
    assert v["queue"] == after["queue"]
    oncourt = [p["id"] for p in v["players"] if p["court_side"] in ("a", "b")]
    assert len(oncourt) == len(set(oncourt))
    assert len(v["queue"]) == len(set(v["queue"]))
    assert not set(oncourt) & set(v["queue"])


def test_redeal_audited(tmp_path: Path, fake):
    """审计行：live_redeal 带 game_id/操作人/detail=片号；被拒路径不落。"""
    logs_dir = tmp_path / "logs"
    client = make_client(tmp_path)
    env = open_live(client, seed=99)
    gid, org = env["game_id"], env["org"]
    v = deal_one(client, env)
    r = redeal(client, org["token"], gid, v)
    assert r.status_code == 200, r.text
    row = next(x for x in audit_rows(logs_dir) if x["action"] == "live_redeal")
    assert row["game_id"] == gid
    assert row["account_id"] == org["account"]["id"]
    assert row["detail"] == "court=1"
    r = redeal(client, env["mate"]["token"], gid, v)
    assert r.status_code == 403
    assert len([x for x in audit_rows(logs_dir) if x["action"] == "live_redeal"]) == 1
