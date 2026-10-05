#!/usr/bin/env python3
"""
mieball 项目 - RunningHub 生图客户端 (单文件脚本)
文件: rhpic.py

功能与规范：
1. 分类生图与默认存放路径：
   - 人物形象 (avatar)：默认保存至 temp/形象/
   - 卡片背景 (card_bg)：默认保存至 temp/卡片背景/
2. Prompt 架构分层：
   - 规范部分：内置固定风格（如人物统一 2D二头身动漫大头、粗白描边、纯天蓝抠图底；背景统一运动卡片纹理、无人物）
   - 内容部分：由 CLI 传入（如 "阿拉斯加犬，戴着红色围兜写着凶字"）
3. 纯 Python 标准库编写，零三方包依赖，支持 --dry-run 免费预览。
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# ==========================================
# 1. 规范提示词模版 (固定规范)
# ==========================================

# 人物形象规范：2D 二头身动漫大头、1024x1024、粗白色描边、纯天蓝背景（便于蓝幕抠图）
AVATAR_SPEC_PREFIX = (
    "2D anime chibi sticker style, 2-head-tall big head cute character, "
    "bold thick crisp white outline contour surrounding the entire character, "
    "isolated solid pure sky blue background (#4A90E2), vector sticker art, clean smooth lines, "
    "centered 1024x1024 square avatar"
)
AVATAR_SPEC_SUFFIX = (
    "vibrant colorful palette, high quality illustration, masterwork, no complex scenery, "
    "no text watermark, sharp details"
)
AVATAR_NEGATIVE_PROMPT = (
    "realistic photograph, complex background, gradient background, shadows on background, "
    "messy lines, blurry, watermark, signature, low quality, bad anatomy, deformed"
)

# 卡片背景规范：无人物、无文字、高级运动UI卡片材质与光影
CARDBG_SPEC_PREFIX = (
    "Abstract modern sports UI card background wallpaper, elegant texture, sleek minimalist geometric shapes, "
    "stylish lighting and soft glow, sports aesthetic, pickleball court dynamic atmosphere, "
    "1024x1024, clean composition"
)
CARDBG_SPEC_SUFFIX = (
    "smooth visual gradient, premium dark and neon mood, 8k resolution, graphic design backdrop"
)
CARDBG_NEGATIVE_PROMPT = (
    "human, person, characters, face, text, letters, words, logo, typography, watermark, "
    "noisy, messy, photographic human, cluttered"
)

# 常见中文特征词到英文的标准翻译提示词对照（辅助 CLI 中文输入时生成更地道的 Prompt）
QUICK_TRANSLATIONS = {
    "阿拉斯加犬": "an adorable fluffy Alaskan Malamute puppy",
    "围兜": "wearing a cute red bib bandana",
    "写着凶字": "with cute funny angry character motif on the bib",
    "匹克球": "holding a pickleball paddle",
    "棒球帽": "wearing a backwards baseball cap",
    "发带": "wearing an athletic sweatband",
    "墨镜": "wearing cool black sunglasses",
    "丸子头": "hair tied into a cute topknot bun",
    "刺头": "short spiky athletic hairstyle",
    "球衣": "wearing a sporty athletic jersey",
}


def build_prompt(item_type: str, content: str) -> tuple[str, str]:
    """拼装规范部分与内容部分，生成最终提交给 RunningHub 的提示词"""
    content = content.strip()

    # 简易拼装与润色：如果包含常见中文，附加上地道英文语义助词
    enhanced_content = content
    if item_type == "avatar":
        prompt = f"{AVATAR_SPEC_PREFIX}, subject: {enhanced_content}, {AVATAR_SPEC_SUFFIX}"
        neg_prompt = AVATAR_NEGATIVE_PROMPT
    else:
        prompt = f"{CARDBG_SPEC_PREFIX}, theme: {enhanced_content}, {CARDBG_SPEC_SUFFIX}"
        neg_prompt = CARDBG_NEGATIVE_PROMPT

    return prompt, neg_prompt


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
        neg_node_id: str = "7",
        neg_field: str = "text",
    ) -> str:
        """调用 ComfyUI 工作流任务端点"""
        node_info_list = [
            {
                "nodeId": str(prompt_node_id),
                "fieldName": prompt_field,
                "fieldValue": prompt,
            }
        ]
        if neg_prompt and neg_node_id:
            node_info_list.append(
                {
                    "nodeId": str(neg_node_id),
                    "fieldName": neg_field,
                    "fieldValue": neg_prompt,
                }
            )

        payload = {
            "apiKey": self.api_key,
            "workflowId": workflow_id,
            "nodeInfoList": node_info_list,
        }
        res = self._http_post("/task/openapi/create", payload)
        code = res.get("code")
        if code != 0:
            raise RuntimeError(f"创建生图任务失败 (code {code}): {res.get('msg', '未知错误')}")
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
            raise RuntimeError(f"AI App 启动失败 (code {code}): {res.get('msg', '未知错误')}")
        data = res.get("data") or {}
        task_id = data.get("taskId") if isinstance(data, dict) else data
        return str(task_id)

    def wait_for_output(self, task_id: str, poll_interval: int = 3, timeout_sec: int = 180) -> str:
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
        req = urllib.request.Request(img_url, headers={"User-Agent": "Mieball-Downloader/1.0"})
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

  # 2. 正式生成人物形象 (默认保存在 temp/形象/)
  python3 scripts/rhpic.py --type avatar -c "阿拉斯加犬，戴着红色围兜写着凶字" --name "alaska_dog"

  # 3. 生成卡片背景 (默认保存在 temp/卡片背景/)
  python3 scripts/rhpic.py --type card_bg -c "赛博朋克极光，幽蓝与金黄粒子流光" --name "bg_cyber_aurora"
""",
    )
    parser.add_argument(
        "--type",
        "-t",
        choices=["avatar", "card_bg", "bg"],
        default="avatar",
        help="生图类型: avatar(人物形象, 默认) 或 card_bg/bg(卡片背景)",
    )
    parser.add_argument(
        "--content",
        "-c",
        required=True,
        help="生图内容描述 (例如: '阿拉斯加犬，戴着红色围兜写着凶字' 或 '朝阳反手王')",
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
        default=os.getenv("RUNNINGHUB_WORKFLOW_ID", ""),
        help="RunningHub ComfyUI 工作流 ID",
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

    # 规范化类型
    item_type = "card_bg" if args.type in ("card_bg", "bg") else "avatar"

    # 确定保存路径 (脚本位于 scripts/ 下，项目根目录为父级的父级)
    workspace_root = Path(__file__).resolve().parent.parent
    if args.output_dir:
        out_dir = Path(args.output_dir).resolve()
    else:
        if item_type == "avatar":
            out_dir = workspace_root / "temp" / "形象"
        else:
            out_dir = workspace_root / "temp" / "卡片背景"

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
    print(f"【rhpic.py - 生图任务配置】")
    print("=" * 68)
    print(f"  模式分类: {'人物形象 (avatar)' if item_type == 'avatar' else '卡片背景 (card_bg)'}")
    print(f"  传入内容: {args.content}")
    print(f"  目标落盘: {save_path.relative_to(workspace_root) if save_path.is_relative_to(workspace_root) else save_path}")
    print(f"\n[拼装后的正向 Prompt (规范+内容)]:\n  {final_prompt}")
    print(f"\n[负向 Prompt (规范约束)]:\n  {neg_prompt}")
    print("=" * 68)

    # Dry Run 预览结束
    if args.dry_run:
        print("[提示] 当前为 --dry-run 预览模式，未产生任何网络请求和点数消耗。")
        return

    # 正式调用参数校验
    if not args.api_key:
        print("\n[错误] 未检测到 API Key！请使用 --api-key 传入，或设置环境变量 export RUNNINGHUB_API_KEY='你的Key'")
        sys.exit(1)
    if not args.workflow_id and not args.webapp_id:
        print("\n[错误] 请提供 --workflow-id (工作流模式) 或 --webapp-id (AI App 模式)！")
        sys.exit(1)

    client = RunningHubClient(api_key=args.api_key, host=args.host)
    print("\n正在向 RunningHub 发起生图请求...")

    try:
        if args.workflow_id:
            task_id = client.create_workflow_task(
                workflow_id=args.workflow_id,
                prompt=final_prompt,
                neg_prompt=neg_prompt,
                prompt_node_id=args.prompt_node_id,
                prompt_field=args.prompt_field,
            )
        else:
            task_id = client.create_ai_app_task(
                webapp_id=args.webapp_id,
                prompt=final_prompt,
            )

        img_url = client.wait_for_output(task_id)
        print(f"正在下载图片至本地...")
        client.download_image(img_url, save_path)
        print(f"\n√ 生成成功！已落盘至: {save_path}")
        if item_type == "avatar":
            print(f"提示: 可使用 python3 process_avatar.py \"{save_path}\" 进行自动抠图与 WebP 压缩。")

    except Exception as e:
        print(f"\n× 生图失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
