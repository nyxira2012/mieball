"""一次性素材落位工具（1.9 批5）——把 temp/ 里的真素材按册子 cid 改名拷入
frontend/public/cosmetics/，缺的用 PIL 程序占位图补齐，跑完产出全 32 件：

- 头像 17 件 .webp：公共 a-p1..a-p6 · 荣誉 a-{m5,m20,m50,t30,t35,t40,t45,o3,o10,o30} · 定制 a-x1
- 卡背 15 件 .webp：公共 b-c1..b-c4 · 荣誉 b-{...同族十件} · 定制 b-x1

真素材来源（首批）：
- a-p1 ← temp/形象/avatar-1189-v1.png（唯一真头像素材）
- b-c1..b-c4 ← 原型 CBG 四件 cardbg-{1660,8466,6986,7922}-v2.webp
- 荣誉卡背十件 ← temp/卡片背景/ 其余主产物 webp 按文件名序分配
  （排除四件公共款的同号其他版本，避免荣誉款与公共款近似撞图）

⚠ 占位图是临时物：正式素材批次逐张同名替换即可（约定路径 /cosmetics/{cid}.webp，头像卡背同格式
不变），前端与册子零改动。Pillow ≥10 支持 webp 直存（本机 12.2 实测），.webp 约定不动。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
BACK_DIR = ROOT / "temp" / "卡片背景"
AVATAR_DIR = ROOT / "temp" / "形象"
OUT_DIR = ROOT / "frontend" / "public" / "cosmetics"

AVATAR_CIDS = [
    "a-p1",
    "a-p2",
    "a-p3",
    "a-p4",
    "a-p5",
    "a-p6",
    "a-m5",
    "a-m20",
    "a-m50",
    "a-t30",
    "a-t35",
    "a-t40",
    "a-t45",
    "a-o3",
    "a-o10",
    "a-o30",
    "a-x1",
]
BACK_CIDS = [
    "b-c1",
    "b-c2",
    "b-c3",
    "b-c4",
    "b-m5",
    "b-m20",
    "b-m50",
    "b-t30",
    "b-t35",
    "b-t40",
    "b-t45",
    "b-o3",
    "b-o10",
    "b-o30",
    "b-x1",
]
# 公共卡背四件 = 原型 CBG 表同源（temp/原型-背景卡组件.html）
PUBLIC_BACK_FILES = [
    "cardbg-1660-v2.webp",
    "cardbg-8466-v2.webp",
    "cardbg-6986-v2.webp",
    "cardbg-7922-v2.webp",
]
REAL_AVATARS = {"a-p1": AVATAR_DIR / "avatar-1189-v1.png"}

# 夜球场 token 色（frontend/src/styles/tokens.scss）：占位按族给底色系
FAMILY_ACCENT = {
    "p": (255, 212, 0),  # 公共 · 柠檬
    "m": (255, 90, 54),  # 场数族 · 珊瑚
    "t": (111, 231, 255),  # 台阶族 · 电青
    "o": (184, 169, 255),  # 组局族 · 淡紫
    "x": (245, 241, 232),  # 定制 · 暖白
}


def family_of(cid: str) -> str:
    return cid.split("-")[1][0]


def honor_back_sources(count: int) -> list[Path]:
    """荣誉卡背真素材：temp 其余主产物 webp 按文件名序取前 N。
    主产物=不含 narrowcrop/preview/_p/rejected 派生件；并剔除四件公共款
    同号其余版本（v1/v3），避免荣誉款分到与公共款同图的近似版本。"""
    used_bases = {f.split("-")[1] for f in PUBLIC_BACK_FILES}
    files = sorted(
        f
        for f in BACK_DIR.glob("cardbg-*-v*.webp")
        if not any(k in f.name for k in ("narrowcrop", "preview", "_p", "rejected"))
        and f.name.split("-")[1] not in used_bases
    )
    if len(files) < count:
        raise SystemExit(f"temp 卡背主产物不足：需要 {count}，只有 {len(files)}")
    return files[:count]


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def placeholder_avatar(cid: str) -> Image.Image:
    """圆脸占位 PNG：透明底圆形 + 族色底 + 简单五官 + cid 记号（256×256）。"""
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    accent = FAMILY_ACCENT[family_of(cid)]
    rim = tuple(int(c * 0.72) for c in accent)
    d.ellipse([6, 6, s - 6, s - 6], fill=rim + (255,))
    d.ellipse([16, 16, s - 16, s - 16], fill=accent + (255,))
    ink = (14, 14, 18, 255)
    d.ellipse([s * 0.34, s * 0.40, s * 0.42, s * 0.50], fill=ink)  # 左眼
    d.ellipse([s * 0.58, s * 0.40, s * 0.66, s * 0.50], fill=ink)  # 右眼
    d.arc([s * 0.36, s * 0.50, s * 0.64, s * 0.74], 20, 160, fill=ink, width=10)  # 笑
    f = font(30)
    label = cid.removeprefix("a-")
    w = d.textlength(label, font=f)
    d.text(((s - w) / 2, s * 0.76), label, font=f, fill=ink)
    return img


def placeholder_back(cid: str) -> Image.Image:
    """卡背占位 webp：1536×640 深色渐变 + 焦点位一团族色光晕 + cid 文字。
    尺寸/构图按册子规格（12:5 横幅、主体居中偏焦点 68,37）。"""
    w, h = 1536, 640
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    ink, ink3 = (14, 14, 18), (30, 30, 39)
    for y in range(h):  # 纵向深色渐变（ink → ink3）
        t = y / (h - 1)
        d.line(
            [(0, y), (w, y)],
            fill=tuple(int(a + (b - a) * t) for a, b in zip(ink, ink3)),
        )
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    accent = FAMILY_ACCENT[family_of(cid)]
    cx, cy = int(w * 0.68), int(h * 0.37)  # 册子统一焦点位——占位也按焦点摆主体
    gd.ellipse([cx - 150, cy - 150, cx + 150, cy + 150], fill=accent + (70,))
    gd.ellipse([cx - 90, cy - 90, cx + 90, cy + 90], fill=accent + (110,))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img)
    f = font(56)
    tw = d.textlength(cid, font=f)
    d.text(((w - tw) / 2, h - 110), cid, font=f, fill=(245, 241, 232))
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[tuple[str, str]] = []

    for cid, src in REAL_AVATARS.items():
        shutil.copy2(src, OUT_DIR / f"{cid}.webp")
        manifest.append((cid, f"真素材 ← {src.name}"))
    honor_sources = honor_back_sources(10)
    for cid, src in zip(BACK_CIDS[:4], PUBLIC_BACK_FILES):
        shutil.copy2(BACK_DIR / src, OUT_DIR / f"{cid}.webp")
        manifest.append((cid, f"真素材 ← {src}"))
    for cid, src in zip(BACK_CIDS[4:14], honor_sources):
        shutil.copy2(src, OUT_DIR / f"{cid}.webp")
        manifest.append((cid, f"真素材 ← {src.name}"))

    for cid in AVATAR_CIDS:
        if cid not in REAL_AVATARS:
            placeholder_avatar(cid).save(
                OUT_DIR / f"{cid}.webp", format="WEBP", quality=82, method=6
            )
            manifest.append((cid, "占位（圆脸 WebP 透明底）"))

    made = {c for c, _ in manifest}
    for cid in BACK_CIDS:
        if cid not in made:
            placeholder_back(cid).save(OUT_DIR / f"{cid}.webp", "WEBP", quality=85)
            manifest.append((cid, "占位（1536×640 深色渐变 webp）"))

    for cid, kind in manifest:
        print(f"{cid:8s} {kind}")
    print(f"\n共 {len(manifest)} 件 → {OUT_DIR}")


if __name__ == "__main__":
    main()
