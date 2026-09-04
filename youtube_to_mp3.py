"""YouTube to MP3 downloader.

Paste a YouTube URL, click Convert, and the best available audio stream is
downloaded and encoded to MP3 (VBR V0) with ID3 tags and a square cover image.
Requires FFmpeg on PATH, next to the app, or at "ffmpeg_location" in config.json.

The whole UI is drawn on one Tk canvas. That is what makes the pop art styling
(ink borders, hard offset shadows, halftone fields, starbursts) match the design
instead of fighting a widget toolkit's idea of a button.
"""

import ctypes
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.font as tkfont
import webbrowser
from pathlib import Path

import yt_dlp
from PIL import Image, ImageDraw, ImageTk

# Inside a PyInstaller exe, __file__ points into a temp folder that is wiped on
# exit, so the config has to live somewhere stable. Next to the script is fine
# when running from source. Bundled resources (fonts, icon) live in _MEIPASS.
FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
RES_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "YouTubeToMP3" if FROZEN else APP_DIR
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "download_folder": str(Path.home() / "Downloads"),
    "ask_each_time": False,
    "ffmpeg_location": "",  # blank means search next to the app, then PATH
}

# ---- design tokens (Direction A: comic pop) ----
W, H = 560, 520
CREAM = "#FFF6E0"
INK = "#111111"
RED = "#E8232A"
YELLOW = "#FFD400"
BLUE = "#1E5BFF"
WHITE = "#FFFFFF"
MUTED = "#6B6B6B"
PLACEHOLDER = "#8A8A8A"
DISABLED = "#CFCFCF"
DISABLED_FG = "#7A7A7A"
HOVER = {RED: "#C1121F", YELLOW: "#E6BE00", WHITE: "#F1EAD6", INK: "#2E2E2E", BLUE: "#1747CC"}
STAR = [(50, 0), (61, 14), (79, 8), (80, 27), (98, 35), (88, 50), (98, 65), (80, 73), (79, 92),
        (61, 86), (50, 100), (39, 86), (21, 92), (20, 73), (2, 65), (12, 50), (2, 35), (20, 27),
        (21, 8), (39, 14)]

URL_HINT = "Paste a YouTube link"
RELEASES_URL = "https://github.com/Roach9223/youtube-to-mp3/releases/latest"
FFMPEG_MISSING = ("FFmpeg not found. Install it and add it to PATH, put ffmpeg.exe next to "
                  "this app, or set ffmpeg_location in config.json.")
CLOSE_GRACE_SECONDS = 15  # how long to wait for a job to stop before closing anyway


def load_config() -> dict:
    try:
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return {**DEFAULT_CONFIG, **cfg}
    except (OSError, ValueError):
        return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass  # settings just won't persist; not worth interrupting the user


def find_ffmpeg(location: str) -> str | None:
    """Return the path to the ffmpeg executable, or None if it is not found.

    Order: the configured location, then a copy sitting next to the app (so a
    release zip can ship one), then PATH.
    """
    if location:
        p = Path(location)
        return shutil.which(str(p / "ffmpeg" if p.is_dir() else p))
    return shutil.which(str(APP_DIR / "ffmpeg")) or shutil.which("ffmpeg")


def no_console() -> dict:
    """subprocess kwargs that stop a console window flashing up on Windows."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def enable_dpi_awareness() -> None:
    """Ask Windows for real pixels so the canvas can scale itself crisply."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (OSError, AttributeError):
            pass


def register_fonts() -> None:
    """Load the bundled fonts for this process only (FR_PRIVATE), no install needed."""
    if sys.platform != "win32":
        return
    for ttf in (RES_DIR / "fonts").glob("*.ttf"):
        try:
            ctypes.windll.gdi32.AddFontResourceExW(str(ttf), 0x10, 0)
        except OSError:
            pass


def make_background(k: float) -> Image.Image:
    """Cream paper, two rotated halftone fields and the ink bar down the left."""
    img = Image.new("RGB", (round(W * k), round(H * k)), CREAM)

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

    paste_centered(dot_field(BLUE, 300, 230, 11, 1.7, 9), 470, 45)
    paste_centered(dot_field(RED, 230, 170, 12, 1.9, 9), 65, 495)
    ImageDraw.Draw(img).rectangle((0, 0, round(14 * k), img.height), fill=INK)
    return img


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.converting = False
        self.updating = False
        self.cancel_requested = False
        self.job_files: set[str] = set()
        self.close_deadline = 0.0
        self.last_output: Path | None = None
        self.buttons: dict[str, dict] = {}
        self.ffmpeg = find_ffmpeg(self.cfg["ffmpeg_location"])
        self.k = max(1.0, self.winfo_fpixels("1i") / 96)

        self.title("YouTube to MP3")
        self.configure(bg=CREAM)
        self.resizable(False, False)
        icon = RES_DIR / "icon.ico"
        if icon.exists():
            try:
                self.iconbitmap(str(icon))
            except tk.TclError:
                pass
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.fonts = self._make_fonts()
        self.c = tk.Canvas(self, width=self.px(W), height=self.px(H), bg=CREAM,
                           highlightthickness=0, bd=0)
        self.c.pack()

        self._draw_background()
        self._draw_header()
        self._draw_url_row()
        self._draw_folder_row()
        self._draw_convert()
        self._draw_progress()
        self._draw_footer()
        if self.ffmpeg:
            self.show_idle("Ready")
        else:
            self.show_error(FFMPEG_MISSING)

    # ----- scale and fonts -----

    def px(self, v: float) -> int:
        return round(v * self.k)

    def _make_fonts(self) -> dict:
        have = set(tkfont.families())
        display = "Archivo Black" if "Archivo Black" in have else "Impact"
        body = "Space Grotesk" if "Space Grotesk" in have else "Segoe UI"
        mono = "Space Mono" if "Space Mono" in have else "Consolas"

        def f(family, size, weight="normal"):
            return tkfont.Font(family=family, size=-self.px(size), weight=weight)

        return {
            "wordmark": f(display, 26), "btn_lg": f(display, 22), "btn": f(display, 15),
            "btn_md": f(display, 12), "btn_sm": f(display, 11), "display16": f(display, 16),
            "display13": f(display, 13), "burst17": f(display, 17), "burst15": f(display, 15),
            "body12": f(body, 12), "body12b": f(body, 12, "bold"), "body13": f(body, 13),
            "body13b": f(body, 13, "bold"), "label11b": f(body, 11, "bold"),
            "mono13": f(mono, 13), "mono12": f(mono, 12), "mono12b": f(mono, 12, "bold"),
        }

    # ----- drawing primitives (all coordinates in design px) -----

    def rect(self, x, y, w, h, fill, outline=INK, border=3, shadow=0, shadow_color=INK, tags=()):
        p, c = self.px, self.c
        if shadow:
            c.create_rectangle(p(x + shadow), p(y + shadow), p(x + w + shadow), p(y + h + shadow),
                               fill=shadow_color, outline=shadow_color, tags=tags)
        b = p(border)
        half = b / 2  # keep the stroke inside the box, the way CSS borders sit
        return c.create_rectangle(p(x) + half, p(y) + half, p(x + w) - half, p(y + h) - half,
                                  fill=fill, outline=outline, width=b, tags=tags)

    def text(self, x, y, s, font, fill=INK, anchor="nw", tags=(), **kw):
        return self.c.create_text(self.px(x), self.px(y), text=s, font=self.fonts[font],
                                  fill=fill, anchor=anchor, tags=tags, **kw)

    def fit(self, s: str, font: str, width: float) -> str:
        """Ellipsize s so it fits in width design px."""
        f, limit = self.fonts[font], self.px(width)
        if f.measure(s) <= limit:
            return s
        while s and f.measure(s + "…") > limit:
            s = s[:-1]
        return s + "…"

    def icon(self, kind, cx, cy, s, color, tags=()):
        p, c = self.px, self.c
        w = max(2, p(2.2))
        h = s / 2
        if kind == "clipboard":
            c.create_rectangle(p(cx - h * 0.6), p(cy - h * 0.7), p(cx + h * 0.6), p(cy + h * 0.95),
                               outline=color, width=w, tags=tags)
            c.create_rectangle(p(cx - h * 0.3), p(cy - h * 0.95), p(cx + h * 0.3), p(cy - h * 0.5),
                               outline=color, fill=color, width=1, tags=tags)
            for dy in (0.05, 0.4):
                c.create_line(p(cx - h * 0.3), p(cy + h * dy), p(cx + h * 0.3), p(cy + h * dy),
                              fill=color, width=w, tags=tags)
        elif kind in ("folder", "open"):
            pts = [(cx - h, cy - h * 0.6), (cx - h * 0.2, cy - h * 0.6), (cx, cy - h * 0.35),
                   (cx + h, cy - h * 0.35), (cx + h, cy + h * 0.8), (cx - h, cy + h * 0.8)]
            c.create_polygon([p(v) for pt in pts for v in pt], outline=color, fill="", width=w,
                             tags=tags)
            if kind == "open":
                c.create_line(p(cx), p(cy + h * 0.55), p(cx), p(cy - h * 0.05), fill=color, width=w,
                              tags=tags)
                c.create_line(p(cx - h * 0.35), p(cy + h * 0.25), p(cx), p(cy - h * 0.05),
                              p(cx + h * 0.35), p(cy + h * 0.25), fill=color, width=w, tags=tags)
        elif kind == "refresh":
            box = (p(cx - h * 0.8), p(cy - h * 0.8), p(cx + h * 0.8), p(cy + h * 0.8))
            c.create_arc(box, start=25, extent=135, style="arc", outline=color, width=w, tags=tags)
            c.create_arc(box, start=205, extent=135, style="arc", outline=color, width=w, tags=tags)
            for ax, ay, sx, sy in ((-0.8, -0.35, 1, 1), (0.8, 0.35, -1, -1)):
                c.create_line(p(cx + h * ax), p(cy + h * ay), p(cx + h * (ax + 0.45 * sx)), p(cy + h * ay),
                              fill=color, width=w, tags=tags)
                c.create_line(p(cx + h * ax), p(cy + h * ay), p(cx + h * ax), p(cy + h * (ay + 0.45 * sy)),
                              fill=color, width=w, tags=tags)
        elif kind == "x":
            c.create_line(p(cx - h * 0.7), p(cy - h * 0.7), p(cx + h * 0.7), p(cy + h * 0.7),
                          fill=color, width=w, tags=tags)
            c.create_line(p(cx + h * 0.7), p(cy - h * 0.7), p(cx - h * 0.7), p(cy + h * 0.7),
                          fill=color, width=w, tags=tags)
        elif kind == "check":
            c.create_line(p(cx - h * 0.7), p(cy), p(cx - h * 0.2), p(cy + h * 0.55),
                          p(cx + h * 0.75), p(cy - h * 0.6), fill=color, width=w, tags=tags,
                          joinstyle="miter", capstyle="projecting")

    def burst(self, x, y, size, label, bg, fg, font, angle=-8, tags=()):
        cx, cy = x + size / 2, y + size / 2
        a = math.radians(angle)

        def points(scale):
            out = []
            for sx, sy in STAR:
                dx, dy = (sx / 100 - 0.5) * size * scale, (sy / 100 - 0.5) * size * scale
                out += [self.px(cx + dx * math.cos(a) - dy * math.sin(a)),
                        self.px(cy + dx * math.sin(a) + dy * math.cos(a))]
            return out

        self.c.create_polygon(points(1.0), fill=INK, outline=INK, tags=tags)
        self.c.create_polygon(points((size - 9) / size), fill=bg, outline=bg, tags=tags)
        self.c.create_text(self.px(cx), self.px(cy), text=label, font=self.fonts[font], fill=fg,
                           angle=-angle, tags=tags)

    # ----- buttons -----

    def button(self, name, x, y, w, h, label, fill, fg, font, shadow=4, icon=None, tags=()):
        self.buttons[name] = dict(x=x, y=y, w=w, h=h, label=label, fill=fill, fg=fg, font=font,
                                  shadow=shadow, icon=icon, enabled=True, tags=tuple(tags))
        self._paint_button(name)

    def set_button(self, name, **changes):
        self.buttons[name].update(changes)
        self._paint_button(name)

    def _paint_button(self, name):
        b, c = self.buttons[name], self.c
        tag = f"btn:{name}"
        c.delete(tag)
        tags = (tag, *b["tags"])
        fill = b["fill"] if b["enabled"] else DISABLED
        fg = b["fg"] if b["enabled"] else DISABLED_FG
        self.rect(b["x"], b["y"], b["w"], b["h"], fill, shadow=b["shadow"], tags=tags + (tag + ":body",))
        f = self.fonts[b["font"]]
        icon_w = 18 + 8 if b["icon"] else 0
        total = f.measure(b["label"]) / self.k + icon_w
        sx = b["x"] + b["w"] / 2 - total / 2
        cy = b["y"] + b["h"] / 2
        if b["icon"]:
            self.icon(b["icon"], sx + 9, cy, 17, fg, tags=tags)
        c.create_text(self.px(sx + icon_w), self.px(cy), text=b["label"], font=f, fill=fg,
                      anchor="w", tags=tags)
        if b["enabled"]:
            c.tag_bind(tag, "<Button-1>", lambda e, n=name: self.on_button(n))
            c.tag_bind(tag, "<Enter>", lambda e, n=name: self._hover(n, True))
            c.tag_bind(tag, "<Leave>", lambda e, n=name: self._hover(n, False))

    def _hover(self, name, on):
        b = self.buttons.get(name)
        if not b or not b["enabled"]:
            return
        self.c.itemconfigure(f"btn:{name}:body", fill=HOVER.get(b["fill"], b["fill"]) if on else b["fill"])
        self.c.configure(cursor="hand2" if on else "")

    def on_button(self, name):
        handler = {"paste": self.paste_url, "browse": self.browse_folder,
                   "convert": self.start_convert, "update": self.start_update,
                   "open_folder": self.open_folder}.get(name)
        if handler:
            handler()

    # ----- static layout -----

    def _draw_background(self):
        self.bg_image = ImageTk.PhotoImage(make_background(self.k))
        self.c.create_image(0, 0, image=self.bg_image, anchor="nw")

    def _draw_header(self):
        f = self.fonts["wordmark"]
        x, y, h, pad = 34, 24, 36, 10
        a = math.radians(-2)  # the whole wordmark leans back two degrees
        px0, py0 = x, y + 2 * h

        def rot(rx, ry):
            dx, dy = rx - px0, ry - py0
            return px0 + dx * math.cos(a) - dy * math.sin(a), py0 + dx * math.sin(a) + dy * math.cos(a)

        def block(bx, by, label, fill, fg):
            bw = f.measure(label) / self.k + 2 * pad
            pts = [rot(bx, by), rot(bx + bw, by), rot(bx + bw, by + h), rot(bx, by + h)]
            self.c.create_polygon([self.px(v) for pt in pts for v in pt], fill=fill, outline=INK,
                                  width=self.px(3))
            cx, cy = rot(bx + bw / 2, by + h / 2 + 1)
            self.c.create_text(self.px(cx), self.px(cy), text=label, font=f, fill=fg, angle=2)

        block(x, y, "YOUTUBE", YELLOW, INK)
        block(x + 14, y + h - 3, "TO MP3", RED, WHITE)

        # speech bubble tagline
        bx, by, bw, bh = 262, 28, 272, 46
        self.rect(bx, by, bw, bh, WHITE, shadow=3)
        ty = by + bh - 18
        p = self.px
        self.c.create_polygon(p(bx - 14), p(ty), p(bx + 2), p(ty - 8), p(bx + 2), p(ty + 8), fill=INK, outline=INK)
        self.c.create_polygon(p(bx - 8), p(ty), p(bx + 4), p(ty - 5), p(bx + 4), p(ty + 5), fill=WHITE, outline=WHITE)
        self.text(bx + 12, by + bh / 2, "Best audio stream. MP3 at V0.\nSquare cover art baked in.",
                  "body12b", anchor="w")

    def _draw_url_row(self):
        self.rect(34, 104, 384, 46, WHITE, shadow=4)
        self.entry = tk.Entry(self.c, font=self.fonts["mono13"], bd=0, relief="flat", bg=WHITE,
                              fg=PLACEHOLDER, insertbackground=INK, highlightthickness=0)
        self.c.create_window(self.px(47), self.px(127), anchor="w", window=self.entry,
                             width=self.px(358), height=self.px(28))
        self.hint_shown = True
        self.entry.insert(0, URL_HINT)
        self.entry.bind("<FocusIn>", self._entry_focus_in)
        self.entry.bind("<FocusOut>", self._entry_focus_out)
        self.entry.bind("<Return>", self.on_return)
        self.button("paste", 430, 104, 104, 46, "PASTE", YELLOW, INK, "btn", icon="clipboard")

    def _draw_folder_row(self):
        self.text(34, 168, "SAVE TO", "label11b")
        self.rect(34, 182, 384, 36, CREAM, border=2)
        self.folder_text = self.text(46, 200, "", "mono12", anchor="w")
        self.set_folder_label(self.cfg["download_folder"])
        self.button("browse", 430, 182, 104, 36, "BROWSE", WHITE, INK, "btn_md", shadow=3, icon="folder")

        self.rect(34, 232, 20, 20, WHITE, tags=("chk",))
        self.text(64, 242, "Ask where to save each time", "body13", anchor="w", tags=("chk",))
        self.c.tag_bind("chk", "<Button-1>", lambda e: self.toggle_ask())
        self._paint_checkbox()

    def _draw_convert(self):
        self.button("convert", 34, 268, 500, 56, "CONVERT", RED, WHITE, "btn_lg", shadow=6)

    def _draw_progress(self):
        self.rect(34, 344, 500, 16, WHITE)
        self.set_progress(0)

    def _draw_footer(self):
        x = self.chip(34, 478, f"yt-dlp {yt_dlp.version.__version__}", WHITE)
        if self.ffmpeg:
            self.chip(x + 8, 478, "FFMPEG OK", YELLOW)
        else:
            self.chip(x + 8, 478, "FFMPEG MISSING", RED, WHITE)
        self.button("update", 384, 478, 150, 30, "GET UPDATE" if FROZEN else "UPDATE YT-DLP",
                    WHITE, INK, "btn_sm", shadow=3, icon="refresh")

    def chip(self, x, y, label, bg, fg=INK) -> float:
        w = self.fonts["label11b"].measure(label) / self.k + 20
        self.rect(x, y, w, 24, bg, border=2)
        self.text(x + w / 2, y + 12, label, "label11b", fill=fg, anchor="center")
        return x + w

    # ----- dynamic pieces -----

    def _paint_checkbox(self):
        self.c.delete("chk:mark")
        if self.cfg["ask_each_time"]:
            self.rect(34, 232, 20, 20, INK, tags=("chk", "chk:mark"))
            self.icon("check", 44, 242, 13, WHITE, tags=("chk", "chk:mark"))

    def set_folder_label(self, folder: str):
        self.c.itemconfigure(self.folder_text, text=self.fit(folder, "mono12", 360))

    def set_progress(self, frac: float, striped: bool = False):
        c, p = self.c, self.px
        c.delete("prog")
        frac = max(0.0, min(1.0, frac))
        if frac <= 0:
            return
        x, y, w, h = 37, 347, 494, 10
        fw = w * frac
        c.create_rectangle(p(x), p(y), p(x + fw), p(y + h), fill=RED, outline=RED, tags=("prog",))
        if not striped:
            return
        sx = x
        while sx < x + fw:
            x1, y1 = sx + h, y
            if x1 > x + fw:  # clip the last stripe at the fill edge
                t = (x + fw - sx) / h
                x1, y1 = x + fw, y + h - t * h
            c.create_line(p(sx), p(y + h), p(x1), p(y1), fill=INK, width=p(4), capstyle="butt",
                          tags=("prog",))
            sx += 14

    def clear_status(self):
        self.c.delete("status")
        self.c.delete("btn:open_folder")
        self.buttons.pop("open_folder", None)

    def show_idle(self, msg: str, color: str = MUTED):
        self.clear_status()
        self.text(34, 380, msg, "body13b", fill=color, tags=("status",), width=self.px(500))

    def show_working(self, label: str, detail: str = "", frac: float | None = None):
        self.clear_status()
        tx = 34
        if frac is not None:
            self.burst(34, 372, 74, f"{frac:.0%}", YELLOW, INK, "burst17", tags=("status",))
            tx = 122
        self.text(tx, 380, label, "display16", tags=("status",))
        self.text(tx, 402, self.fit(detail, "body12", 534 - tx), "body12", fill=MUTED, tags=("status",))

    def show_done(self, path: Path):
        self.clear_status()
        self.last_output = path
        self.burst(34, 372, 78, "DONE", BLUE, WHITE, "burst15", angle=6, tags=("status",))
        self.text(126, 380, self.fit(path.name, "mono12b", 408), "mono12b", tags=("status",))
        self.button("open_folder", 126, 404, 170, 32, "SHOW IN FOLDER", WHITE, INK, "btn_sm",
                    shadow=3, icon="open", tags=("status",))

    def show_error(self, msg: str):
        self.clear_status()
        body = self.text(78, 398, msg, "body12", tags=("status",), width=self.px(440))
        x1, y1, x2, y2 = self.c.bbox(body)
        box_h = max(64, (y2 - self.px(372)) / self.k + 12)
        # The box has to size to the wrapped text, so it is drawn after and then
        # pushed under it (shadow first, then box, order preserved).
        self.rect(34, 372, 500, box_h, WHITE, outline=RED, shadow=4, shadow_color=RED,
                  tags=("status", "status:box"))
        self.c.tag_lower("status:box", body)
        self.rect(44, 381, 24, 24, RED, tags=("status",))
        self.icon("x", 56, 393, 12, WHITE, tags=("status",))
        self.text(78, 380, "ERROR", "display13", fill=RED, tags=("status",))

    # ----- entry helpers -----

    def _entry_focus_in(self, _e):
        if self.hint_shown:
            self.entry.delete(0, "end")
            self.entry.configure(fg=INK)
            self.hint_shown = False

    def _entry_focus_out(self, _e):
        if not self.entry.get():
            self.entry.insert(0, URL_HINT)
            self.entry.configure(fg=PLACEHOLDER)
            self.hint_shown = True

    def get_url(self) -> str:
        return "" if self.hint_shown else self.entry.get().strip()

    def set_url(self, url: str):
        self.entry.delete(0, "end")
        self.entry.insert(0, url)
        self.entry.configure(fg=INK)
        self.hint_shown = False

    # ----- UI actions -----

    def paste_url(self):
        try:
            self.set_url(self.clipboard_get().strip())
        except tk.TclError:
            self.show_idle("Clipboard is empty", RED)

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.cfg["download_folder"])
        if folder:
            self.cfg["download_folder"] = folder
            self.set_folder_label(folder)
            save_config(self.cfg)

    def toggle_ask(self):
        self.cfg["ask_each_time"] = not self.cfg["ask_each_time"]
        self._paint_checkbox()
        save_config(self.cfg)

    def open_folder(self):
        if not self.last_output:
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(self.last_output)])
        else:
            subprocess.Popen(["xdg-open", str(self.last_output.parent)])

    def on_return(self, _event):
        if not self.converting:
            self.start_convert()

    def start_convert(self):
        if self.converting:
            self.request_cancel()
            return
        if self.updating:
            self.show_idle("Wait for the yt-dlp update to finish", RED)
            return
        if not self.ffmpeg:
            self.show_error(FFMPEG_MISSING)
            return
        url = self.get_url()
        if not url:
            self.show_idle("Paste a YouTube link first", RED)
            self.entry.focus_set()
            return

        folder = self.cfg["download_folder"]
        if self.cfg["ask_each_time"]:
            chosen = filedialog.askdirectory(initialdir=folder, title="Save MP3 to…")
            if not chosen:
                return
            folder = chosen

        self.converting = True
        self.cancel_requested = False
        self.job_files = set()
        self.set_button("convert", label="CANCEL", fill=INK, fg=WHITE, icon="x")
        self.set_button("update", enabled=False)
        self.set_progress(0)
        self.show_working("STARTING", "Asking YouTube for the audio stream")
        threading.Thread(target=self.download, args=(url, folder), daemon=True).start()

    def request_cancel(self):
        if not self.converting or self.cancel_requested:
            return
        self.cancel_requested = True
        self.set_button("convert", label="CANCELLING…", enabled=False)
        self.show_working("CANCELLING", "Stopping the download and cleaning up")

    def on_close(self):
        """Window close: stop a running job first so no half-written files are left."""
        if not self.converting:
            self.destroy()
            return
        self.request_cancel()
        self.show_working("CANCELLING", "The window will close in a moment")
        self.close_deadline = time.monotonic() + CLOSE_GRACE_SECONDS
        self._close_when_idle()

    def _close_when_idle(self):
        if self.converting and time.monotonic() < self.close_deadline:
            self.after(200, self._close_when_idle)
            return
        self.destroy()

    # ----- download (background thread) -----

    def download(self, url: str, folder: str):
        opts = {
            "format": "bestaudio/best",
            "outtmpl": str(Path(folder) / "%(title)s.%(ext)s"),
            "noplaylist": True,
            "writethumbnail": True,
            "postprocessors": [
                # YouTube's thumbnails are 16:9. Convert to png and crop the centre
                # square so the cover art is not letterboxed in players.
                {"key": "FFmpegThumbnailsConvertor", "format": "png", "when": "before_dl"},
                # "0" is LAME VBR V0, roughly 245 kbps. YouTube's best source stream is
                # about 130 kbps Opus, so a fixed 320 kbps only makes the file bigger.
                {"key": "FFmpegExtractAudio",
                 "preferredcodec": "mp3",
                 "preferredquality": "0"},
                {"key": "FFmpegMetadata"},
                {"key": "EmbedThumbnail"},
            ],
            "postprocessor_args": {
                "thumbnailsconvertor+ffmpeg_o": ["-vf", "crop=min(iw\\,ih):min(iw\\,ih)"],
            },
            "progress_hooks": [self.progress_hook],
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }
        # Pass the resolved path so yt-dlp finds a copy next to the exe too.
        if self.ffmpeg:
            opts["ffmpeg_location"] = self.ffmpeg
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            # The real path on disk, after yt-dlp's filename sanitising and the
            # mp3 conversion. The raw title can differ from it quite a bit.
            path = Path(info["requested_downloads"][0]["filepath"])
            self.ui(self.finish_ok, path)
        except yt_dlp.utils.DownloadCancelled:
            self.cleanup_job_files(keep_download=False)
            self.ui(self.finish_cancelled)
        except yt_dlp.utils.DownloadError as e:
            self.cleanup_job_files(keep_download=True)
            msg = str(e).replace("ERROR: ", "").split(";")[0]
            self.ui(self.finish_err, msg)
        except Exception as e:
            self.cleanup_job_files(keep_download=True)
            self.ui(self.finish_err, str(e))

    def progress_hook(self, d: dict):
        for key in ("filename", "tmpfilename"):
            if d.get(key):
                self.job_files.add(d[key])
        if self.cancel_requested:
            raise yt_dlp.utils.DownloadCancelled("Cancelled by user")
        title = (d.get("info_dict") or {}).get("title", "")
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                frac = d.get("downloaded_bytes", 0) / total
                self.ui(self.show_download_progress, title, frac)
        elif d["status"] == "finished":
            self.ui(self.show_converting, title)

    def cleanup_job_files(self, keep_download: bool):
        """Remove what a cancelled or failed job leaves behind: the partial download
        and the thumbnail. On a failure the downloaded audio itself is kept, since it
        may be the only thing the user gets."""
        for name in list(self.job_files):
            p = Path(name)
            leftovers = [p.with_name(p.name + ".part"), p.with_name(p.name + ".ytdl")]
            leftovers += [p.with_suffix(ext) for ext in (".webp", ".jpg", ".png")]
            if not keep_download:
                leftovers.append(p)
            for f in leftovers:
                try:
                    f.unlink(missing_ok=True)
                except OSError:
                    pass

    # ----- yt-dlp updater (background thread) -----

    def start_update(self):
        if self.converting or self.updating:
            return
        if FROZEN:
            # pip can't reach inside a PyInstaller bundle; new yt-dlp ships as a new release.
            webbrowser.open(RELEASES_URL)
            self.show_idle("Opened the releases page. Download the newest build to update yt-dlp.", INK)
            return
        self.updating = True
        self.set_button("update", label="UPDATING…", enabled=False)
        self.show_working("UPDATING YT-DLP", "Fetching the latest release with pip")
        threading.Thread(target=self.update_ytdlp, daemon=True).start()

    def update_ytdlp(self):
        py = sys.executable
        try:
            r = subprocess.run([py, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                               capture_output=True, text=True, timeout=300, **no_console())
            if r.returncode != 0:
                lines = (r.stderr or r.stdout).strip().splitlines()
                self.ui(self.finish_update, False, lines[-1] if lines else "pip failed")
                return
            # Ask a fresh interpreter, since this process still has the old module loaded.
            v = subprocess.run([py, "-c", "import yt_dlp;print(yt_dlp.version.__version__)"],
                               capture_output=True, text=True, timeout=60, **no_console())
            new = v.stdout.strip()
        except (OSError, subprocess.TimeoutExpired) as e:
            self.ui(self.finish_update, False, str(e))
            return
        if new and new != yt_dlp.version.__version__:
            self.ui(self.finish_update, True,
                    f"Updated yt-dlp to {new}. Restart the app to use it.")
        else:
            self.ui(self.finish_update, True,
                    f"yt-dlp {yt_dlp.version.__version__} is already the latest.")

    # ----- UI updates (marshalled to main thread) -----

    def ui(self, fn, *args):
        try:
            self.after(0, fn, *args)
        except (RuntimeError, tk.TclError):
            pass  # window already closed; nothing left to update

    def show_download_progress(self, title: str, frac: float):
        self.set_progress(frac, striped=True)
        self.show_working("DOWNLOADING", title, frac)

    def show_converting(self, title: str):
        self.set_progress(1, striped=True)
        self.show_working("CONVERTING TO MP3", title, 1.0)

    def finish_ok(self, path: Path):
        self.reset_button()
        self.set_progress(1)
        self.show_done(path)

    def finish_cancelled(self):
        self.reset_button()
        self.set_progress(0)
        self.show_idle("Cancelled")

    def finish_err(self, msg: str):
        self.reset_button()
        self.set_progress(0)
        self.show_error(msg)

    def finish_update(self, ok: bool, msg: str):
        self.updating = False
        self.set_button("update", label="UPDATE YT-DLP", enabled=True)
        self.show_idle(msg, INK if ok else RED)

    def reset_button(self):
        self.converting = False
        self.cancel_requested = False
        self.set_button("convert", label="CONVERT", fill=RED, fg=WHITE, icon=None, enabled=True)
        self.set_button("update", enabled=True)


if __name__ == "__main__":
    enable_dpi_awareness()
    register_fonts()
    App().mainloop()
