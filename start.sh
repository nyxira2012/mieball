#!/usr/bin/env bash
# mieball 唯一启动脚本 —— 前端 12543 · 后端 16588
# 用法：
#   ./start.sh        前后端一起启动（Ctrl-C 全部退出）
#   ./start.sh fe     只启前端
#   ./start.sh be     只启后端
# 首次运行自动装依赖（frontend: npm install；backend: .venv + pip install）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-all}"

# ---------- 后端（FastAPI · 16588） ----------
start_backend() {
  cd "$ROOT/backend"
  if [ ! -d .venv ]; then
    echo "[backend] 创建虚拟环境 backend/.venv ..."
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  if ! python -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    echo "[backend] 安装依赖 ..."
    pip install --quiet -r requirements.txt
  fi
  echo "[backend] http://127.0.0.1:16588 （API 文档 /docs）"
  exec uvicorn app.main:app --host 0.0.0.0 --port 16588 --reload
}

# ---------- 前端（uni-app H5 · 12543，端口/代理配置见 frontend/vite.config.ts） ----------
start_frontend() {
  cd "$ROOT/frontend"
  if [ ! -d node_modules ]; then
    echo "[frontend] 安装依赖（node_modules 不存在）..."
    npm install
  fi
  echo "[frontend] http://localhost:12543"
  exec npm run dev:h5
}

case "$MODE" in
  be) start_backend ;;
  fe) start_frontend ;;
  all)
    pids=()
    cleanup() {
      trap - EXIT INT TERM
      [ ${#pids[@]} -gt 0 ] && kill "${pids[@]}" 2>/dev/null || true
    }
    trap cleanup EXIT INT TERM

    ( start_backend ) & pids+=($!)
    ( start_frontend ) & pids+=($!)

    # 就绪探测：只提示不强等（首次装依赖可能超过 60 秒）
    for port in 16588 12543; do
      ok=""
      for _ in $(seq 1 60); do
        if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$port"; then ok=1; break; fi
        sleep 1
      done
      if [ -n "$ok" ]; then echo "[start] 端口 $port 已就绪"; else echo "[start] 端口 $port 暂未响应（可能仍在装依赖，稍后直接访问即可）"; fi
    done

    echo "[start] 前端 http://localhost:12543 · 后端 http://127.0.0.1:16588 （Ctrl-C 全部退出）"
    wait
    ;;
  *)
    echo "用法: ./start.sh [fe|be]（无参数 = 前后端一起启动）"
    exit 1
    ;;
esac
