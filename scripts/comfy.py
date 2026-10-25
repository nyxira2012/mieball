#!/usr/bin/env python3
"""ComfyUI 远程生图工具（单文件自包含：工程参数内置，提示词内容全由调用方传入）。

分工纪律：
    脚本只管工程——画布尺寸、蓝幕底色契约、导出缩放、防覆盖版本号、命名与
    朝向纪律。画风锁/构图约束/动作描述等一切内容词由调用方（人或 AI）在
    命令行 position prompt 里完整传入——本管线 cfg=1（turbo 两段采样，
    负向接 ConditioningZeroOut），负向提示词通道无效，一切约束只能写进正向，
    故不设 negative 参数。

用法示例：
    # mieball 槽位（天蓝底+白描边贴纸头像直出 PNG，抠图走 gen_avatars.py；
    # 卡背 1536x640 居中生成，出图自动裁切对位 (68,37) + 规格闸门 + 压 WebP）：
    python scripts/comfy.py -p mb_avatar "阿拉斯加犬，戴红色围兜，神气叉腰"
    python scripts/comfy.py -p mb_cardbg "霓虹夜场，金黄与青色光斑"

    # 演练：只看装配后的正向 Prompt 与工程规格，不请求服务器
    python scripts/comfy.py -p mb_cardbg "……" --dry-run

    # 查看槽位工程参数清单
    python scripts/comfy.py --list-presets
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

# 确保本目录模块（process_asset）直接可导入
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 默认服务器地址，可用环境变量 COMFY_SERVER 或 --server 覆盖。
# 走虚拟局域网 utun5（10.144.144.x 网段，.1/.2 为同一台 Windows 机器，取 .1）
DEFAULT_SERVER = os.getenv("COMFY_SERVER", "http://10.144.144.1:8188")

# ==============================================================================
# 内置 ComfyUI API 工作流模板（Turbo 两段采样 + Qwen CLIP 文本编码 + VAE 解码；
# 两段共用同一条 12 步时间轴：1pass er_sde 0-8步保留残差 ->
# 2pass dpmpp_2m_sde 8-999步细化。步数预算是画质旋钮：8步总预算出图快但
# 边缘发虚，12 步（8+4）在 turbo 甜区内明显更锐。2pass 必须 add_noise=disable
# 直接接力残差，若再注噪等于双倍噪声进细化段，出图破碎）
# ==============================================================================
DEFAULT_WORKFLOW_TEMPLATE: dict[str, Any] = json.loads(r"""
{
  "599": {
    "inputs": {
      "add_noise": "enable",
      "noise_seed": ["851", 0],
      "steps": 12,
      "cfg": 1.0,
      "sampler_name": "er_sde",
      "scheduler": "simple",
      "start_at_step": 0,
      "end_at_step": 8,
      "return_with_leftover_noise": "enable",
      "model": ["859", 0],
      "positive": ["627", 0],
      "negative": ["763", 0],
      "latent_image": ["698", 0]
    },
    "class_type": "KSamplerAdvanced",
    "_meta": {"title": "1pass"}
  },
  "627": {
    "inputs": {
      "text": "2d日式动漫，1girl 25yo，3/4身立绘，红色军装白色短裙，在汇报工作，面朝右边，蓝色背景",
      "clip": ["860:755", 0]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {"title": "CLIP文本编码"}
  },
  "698": {
    "inputs": {"width": 800, "height": 1200, "batch_size": 1},
    "class_type": "EmptyLatentImage",
    "_meta": {"title": "Empty Latent Image (Base Dimensions) 初始大小"}
  },
  "763": {
    "inputs": {"conditioning": ["627", 0]},
    "class_type": "ConditioningZeroOut",
    "_meta": {"title": "条件零化"}
  },
  "829": {
    "inputs": {"samples": ["599", 0], "vae": ["860:858", 0]},
    "class_type": "VAEDecode",
    "_meta": {"title": "VAE解码 (1pass)"}
  },
  "851": {
    "inputs": {"seed": 638208442578987},
    "class_type": "SeedNode",
    "_meta": {"title": "Seed 1ST"}
  },
  "859": {
    "inputs": {
      "lora_name": "krea2-Cc-天魔-身材.safetensors",
      "strength_model": 0.0,
      "model": ["860:761", 0]
    },
    "class_type": "LoraLoaderModelOnly",
    "_meta": {"title": "LoRA加载器（仅模型）"}
  },
  "868": {
    "inputs": {
      "add_noise": "disable",
      "noise_seed": ["851", 0],
      "steps": 12,
      "cfg": 1.0,
      "sampler_name": "dpmpp_2m_sde",
      "scheduler": "sgm_uniform",
      "start_at_step": 8,
      "end_at_step": 999,
      "return_with_leftover_noise": "disable",
      "model": ["860:761", 0],
      "positive": ["627", 0],
      "negative": ["763", 0],
      "latent_image": ["599", 0]
    },
    "class_type": "KSamplerAdvanced",
    "_meta": {"title": "2pass"}
  },
  "869": {
    "inputs": {"samples": ["868", 0], "vae": ["860:858", 0]},
    "class_type": "VAEDecode",
    "_meta": {"title": "VAE解码 (2pass)"}
  },
  "871": {
    "inputs": {"anything": ["627", 0]},
    "class_type": "Anything Everywhere",
    "_meta": {"title": "text"}
  },
  "872": {
    "inputs": {
      "anything": ["860:761", 0],
      "anything11": ["860:755", 0],
      "anything12": ["860:858", 0]
    },
    "class_type": "Anything Everywhere",
    "_meta": {"title": "Anything Everywhere"}
  },
  "860:755": {
    "inputs": {"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"},
    "class_type": "CLIPLoader",
    "_meta": {"title": "加载CLIP"}
  },
  "860:858": {
    "inputs": {"vae_name": "qwen_image_vae.safetensors"},
    "class_type": "VAELoader",
    "_meta": {"title": "加载VAE"}
  },
  "860:761": {
    "inputs": {"unet_name": "museByStableYogi_v25INT8Turbo.safetensors", "weight_dtype": "default"},
    "class_type": "UNETLoader",
    "_meta": {"title": "UNet加载器"}
  }
}
""")


# 抠图用背景色短语：追加到提示词末尾——背景短语与后处理抠图是硬契约，
# 选了色就必须让模型画出对应纯色底
BACKGROUND_PRESETS = {
    "none": "",
    # mieball 头像专用：与 gen_avatars.py 角点采样泛洪抠图互为硬契约
    # （天蓝 #4A90E2 期望底色，白描边阻断泛洪侵入主体内部）；
    # 改色需 grep #4A90E2 同步全部出现处（gen_avatars.py 抠图与 picfit.html 页内同款算法）
    "sky_blue": "纯天蓝色背景 (#4A90E2)，背景无渐变无阴影，干净单一天蓝色背景，背景完全纯色空白无杂物",
}

# 功能性朝向短语：默认正面（贴纸头像/卡背都不需要侧向），槽位可自带或显式覆盖
ORIENTATION_PRESETS = {
    "right": "面朝右边，身体与视线朝向右方（facing right, looking right）",
    "left": "面朝左边，身体与视线朝向左方（facing left, looking left）",
    "front": "正面正向视角（facing viewer, frontal view）",
    "none": "",
}
DEFAULT_ORIENTATION = "front"

# 轮询间隔与单次生成超时（秒）
POLL_INTERVAL = 2.0
DEFAULT_TIMEOUT = 600.0


# ==============================================================================
# 槽位工程参数（不含任何画风/构图提示词——内容词全由调用方传入；
# 措辞基准模板见模块 docstring 用法示例）
# ==============================================================================

PRESETS: dict[str, dict[str, Any]] = {
    # ---- mieball 槽位（蓝幕抠图契约、卡背文字排版硬约束；本机直连 ComfyUI）----
    "mb_avatar": {
        "title": "mieball 球员头像（半身胸像贴纸）",
        "width": 1024,
        "height": 1024,
        "background": "sky_blue",
        "orientation": "front",
        "spec_prefix": (
            "2D动漫贴纸风，Q版可爱角色半身胸像贴纸（chibi bust sticker），"
            "整个半身胸像外围包着粗而干净的完整白描边，居中完整构图，"
            "四周留有安全边距（centered with margin, floating in solid sky blue background），"
            "干净流畅的线条，正面正向视角（facing viewer, frontal view），姿态端正自然无外展大道具，"
            "底部自然圆润收边不贴边，画面中不出现任何文字、字母、数字与标志"
        ),
        "out_dir": "temp/形象",
        "file_prefix": "avatar",
        "out_ext": ".png",
        # 抠图/居中/512 WebP 全走 gen_avatars.py 蓝幕流水线，
        # 本槽直出无损 PNG（白描边细节是抠图保护层，有损压缩会伤边缘）
        "skip_optimize": True,
    },
    "mb_cardbg": {
        "title": "mieball 战力卡背横幅",
        # 单图交付：生成只管「画面好看、一个主体、无复制无接缝」，主体一律
        # 画在中间（模型只听话到这里）；落位 (68,37) 与交付尺寸是跨脚本契约，
        # 唯一真源在 process_asset.CARD_CORE/CARD_SIZE（为何是 68/37 见其注），
        # 出图后的裁切对位与规格闸门都从那边读缺省，这里只负责画布开对尺寸。
        "width": 1536,
        "height": 640,
        "background": "none",
        "is_background": True,
        "spec_prefix": (
            "现代运动风高品质壁纸，唯美自然景深，精致材质质感，"
            "居中对称构图，主要视觉焦点位于画面正中央（centered composition, subject perfectly centered in frame），构图均衡饱满，"
            "柔和光影，无刺眼直射强光无光斑（no harsh light beams, no lens flare），"
            "超宽横幅构图，画面纯净无任何文字内容（absolutely no text, no letters, no numbers, no calligraphy, no signage, no watermark, no logos, no characters），"
            "画面构图完整大气，无竖向接缝或拼接痕迹"
        ),
        "out_dir": "temp/卡片背景",
        "file_prefix": "cardbg",
        "out_ext": ".webp",
        "optimize_quality": 80,
        # 出图后的两步：先裁切对位（把居中主体搬到 CARD_CORE），再过规格闸门；
        # 闸门不过抛 CardbgQcError 并落 *_rejected，不「只警告、照样保存」。
        "reframe": True,
        # 实景卡背关闭盲目修缝，避免把球网和树纹误判为接缝涂抹
        "seam_repair": False,
        # 左侧 UI 文字安全平滑暗色过渡（UI Scrim）：生图只管画自然实景，暗部由算法确定性压暗
        "apply_scrim": True,
        "cardbg_qc": True,
    },
}


def resolve_plan(
    prompt: str,
    preset_name: str | None,
    width: int | None,
    height: int | None,
    background: str | None,
    orientation: str | None,
) -> dict[str, Any]:
    """预设 + 显式覆盖 → 一次生成的完整工程方案。

    dry-run 与 generate 共用本函数装配，保证演练所见即实出所提交：
    画布尺寸/背景模式取「显式参数 > 预设 > 通用缺省」，朝向取
    「显式参数 > 槽位预设 > 通用缺省（正面）」。
    """
    preset = (PRESETS.get(preset_name) if preset_name else None) or {}
    w = width or preset.get("width", 800)
    h = height or preset.get("height", 1200)
    bg = background or preset.get("background", "none")
    ori = orientation or preset.get("orientation", DEFAULT_ORIENTATION)
    final_prompt = assemble_prompt(
        prompt,
        background=bg,
        orientation=ori,
        is_background=bool(preset.get("is_background")),
        spec_prefix=preset.get("spec_prefix", ""),
    )
    return {
        "preset": preset,
        "width": w,
        "height": h,
        "prompt": final_prompt,
    }


def scale_note(width: int, height: int, max_side: int | None) -> str:
    """导出缩放说明文案：生图尺寸（必要时附默认导出尺寸）。"""
    if max_side and max(width, height) > max_side:
        scale = max_side / max(width, height)
        return f"{width}x{height} -> 默认导出 {round(width * scale)}x{round(height * scale)}"
    return f"{width}x{height}"


def assemble_prompt(
    user_prompt: str,
    background: str = "none",
    orientation: str = DEFAULT_ORIENTATION,
    is_background: bool = False,
    spec_prefix: str = "",
) -> str:
    """槽位规范词 + 内容词 + 朝向短语 + 背景短语 → 最终正向 Prompt（唯一有效通道）。

    纯背景图（is_background）不追加朝向词；背景短语与后处理抠图互为硬契约，
    二者必须同进同出。spec_prefix 是槽位自带的固定画风/构图规范，排在内容词之前。
    """
    parts: list[str] = []
    if spec_prefix:
        parts.append(spec_prefix.strip("，,"))
    parts.append(user_prompt.strip("，,"))
    ori_mode = "none" if is_background else (orientation or "none")
    ori_phrase = ORIENTATION_PRESETS.get(ori_mode, "")
    if ori_phrase:
        parts.append(ori_phrase.strip("，,"))
    bg_phrase = BACKGROUND_PRESETS.get(background, "")
    if bg_phrase:
        parts.append(bg_phrase.strip("，,"))
    return "，".join(p for p in parts if p)


# ==============================================================================
# ComfyUI 客户端与工作流准备
# ==============================================================================


class ComfyUIClient:
    """ComfyUI HTTP API 客户端。"""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"User-Agent": "mieball-artgen/1.0"}

    def submit(self, workflow: dict[str, Any]) -> str:
        """提交工作流到执行队列。"""
        payload = json.dumps(
            {"prompt": workflow, "client_id": str(uuid.uuid4())}
        ).encode("utf-8")
        req_headers = {"Content-Type": "application/json", **self.headers}
        req = urllib.request.Request(
            f"{self.base_url}/prompt",
            data=payload,
            headers=req_headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)["prompt_id"]
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"提交工作流失败（HTTP {exc.code}）：{detail}") from exc

    def wait(self, prompt_id: str, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """阻塞等待指定任务执行完成。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with urllib.request.urlopen(
                f"{self.base_url}/history/{prompt_id}", timeout=30
            ) as resp:
                history: dict[str, dict[str, Any]] = json.load(resp)
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(
                        f"工作流执行失败：{json.dumps(status.get('messages'), ensure_ascii=False)}"
                    )
                return entry["outputs"]
            time.sleep(POLL_INTERVAL)
        raise TimeoutError(f"等待 {timeout}s 后任务仍未完成：{prompt_id}")

    def download(self, image_ref: dict[str, str]) -> bytes:
        """从服务器 /view 端点下载生成图片字节流。"""
        query = urllib.parse.urlencode(image_ref)
        with urllib.request.urlopen(
            f"{self.base_url}/view?{query}", timeout=60
        ) as resp:
            return resp.read()


def prepare_workflow(
    template: dict[str, dict[str, object]],
    prompt: str,
    seed: int,
    width: int,
    height: int,
    filename_prefix: str,
    two_pass: bool = True,
) -> dict[str, dict[str, Any]]:
    """基于模板生成待提交的工作流副本，支持 1pass / 2pass 动态切换。

    种子只经 SeedNode 一处注入（1pass/2pass 的 noise_seed 均引用它）；
    产物落盘由脚本端统一追加的 __save__ 节点承担，模板内不保存存档节点。
    模板本身即 2pass 事实源，two_pass=True 时一字不改；仅单 pass 才改写。
    """
    workflow: dict[str, dict[str, Any]] = copy.deepcopy(template)

    # 采样模式：2pass 接力（模板原样，1pass 0-8 步留残差 -> 2pass 8-999 步细化）
    # vs 1pass 全程跑满时间轴直出（清掉 2pass 节点；end 必须取模板总步数，
    # 写死数字会在时间轴加长后变成「中途截断」出噪图）
    if two_pass:
        save_source: list[object] = ["869", 0]
    else:
        workflow.pop("868", None)
        workflow.pop("869", None)
        save_source = ["829", 0]
        inputs_599 = workflow["599"]["inputs"]
        inputs_599["end_at_step"] = int(inputs_599["steps"])
        inputs_599["return_with_leftover_noise"] = "disable"

    for workflow_node in workflow.values():
        inputs = workflow_node.get("inputs", {})
        class_type = str(workflow_node.get("class_type", ""))
        if class_type == "CLIPTextEncode" and "text" in inputs:
            inputs["text"] = prompt
        elif class_type == "EmptyLatentImage":
            inputs["width"] = width
            inputs["height"] = height
        elif class_type == "SeedNode":
            inputs["seed"] = seed

    workflow["__save__"] = {
        "class_type": "SaveImage",
        "inputs": {"images": save_source, "filename_prefix": filename_prefix},
    }
    return workflow


# ==============================================================================
# 后处理与落盘
# ==============================================================================


def postprocess_and_save(
    raw_bytes: bytes,
    output_path: Path,
    preset: dict[str, Any] | None = None,
    skip_postprocess: bool = False,
    max_side: int | None = None,
    reject_tag: str = "",
) -> Path:
    """处理产物并在本地落盘。若命中预设则自动执行裁切对位/接缝修复/规格闸门/压缩。

    reject_tag 拼进闸门拦截存证的文件名：批量换种子重试时同一目标路径会被
    反复拦截，不带标记后一粒种子会覆盖前一粒的存证，复查时对不上号。
    """
    # 裁切/压缩算法统一在 process_asset（numpy/scipy 随之引入）
    import process_asset
    from PIL import Image

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(BytesIO(raw_bytes))

    if preset and not skip_postprocess:
        # 1. 卡背裁切对位（mb_cardbg）：生成时主体在中间，这里按量测质心裁切，
        #    把核心搬到 CARD_CORE——一张图才能同时伺候行卡与扁平卡。
        #    裁切是确定性工序，失败直接上抛：吞掉只会让闸门以「落点偏了」
        #    报假因，批量侧还照单换种子重烧 GPU。
        if preset.get("reframe"):
            image, info = process_asset.reframe_cardbg(image)
            # 报表口径与 process_asset CLI 的 --reframe 同款：量测焦点要人工登记进册子
            print(
                f"[{preset['title']}] 裁切对位 · 主体({info['fx']:.2f},{info['fy']:.2f})"
                f" → ({process_asset.CARD_CORE[0]:.2f},{process_asset.CARD_CORE[1]:.2f})"
                f" · 裁切 {info['crop'][2]:.0f}x{info['crop'][3]:.0f}"
                f" · 缩放 {info['zoom']:.2f}x"
            )

        # 2. 接缝修复：整贯穿的竖缝用左右两缘窄带过渡（主体不动，见 repair_seams）
        if preset.get("seam_repair"):
            try:
                image, seams = process_asset.repair_seams(image)
                if seams:
                    print(
                        f"[{preset['title']}] 已修接缝 "
                        + "、".join(f"x={a}-{b}(阶{step:.0f})" for a, b, step in seams)
                    )
            except Exception as e:  # noqa: BLE001 —— 修缝尽力而为，真缝留给规格闸门拦
                print(f"[警告] 接缝修复跳过: {e}", file=sys.stderr)

        # 3. UI 安全暗色过渡（mb_cardbg）：生图只管画好看的自然实景/场景，
        #    左侧文字安全暗部（left <= 30）由算法以平滑 S 曲线确定性压暗，无需模型生硬画黑洞
        if preset.get("apply_scrim"):
            try:
                image = process_asset.apply_cardbg_scrim(image)
                print(
                    f"[{preset['title']}] 已应用左侧 UI 文字安全平滑暗色过渡 (UI Scrim)"
                )
            except Exception as e:  # noqa: BLE001
                print(f"[警告] UI 暗色过渡跳过: {e}", file=sys.stderr)

        # 4. 卡背规格闸门：核心落点/右缘干净/接缝/亮度，不合格抛 CardbgQcError
        #    不落盘；另存一张 *_rejected 供复查（硬闸的意义是别让次品混进素材目录）
        if preset.get("cardbg_qc"):
            qc = process_asset.cardbg_spec_qc(image)
            process_asset.print_qc_report(preset["title"], qc)
            if not qc["ok"]:
                tag = f"_{reject_tag}" if reject_tag else ""
                rejected = output_path.with_stem(f"{output_path.stem}{tag}_rejected")
                rejected.write_bytes(process_asset.encode_webp(image, 82))
                raise process_asset.CardbgQcError(
                    "卡背规格质检未通过（已存 "
                    + rejected.name
                    + " 供复查）: "
                    + "; ".join(qc["problems"])
                )

        # 5. 自动调色板压缩优化与等比缩放（skip_optimize 槽位跳过：
        #    mieball 头像直出无损 PNG，WebP 压缩留给 gen_avatars.py 流水线）
        if not preset.get("skip_optimize"):
            try:
                scheme, payload = process_asset.optimize_image_bytes(
                    image,
                    colors=preset.get("optimize_colors"),
                    quality=preset.get("optimize_quality", 80),
                    max_side=max_side,
                )
                output_path.write_bytes(payload)
                out_img = Image.open(BytesIO(payload))
                dim_str = f"{out_img.width}x{out_img.height}"
                print(
                    f"[{preset['title']}] 调色板优化与缩放完成 ({scheme}, {dim_str}): {len(raw_bytes) / 1024:.0f}KB -> {len(payload) / 1024:.0f}KB"
                )
                return output_path
            except Exception as e:  # noqa: BLE001 —— 压缩尽力而为，失败回退原样保存
                print(f"[警告] 调色板优化跳过，直接保存: {e}", file=sys.stderr)

    # 普通保存流程：等比缩放与 WebP 编码统一走 process_asset（与调色板优化同口径）
    if max_side is not None:
        image = process_asset.resize_to_max_side(image, max_side)

    suffix = output_path.suffix.lower()
    if suffix == ".webp":
        output_path.write_bytes(process_asset.encode_webp(image, 80))
    elif suffix in (".jpg", ".jpeg"):
        image.convert("RGB").save(output_path, "JPEG", quality=92)
    elif max_side is not None:
        image.save(output_path)
    else:
        output_path.write_bytes(raw_bytes)
    return output_path


def default_output_dir(preset: dict[str, Any]) -> Path:
    """槽位落盘目录：锚定项目根（scripts/ 的父级），与 gen_avatars.py 的生图暂存目录同根。

    本 CLI 与批量调用方都从这里取目录，目录口径只认这一处。
    """
    return Path(__file__).resolve().parent.parent / preset["out_dir"]


def default_output_path(preset: dict[str, Any], tag: str, version: int = 1) -> Path:
    """缺省产物全路径，`{file_prefix}-{tag}-v{version}{out_ext}` 命名规范唯一装配处。

    单发生图传随机数 tag，批量脚本传素材号 tag——目录/前缀/后缀/版本号的拼装
    只认这一处，resolve_output_path 的防覆盖递增也按同一规范解析。
    """
    return default_output_dir(preset) / (
        f"{preset['file_prefix']}-{tag}-v{version}{preset['out_ext']}"
    )


def resolve_output_path(target_path: Path) -> Path:
    """若目标文件已存在则自动递增版本号（如 stem-v2.webp, stem-v3.webp），避免覆盖既有资产。

    命名规范见 default_output_path：[前缀]-[标识]-v[版本号]；历史遗留的 _N 尾巴也认。
    """
    if not target_path.exists():
        return target_path
    stem = target_path.stem
    suffix = target_path.suffix
    parent = target_path.parent

    # 检查当前文件名是否已包含版本号后缀，例如 -v1, -v2 或历史遗留 _1, _2
    m = re.search(r"^(.*?)(?:-v|_)(\d+)$", stem)
    if m:
        base_stem = m.group(1)
        counter = int(m.group(2)) + 1
    else:
        base_stem = stem
        counter = 2  # 原图视为第1版，下一版本为 -v2

    while True:
        candidate = parent / f"{base_stem}-v{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def generate(
    prompt: str,
    output_path: Path,
    preset_name: str | None = None,
    server: str = DEFAULT_SERVER,
    seed: int | None = None,
    width: int | None = None,
    height: int | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    background: str | None = None,
    orientation: str | None = None,
    skip_postprocess: bool = False,
    export_max_side: int | None = None,
    two_pass: bool = True,
    overwrite: bool = False,
) -> Path:
    """核心生图 API。prompt 为完整内容词（画风+构图+主体），工程参数取预设。"""
    actual_output_path = output_path if overwrite else resolve_output_path(output_path)
    if actual_output_path != output_path:
        print(
            f"[防覆盖保护] 目标文件 {output_path.name} 已存在，自动重命名并保存为 -> {actual_output_path.name}"
        )

    actual_seed = seed if seed is not None else random.randint(0, 2**48)
    plan = resolve_plan(prompt, preset_name, width, height, background, orientation)
    preset = plan["preset"]
    actual_width, actual_height = plan["width"], plan["height"]
    final_prompt = plan["prompt"]

    # 工作流模板：工程参数内置单一份，避免外部 JSON 漂移
    workflow = prepare_workflow(
        DEFAULT_WORKFLOW_TEMPLATE,
        prompt=final_prompt,
        seed=actual_seed,
        width=actual_width,
        height=actual_height,
        filename_prefix=actual_output_path.stem,
        two_pass=two_pass,
    )

    client = ComfyUIClient(server)
    tag = f"[{preset['title']}] " if preset else ""
    pass_tag = " [2次采样]" if two_pass else " [单次采样]"
    print(
        f"{tag}提交 ComfyUI 任务 · seed={actual_seed} · {actual_width}x{actual_height}{pass_tag}..."
    )
    prompt_id = client.submit(workflow)
    print(f"{tag}等待生成 (ID: {prompt_id})...")
    outputs = client.wait(prompt_id, timeout=timeout)

    refs = [
        ref
        for node_out in outputs.values()
        for ref in node_out.get("images", [])  # type: ignore[union-attr]
        if ref.get("type") == "output"
    ]
    if not refs:
        raise RuntimeError("ComfyUI 执行完毕但未返回任何图片产物")

    raw_bytes = client.download(dict(refs[0]))
    return postprocess_and_save(
        raw_bytes,
        actual_output_path,
        preset=preset,
        skip_postprocess=skip_postprocess,
        max_side=export_max_side,
        reject_tag=str(actual_seed),
    )


# ==============================================================================
# CLI 入口
# ==============================================================================


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """命令行参数解析。"""
    parser = argparse.ArgumentParser(
        description="mieball 生图工具：工程参数（尺寸/底色/导出/命名/朝向）内置，"
        "提示词内容（画风+构图+主体）由调用方完整传入——措辞基准模板见模块 docstring 用法示例",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="",
        help="完整内容词（画风+构图+主体）；脚本自动追加朝向与背景短语",
    )
    parser.add_argument(
        "-p",
        "--preset",
        choices=list(PRESETS.keys()),
        default=None,
        help="槽位工程参数（尺寸/抠底/导出缩放/命名）",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="输出文件路径（支持 .png / .jpg / .webp）",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="若目标文件已存在，允许直接覆盖（默认不覆盖，自动递增版本号如 -v2, -v3 严格保护已有资产）",
    )
    parser.add_argument("--server", default=DEFAULT_SERVER, help="ComfyUI 服务器地址")
    parser.add_argument("--seed", type=int, default=None, help="随机种子，缺省时随机")
    parser.add_argument(
        "--width", type=int, default=None, help="画布宽（缺省从预设读取或 800）"
    )
    parser.add_argument(
        "--height", type=int, default=None, help="画布高（缺省从预设读取或 1200）"
    )
    parser.add_argument(
        "--export-max-side",
        "--max-side",
        type=int,
        default=None,
        dest="export_max_side",
        help="导出缩放：最长边像素上限（等比缩小），缺省不缩放",
    )
    parser.add_argument(
        "--orientation",
        choices=sorted(ORIENTATION_PRESETS.keys()),
        default=None,
        help="主体朝向短语：缺省 front（本工程出图以正面为主）；槽位可自带朝向",
    )
    parser.add_argument(
        "--single-pass",
        "--no-two-pass",
        dest="two_pass",
        action="store_false",
        help="仅执行单次采样（全程跑满时间轴直出，跳过2pass细化）；默认 2pass 接力细化",
    )
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, help="单次生成超时（秒）"
    )
    parser.add_argument(
        "--background",
        choices=sorted(BACKGROUND_PRESETS),
        default=None,
        help="覆盖背景色预设（sky_blue 与 gen_avatars.py 抠图为硬契约）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="演练模式：仅打印装配后的提示词与规格，不请求服务器",
    )
    parser.add_argument(
        "--list-presets", action="store_true", help="列出所有槽位工程参数"
    )
    parser.add_argument(
        "--skip-postprocess", action="store_true", help="跳过裁切对位与调色板优化"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """脚本入口。"""
    args = parse_args(argv)

    if args.list_presets:
        print("\n" + "=" * 76)
        print("mieball 槽位工程参数清单（提示词内容自备，措辞基准见模块 docstring）:")
        print("=" * 76)
        for key, p in PRESETS.items():
            print(f"• {key:<14} | {p['title']} ({p['width']}x{p['height']})")
        print()
        return 0

    if not args.prompt and not args.dry_run:
        print("错误: 请提供提示词 prompt。输入 -h 查看帮助。")
        return 1

    if args.dry_run:
        plan = resolve_plan(
            args.prompt,
            args.preset,
            args.width,
            args.height,
            args.background,
            args.orientation,
        )
        preset = plan["preset"]
        size_info = scale_note(plan["width"], plan["height"], args.export_max_side)
        sampling_info = (
            "2次采样 (1pass er_sde 0-8步 -> 2pass dpmpp_2m_sde 8-999步)"
            if args.two_pass
            else "单次采样 (1pass 全时间轴直出)"
        )
        print("=" * 72)
        print(
            f"【DRY-RUN】{preset['title'] if preset else '无预设'} ({args.preset or '-'}) · {size_info} · {sampling_info}"
        )
        print("-" * 72)
        print(
            f"【装配后正向 Prompt（唯一有效通道，负向在本管线无效）】:\n  {plan['prompt']}\n"
        )
        print("=" * 72)
        return 0

    if args.output is None:
        preset = PRESETS.get(args.preset) if args.preset else None
        if preset and preset.get("out_dir"):
            args.output = default_output_path(
                preset, tag=str(random.randint(1000, 9999))
            )
        else:
            print("错误: 未用 -p 预设时必须用 -o 指定输出路径。输入 -h 查看帮助。")
            return 1

    path = generate(
        prompt=args.prompt,
        output_path=args.output,
        preset_name=args.preset,
        server=args.server,
        seed=args.seed,
        width=args.width,
        height=args.height,
        timeout=args.timeout,
        background=args.background,
        orientation=args.orientation,
        skip_postprocess=args.skip_postprocess,
        export_max_side=args.export_max_side,
        two_pass=args.two_pass,
        overwrite=args.overwrite,
    )
    print(f"产物已落盘：{path}（{path.stat().st_size / 1024:.0f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
