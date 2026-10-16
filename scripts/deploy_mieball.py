#!/usr/bin/env python3
"""mieball 一键自动化部署至阿里云 ECS 工具 (支持前端/后端/全量)"""
import os
import sys
import math
import time
import base64
import subprocess
import json

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

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target in ["fe", "frontend"]:
        deploy_frontend()
    elif target in ["be", "backend"]:
        deploy_backend()
    elif target in ["all"]:
        deploy_frontend()
        deploy_backend()
    else:
        print("用法: python3 scripts/deploy_mieball.py [fe|be|all]")
        sys.exit(1)
    print("\n🎉 访问地址: https://2win.s2g2b2c.com")
