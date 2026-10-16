#!/usr/bin/env python3
"""远程查询 ECS 上 Mieball 运行日志与审计事件的小工具"""
import argparse
import json
import subprocess
import time

REGION = "cn-shenzhen"
INSTANCE_ID = "i-wz9864d167bjcvgk6mde"

def main():
    parser = argparse.ArgumentParser(description="一键远程查询阿里云 ECS 上 Mieball 的日志")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--err", metavar="ERR-XXXXXX", help="按错误编号查询案发现场堆栈")
    group.add_argument("--game", type=int, metavar="N", help="按球局编号拉取审计事件流")
    parser.add_argument("--days", type=int, default=14, help="查询近几天（默认 14 天）")
    args = parser.parse_args()

    if args.err:
        query_arg = f"--err {args.err}"
    else:
        query_arg = f"--game {args.game}"

    cmd = (
        f"cd /work/mieball/backend && "
        f".venv/bin/python scripts/query_log.py {query_arg} --days {args.days} --dir /work/mieball/logs"
    )

    print(f"🔍 正在连接阿里云 ECS (深圳) 检索日志...")
    res = subprocess.run([
        "aliyun", "ecs", "RunCommand",
        "--RegionId", REGION,
        "--InstanceId.1", INSTANCE_ID,
        "--Type", "RunShellScript",
        "--CommandContent", cmd,
        "--cli-query", "InvokeId"
    ], capture_output=True, text=True)

    if res.returncode != 0:
        print("❌ 云助手指令下发失败:\n", res.stderr)
        return

    invoke_id = res.stdout.strip().strip('"')

    for _ in range(15):
        time.sleep(2)
        res = subprocess.run([
            "aliyun", "ecs", "DescribeInvocationResults",
            "--RegionId", REGION,
            "--InvokeId", invoke_id,
            "--ContentEncoding", "PlainText"
        ], capture_output=True, text=True)
        try:
            data = json.loads(res.stdout)
            item = data["Invocation"]["InvocationResults"]["InvocationResult"][0]
            status = item["InvocationStatus"]
            if status in ["Success", "Failed"]:
                output = item.get("Output", "")
                print(output.strip())
                return
        except Exception:
            pass

    print("⚠️ 查询超时，请稍后重试。")

if __name__ == "__main__":
    main()
