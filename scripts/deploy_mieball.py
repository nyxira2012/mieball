#!/usr/bin/env python3
"""mieball 一键自动化部署至阿里云 ECS 工具 (支持前端/后端/素材/全量)"""
import os
import sys
import math
import time
import base64
import subprocess
import json
import hashlib

REGION = "cn-shenzhen"
INSTANCE_ID = "i-wz9864d167bjcvgk6mde"
CHUNK_SIZE = 24000
# 脚本随仓库走，默认取仓库根（scripts/ 的上一级）；MIEBALL_ROOT 环境变量可覆盖
MIEBALL_ROOT = os.environ.get(
    "MIEBALL_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

def run_remote_script(script):
    res = subprocess.run([
        "aliyun", "ecs", "RunCommand",
        "--RegionId", REGION,
        "--InstanceId.1", INSTANCE_ID,
        "--Type", "RunShellScript",
        "--CommandContent", script,
        "--cli-query", "InvokeId"
    ], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"RunCommand failed: {res.stderr}")
    invoke_id = res.stdout.strip().strip('"')
    
    for _ in range(30):
        time.sleep(2)
        res = subprocess.run([
            "aliyun", "ecs", "DescribeInvocationResults",
            "--RegionId", REGION,
            "--InvokeId", invoke_id,
            "--ContentEncoding", "PlainText"
        ], capture_output=True, text=True)
        data = json.loads(res.stdout)
        item = data["Invocation"]["InvocationResults"]["InvocationResult"][0]
        status = item["InvocationStatus"]
        if status in ["Success", "Failed"]:
            if status == "Failed":
                raise RuntimeError(f"Remote script failed: {item.get('Output')}")
            return item.get("Output", "")
    raise TimeoutError("Remote script execution timed out")

def upload_and_extract(local_file, remote_dir):
    with open(local_file, "rb") as f:
        data = f.read()
    total_len = len(data)
    total_chunks = math.ceil(total_len / CHUNK_SIZE)
    print(f"   [上传中] 大小 {total_len / 1024:.1f} KB，分 {total_chunks} 包传输...")
    
    run_remote_script("rm -rf /tmp/mieball_upload && mkdir -p /tmp/mieball_upload")
    
    for i in range(total_chunks):
        chunk = data[i * CHUNK_SIZE : (i + 1) * CHUNK_SIZE]
        b64_chunk = base64.b64encode(chunk).decode("utf-8")
        chunk_name = f"chunk_{i:04d}.bin"
        
        subprocess.run([
            "aliyun", "ecs", "SendFile",
            "--RegionId", REGION,
            "--InstanceId.1", INSTANCE_ID,
            "--Name", chunk_name,
            "--TargetDir", "/tmp/mieball_upload",
            "--ContentType", "Base64",
            "--Content", b64_chunk,
            "--Overwrite", "true"
        ], capture_output=True, text=True, check=True)
        time.sleep(0.3)

    assemble_script = f"""#!/bin/bash
set -e
cat /tmp/mieball_upload/chunk_*.bin > /tmp/mieball_upload/archive.tar.gz
mkdir -p {remote_dir}
tar -xzf /tmp/mieball_upload/archive.tar.gz -C {remote_dir}
rm -rf /tmp/mieball_upload
echo "EXTRACT_OK"
"""
    run_remote_script(assemble_script)

def deploy_frontend():
    print(f"🔨 [1/2] 正在构建前端 H5 静态资源 ({MIEBALL_ROOT}/frontend)...")
    res = subprocess.run(["npm", "run", "build:h5"], cwd=os.path.join(MIEBALL_ROOT, "frontend"), capture_output=True, text=True)
    if res.returncode != 0:
        print("❌ 前端打包失败:\n", res.stderr)
        sys.exit(1)
    
    tar_path = "/tmp/mieball_fe_dist.tar.gz"
    h5_dir = os.path.join(MIEBALL_ROOT, "frontend", "dist", "build", "h5")
    env = os.environ.copy()
    env["COPYFILE_DISABLE"] = "1"
    subprocess.run(["tar", "-czf", tar_path, "-C", h5_dir, "."], env=env, check=True)
    
    print("🚀 [2/2] 正在同步前端至 ECS /work/mieball/frontend/ ...")
    upload_and_extract(tar_path, "/work/mieball/frontend")
    if os.path.exists(tar_path):
        os.remove(tar_path)
    print("✨ 前端静态产物发布成功！浏览器刷新即生效。")

def deploy_backend():
    print(f"📦 [1/2] 正在打包后端核心源码 ({MIEBALL_ROOT}/backend/app)...")
    tar_path = "/tmp/mieball_be_dist.tar.gz"
    backend_dir = os.path.join(MIEBALL_ROOT, "backend")
    env = os.environ.copy()
    env["COPYFILE_DISABLE"] = "1"
    items = ["app", "requirements.txt"]
    if os.path.exists(os.path.join(backend_dir, "scripts")):
        items.append("scripts")
    subprocess.run(["tar", "-czf", tar_path, "-C", backend_dir, *items], env=env, check=True)
    
    print("🚀 [2/2] 正在同步后端至 ECS 并热重启服务...")
    upload_and_extract(tar_path, "/work/mieball/backend")
    if os.path.exists(tar_path):
        os.remove(tar_path)
    
    # 重启 systemd 服务
    run_remote_script("systemctl restart mieball")
    print("✨ 后端服务已成功更新并热重启！")


# 素材与 H5 同住 /work/mieball/frontend 一棵树：fe 通道产物不含素材、且 tar 解压
# 从不清目录——两通道互不踩，素材也不必赶在 fe 之前发（无顺序约束）。
# nginx /cosmetics/ 走 immutable 永久缓存（配置在 aliyun-ocs 仓库），同名换图
# 的换新全靠前端 ASSET_REV 版本号，这里检测到同名有变时负责提醒。
COSMETICS_LOCAL_DIR = os.path.join(MIEBALL_ROOT, "cosmetics")
COSMETICS_REMOTE_DIR = "/work/mieball/frontend/cosmetics"


def _md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def deploy_cosmetics():
    local = {}
    for name in sorted(os.listdir(COSMETICS_LOCAL_DIR)):
        p = os.path.join(COSMETICS_LOCAL_DIR, name)
        # 跳过 .DS_Store 之类系统隐藏文件（git 忽略它们，别当素材传上服务器）
        if name.startswith(".") or not os.path.isfile(p):
            continue
        local[name] = _md5_of(p)
    if not local:
        print("❌ 本地素材目录为空，先跑生图/落位工具再发素材通道")
        sys.exit(1)

    # 远端逐件 md5 对账：只传新增+有变（上新几件就传几件），零变更直接收工
    out = run_remote_script(
        f"cd {COSMETICS_REMOTE_DIR} 2>/dev/null && md5sum * 2>/dev/null || true"
    )
    remote = {}
    for line in (out or "").splitlines():
        parts = line.split()
        if len(parts) == 2:
            remote[os.path.basename(parts[1])] = parts[0]

    fresh = [n for n in local if n not in remote]
    changed = [n for n in local if n in remote and remote[n] != local[n]]
    gone = [n for n in remote if n not in local]
    print(f"👕 [1/2] 素材对账：新增 {len(fresh)} 件 · 同名有变 {len(changed)} 件 · 远端独有 {len(gone)} 件")
    if gone:
        print(f"   （远端独有只报不删：{', '.join(gone)}）")
    if not fresh and not changed:
        print("✨ 远端已同步，无需上传。")
        return

    names = sorted(fresh + changed)
    tar_path = "/tmp/mieball_cosmetics.tar.gz"
    env = os.environ.copy()
    env["COPYFILE_DISABLE"] = "1"
    subprocess.run(
        ["tar", "-czf", tar_path, "-C", MIEBALL_ROOT, *[f"cosmetics/{n}" for n in names]],
        env=env,
        check=True,
    )
    print(f"🚀 [2/2] 上传 {len(names)} 件素材至 ECS {COSMETICS_REMOTE_DIR}/ ...")
    upload_and_extract(tar_path, "/work/mieball/frontend")
    if os.path.exists(tar_path):
        os.remove(tar_path)
    if changed:
        print(f"⚠️  同名替换 {len(changed)} 件：{', '.join(changed)}")
        print("   /cosmetics/ 是永久缓存——同名换图必须把 frontend/src/utils/cardbg.ts")
        print("   的 ASSET_REV +1 并走 fe 通道，否则老访客缓存不换新；纯上新新编号不受影响。")
    print("✨ 素材发布成功！")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target in ["fe", "frontend"]:
        deploy_frontend()
    elif target in ["be", "backend"]:
        deploy_backend()
    elif target in ["cosmetics", "assets"]:
        deploy_cosmetics()
    elif target in ["all"]:
        deploy_frontend()
        deploy_backend()
        deploy_cosmetics()
    else:
        print("用法: python3 scripts/deploy_mieball.py [fe|be|cosmetics|all]")
        sys.exit(1)
    print("\n🎉 访问地址: https://2win.s2g2b2c.com")
