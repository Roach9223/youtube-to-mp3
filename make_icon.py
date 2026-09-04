"""Draw the app icon and save icon.ico plus icon.png.

Run: python make_icon.py            writes the chosen concept
     python make_icon.py sheet      also writes docs/icon-concepts.png with all three

The mark is an eighth note on a rounded tile with a small download badge, flat
and high contrast so it survives 16 px in a taskbar.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

RED = (232, 35, 42)
INK = (17, 17, 17)
WHITE = (255, 255, 255)
CREAM = (255, 246, 224)

CONCEPTS = {
    # tile, note, badge circle, badge arrow
    "A": dict(tile=INK, note=WHITE, head=RED, badge=WHITE, arrow=INK),
    "B": dict(tile=RED, note=WHITE, head=WHITE, badge=WHITE, arrow=RED),
    "C": dict(tile=CREAM, note=INK, head=INK, badge=RED, arrow=WHITE),
}
CHOSEN = "B"


def draw_icon(size: int, c: dict, badge: bool = True) -> Image.Image:
    ss = 4  # supersample for clean edges
    s = size * ss
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=round(s * 0.22), fill=c["tile"])

    # eighth note: head (tilted ellipse), stem, flag
    u = s / 100  # design units
    head_cx, head_cy = 40 * u, 68 * u
    head = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    hd = ImageDraw.Draw(head)
    hd.ellipse((head_cx - 15 * u, head_cy - 11 * u, head_cx + 15 * u, head_cy + 11 * u), fill=c["head"])
    head = head.rotate(20, center=(head_cx, head_cy), resample=Image.BICUBIC)
    stem_w = 8 * u
    stem_x = head_cx + 12 * u
    d.rounded_rectangle((stem_x - stem_w / 2, 20 * u, stem_x + stem_w / 2, head_cy), radius=stem_w / 2, fill=c["note"])
    # flag: a thick curve from the stem top sweeping down and right
    pts = []
    import math
    for i in range(0, 21):
        t = i / 20
        x = stem_x + 22 * u * math.sin(t * math.pi * 0.85)
        y = 20 * u + 30 * u * t
        pts.append((x, y))
    for i in range(0, 21):
        t = 1 - i / 20
        x = stem_x + 22 * u * math.sin(t * math.pi * 0.85) - 9 * u * (0.4 + 0.6 * (1 - t))
        y = 20 * u + 30 * u * t + 4 * u
        pts.append((x, y))
    d.polygon(pts, fill=c["note"])
    d.rounded_rectangle((stem_x - stem_w / 2, 20 * u, stem_x + stem_w / 2, 28 * u), radius=stem_w / 2, fill=c["note"])
    img.alpha_composite(head)

    if badge and size >= 32:
        bx, by, br = 76 * u, 76 * u, 16 * u
        d = ImageDraw.Draw(img)
        d.ellipse((bx - br - 3 * u, by - br - 3 * u, bx + br + 3 * u, by + br + 3 * u), fill=c["tile"])
        d.ellipse((bx - br, by - br, bx + br, by + br), fill=c["badge"])
        aw = 3.2 * u
        d.rounded_rectangle((bx - aw / 2, by - 9 * u, bx + aw / 2, by + 3 * u), radius=aw / 2, fill=c["arrow"])
        d.polygon([(bx - 7 * u, by + 1 * u), (bx + 7 * u, by + 1 * u), (bx, by + 9 * u)], fill=c["arrow"])

    return img.resize((size, size), Image.LANCZOS)


def write_icon(c: dict) -> None:
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [draw_icon(s, c) for s in sizes]
    out = Path(__file__).with_name("icon.ico")
    frames[0].save(out, format="ICO", sizes=[(s, s) for s in sizes], append_images=frames[1:])
    frames[0].save(out.with_name("icon.png"))
    print("wrote", out.name, "and icon.png")


def write_sheet() -> None:
    pad, tile = 40, 160
    small = [64, 32, 16]
    w = pad * 2 + 3 * (tile + pad) + 40
    h = pad * 2 + tile + 90
    sheet = Image.new("RGB", (w, h), (246, 241, 234))
    d = ImageDraw.Draw(sheet)
    x = pad
    for key, c in CONCEPTS.items():
        sheet.paste(draw_icon(tile, c), (x, pad), draw_icon(tile, c))
        sx = x
        for s in small:
            ic = draw_icon(s, c)
            sheet.paste(ic, (sx, pad + tile + 24 + (64 - s)), ic)
            sx += s + 12
        d.text((x, pad + tile + 24 + 70), f"{key}{'  (chosen)' if key == CHOSEN else ''}", fill=(60, 60, 60))
        x += tile + pad + 13
    out = Path(__file__).with_name("docs") / "icon-concepts.png"
    out.parent.mkdir(exist_ok=True)
    sheet.save(out)
    print("wrote", out)


if __name__ == "__main__":
    if "sheet" in sys.argv:
        write_sheet()
    write_icon(CONCEPTS[CHOSEN])
