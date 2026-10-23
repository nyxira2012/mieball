#!/usr/bin/env python3
"""mieball 美术资产二次处理工具（卡背裁切对位 + 规格闸门 + WebP 压缩）。

本模块三部分：
    1. 【卡背裁切对位】(reframe)：生图只保证「一个主体、画在中间」，把主体
       搬到正确位置不指望模型——量测质心后裁切落位 (68,37)，缩回 1536×640；
    2. 【卡背规格闸门】(qc)：核心落点/右缘干净/亮度/竖缝四类硬项，不合格
       由调用方抛错拒绝落盘，不许次品混进素材目录；
    3. 【通用压缩】(optimize)：WebP method=6 深度编码，量化版与直转版择优。

生图侧 comfy.py 的 mb_cardbg 预设出图后自动走 1→2→3 全链；本命令行用于
存量图复验、单独裁切与体积优化。

用法示例：
    # 1. 复验存量卡背（缺省模式）：跑规格闸门只报不裁，不过退出码 1
    python scripts/process_asset.py temp/卡片背景/cardbg-1660-v2.webp

    # 2. 对「居中生成」的原图做裁切对位：另存 *_reframed.webp 并附质检报告
    python scripts/process_asset.py --reframe temp/卡片背景/居中原图.webp

    # 3. 通用体积优化（量化版与直转版择优，支持批量）
    python scripts/process_asset.py --optimize --quality 52 --max-side 960 img.webp
"""

from __future__ import annotations

import argparse
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

# ==============================================================================
# 模块一：WebP 编码与通用压缩
# ==============================================================================


def encode_webp(image: Image.Image, quality: int) -> bytes:
    """以指定质量将图片编码为 WebP 字节流（method=6 深度搜索最佳压缩）。

    本项目生图管线统一从这里出 WebP，保证同一 quality 产出体积口径一致
    （gen_avatars.py 抠图流水线自带同参编码，是唯一例外）。
    """
    buf = BytesIO()
    image.save(buf, "WEBP", quality=quality, method=6)
    return buf.getvalue()


def resize_to_max_side(image: Image.Image, max_side: int) -> Image.Image:
    """最长边超限时等比缩小（LANCZOS），未超限原样返回——导出缩放唯一算式。"""
    if max(image.size) <= max_side:
        return image
    scale = max_side / max(image.size)
    return image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )


def optimize_image_bytes(
    image: Image.Image,
    colors: int | None = 128,
    quality: int = 90,
    max_side: int | None = None,
) -> tuple[str, bytes]:
    """在内存中进行 WebP 调色板优化与编码。"""
    has_alpha = image.mode in ("RGBA", "LA") or "transparency" in image.info
    converted = image.convert("RGBA" if has_alpha else "RGB")

    if max_side is not None:
        converted = resize_to_max_side(converted, max_side)

    candidates: list[tuple[str, bytes]] = [
        ("webp-direct", encode_webp(converted, quality)),
    ]
    if colors is not None and colors > 0:
        if has_alpha:
            quantized = converted.quantize(colors=colors, method=Image.FASTOCTREE)
        else:
            quantized = converted.quantize(colors=colors, method=Image.MEDIANCUT)
        candidates.append(
            ("quantized", encode_webp(quantized.convert(converted.mode), quality))
        )

    return min(candidates, key=lambda item: len(item[1]))


# ==============================================================================
# 模块二：卡背裁切对位（居中生成 → 落位 68,37）
# ==============================================================================

# 卡背单图规格：核心落点与交付尺寸。
# 为什么是 (68,37)：13 个卡位实测，这个点同时避开行卡的文字带与扁平卡的
# 名字/分数区；主体由 reframe 从「居中生成」搬到此处，交付仍是一张图。
CARD_CORE = (0.68, 0.37)
CARD_SIZE = (1536, 640)


class CardbgQcError(RuntimeError):
    """卡背规格闸门拒绝的专用异常：批量出图侧只对它换种子重出，其余错误照常上抛。"""


def card_subject_center(image: Image.Image) -> tuple[float, float] | None:
    """估主体核心：中央 64%×76% 内「局部对比×亮度」最高 1% 的加权质心。

    只搜中央是因为生成时主体被要求画在中间；边缘的光锥、右缘复制体再亮
    也不参与——否则质心会被光斑/复制体拽走（夜场登记 75 打空就是这么来的）。
    返回归一化坐标，找不到主体返回 None。
    """
    g = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    h, w = g.shape
    hi = np.clip(g - ndimage.gaussian_filter(g, 10), 0, None)
    sal = hi * g
    region = np.zeros_like(g, dtype=bool)
    region[int(h * 0.12) : int(h * 0.88), int(w * 0.18) : int(w * 0.82)] = True
    if not region.any() or float(sal[region].max()) <= 0:
        return None
    thr = float(np.quantile(sal[region], 0.99))
    ys, xs = np.nonzero((sal >= thr) & region)
    weights = sal[ys, xs]
    total = float(weights.sum())
    if total <= 0:
        return None
    return (float(xs @ weights / total / w), float(ys @ weights / total / h))


def reframe_cardbg(
    image: Image.Image,
    target: tuple[float, float] = CARD_CORE,
    size: tuple[int, int] = CARD_SIZE,
) -> tuple[Image.Image, dict]:
    """居中生成 → 裁切对位：把主体质心搬到 target，再缩回交付尺寸。

    裁切窗取「刚好让质心落在 target」的最大窗口，因此 zoom=原宽/裁切宽 ≥ 1、
    不会放大原图；质心越靠右裁得越少。返回 (图, 量测)：量测的 fx/fy 写进
    素材账当焦点登记，不再靠肉眼估。
    """
    fx, fy = card_subject_center(image) or (0.5, 0.5)
    W, H = image.size
    ow, oh = size
    tx, ty = target
    # 两轴都要留出「把质心挪到 target」的余量：只按宽度取最大窗会顶到画底，
    # 主体就压不到 37%（对樱花就是这样，落点只到 53%）。右缘另留 10%
    # 安全边——右缘复制条都长在 86~92%，这一刀顺手切掉。
    Wc_max = min(
        W,
        fx * W / tx,
        (1 - fx) * W / (1 - tx),
        (0.90 - fx) * W / (1 - tx),
    )
    Hc_max = min(H, fy * H / ty, (1 - fy) * H / (1 - ty))
    Wc = min(Wc_max, Hc_max * ow / oh)
    Hc = Wc * oh / ow
    left = min(max(fx * W - tx * Wc, 0.0), W - Wc)
    top = min(max(fy * H - ty * Hc, 0.0), H - Hc)
    crop = image.crop((round(left), round(top), round(left + Wc), round(top + Hc)))
    out = crop.resize(size, Image.LANCZOS)
    return out, {
        "fx": round(fx, 3),
        "fy": round(fy, 3),
        "crop": (round(left), round(top), round(Wc), round(Hc)),
        "zoom": round(ow / Wc, 3),
    }


def seam_columns(image: Image.Image) -> list[tuple[int, int, float]]:
    """找「整条竖线」：列差中位数 > 1.8 且超过 35% 的行有差。

    为什么不用单纯峰值：主体的竖边（球/王冠侧面）只在局部行出现，整列
    中位数接近 0；模型在 2.4:1 画布上拼出的接缝则是整条贯穿，中位数也高。
    """
    g = np.asarray(image.convert("L"), dtype=np.float32)
    d = np.abs(np.diff(g, axis=1))
    med = np.median(d, axis=0)
    frac = (d > 2).mean(axis=0)
    cand = np.where((med > 1.8) & (frac > 0.35))[0]
    if cand.size == 0:
        return []
    groups: list[tuple[int, int, float]] = []
    start = prev = int(cand[0])
    for x in cand[1:]:
        x = int(x)
        if x - prev <= 2:
            prev = x
            continue
        groups.append((start, prev, float(med[start : prev + 1].max())))
        start = prev = x
    groups.append((start, prev, float(med[start : prev + 1].max())))
    return groups


def repair_seams(
    image: Image.Image,
) -> tuple[Image.Image, list[tuple[int, int, float]]]:
    """把整条竖缝用左右两缘逐行线性过渡掉（宽 12~20px，抽象底看不出）。

    生成侧在 2.4:1 画布上偶尔拼出一条贯穿接缝；与其无限换种子，不如在
    落盘前做一次确定性的窄带过渡——不移动主体、不改构图。
    """
    groups = seam_columns(image)
    if not groups:
        return image, []
    arr = np.asarray(image.convert("RGB"), dtype=np.float32)
    w = arr.shape[1]
    for a, b, step in groups:
        center = (a + b) // 2
        k = min(10, max(4, int(step) + 4))
        x0, x1 = max(0, center - k), min(w - 1, center + k)
        left = arr[:, max(0, x0 - 1) : max(0, x0 - 1) + 1]
        right = arr[:, min(w - 1, x1 + 1) : min(w - 1, x1 + 1) + 1]
        t = np.linspace(0.0, 1.0, x1 - x0 + 1, dtype=np.float32)[None, :, None]
        arr[:, x0 : x1 + 1] = left * (1 - t) + right * t
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)), groups


def apply_cardbg_scrim(
    image: Image.Image,
    ramp_start: float = 0.30,
    ramp_end: float = 0.65,
    bg_color: tuple[float, float, float] = (14.0, 14.0, 18.0),
) -> Image.Image:
    """卡背左侧 UI 文字安全平滑融底暗色过渡（UI Scrim）。

    为什么用平滑融底代替单纯乘法暗化：
    白天的实景（阳光樱花球场、沙滩）原生亮度高达 150~200，单纯打折乘法
    难以将左侧稳定压入文字安全区（<= 30）；以 S 曲线将左侧平滑融合至卡底背景色
    （#0e0e12），左端保证文字对比度绝对安全，右侧（x >= ramp_end）100% 保持
    原始真实场景与丰富光影。
    """
    arr = np.asarray(image.convert("RGB"), dtype=np.float32)
    _, w, _ = arr.shape
    x = np.linspace(0.0, 1.0, w, dtype=np.float32)
    t = np.clip((x - ramp_start) / (ramp_end - ramp_start), 0.0, 1.0)
    # S 曲线平滑缓起：0 -> 1
    s = 3.0 * t**2 - 2.0 * t**3
    alpha = 0.03 + 0.97 * s
    alpha = alpha[None, :, None]

    bg = np.array(bg_color, dtype=np.float32)[None, None, :]
    blended = arr * alpha + bg * (1.0 - alpha)
    return Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))


def cardbg_spec_qc(image: Image.Image, target: tuple[float, float] = CARD_CORE) -> dict:
    """卡背单图规格闸门（mb_cardbg 专用）：不合格由调用方抛错，不许静默落盘。

    只卡会毁画面的硬项：核心落点、右缘复制/接缝、左半与整图亮度、主体在场。
    左半严格保证文字安全暗区；右缘与整图允许白天风景明媚，只拦极端暴光与硬接缝。
    """
    g = np.asarray(image.convert("L"), dtype=np.float32)
    _, w = g.shape
    problems: list[str] = []
    center = card_subject_center(image)
    if center is None:
        problems.append("找不到主体（中央没有高对比亮块）")
        center = (0.5, 0.5)
    cx, cy = center
    if abs(cx - target[0]) > 0.12 or abs(cy - target[1]) > 0.18:
        problems.append(
            f"核心落点 ({cx:.2f},{cy:.2f}) 偏离目标 ({target[0]:.2f},{target[1]:.2f})"
        )

    left = float(g[:, : int(w * 0.45)].mean())
    mean = float(g.mean())
    edge = g[:, int(w * 0.94) :]
    edge_mean, edge_std = float(edge.mean()), float(edge.std())
    if left > 30:
        problems.append(f"左半太亮({left:.0f}>30)——文字安全暗部没了")
    if mean > 110:
        problems.append(f"整图太亮({mean:.0f}>110)——文字安全纱会失效")
    # 右缘只查极端过曝：白天实景树冠/球网延伸允许明媚，但不能死白
    if edge_mean > 180:
        problems.append(f"右缘过曝严重(均{edge_mean:.0f}>180)")

    # 接缝：列均值的一阶差分在画内出现孤立尖峰（复制条与硬拼缝的特征）
    col = g.mean(axis=0)
    diff = np.abs(np.diff(col))
    lo, hi_i = int(w * 0.20), int(w * 0.95)
    peak = float(diff[lo:hi_i].max()) if hi_i > lo else 0.0
    median = float(np.median(diff)) or 1.0
    if peak > max(24.0, median * 10):
        problems.append(f"检测到竖直接缝(峰值{peak:.0f}/中位{median:.0f})")

    return {
        "ok": not problems,
        "problems": problems,
        "center": (round(cx, 3), round(cy, 3)),
        "left": round(left, 1),
        "mean": round(mean, 1),
        "edge_mean": round(edge_mean, 1),
        "edge_std": round(edge_std, 1),
        "seam_peak": round(peak, 1),
    }


def print_qc_report(name: str, qc: dict) -> None:
    mark = "✓ 通过" if qc["ok"] else "✗ 拦截"
    print(
        f"[{name}] 规格质检 {mark} · 核心=({qc['center'][0]:.2f},{qc['center'][1]:.2f})"
        f" 左半={qc['left']:.0f} 均值={qc['mean']:.0f}"
        f" 右缘={qc['edge_mean']:.0f}(σ={qc['edge_std']:.0f}) 接缝峰={qc['seam_peak']:.0f}"
    )
    for p in qc["problems"]:
        print(f"    - {p}")


# ==============================================================================
# CLI 入口与调度
# ==============================================================================


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="mieball 美术资产二次处理工具（卡背裁切对位、规格闸门与体积优化）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("inputs", type=Path, nargs="+", help="输入图片路径（支持批量）")
    parser.add_argument(
        "-i", "--in-place", action="store_true", help="原地覆盖而不是另存"
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="输出路径（单个输入时可用）"
    )

    mode_group = parser.add_argument_group("处理模式选项")
    mode_group.add_argument(
        "--reframe",
        action="store_true",
        help="卡背裁切对位：量测质心搬到 (68,37)、缩回 1536×640，随后附质检报告",
    )
    mode_group.add_argument(
        "--optimize",
        action="store_true",
        help="通用 WebP 体积优化（量化版与直转版择优）",
    )
    # 缺省模式 = 规格闸门复验：生图链路里闸门是硬的（comfy 抛错不落盘），
    # 命令行复验以退出码报告，方便对存量图做巡检
    mode_group.add_argument(
        "--qc",
        dest="qc",
        action="store_true",
        help="只跑规格闸门不裁不改（未指定任何模式时的缺省行为）",
    )

    opt_group = parser.add_argument_group("优化参数选项")
    opt_group.add_argument(
        "--colors", type=int, default=None, help="量化色数（不传则不量化，仅直转压缩）"
    )
    opt_group.add_argument("--quality", type=int, default=80, help="WebP 编码质量")
    opt_group.add_argument(
        "--max-side", type=int, default=None, help="最长边像素上限，超出等比缩小"
    )
    args = parser.parse_args(argv)
    if not (args.reframe or args.optimize or args.qc):
        args.qc = True
    if args.output and len(args.inputs) > 1:
        parser.error("-o 只在单个输入时可用")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rc = 0

    for path in args.inputs:
        if not path.exists():
            print(f"警告: 文件不存在，跳过: {path}", file=sys.stderr)
            rc = 1
            continue

        img = Image.open(path)

        if args.reframe:
            out_img, info = reframe_cardbg(img)
            print(
                f"[{path.name}] 裁切对位 · 主体({info['fx']:.2f},{info['fy']:.2f})"
                f" → ({CARD_CORE[0]:.2f},{CARD_CORE[1]:.2f}) · 裁切 {info['crop'][2]:.0f}x{info['crop'][3]:.0f}"
                f" · 缩放 {info['zoom']:.2f}x"
            )
            qc = cardbg_spec_qc(out_img)
            print_qc_report(path.name, qc)
            default_out = (
                path
                if args.in_place
                else path.with_stem(f"{path.stem}_reframed").with_suffix(".webp")
            )
            out_target = args.output or default_out
            out_target.parent.mkdir(parents=True, exist_ok=True)
            # 对位稿固定 80：它是落位与闸门的存证，--quality 只管 --optimize 自己的产物
            out_target.write_bytes(encode_webp(out_img, 80))
            print(f"[{path.name}] -> {out_target.name}")
            img = out_img
            if not qc["ok"]:
                rc = 1

        if args.optimize:
            scheme, payload = optimize_image_bytes(
                img, colors=args.colors, quality=args.quality, max_side=args.max_side
            )
            raw_size = path.stat().st_size
            default_out = path if args.in_place else path.with_stem(f"{path.stem}_opt")
            out_target = args.output or default_out
            out_target.parent.mkdir(parents=True, exist_ok=True)
            out_target.write_bytes(payload)
            ratio = (1 - len(payload) / raw_size) * 100 if raw_size else 0
            print(
                f"[{path.name}] -> {out_target.name} ({raw_size / 1024:.0f}KB -> {len(payload) / 1024:.0f}KB, -{ratio:.0f}%, {scheme})"
            )
            continue

        if args.qc:
            qc = cardbg_spec_qc(img)
            print_qc_report(path.name, qc)
            if not qc["ok"]:
                rc = 1

    return rc


if __name__ == "__main__":
    sys.exit(main())
