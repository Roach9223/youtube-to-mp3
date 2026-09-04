"""Draw the app icon and save icon.ico plus icon.png.

Run: python make_icon.py            writes the chosen concept
     python make_icon.py B          writes concept B
     python make_icon.py sheet      writes docs/icon-concepts.png with every concept

F-16 palette, chamfered tile, a play button in the crosshairs.
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

SCREEN = (11, 13, 11)
PANEL = (74, 79, 82)
BEZEL = (38, 40, 43)
OLIVE = (62, 70, 40)
HUD = (77, 255, 77)
AMBER = (255, 176, 0)
WHITE = (230, 230, 230)
INK = (17, 17, 17)

CONCEPTS = {
    # every concept: crosshairs round a play symbol, F-16 colours
    "A": dict(tile=SCREEN, ring=HUD, play=HUD, chevron=AMBER),                   # thin ring, ticks, green play
    "B": dict(tile=SCREEN, ring=HUD, play=AMBER, tube=HUD, cross=True),          # full crosshair lines, tube outline, amber play
    "C": dict(tile=PANEL, ring=HUD, play=SCREEN, tube_fill=HUD, chevron=AMBER),  # gull gray, solid green tube, black play
}
CHOSEN = "C"


def chamfer(s, c):
    return [(c, 0), (s - c, 0), (s, c), (s, s - c), (s - c, s), (c, s), (0, s - c), (0, c)]


def note(d, s, cx, cy, scale, color, gap=False):
    """Eighth note centred near (cx, cy). scale 1.0 fills about 60% of the tile."""
    u = s / 100 * scale
    head_cx, head_cy = cx - 10 * u, cy + 18 * u
    stem_w = 8 * u
    stem_x = head_cx + 12 * u
    top = cy - 30 * u
    d.rounded_rectangle((stem_x - stem_w / 2, top, stem_x + stem_w / 2, head_cy), radius=stem_w / 2, fill=color)
    pts = []
    for i in range(0, 21):
        t = i / 20
        pts.append((stem_x + 22 * u * math.sin(t * math.pi * 0.85), top + 30 * u * t))
    for i in range(0, 21):
        t = 1 - i / 20
        pts.append((stem_x + 22 * u * math.sin(t * math.pi * 0.85) - 9 * u * (0.4 + 0.6 * (1 - t)), top + 30 * u * t + 4 * u))
    d.polygon(pts, fill=color)
    return head_cx, head_cy, 15 * u, 11 * u


def paste_head(img, s, head_cx, head_cy, rx, ry, color, tilt=20):
    head = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(head).ellipse((head_cx - rx, head_cy - ry, head_cx + rx, head_cy + ry), fill=color)
    img.alpha_composite(head.rotate(tilt, center=(head_cx, head_cy), resample=Image.BICUBIC))


def draw_icon(size: int, c: dict) -> Image.Image:
    ss = 8 if size <= 48 else 4  # heavier supersampling where every pixel counts
    s = size * ss
    u = s / 100
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon(chamfer(s, round(s * 0.14)), fill=c["tile"])
    # strokes never thinner than 1.4 real px, or they turn to haze in a taskbar
    lw = max(round(ss * 1.4), round(s * 0.022))

    cx = cy = s / 2
    r = s * 0.36
    ring = c["ring"]
    if c.get("cross"):  # hairlines across the whole tile, broken round the centre
        gap = s * 0.16
        for (x0, y0, x1, y1) in ((10 * u, cy, cx - gap, cy), (cx + gap, cy, s - 10 * u, cy),
                                 (cx, 10 * u, cx, cy - gap), (cx, cy + gap, cx, s - 10 * u)):
            d.line((x0, y0, x1, y1), fill=ring, width=lw)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ring, width=lw)
    for ang in ((0, 180, 270) if c.get("chevron") else (0, 90, 180, 270)):
        a = math.radians(ang)
        d.line((cx + (r - 7 * u) * math.cos(a), cy + (r - 7 * u) * math.sin(a),
                cx + (r + 7 * u) * math.cos(a), cy + (r + 7 * u) * math.sin(a)), fill=ring, width=lw)
    if c.get("chevron"):
        d.line((cx - 10 * u, cy + 30 * u, cx, cy + 39 * u, cx + 10 * u, cy + 30 * u), fill=c["chevron"],
               width=max(lw, round(s * 0.03)), joint="curve")
    # the play symbol, optionally inside a rounded "tube"
    tw, th = (46 * u, 32 * u) if size <= 24 else (34 * u, 24 * u)  # bigger target at taskbar sizes
    if c.get("tube_fill"):
        d.rounded_rectangle((cx - tw / 2, cy - th / 2, cx + tw / 2, cy + th / 2), radius=7 * u, fill=c["tube_fill"])
    elif c.get("tube"):
        d.rounded_rectangle((cx - tw / 2, cy - th / 2, cx + tw / 2, cy + th / 2), radius=7 * u, outline=c["tube"], width=lw)
    ph = (18 * u if size <= 24 else 13 * u) if (c.get("tube") or c.get("tube_fill")) else 22 * u
    pw = ph * 0.95
    px0 = cx - pw / 2 + 1.5 * u
    d.polygon([(px0, cy - ph / 2), (px0 + pw, cy), (px0, cy + ph / 2)], fill=c["play"])

    return img.resize((size, size), Image.LANCZOS)


def write_icon(c: dict) -> None:
    # every size Windows picks from at 100 / 125 / 150 / 200 percent scaling
    sizes = [256, 128, 96, 64, 48, 40, 32, 24, 20, 16]
    frames = [draw_icon(s, c) for s in sizes]
    out = Path(__file__).with_name("icon.ico")
    frames[0].save(out, format="ICO", sizes=[(s, s) for s in sizes], append_images=frames[1:])
    frames[0].save(out.with_name("icon.png"))
    print("wrote", out.name, "and icon.png")


def write_sheet() -> None:
    pad, tile = 40, 160
    small = [64, 32, 16]
    w = pad * 2 + len(CONCEPTS) * (tile + pad) + 40
    h = pad * 2 + tile + 90
    sheet = Image.new("RGB", (w, h), (30, 32, 34))
    d = ImageDraw.Draw(sheet)
    x = pad
    for key, c in CONCEPTS.items():
        big = draw_icon(tile, c)
        sheet.paste(big, (x, pad), big)
        sx = x
        for s in small:
            ic = draw_icon(s, c)
            sheet.paste(ic, (sx, pad + tile + 24 + (64 - s)), ic)
            sx += s + 12
        d.text((x, pad + tile + 24 + 70), key, fill=(200, 200, 200))
        x += tile + pad + 13
    out = Path(__file__).with_name("docs") / "icon-concepts.png"
    out.parent.mkdir(exist_ok=True)
    sheet.save(out)
    print("wrote", out)


if __name__ == "__main__":
    if "sheet" in sys.argv:
        write_sheet()
    else:
        write_icon(CONCEPTS[sys.argv[1] if len(sys.argv) > 1 else CHOSEN])
