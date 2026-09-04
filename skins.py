"""Skins for YouTube to MP3.

A skin owns its palette, fonts, copy, background image and the shape primitives
the app draws with: boxes (fields, buttons, chips, panels), the status badge,
the progress bar and the header. The app keeps the layout and the behaviour;
switching skins only changes how those pieces are painted.

Every coordinate here is in design px (a 560 x 520 window). Skins convert to
real pixels through app.px(), which carries the display scale.
"""

import math

from PIL import Image, ImageDraw, ImageFilter

W, H = 560, 520
PROGRESS = (34, 344, 500, 16)  # x, y, w, h of the bar


# ---- colour and geometry helpers ----

def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(c):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in c)


def mix(a: str, b: str, t: float) -> str:
    """Blend colour a toward colour b by t (0..1)."""
    ca, cb = _rgb(a), _rgb(b)
    return _hex(tuple(ca[i] + (cb[i] - ca[i]) * t for i in range(3)))


def rounded_points(x, y, w, h, r, steps=6):
    r = max(0, min(r, w / 2, h / 2))
    corners = [(x + w - r, y + r, -90, 0), (x + w - r, y + h - r, 0, 90),
               (x + r, y + h - r, 90, 180), (x + r, y + r, 180, 270)]
    pts = []
    for cx, cy, a0, a1 in corners:
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def chamfer_points(x, y, w, h, c):
    c = max(0, min(c, w / 2, h / 2))
    return [(x + c, y), (x + w - c, y), (x + w, y + c), (x + w, y + h - c),
            (x + w - c, y + h), (x + c, y + h), (x, y + h - c), (x, y + c)]


def rotate(points, cx, cy, deg):
    a = math.radians(deg)
    out = []
    for x, y in points:
        dx, dy = x - cx, y - cy
        out.append((cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)))
    return out


def flat(app, pts):
    return [app.px(v) for pt in pts for v in pt]


# ---- base skin: Direction A, comic pop art ----

class Skin:
    key = "pop"
    name = "POP ART"

    bg = "#FFF6E0"
    ink = "#111111"        # borders
    text = "#111111"
    muted = "#6B6B6B"
    placeholder = "#8A8A8A"
    surface = "#FFFFFF"    # fields, neutral buttons
    field = "#FFF6E0"      # read-only field (the folder path)
    primary = "#E8232A"
    primary_fg = "#FFFFFF"
    accent = "#FFD400"     # the paste button
    accent_fg = "#111111"
    accent2 = "#1E5BFF"    # the done badge
    accent2_fg = "#FFFFFF"
    working = "#FFD400"      # the working badge
    working_fg = "#111111"
    cancel = "#111111"
    cancel_fg = "#FFFFFF"
    error = "#E8232A"
    error_fg = "#FFFFFF"
    disabled = "#CFCFCF"
    disabled_fg = "#7A7A7A"
    hover = {"#E8232A": "#C1121F", "#FFD400": "#E6BE00", "#FFFFFF": "#F1EAD6", "#111111": "#2E2E2E"}

    border = 3
    border_thin = 2
    shadows = {"lg": 6, "md": 4, "sm": 3}
    display_scale = 1.0
    animated = False

    families = {
        "display": ("Archivo Black", "Impact"),
        "body": ("Space Grotesk", "Segoe UI"),
        "body_bold": ("Space Grotesk", "Segoe UI"),
        "mono": ("Space Mono", "Consolas"),
        "mono_bold": ("Space Mono", "Consolas"),
    }
    body_bold_weight = "bold"
    mono_bold_weight = "bold"

    copy = {
        "tagline": "Best audio stream. MP3 at V0.\nSquare cover art baked in.",
        "url_hint": "Paste a YouTube link", "paste": "PASTE", "save_to": "SAVE TO",
        "browse": "BROWSE", "ask": "Ask where to save each time", "convert": "CONVERT",
        "cancel": "CANCEL", "cancelling": "CANCELLING…", "ready": "Ready",
        "starting": "STARTING", "starting_detail": "Asking YouTube for the audio stream",
        "downloading": "DOWNLOADING", "converting": "CONVERTING TO MP3",
        "cancel_title": "CANCELLING", "cancel_detail": "Stopping the download and cleaning up",
        "close_detail": "The window will close in a moment", "cancelled": "Cancelled",
        "done": "DONE", "show": "SHOW IN FOLDER", "error": "ERROR",
        "update": "UPDATE YT-DLP", "get_update": "GET UPDATE", "updating": "UPDATING…",
        "update_title": "UPDATING YT-DLP", "update_detail": "Fetching the latest release with pip",
        "ffmpeg_ok": "FFMPEG OK", "ffmpeg_missing": "FFMPEG MISSING",
    }

    def hover_color(self, fill):
        return self.hover.get(fill, fill)

    def button_glow(self, fill):
        return None

    # -- background --

    def background(self, k: float) -> Image.Image:
        img = Image.new("RGB", (round(W * k), round(H * k)), self.bg)

        def dot_field(color, fw, fh, step, r, angle):
            tile = Image.new("RGBA", (round(fw * k), round(fh * k)), (0, 0, 0, 0))
            d = ImageDraw.Draw(tile)
            s, rr = step * k, r * k
            y = s / 2
            while y < tile.height:
                x = s / 2
                while x < tile.width:
                    d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=color)
                    x += s
                y += s
            return tile.rotate(angle, expand=True, resample=Image.BICUBIC)

        def paste_centered(field, cx, cy):
            img.paste(field, (round(cx * k - field.width / 2), round(cy * k - field.height / 2)), field)

        paste_centered(dot_field(self.accent2, 300, 230, 11, 1.7, 9), 470, 45)
        paste_centered(dot_field(self.primary, 230, 170, 12, 1.9, 9), 65, 495)
        ImageDraw.Draw(img).rectangle((0, 0, round(14 * k), img.height), fill=self.ink)
        return img

    # -- shapes --

    def box(self, app, x, y, w, h, fill, outline=None, border=None, shadow=None,
            shadow_color=None, tags=(), glow=None, kind="box"):
        p, c = app.px, app.c
        outline = outline or self.ink
        sh = self.shadows.get(shadow, 0)
        if sh:
            c.create_rectangle(p(x + sh), p(y + sh), p(x + w + sh), p(y + h + sh),
                               fill=shadow_color or self.ink, outline=shadow_color or self.ink, tags=tags)
        b = p(border if border is not None else self.border)
        half = b / 2  # keep the stroke inside the box, the way CSS borders sit
        return c.create_rectangle(p(x) + half, p(y) + half, p(x + w) - half, p(y + h) - half,
                                  fill=fill, outline=outline, width=b, tags=tags)

    STAR = [(50, 0), (61, 14), (79, 8), (80, 27), (98, 35), (88, 50), (98, 65), (80, 73), (79, 92),
            (61, 86), (50, 100), (39, 86), (21, 92), (20, 73), (2, 65), (12, 50), (2, 35), (20, 27),
            (21, 8), (39, 14)]

    def badge(self, app, x, y, size, label, bg, fg, font, angle=-8, tags=()):
        cx, cy = x + size / 2, y + size / 2

        def points(scale):
            pts = [(cx + (sx / 100 - 0.5) * size * scale, cy + (sy / 100 - 0.5) * size * scale)
                   for sx, sy in self.STAR]
            return flat(app, rotate(pts, cx, cy, angle))

        app.c.create_polygon(points(1.0), fill=self.ink, outline=self.ink, tags=tags)
        app.c.create_polygon(points((size - 9) / size), fill=bg, outline=bg, tags=tags)
        app.c.create_text(app.px(cx), app.px(cy), text=label, font=app.fonts[font], fill=fg,
                          angle=-angle, tags=tags)

    def progress(self, app, frac, striped, phase, tags=("prog",)):
        x, y, w, h = PROGRESS
        p, c = app.px, app.c
        self.box(app, x, y, w, h, self.surface, tags=tags)
        if frac <= 0:
            return
        b = self.border
        ix, iy, iw, ih = x + b, y + b, w - 2 * b, h - 2 * b
        fw = iw * frac
        c.create_rectangle(p(ix), p(iy), p(ix + fw), p(iy + ih), fill=self.primary, outline=self.primary, tags=tags)
        if not striped:
            return
        sx = ix
        while sx < ix + fw:
            x1, y1 = sx + ih, iy
            if x1 > ix + fw:  # clip the last stripe at the fill edge
                t = (ix + fw - sx) / ih
                x1, y1 = ix + fw, iy + ih - t * ih
            c.create_line(p(sx), p(iy + ih), p(x1), p(y1), fill=self.ink, width=p(4), capstyle="butt", tags=tags)
            sx += 14

    def header(self, app):
        f = app.fonts["wordmark"]
        x, y, h, pad = 34, 24, 36, 10
        px0, py0 = x, y + 2 * h

        def block(bx, by, label, fill, fg):
            bw = f.measure(label) / app.k + 2 * pad
            pts = rotate([(bx, by), (bx + bw, by), (bx + bw, by + h), (bx, by + h)], px0, py0, -2)
            app.c.create_polygon(flat(app, pts), fill=fill, outline=self.ink, width=app.px(3))
            cx, cy = rotate([(bx + bw / 2, by + h / 2 + 1)], px0, py0, -2)[0]
            app.c.create_text(app.px(cx), app.px(cy), text=label, font=f, fill=fg, angle=2)

        block(x, y, "YOUTUBE", self.accent, self.ink)
        block(x + 14, y + h - 3, "TO MP3", self.primary, self.primary_fg)

        bx, by, bw, bh = 262, 28, 272, 46
        self.box(app, bx, by, bw, bh, self.surface, shadow="sm")
        ty, p = by + bh - 18, app.px
        app.c.create_polygon(p(bx - 14), p(ty), p(bx + 2), p(ty - 8), p(bx + 2), p(ty + 8), fill=self.ink, outline=self.ink)
        app.c.create_polygon(p(bx - 8), p(ty), p(bx + 4), p(ty - 5), p(bx + 4), p(ty + 5), fill=self.surface, outline=self.surface)
        app.text(bx + 12, by + bh / 2, self.copy["tagline"], "body12b", anchor="w")

    def tick(self, app, phase):
        pass


# ---- Black Ops: covert, matte, stencil ----

class BlackOps(Skin):
    key = "ops"
    name = "BLACK OPS"

    bg = "#0C0E0C"
    ink = "#C8B98A"
    text = "#E6DFC8"
    muted = "#8E8A73"
    placeholder = "#5E5B4B"
    surface = "#161916"
    field = "#111411"
    primary = "#5C6B3A"
    primary_fg = "#F2EEDC"
    accent = "#C8B98A"
    accent_fg = "#0C0E0C"
    accent2 = "#5C6B3A"
    accent2_fg = "#F2EEDC"
    working = "#0C0E0C"
    working_fg = "#C8B98A"
    cancel = "#2A2D2A"
    cancel_fg = "#E6DFC8"
    error = "#B5483B"
    error_fg = "#F2EEDC"
    disabled = "#1C1F1C"
    disabled_fg = "#5E5B4B"
    hover = {"#5C6B3A": "#6E8046", "#C8B98A": "#DACCA3", "#161916": "#212521", "#2A2D2A": "#373B37"}

    border = 1
    border_thin = 1
    shadows = {}

    families = {
        "display": ("Black Ops One", "Impact"),
        "body": ("Barlow Medium", "Segoe UI"),
        "body_bold": ("Barlow SemiBold", "Segoe UI"),
        "mono": ("Share Tech Mono", "Consolas"),
        "mono_bold": ("Share Tech Mono", "Consolas"),
    }
    body_bold_weight = "normal"
    mono_bold_weight = "normal"

    copy = {**Skin.copy, "tagline": "BEST STREAM  //  MP3 V0  //  SQUARE COVER",
            "url_hint": "Enter target URL", "paste": "PASTE", "save_to": "DROP ZONE",
            "browse": "BROWSE", "ask": "Confirm drop zone before each run", "convert": "EXECUTE",
            "cancel": "ABORT", "cancelling": "ABORTING…", "ready": "Standing by",
            "starting": "ACQUIRING", "downloading": "EXTRACTING", "converting": "ENCODING",
            "cancel_title": "ABORTING", "cancelled": "Aborted", "done": "DONE",
            "show": "OPEN DROP ZONE", "error": "FAILED", "ffmpeg_ok": "FFMPEG ONLINE",
            "ffmpeg_missing": "FFMPEG OFFLINE"}

    def background(self, k):
        w, h = round(W * k), round(H * k)
        img = Image.new("RGB", (w, h), self.bg)
        d = ImageDraw.Draw(img)
        hatch = mix(self.bg, self.ink, 0.045)
        step = round(7 * k)
        for x in range(-h, w, step):  # fine diagonal hatch
            d.line((x, 0, x + h, h), fill=hatch, width=1)
        band = mix(self.bg, self.ink, 0.09)
        d.rectangle((0, 0, w, round(6 * k)), fill=band)
        d.rectangle((0, h - round(6 * k), w, h), fill=band)
        # corner brackets
        L, t = round(18 * k), max(1, round(2 * k))
        m = round(12 * k)
        for (cx, cy, sx, sy) in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            d.line((cx, cy, cx + L * sx, cy), fill=self.ink, width=t)
            d.line((cx, cy, cx, cy + L * sy), fill=self.ink, width=t)
        return img

    def box(self, app, x, y, w, h, fill, outline=None, border=None, shadow=None,
            shadow_color=None, tags=(), glow=None, kind="box"):
        p, c = app.px, app.c
        outline = outline or self.ink
        b = max(1, p(border if border is not None else self.border))
        half = b / 2
        item = c.create_rectangle(p(x) + half, p(y) + half, p(x + w) - half, p(y + h) - half,
                                  fill=fill, outline=outline, width=b, tags=tags)
        if kind == "button" and h >= 30:
            L, t = 6, max(1, p(2))
            for (cx, cy, sx, sy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
                c.create_line(p(cx), p(cy), p(cx + L * sx), p(cy), fill=outline, width=t, tags=tags)
                c.create_line(p(cx), p(cy), p(cx), p(cy + L * sy), fill=outline, width=t, tags=tags)
        return item

    def badge(self, app, x, y, size, label, bg, fg, font, angle=-8, tags=()):
        cx, cy = x + size / 2, y + size / 2
        w, h = size, size * 0.56
        outer = rotate([(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)], cx, cy, angle)
        inner = rotate([(cx - w / 2 + 4, cy - h / 2 + 4), (cx + w / 2 - 4, cy - h / 2 + 4), (cx + w / 2 - 4, cy + h / 2 - 4), (cx - w / 2 + 4, cy + h / 2 - 4)], cx, cy, angle)
        app.c.create_polygon(flat(app, outer), fill=self.bg, outline=fg, width=max(1, app.px(2)), tags=tags)
        app.c.create_polygon(flat(app, inner), fill="", outline=fg, width=max(1, app.px(1)), tags=tags)
        app.c.create_text(app.px(cx), app.px(cy), text=label, font=app.fonts[font], fill=fg, angle=-angle, tags=tags)

    def progress(self, app, frac, striped, phase, tags=("prog",)):
        x, y, w, h = PROGRESS
        p, c = app.px, app.c
        self.box(app, x, y, w, h, self.surface, tags=tags)
        n, gap = 40, 2
        ix, iy, iw, ih = x + 3, y + 3, w - 6, h - 6
        seg = (iw - gap * (n - 1)) / n
        filled = round(frac * n)
        for i in range(n):
            sx = ix + i * (seg + gap)
            if i < filled:
                color = self.ink
            elif i == filled and striped:
                color = mix(self.surface, self.ink, 0.5 if phase % 2 else 0.15)
            else:
                continue
            c.create_rectangle(p(sx), p(iy), p(sx + seg), p(iy + ih), fill=color, outline=color, tags=tags)

    def header(self, app):
        p = app.px
        app.text(34, 26, "YOUTUBE // MP3", "wordmark", fill=self.ink)
        # redaction bar
        self.box(app, 34, 64, 214, 10, self.ink, tags=())
        app.text(34, 82, self.copy["tagline"], "mono12", fill=self.muted, anchor="nw")
        # stamp at right
        cx, cy, w, h = 462, 46, 144, 40
        outer = rotate([(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)], cx, cy, -6)
        inner = rotate([(cx - w / 2 + 4, cy - h / 2 + 4), (cx + w / 2 - 4, cy - h / 2 + 4), (cx + w / 2 - 4, cy + h / 2 - 4), (cx - w / 2 + 4, cy + h / 2 - 4)], cx, cy, -6)
        app.c.create_polygon(flat(app, outer), fill="", outline=self.error, width=max(1, p(2)))
        app.c.create_polygon(flat(app, inner), fill="", outline=self.error, width=max(1, p(1)))
        app.c.create_text(p(cx), p(cy - 7), text="COVERT AUDIO OPS", font=app.fonts["display13"], fill=self.error, angle=6)
        app.c.create_text(p(cx), p(cy + 9), text="EYES ONLY", font=app.fonts["label11b"], fill=self.error, angle=6)


# ---- Fighter Jet: cockpit HUD with lights ----

class FighterJet(Skin):
    key = "jet"
    name = "FIGHTER JET"

    bg = "#0A1220"
    ink = "#39E0FF"
    text = "#D8F6FF"
    muted = "#6FA3B5"
    placeholder = "#3F6B7A"
    surface = "#0F1B2E"
    field = "#0C1626"
    primary = "#FFB000"
    primary_fg = "#0A1220"
    accent = "#39E0FF"
    accent_fg = "#0A1220"
    accent2 = "#39E0FF"
    accent2_fg = "#0A1220"
    working = "#FFB000"
    working_fg = "#0A1220"
    cancel = "#0F1B2E"
    cancel_fg = "#39E0FF"
    error = "#FF4D4D"
    error_fg = "#0A1220"
    disabled = "#15243C"
    disabled_fg = "#3F6B7A"
    hover = {"#FFB000": "#FFC43D", "#39E0FF": "#7FEBFF", "#0F1B2E": "#15243C"}

    border = 1
    border_thin = 1
    shadows = {}
    chamfer = 8
    display_scale = 0.82
    animated = True

    families = {
        "display": ("Michroma", "Impact"),
        "body": ("Rajdhani Medium", "Segoe UI"),
        "body_bold": ("Rajdhani SemiBold", "Segoe UI"),
        "mono": ("Share Tech Mono", "Consolas"),
        "mono_bold": ("Share Tech Mono", "Consolas"),
    }
    body_bold_weight = "normal"
    mono_bold_weight = "normal"

    copy = {**Skin.copy, "tagline": "BEST STREAM  //  MP3 V0  //  SQUARE COVER",
            "url_hint": "Lock a YouTube link", "paste": "PASTE", "save_to": "LANDING ZONE",
            "browse": "BROWSE", "ask": "Confirm landing zone every sortie", "convert": "ENGAGE",
            "cancel": "ABORT", "cancelling": "ABORTING…", "ready": "Systems nominal",
            "starting": "SPOOLING UP", "downloading": "DOWNLINK", "converting": "ENCODING",
            "cancel_title": "ABORTING", "cancelled": "Aborted", "done": "LANDED",
            "show": "OPEN LANDING ZONE", "error": "WARNING", "ffmpeg_ok": "FFMPEG ONLINE",
            "ffmpeg_missing": "FFMPEG OFFLINE"}

    def button_glow(self, fill):
        return fill if fill in (self.primary, self.accent, self.ink) else None

    def background(self, k):
        w, h = round(W * k), round(H * k)
        img = Image.new("RGB", (w, h), self.bg)
        d = ImageDraw.Draw(img)
        top, bottom = _rgb("#070B14"), _rgb("#101C33")
        for y in range(h):  # vertical gradient
            t = y / h
            d.line((0, y, w, y), fill=_hex(tuple(top[i] + (bottom[i] - top[i]) * t for i in range(3))))
        grid = mix(self.bg, self.ink, 0.07)
        step = round(20 * k)
        for x in range(0, w, step):
            d.line((x, 0, x, h), fill=grid, width=1)
        for y in range(0, h, step):
            d.line((0, y, w, y), fill=grid, width=1)
        # horizon arc, faint
        arc = mix(self.bg, self.ink, 0.16)
        r = round(W * 0.9 * k)
        cx, cy = round(W / 2 * k), round(H * 1.35 * k)
        d.arc((cx - r, cy - r, cx + r, cy + r), 200, 340, fill=arc, width=max(1, round(1.5 * k)))
        # scanlines
        scan = mix(self.bg, "#000000", 0.25)
        for y in range(0, h, max(2, round(3 * k))):
            d.line((0, y, w, y), fill=scan, width=1)
        # corner brackets
        L, t, m = round(22 * k), max(1, round(2 * k)), round(10 * k)
        for (bx, by, sx, sy) in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            d.line((bx, by, bx + L * sx, by), fill=self.ink, width=t)
            d.line((bx, by, bx, by + L * sy), fill=self.ink, width=t)
        return img

    def box(self, app, x, y, w, h, fill, outline=None, border=None, shadow=None,
            shadow_color=None, tags=(), glow=None, kind="box"):
        p, c = app.px, app.c
        outline = outline or self.ink
        ch = self.chamfer if kind in ("button", "panel") else 4
        if glow:
            for i, (grow, t) in enumerate(((7, 0.10), (4, 0.20), (2, 0.34))):
                pts = chamfer_points(x - grow, y - grow, w + 2 * grow, h + 2 * grow, ch + grow * 0.6)
                c.create_polygon(flat(app, pts), fill=mix(self.bg, glow, t), outline="",
                                 tags=tags + ((tags[0] + f":glow{i}",) if tags else ()))
        b = max(1, p(border if border is not None else self.border))
        return c.create_polygon(flat(app, chamfer_points(x, y, w, h, ch)), fill=fill, outline=outline,
                                width=b, tags=tags)

    def badge(self, app, x, y, size, label, bg, fg, font, angle=-8, tags=()):
        cx, cy, r = x + size / 2, y + size / 2, size / 2
        hexa = [(cx + r * math.cos(math.radians(60 * i - 90)), cy + r * math.sin(math.radians(60 * i - 90))) for i in range(6)]
        for grow, t in ((8, 0.12), (4, 0.25)):
            g = [(cx + (r + grow) * math.cos(math.radians(60 * i - 90)), cy + (r + grow) * math.sin(math.radians(60 * i - 90))) for i in range(6)]
            app.c.create_polygon(flat(app, g), fill=mix(self.bg, bg, t), outline="", tags=tags)
        app.c.create_polygon(flat(app, hexa), fill=bg, outline=self.text, width=max(1, app.px(1)), tags=tags)
        app.c.create_text(app.px(cx), app.px(cy), text=label, font=app.fonts[font], fill=fg, tags=tags)

    def progress(self, app, frac, striped, phase, tags=("prog",)):
        x, y, w, h = PROGRESS
        p, c = app.px, app.c
        self.box(app, x, y, w, h, self.surface, tags=tags)
        ix, iy, iw, ih = x + 3, y + 3, w - 6, h - 6
        # tick ladder along the top edge
        for i in range(0, 11):
            tx = x + i * w / 10
            c.create_line(p(tx), p(y - 5), p(tx), p(y - 1), fill=self.muted, width=1, tags=tags)
        if frac <= 0:
            return
        fw = iw * frac
        c.create_rectangle(p(ix), p(iy), p(ix + fw), p(iy + ih), fill=self.ink, outline=self.ink, tags=tags)
        if not striped:
            return
        off = (phase * 2) % 12
        sx = ix - 12 + off
        while sx < ix + fw - 6:
            if sx >= ix:
                c.create_line(p(sx), p(iy), p(sx + 5), p(iy + ih / 2), p(sx), p(iy + ih), fill=self.bg, width=p(2), tags=tags)
            sx += 12

    def header(self, app):
        p, c = app.px, app.c
        glow = mix(self.bg, self.ink, 0.35)
        for dx, dy in ((1, 1), (-1, -1), (1, -1), (-1, 1)):
            c.create_text(p(34 + dx), p(30 + dy), text="YOUTUBE / MP3", font=app.fonts["wordmark"], fill=glow, anchor="nw")
        c.create_text(p(34), p(30), text="YOUTUBE / MP3", font=app.fonts["wordmark"], fill=self.ink, anchor="nw")
        y = 66
        c.create_line(p(34), p(y), p(534), p(y), fill=self.ink, width=1)
        for i in range(0, 26):
            tx = 34 + i * 20
            c.create_line(p(tx), p(y), p(tx), p(y - (7 if i % 5 == 0 else 3)), fill=self.ink, width=1)
        app.text(34, 76, self.copy["tagline"], "body12b", fill=self.muted)
        # indicator lights
        for i, (label, lx) in enumerate((("PWR", 452), ("NET", 486), ("FFM", 520))):
            c.create_oval(p(lx - 5), p(31), p(lx + 5), p(41), fill="#1E3A2C", outline=self.muted, width=1, tags=(f"led:{i}",))
            app.text(lx, 50, label, "label11b", fill=self.muted, anchor="center")

    def tick(self, app, phase):
        c = app.c
        green, red, off = "#3DFF8A", "#FF4D4D", "#1E3A2C"
        c.itemconfigure("led:0", fill=green)
        c.itemconfigure("led:1", fill=green if (phase // 4) % 3 else off)
        if app.ffmpeg:
            c.itemconfigure("led:2", fill=green)
        else:
            c.itemconfigure("led:2", fill=red if phase % 6 < 3 else off)
        # breathing glow on the main button
        b = app.buttons.get("convert")
        if b and b["enabled"]:
            t = 0.55 + 0.45 * math.sin(phase / 6)
            for i, base in enumerate((0.10, 0.20, 0.34)):
                c.itemconfigure(f"btn:convert:glow{i}", fill=mix(self.bg, b["fill"], base * t))
        if app.converting and app.progress_state[1]:
            app.redraw_progress()


# ---- Chill: soft, rounded, low contrast ----

class Chill(Skin):
    key = "chill"
    name = "chill"

    bg = "#F6F1EA"
    ink = "#DDD4C8"
    text = "#3B3550"
    muted = "#8A8399"
    placeholder = "#B3ACBE"
    surface = "#FFFFFF"
    field = "#FBF8F3"
    primary = "#8FB99A"
    primary_fg = "#1F2A22"
    accent = "#F4B08C"
    accent_fg = "#3B2A22"
    accent2 = "#B9AEE8"
    accent2_fg = "#2C2542"
    working = "#F4B08C"
    working_fg = "#3B2A22"
    cancel = "#E8E1F5"
    cancel_fg = "#3B3550"
    error = "#E07A7A"
    error_fg = "#3B3550"
    disabled = "#ECE7E0"
    disabled_fg = "#B3ACBE"
    hover = {"#8FB99A": "#7FAA8B", "#F4B08C": "#EF9F78", "#FFFFFF": "#FBF7F1", "#E8E1F5": "#DED5F0"}
    shadow_color = "#E9E1D6"

    border = 2
    border_thin = 2
    shadows = {"lg": 6, "md": 4, "sm": 3}
    radius = 14

    families = {
        "display": ("Varela Round", "Segoe UI"),
        "body": ("Varela Round", "Segoe UI"),
        "body_bold": ("Varela Round", "Segoe UI"),
        "mono": ("DM Mono", "Consolas"),
        "mono_bold": ("DM Mono Medium", "Consolas"),
    }
    body_bold_weight = "normal"
    mono_bold_weight = "normal"

    copy = {**Skin.copy, "tagline": "best audio  ·  mp3 v0  ·  square cover art",
            "url_hint": "paste a youtube link", "paste": "paste", "save_to": "save to",
            "browse": "browse", "ask": "ask where to save each time", "convert": "convert",
            "cancel": "stop", "cancelling": "stopping…", "ready": "ready when you are",
            "starting": "starting", "starting_detail": "asking youtube for the audio",
            "downloading": "downloading", "converting": "converting to mp3",
            "cancel_title": "stopping", "cancel_detail": "cleaning up", "close_detail": "closing in a moment",
            "cancelled": "stopped", "done": "done", "show": "show in folder", "error": "hmm",
            "update": "update yt-dlp", "get_update": "get update", "updating": "updating…",
            "update_title": "updating yt-dlp", "update_detail": "fetching the latest release",
            "ffmpeg_ok": "ffmpeg ok", "ffmpeg_missing": "ffmpeg missing"}

    def background(self, k):
        w, h = round(W * k), round(H * k)
        img = Image.new("RGB", (w, h), self.bg)
        blobs = Image.new("RGB", (w, h), self.bg)
        d = ImageDraw.Draw(blobs)
        for (cx, cy, r, color) in ((500, 60, 150, "#F8D3BE"), (60, 470, 130, "#DCD5F3"), (520, 470, 110, "#D4E6D8")):
            d.ellipse((round((cx - r) * k), round((cy - r) * k), round((cx + r) * k), round((cy + r) * k)), fill=color)
        blobs = blobs.filter(ImageFilter.GaussianBlur(radius=45 * k))
        return Image.blend(img, blobs, 0.85)

    def _radius(self, kind, h):
        if kind == "chip":
            return 12
        if kind == "panel":
            return 16
        return min(self.radius, h / 2)

    def box(self, app, x, y, w, h, fill, outline=None, border=None, shadow=None,
            shadow_color=None, tags=(), glow=None, kind="box"):
        c = app.c
        r = self._radius(kind, h)
        sh = self.shadows.get(shadow, 0)
        if sh:
            c.create_polygon(flat(app, rounded_points(x, y + sh, w, h, r)), fill=shadow_color or self.shadow_color,
                             outline="", tags=tags)
        b = max(1, app.px(border if border is not None else self.border))
        return c.create_polygon(flat(app, rounded_points(x, y, w, h, r)), fill=fill, outline=outline or self.ink,
                                width=b, tags=tags)

    def badge(self, app, x, y, size, label, bg, fg, font, angle=-8, tags=()):
        p = app.px
        app.c.create_oval(p(x), p(y + 4), p(x + size), p(y + size + 4), fill=self.shadow_color, outline="", tags=tags)
        app.c.create_oval(p(x), p(y), p(x + size), p(y + size), fill=bg, outline="", tags=tags)
        app.c.create_text(p(x + size / 2), p(y + size / 2), text=label, font=app.fonts[font], fill=fg, tags=tags)

    def progress(self, app, frac, striped, phase, tags=("prog",)):
        x, y, w, h = PROGRESS
        c = app.c
        c.create_polygon(flat(app, rounded_points(x, y, w, h, 8)), fill=self.surface, outline=self.ink,
                         width=max(1, app.px(2)), tags=tags)
        if frac <= 0:
            return
        fw = max(10, (w - 6) * frac)
        c.create_polygon(flat(app, rounded_points(x + 3, y + 3, fw, h - 6, 5)), fill=self.primary, outline="", tags=tags)

    def header(self, app):
        app.text(34, 24, "youtube to mp3", "wordmark")
        f = app.fonts["body12b"]
        tw = f.measure(self.copy["tagline"]) / app.k + 28
        self.box(app, 34, 66, tw, 26, self.accent2, border=0, kind="chip")
        app.text(34 + tw / 2, 79, self.copy["tagline"], "body12b", fill=self.accent2_fg, anchor="center")


# ---- Blueprint: drafting sheet ----

class Blueprint(Skin):
    key = "blueprint"
    name = "BLUEPRINT"

    bg = "#17418F"
    ink = "#FFFFFF"
    text = "#FFFFFF"
    muted = "#A9BEE6"
    placeholder = "#7F9BD1"
    surface = "#1B4A9F"
    field = "#173F8A"
    primary = "#FFFFFF"
    primary_fg = "#17418F"
    accent = "#1B4A9F"
    accent_fg = "#FFFFFF"
    accent2 = "#FFFFFF"
    accent2_fg = "#17418F"
    working = "#17418F"
    working_fg = "#FFFFFF"
    cancel = "#17418F"
    cancel_fg = "#FFFFFF"
    error = "#FFB4AA"
    error_fg = "#17418F"
    disabled = "#2B5199"
    disabled_fg = "#7F9BD1"
    hover = {"#FFFFFF": "#E4ECFA", "#1B4A9F": "#2458B4", "#17418F": "#2458B4"}

    border = 2
    border_thin = 1
    shadows = {}

    families = {
        "display": ("Architects Daughter", "Segoe Print"),
        "body": ("Architects Daughter", "Segoe UI"),
        "body_bold": ("Architects Daughter", "Segoe UI"),
        "mono": ("Courier Prime", "Consolas"),
        "mono_bold": ("Courier Prime", "Consolas"),
    }
    body_bold_weight = "normal"
    mono_bold_weight = "bold"

    copy = {**Skin.copy, "tagline": "DWG 001  ·  REV A  ·  BEST STREAM  ·  MP3 V0  ·  SQUARE COVER",
            "url_hint": "Paste a YouTube link here", "save_to": "OUTPUT FOLDER",
            "convert": "CONVERT", "cancel": "CANCEL", "ready": "Ready to draft",
            "starting": "STARTING", "downloading": "DOWNLOADING", "converting": "ENCODING",
            "done": "DONE", "show": "OPEN FOLDER", "error": "ERROR"}

    def background(self, k):
        w, h = round(W * k), round(H * k)
        img = Image.new("RGB", (w, h), self.bg)
        d = ImageDraw.Draw(img)
        minor, major = mix(self.bg, self.ink, 0.07), mix(self.bg, self.ink, 0.16)
        s = round(10 * k)
        for i, x in enumerate(range(0, w, s)):
            d.line((x, 0, x, h), fill=major if i % 5 == 0 else minor, width=1)
        for i, y in enumerate(range(0, h, s)):
            d.line((0, y, w, y), fill=major if i % 5 == 0 else minor, width=1)
        m, t = round(12 * k), max(1, round(2 * k))
        d.rectangle((m, m, w - m, h - m), outline=self.ink, width=t)
        d.rectangle((m + round(4 * k), m + round(4 * k), w - m - round(4 * k), h - m - round(4 * k)),
                    outline=mix(self.bg, self.ink, 0.5), width=1)
        return img

    def box(self, app, x, y, w, h, fill, outline=None, border=None, shadow=None,
            shadow_color=None, tags=(), glow=None, kind="box"):
        p, c = app.px, app.c
        outline = outline or self.ink
        b = max(1, p(border if border is not None else self.border))
        half = b / 2
        dash = (6, 4) if kind == "field" else None
        item = c.create_rectangle(p(x) + half, p(y) + half, p(x + w) - half, p(y + h) - half,
                                  fill=fill, outline=outline, width=b, tags=tags, dash=dash)
        if kind == "button" and fill == self.primary:
            c.create_rectangle(p(x + 4), p(y + 4), p(x + w - 4), p(y + h - 4), fill="", outline=self.bg,
                               width=1, tags=tags)
        return item

    def badge(self, app, x, y, size, label, bg, fg, font, angle=-8, tags=()):
        p = app.px
        cx, cy, r = x + size / 2, y + size / 2, size / 2 - 4
        app.c.create_oval(p(cx - r), p(cy - r), p(cx + r), p(cy + r), fill=bg, outline=fg, width=max(1, p(2)), tags=tags)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            app.c.create_line(p(cx + dx * (r - 2)), p(cy + dy * (r - 2)), p(cx + dx * (r + 6)), p(cy + dy * (r + 6)),
                              fill=fg, width=1, tags=tags)
        app.c.create_text(p(cx), p(cy), text=label, font=app.fonts[font], fill=fg, tags=tags)

    def progress(self, app, frac, striped, phase, tags=("prog",)):
        x, y, w, h = PROGRESS
        p, c = app.px, app.c
        self.box(app, x, y, w, h, self.field, tags=tags)
        if frac <= 0:
            return
        ix, iy, iw, ih = x + 3, y + 3, w - 6, h - 6
        fw = iw * frac
        c.create_rectangle(p(ix), p(iy), p(ix + fw), p(iy + ih), fill=mix(self.bg, self.ink, 0.3), outline="", tags=tags)
        off = (phase % 6) if striped else 0
        sx = ix - ih + off
        while sx < ix + fw:
            x0, x1, y0, y1 = sx, sx + ih, iy + ih, iy
            if x0 < ix:
                t = (ix - x0) / ih
                x0, y0 = ix, iy + ih - t * ih
            if x1 > ix + fw:
                t = (ix + fw - sx) / ih
                x1, y1 = ix + fw, iy + ih - t * ih
            c.create_line(p(x0), p(y0), p(x1), p(y1), fill=self.ink, width=1, tags=tags)
            sx += 6

    def header(self, app):
        p, c = app.px, app.c
        app.text(34, 22, "YOUTUBE TO MP3", "wordmark")
        tw = app.fonts["wordmark"].measure("YOUTUBE TO MP3") / app.k
        y = 62
        c.create_line(p(34), p(y), p(34 + tw), p(y), fill=self.ink, width=1, arrow="both")
        c.create_line(p(34), p(y - 5), p(34), p(y + 5), fill=self.ink, width=1)
        c.create_line(p(34 + tw), p(y - 5), p(34 + tw), p(y + 5), fill=self.ink, width=1)
        # the measurement sits in a gap in the line, drafting style
        label = f"{round(tw)} px"
        lw = app.fonts["label11b"].measure(label) / app.k + 10
        c.create_rectangle(p(34 + tw / 2 - lw / 2), p(y - 7), p(34 + tw / 2 + lw / 2), p(y + 7), fill=self.bg, outline="")
        app.text(34 + tw / 2, y, label, "label11b", fill=self.muted, anchor="center")
        app.text(34, 72, self.copy["tagline"], "mono12", fill=self.muted)
        # north arrow
        cx, cy, r = 506, 46, 20
        c.create_oval(p(cx - r), p(cy - r), p(cx + r), p(cy + r), fill="", outline=self.ink, width=max(1, p(1.5)))
        c.create_polygon(p(cx), p(cy - r + 4), p(cx - 5), p(cy + 4), p(cx), p(cy), p(cx + 5), p(cy + 4), fill=self.ink, outline=self.ink)
        app.text(cx, cy + r + 4, "N", "label11b", fill=self.muted, anchor="n")


SKINS = {s.key: s for s in (Skin, BlackOps, FighterJet, Chill, Blueprint)}
ORDER = ["pop", "ops", "jet", "chill", "blueprint"]
