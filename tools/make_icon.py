"""把 logo/simple-view-icon.png 归一成应用图标（PNG + 多尺寸 ICO）。

源图是 512×512 透明底，但图形只占中间 ~75%，四周留白 + 一层投影。
小尺寸（16/24px）直接缩放的话眼睛会缩成一个小点，所以这里先按 alpha
包围盒裁掉空边、再按固定比例居中，让图形在各尺寸下都能占满视觉重心。

用法：
    python tools/make_icon.py            # 生成 assets/branding/app-icon.png + build/WinIsland.ico
    python tools/make_icon.py --preview  # 额外导出 build/icon-preview-*.png 供人眼检查
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "logo" / "simple-view-icon.png"
OUT_PNG = ROOT / "assets" / "branding" / "app-icon.png"
OUT_ICO = ROOT / "build" / "WinIsland.ico"

# 图形在画布中的占比：88% 是 Windows 图标惯例（留一圈呼吸空间，又不至于缩太小）
FILL = 0.88
ICO_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (40, 40),
             (32, 32), (24, 24), (20, 20), (16, 16)]


def normalize(src: Path, size: int = 512) -> Image.Image:
    """裁到 alpha 包围盒 → 居中放进正方形 → 缩放到目标尺寸。"""
    im = Image.open(src).convert("RGBA")
    bbox = im.split()[3].getbbox()
    if bbox:
        im = im.crop(bbox)

    # 先贴到正方形画布中央（保持宽高比），再整体缩放到 FILL 占比
    side = max(im.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)

    # 放大到 4 倍再做 LANCZOS 收缩，小尺寸的边缘更干净
    work = max(size * 4, side)
    inner = int(round(work * FILL))
    art = square.resize((inner, inner), Image.LANCZOS)

    out = Image.new("RGBA", (work, work), (0, 0, 0, 0))
    off = (work - inner) // 2
    out.paste(art, (off, off), art)
    return out.resize((size, size), Image.LANCZOS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="导出各尺寸 PNG 供检查")
    ap.add_argument("--src", default=str(SRC),
                    help="换源图，例如 logo/simple-view-icon-dark.png（深色圆角底板版）")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.is_absolute():
        src = ROOT / src
    if not src.exists():
        print(f"缺少源图：{src}")
        return 1

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    OUT_ICO.parent.mkdir(parents=True, exist_ok=True)

    master = normalize(src, 512)
    master.save(OUT_PNG)
    print(f"png  {OUT_PNG.relative_to(ROOT)}  {master.width}x{master.height}  <- {src.name}")

    # ICO 里每个尺寸都从 512 母版独立降采样，而不是 256→16 逐级缩（后者会糊）
    frames = [normalize(src, s[0]) for s in ICO_SIZES]
    frames[0].save(OUT_ICO, format="ICO", sizes=ICO_SIZES,
                   append_images=frames[1:])
    print(f"ico  {OUT_ICO.relative_to(ROOT)}  {len(frames)} 个尺寸："
          f"{', '.join(str(s[0]) for s in ICO_SIZES)}")

    if args.preview:
        for s in (16, 24, 32, 48):
            p = ROOT / "build" / f"icon-preview-{s}.png"
            # 放大到 128 便于人眼看细节（最近邻，不引入新的插值）
            frames[ICO_SIZES.index(next(x for x in ICO_SIZES if x[0] == s))].resize(
                (128, 128), Image.NEAREST).save(p)
            print(f"preview {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
