#!/usr/bin/env python3
"""manage_users —— Mieball 用户检索与密码重置运维工具 (支持远程 ECS 与本地开发库)

功能速览：
  - 🔍 检索用户：支持按 ID、手机号模糊、昵称模糊检索
  - 📋 列表展示：查看最新注册用户或全部在册用户
  - 🔑 重置密码：一键为指定用户（或批量为全部用户）设置密码（默认 123456）
  - 🔓 账号解锁：清空连续输错密码导致的 15 分钟锁定状态
  - 🎁 发卡收卡：往解锁清单发放/收回定制款装扮（可顺手穿上；收回时正穿着自动退默认）
  - 🧩 跨端记号三动作：翻「跨端绑定不一致」清单 / 清记号 / 把小程序钥匙搬到该去的号
  - 🌐 环境自由切换：默认操作阿里云 ECS 线上生产库，加 --local 切换至本地开发库

常见用法：
  python3 scripts/manage_users.py                          # 查看最新 10 个用户与使用帮助
  python3 scripts/manage_users.py -l                       # 查看最新 10 个用户
  python3 scripts/manage_users.py -l all                   # 查看所有用户
  python3 scripts/manage_users.py -s 133                   # 搜索手机号或昵称包含 133 的用户
  python3 scripts/manage_users.py -s 测试员                # 搜索昵称包含“测试员”的用户
  python3 scripts/manage_users.py -r 4                     # 重置 ID 为 4 的用户密码为 123456
  python3 scripts/manage_users.py -r 13300009999 -p 666888 # 为手机号重置密码为 666888
  python3 scripts/manage_users.py -u 4                     # 单独解除用户 4 的登录锁定
  python3 scripts/manage_users.py --reset-all              # 批量重置所有用户密码为 123456
  python3 scripts/manage_users.py -g 4 --cid a-x1 --wear   # 给用户 4 发定制头像并顺手穿上
  python3 scripts/manage_users.py --revoke 4 --cid b-x1    # 收回用户 4 的定制卡背（穿着自动退默认）
  python3 scripts/manage_users.py --cross-flags            # 翻跨端绑定不一致记号清单
  python3 scripts/manage_users.py --clear-flags 4          # 清掉账号 4 名下记号（双向）
  python3 scripts/manage_users.py --move-mp-key 4 7        # 把账号 4 的小程序钥匙搬到账号 7
  python3 scripts/manage_users.py --local -l               # 操作本地开发库
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time

REGION = "cn-shenzhen"
INSTANCE_ID = "i-wz9864d167bjcvgk6mde"

# 远端 ECS 执行的核心 Python 逻辑
REMOTE_WORKER_SCRIPT = r"""
import sqlite3, json, sys, os
from datetime import datetime
sys.path.insert(0, '/work/mieball/backend')

from app.core import security
from app.services.cosmetics import (
    DEFAULT_AVATAR,
    DEFAULT_BACK,
    by_id,
    parse_unlocks,
)
from app.services.passwords import PWD_MIN_LEN

db_path = '/work/mieball/data/mieball.db'
if not os.path.exists(db_path):
    print(json.dumps({'error': f'未找到数据库: {db_path}'}))
    sys.exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

def parse_lock(until_str, fail_cnt):
    if not until_str:
        return False, f"正常 (错 {fail_cnt} 次)" if fail_cnt > 0 else "正常"
    try:
        until = datetime.fromisoformat(until_str)
        now = datetime.now()
        if until > now:
            mins = max(1, int((until - now).total_seconds()) // 60)
            return True, f"🔒 锁定中 (剩约 {mins} 分钟)"
    except Exception:
        pass
    return False, "正常"

def ser(r):
    fc = r['pwd_fail_count'] if 'pwd_fail_count' in r.keys() else 0
    lu = r['pwd_locked_until'] if 'pwd_locked_until' in r.keys() else None
    locked, ldesc = parse_lock(lu, fc)
    ca = r['created_at']
    if isinstance(ca, str) and '.' in ca:
        ca = ca.split('.')[0]
    return {
        'id': r['id'],
        'phone': r['phone'] or '无 (游客/注销)',
        'nickname': r['nickname'],
        'status': r['status'],
        'created_at': ca,
        'has_password': r['password_hash'] is not None,
        'is_locked': locked,
        'fail_count': fc,
        'lock_desc': ldesc
    }

action = sys.argv[1] if len(sys.argv) > 1 else 'list'
param1 = sys.argv[2] if len(sys.argv) > 2 else ''
param2 = sys.argv[3] if len(sys.argv) > 3 else '123456'
param3 = sys.argv[4] if len(sys.argv) > 4 else ''

CUR_COLS = 'id, phone, nickname, status, created_at, password_hash, pwd_fail_count, pwd_locked_until'

cur = conn.cursor()

def die(msg):
    # 动作出错单一出口：JSON 回话 + 退出码 0（外层按输出行解析，不看退出码）
    # 注意：本函数与下方分支住在 REMOTE_WORKER_SCRIPT 字符串里，不可用三引号 docstring
    print(json.dumps({'error': msg}, ensure_ascii=False))
    sys.exit(0)

def find_account(target):
    # 按 id（纯数字短串）或手机号精确找 account 行，查无返 None（reset/unlock 共用）
    if target.isdigit() and len(target) <= 6:
        cur.execute("SELECT id FROM accounts WHERE id = ?", (int(target),))
        acc = cur.fetchone()
        if acc:
            return acc
    cur.execute("SELECT id FROM accounts WHERE phone = ?", (target,))
    return cur.fetchone()

if action == 'list':
    limit = None if param1.lower() == 'all' else int(param1 if param1.isdigit() else 10)
    q = f"SELECT {CUR_COLS} FROM accounts ORDER BY id DESC"
    if limit:
        q += f" LIMIT {limit}"
    cur.execute(q)
    rows = [ser(r) for r in cur.fetchall()]
    print(json.dumps({'success': True, 'action': 'list', 'users': rows}, ensure_ascii=False))

elif action == 'search':
    kw = param1.strip()
    if kw.isdigit() and len(kw) <= 6:
        q = f"SELECT {CUR_COLS} FROM accounts WHERE id = ? OR phone LIKE ? OR nickname LIKE ? ORDER BY id DESC"
        cur.execute(q, (int(kw), f"%{kw}%", f"%{kw}%"))
    else:
        q = f"SELECT {CUR_COLS} FROM accounts WHERE phone LIKE ? OR nickname LIKE ? ORDER BY id DESC"
        cur.execute(q, (f"%{kw}%", f"%{kw}%"))
    rows = [ser(r) for r in cur.fetchall()]
    print(json.dumps({'success': True, 'action': 'search', 'users': rows, 'keyword': kw}, ensure_ascii=False))

elif action in ('reset', 'unlock'):
    # reset/unlock 共用骨架：找号 → 改写（SET 语句随动作）→ 回查 → 回话
    target = param1.strip()
    pwd = param2.strip()
    if action == 'reset' and len(pwd) < PWD_MIN_LEN:
        die(f'密码长度不能少于 {PWD_MIN_LEN} 位')
    acc = find_account(target)
    if not acc:
        die(f'未找到目标用户: {target}')
    uid = acc['id']
    if action == 'reset':
        # 只落新 hash+清计数，不撤设备钥匙——与 app 内「找回/重设」的换锁语义
        # （passwords reset_password/redeem_password：revoke_all 全钥匙作废）有意
        # 不同：运维 reset 是帮机主设新密码，不把其全部端踢下线。处置被盗号请走
        # app 内找回链
        cur.execute(
            "UPDATE accounts SET password_hash = ?, pwd_fail_count = 0, pwd_locked_until = NULL WHERE id = ?",
            (security.hash_password(pwd), uid),
        )
    else:
        cur.execute(
            "UPDATE accounts SET pwd_fail_count = 0, pwd_locked_until = NULL WHERE id = ?",
            (uid,),
        )
    conn.commit()
    cur.execute(f"SELECT {CUR_COLS} FROM accounts WHERE id = ?", (uid,))
    out = {'success': True, 'action': action, 'user': ser(cur.fetchone())}
    if action == 'reset':
        out['password'] = pwd
    print(json.dumps(out, ensure_ascii=False))

elif action == 'reset_all':
    pwd = param2.strip()
    if len(pwd) < PWD_MIN_LEN:
        die(f'密码长度不能少于 {PWD_MIN_LEN} 位')
    # 同一密码一条 UPDATE 拉齐全部在册号（逐行发同值 SQL 的整批版）
    cur.execute(
        "UPDATE accounts SET password_hash = ?, pwd_fail_count = 0, pwd_locked_until = NULL WHERE status = 'active'",
        (security.hash_password(pwd),),
    )
    conn.commit()
    cur.execute(f"SELECT {CUR_COLS} FROM accounts WHERE status = 'active' ORDER BY id DESC")
    rows = [ser(r) for r in cur.fetchall()]
    print(json.dumps({'success': True, 'action': 'reset_all', 'users': rows, 'password': pwd, 'count': len(rows)}, ensure_ascii=False))

elif action in ('grant', 'revoke'):
    # 发卡/收卡：编号校验单一源在后端装扮册子（by_id/tier/默认款都从册子取，
    # 不在本脚本抄第二份清单——加款改档只改册子一处，运维口自动跟随）
    target = param1.strip()
    cid = param2.strip()
    wear = param3.strip() == 'wear'
    acc = find_account(target)
    if not acc:
        die(f'未找到目标用户: {target}')
    item = by_id(cid)
    if item is None:
        die(f'编号不存在: {cid}')
    if item.tier != 'custom':
        # 荣誉款进出只走达标核算（收了会被核算复活、发了等于绕过达标后门），公共款人人可用无需发
        if item.tier == 'honor':
            die(f'只支持定制款: {cid} 是荣誉款，荣誉款进出只走达标核算')
        die(f'只支持定制款: {cid} 是公共款，公共款人人可用无需发放')
    uid = acc['id']
    cur.execute("SELECT unlocks, dress_avatar, dress_back FROM accounts WHERE id = ?", (uid,))
    row = cur.fetchone()
    rows = parse_unlocks(row['unlocks'])
    owned = [r['id'] for r in rows]

    if action == 'grant':
        # 幂等：已有该款不再追加（「新」标保持首次发放那一行原样）
        already = cid in owned
        if not already:
            rows.append({'id': cid, 'new': True})
            cur.execute(
                "UPDATE accounts SET unlocks = ? WHERE id = ?",
                (json.dumps(rows, ensure_ascii=False), uid),
            )
        worn = False
        if wear:
            # 穿哪列看册子 kind（avatar/back 前缀的语义真值在册子，不在此另判一遍）
            col = 'dress_avatar' if item.kind == 'avatar' else 'dress_back'
            cur.execute(f"UPDATE accounts SET {col} = ? WHERE id = ?", (cid, uid))
            worn = True
        conn.commit()
        out = {'success': True, 'action': 'grant', 'cid': cid, 'already': already, 'worn': worn}
    else:
        had = cid in owned
        if had:
            rows = [r for r in rows if r['id'] != cid]
            cur.execute(
                "UPDATE accounts SET unlocks = ? WHERE id = ?",
                (json.dumps(rows, ensure_ascii=False), uid),
            )
        # 正穿着该件才退默认，头像退头像的、卡背退卡背的（互不影响）；默认款取册子
        # 常量。安静收回：纯库操作无通知，对方下次进装扮页自然见不到
        undressed = False
        if item.kind == 'avatar' and row['dress_avatar'] == cid:
            cur.execute("UPDATE accounts SET dress_avatar = ? WHERE id = ?", (DEFAULT_AVATAR, uid))
            undressed = True
        if item.kind == 'back' and row['dress_back'] == cid:
            cur.execute("UPDATE accounts SET dress_back = ? WHERE id = ?", (DEFAULT_BACK, uid))
            undressed = True
        conn.commit()
        out = {'success': True, 'action': 'revoke', 'cid': cid, 'had': had, 'undressed': undressed}

    cur.execute("SELECT id, phone, nickname, dress_avatar, dress_back, unlocks FROM accounts WHERE id = ?", (uid,))
    r = cur.fetchone()
    final = [x['id'] for x in parse_unlocks(r['unlocks'])]
    out['user'] = {
        'id': r['id'],
        'phone': r['phone'] or '无',
        'nickname': r['nickname'],
        'dress_avatar': r['dress_avatar'],
        'dress_back': r['dress_back'],
        'unlocks': final,
    }
    print(json.dumps(out, ensure_ascii=False))

elif action == 'cross_flags':
    # 跨端绑定不一致记号清单：只翻不写，一行=一个号视角指向对方（一对冲突两行）
    cur.execute(
        "SELECT f.id, f.account_id, f.other_account_id, f.found_at, "
        "a.nickname AS nickname, b.nickname AS other_nickname "
        "FROM wechat_cross_flags f "
        "JOIN accounts a ON a.id = f.account_id "
        "JOIN accounts b ON b.id = f.other_account_id "
        "ORDER BY f.id"
    )
    rows = [{
        'id': r['id'],
        'account_id': r['account_id'],
        'nickname': r['nickname'],
        'other_account_id': r['other_account_id'],
        'other_nickname': r['other_nickname'],
        'found_at': r['found_at'],
    } for r in cur.fetchall()]
    print(json.dumps({'success': True, 'action': 'cross_flags', 'flags': rows}, ensure_ascii=False))

elif action == 'clear_flags':
    # 双向清：该号不管站在记号哪一侧（account_id 或 other_account_id）都算它的记号
    acc = find_account(param1.strip())
    if not acc:
        die(f'未找到目标用户: {param1.strip()}')
    uid = acc['id']
    cur.execute(
        "DELETE FROM wechat_cross_flags WHERE account_id = ? OR other_account_id = ?",
        (uid, uid),
    )
    n = cur.rowcount
    conn.commit()
    print(json.dumps({'success': True, 'action': 'clear_flags', 'account_id': uid, 'cleared': n}, ensure_ascii=False))

elif action == 'move_mp_key':
    # 人工把两个账号绑成一起的落手处：小程序钥匙三列整体搬家（to 原值被覆盖）、
    # 两号记号全清——只搬微信钥匙不搬任何业务数据，与「不自动并号不搬数据」同口径
    src = find_account(param1.strip())
    dst = find_account(param2.strip())
    if not src:
        die(f'未找到来源账号: {param1.strip()}')
    if not dst:
        die(f'未找到目标账号: {param2.strip()}')
    fid, tid = src['id'], dst['id']
    if fid == tid:
        die('来源与目标不能是同一个账号')
    cur.execute(
        "SELECT wechat_mp_openid, wechat_mp_bound_at, wechat_unionid FROM accounts WHERE id = ?",
        (fid,),
    )
    r = cur.fetchone()
    if not r or not r['wechat_mp_openid']:
        die(f'账号 {fid} 名下没有小程序钥匙可搬')
    cur.execute(
        "UPDATE accounts SET wechat_mp_openid = ?, wechat_mp_bound_at = ?, wechat_unionid = ? WHERE id = ?",
        (r['wechat_mp_openid'], r['wechat_mp_bound_at'], r['wechat_unionid'], tid),
    )
    cur.execute(
        "UPDATE accounts SET wechat_mp_openid = NULL, wechat_mp_bound_at = NULL, wechat_unionid = NULL WHERE id = ?",
        (fid,),
    )
    cur.execute(
        "DELETE FROM wechat_cross_flags WHERE account_id IN (?, ?) OR other_account_id IN (?, ?)",
        (fid, tid, fid, tid),
    )
    n = cur.rowcount
    conn.commit()
    print(json.dumps({
        'success': True,
        'action': 'move_mp_key',
        'from_id': fid,
        'to_id': tid,
        'openid': r['wechat_mp_openid'],
        'unionid': r['wechat_unionid'],
        'flags_cleared': n,
    }, ensure_ascii=False))

conn.close()
"""


def parse_json_tail(text: str, err_label: str) -> dict:
    """从输出尾部找 JSON 行（worker 的真结果恒在末尾；前面可能是 [config] 警告）"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue  # 噪音行也可能是 {...} 形，解析失败跳过找真结果行
    return {"error": f"未能解析{err_label}: {text}"}


def run_local(
    action: str, param1: str = "", param2: str = "", param3: str = ""
) -> dict:
    """在本地环境（Mac 开发机或 ECS 本机）直接执行。库址可被 MIEBALL_MANAGE_DB
    环境变量改指（测试与临时操作别库用，不碰默认库）；后端代码目录按脚本自身
    所在位置定位，不写死开发机绝对路径。"""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_db = os.environ.get("MIEBALL_MANAGE_DB") or (
        # ECS 本机运维把库放数据目录；开发机库在 backend 内
        "/work/mieball/data/mieball.db"
        if os.path.exists("/work/mieball/data/mieball.db")
        else os.path.join(backend_dir, "mieball.db")
    )

    local_script = REMOTE_WORKER_SCRIPT.replace(
        "/work/mieball/backend", backend_dir
    ).replace("/work/mieball/data/mieball.db", local_db)

    cmd = [
        sys.executable,
        "-c",
        local_script,
        action,
        param1,
        param2,
        param3,
    ]
    # 路径已由 local_script 里的 sys.path.insert 改写覆盖，不再另设 PYTHONPATH
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        return {"error": f"本地执行出错: {res.stderr}"}

    return parse_json_tail(res.stdout, "执行输出")


def run_ecs(action: str, param1: str = "", param2: str = "", param3: str = "") -> dict:
    """通过阿里云云助手在 ECS 执行"""
    b64_worker = base64.b64encode(REMOTE_WORKER_SCRIPT.encode("utf-8")).decode("utf-8")

    # 对参数做转义或 base64 处理
    b64_p1 = base64.b64encode(param1.encode("utf-8")).decode("utf-8")
    b64_p2 = base64.b64encode(param2.encode("utf-8")).decode("utf-8")
    b64_p3 = base64.b64encode(param3.encode("utf-8")).decode("utf-8")

    remote_shell = f"""#!/bin/bash
export LC_ALL=C
PARAM1=$(echo "{b64_p1}" | base64 -d)
PARAM2=$(echo "{b64_p2}" | base64 -d)
PARAM3=$(echo "{b64_p3}" | base64 -d)
echo "{b64_worker}" | base64 -d > /tmp/mieball_user_worker.py
cd /work/mieball/backend && .venv/bin/python3 /tmp/mieball_user_worker.py "{action}" "$PARAM1" "$PARAM2" "$PARAM3"
rm -f /tmp/mieball_user_worker.py
"""

    res = subprocess.run(
        [
            "aliyun",
            "ecs",
            "RunCommand",
            "--RegionId",
            REGION,
            "--InstanceId.1",
            INSTANCE_ID,
            "--Type",
            "RunShellScript",
            "--CommandContent",
            remote_shell,
            "--cli-query",
            "InvokeId",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if res.returncode != 0:
        return {"error": f"云助手指令下发失败: {res.stderr}"}

    invoke_id = res.stdout.strip().strip('"')

    for _ in range(15):
        time.sleep(1.5)
        res = subprocess.run(
            [
                "aliyun",
                "ecs",
                "DescribeInvocationResults",
                "--RegionId",
                REGION,
                "--InvokeId",
                invoke_id,
                "--ContentEncoding",
                "PlainText",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            data = json.loads(res.stdout)
            item = data["Invocation"]["InvocationResults"]["InvocationResult"][0]
            status = item["InvocationStatus"]
            if status in ["Success", "Failed"]:
                output = item.get("Output", "")
                if status == "Failed":
                    return {"error": f"远程脚本执行报错: {output}"}
                return parse_json_tail(output, "远程输出")
        except (json.JSONDecodeError, KeyError, IndexError):
            continue  # 结果未就绪/输出尚未成形，下一轮再取

    return {"error": "云助手指令执行超时，请重试。"}


def print_table(users: list[dict], title: str, env_name: str) -> None:
    if not users:
        print(f"\n📭 [{env_name}] 没有找到匹配的用户记录。\n")
        return

    print(f"\n📋 [{env_name}] {title}（共 {len(users)} 位）：")
    header = f"{'ID':<6} {'手机号':<13} {'昵称':<12} {'状态':<8} {'注册时间':<20} {'密码':<8} {'安全状态'}"
    print("-" * 80)
    print(header)
    print("-" * 80)

    for u in users:
        pwd_mark = "✅ 已设" if u.get("has_password") else "❌ 未设"
        status_mark = "正常" if u.get("status") == "active" else "已注销"
        print(
            f"#{u['id']:<5} {u['phone']:<13} {u['nickname']:<12} {status_mark:<8} {u['created_at']:<20} {pwd_mark:<8} {u['lock_desc']}"
        )
    print("-" * 80 + "\n")


def print_help_footer(env_flag: str) -> None:
    print("💡 快捷操作指引：")
    print(
        f"  • 重置密码为 123456： python3 scripts/manage_users.py {env_flag}-r <用户ID或手机号>"
    )
    print(
        f"  • 自定义新密码：      python3 scripts/manage_users.py {env_flag}-r <用户ID或手机号> -p <新密码>"
    )
    print(
        f"  • 搜索用户：          python3 scripts/manage_users.py {env_flag}-s <手机号或昵称>"
    )
    print(
        f"  • 单独解除锁定：      python3 scripts/manage_users.py {env_flag}-u <用户ID或手机号>"
    )
    print(
        f"  • 发定制款装扮：      python3 scripts/manage_users.py {env_flag}-g <用户ID或手机号> --cid a-x1 [--wear]"
    )
    print(
        f"  • 收定制款装扮：      python3 scripts/manage_users.py {env_flag}--revoke <用户ID或手机号> --cid b-x1"
    )
    print(
        f"  • 批量重置所有用户：  python3 scripts/manage_users.py {env_flag}--reset-all"
    )
    print(
        f"  • 跨端绑定记号：      python3 scripts/manage_users.py {env_flag}--cross-flags / --clear-flags <ID> / --move-mp-key <FROM> <TO>\n"
    )


def fail(res: dict, verb: str) -> None:
    """动作回话的失败出口单一源（九路动作共用）：有错报错并退出，无错原样放行。
    出口必须放行成功回话——动作分支紧随其后读 res['user'] 等成功字段。"""
    if "error" not in res:
        return
    print(f"❌ {verb}失败: {res['error']}\n")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mieball 用户检索与密码运维工具")
    parser.add_argument(
        "-l",
        "--list",
        nargs="?",
        const="10",
        default=None,
        metavar="N",
        help="列出最新注册的 N 个用户 (默认 10，支持 all)",
    )
    parser.add_argument(
        "-s",
        "--search",
        metavar="KEYWORD",
        help="按手机号/昵称模糊搜索或按 ID 精确查询",
    )
    parser.add_argument(
        "-r", "--reset", metavar="USER", help="重置指定用户的密码 (输入 ID 或手机号)"
    )
    parser.add_argument(
        "-p",
        "--password",
        default="123456",
        help="设置的新密码 (默认 123456，最少 6 位)",
    )
    parser.add_argument(
        "-u", "--unlock", metavar="USER", help="解除指定用户的登录锁定 (清零连错计数)"
    )
    parser.add_argument(
        "-g",
        "--grant",
        metavar="USER",
        help="发定制款装扮到解锁清单 (输入 ID 或手机号，需配 --cid)",
    )
    parser.add_argument(
        "--revoke",
        metavar="USER",
        help="从解锁清单收回定制款装扮 (输入 ID 或手机号，需配 --cid)",
    )
    parser.add_argument(
        "--cid",
        metavar="CID",
        help="装扮编号 (grant/revoke 必填，只收定制款如 a-x1/b-x1)",
    )
    parser.add_argument(
        "--wear",
        action="store_true",
        help="grant 时顺手帮穿上 (效果即刻全站可见)",
    )
    parser.add_argument(
        "--reset-all", action="store_true", help="一键重置所有在册用户的密码为指定密码"
    )
    parser.add_argument(
        "--cross-flags",
        action="store_true",
        help="列出全部「跨端绑定不一致」记号 (两端微信钥匙对不上号的账号清单)",
    )
    parser.add_argument(
        "--clear-flags",
        metavar="USER",
        help="清掉指定账号名下的跨端绑定记号 (双向，输入 ID 或手机号)",
    )
    parser.add_argument(
        "--move-mp-key",
        nargs=2,
        metavar=("FROM", "TO"),
        help="把 FROM 账号的小程序钥匙搬到 TO 账号并清两号记号 (人工绑定归一)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="切换至本地开发环境数据库 (默认操作 ECS 生产库)",
    )

    args = parser.parse_args()

    env_name = "本地开发环境" if args.local else "阿里云 ECS 生产环境"
    env_flag = "--local " if args.local else ""
    runner = run_local if args.local else run_ecs

    # 1. 重置单个用户密码
    if args.reset:
        print(f"🔄 正在向 [{env_name}] 下发密码重置请求...")
        res = runner("reset", args.reset, args.password)
        fail(res, "重置")
        u = res["user"]
        print("\n🎉 密码重置成功！")
        print(
            f"👉 用户 #{u['id']} ({u['nickname']} · {u['phone']}) 密码已设置为: {res['password']} (锁定已解除)"
        )
        print("🔐 密码登录接口已就绪: POST /api/auth/password/login\n")
        return

    # 2. 单独解除锁定
    if args.unlock:
        print(f"🔄 正在向 [{env_name}] 下发解锁请求...")
        res = runner("unlock", args.unlock)
        fail(res, "解锁")
        u = res["user"]
        print(
            f"\n🔓 用户 #{u['id']} ({u['nickname']} · {u['phone']}) 锁定已解除，连续输错计数已清零。\n"
        )
        return

    # 3. 发卡 / 收卡（仅定制款；荣誉款进出只走达标核算）
    if args.grant or args.revoke:
        action = "grant" if args.grant else "revoke"
        target = args.grant or args.revoke
        verb = "发卡" if action == "grant" else "收卡"
        if not args.cid:
            print(f"❌ {verb}需要 --cid 指定装扮编号 (如 a-x1)\n")
            sys.exit(1)
        print(f"🔄 正在向 [{env_name}] 下发{verb}请求...")
        res = runner(action, target, args.cid, "wear" if args.wear else "")
        fail(res, verb)
        u = res["user"]
        print(f"\n🎉 {verb}成功！用户 #{u['id']} ({u['nickname']} · {u['phone']})")
        if action == "grant":
            if res.get("already"):
                print(f"ℹ️ {res['cid']} 已在其解锁清单，未重复发放")
            else:
                print(f"👉 已发放定制款 {res['cid']}，对方下次打开装扮页即见")
            if res.get("worn"):
                print(f"👕 已顺手穿上 {res['cid']}，效果即刻全站可见")
        else:
            if res.get("had"):
                print(f"👉 已从解锁清单收回 {res['cid']}")
            else:
                print(f"ℹ️ 其清单里本就没有 {res['cid']}，未动清单")
            if res.get("undressed"):
                print("👕 其正穿着该件，已自动退回默认公共款 (头像、卡背各退各的)")
            print("🤫 安静收回：不另发通知，对方下次进装扮页自然见不到")
        print(f"🎁 当前解锁清单: {'、'.join(u['unlocks']) or '（空）'}")
        print(
            f"👕 当前穿戴: 头像={u['dress_avatar'] or '默认'} · 卡背={u['dress_back'] or '默认'}\n"
        )
        return

    # 4. 批量重置所有用户密码
    if args.reset_all:
        print(f"🔄 正在向 [{env_name}] 下发全量用户密码重置请求...")
        res = runner("reset_all", "", args.password)
        fail(res, "批量重置")
        users = res.get("users", [])
        print(
            f"\n🎉 批量重置成功！共 {len(users)} 位在册用户密码已设置为: {res['password']}"
        )
        print_table(users, "重置后的在册用户", env_name)
        return

    # 5. 跨端绑定不一致记号三动作（群主人工处理口：翻清单 → 搬钥匙或清记号）
    if args.cross_flags:
        print(f"📋 正在向 [{env_name}] 翻查跨端绑定不一致记号...")
        res = runner("cross_flags")
        fail(res, "翻查")
        flags = res.get("flags", [])
        if not flags:
            print("\n✅ 当前没有跨端绑定不一致的记号。\n")
            return
        print(f"\n📋 [{env_name}] 跨端绑定不一致记号（共 {len(flags)} 条）：")
        print("-" * 72)
        for f in flags:
            print(
                f"#{f['id']} 账号 #{f['account_id']} ({f['nickname']}) ↔ #{f['other_account_id']} ({f['other_nickname']}) · 发现于 {f['found_at']}"
            )
        print("-" * 72)
        print(
            "💡 联系本人确认后：--move-mp-key 搬钥匙到该去的号，或 --clear-flags 清记号\n"
        )
        return

    if args.clear_flags:
        print(f"🔄 正在向 [{env_name}] 下发清记号请求...")
        res = runner("clear_flags", args.clear_flags)
        fail(res, "清记号")
        print(f"\n🎉 已清掉账号 #{res['account_id']} 名下记号 {res['cleared']} 条。\n")
        return

    if args.move_mp_key:
        frm, to = args.move_mp_key
        print(f"🔄 正在向 [{env_name}] 搬小程序钥匙: {frm} → {to} ...")
        res = runner("move_mp_key", frm, to)
        fail(res, "搬钥匙")
        print(
            f"\n🎉 搬钥匙成功！账号 #{res['from_id']} 的小程序钥匙已归到 #{res['to_id']}"
        )
        print(f"👉 openid={res['openid']} · unionid={res['unionid'] or '无'}")
        print(
            f"🧹 两号记号已清 {res['flags_cleared']} 条；两号其余数据各归各、互不搬迁\n"
        )
        return

    # 6. 搜索用户
    if args.search:
        print(f"🔍 正在检索 [{env_name}] 用户 (关键字: {args.search})...")
        res = runner("search", args.search)
        fail(res, "检索")
        users = res.get("users", [])
        print_table(users, f"关键字 [{args.search}] 搜索结果", env_name)
        print_help_footer(env_flag)
        return

    # 7. 默认或 --list
    limit_str = "10"
    if args.list is not None:
        limit_str = str(args.list)

    print(f"🔍 正在连接 [{env_name}] 获取用户信息...")
    res = runner("list", limit_str)
    fail(res, "获取")

    users = res.get("users", [])
    title = (
        "所有在册用户"
        if limit_str.lower() == "all"
        else f"最新注册的 {len(users)} 位用户"
    )
    print_table(users, title, env_name)
    print_help_footer(env_flag)


if __name__ == "__main__":
    main()
