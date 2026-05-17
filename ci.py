import json
import plistlib
import random
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import rumps
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


APP_NAME = "Ci"
BUNDLE_IDENTIFIER = "com.yankihue.ci"
DEFAULT_INTERVAL = 600
INTERVALS = {
    "10 min": 10 * 60,
    "30 min": 30 * 60,
    "1 hour": 60 * 60,
    "Daily": 24 * 60 * 60,
}
WALLPAPER_PREFIX = "Ci-Wallpaper"
EMPTY_POEM_TEXT = "Generate a wallpaper to see the current poem."
MENU_POEM_LINE_LIMIT = 10
UNSUPPORTED_RENDER_CHARS = str.maketrans({
    "-": " ",
    "—": " ",
    "–": " ",
    "，": " ",
    "。": " ",
    "！": " ",
    "？": " ",
    "；": " ",
    "：": " ",
    "、": " ",
    "“": "",
    "”": "",
    "‘": "",
    "’": "",
    "《": "",
    "》": "",
    "（": "",
    "）": "",
    "(": "",
    ")": "",
})
THEMES = [
    {
        "name": "warm paper",
        "paper": (226, 217, 198),
        "paper_alt": (239, 232, 213),
        "ink": (49, 27, 8),
        "wash": (123, 92, 51),
    },
    {
        "name": "mist blue",
        "paper": (211, 220, 216),
        "paper_alt": (229, 234, 228),
        "ink": (31, 45, 42),
        "wash": (74, 101, 101),
    },
    {
        "name": "old rose",
        "paper": (226, 209, 203),
        "paper_alt": (240, 226, 218),
        "ink": (55, 29, 24),
        "wash": (132, 74, 66),
    },
    {
        "name": "bamboo",
        "paper": (213, 221, 198),
        "paper_alt": (232, 236, 217),
        "ink": (35, 48, 28),
        "wash": (83, 111, 65),
    },
    {
        "name": "smoke",
        "paper": (211, 208, 199),
        "paper_alt": (232, 228, 218),
        "ink": (34, 31, 28),
        "wash": (91, 86, 76),
    },
]


@dataclass
class Poem:
    title: str
    author: str
    contents: str
    kind: str

    @property
    def menu_summary(self):
        author = f"　　{self.author}" if self.author else ""
        return f"{self.title}{author}"

    @property
    def menu_lines(self):
        lines = [self.title]
        if self.author:
            lines.append(self.author)
        lines.extend(line for line in self.contents.splitlines() if line.strip())
        return lines


def app_support_dir():
    path = Path.home() / "Library" / "Application Support" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path():
    return app_support_dir() / "settings.json"


def wallpaper_path():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return app_support_dir() / f"{WALLPAPER_PREFIX}-{stamp}-{random.randrange(1_000_000):06d}.png"


def latest_wallpaper_path(settings=None):
    if settings:
        path = settings.get("last_wallpaper")
        if path:
            return Path(path)
    generated = sorted(app_support_dir().glob(f"{WALLPAPER_PREFIX}-*.png"))
    if generated:
        return generated[-1]
    legacy = app_support_dir() / "Ci-Wallpaper.png"
    return legacy


def resource_path(name):
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / name)
    candidates.append(Path(__file__).resolve().parent / name)
    candidates.append(Path(sys.executable).resolve().parent.parent / "Resources" / name)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_settings():
    defaults = {
        "interval": DEFAULT_INTERVAL,
        "paused": False,
        "launch_at_login": False,
        "last_wallpaper": None,
    }
    path = settings_path()
    if not path.exists():
        return defaults
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return defaults
    return {**defaults, **loaded}


def save_settings(settings):
    with settings_path().open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2, sort_keys=True)


def load_poems():
    poems_file = resource_path("poems.json")
    with poems_file.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return [
        Poem(
            title=item.get("title", "Untitled"),
            author=item.get("author", ""),
            contents=item.get("contents", ""),
            kind=item.get("type", ""),
        )
        for item in data
    ]


def screen_size():
    try:
        from AppKit import NSScreen
    except ImportError as exc:
        raise RuntimeError("PyObjC/AppKit is required to detect the screen size.") from exc

    frame = NSScreen.mainScreen().frame()
    scale = NSScreen.mainScreen().backingScaleFactor()
    return int(frame.size.width * scale), int(frame.size.height * scale)


def font_path():
    bundled = resource_path("qiji-combo.ttf")
    if bundled.exists():
        return str(bundled)
    for directory in (
        Path.home() / "Library" / "Fonts",
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
    ):
        installed = directory / "qiji-combo.ttf"
        if installed.exists():
            return str(installed)
    return "qiji-combo.ttf"


def load_font(size):
    try:
        return ImageFont.truetype(font_path(), size)
    except OSError as exc:
        raise RuntimeError(
            "Missing qiji-combo.ttf. Install qiji-combo from qiji-font, "
            "or place qiji-combo.ttf next to Ci.app before building."
        ) from exc


def text_size(draw, text, font):
    left, top, right, bottom = draw.multiline_textbbox((0, 0), text, font=font, spacing=16)
    return right - left, bottom - top


def render_text(text):
    return text.translate(UNSUPPORTED_RENDER_CHARS)


def clamp_channel(value):
    return max(0, min(255, int(value)))


def mix_color(left, right, amount):
    return tuple(
        clamp_channel(left[index] * (1 - amount) + right[index] * amount)
        for index in range(3)
    )


def jitter_color(color, spread):
    return tuple(clamp_channel(channel + random.randint(-spread, spread)) for channel in color)


def theme_variant(theme):
    accent = (
        random.randint(175, 245),
        random.randint(175, 240),
        random.randint(165, 230),
    )
    paper = jitter_color(mix_color(theme["paper"], accent, random.uniform(0.10, 0.24)), 10)
    paper_alt = jitter_color(mix_color(theme["paper_alt"], accent, random.uniform(0.08, 0.18)), 10)
    wash = jitter_color(mix_color(theme["wash"], accent, random.uniform(0.08, 0.20)), 16)
    ink = jitter_color(theme["ink"], 7)
    return {**theme, "paper": paper, "paper_alt": paper_alt, "wash": wash, "ink": ink}


def add_paper_texture(base, theme):
    width, height = base.size
    noise = Image.effect_noise((width, height), random.randint(16, 32)).convert("L")
    grain = ImageOps.colorize(noise, black=theme["paper"], white=theme["paper_alt"])
    base = Image.blend(base, grain, random.uniform(0.06, 0.12))

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for _ in range(random.randint(120, 220)):
        y = random.randrange(height)
        x = random.randrange(width)
        length = random.randint(width // 30, width // 8)
        color = (*theme["wash"], random.randint(8, 18))
        draw.line((x, y, min(width, x + length), y + random.randint(-2, 2)), fill=color, width=1)

    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def add_wash_marks(base, theme):
    width, height = base.size
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for _ in range(random.randint(2, 4)):
        radius = random.randint(min(width, height) // 8, min(width, height) // 3)
        x = random.randint(-radius // 2, width - radius // 2)
        y = random.choice([
            random.randint(-radius // 2, height // 3),
            random.randint((height * 2) // 3, height + radius // 2),
        ])
        color = (*theme["wash"], random.randint(12, 28))
        draw.ellipse((x, y, x + radius * 2, y + radius), fill=color)

    for _ in range(random.randint(1, 3)):
        x = random.randint(0, width)
        color = (*theme["wash"], random.randint(14, 26))
        draw.line((x, 0, x + random.randint(-width // 5, width // 5), height), fill=color, width=random.randint(2, 5))

    overlay = overlay.filter(ImageFilter.GaussianBlur(random.randint(28, 56)))
    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def add_deckle_shadow(base, theme):
    width, height = base.size
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    margin = max(24, min(width, height) // 42)
    color = (*theme["ink"], 22)
    draw.rectangle((margin, margin, width - margin, height - margin), outline=color, width=max(2, margin // 9))
    overlay = overlay.filter(ImageFilter.GaussianBlur(max(2, margin // 6)))
    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def draw_wallpaper(poem, output_path):
    width, height = screen_size()
    theme = theme_variant(random.choice(THEMES))
    base = Image.new("RGB", (width, height), theme["paper"])
    base = add_paper_texture(base, theme)
    base = add_wash_marks(base, theme)
    if random.random() < 0.65:
        base = add_deckle_shadow(base, theme)
    draw = ImageDraw.Draw(base)
    poem_font = load_font(max(44, min(width, height) // 24))
    title_font = load_font(max(30, min(width, height) // 36))

    poem_text = render_text(poem.contents)
    poem_w, poem_h = text_size(draw, poem_text, poem_font)
    title = render_text(poem.menu_summary)
    title_w, title_h = text_size(draw, title, title_font)

    x = max((width - poem_w) / 2, 80)
    y = max((height - poem_h) / 2, 120)
    title_y = max(y - title_h - 48, 80)
    ink = theme["ink"]

    draw.multiline_text(((width - title_w) / 2, title_y), title, ink, font=title_font, spacing=16)
    draw.multiline_text((x, y), poem_text, ink, font=poem_font, spacing=16, align="center")
    base.save(output_path)
    return width, height


def set_wallpaper(path):
    script = """
    tell application "System Events"
        tell every desktop
            set picture to POSIX file "%s"
        end tell
    end tell
    """ % str(path).replace('"', '\\"')
    subprocess.run(["/usr/bin/osascript", "-e", script], check=True)


def reveal_in_finder(path):
    if path.exists():
        subprocess.run(["/usr/bin/open", "-R", str(path)], check=True)
    else:
        subprocess.run(["/usr/bin/open", str(app_support_dir())], check=True)


def launch_agent_path():
    return Path.home() / "Library" / "LaunchAgents" / f"{BUNDLE_IDENTIFIER}.plist"


def launch_command():
    executable = Path(sys.executable).resolve()
    if ".app/Contents/MacOS" in str(executable):
        return [str(executable)]
    return [sys.executable, str(Path(__file__).resolve())]


def set_launch_at_login(enabled):
    path = launch_agent_path()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "Label": BUNDLE_IDENTIFIER,
            "ProgramArguments": launch_command(),
            "RunAtLoad": True,
        }
        with path.open("wb") as handle:
            plistlib.dump(payload, handle)
    elif path.exists():
        path.unlink()


def launch_at_login_enabled():
    return launch_agent_path().exists()


class CiApp:
    def __init__(self):
        self.settings = load_settings()
        self.poems = load_poems()
        self.current_poem = None
        self.remaining = int(self.settings["interval"])

        self.app = rumps.App(APP_NAME, title="词", quit_button="Quit Ci")
        self.timer = rumps.Timer(self.on_tick, 1)

        self.new_item = rumps.MenuItem("New Wallpaper", callback=self.generate_poem)
        self.pause_item = rumps.MenuItem("", callback=self.toggle_pause)
        self.current_header = rumps.MenuItem(f"Current Poem: {EMPTY_POEM_TEXT}")
        self.current_line_items = [
            rumps.MenuItem("")
            for _ in range(MENU_POEM_LINE_LIMIT)
        ]
        self.reveal_item = rumps.MenuItem("Reveal Wallpaper", callback=self.reveal_wallpaper)
        self.login_item = rumps.MenuItem("Start at Login", callback=self.toggle_launch_at_login)
        self.interval_items = {
            label: rumps.MenuItem(label, callback=self.set_interval)
            for label in INTERVALS
        }

        self.app.menu = [
            self.new_item,
            self.pause_item,
            None,
            self.current_header,
            *self.current_line_items,
            self.reveal_item,
            None,
            {"Interval": list(self.interval_items.values())},
            self.login_item,
        ]
        self.refresh_menu()
        self.timer.start()

    def refresh_menu(self):
        paused = bool(self.settings["paused"])
        self.pause_item.title = "Resume" if paused else "Pause"
        self.login_item.state = launch_at_login_enabled()
        for label, item in self.interval_items.items():
            item.state = self.settings["interval"] == INTERVALS[label]
        if self.current_poem:
            self.current_header.title = f"Current Poem: {self.current_poem.menu_summary}"
            for item, line in zip(self.current_line_items, self.current_poem.contents.splitlines()):
                item.title = line
                item.show()
            for item in self.current_line_items[len(self.current_poem.contents.splitlines()):]:
                item.hide()
        else:
            self.current_header.title = f"Current Poem: {EMPTY_POEM_TEXT}"
            for item in self.current_line_items:
                item.hide()

    def save_and_refresh(self):
        save_settings(self.settings)
        self.refresh_menu()

    def on_tick(self, _sender):
        if self.settings["paused"]:
            return
        self.remaining -= 1
        if self.remaining <= 0:
            self.generate_poem()

    def reset_timer(self):
        self.remaining = int(self.settings["interval"])

    def set_interval(self, sender):
        self.settings["interval"] = INTERVALS[sender.title]
        self.reset_timer()
        self.save_and_refresh()

    def toggle_pause(self, _sender):
        self.settings["paused"] = not self.settings["paused"]
        self.save_and_refresh()

    def toggle_launch_at_login(self, _sender):
        enabled = not launch_at_login_enabled()
        try:
            set_launch_at_login(enabled)
        except OSError as exc:
            rumps.alert("Ci could not update Start at Login", str(exc))
            return
        self.settings["launch_at_login"] = enabled
        self.save_and_refresh()

    def reveal_wallpaper(self, _sender):
        try:
            reveal_in_finder(latest_wallpaper_path(self.settings))
        except (OSError, subprocess.CalledProcessError) as exc:
            rumps.alert("Ci could not reveal the wallpaper", str(exc))

    def generate_poem(self, _sender=None):
        poem = random.choice(self.poems)
        output = wallpaper_path()
        try:
            width, height = draw_wallpaper(poem, output)
            set_wallpaper(output)
        except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
            rumps.alert("Ci could not generate a wallpaper", str(exc))
            return

        self.current_poem = poem
        self.settings["last_wallpaper"] = str(output)
        save_settings(self.settings)
        print(f"Generated {poem.menu_summary} at {width}x{height}: {output}")
        self.reset_timer()
        self.refresh_menu()

    def run(self):
        self.app.run()


if __name__ == "__main__":
    CiApp().run()
