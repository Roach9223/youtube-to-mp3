"""Draw the app icon (yellow tile, blue halftone, red disc, white note) and save icon.ico.

Run: python make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

YELLOW = (255, 212, 0)
BLUE = (30, 91, 255)
RED = (232, 35, 42)
INK = (17, 17, 17)
WHITE = (255, 255, 255)


def draw_icon(size: int) -> Image.Image:
    scale = 4  # draw big, shrink for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    border = max(2 * scale, round(s * 0.05))
    radius = round(s * 0.18)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=radius, fill=YELLOW, outline=INK, width=border)

    # halftone dots, clipped to the tile
    dots = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    step = max(6, round(s * 0.055))
    r = max(1, round(s * 0.011))
    for y in range(step // 2, s, step):
        for x in range(step // 2, s, step):
            dd.ellipse((x - r, y - r, x + r, y + r), fill=BLUE)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (border, border, s - 1 - border, s - 1 - border), radius=radius - border, fill=255)
    img.paste(dots, (0, 0), Image.composite(mask, Image.new("L", (s, s), 0), dots.split()[3]))

    # red disc
    inset = round(s * 0.12)
    d.ellipse((inset, inset, s - inset, s - inset), fill=RED, outline=INK, width=border)

    # eighth-note pair: stems, beam, two heads (in disc coordinates)
    stem_w = round(s * 0.06)
    x1, x2 = round(s * 0.40), round(s * 0.66)
    top1, top2 = round(s * 0.24), round(s * 0.19)
    bottom1, bottom2 = round(s * 0.66), round(s * 0.61)
    d.line((x1, top1, x1, bottom1), fill=INK, width=stem_w)
    d.line((x2, top2, x2, bottom2), fill=INK, width=stem_w)
    d.line((x1, top1, x2, top2), fill=INK, width=round(stem_w * 1.6))
    hw, hh = round(s * 0.12), round(s * 0.085)
    for (x, y) in ((x1 - round(s * 0.06), bottom1), (x2 - round(s * 0.06), bottom2)):
        d.ellipse((x - hw, y - hh, x + hw, y + hh), fill=WHITE, outline=INK, width=max(2, round(border * 0.8)))

    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [draw_icon(s) for s in sizes]
    out = Path(__file__).with_name("icon.ico")
    frames[0].save(out, format="ICO", sizes=[(s, s) for s in sizes], append_images=frames[1:])
    frames[0].save(out.with_name("icon.png"))
    print("wrote", out.name, "and icon.png")
