"""mieball 后端骨架 —— 仅基建（健康检查/服务信息/CORS）。

业务 API（账号 1.1、球局等）按 docs/ 下对应规格走 newfun→mawang 流程另行实现，
不要在本文件里堆业务路由；到规模后按路由拆 app/ 下的子模块。
约定端口 16588（启动脚本传入 --port，此处不再绑定）。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="mieball API", version="0.1.0")

# 开发期全放开：前端 12543 与手机真机（微信内 H5 走局域网 IP）都要能直连
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "service": "mieball-backend",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
