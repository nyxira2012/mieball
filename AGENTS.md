# AGENTS.md — mieball 项目指引

> 开工前先读 `docs/项目地图.md` 对齐；新增模块 / 文档 / 决策后跑 naofu 补足登记。
要求，与用户商议功能设计时，少说代码多说方法，说人话。

- 端口：前端 12543 · 后端 16588

## 常用命令

```bash
./start.sh        # 前后端一起启动
./start.sh fe     # 仅前端
./start.sh be     # 仅后端
cd frontend && npm run test         # vitest
cd frontend && npm run type-check   # vue-tsc
```

## 文档

- `docs/0号文档.md` — 产品总纲（一句话、核心循环、术语表；术语以它为准，如"球局/组织者/轮转/积分"）
- `docs/1.1.账号与登录-后端.md` — 后端第一份业务规格（账号体系，已评审）
- `docs/1.5.灵活首页-后端.md` — 角色化动态首页规格
- `docs/2.1 ~ 5.1.*-前端.md` — 各页面前端规格
- temp/原型图存放处