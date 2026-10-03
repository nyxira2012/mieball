# 前端迁移计划：alpha.html → uni-app 正式前端

编号 FE-MIGRATION · 2026-10-04 · 状态：定稿（供子代理分阶段实施）

## 0. 目标与范围

把 `alpha.html`（单文件、1982 行、零依赖的高保真原型）用 **uni-app（Vue3 + Vite + TS）** 重写为正式前端工程，**1:1 还原其视觉与全部交互**。

- **唯一基准**：`alpha.html` 的视觉、文案、交互、数据口径。文档（2.1/3.1/3.2/4.1/5.1）只作语义参考；与 alpha 不一致处以 alpha 为准（docs 未在 alpha 中体现的能力，如 1.5 灵活首页、真实分享、真实登录，一律不在本次范围）。
- **运行目标**：MVP 纯 H5（docs/1.1 已定：微信内 H5，小程序二期）。所有代码写法避免堵死小程序路径（不写仅 H5 才有的 API 散落各处，平台差异集中封装）。
- **验收方式**：本机 `npm run dev:h5` 浏览器验收（无微信开发者工具，mp-weixin 只做可选的构建通过检查，不做预览）。
- alpha.html 本身**保持只读**，迁移期间不动它。

## 1. 技术选型与工程骨架

| 项 | 决定 | 理由 |
|----|------|------|
| 框架 | uni-app CLI 版（Vue 3 + Vite + TypeScript） | 命令行可操作（子代理无 HBuilderX），一套代码 H5 + 未来小程序 |
| 脚手架 | `npx degit dcloudio/uni-preset-vue#vite-ts frontend` | 官方模板；失败时的手工兜底见 P0 |
| 状态 | Pinia | alpha 的全局可变数据（games/live/intents/scoreMode…）直接映射 |
| 样式 | SCSS + CSS 变量（tokens），单位用 **px** | 原型即 430px 设计宽，px 在 H5/小程序均可渲染，避免 rpx 换算错误；最大宽度容器控制在 P11 处理 |
| 字体 | Anton、Space Grotesk 通过 npm 包 `@fontsource/anton`、`@fontsource/space-grotesk` 自托管（woff2 拷入 `src/static/fonts/`） | Google Fonts 国内不可达；npm 源可达。中文标题回退 PingFang SC 等系统字体（原型本就如此） |
| 测试 | vitest，只覆盖纯逻辑（Elo 引擎、轮转、费用摊法、时间解析） | 这些是产品口径，最值得锁 |
| UI 库 | **不引入任何第三方 UI 库** | 设计完全自定义（夜光霓虹风），自建组件保证还原度 |

### 目录结构（目标态）

```
frontend/
  src/
    pages/
      home/home.vue        # ① 首页
      meet/meet.vue        # ⑤ 约球页(3.1)
      power/power.vue      # ④ 战力页(4.1)
      mine/mine.vue        # ⑥ 我的(5.1)
      detail/detail.vue    # ② 球局详情(3.2)
      live/live.vue        # ③ 现场页(2.1)
    components/
      ui/                  # ★ 自建组件库：从原型逐个抽出的通用件，不含业务语义
        ChibiAvatar.vue      # Q版头像（关键封装，见 §2.1；全库唯一 chibi v-html 出口）
        AppButton.vue        # .btn（pri/burn/ghost/blk/sm 全变体）
        AppChip.vue          # .chip（hot/full/ok）与角色标签（roletag org/inv/dim）
        TierBadge.vue        # .tierb 段位徽章（SS/S/A/B/C）
        Last5Dots.vue        # 近 5 场 W/L 点
        AvatarStack.vue      # 名单头像叠层（前 5 + +N·含随行）
        AppInput.vue         # .inp（含 textarea 态）
        AppField.vue         # .field 表单字段壳（label + 插槽）
        AppStepper.vue       # .stepper
        AppSeg.vue           # .seg 分段选择
        OptionChips.vue      # .crow/.cbtn 单选 chips（组局表单用）
        FilterChips.vue      # .fchips 横滚筛选 chips
        AppToggle.vue        # .tog 开关行
        AppSheet.vue         # 抽屉壳（grab/标题/hint/过渡/遮罩点击关闭）
        SheetHost.vue        # 全局单例弹层宿主（§2.2，按 payload.type 分发）
        AppToast.vue         # 自绘 toast（对应 #toast）
        Confetti.vue         # 撒花（H5 DOM 实现，接口留 canvas 化余地）
        Ticker.vue           # 跑马灯
        SectionTitle.vue     # .sec-t 标题行
        EmptyBox.vue         # .empty 空态
        NoteCard.vue         # .notecard 提示卡
      biz/                 # 业务组件：只允许组合 ui/ 件与业务数据，不得另起样式体系
        TabBar.vue           # 底部导航（4 tab + 中间 FAB，自绘；图标 SVG 走 v-html，作为与 ChibiAvatar 并列登记的例外）
        GameCard.vue / DeadCard.vue / IntentCard.vue
        ProfileSheet.vue     # 球员档案（全产品共用）
        LaunchSheet.vue      # 组局表单（新建/改局复用）
        JoinSheet.vue / ConfirmSheet.vue / InviteSheet.vue / IntentFormSheet.vue
        WinPopup.vue         # 胜利结算卡
        CourtCard.vue / QueueList.vue / Scoreboard.vue / AttendRow.vue
        RankRow.vue / BrawlStage.vue / MyPowerCard.vue
    stores/
      user.ts  game.ts  live.ts  ui.ts
    utils/
      elo.ts  rotate.ts  score.ts  time.ts  chibi.ts  format.ts
    api/
      types.ts  mock.ts  index.ts   # 接口层：mock 适配器，后续换真后端只动这层
    mock/
      data.ts               # alpha 的 U/games/slots/intents/ledger 原样搬入
    styles/
      tokens.scss  base.scss  animations.scss
    static/fonts/
```

**组件库铁律**（用户定版：前端以「从原型抽取的自建组件库」方式实现）：页面（pages/）只做布局与数据接线，一律组合 `components/ui`（通用件）与 `components/biz`（业务件）；ui 件不含业务文案与业务字段；biz 件不重复定义基础样式，只准用 tokens/base 类与 ui 件。新样式需求先落进 tokens/base 或 ui 件，再被页面消费——保证原型抽出的组件体系可复用、可盘点。

### 路由与导航方案

- `pages.json`：全部页面 `navigationStyle: custom`；配置 4 个 tabBar 页（home/meet/power/mine，**不配中间 FAB**），启动时 `uni.hideTabBar()` 隐藏原生条，用自绘 `TabBar.vue`。
- 这样 `uni.switchTab` 保留页面实例（各 tab 滚动位置天然保留，对应 alpha 手动存 scrollTop 的行为）；局详情/现场页用 `uni.navigateTo`。
- FAB（发局按钮）打开 `LaunchSheet`（全局抽屉），不是页面跳转。
- TabBar 的 LIVE 红点 = live store 有进行中球局时点亮（对应 alpha `#live-dot-nav`）。

## 2. 关键技术决策与风险（子代理必读）

### 2.1 Q 版头像（alpha 最核心的资产）

alpha 用参数化 **inline SVG 字符串**（`chibi()`，alpha.html:715-758）+ innerHTML 注入。inline `<svg>` 标签在小程序不渲染、Vue 模板里也写不了动态字符串。

**方案**：封装 `ChibiAvatar.vue` 单一组件，对外只暴露 `:chibi`（配置对象）和 `:size`。
- MVP 实现（H5）：组件内 `v-html` 渲染 SVG 字符串（`utils/chibi.ts` 原样移植 alpha 的生成函数，逐字保留）。
- 该组件是**唯一**允许 v-html 的地方；将来小程序化只改这一个组件（canvas 绘制或预渲染位图），页面代码零改动。

### 2.2 弹层体系

alpha 的 `#sheet` 是全局单例，约 10 种弹层内容共用。对应实现：
- `ui` store 提供 `openSheet(payload)/closeSheet()`，`SheetHost.vue`（每个页面挂一份）按 payload 的 `type` 分发渲染（join/quit-confirm/cancel-confirm/add-court/invite/intent-form/launch/profile）。
- 交互细节保留：mask 点击关闭、grab 条、`transform: translateY(105%)` 过渡、圆角与顶部黄描边。
- `WinPopup`（胜利结算）层级最高，独立组件不走 SheetHost。
- `confirm` 类（退局/取消局/加场）可用一个通用 `ConfirmSheet` 配按钮文案实现。

### 2.3 约球页的两处 sticky 特效（最容易做坏的地方）

alpha.html:986-1016 的「意向头贴底钉位 dockIntentHead」和「焦点切换 focusIntent」依赖 DOM `offsetTop/getComputedStyle`。uni-app 里改用：
- `onPageScroll` + `uni.createSelectorQuery()` 量 `.isec-head` 的位置（页面渲染后先量一次记下自然 offsetTop）；
- 意向头钉位：滚动时算「头自然位置 - scrollTop」，沉到 nav 下沿时用 `transform: translateY()` 拉住——逻辑与 alpha 完全同构，只是取数方式换 API；
- 球局区头 `position: sticky` 保留 CSS 实现（webview 支持）。
- 若首次实现误差大，降级方案：意向区固定为页面普通区块 + 头部吸顶，不做贴底钉位（记录到实施日志，视觉验收时与用户确认）。

### 2.4 动画

CSS keyframes（spin/tick/pulse/fadeUp/pop/bob/clashp/cfall/rankFadeIn）原样搬入 `animations.scss`，H5/微信 webview 均支持。`point()` 里的 `Element.animate()` 得分数字弹跳改用 Vue class 切换 + keyframes 等价实现。入场 stagger（.stag）保留。榜单懒加载的 IntersectionObserver 改为 `onPageScroll` 距底 160px 触发（alpha 本身就有这条双通道逻辑，保滚动通道即可）。

### 2.5 桌面呈现

alpha 在宽屏有 #stage 手机画布居中 + 两侧竖排装饰字 + 噪点 grain。处理：移动端优先 100% 还原；宽屏时 App.vue 全局样式给页面内容加 `max-width: 480px; margin: 0 auto` + 背景装饰，两侧 deco 竖字可选实现（P11，丢了不影响验收）。

### 2.6 环境事实

- node v24.13.1 / npm 11.8.0 ✅；**无微信开发者工具** → 只验 H5。
- npm 需可达（uni-app 依赖、@fontsource 字体包都要装）。若 `degit`（走 GitHub）失败：手工建工程——`package.json` 依赖 `@dcloudio/uni-app、@dcloudio/uni-h5、@dcloudio/vite-plugin-uni、vue、vue-i18n(模板带就留)、pinia、sass、vite、typescript`，配 `vite.config.ts`（uni 插件）与 `src/main.ts`（createSSRApp + Pinia）。模板文件（index.html、shims、pages.json、manifest.json）从 uni-preset-vue 仓库内容手写补齐。
- `.gitignore` 追加 `frontend/node_modules/`、`frontend/dist/`。

## 3. 阶段计划（每阶段 = 一次子代理任务）

> 通用约束（每个子代理任务都要带上）：
> 1. 必读：本计划对应章节 + `alpha.html` 指定行段 + `frontend/` 已有代码。
> 2. 禁止：修改 `alpha.html`；引入第三方 UI 库；绕过 `ChibiAvatar`/`SheetHost` 等既有封装另写一套；颜色/字号/文案自己发明（一律取自 alpha 原文）。
> 3. DoD 通用项：`npm run type-check`（vue-tsc）通过（P2 另加 `npm run test` 全绿）。**子代理不跑 dev/build、不做 git 提交**——构建验证与 `FE-P<N>: <摘要>` 提交由主会话在每波完成后统一执行（避免并行波次的端口/dist/git 竞争）。
> 4. 并行波次中的弹层类任务：`SheetHost` 与 sheet payload 联合类型在 P2/P3 已全量预定义、各弹层 stub 文件已建好，任务只填充自己的 stub 组件文件，不改共享注册文件。

### P0 脚手架（串行第一步）
- 建 `frontend/`（degit vite-ts 模板，兜底手工）。装 pinia、sass、vitest、@fontsource/anton、@fontsource/space-grotesk。
- `pages.json`：6 页注册 + custom 导航 + tabBar(4) ；`manifest.json` h5 基础配置（title 夜球场、theme-color #0E0E12）。
- `App.vue` onLaunch `uni.hideTabBar()`；全局 reset 样式（对应 alpha 33-42 行）。
- `.gitignore` 追加。
- **DoD**：`npm run dev:h5` 出空白可路由首页；`npm run test`（vitest 空跑）通过；`npm run build:h5` 产物生成。

### P1 自建组件库（依赖 P0）
> 用户定版：前端以「从原型抽取的自建组件库」方式实现。本阶段交付 `components/ui/` 全量通用件，后续所有页面阶段只准组合这些件，不得另写平行样式体系（§1 组件库铁律）。

- `styles/tokens.scss`：alpha:16-32 的 CSS 变量全部搬入（颜色/圆角/nav-h/字体栈）+ `@font-face`（woff2 从 `node_modules/@fontsource/{anton,space-grotesk}/files` 拷入 `src/static/fonts/`，禁外网加载；Anton latin + Space Grotesk 400/500/700）。
- `styles/base.scss`：只放**非组件**的通用排版类（reset、kicker/h-disp/brand/sub/sec-t 结构类，alpha:33-91）；已组件化的类（btn/chip/field/inp/stepper/seg/crow/cbtn/tog/empty/notecard…）样式只封装进对应 ui 组件，base 不留重复副本。
- `styles/animations.scss`：全部 keyframes（alpha:67-100, 250-251, 481, 489-490, 571, 589, 591-596 等）。
- `components/ui/` 全量 21 个组件（§1 目录树），样式从 alpha 对应类逐类移植：btn(159-170)、field/inp/stepper/seg(172-192)、sw-capsule(194-200)、crow/cbtn(202-206)、tog/sw(208-216)、chip(116-119)、roletag(325-328)、tierb(407-409)、last5(450-452)、empty/notecard(598-602)、ticker(93-100)、sheet/toast(551-585)、stag(591-596)、avatar(241)、stack(127-132)。
- `utils/chibi.ts`：alpha:715-758 的 `chibi()` 逐字移植；`ChibiAvatar.vue` 封装。
- ui store **归 P2**（并行波次避免共享文件冲突）：P1 的 AppToast/AppSheet 做成 props/事件驱动的纯展示件，P3 再与 store 接线。
- 建路由外挂的 `/pages/dev/style` 样式试衣间页（仅开发用，验收后 P12 删除）：陈列全部 ui 组件全变体与排版类。
- **DoD**：`npx vue-tsc --noEmit` 通过；试衣间页陈列件与 alpha 目测一致；字体 woff2 生效。

### P2 数据层与核心引擎（依赖 P0，可与 P1 并行）
- `mock/data.ts`：U（13 人含 chibi 配置）、games(7 局)、slots、intents、ledger **原样移植**（alpha:760-830），含注释口径（heads/perHead/min-cap/deadline 语义，alpha:776-780 的注释要保留）。
- `api/types.ts`：User/Game/GameEntry/Intent/Slot/Ledger/LiveMatch/LiveState TS 类型。
- `utils/`：
  - `elo.ts`：ntrp 阈值、tier SS/S/A/B/C、K=24、败方 0.6 系数、地板 400、随行半权重、双打按两队人均分结算（alpha:849-865, 1688-1714 公式逐条对齐）；
  - `time.ts`：`gameTime()` 中文相对日解析（alpha:958-974）、`untilTxt`；
  - `rotate.ts`：`fillCourts/nextMatch/avail`（发牌只补片不清场、胜者留场仅头片、fire 排队首、迟到排队尾，alpha:1492-1529）；
  - `score.ts`：净胜 2 分判胜（alpha:1680-1687）、undoPoint 语义；
  - `format.ts`：heads/needOf/perHead/isOrg/isMine/known/freqName/slotName（alpha:882-892）。
- stores：`user.ts`（me + liked 列表 + 换装）、`game.ts`（games/intents/myIntent/增删改查动作，移植 doJoin/doQuit/publish/doCancel/sureGame/hitDeadline/doAddCourt/restoreGame/doInvite/shareGame/saveIntent/delIntent 及其 3 秒模拟延时）、`live.ts`（startLive/point/endMatch/setCheck/toggleMine/newRound）、`ui.ts`（scoreMode/sheet/toast）。
- vitest 单测：elo 结算（强弱对比、随行、地板）、perHead 三口径（不足最少/够最少/必定开局）、gameTime 解析、净胜 2 判胜、fillCourts 三模式。
- **DoD**：`npm run test` 全绿；单测值与手工对照 alpha 控制台一致。

### P3 布局骨架与导航（依赖 P1、P2）
- `TabBar.vue`：5 槽位（首页/约球/FAB/战力/我的）自绘，SVG 图标、选中黄字 + 顶部短横条、LIVE 红点；switchTab 跳转；FAB 触发 `ui.openSheet({type:'launch'})`。
- 4 个 tab 页 + detail/live 页壳：页面容器 padding（safe-area + nav-h 底距，alpha:75-76）、背景装饰圆环（phone::before/after 两条旋转虚线环，alpha:60-67，改为 fixed 伪元素/装饰组件）。
- `SheetHost.vue` 挂到 6 个页面；`AppToast`、`Confetti` 同挂。
- **DoD**：4 tab 可切换、FAB 弹出空抽屉可关、红点逻辑通（临时手改 live store 验证后还原）。

### P4 首页（依赖 P3；可与 P5/P6 并行）
- alpha:611-629、933-950：日期行、跑马灯（`Ticker.vue`，内容×2 无缝循环）、球局列表（先用 `GameCard.vue` 基础版：无角色标签态也行，P5 完善）、约球入口 wave 卡（waveCount/未留意向两态）。
- **DoD**：与 alpha 首页逐屏目测一致；点球局卡可跳详情占位页；wave 卡跳约球页。

### P5a 局卡组件 + 局详情静态（依赖 P3、P2）
- `GameCard.vue` 完整版（alpha:898-917）：时间大字、角色标签（我发起/被邀请/已加入）、状态 chips（剩 N 坑/满员候补/进行中 live 呼吸灯）、人数/人均 chip、头像叠层 stack（前 5 + +N ·含随行）、被邀请点击直接开 joinSheet 的分支。
- `DeadCard.vue`（未成局，alpha:919-931）。
- 详情页静态结构（alpha:1400-1467）：hero 大时间 + kv 行（名单/剩坑/总价/人均/截止）、说明与人均口径文案、steps 进度、名单网格（含「带 N 人」「随行」标签、虚线加入卡）、候补栏、组织者按钮区、规则牌 notecard、状态相关按钮的显隐逻辑（joined/org/locked/sure/live 全组合）。
- **DoD**：从首页点进 7 个 mock 局，每种状态组合渲染正确（截图对照 alpha 手工核对）。

### P5b 详情页全部操作与弹层（依赖 P5a）
- 弹层：`JoinSheet`（带人 stepper、满员进候补文案、不足最少按最少摊提示，alpha:1107-1138）、`ConfirmSheet`（退局/取消局/加场三用）、`InviteSheet`（翻我发起的局/翻意向列表两入口，alpha:1213-1263）。
- 动作全部走 game store：加入/带人/候补、退出（释放名额含带的人）、改信息（打开 LaunchSheet 带原值）、取消局、锁定必打、到截止判定（<min 且未 sure → dead；否则 locked）、加场 +2 上限候补自动转正、恢复局、分享 toast + 3 秒模拟球友加入。
- 每个动作后相关页面数据联动（首页/约球/详情/我的 —— store 响应式天然解决，需验证）。
- **DoD**：§6 验收清单 C1-C10 全部可走通。

### P6 组局表单（依赖 P5a；可与 P7 前期并行）
- `LaunchSheet.vue`（alpha:1299-1398）：局名（空则「时间·地点」自动起）、时间 chips + 自定义输入、时长 chips、截止 chips + 自定义（**编辑态截止定死只读**）、场地 chips + 手输、最少/最多双 stepper（联动约束 min≤cap-1、范围 2-16）、费用 chips + 手输、说明、发布/保存修改。
- 新建与编辑同一表单复用（编辑时名单不动提示）。
- **DoD**：新建一局出现在列表顶部且我是头一个；编辑后详情同步；验收清单 C11-C12。

### P7 约球页（依赖 P5a、P6）
- alpha:952-1105：头部 + meet 跑马灯（被邀请 + NEXT 倒计时，alpha:983-994）、球局区吸顶头（筛选▾/收起按钮、N 个 · 我的置顶）、折叠筛选 chips（时间×5、地区×5）、列表（pinned 置顶排序 + gameTime 升序）、空态、未成局区（仅组织者）、意向区（头 + scope 切换所有人/熟人 + 我的意向条目 改/删 或 useentry）、`IntentCard.vue`（时段大字卡 + 分值 chip + ♥/熟人标签）、排序（liked 优先→熟人优先）。
- `IntentFormSheet.vue`（alpha:1264-1297）：4 时段 slotgrid（含同波段 N 人）、频率三段 seg、保存校验（至少一个时段）。
- §2.3 的意向头钉位/焦点切换。
- **DoD**：验收清单 C13-C18；筛选/折叠/钉位行为与 alpha 一致。

### P8a 现场页：到场 + 轮转（依赖 P5a；可与 P8b 一次做或拆分）
- `startLive`（alpha:1471-1490）：名单展开随行访客（随机 chibi、shadow 标记）、前 9 人 ok 其余 absent、live store 初始化、导航红点。
- 页面三 tab（segtab：到场/轮转/记分，alpha:1531-1571）。
- 到场面板：`AttendRow`（已到/迟到/早退/未到/中途加入五态 + 四操作钮，setCheck 副作用：迟到排队尾、早退清队清场、中途加入进队首）。
- 轮转面板：歇一轮/连战双按钮（互斥）、场地卡 `CourtCard`（A/B 队、VS、net 虚线、playing 标）、候场队列 `QueueList`（序号、歇/燃/迟到/随行角标）、开下一轮（未打完场次退回重排 + confetti(14)）。
- **DoD**：验收清单 C19-C23。

### P8b 现场页：记分 + Elo 结算 + 胜利弹层（依赖 P8a）
- `Scoreboard.vue`（alpha:1651-1687）：COURT 1 · FIRST TO N · WIN BY 2、76px 大比分、A/B 得分钮、撤回一分（按最后得分方回退）、得分数字弹跳动画。
- `endMatch` + `WinPopup.vue`（alpha:1688-1729）：胜队、比分、胜者头像、每人 Elo 涨跌（K=24/败方六成/随行半权重注脚）、confetti(56)、收下·下一轮。
- 结算后：Elo 落回 user/榜单（同一份数据）、last5 更新、败者回队尾/胜者留场规则（winner 模式且头片空缺）、history 列表。
- **DoD**：验收清单 C24-C27；打一场后战力页分数变化与 alpha 相同操作路径的结果一致。

### P9 战力页 + 球员档案（依赖 P3、P2；可与 P5-P8 并行）
- alpha:1731-1929：Elo/NTRP 胶囊切换（右上）、我的战力卡（4 种卡背 bg-neon/gold/cyber/aurora、排名、段位徽章、本月涨跌、未开局两态、运动数据条）、前三打架图 `BrawlStage`（bob 浮动、⚡clash 脉冲、皇冠、球拍 SVG——球拍也走 chibi.ts 同款 SVG 字符串 + v-html，并入 ChibiAvatar 封装边界内）、评分排行 `RankRow`（前三高亮、近 5 场点、本月涨跌、懒加载每批 5 条 + 距底自动加载 + 尾部提示）、规则折叠（积分怎么算的）。
- `ProfileSheet.vue`（alpha:1891-1929）：头像+徽章+分+摘要+近5场、意向行（若有）、喜欢/邀请入局按钮（我则无）、tierB 徽章组件。全产品共用（榜单/意向卡/现场队员/我的头像都唤起它）。
- **DoD**：验收清单 C28-C33。

### P10 我的页（依赖 P3、P2；可并行）
- alpha:1931-1976：mecard（点头像换装：先选部件 chips 肤色/发型/发色/球衣/表情/配饰，再点小人循环换）、战绩行、ELO chip、换装提示 notecard、账本 ledger（池子总额/我的结余 垫多收钱 or 还欠转账、逐笔 已垫付/待付、结束本期按钮 toast）、我的球局近 3 场、退出登录/注销账号按钮（toast 文案原样）。
- **DoD**：验收清单 C34-C36。

### P11 串联与打磨（依赖全部）
- 页面级细节补齐：入场 stagger、LIVE 状态下首页/详情的「回到现场」、各空态。
- 桌面宽屏画布（§2.5）：480px 居中 + 背景圆环 + grain 噪点层；两侧 deco 竖字可选。
- 跨页一致性扫尾：toast 文案逐条对照 alpha；被邀请局在首页/约球的双入口行为。
- 移除 P1 的开发试衣间页路由外的引用（页面删除挪到 P12）。
- **DoD**：全页面走查无布局破版；`npm run build:h5` 成功。

### P12 验收与收尾（依赖 P11；建议回主会话做）
- 按 §6 全清单在浏览器逐条执行并截图对照 alpha.html（同屏双开对照）。
- `npm run build:h5` 产物本地起静态服务可跑通主链路。
- 删除试衣间页；`window.__alpha` 调试口不迁移（Pinia devtools 替代）。
- 回写本计划文档的实施状态（各阶段 ✅ + 偏差记录）。

### 依赖与并行图

```
P0 → P1 ┐
P0 → P2 ┤→ P3 → P4        (P4 ‖ P5a ‖ P9 ‖ P10)
        └→ P5a → P5b → P7
              ↘ P6 ↗
        P5a → P8a → P8b
全部 → P11 → P12
```

## 4. 数据与逻辑迁移映射（速查）

| alpha 全局量/函数 | 行号 | 去处 |
|---|---|---|
| U / games / slots / intents / ledger / myIntent | 760-830 | `mock/data.ts`（原样） |
| chibi / av | 715-758 | `utils/chibi.ts` + `ChibiAvatar.vue` |
| toast/openSheet/closeSheet/confetti | 832-847 | ui store + AppToast/SheetHost/Confetti |
| ntrp/fmtScore/tier/tierB/last5dots/rankRows | 849-865 | `utils/elo.ts` |
| go()/页面切换 | 867-879 | uni 路由 + TabBar |
| heads/needOf/perHead/myEntry/isOrg/isMine/known | 881-892 | `utils/format.ts` |
| gameCard/deadCard | 898-931 | GameCard/DeadCard 组件 |
| gameTime/untilTxt/meetTicker | 958-994 | `utils/time.ts` + meet 页 |
| join/quit/cancel/sure/hitDeadline/addCourt/restore/invite/share | 1106-1263 | game store 动作 |
| intentForm/ifTog/saveIntent/delIntent | 1264-1297 | IntentFormSheet |
| openLaunch/lfMin/lfCap/publish | 1299-1398 | LaunchSheet |
| openDetail | 1400-1467 | detail 页 |
| startLive/pById/avail/fillCourts/nextMatch | 1471-1529 | live store + `utils/rotate.ts` |
| renderAttend/setCheck/renderCourts/tp/toggleMine/newRound | 1531-1648 | live 页到场/轮转面板 |
| renderScore/undoPoint/point/endMatch/closeWin | 1651-1729 | Scoreboard + `utils/score.ts`/`elo.ts` + WinPopup |
| renderPower/榜单/懒加载/规则折叠 | 1731-1889 | power 页 |
| openProfile/toggleLike | 1891-1929 | ProfileSheet |
| renderMine/换装/mountDress | 1931-1976 | mine 页 |

**必须逐字保留的业务口径**（写代码时的注释也要带上）：
- 带的人也占坑（heads 计入 bring）；满员线口径只讲「剩几坑」。
- 人均摊法三口径：不足最少按最少摊 / 够最少按当前人数摊 / 锁定必打后最少作废按当前人数摊（perHead，alpha:884）。
- 截止到点：低于最少且未锁必打 → 自动终止（dead，仅组织者可见可恢复）；否则名单锁定不可退。
- 加场 = 上限 +2，候补按先后自动转正。
- Elo：K=24、爆冷大涨、败方只扣六成、地板 400、随行访客半权重不进榜、双打按两队人均分结算到个人。
- 记分：先到 N 且净胜 2 才算赢。
- 迟到自动排队尾；早退从队列和场上清除；中途加入进队首；歇一轮消耗型徽章；连战排到队首且与歇互斥。
- 喜欢：静默单向，约球页/意向列表优先展示。

## 5. 组件与样式映射注意

- alpha 的 CSS 类分三类搬：①通用类进 `base.scss`；②页面专属类放各页 `<style lang="scss" scoped>`；③确认未使用的类（如 `.gscale/.gsl`、`.radwrap`）不搬，在 P12 回写时记录。
- 颜色一律用 token 变量，不许硬编码 hex（alpha 内联 style 里的硬编码色，搬的时候替换为对应变量或补 token）。
- 文案（toast/提示/空态/规则牌）**逐字照抄 alpha**，不得润色。

## 6. 全局验收清单（P12 执行；各阶段先自测对应项）

- C1 点球局卡进详情，各状态 kv/按钮显隐正确
- C2 未加入局点「加入」→ stepper 带 0-3 人 → 名单/剩坑/人均联动、toast 正确
- C3 满员局加入 → 进候补栏提示
- C4 已加入非锁定局退局 → 名额释放（带的人一起退）
- C5 组织者：改信息（截止只读）→ 名单不动其余更新
- C6 组织者：取消局 → 局从列表消失
- C7 组织者：锁定必打 → 徽章态；到截止判定 → 名单锁定/不能退
- C8 人数不足局到截止 → 自动终止 → 约球页「未成局」区出现 → 可恢复 / 可撤局
- C9 加场 → 上限+2 → 候补自动转正 toast
- C10 分享按钮 → toast → 3 秒后小张加入并带 1 人
- C11 FAB 发局：全默认发布 → 列表顶部新局、我是名单头一个
- C12 发局自定义时间/场地/费用 → 局名自动起名规则正确
- C13 约球页：时间/地区筛选、列表收起/展开
- C14 我的（参加/组织/被邀请）置顶 + 角色标签正确
- C15 留意向 → 时段多选 + 频率 → 保存；改/删意向
- C16 意向列表：所有人/熟人切换、喜欢的人优先、意向卡分值显示
- C17 邀请入局（档案/局详情两入口）→ 3.2 秒后模拟加入 toast
- C18 意向头贴底钉位与焦点切换（或降级方案已记录）
- C19 开始打球 → 现场页、导航红点亮、随行访客生成
- C20 签到/迟到（排队尾）/早退（清场）/中途加入（队首）四操作及 toast
- C21 歇一轮 / 连战切换互斥 + 队列角标
- C22 三模式发牌：均衡蛇形 / 胜者留场（仅头片空缺生效）/ 纯轮转
- C23 开下一轮：未打完场次退回重排 + 撒花
- C24 记分：A/B 得分、数字弹跳、误记撤回（按最后得分方）
- C25 11:9 收局 vs 11:10 继续（净胜 2 规则）
- C26 胜利弹层：比分/胜者/Elo 变动列表/注脚/大撒花
- C27 打完后战力页：分数、近 5 场、榜单顺序变化与 alpha 一致
- C28 Elo/NTRP 切换全页联动（榜单、档案、意向卡）
- C29 我的战力卡：未开局态/已开局态、四种卡背
- C30 前三打架图动画与点击档案
- C31 榜单懒加载：滚动自动 + 点尾部加载 + 全部加载完提示
- C32 规则折叠展开
- C33 球员档案：喜欢/取消、邀请按钮、意向行展示
- C34 我的页换装：部件选择 + 点小人循环换 + 全产品形象同步
- C35 账本数字口径：结余 = myPaid − myShare，垫多/还欠两态文案
- C36 退出登录/注销账号 toast
- C37 跑马灯：首页固定内容、约球页动态（邀请 + NEXT 倒计时）
- C38 战力页「我的卡」点头像 → 我的页（stopPropagation 正确）

## 7. 明确不做 / 后续任务（迁移完成后另立）

- 真实后端接入（1.1 账号、1.5 灵活首页）——api 层已留缝。
- 微信分享卡片真实实现（现为模拟）。
- 小程序端专项适配（ChibiAvatar canvas 化、loadFontFace、分享语义）。
- alpha 中未出现的 docs 能力（灵活首页四态、战报页、迟到分钟累计、多片步进器 1-8、均衡指数环等）。
- `window.__alpha` 调试口（用 Pinia devtools 替代）。

## 8. 实施状态回写（P12 填写）

> 2026-10-04 实施完成。P0–P11 由子代理分阶段实施（P1‖P2、P4‖P5a‖P9‖P10、P5b‖P6‖P7‖P8a 并行波次），每阶段独立提交（FE-P0…FE-P12）；P12 由主会话浏览器对照验收。

| 阶段 | 状态 | 完成日期 | 偏差记录 |
|------|------|----------|----------|
| P0 | ✅ | 2026-10-04 | 无（degit 模板一次成功；构建/dev/type-check 三验证通过） |
| P1 | ✅ | 2026-10-04 | body reset 未搬 overflow:hidden/100dvh（单文件画布专用，uni 页面自滚动）；sw-capsule 落 base.scss 作通用类；AppSheet 用 fixed 替代 absolute；FilterChips 用 scroll-view |
| P2 | ✅ | 2026-10-04 | MatchHistory/WinData 存纯文本而非 HTML 串（v-html 纪律）；gameTime 入参为 t 字符串便于单测；myIntent 以 store ref 为准；测试放 frontend/tests/ 避开 uni 编译扫描。77 单测全绿 |
| P3 | ✅ | 2026-10-04 | 页签转场由 uni 路由自带，未搬 alpha 手动 translateX；grain 留 P11；ui store 纯增量补 confettiKey/confettiN |
| P4 | ✅ | 2026-10-04 | brand/em 用 text+class 等价（uni 模板无 h1/em/br） |
| P5a | ✅ | 2026-10-04 | plusn 由 GameCard 自绘（AvatarStack 只管头像）；gcard 壳样式组件内副本；直链无局兜底文案「该局不存在或已被撤下」 |
| P5b | ✅ | 2026-10-04 | 动作后导航以 store 响应式替代 alpha 的 go()/openDetail 重渲染；invite 两形态沿用 SheetPayload 契约（to-game/to-slot） |
| P6 | ✅ | 2026-10-04 | DOM 显隐切换改 v-if；自定义时间未输入即发布的 alpha 边界行为原样保留 |
| P7 | ✅ | 2026-10-04 | 钉位/焦点切换**未降级**，用 onPageScroll+createSelectorQuery 缓存自然位实现（量前清 transform，布局变化重测） |
| P8a | ✅ | 2026-10-04 | 开下一轮 confetti 由页面调 ui.burst(14)；onShow 自动 startLive 防重复 |
| P8b | ✅ | 2026-10-04 | 得分弹跳用 CSS class 等价 Element.animate；endMatch 在 store 内自动触发，页面 watch ui.win 撒花 56 |
| P9 | ✅ | 2026-10-04 | 分制切换绑在 option 上（点选中项 no-op，净行为同 alpha）；懒加载测高用 createSelectorQuery 折算；paddleSvg v-html 登记为第三例外 |
| P10 | ✅ | 2026-10-04 | 我的球局复用完整 GameCard（alpha 为简化两行）；ledger 直读 api/mock（stores 未暴露，后续可收敛） |
| P11 | ✅ | 2026-10-04 | PageShell onHide 关弹层；quit/cancel 后 switchTab meet（同页守卫）；宽屏 480 画布+deco 竖字+grain；toast 文案 28 处机械对照**零不一致**；删除 SheetStub |
| P12 | ✅ | 2026-10-04 | 浏览器对照验收 + judge 两组合议 12 对：11 pass。修复三项：① uni-text 框架默认 pre-line 致跑马灯/chips 逐字竖排（base.scss 全局 !important inherit）；② 原生 tabBar 时序盖回（CSS 隐藏 uni-tabbar）；③ AppChip 误加 nowrap 破坏 alpha 收缩形态（已撤）。已知残留小偏差：满员卡「+8·含随行」在 foot 极限收缩下尾部两字被裁（alpha 为两行完整，量级 2×10px）；胜利弹层超长胜队名自然换行。试衣间页与 static/alpha-ref.html 已按计划删除。 |

**P12 修复的横切根因（后续小程序化需复检）**：uni-h5 `uni-text{white-space:pre-line}` 与原生 tabBar 时序——见 frontend/src/styles/base.scss 顶部注释。
