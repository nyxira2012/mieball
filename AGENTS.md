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

## 质量工具（已全局装在本机，直接命令可用）

- prettier / eslint — 前端格式化、规范检查（`prettier --write <文件>` · `eslint <文件>`）
- ruff — 后端格式化+规范检查一体（`ruff format .` · `ruff check .`）
- 注意：是机器级安装，项目内暂无规则配置与 npm script；换机器需重装（npm i -g / brew install ruff）

## 文档

- `docs/0号文档.md` — 产品总纲（一句话、核心循环、术语表；术语以它为准，如"球局/组织者/轮转/积分"）
- `docs/1.1.账号与登录-后端.md` — 后端第一份业务规格（账号体系，已评审）
- `docs/1.2.组局与报名-后端.md` — 球局域后端规格（组局/报名/可见性三档/意向与邀请，已评审）
- `docs/1.5.灵活首页-后端.md` — 角色化动态首页规格
- `docs/2.1 ~ 5.1.*-前端.md` — 各页面前端规格
- temp/原型图存放处