#!/usr/bin/env python3
"""
mieball 项目 - RunningHub 生图客户端 (单文件脚本)
文件: rhpic.py

功能与规范：
1. 槽位预设（仿 comfy.py 分工纪律：工程归脚本，内容归调用方）：
   - 人物形象 (avatar)：1024x1024 方图，2D 二头身动漫大头贴纸、粗白描边、
     纯天蓝抠图底；默认保存至 temp/形象/
   - 卡片背景 (card_bg)：1536x640 超宽横幅（战力卡横条构图、左侧安静区
     留给 UI 文字）；默认保存至 temp/卡片背景/
2. Prompt 架构分层：
   - 规范部分（画风/画布/底色）：按槽位预设内置，尺寸字样由预设画布派生
   - 内容部分：由 CLI 传入（如 "阿拉斯加犬，戴着红色围兜写着凶字"），只写
     「谁/穿什么/神态」，不写画风与构图
3. 画布尺寸同步纪律（远程工作流画布不在本脚本手里，改尺寸两处需同步）：
   - 路线 A：每槽位一个专用工作流（RUNNINGHUB_WORKFLOW_ID_AVATAR /
     RUNNINGHUB_WORKFLOW_ID_CARD_BG），画布在工作流里建好
   - 路线 B：共用一个工作流 + --canvas-node-id 指出空潜空间画布节点，
     脚本直接下发 width/height 覆盖
4. 纯 Python 标准库编写，零三方包依赖，支持 --dry-run 免费预览与 --list-presets。
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ==========================================
# 1. 槽位预设（工程参数 + 规范提示词模版）
# ==========================================
# 分工纪律仿 comfy.py：画风/画布/底色/落盘目录归脚本管，「谁/穿什么/神态」
# 内容词全由 -c 调用方传入。提示词里的尺寸字样由 width/height 派生注入，
# 预设改尺寸不会与提示词各说各话；远程工作流画布须与预设一致（同步纪律
# 见模块 docstring：专用工作流或 --canvas-node-id 下发覆盖）。

PRESETS: dict = {
    # 蓝幕色 #4A90E2 是 process_avatar.py 角点采样抠图的期望底色；
    # 改色需 grep #4A90E2 同步全部出现处（含 comfy.py 的 sky_blue 短语）
    "avatar": {
        "title": "球员头像（二头身大头贴纸）",
        "width": 1024,
        "height": 1024,
        "size_phrase": "centered {w}x{h} square avatar",
        "role": "subject",
        "workflow_env": "RUNNINGHUB_WORKFLOW_ID_AVATAR",
        "out_dirname": "形象",
        "spec_prefix": (
            "2D anime chibi sticker style, 2-head-tall big head cute character, "
            "bold thick crisp white outline contour surrounding the entire character, "
            "isolated solid pure sky blue background (#4A90E2), vector sticker art, "
            "clean smooth lines"
        ),
        "spec_suffix": (
            "vibrant colorful palette, high quality illustration, masterwork, "
            "no complex scenery, no text watermark, sharp details"
        ),
        "neg_prompt": (
            "realistic photograph, complex background, gradient background, "
            "shadows on background, messy lines, blurry, watermark, signature, "
            "low quality, bad anatomy, deformed"
        ),
        # 生成成功后的指路提示（{save_path}/{w}/{h} 在打印时注入）
        "post_hint": (
            '可使用 python3 scripts/process_avatar.py "{save_path}" 进行自动抠图与 WebP 压缩。'
        ),
    },
    # 1536x640：战力卡约 480x190 逻辑像素、@3x 清晰铺满的最小整画布；
    # 左侧安静暗部与主体光效居右是卡面文字排版硬约束，属工程规范不属内容词；
    # 改尺寸须与 comfy.py mb_cardbg 及 process_asset.CARD_SIZE 同步（跨脚本契约）
    "card_bg": {
        "title": "战力卡背横幅",
        "width": 1536,
        "height": 640,
        "size_phrase": "ultra-wide {w}x{h} horizontal banner composition",
        "layout_phrase": (
            "key visuals spread across the central horizontal band, "
            "left half kept as quiet low-contrast dark zone reserved for UI text overlay, "
            "focal glow concentrated on the right side"
        ),
        "role": "theme",
        "workflow_env": "RUNNINGHUB_WORKFLOW_ID_CARD_BG",
        "out_dirname": "卡片背景",
        "spec_prefix": (
            "Abstract modern sports UI card background wallpaper, elegant texture, "
            "sleek minimalist geometric shapes, stylish lighting and soft glow, "
            "sports aesthetic, pickleball court dynamic atmosphere, clean composition"
        ),
        "spec_suffix": (
            "smooth visual gradient, premium dark and neon mood, 8k resolution, "
            "graphic design backdrop"
        ),
        "neg_prompt": (
            "human, person, characters, face, text, letters, words, logo, typography, "
            "watermark, noisy, messy, photographic human, cluttered"
        ),
        "post_hint": (
            "卡背 {w}x{h} 直出即用；体积大时可用 "
            'python3 scripts/process_asset.py --optimize --quality 52 "{save_path}" 压缩，'
            '也可随时跑 python3 scripts/process_asset.py "{save_path}" 复验规格闸门。'
        ),
    },
}

# --type 简称 → 正式槽位名（argparse choices 与 main 归一化都从这里派生）
TYPE_ALIASES: dict = {"bg": "card_bg"}


def build_prompt(item_type: str, content: str) -> tuple[str, str]:
    """按槽位预设拼装规范部分与内容部分，生成最终提交给 RunningHub 的提示词"""
    preset = PRESETS[item_type]
    content = content.strip()
    canvas = preset["size_phrase"].format(w=preset["width"], h=preset["height"])
    parts = [
        preset["spec_prefix"],
        canvas,
        preset.get("layout_phrase", ""),
        f"{preset['role']}: {content}",
        preset["spec_suffix"],
    ]
    return ", ".join(p for p in parts if p), preset["neg_prompt"]


# ==========================================
# 2. RunningHub API 请求客户端 (纯标准库)
# ==========================================
class RunningHubClient:
    def __init__(self, api_key: str, host: str = "www.runninghub.cn"):
        self.api_key = api_key.strip()
        self.host = host.strip()
        self.base_url = f"https://{self.host}"

    def _http_post(self, path: str, data: dict) -> dict:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        headers = {
            "Host": self.host,
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Mieball-RHPic/1.0",
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP 错误 {e.code}: {err_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"网络连接失败: {e.reason}")

    def create_workflow_task(
        self,
        workflow_id: str,
        prompt: str,
        neg_prompt: str = "",
        prompt_node_id: str = "6",
        prompt_field: str = "text",
        *,
        canvas=None,
    ) -> str:
        """调用 ComfyUI 工作流任务端点（负向提示词固定写节点 7 的 text 字段）。

        canvas=(画布节点 ID, 宽, 高) 时对该节点（空潜空间画布节点）追加下发
        width/height，一个远程工作流即可承载多尺寸预设，无需每预设各建一份。
        """
        node_info_list = [
            {
                "nodeId": str(prompt_node_id),
                "fieldName": prompt_field,
                "fieldValue": prompt,
            }
        ]
        if neg_prompt:
            node_info_list.append(
                {
                    "nodeId": "7",
                    "fieldName": "text",
                    "fieldValue": neg_prompt,
                }
            )
        if canvas:
            node_id, width, height = canvas
            node_info_list.extend(
                [
                    {
                        "nodeId": str(node_id),
                        "fieldName": "width",
                        "fieldValue": str(width),
                    },
                    {
                        "nodeId": str(node_id),
                        "fieldName": "height",
                        "fieldValue": str(height),
                    },
                ]
            )

        payload = {
            "apiKey": self.api_key,
            "workflowId": workflow_id,
            "nodeInfoList": node_info_list,
        }
        res = self._http_post("/task/openapi/create", payload)
        code = res.get("code")
        if code != 0:
            raise RuntimeError(
                f"创建生图任务失败 (code {code}): {res.get('msg', '未知错误')}"
            )
        data = res.get("data") or {}
        task_id = data.get("taskId") if isinstance(data, dict) else data
        if not task_id:
            raise RuntimeError(f"未获取到 taskId: {res}")
        return str(task_id)

    def create_ai_app_task(self, webapp_id: str, prompt: str) -> str:
        """调用 AI App / WebApp 快速任务端点"""
        payload = {
            "apiKey": self.api_key,
            "webappId": webapp_id,
            "nodeInfoList": [
                {
                    "nodeId": "1",
                    "fieldName": "prompt",
                    "fieldValue": prompt,
                }
            ],
        }
        res = self._http_post("/task/openapi/ai-app/run", payload)
        code = res.get("code")
        if code != 0:
            raise RuntimeError(
                f"AI App 启动失败 (code {code}): {res.get('msg', '未知错误')}"
            )
        data = res.get("data") or {}
        task_id = data.get("taskId") if isinstance(data, dict) else data
        return str(task_id)

    def wait_for_output(
        self, task_id: str, poll_interval: int = 3, timeout_sec: int = 180
    ) -> str:
        """轮询查询生图结果"""
        payload = {"apiKey": self.api_key, "taskId": task_id}
        start_time = time.time()
        print(f"  -> 任务已提交 (ID: {task_id})，等待生成中", end="", flush=True)

        while time.time() - start_time < timeout_sec:
            time.sleep(poll_interval)
            print(".", end="", flush=True)
            res = self._http_post("/task/openapi/outputs", payload)
            code = res.get("code")

            if code == 0:
                data = res.get("data")
                img_url = self._extract_file_url(data)
                if img_url:
                    print(" 完成!")
                    return img_url
                raise RuntimeError(f"任务完成但未找到图片地址: {res}")

            msg = str(res.get("msg", "")).lower()
            if code in (804, 805) or "running" in msg or "pending" in msg:
                continue

            raise RuntimeError(f"\n生成任务异常 (code {code}): {res.get('msg')}")

        raise TimeoutError(f"\n生成等待超时 (已等待 {timeout_sec} 秒)")

    @staticmethod
    def _extract_file_url(data) -> str:
        if isinstance(data, list) and len(data) > 0:
            for item in data:
                if isinstance(item, dict):
                    if "fileUrl" in item:
                        return item["fileUrl"]
                    if "url" in item:
                        return item["url"]
                elif isinstance(item, str) and item.startswith("http"):
                    return item
        elif isinstance(data, dict):
            return data.get("fileUrl") or data.get("url") or ""
        elif isinstance(data, str) and data.startswith("http"):
            return data
        return ""

    @staticmethod
    def download_image(img_url: str, save_path: Path):
        save_path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(
            img_url, headers={"User-Agent": "Mieball-Downloader/1.0"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = resp.read()
        with open(save_path, "wb") as f:
            f.write(content)


# ==========================================
# 3. 命令行交互入口
# ==========================================
def main():
    parser = argparse.ArgumentParser(
        description="rhpic.py - RunningHub 规范生图工具 (支持人物形象/卡片背景)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例用法:
  # 1. 免点数预览人物形象提示词与落盘路径
  python3 scripts/rhpic.py --type avatar -c "阿拉斯加犬，戴着红色围兜写着凶字" --dry-run

  # 2. 正式生成人物形象 (1024x1024 方图，默认保存在 temp/形象/)
  python3 scripts/rhpic.py --type avatar -c "阿拉斯加犬，戴着红色围兜写着凶字" --name "alaska_dog"

  # 3. 生成卡片背景 (1536x640 超宽横幅，默认保存在 temp/卡片背景/)
  python3 scripts/rhpic.py --type card_bg -c "赛博朋克极光，幽蓝与金黄粒子流光" --name "bg_cyber_aurora"

  # 4. 共用一个工作流时，让脚本按预设尺寸直接覆盖远程画布节点
  python3 scripts/rhpic.py --type card_bg -c "暗金熔炉，琥珀色流光" --canvas-node-id 3

  # 5. 查看全部槽位预设（画布尺寸/落盘目录/专用工作流环境变量）
  python3 scripts/rhpic.py --list-presets
""",
    )
    parser.add_argument(
        "--type",
        "-t",
        choices=[*PRESETS, *TYPE_ALIASES],
        default="avatar",
        help="生图类型: avatar(人物形象, 默认) 或 card_bg/bg(卡片背景)",
    )
    parser.add_argument(
        "--content",
        "-c",
        default="",
        help="生图内容描述，只写「谁/穿什么/神态」 (例如: '阿拉斯加犬，戴着红色围兜写着凶字')",
    )
    parser.add_argument(
        "--name",
        "-n",
        default="",
        help="输出图片文件名 (不含后缀，默认根据时间或内容自动命名)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("RUNNINGHUB_API_KEY", ""),
        help="RunningHub API Key (默认读环境变量 RUNNINGHUB_API_KEY)",
    )
    parser.add_argument(
        "--workflow-id",
        default="",
        help="RunningHub ComfyUI 工作流 ID (缺省按优先级读槽位专用与通用环境变量)",
    )
    parser.add_argument(
        "--webapp-id",
        default=os.getenv("RUNNINGHUB_WEBAPP_ID", ""),
        help="RunningHub AI App ID (可选，与 workflow-id 二选一)",
    )
    parser.add_argument(
        "--prompt-node-id",
        default="6",
        help="工作流中正向提示词节点 ID (默认 6)",
    )
    parser.add_argument(
        "--prompt-field",
        default="text",
        help="工作流中提示词输入字段 (默认 text)",
    )
    parser.add_argument(
        "--canvas-node-id",
        default="",
        help="工作流中空潜空间画布节点 ID (如 EmptyLatentImage 节点号)；提供时脚本按预设尺寸下发 width/height 覆盖",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="列出全部槽位预设 (画布/落盘目录/专用工作流环境变量) 后退出",
    )
    parser.add_argument(
        "--host",
        default="www.runninghub.cn",
        help="RunningHub 域名 (国内站 www.runninghub.cn，海外站 www.runninghub.ai)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="免点数预览：仅打印拼装后的提示词及参数，不调用接口",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="自定义保存目录 (留空时: avatar保存在 temp/形象/，card_bg保存在 temp/卡片背景/)",
    )

    args = parser.parse_args()

    # --list-presets：打印槽位清单后退出（无需 -c 与 API Key）
    if args.list_presets:
        print("=" * 68)
        print("【rhpic.py - 槽位预设清单】")
        print("=" * 68)
        for key, p in PRESETS.items():
            print(f"  {key:8s} {p['title']}")
            print(
                f"          画布: {p['width']}x{p['height']}   落盘: temp/{p['out_dirname']}/"
            )
            print(f"          专用工作流环境变量: {p['workflow_env']}")
        print("=" * 68)
        return

    if not args.content:
        parser.error("参数 --content/-c 为必填（--list-presets 除外）")

    # 规范化类型与槽位预设（别名表兜住简称，加新槽位只改 PRESETS 与 TYPE_ALIASES）
    item_type = TYPE_ALIASES.get(args.type, args.type)
    preset = PRESETS[item_type]

    # 确定保存路径 (脚本位于 scripts/ 下，项目根目录为父级的父级)
    workspace_root = Path(__file__).resolve().parent.parent
    if args.output_dir:
        out_dir = Path(args.output_dir).resolve()
    else:
        out_dir = workspace_root / "temp" / preset["out_dirname"]

    # 确定文件名
    if args.name:
        safe_name = args.name.strip()
    else:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = f"{item_type}_{timestamp}"

    save_path = out_dir / f"{safe_name}.png"

    # 拼装提示词：规范部分 + 内容部分
    final_prompt, neg_prompt = build_prompt(item_type, args.content)

    print("=" * 68)
    print("【rhpic.py - 生图任务配置】")
    print("=" * 68)
    print(f"  模式分类: {preset['title']} ({item_type})")
    print(
        f"  预设画布: {preset['width']}x{preset['height']}"
        "（远程工作流画布须与此一致；不一致时用 --canvas-node-id 由脚本下发覆盖）"
    )
    print(
        f"  画布覆盖: {'节点 ' + args.canvas_node_id if args.canvas_node_id else '未启用'}"
    )
    print(f"  传入内容: {args.content}")
    print(
        f"  目标落盘: {save_path.relative_to(workspace_root) if save_path.is_relative_to(workspace_root) else save_path}"
    )
    print(f"\n[拼装后的正向 Prompt (规范+内容)]:\n  {final_prompt}")
    print(f"\n[负向 Prompt (规范约束)]:\n  {neg_prompt}")
    print("=" * 68)

    # Dry Run 预览结束
    if args.dry_run:
        print("[提示] 当前为 --dry-run 预览模式，未产生任何网络请求和点数消耗。")
        return

    # 正式调用参数校验
    if not args.api_key:
        print(
            "\n[错误] 未检测到 API Key！请使用 --api-key 传入，或设置环境变量 export RUNNINGHUB_API_KEY='你的Key'"
        )
        sys.exit(1)
    # 工作流 ID 解析优先级：命令行 > 槽位专用环境变量 > 通用环境变量回退
    # （通用回退时画布未必匹配本槽位预设，输出里带提示人工把关）
    workflow_id = args.workflow_id
    workflow_src = "命令行 --workflow-id" if workflow_id else ""
    if not workflow_id:
        for env, note in (
            (preset["workflow_env"], "槽位专用"),
            ("RUNNINGHUB_WORKFLOW_ID", "通用回退，注意画布是否匹配预设"),
        ):
            workflow_id = os.getenv(env, "")
            if workflow_id:
                workflow_src = f"环境变量 {env} ({note})"
                break

    if not workflow_id and not args.webapp_id:
        print(
            f"\n[错误] 请提供 --workflow-id / 环境变量 {preset['workflow_env']} (工作流模式) 或 --webapp-id (AI App 模式)！"
        )
        sys.exit(1)

    client = RunningHubClient(api_key=args.api_key, host=args.host)
    src_note = f"（工作流来源: {workflow_src}）" if workflow_src else "（AI App 模式）"
    print(f"\n正在向 RunningHub 发起生图请求{src_note}...")

    try:
        if workflow_id:
            task_id = client.create_workflow_task(
                workflow_id=workflow_id,
                prompt=final_prompt,
                neg_prompt=neg_prompt,
                prompt_node_id=args.prompt_node_id,
                prompt_field=args.prompt_field,
                canvas=(
                    (args.canvas_node_id, preset["width"], preset["height"])
                    if args.canvas_node_id
                    else None
                ),
            )
        else:
            task_id = client.create_ai_app_task(
                webapp_id=args.webapp_id,
                prompt=final_prompt,
            )

        img_url = client.wait_for_output(task_id)
        print("正在下载图片至本地...")
        client.download_image(img_url, save_path)
        print(f"\n√ 生成成功！已落盘至: {save_path}")
        print(
            "提示: "
            + preset["post_hint"].format(
                save_path=save_path, w=preset["width"], h=preset["height"]
            )
        )

    except Exception as e:  # noqa: BLE001 —— CLI 顶层兜底，任何生图故障转成人话退出
        print(f"\n× 生图失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
