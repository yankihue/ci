import json
import math
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


class Noise2D:
    def __init__(self, seed):
        rng = random.Random(seed)
        perm = list(range(256))
        rng.shuffle(perm)
        self.perm = perm * 2
        self.gradients = [
            (math.cos(rng.random() * math.tau), math.sin(rng.random() * math.tau))
            for _ in range(256)
        ] * 2

    @staticmethod
    def fade(value):
        return value * value * value * (value * (value * 6 - 15) + 10)

    @staticmethod
    def lerp(left, right, amount):
        return left + amount * (right - left)

    def dot(self, index, x, y):
        gx, gy = self.gradients[self.perm[index & 255]]
        return gx * x + gy * y

    def noise2d(self, x, y):
        x0 = math.floor(x)
        y0 = math.floor(y)
        xf = x - x0
        yf = y - y0
        u = self.fade(xf)
        v = self.fade(yf)

        aa = self.perm[(x0 & 255)] + y0
        ab = self.perm[(x0 & 255)] + y0 + 1
        ba = self.perm[((x0 + 1) & 255)] + y0
        bb = self.perm[((x0 + 1) & 255)] + y0 + 1

        x1 = self.lerp(self.dot(aa, xf, yf), self.dot(ba, xf - 1, yf), u)
        x2 = self.lerp(self.dot(ab, xf, yf - 1), self.dot(bb, xf - 1, yf - 1), u)
        return self.lerp(x1, x2, v) * 0.5 + 0.5

    def fbm(self, x, y, octaves=5, lacunarity=2.0, gain=0.5):
        value = 0
        amplitude = 1
        frequency = 1
        maximum = 0
        for _ in range(octaves):
            value += self.noise2d(x * frequency, y * frequency) * amplitude
            maximum += amplitude
            amplitude *= gain
            frequency *= lacunarity
        return value / maximum

    def ridge(self, x, y, octaves=4, sharpness=2.0):
        value = 0
        amplitude = 1
        frequency = 1
        maximum = 0
        previous = 1
        for _ in range(octaves):
            sample = self.noise2d(x * frequency, y * frequency)
            sample = 1 - abs(sample * 2 - 1)
            sample = math.pow(sample, sharpness) * previous
            previous = sample
            value += sample * amplitude
            maximum += amplitude
            amplitude *= 0.5
            frequency *= 2.1
        return value / maximum

    def warp(self, x, y, amount=0.5, octaves=4):
        qx = self.fbm(x, y, octaves)
        qy = self.fbm(x + 5.2, y + 1.3, octaves)
        return self.fbm(x + qx * amount, y + qy * amount, octaves)

    def turbulence(self, x, y, octaves=4):
        value = 0
        amplitude = 1
        frequency = 1
        maximum = 0
        for _ in range(octaves):
            value += abs(self.noise2d(x * frequency, y * frequency) * 2 - 1) * amplitude
            maximum += amplitude
            amplitude *= 0.5
            frequency *= 2
        return value / maximum


def draw_gradient_rect(base, top, bottom, alpha=90, stop=0.7):
    width, height = base.size
    gradient_height = max(1, int(height * stop))
    gradient = Image.new("RGBA", (1, gradient_height), (0, 0, 0, 0))
    pixels = gradient.load()
    for y in range(gradient_height):
        amount = y / max(1, height * stop)
        color = mix_color(top, bottom, amount)
        pixels[0, y] = (*color, alpha)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    overlay.paste(gradient.resize((width, gradient_height)), (0, 0))
    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def generate_mountain_profile(noise, width, height, base_y, layer_seed, complexity, rng):
    points = []
    segments = max(80, math.ceil(width / 6))
    for index in range(segments + 1):
        x = (index / segments) * width
        nx = x / width
        elevation = 0
        elevation += noise.warp(nx * 1.2 + layer_seed, layer_seed * 0.1, 0.8, 3) * 0.35
        ridge = noise.ridge(nx * 1.8 + layer_seed * 2, layer_seed * 0.2, 4, 2.5)
        elevation += ridge * 0.4 * complexity
        elevation += noise.ridge(nx * 3 + layer_seed * 3, layer_seed * 0.3, 3, 1.8) * 0.15 * complexity
        elevation += noise.turbulence(nx * 6 + layer_seed * 4, layer_seed * 0.4, 4) * 0.1 * complexity
        valley = noise.fbm(nx * 0.6 + layer_seed * 5, 0, 2)
        valley_depth = math.pow(max(0, 0.4 - valley), 2) * 3
        elevation *= 1 - valley_depth * 0.6
        left_fade = math.pow(math.sin(min(nx * 2, 1) * (math.pi / 2)), 0.6)
        right_fade = math.pow(math.sin(min((1 - nx) * 2, 1) * (math.pi / 2)), 0.6)
        elevation *= left_fade * right_fade
        if ridge > 0.6 and rng.random() > 0.7:
            elevation += rng.random() * 0.08 * complexity
        points.append((x, base_y - elevation * height * 0.45))
    return points


def draw_mountain_layer(base, points, color, alpha, bottom_y, strokes=False, rng=None):
    width, height = base.size
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    polygon = [(-10, height + 10), *points, (width + 10, height + 10)]
    draw.polygon(polygon, fill=(*color, alpha))

    if strokes and rng:
        stroke_count = 0
        for index in range(2, len(points) - 2, 4):
            if rng.random() > 0.28:
                continue
            x, y = points[index]
            next_x, next_y = points[index + 1]
            prev_x, prev_y = points[index - 1]
            slope = (next_y - prev_y) / max(1, next_x - prev_x)
            for _ in range(1 + int(rng.random() * 4)):
                length = 8 + rng.random() * 34
                start_y = y + 8 + rng.random() * 70
                if start_y > bottom_y:
                    continue
                end_y = start_y + slope * length + (rng.random() - 0.5) * 5
                line_alpha = int(18 + rng.random() * 28)
                line_width = max(1, int(1 + rng.random() * 2))
                draw.line(
                    (x - length / 2, start_y, x + length / 2, end_y),
                    fill=(*color, line_alpha),
                    width=line_width,
                )
                stroke_count += 1
                if stroke_count > 360:
                    break

    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def draw_mist(base, theme, rng):
    width, height = base.size
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    mist = mix_color(theme["paper_alt"], (245, 245, 238), 0.45)
    for _ in range(5 + rng.randrange(4)):
        y = height * (0.32 + rng.random() * 0.42)
        band_h = height * (0.035 + rng.random() * 0.07)
        x0 = -width * 0.08 + rng.random() * width * 0.12
        draw.rounded_rectangle(
            (x0, y, x0 + width * (0.8 + rng.random() * 0.35), y + band_h),
            radius=int(band_h / 2),
            fill=(*mist, int(20 + rng.random() * 34)),
        )
    overlay = overlay.filter(ImageFilter.GaussianBlur(max(12, width // 95)))
    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def draw_water(base, theme, rng):
    width, height = base.size
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    water_y = height * 0.82
    water_color = mix_color(theme["paper_alt"], theme["wash"], 0.18)
    draw.rectangle((0, water_y, width, height), fill=(*water_color, 42))
    ripple_color = mix_color(theme["ink"], theme["wash"], 0.45)
    for index in range(16):
        y = water_y + 10 + index * height * 0.013 + rng.random() * 8
        amplitude = 2 + rng.random() * 4
        step = width / 8
        points = []
        for segment in range(9):
            x = segment * step
            points.append((x, y + math.sin(segment + rng.random()) * amplitude))
        draw.line(points, fill=(*ripple_color, max(8, 26 - index)), width=1)
    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def draw_tree(draw, x, y, size, color, alpha, rng):
    lean = (rng.random() - 0.5) * size * 0.25
    draw.line((x, y, x + lean, y - size), fill=(*color, alpha), width=max(1, int(size * 0.025)))
    if rng.random() > 0.45:
        for index in range(5):
            by = y - size * (0.22 + index * 0.13)
            bw = size * (0.42 - index * 0.035)
            draw.arc(
                (x - bw, by - size * 0.05, x + bw, by + size * 0.14),
                185,
                355,
                fill=(*color, int(alpha * 0.75)),
                width=max(1, int(size * 0.025)),
            )
    else:
        for index in range(3):
            cy = y - size * (0.42 + index * 0.18)
            cx = x + lean * (1 - index * 0.18)
            draw.ellipse(
                (
                    cx - size * 0.23,
                    cy - size * 0.07,
                    cx + size * 0.23,
                    cy + size * 0.07,
                ),
                fill=(*color, int(alpha * (0.7 - index * 0.08))),
            )


def draw_scene_details(base, theme, rng):
    width, height = base.size
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    ink = theme["ink"]

    for _ in range(7 + rng.randrange(6)):
        x = width * (0.05 + rng.random() * 0.9)
        y = height * (0.58 + rng.random() * 0.22)
        draw_tree(draw, x, y, height * (0.035 + rng.random() * 0.05), ink, 80, rng)

    if rng.random() > 0.25:
        bx = width * (0.18 + rng.random() * 0.58)
        by = height * (0.14 + rng.random() * 0.16)
        for _ in range(4 + rng.randrange(5)):
            x = bx + (rng.random() - 0.5) * width * 0.09
            y = by + (rng.random() - 0.5) * height * 0.06
            size = 5 + rng.random() * 7
            draw.arc((x - size, y - size, x, y + size), 210, 340, fill=(*ink, 80), width=1)
            draw.arc((x, y - size, x + size, y + size), 200, 330, fill=(*ink, 80), width=1)

    if rng.random() > 0.35:
        x = width * (0.18 + rng.random() * 0.55)
        y = height * (0.835 + rng.random() * 0.035)
        size = width * (0.018 + rng.random() * 0.014)
        draw.pieslice((x - size, y - size * 0.35, x + size, y + size * 0.45), 0, 180, fill=(*ink, 82))
        draw.line((x + size * 0.12, y, x + size * 0.12, y - size * 0.58), fill=(*ink, 82), width=max(1, int(size * 0.06)))
        draw.arc((x - size * 0.08, y - size * 0.72, x + size * 0.32, y - size * 0.2), 205, 335, fill=(*ink, 70), width=1)

    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def draw_shanshui_background(width, height, theme):
    seed = random.randrange(1_000_000_000)
    rng = random.Random(seed)
    noise = Noise2D(seed)
    base = Image.new("RGB", (width, height), theme["paper"])
    sky_top = mix_color(theme["paper_alt"], (230, 235, 232), 0.35)
    base = draw_gradient_rect(base, sky_top, theme["paper"], alpha=115, stop=0.72)
    base = add_paper_texture(base, theme)

    mountain_specs = [
        (0.40, 0.52, 0.18, 5, 55),
        (0.48, 0.70, 0.28, 4, 72),
        (0.56, 0.84, 0.40, 3, 92),
        (0.66, 1.00, 0.58, 2, 116),
        (0.76, 1.12, 0.75, 1, 138),
    ]
    for idx, (base_pct, complexity, color_amount, layer_seed, alpha) in enumerate(mountain_specs):
        color = mix_color(theme["paper_alt"], theme["ink"], color_amount)
        points = generate_mountain_profile(
            noise,
            width,
            height,
            height * base_pct,
            layer_seed,
            complexity,
            rng,
        )
        base = draw_mountain_layer(
            base,
            points,
            color,
            alpha,
            height * 0.9,
            strokes=idx >= 2,
            rng=rng,
        )
        if idx in (1, 3):
            base = draw_mist(base, theme, rng)

    base = draw_water(base, theme, rng)
    base = draw_scene_details(base, theme, rng)
    base = draw_mist(base, theme, rng)
    if random.random() < 0.45:
        base = add_deckle_shadow(base, theme)
    return base


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
    base = draw_shanshui_background(width, height, theme)
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
