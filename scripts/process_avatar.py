#!/usr/bin/env python3
"""
mieball 项目 - 人物头像自动抠图与 WebP 规范压缩工具 (单文件脚本)
文件: process_avatar.py

功能说明：
1. 自动抠图：
   - 专为 "天蓝色背景 + 粗白色描边" 设计的边缘泛洪 (FloodFill) 蓝幕抠图算法。
   - 从图片四周边框向内扫描，遇到白色描边自动阻断，绝不误抠主体内部的蓝色细节。
   - 边缘自适应羽化，去除残留蓝边，生成干净透明通道 (Alpha)。
2. 规范尺寸与 WebP 压缩：
   - 支持主体自动智能居中与边距校准 (默认四周保留 8% 安全留白，防圆角切角)。
   - 规范输出为 1:1 正方形 (默认 512x512，保留超清 Retina 质感)。
   - 输出为高压缩比 WebP 格式 (通常仅 20KB~50KB)，完美符合小程序与 Web 加载规范。
3. 一键同步：
   - 提供 --to-app 选项，直接同步至 frontend/src/static/avatars/ 供前端直接消费。
"""

import os
import sys
import argparse
from pathlib import Path
from collections import deque
from PIL import Image, ImageFilter


def is_sky_blue(r: int, g: int, b: int, ref_rgb: tuple[int, int, int] = (74, 144, 226), tolerance: int = 65) -> bool:
    """判断像素是否属于天蓝色背景色系"""
    # 典型天蓝特征: B 通道显著大于 R 通道，且 G/B 较高
    if b > r + 30 and g > r + 15:
        # 欧氏色彩距离
        dr = r - ref_rgb[0]
        dg = g - ref_rgb[1]
        db = b - ref_rgb[2]
        dist = (dr * dr + dg * dg + db * db) ** 0.5
        if dist < tolerance:
            return True
        # 稍微泛化判断色系
        if b > 140 and r < 140:
            return True
    return False


def is_white_outline(r: int, g: int, b: int, threshold: int = 210) -> bool:
    """判断是否为粗白色描边保护层"""
    # 只要三通道都很高且色差较小即视为白色描边
    return r >= threshold and g >= threshold and b >= threshold and abs(r - g) < 25 and abs(r - b) < 25


def remove_sky_blue_background(img: Image.Image, tolerance: int = 65) -> Image.Image:
    """
    使用边缘连通泛洪 (FloodFill) 算法剥离天蓝色背景：
    仅从图像四周边沿向内部扩散，遇到白色轮廓自然停止，生成高质量透明图层。
    """
    rgba = img.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()

    # 1. 自动采样四角背景颜色作为基准
    corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    corner_colors = [pixels[x, y][:3] for x, y in corners]
    avg_r = sum(c[0] for c in corner_colors) // 4
    avg_g = sum(c[1] for c in corner_colors) // 4
    avg_b = sum(c[2] for c in corner_colors) // 4
    ref_rgb = (avg_r, avg_g, avg_b)

    # 2. 从边缘四个边框进行 BFS 扩散标记背景
    visited = bytearray(width * height)
    queue = deque()

    # 注入四条边缘的所有外围像素
    for x in range(width):
        for y in (0, height - 1):
            idx = y * width + x
            if not visited[idx]:
                visited[idx] = 1
                r, g, b, _ = pixels[x, y]
                if is_sky_blue(r, g, b, ref_rgb, tolerance):
                    queue.append((x, y))

    for y in range(height):
        for x in (0, width - 1):
            idx = y * width + x
            if not visited[idx]:
                visited[idx] = 1
                r, g, b, _ = pixels[x, y]
                if is_sky_blue(r, g, b, ref_rgb, tolerance):
                    queue.append((x, y))

    # BFS 扩散
    bg_mask = bytearray(width * height)
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]

    while queue:
        cx, cy = queue.popleft()
        bg_mask[cy * width + cx] = 255  # 标记为确定背景

        for dx, dy in directions:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < width and 0 <= ny < height:
                nidx = ny * width + nx
                if not visited[nidx]:
                    visited[nidx] = 1
                    nr, ng, nb, _ = pixels[nx, ny]
                    # 如果不是白色描边，且属于天蓝背景，则继续向内扩散
                    if not is_white_outline(nr, ng, nb) and is_sky_blue(nr, ng, nb, ref_rgb, tolerance):
                        queue.append((nx, ny))

    # 3. 创建 Alpha 蒙版，并对边缘进行轻微柔化防生硬毛刺
    mask_img = Image.frombytes("L", (width, height), bytes(bg_mask))
    # 将背景(255)转为主体(255)，背景(0)
    fg_mask = Image.eval(mask_img, lambda v: 0 if v == 255 else 255)
    
    # 柔和羽化边缘 (半径 1)
    soft_mask = fg_mask.filter(ImageFilter.GaussianBlur(radius=0.8))

    # 4. 合成透明通道
    r, g, b, _ = rgba.split()
    result = Image.merge("RGBA", (r, g, b, soft_mask))
    return result


def process_image(
    input_path: Path,
    output_path: Path,
    target_size: int = 512,
    padding_pct: float = 0.08,
    quality: int = 90,
) -> tuple[int, int]:
    """
    完整后处理管线：
    读取 -> 蓝幕抠图 -> 主体居中留白 -> 规范尺寸缩放 -> 导出 WebP
    返回 (原始体积字节, 产物体积字节)
    """
    orig_size_bytes = input_path.stat().st_size
    img = Image.open(input_path)

    # 1. 抠图
    cutout = remove_sky_blue_background(img)

    # 2. 计算人物主体的边界盒 (Bounding Box) 并做自适应正方形排版
    bbox = cutout.getbbox()
    if bbox:
        cropped = cutout.crop(bbox)
        bw, bh = cropped.size

        # 留白计算 (例如 8% padding)
        side = int(max(bw, bh) / (1.0 - padding_pct * 2))
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))

        # 居中粘贴
        offset_x = (side - bw) // 2
        offset_y = (side - bh) // 2
        canvas.paste(cropped, (offset_x, offset_y), cropped)
    else:
        canvas = cutout

    # 3. 规范缩放到目标大小 (如 512x512)
    final_img = canvas.resize((target_size, target_size), Image.Resampling.LANCZOS)

    # 4. 保存为 WebP
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_img.save(output_path, format="WEBP", quality=quality, method=6)

    out_size_bytes = output_path.stat().st_size
    return orig_size_bytes, out_size_bytes


def main():
    parser = argparse.ArgumentParser(
        description="process_avatar.py - 球员形象抠图与 WebP 规范压缩工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例用法:
  # 1. 处理单张图片并输出到默认目录
  python3 scripts/process_avatar.py temp/形象/alaska_dog.png

  # 2. 批量处理 temp/形象/ 下的所有 png 图片
  python3 scripts/process_avatar.py temp/形象/

  # 3. 处理并直接同步到前端工程目录 (frontend/src/static/avatars/)
  python3 scripts/process_avatar.py temp/形象/ --to-app
""",
    )
    parser.add_argument("input_path", help="输入图片文件路径或目录路径")
    parser.add_argument("--output-dir", "-o", default="", help="输出目录 (默认: 输入目录下的 webp/ 文件夹)")
    parser.add_argument("--size", "-s", type=int, default=512, help="规范输出分辨率 (默认 512，即 512x512)")
    parser.add_argument("--quality", "-q", type=int, default=90, help="WebP 压缩质量 1-100 (默认 90)")
    parser.add_argument("--padding", "-p", type=float, default=0.08, help="四周安全留白比例 (默认 0.08)")
    parser.add_argument("--to-app", action="store_true", help="直接同步至前端 static/avatars/ 目录")

    args = parser.parse_args()
    # 确定项目根目录 (脚本位于 scripts/ 下，项目根目录为父级的父级)
    workspace_root = Path(__file__).resolve().parent.parent

    in_path = Path(args.input_path).resolve()
    if not in_path.exists():
        print(f"[错误] 路径不存在: {in_path}")
        sys.exit(1)

    # 收集待处理文件
    if in_path.is_file():
        file_list = [in_path]
        base_dir = in_path.parent
    else:
        file_list = sorted([p for p in in_path.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")])
        base_dir = in_path

    if not file_list:
        print(f"[提示] 未在 {in_path} 找到可处理的图片文件。")
        sys.exit(0)

    # 确定输出目录
    if args.to_app:
        target_dir = workspace_root / "frontend" / "src" / "static" / "avatars"
    elif args.output_dir:
        target_dir = Path(args.output_dir).resolve()
    else:
        target_dir = base_dir / "webp"

    print("=" * 68)
    print("【process_avatar.py - 抠图与 WebP 压缩】")
    print("=" * 68)
    print(f"  处理文件数量: {len(file_list)}")
    print(f"  规范输出尺寸: {args.size}x{args.size} (1:1 正方形)")
    print(f"  目标输出目录: {target_dir}")
    print("=" * 68)

    success_cnt = 0
    total_saved_bytes = 0

    for idx, f in enumerate(file_list, 1):
        out_file = target_dir / f"{f.stem}.webp"
        print(f"[{idx}/{len(file_list)}] 正在处理: {f.name} ... ", end="", flush=True)
        try:
            orig_sz, new_sz = process_image(
                input_path=f,
                output_path=out_file,
                target_size=args.size,
                padding_pct=args.padding,
                quality=args.quality,
            )
            saved_sz = orig_sz - new_sz
            total_saved_bytes += max(0, saved_sz)
            print(f"完成! {orig_sz // 1024}KB -> {new_sz // 1024}KB (WebP)")
            success_cnt += 1
        except Exception as e:
            print(f"失败: {e}")

    print("\n" + "=" * 68)
    print(f"处理完毕！成功: {success_cnt}/{len(file_list)}")
    print(f"产物已保存至: {target_dir}")
    if total_saved_bytes > 0:
        print(f"累计节省空间约: {total_saved_bytes // 1024} KB")


if __name__ == "__main__":
    main()
