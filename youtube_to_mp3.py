"""YouTube to MP3 downloader.

Paste a YouTube URL, click Convert, and the best available audio stream is
downloaded and encoded to MP3 (VBR V0) with ID3 tags and a square cover image.
Requires FFmpeg on PATH, next to the app, or at "ffmpeg_location" in config.json.

The whole UI is drawn on one Tk canvas, and every visual decision is delegated
to the active skin (see skins.py). That is what lets one layout wear five
very different looks and switch between them live.
"""

import ctypes
import json
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
from PIL import ImageTk

from skins import ORDER, SKINS

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
    "skin": "pop",
}

W, H = 560, 520
RELEASES_URL = "https://github.com/Roach9223/youtube-to-mp3/releases/latest"
FFMPEG_MISSING = ("FFmpeg not found. Install it and add it to PATH, put ffmpeg.exe next to "
                  "this app, or set ffmpeg_location in config.json.")
CLOSE_GRACE_SECONDS = 15  # how long to wait for a job to stop before closing anyway
TICK_MS = 100


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
        self.menu_open = False
        self.phase = 0
        self.url_text = ""
        self.progress_state = (0.0, False)
        self.status_state = ("idle", "ready", "muted")
        self.ffmpeg = find_ffmpeg(self.cfg["ffmpeg_location"])
        self.k = max(1.0, self.winfo_fpixels("1i") / 96)
        self.skin = SKINS.get(self.cfg["skin"], SKINS["pop"])()

        self.title("YouTube to MP3")
        self.resizable(False, False)
        icon = RES_DIR / "icon.ico"
        if icon.exists():
            try:
                self.iconbitmap(str(icon))
            except tk.TclError:
                pass
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.c = tk.Canvas(self, width=self.px(W), height=self.px(H), highlightthickness=0, bd=0)
        self.c.pack()
        self.c.bind("<Button-1>", self._on_canvas_click, add="+")
        self.entry: tk.Entry | None = None

        self._build()
        if not self.ffmpeg:
            self.show_error(FFMPEG_MISSING)
        self.after(TICK_MS, self._tick)

    # ----- scale and fonts -----

    def px(self, v: float) -> int:
        return round(v * self.k)

    def _make_fonts(self) -> dict:
        have = set(tkfont.families())
        s = self.skin

        def fam(role):
            wanted, fallback = s.families[role]
            return wanted if wanted in have else fallback

        display, body, body_b, mono, mono_b = (fam(r) for r in ("display", "body", "body_bold", "mono", "mono_bold"))
        bw, mw = s.body_bold_weight, s.mono_bold_weight

        def f(family, size, weight="normal", scale=1.0):
            return tkfont.Font(family=family, size=-self.px(size * scale), weight=weight)

        ds = s.display_scale
        return {
            "wordmark": f(display, 26, scale=ds), "btn_lg": f(display, 22, scale=ds),
            "btn": f(display, 15, scale=ds), "btn_md": f(display, 12, scale=ds),
            "btn_sm": f(display, 11, scale=ds), "display16": f(display, 16, scale=ds),
            "display13": f(display, 13, scale=ds), "burst17": f(display, 17, scale=ds),
            "burst15": f(display, 15, scale=ds),
            "body12": f(body, 12), "body12b": f(body_b, 12, bw), "body13": f(body, 13),
            "body13b": f(body_b, 13, bw), "label11b": f(body_b, 11, bw),
            "mono13": f(mono, 13), "mono12": f(mono, 12), "mono12b": f(mono_b, 12, mw),
        }

    # ----- drawing primitives (design px in, skin does the painting) -----

    def rect(self, x, y, w, h, fill, **kw):
        return self.skin.box(self, x, y, w, h, fill, **kw)

    def text(self, x, y, s, font, fill=None, anchor="nw", tags=(), **kw):
        return self.c.create_text(self.px(x), self.px(y), text=s, font=self.fonts[font],
                                  fill=fill or self.skin.text, anchor=anchor, tags=tags, **kw)

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
            c.create_polygon([p(v) for pt in pts for v in pt], outline=color, fill="", width=w, tags=tags)
            if kind == "open":
                c.create_line(p(cx), p(cy + h * 0.55), p(cx), p(cy - h * 0.05), fill=color, width=w, tags=tags)
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
            c.create_line(p(cx - h * 0.7), p(cy - h * 0.7), p(cx + h * 0.7), p(cy + h * 0.7), fill=color, width=w, tags=tags)
            c.create_line(p(cx + h * 0.7), p(cy - h * 0.7), p(cx - h * 0.7), p(cy + h * 0.7), fill=color, width=w, tags=tags)
        elif kind == "check":
            c.create_line(p(cx - h * 0.7), p(cy), p(cx - h * 0.2), p(cy + h * 0.55), p(cx + h * 0.75), p(cy - h * 0.6),
                          fill=color, width=w, tags=tags, joinstyle="miter", capstyle="projecting")
        elif kind == "chevron":
            c.create_polygon(p(cx - h * 0.6), p(cy - h * 0.3), p(cx + h * 0.6), p(cy - h * 0.3), p(cx), p(cy + h * 0.4),
                             fill=color, outline=color, tags=tags)
        elif kind == "palette":
            c.create_oval(p(cx - h * 0.8), p(cy - h * 0.8), p(cx + h * 0.8), p(cy + h * 0.8), outline=color, width=w, tags=tags)
            for dx, dy in ((-0.35, -0.3), (0.05, -0.45), (0.4, -0.1)):
                c.create_oval(p(cx + h * dx - 2), p(cy + h * dy - 2), p(cx + h * dx + 2), p(cy + h * dy + 2), fill=color, outline=color, tags=tags)

    def badge(self, x, y, size, label, bg, fg, font, angle=-8, tags=()):
        self.skin.badge(self, x, y, size, label, bg, fg, font, angle=angle, tags=tags)

    # ----- buttons -----

    def button(self, name, x, y, w, h, label, fill, fg, font, shadow="md", icon=None, icon_side="left", tags=()):
        self.buttons[name] = dict(x=x, y=y, w=w, h=h, label=label, fill=fill, fg=fg, font=font, shadow=shadow,
                                  icon=icon, icon_side=icon_side, enabled=True, tags=tuple(tags))
        self._paint_button(name)

    def set_button(self, name, **changes):
        self.buttons[name].update(changes)
        self._paint_button(name)

    def _paint_button(self, name):
        b, c, s = self.buttons[name], self.c, self.skin
        tag = f"btn:{name}"
        c.delete(tag)
        tags = (tag, *b["tags"])
        fill = b["fill"] if b["enabled"] else s.disabled
        fg = b["fg"] if b["enabled"] else s.disabled_fg
        glow = s.button_glow(fill) if b["enabled"] else None
        self.rect(b["x"], b["y"], b["w"], b["h"], fill, shadow=b["shadow"], tags=tags + (tag + ":body",),
                  glow=glow, kind="button")
        f = self.fonts[b["font"]]
        icon_w = 18 + 8 if b["icon"] else 0
        tw = f.measure(b["label"]) / self.k
        sx = b["x"] + b["w"] / 2 - (tw + icon_w) / 2
        cy = b["y"] + b["h"] / 2
        if b["icon"] and b["icon_side"] == "left":
            self.icon(b["icon"], sx + 9, cy, 17, fg, tags=tags)
            c.create_text(self.px(sx + icon_w), self.px(cy), text=b["label"], font=f, fill=fg, anchor="w", tags=tags)
        else:
            c.create_text(self.px(sx), self.px(cy), text=b["label"], font=f, fill=fg, anchor="w", tags=tags)
            if b["icon"]:
                self.icon(b["icon"], sx + tw + 8 + 7, cy, 15, fg, tags=tags)
        if b["enabled"]:
            c.tag_bind(tag, "<Button-1>", lambda e, n=name: self.on_button(n))
            c.tag_bind(tag, "<Enter>", lambda e, n=name: self._hover(n, True))
            c.tag_bind(tag, "<Leave>", lambda e, n=name: self._hover(n, False))

    def _hover(self, name, on):
        b = self.buttons.get(name)
        if not b or not b["enabled"]:
            return
        self.c.itemconfigure(f"btn:{name}:body", fill=self.skin.hover_color(b["fill"]) if on else b["fill"])
        self.c.configure(cursor="hand2" if on else "")

    def on_button(self, name):
        handler = {"paste": self.paste_url, "browse": self.browse_folder, "convert": self.start_convert,
                   "update": self.start_update, "open_folder": self.open_folder,
                   "skin": self.toggle_skin_menu}.get(name)
        if handler:
            handler()

    # ----- build and rebuild -----

    def _build(self):
        """Paint the whole window with the current skin, keeping any live state."""
        s = self.skin
        if self.entry is not None:
            self.url_text = self.get_url()
            self.entry.destroy()
        self.c.delete("all")
        self.buttons = {}
        self.menu_open = False
        self.fonts = self._make_fonts()
        self.configure(bg=s.bg)
        self.c.configure(bg=s.bg)

        self.bg_image = ImageTk.PhotoImage(s.background(self.k))
        self.c.create_image(0, 0, image=self.bg_image, anchor="nw")
        s.header(self)
        self._draw_url_row()
        self._draw_folder_row()
        self.button("convert", 34, 268, 500, 56, s.copy["convert"], s.primary, s.primary_fg, "btn_lg", shadow="lg")
        self._draw_footer()
        self.redraw_progress()
        self._restore_status()
        self._sync_buttons()

    def _draw_url_row(self):
        s = self.skin
        self.rect(34, 104, 384, 46, s.surface, shadow="md", kind="field")
        self.entry = tk.Entry(self.c, font=self.fonts["mono13"], bd=0, relief="flat", bg=s.surface,
                              fg=s.text, insertbackground=s.text, highlightthickness=0)
        self.c.create_window(self.px(47), self.px(127), anchor="w", window=self.entry,
                             width=self.px(358), height=self.px(28))
        self.hint_shown = True
        if self.url_text:
            self.set_url(self.url_text)
        else:
            self.entry.insert(0, s.copy["url_hint"])
            self.entry.configure(fg=s.placeholder)
        self.entry.bind("<FocusIn>", self._entry_focus_in)
        self.entry.bind("<FocusOut>", self._entry_focus_out)
        self.entry.bind("<Return>", self.on_return)
        self.button("paste", 430, 104, 104, 46, s.copy["paste"], s.accent, s.accent_fg, "btn", icon="clipboard")

    def _draw_folder_row(self):
        s = self.skin
        self.text(34, 168, s.copy["save_to"], "label11b")
        self.rect(34, 182, 384, 36, s.field, border=s.border_thin, kind="field")
        self.folder_text = self.text(46, 200, "", "mono12", anchor="w")
        self.set_folder_label(self.cfg["download_folder"])
        self.button("browse", 430, 182, 104, 36, s.copy["browse"], s.surface, s.text, "btn_md", shadow="sm", icon="folder")
        self.rect(34, 232, 20, 20, s.surface, tags=("chk",), kind="check")
        self.text(64, 242, s.copy["ask"], "body13", anchor="w", tags=("chk",))
        self.c.tag_bind("chk", "<Button-1>", lambda e: self.toggle_ask())
        self._paint_checkbox()

    def _draw_footer(self):
        s = self.skin
        x = self.chip(34, 478, f"yt-dlp {yt_dlp.version.__version__}", s.surface, s.text)
        if self.ffmpeg:
            x = self.chip(x + 8, 478, s.copy["ffmpeg_ok"], s.accent, s.accent_fg)
        else:
            x = self.chip(x + 8, 478, s.copy["ffmpeg_missing"], s.error, s.error_fg)
        sx = max(262, x + 10)
        self.button("skin", sx, 478, 376 - sx, 30, s.name, s.surface, s.text, "btn_sm", shadow="sm",
                    icon="chevron", icon_side="right")
        self.button("update", 384, 478, 150, 30, s.copy["get_update"] if FROZEN else s.copy["update"],
                    s.surface, s.text, "btn_sm", shadow="sm", icon="refresh")

    def chip(self, x, y, label, bg, fg) -> float:
        w = self.fonts["label11b"].measure(label) / self.k + 20
        self.rect(x, y, w, 24, bg, border=self.skin.border_thin, kind="chip")
        self.text(x + w / 2, y + 12, label, "label11b", fill=fg, anchor="center")
        return x + w

    def _sync_buttons(self):
        s = self.skin
        if self.converting and self.cancel_requested:
            self.set_button("convert", label=s.copy["cancelling"], fill=s.cancel, fg=s.cancel_fg, icon="x", enabled=False)
        elif self.converting:
            self.set_button("convert", label=s.copy["cancel"], fill=s.cancel, fg=s.cancel_fg, icon="x", enabled=True)
        if self.updating:
            self.set_button("update", label=s.copy["updating"], enabled=False)
        elif self.converting:
            self.set_button("update", enabled=False)

    # ----- skin menu -----

    def toggle_skin_menu(self):
        if self.menu_open:
            self.close_skin_menu()
        else:
            self.open_skin_menu()

    def open_skin_menu(self):
        s, c = self.skin, self.c
        b = self.buttons["skin"]
        item_h, w = 30, 150
        x = b["x"]
        y0 = b["y"] - 8 - item_h * len(ORDER)
        self.rect(x, y0, w, item_h * len(ORDER), s.surface, shadow="md", tags=("menu",), kind="panel")
        for i, key in enumerate(ORDER):
            sk = SKINS[key]
            y = y0 + i * item_h
            tag = f"menu:{key}"
            c.create_rectangle(self.px(x + 2), self.px(y + 2), self.px(x + w - 2), self.px(y + item_h - 2),
                               fill=s.surface, outline="", tags=("menu", tag, tag + ":bg"))
            self.icon("check" if key == s.key else "palette", x + 18, y + item_h / 2, 12,
                      s.text if key == s.key else s.muted, tags=("menu", tag))
            self.text(x + 34, y + item_h / 2, sk.name, "body13b", anchor="w", tags=("menu", tag))
            c.tag_bind(tag, "<Enter>", lambda e, t=tag: c.itemconfigure(t + ":bg", fill=s.hover_color(s.surface) if s.hover_color(s.surface) != s.surface else s.field))
            c.tag_bind(tag, "<Leave>", lambda e, t=tag: c.itemconfigure(t + ":bg", fill=s.surface))
            c.tag_bind(tag, "<Button-1>", lambda e, k=key: self.apply_skin(k))
        self.menu_open = True

    def close_skin_menu(self):
        self.c.delete("menu")
        self.menu_open = False

    def _on_canvas_click(self, _event):
        if not self.menu_open:
            return
        tags = self.c.gettags("current")
        if "menu" not in tags and "btn:skin" not in tags:
            self.close_skin_menu()

    def apply_skin(self, key: str):
        self.close_skin_menu()
        if key == self.skin.key:
            return
        self.cfg["skin"] = key
        save_config(self.cfg)
        self.skin = SKINS[key]()
        self._build()

    # ----- dynamic pieces -----

    def _paint_checkbox(self):
        self.c.delete("chk:mark")
        if self.cfg["ask_each_time"]:
            s = self.skin
            self.rect(34, 232, 20, 20, s.text, outline=s.text, tags=("chk", "chk:mark"), kind="check")
            self.icon("check", 44, 242, 13, s.surface, tags=("chk", "chk:mark"))

    def set_folder_label(self, folder: str):
        self.c.itemconfigure(self.folder_text, text=self.fit(folder, "mono12", 360))

    def set_progress(self, frac: float, striped: bool = False):
        self.progress_state = (max(0.0, min(1.0, frac)), striped)
        self.redraw_progress()

    def redraw_progress(self):
        self.c.delete("prog")
        frac, striped = self.progress_state
        self.skin.progress(self, frac, striped, self.phase)

    def clear_status(self):
        self.c.delete("status")
        self.c.delete("btn:open_folder")
        self.buttons.pop("open_folder", None)

    def _restore_status(self):
        kind, *args = self.status_state
        {"idle": self.show_idle, "working": self.show_working, "done": self.show_done,
         "error": self.show_error}[kind](*args)

    def show_idle(self, msg: str, role: str = "muted"):
        """msg is a copy key when the skin has one, else literal text."""
        self.status_state = ("idle", msg, role)
        s = self.skin
        self.clear_status()
        color = {"muted": s.muted, "text": s.text, "error": s.error if s.error_fg != s.error else s.text}[role]
        self.text(34, 380, s.copy.get(msg, msg), "body13b", fill=color, tags=("status",), width=self.px(500))

    def show_working(self, label: str, detail: str = "", frac: float | None = None):
        self.status_state = ("working", label, detail, frac)
        s = self.skin
        self.clear_status()
        tx = 34
        if frac is not None:
            self.badge(34, 372, 74, f"{frac:.0%}", s.working, s.working_fg, "burst17", tags=("status",))
            tx = 122
        self.text(tx, 380, s.copy.get(label, label), "display16", tags=("status",))
        self.text(tx, 402, self.fit(s.copy.get(detail, detail), "body12", 534 - tx), "body12", fill=s.muted, tags=("status",))

    def show_done(self, path: Path):
        self.status_state = ("done", path)
        s = self.skin
        self.clear_status()
        self.last_output = path
        self.badge(34, 372, 78, s.copy["done"], s.accent2, s.accent2_fg, "burst15", angle=6, tags=("status",))
        self.text(126, 380, self.fit(path.name, "mono12b", 408), "mono12b", tags=("status",))
        self.button("open_folder", 126, 404, 170, 32, s.copy["show"], s.surface, s.text, "btn_sm",
                    shadow="sm", icon="open", tags=("status",))

    def show_error(self, msg: str):
        self.status_state = ("error", msg)
        s = self.skin
        self.clear_status()
        body = self.text(78, 398, msg, "body12", tags=("status",), width=self.px(440))
        x1, y1, x2, y2 = self.c.bbox(body)
        box_h = max(64, (y2 - self.px(372)) / self.k + 12)
        # The box has to size to the wrapped text, so it is drawn after and then
        # pushed under it (shadow first, then box, order preserved).
        self.rect(34, 372, 500, box_h, s.surface, outline=s.error, shadow="md", shadow_color=s.error,
                  tags=("status", "status:box"), kind="panel")
        self.c.tag_lower("status:box", body)
        self.rect(44, 381, 24, 24, s.error, outline=s.error, tags=("status",), kind="check")
        self.icon("x", 56, 393, 12, s.error_fg, tags=("status",))
        self.text(78, 380, s.copy["error"], "display13", fill=s.error, tags=("status",))

    # ----- animation -----

    def _tick(self):
        if self.skin.animated:
            self.phase += 1
            self.skin.tick(self, self.phase)
        self.after(TICK_MS, self._tick)

    # ----- entry helpers -----

    def _entry_focus_in(self, _e):
        if self.hint_shown:
            self.entry.delete(0, "end")
            self.entry.configure(fg=self.skin.text)
            self.hint_shown = False

    def _entry_focus_out(self, _e):
        if not self.entry.get():
            self.entry.insert(0, self.skin.copy["url_hint"])
            self.entry.configure(fg=self.skin.placeholder)
            self.hint_shown = True

    def get_url(self) -> str:
        return "" if self.hint_shown else self.entry.get().strip()

    def set_url(self, url: str):
        self.entry.delete(0, "end")
        self.entry.insert(0, url)
        self.entry.configure(fg=self.skin.text)
        self.hint_shown = False

    # ----- UI actions -----

    def paste_url(self):
        try:
            self.set_url(self.clipboard_get().strip())
        except tk.TclError:
            self.show_idle("Clipboard is empty", "error")

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
            self.show_idle("Wait for the yt-dlp update to finish", "error")
            return
        if not self.ffmpeg:
            self.show_error(FFMPEG_MISSING)
            return
        url = self.get_url()
        if not url:
            self.show_idle("Paste a YouTube link first", "error")
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
        self._sync_buttons()
        self.set_progress(0)
        self.show_working("starting", "starting_detail")
        threading.Thread(target=self.download, args=(url, folder), daemon=True).start()

    def request_cancel(self):
        if not self.converting or self.cancel_requested:
            return
        self.cancel_requested = True
        self._sync_buttons()
        self.show_working("cancel_title", "cancel_detail")

    def on_close(self):
        """Window close: stop a running job first so no half-written files are left."""
        if not self.converting:
            self.destroy()
            return
        self.request_cancel()
        self.show_working("cancel_title", "close_detail")
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
            self.show_idle("Opened the releases page. Download the newest build to update yt-dlp.", "text")
            return
        self.updating = True
        self._sync_buttons()
        self.show_working("update_title", "update_detail")
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
            self.ui(self.finish_update, True, f"Updated yt-dlp to {new}. Restart the app to use it.")
        else:
            self.ui(self.finish_update, True, f"yt-dlp {yt_dlp.version.__version__} is already the latest.")

    # ----- UI updates (marshalled to main thread) -----

    def ui(self, fn, *args):
        try:
            self.after(0, fn, *args)
        except (RuntimeError, tk.TclError):
            pass  # window already closed; nothing left to update

    def show_download_progress(self, title: str, frac: float):
        self.set_progress(frac, striped=True)
        self.show_working("downloading", title, frac)

    def show_converting(self, title: str):
        self.set_progress(1, striped=True)
        self.show_working("converting", title, 1.0)

    def finish_ok(self, path: Path):
        self.reset_button()
        self.set_progress(1)
        self.show_done(path)

    def finish_cancelled(self):
        self.reset_button()
        self.set_progress(0)
        self.show_idle("cancelled")

    def finish_err(self, msg: str):
        self.reset_button()
        self.set_progress(0)
        self.show_error(msg)

    def finish_update(self, ok: bool, msg: str):
        self.updating = False
        s = self.skin
        self.set_button("update", label=s.copy["update"], enabled=True)
        self.show_idle(msg, "text" if ok else "error")

    def reset_button(self):
        self.converting = False
        self.cancel_requested = False
        s = self.skin
        self.set_button("convert", label=s.copy["convert"], fill=s.primary, fg=s.primary_fg, icon=None, enabled=True)
        self.set_button("update", enabled=not self.updating)


if __name__ == "__main__":
    enable_dpi_awareness()
    register_fonts()
    App().mainloop()
