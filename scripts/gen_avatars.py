#!/usr/bin/env python3
"""mieball 球员头像生成流水线：生图 → 蓝幕抠图 → 归一 → WebP，前置环节一肩挑。

取景参数的人工定格在 scripts/picfit.html，不在本脚本。

用法：
  # 六款公共头像全流程（ComfyUI 生图 → 抠图归一 → 仓库顶层 cosmetics/{cid}.webp）
  python3 scripts/gen_avatars.py [--overwrite] [--only a-p1]

  # 只做后处理：把已有生图 PNG（天蓝底）抠图归一成 512 透明 WebP（不生图）
  python3 scripts/gen_avatars.py --cutout temp/形象/avatar-5644-v1.png
  python3 scripts/gen_avatars.py --cutout temp/形象/ -o 输出目录
"""

from __future__ import annotations

import argparse
import sys
from collections import deque
from pathlib import Path

from comfy import generate
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]

# 蓝幕色彩距离容差（平方比较口径）：像素与参考色的欧氏距离小于它即视为背景
SKY_TOLERANCE = 65


def is_sky_blue(r: int, g: int, b: int, ref_rgb: tuple[int, int, int]) -> bool:
    """判断像素是否属于天蓝色背景色系（参考色与 comfy.py sky_blue 预设的蓝幕色 #4A90E2 同一色）"""
    # 典型天蓝特征: B 通道显著大于 R 通道，且 G/B 较高
    if b > r + 30 and g > r + 15:
        # 欧氏色彩距离（平方比较，免逐像素开方）
        dr = r - ref_rgb[0]
        dg = g - ref_rgb[1]
        db = b - ref_rgb[2]
        if dr * dr + dg * dg + db * db < SKY_TOLERANCE * SKY_TOLERANCE:
            return True
        # 稍微泛化判断色系
        if b > 140 and r < 140:
            return True
    return False


def is_white_outline(r: int, g: int, b: int, threshold: int = 210) -> bool:
    """判断是否为粗白色描边保护层"""
    # 只要三通道都很高且色差较小即视为白色描边
    return (
        r >= threshold
        and g >= threshold
        and b >= threshold
        and abs(r - g) < 25
        and abs(r - b) < 25
    )


def remove_sky_blue_background(img: Image.Image) -> Image.Image:
    """
    使用边缘连通泛洪 (FloodFill) 算法剥离天蓝色背景：
    仅从图像四周边沿向内部扩散，遇到白色轮廓自然停止，生成高质量透明图层。
    与 scripts/picfit.html 页内同款算法互为硬契约，改一处须同步另一处。
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

    # 2. 从四条边框的全部边缘像素注入 BFS 种子（角点由 visited 守卫去重）
    visited = bytearray(width * height)
    queue = deque()
    border = [(x, y) for x in range(width) for y in (0, height - 1)] + [
        (x, y) for y in range(height) for x in (0, width - 1)
    ]
    for x, y in border:
        idx = y * width + x
        if not visited[idx]:
            visited[idx] = 1
            r, g, b, _ = pixels[x, y]
            if is_sky_blue(r, g, b, ref_rgb):
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
                    if not is_white_outline(nr, ng, nb) and is_sky_blue(
                        nr, ng, nb, ref_rgb
                    ):
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
    padding_pct: float = 0.04,
    quality: int = 90,
) -> tuple[int, int]:
    """
    后处理管线：读取 -> 蓝幕抠图 -> 主体居中留白 -> 规范尺寸缩放 -> 导出 WebP。
    边距口径 4% 与 picfit.html 的 PNG 归一一致，返回 (原始体积字节, 产物体积字节)。
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

        # 留白计算 (4% 安全边)
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


# 6款公共头像提示词：严格遵循半身胸像三原则（正面正视、姿态端正自然、道具内聚或无道具、圆润收边）
AVATARS = [
    {
        "cid": "a-p1",
        "name": "阿拉斯加犬（红领巾）",
        "seed": 1189,
        "prompt": (
            "Q版可爱角色半身像贴纸（chibi bust sticker），阿拉斯加犬，黑灰白经典毛色，"
            "戴红色小领巾，正面正向视角（facing viewer, frontal view），双手在胸前端正自然，"
            "神气微笑，整个半身胸像外围包着完整粗白描边，居中完整构图，"
            "四周留有安全边距（centered with margin, floating in solid sky blue background），"
            "底部自然圆润收边不贴边"
        ),
    },
    {
        "cid": "a-p2",
        "name": "阿拉斯加雪橇犬（蓝发带）",
        "seed": 6410,
        "prompt": (
            "Q版可爱角色半身像贴纸（chibi bust sticker），阿拉斯加雪橇犬，灰白蓬松厚毛，宽脸憨厚，"
            "戴蓝色运动发带，咧嘴大笑，正面正向视角（facing viewer, frontal view），双手在胸前端正自然，"
            "整个半身胸像外围包着完整粗白描边，居中完整构图，"
            "四周留有安全边距（centered with margin, floating in solid sky blue background），"
            "底部自然圆润收边不贴边"
        ),
    },
    {
        "cid": "a-p3",
        "name": "哈士奇犬（冰蓝眼）",
        "seed": 8145,
        "prompt": (
            "Q版可爱角色半身像贴纸（chibi bust sticker），哈士奇犬，黑白经典面具脸谱，冰蓝色眼睛，"
            "头正身直正视前方不歪头（facing viewer, frontal view, straight head not tilted），自信机灵微笑，"
            "双手在胸前端正自然，嘴部闭合微笑不叼大道具，整个半身胸像外围包着完整粗白描边，居中完整构图，"
            "四周留有安全边距（centered with margin, floating in solid sky blue background），"
            "底部自然圆润收边不贴边"
        ),
    },
    {
        "cid": "a-p4",
        "name": "金毛寻回犬（绿领巾）",
        "seed": 5644,
        "prompt": (
            "Q版可爱角色半身像贴纸（chibi bust sticker），金毛寻回犬，奶金色蓬松长毛，温暖眯眼微笑，"
            "脖子上系着绿色运动领巾，头正身直正面正视（facing viewer, frontal view），双手在胸前端正收拢，"
            "不举手不遮面，整个半身胸像外围包着完整粗白描边，居中完整构图，"
            "四周留有安全边距（centered with margin, floating in solid sky blue background），"
            "底部自然圆润收边不贴边"
        ),
    },
    {
        "cid": "a-p5",
        "name": "花栗鼠（抱球款）",
        "seed": 4427,
        "prompt": (
            "Q版可爱角色半身像贴纸（chibi bust sticker），花栗鼠，栗棕色毛，背上有黑白条纹，"
            "腮帮子鼓鼓的，好奇圆眼睛，头正身直正面正视（facing viewer, frontal view），"
            "双手在胸前正中稳稳抱紧一枚黄色小匹克球，无大球拍，无外突肢体，整个半身胸像外围包着完整粗白描边，"
            "居中完整构图，四周留有安全边距（centered with margin, floating in solid sky blue background），"
            "底部自然圆润收边不贴边"
        ),
    },
    {
        "cid": "a-p6",
        "name": "小熊猫（发带款）",
        "seed": 9850,
        "prompt": (
            "Q版可爱角色半身像贴纸（chibi bust sticker），小熊猫，锈红色蓬松毛，白色脸颊和尖耳朵，"
            "头戴蓝色运动发带，头正身直正面正视（facing viewer, frontal view），慵懒满足微笑，"
            "双手在胸前端正自然，无横甩外展的大尾巴，尾巴自然收拢在身后，整个半身胸像外围包着完整粗白描边，"
            "居中完整构图，四周留有安全边距（centered with margin, floating in solid sky blue background），"
            "底部自然圆润收边不贴边"
        ),
    },
    # 系统款。访客 a-s1=没账号的人，身份标记不进册（人人可穿就失去标记意义）；
    # 默认 g-00=RO 波利加白翅膀（粉果冻+白翅，无光环），模型生图，
    # 例外进册公共款——换走默认脸的人能换回来，后端 DEFAULT_AVATAR 读它。
    # g-00 无胸像前缀（preset=None 自带全部贴纸语言），天蓝底供抠图流水线
    {
        "cid": "a-s1",
        "name": "访客（灰柴犬·空白访客牌）",
        "seed": 2401,
        "prompt": (
            "Q版可爱角色半身像贴纸（chibi bust sticker），灰白色圆脸柴犬，柔和浅灰色绒毛，"
            "胸前挂着一张空白访客吊牌（blank visitor badge on a lanyard，牌面干净无字无图案），"
            "双手在胸前端正轻持挂绳，腼腆友善微笑，"
            "正面正向视角（facing viewer, frontal view），整个半身胸像外围包着完整粗白描边，"
            "居中完整构图，四周留有安全边距（centered with margin, floating in solid sky blue background），"
            "底部自然圆润收边不贴边"
        ),
    },
    {
        "cid": "g-00",
        "name": "波利（默认）",
        "seed": 2003,
        "preset": None,
        "width": 1024,
        "height": 1024,
        "background": "sky_blue",
        "prompt": (
            "Q版可爱游戏怪物角色波利作为唯一主体（Poring from Ragnarok Online, the iconic "
            "cute pink slime monster as the only subject, no people, no buildings, no ground），"
            "2D 贴纸插画风格，粉红色半透明果冻质感的水滴形身体（pink jelly slime with a "
            "teardrop-shaped bouncy body，下宽上窄圆润收顶），身体两侧长着一对小小的白色天使翅膀"
            "（a pair of small white angel wings on both sides of the body，翅膀小巧圆润不外展），"
            "没有金色光环（no halo），头顶一根弯曲的小呆毛（a single curly antenna on top），"
            "脸部只有一双又大又圆的乌黑卡通眼睛带白色高光（two big round black cartoon eyes "
            "with white highlights），无嘴无鼻（no mouth, no nose），表情软萌无辜，"
            "身体微微弹跳的憨态，"
            "整个形象（含翅膀）外围包着粗而干净的完整白描边（thick white sticker outline "
            "around the whole figure including wings），"
            "居中完整构图，四周留有安全边距（centered with margin），"
            "底部圆润收边不贴边，画面中不出现任何文字、字母、数字与标志"
        ),
    },
]


def run_generate(args: argparse.Namespace) -> None:
    """头像全流程：ComfyUI 生图 → 抠图归一 → 落位 cosmetics（条目可带槽位覆盖）。"""
    temp_dir = ROOT / "temp" / "形象"
    temp_dir.mkdir(parents=True, exist_ok=True)
    # 仓库顶层素材目录：开发期由 vite 中间件直出、线上由部署素材通道直传 nginx 树
    out_dir = ROOT / "cosmetics"
    out_dir.mkdir(parents=True, exist_ok=True)

    items = [a for a in AVATARS if not args.only or a["cid"] == args.only]

    print(f"=== 开始生成 {len(items)} 款半身胸像头像 ===")
    for idx, item in enumerate(items, 1):
        cid = item["cid"]
        seed = item["seed"]
        raw_png = temp_dir / f"{cid}_bust_v1.png"
        target_webp = out_dir / f"{cid}.webp"

        print(
            f"\n[{idx}/{len(items)}] 正在处理 {cid} ({item['name']}) · seed={seed}..."
        )
        if raw_png.exists() and not args.overwrite:
            print(f"  PNG 已存在，跳过生图：{raw_png}")
        else:
            generate(
                prompt=item["prompt"],
                output_path=raw_png,
                preset_name=item.get("preset", "mb_avatar"),
                seed=seed,
                width=item.get("width"),
                height=item.get("height"),
                background=item.get("background"),
                overwrite=True,
            )
            print(f"  生图完成：{raw_png}")

        print(f"  正在抠图并压缩导出至：{target_webp}...")
        _, out_sz = process_image(raw_png, target_webp)
        print(f"  ✓ 落位完成：{target_webp.name} ({out_sz // 1024} KB)")

    print("\n=== 全部完成！接下来在 scripts/picfit.html 里定取景参数 ===")


def run_cutout(args: argparse.Namespace) -> None:
    """只做后处理：已有生图 PNG（天蓝底）→ 抠图归一 512 透明 WebP。"""
    inputs: list[Path] = []
    for p in args.cutout:
        path = Path(p)
        if not path.exists():
            print(f"[错误] 路径不存在: {path}")
            sys.exit(1)
        if path.is_dir():
            inputs += sorted(
                q
                for q in path.iterdir()
                if q.suffix.lower() in (".png", ".jpg", ".jpeg")
            )
        else:
            inputs.append(path)
    if not inputs:
        print("[提示] 没有可处理的图片文件。")
        return

    out_dir = Path(args.output).resolve() if args.output else inputs[0].parent / "webp"
    print(f"处理 {len(inputs)} 张 → {out_dir}")
    ok = 0
    for f in inputs:
        out = out_dir / f"{f.stem}.webp"
        try:
            orig_sz, new_sz = process_image(
                f, out, args.size, args.padding, args.quality
            )
            print(f"  {f.name}: {orig_sz // 1024}KB -> {new_sz // 1024}KB")
            ok += 1
        except Exception as e:  # noqa: BLE001 —— 批处理里坏图/读不了的图跳过不拦整批
            print(f"  {f.name}: 失败 {e}")
    print(f"完成 {ok}/{len(inputs)}")


def main():
    parser = argparse.ArgumentParser(
        description="球员头像生成流水线（生图+抠图+归一+WebP）"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="覆盖已有 PNG 重新生图"
    )
    parser.add_argument("--only", help="仅生成指定 cid，如 a-p1")
    parser.add_argument(
        "--cutout",
        nargs="+",
        metavar="PATH",
        help="只做后处理：抠图归一已有 PNG/目录（不生图）",
    )
    parser.add_argument(
        "-o", "--output", default="", help="--cutout 的输出目录（默认输入旁 webp/）"
    )
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--quality", type=int, default=90)
    parser.add_argument(
        "--padding",
        type=float,
        default=0.04,
        help="四周安全留白比例（默认 0.04，与 picfit 一致）",
    )
    args = parser.parse_args()

    if args.cutout:
        run_cutout(args)
    else:
        run_generate(args)


if __name__ == "__main__":
    main()
