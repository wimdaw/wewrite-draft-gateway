#!/usr/bin/env python3
"""生成一张纯色渐变封面，避免使用有版权的图片。

    python examples/make_cover.py examples/cover.png "告别 access_token"
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 900, 383  # 微信封面常用 2.35:1


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def build(out_path: str, text: str = "", c1=(28, 43, 78), c2=(86, 132, 214)) -> Path:
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):                      # 竖向渐变
        draw.line([(0, y), (W, y)], fill=lerp(c1, c2, y / H))
    draw.ellipse([W - 320, -140, W + 140, 320], fill=(255, 255, 255, 20))

    if text:
        font = None
        for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf", "arial.ttf"):
            try:
                font = ImageFont.truetype(name, 54)
                break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default()
        # 按宽度自动折行
        words, lines, cur = list(text), [], ""
        for ch in words:
            if draw.textlength(cur + ch, font=font) > W - 160:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
        lines = lines[:3]
        total = len(lines) * 72
        y = (H - total) // 2
        for line in lines:
            w = draw.textlength(line, font=font)
            draw.text(((W - w) / 2, y), line, font=font, fill=(255, 255, 255))
            y += 72

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p, "PNG")
    return p


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "examples/cover.png"
    title = sys.argv[2] if len(sys.argv) > 2 else "公众号草稿网关"
    print(build(out, title))
