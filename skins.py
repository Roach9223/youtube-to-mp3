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
    display_weight = "normal"
    field_fg = None        # text inside fields; None means the skin's text colour
    status_fg = None       # status headline; None means text
    status_muted = None    # status detail; None means muted
    button = None          # neutral buttons; None means surface
    button_fg = None
    chip_ok = None         # the FFmpeg-found chip; None means accent
    chip_ok_fg = None

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

    def status_panel(self, app, kind) -> bool:
        """Optional backdrop behind the status area; kind is idle, working or done.
        Return True when something was drawn so the app insets its text."""
        return False

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


# ---- F-16 cockpit: glareshield, HUD, DED, ICP keys, MFD screen ----

class FighterJet(Skin):
    key = "jet"
    name = "F-16"

    PANEL = "#4A4F52"      # dark gull gray, FS 36231, in cockpit shadow
    GLARE = "#1E2022"
    BEZEL = "#26282B"
    SCREEN = "#0B0D0B"
    KEY = "#2A2C2F"
    HUD = "#4DFF4D"        # P43 phosphor, about 545 nm
    HUD_DIM = "#2E8F2E"
    MFD = "#5FE86A"
    MFD_DIM = "#3FA84A"
    AMBER = "#FFB000"
    RED = "#FF3B30"
    LIT_RED = "#C8102E"

    bg = PANEL
    ink = BEZEL
    text = "#E6E6E6"
    muted = "#A6A9AD"
    placeholder = "#2F6B36"
    surface = SCREEN
    field = SCREEN
    field_fg = MFD
    button = KEY
    button_fg = "#E6E6E6"
    primary = AMBER
    primary_fg = "#111111"
    accent = KEY
    accent_fg = "#E6E6E6"
    accent2 = MFD
    accent2_fg = SCREEN
    working = SCREEN
    working_fg = HUD
    cancel = LIT_RED
    cancel_fg = "#FFFFFF"
    error = AMBER
    error_fg = "#111111"
    disabled = "#2A2C2F"
    disabled_fg = "#6B6E72"
    chip_ok = MFD
    chip_ok_fg = SCREEN
    status_fg = MFD
    status_muted = MFD_DIM
    hover = {AMBER: "#FFC43D", KEY: "#383B3F", LIT_RED: "#E0203A", MFD: "#7DF288", SCREEN: "#141614"}

    border = 2
    border_thin = 1
    shadows = {}
    display_scale = 0.95
    display_weight = "bold"
    animated = True

    # B612 is the Airbus cockpit face. Its mono cut spaces punctuation oddly in a
    # text field, so the DED lines use Share Tech Mono and the HUD keeps B612 Mono.
    families = {
        "display": ("B612", "Segoe UI"),
        "body": ("B612", "Segoe UI"),
        "body_bold": ("B612", "Segoe UI"),
        "mono": ("Share Tech Mono", "Consolas"),
        "mono_bold": ("Share Tech Mono", "Consolas"),
        "hud": ("B612 Mono", "Consolas"),
    }
    body_bold_weight = "bold"
    mono_bold_weight = "normal"
    hud_weight = "bold"

    copy = {**Skin.copy, "tagline": "MP3 V0 · SQ COVER",
            "url_hint": "ENTER TARGET LINK", "paste": "PASTE", "save_to": "LANDING ZONE",
            "browse": "BROWSE", "ask": "CONFIRM LANDING ZONE EVERY SORTIE", "convert": "ENGAGE",
            "cancel": "ABORT", "cancelling": "ABORTING", "ready": "SYSTEMS NOMINAL",
            "starting": "SPOOLING UP", "starting_detail": "REQUESTING STREAM FROM YOUTUBE",
            "downloading": "DOWNLINK", "converting": "ENCODING MP3",
            "cancel_title": "ABORTING", "cancel_detail": "DUMPING PARTIAL FILES",
            "close_detail": "CANOPY CLOSING", "cancelled": "SORTIE ABORTED", "done": "LANDED",
            "show": "OPEN LANDING ZONE", "error": "MASTER CAUTION",
            "update": "UPDATE YT-DLP", "get_update": "GET UPDATE", "updating": "UPDATING",
            "update_title": "UPDATING YT-DLP", "update_detail": "PULLING LATEST RELEASE",
            "ffmpeg_ok": "FFMPEG OK", "ffmpeg_missing": "FFMPEG OFFLINE"}

    # Block 50 eyebrow panels: (label, width). Left carries MASTER CAUTION, TF FAIL and
    # two push buttons; right is the warning row, all red except DBU ON.
    EYEBROW_LEFT = [("MASTER\nCAUTION", 66), ("TF FAIL", 50), ("F-ACK", 30), ("IFF\nIDENT", 30)]
    EYEBROW_RIGHT = [("ENG FIRE", 36), ("ENGINE", 36), ("HYD/OIL\nPRESS", 36), ("FLCS", 36),
                     ("DBU ON", 36), ("TO/LDG\nCONFIG", 36), ("CANOPY", 36), ("OXY LOW", 36)]

    # -- background: brushed panel, glareshield, screws --

    def background(self, k):
        import random
        w, h = round(W * k), round(H * k)
        img = Image.new("RGB", (w, h), self.PANEL)
        d = ImageDraw.Draw(img)
        rnd = random.Random(16)
        base = _rgb(self.PANEL)
        for y in range(h):  # brushed metal: per-row brightness jitter
            v = rnd.randint(-6, 6)
            d.line((0, y, w, y), fill=_hex(tuple(c + v for c in base)))
        for _ in range(900):  # short scratches
            x, y = rnd.randint(0, w), rnd.randint(0, h)
            ln = rnd.randint(round(6 * k), round(40 * k))
            v = rnd.choice((-10, 8))
            d.line((x, y, x + ln, y), fill=_hex(tuple(c + v for c in base)))
        # vignette on the sides
        for i in range(round(28 * k)):
            t = 1 - i / (28 * k)
            col = mix(self.PANEL, "#000000", 0.35 * t)
            d.line((i, 0, i, h), fill=col)
            d.line((w - 1 - i, 0, w - 1 - i, h), fill=col)
        # glareshield across the top, and a lower lip
        gs = round(40 * k)
        top, bottom = _rgb("#2A2D31"), _rgb(self.GLARE)
        for y in range(gs):
            t = y / gs
            d.line((0, y, w, y), fill=_hex(tuple(top[i] + (bottom[i] - top[i]) * t for i in range(3))))
        d.rectangle((0, gs, w, gs + round(2 * k)), fill="#0B0C0D")
        d.rectangle((0, h - round(10 * k), w, h), fill=self.GLARE)
        d.rectangle((0, h - round(12 * k), w, h - round(10 * k)), fill="#0B0C0D")
        # panel seam under the HUD
        d.line((0, round(101 * k), w, round(101 * k)), fill="#2A2D31", width=max(1, round(k)))
        d.line((0, round(102 * k), w, round(102 * k)), fill="#4A4E53", width=1)
        # screws
        r = round(4 * k)
        for (sx, sy) in ((20, 112), (540, 112), (20, 470), (540, 470)):
            cx, cy = round(sx * k), round(sy * k)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill="#4A4E53", outline="#141517")
            d.ellipse((cx - r + 1, cy - r + 1, cx + r - 2, cy + r - 2), fill="#3A3D41")
            d.line((cx - r * 0.6, cy - r * 0.5, cx + r * 0.6, cy + r * 0.5), fill="#17191B", width=max(1, round(k)))
        return img

    # -- shapes --

    def _key(self, app, x, y, w, h, fill, tags):
        """ICP keypad button: rounded, bevelled, black rim."""
        p, c = app.px, app.c
        deco = tuple(t for t in tags if not t.endswith(":body"))
        c.create_polygon(flat(app, rounded_points(x, y + 2, w, h, 4)), fill="#0B0C0D", outline="", tags=deco)
        item = c.create_polygon(flat(app, rounded_points(x, y, w, h, 4)), fill=fill, outline="#0B0C0D",
                                width=max(1, p(1)), tags=tags)
        c.create_line(p(x + 5), p(y + 1.5), p(x + w - 5), p(y + 1.5), fill="#4A4E53", width=max(1, p(1)), tags=deco)
        return item

    def _hazard_lens(self, app, x, y, w, h, fill, tags):
        """Guarded pushbutton: amber and black hazard stripes round a lit lens."""
        p, c = app.px, app.c
        deco = tuple(t for t in tags if not t.endswith(":body"))
        c.create_rectangle(p(x), p(y), p(x + w), p(y + h), fill="#111111", outline="#0B0C0D", width=max(1, p(1)), tags=deco)
        sx = x - h
        while sx < x + w:
            pts = [(sx, y + h), (sx + 8, y + h), (sx + 8 + h, y), (sx + h, y)]
            pts = [(min(max(px_, x), x + w), py_) for px_, py_ in pts]
            c.create_polygon(flat(app, pts), fill=self.AMBER, outline="", tags=deco)
            sx += 16
        m = 7
        item = c.create_rectangle(p(x + m), p(y + m), p(x + w - m), p(y + h - m), fill=fill, outline="#0B0C0D",
                                  width=max(1, p(2)), tags=tags + ((tags[0] + ":lens",) if tags else ()))
        c.create_rectangle(p(x + m + 3), p(y + m + 3), p(x + w - m - 3), p(y + h - m - 3), fill="",
                           outline=mix(fill, "#000000", 0.35), width=1, tags=deco)
        return item

    def box(self, app, x, y, w, h, fill, outline=None, border=None, shadow=None,
            shadow_color=None, tags=(), glow=None, kind="box"):
        p, c = app.px, app.c
        if kind == "button":
            if fill in (self.AMBER, self.LIT_RED) or (fill == self.disabled and h >= 50):
                return self._hazard_lens(app, x, y, w, h, fill, tags)
            return self._key(app, x, y, w, h, fill, tags)
        if kind == "chip":
            return c.create_polygon(flat(app, rounded_points(x, y, w, h, 3)), fill=fill, outline="#0B0C0D",
                                    width=max(1, p(1)), tags=tags)
        if kind == "check":
            b = max(1, p(1))
            return c.create_rectangle(p(x) + b / 2, p(y) + b / 2, p(x + w) - b / 2, p(y + h) - b / 2, fill=fill,
                                      outline="#0B0C0D", width=b, tags=tags)
        # fields, panels, screens: black glass in a bezel
        b = p(border if border is not None else self.border)
        half = b / 2
        item = c.create_rectangle(p(x) + half, p(y) + half, p(x + w) - half, p(y + h) - half, fill=fill,
                                  outline=outline or self.BEZEL, width=b, tags=tags)
        c.create_rectangle(p(x + 3), p(y + 3), p(x + w - 3), p(y + h - 3), fill="", outline="#050605", width=1, tags=tags)
        return item

    def badge(self, app, x, y, size, label, bg, fg, font, angle=-8, tags=()):
        """Round engine gauge. A percent label drives the needle; anything else pegs it."""
        p, c = app.px, app.c
        cx, cy, r = x + size / 2, y + size / 2, size / 2
        frac = int(label.rstrip("%")) / 100 if label.endswith("%") else 1.0
        c.create_oval(p(cx - r), p(cy - r), p(cx + r), p(cy + r), fill=self.BEZEL, outline="#0B0C0D", width=max(1, p(1)), tags=tags)
        c.create_oval(p(cx - r + 3), p(cy - r + 3), p(cx + r - 3), p(cy + r - 3), fill=self.SCREEN, outline="", tags=tags)
        for i in range(0, 11):
            a = math.radians(-210 + 240 * i / 10)
            L = 6 if i % 5 == 0 else 3
            c.create_line(p(cx + (r - 6) * math.cos(a)), p(cy + (r - 6) * math.sin(a)),
                          p(cx + (r - 6 - L) * math.cos(a)), p(cy + (r - 6 - L) * math.sin(a)),
                          fill=self.text, width=max(1, p(1.2)), tags=tags)
        a = math.radians(-210 + 240 * frac)
        c.create_line(p(cx), p(cy), p(cx + (r - 9) * math.cos(a)), p(cy + (r - 9) * math.sin(a)),
                      fill=self.text, width=max(1, p(2)), tags=tags)
        c.create_oval(p(cx - 3), p(cy - 3), p(cx + 3), p(cy + 3), fill=self.text, outline="", tags=tags)
        small = "mono12b" if len(label) > 4 else font
        c.create_text(p(cx), p(cy + r * 0.5), text=label, font=app.fonts[small], fill=self.HUD, tags=tags)

    def progress(self, app, frac, striped, phase, tags=("prog",)):
        x, y, w, h = PROGRESS
        p, c = app.px, app.c
        self.box(app, x, y, w, h, self.SCREEN, tags=tags)
        for i in range(1, 10):
            tx = x + i * w / 10
            c.create_line(p(tx), p(y + 3), p(tx), p(y + 6), fill=self.muted, width=1, tags=tags)
        if frac <= 0:
            return
        ix, iy, iw, ih = x + 4, y + 4, w - 8, h - 8
        seg, gap = 8, 2
        n = int(iw // (seg + gap))
        filled = round(frac * n)
        for i in range(n):
            sx = ix + i * (seg + gap)
            if i < filled:
                col = self.MFD
            elif i == filled and striped:
                col = self.MFD if phase % 4 < 2 else self.MFD_DIM
            else:
                continue
            c.create_rectangle(p(sx), p(iy), p(sx + seg), p(iy + ih), fill=col, outline="", tags=tags)

    # -- header: eyebrow lights and the HUD --

    def _light(self, app, x, y, w, label, tag):
        p, c = app.px, app.c
        c.create_polygon(flat(app, rounded_points(x, y, w, 22, 3)), fill="#26282B", outline="#0B0C0D",
                         width=max(1, p(1)), tags=(tag, tag + ":lens"))
        c.create_text(p(x + w / 2), p(y + 11), text=label, font=app.fonts["tiny"], fill="#5A5D61",
                      justify="center", tags=(tag, tag + ":text"))

    def _set_light(self, app, tag, color):
        """color None = dark."""
        lit = color is not None
        app.c.itemconfigure(tag + ":lens", fill=color if lit else "#26282B")
        app.c.itemconfigure(tag + ":text", fill="#111111" if lit else "#5A5D61")

    def header(self, app):
        p, c = app.px, app.c
        x = 34
        for i, (label, w) in enumerate(self.EYEBROW_LEFT):
            self._light(app, x, 9, w, label, f"eb:L{i}")
            x += w + 3
        x = 534 - sum(w for _, w in self.EYEBROW_RIGHT) - 3 * (len(self.EYEBROW_RIGHT) - 1)
        for i, (label, w) in enumerate(self.EYEBROW_RIGHT):
            self._light(app, x, 9, w, label, f"eb:R{i}")
            x += w + 3
        # HUD glass
        gx, gy, gw, gh = 34, 46, 500, 52
        c.create_polygon(flat(app, rounded_points(gx, gy, gw, gh, 6)), fill="#0E2014", outline="#55605A",
                         width=max(1, p(1)))
        self._tape(app, 0)
        c.create_polygon(p(gx + gw / 2 - 4), p(gy + 2), p(gx + gw / 2 + 4), p(gy + 2), p(gx + gw / 2), p(gy + 7),
                         fill=self.HUD, outline="")
        for label, lx, anchor in (("420", gx + 14, "nw"), ("12000", gx + gw - 14, "ne")):
            t = c.create_text(p(lx), p(gy + 24), text=label, font=app.fonts["tiny_mono"], fill=self.HUD, anchor=anchor)
            x1, y1, x2, y2 = c.bbox(t)
            c.create_rectangle(x1 - p(3), y1 - p(1), x2 + p(3), y2 + p(1), outline=self.HUD, width=1)
        glow = mix("#0E2014", self.HUD, 0.3)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c.create_text(p(gx + gw / 2 + dx), p(gy + 30 + dy), text="YOUTUBE / MP3", font=app.fonts["hud"], fill=glow)
        c.create_text(p(gx + gw / 2), p(gy + 30), text="YOUTUBE / MP3", font=app.fonts["hud"], fill=self.HUD)
        # flight path marker, bobbing in tick()
        fx, fy = gx + gw / 2, gy + 44
        c.create_oval(p(fx - 4), p(fy - 4), p(fx + 4), p(fy + 4), outline=self.HUD, width=1, tags=("fpm",))
        c.create_line(p(fx - 11), p(fy), p(fx - 4), p(fy), fill=self.HUD, width=1, tags=("fpm",))
        c.create_line(p(fx + 4), p(fy), p(fx + 11), p(fy), fill=self.HUD, width=1, tags=("fpm",))
        c.create_line(p(fx), p(fy - 4), p(fx), p(fy - 8), fill=self.HUD, width=1, tags=("fpm",))
        c.create_text(p(gx + 14), p(gy + gh - 3), text="NAV", font=app.fonts["tiny_mono"], fill=self.HUD, anchor="sw")
        c.create_text(p(gx + gw - 14), p(gy + gh - 3), text=self.copy["tagline"], font=app.fonts["tiny_mono"], fill=self.HUD, anchor="se")

    def _tape(self, app, offset):
        """Heading tape across the top of the HUD glass; offset scrolls it."""
        p, c = app.px, app.c
        c.delete("hud:tape")
        gx, gy, gw = 34, 46, 500
        c.create_line(p(gx + 8), p(gy + 8), p(gx + gw - 8), p(gy + 8), fill=self.HUD_DIM, width=1, tags=("hud:tape",))
        step = 38.0
        start = -((offset) % step)
        i = 0
        while start + i * step <= gw:
            tx = gx + start + i * step
            if gx + 30 < tx < gx + gw - 30:
                heading = (240 + int((offset // step) * 10) + i * 10) % 360
                c.create_line(p(tx), p(gy + 8), p(tx), p(gy + 12), fill=self.HUD, width=1, tags=("hud:tape",))
                c.create_text(p(tx), p(gy + 18), text=f"{heading:03d}", font=app.fonts["tiny_mono"], fill=self.HUD, tags=("hud:tape",))
            i += 1

    def status_panel(self, app, kind):
        """MFD screen behind the status text, with the AOA indexer at the right."""
        p, c = app.px, app.c
        x = 34 if kind == "idle" else 122
        self.box(app, x, 372, 534 - x, 78, self.SCREEN, tags=("status",))
        for i, (shape, dim, lit) in enumerate((("down", "#4A2A28", self.RED), ("circle", "#23402A", self.MFD), ("up", "#4A3A16", self.AMBER))):
            cx, cy = 518, 386 + i * 22
            tag = f"aoa:{i}"
            if shape == "circle":
                c.create_oval(p(cx - 6), p(cy - 6), p(cx + 6), p(cy + 6), fill=dim, outline="", tags=("status", tag))
            elif shape == "down":
                c.create_polygon(p(cx - 6), p(cy - 6), p(cx + 6), p(cy - 6), p(cx), p(cy + 6), fill=dim, outline="", tags=("status", tag))
            else:
                c.create_polygon(p(cx - 6), p(cy + 6), p(cx + 6), p(cy + 6), p(cx), p(cy - 6), fill=dim, outline="", tags=("status", tag))
        lit = {"done": ("aoa:1", self.MFD), "working": ("aoa:2", self.AMBER)}.get(kind)
        if lit:
            c.itemconfigure(lit[0], fill=lit[1])
        return True

    def tick(self, app, phase):
        c = app.c
        kind = app.status_state[0]
        if phase % 3 == 0:
            self._tape(app, phase * 0.5)
        # flight path marker bobs a pixel or two
        dy = app.px(0.6 * math.sin(phase / 5)) - app.px(0.6 * math.sin((phase - 1) / 5))
        c.move("fpm", 0, dy)
        # eyebrow lights follow the app: MASTER CAUTION on error, FLCS when FFmpeg is
        # missing (no flight controls), DBU ON while a job runs, CANOPY when the
        # folder prompt is armed
        self._set_light(app, "eb:L0", self.AMBER if kind == "error" and phase % 8 < 4 else None)
        self._set_light(app, "eb:R3", self.RED if not app.ffmpeg and phase % 10 < 5 else None)
        self._set_light(app, "eb:R4", self.AMBER if app.converting else None)
        self._set_light(app, "eb:R6", self.RED if app.cfg.get("ask_each_time") else None)
        # AOA amber blinks while working
        if kind == "working":
            c.itemconfigure("aoa:2", fill=self.AMBER if phase % 6 < 3 else "#4A3A16")
        # the lit lens breathes
        b = app.buttons.get("convert")
        if b and b["enabled"] and b["fill"] in (self.AMBER, self.LIT_RED):
            t = 0.5 + 0.5 * math.sin(phase / 7)
            c.itemconfigure("btn:convert:lens", fill=mix(b["fill"], "#FFFFFF", 0.12 * t))
        if app.converting and app.progress_state[1] and phase % 2 == 0:
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
ORDER = ["jet", "pop", "ops", "chill", "blueprint"]
