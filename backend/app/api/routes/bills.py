"""bills 路由 —— 账单域（docs/1.3）的 HTTP 面，前缀 /api/bills。

域职责：账单页全视图（GET /api/bills，批4 读链入住）与两向记账动作
（POST /api/bills/{game_id}/settle・receive，批5 写链入住）。出账的写入口不在这里
——散场出账挂在 live 的 end() commit 内、补填总价走 games 路由的 fee 端点；
本文件先立骨架占位（前缀与域归属定死，逐批入住不再动注册）。

响应约定同 auth/games：成功体直接是业务字段；失败体 {"error": {code, message}}。
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/bills", tags=["bills"])
