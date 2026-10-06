"""Build one animated avatar SVG per state from the chibi artwork.

    build_avatar.py <sprites/el directory> <six-scene sheet.png>

Writes assets/avatar/<state>.svg. Every image is embedded as WebP, so each file
is self-contained and works inside an <img>. `wave` cycles through several
poses; the other states are a single drawing with a small idle motion.
"""

import base64
import io
import sys
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "assets" / "avatar"
SIZE = 400
LOOP_SECONDS = 9

# (pose, start %, end %) over one loop.
WAVE = [
    ("quieto", 0, 22),
    ("parpadeo", 22, 24),
    ("quieto", 24, 34),
    ("saludo", 34, 52),
    ("sonrisa", 52, 60),
    ("hablar", 60, 64),
    ("sonrisa", 64, 68),
    ("hablar", 68, 72),
    ("sonrisa", 72, 78),
    ("quieto", 78, 88),
    ("parpadeo", 88, 90),
    ("quieto", 90, 100),
]
WAVE_SCALE = SIZE / 490

# Sheet cells, left to right and top to bottom: (state, alt text, idle motion).
SHEET_COLS, SHEET_ROWS = 3, 2
SHEET = [
    ("coding", "Dayan coding at a desk", "breathe"),
    ("shipped", "Dayan celebrating a pushed commit", "hop"),
    ("night", "Dayan coding at night under a desk lamp", "breathe"),
    ("vacation", "Dayan on vacation in a hammock", "sway"),
    ("debugging", "Dayan puzzled, holding a laptop", "breathe"),
    ("coffee", "Dayan yawning with a morning coffee", "breathe"),
]

MOTION = (
    ".body{transform-origin:50% 100%}"
    ".breathe{animation:breathe 3s ease-in-out infinite}"
    ".hop{animation:hop 1.1s ease-in-out infinite}"
    ".sway{animation:sway 4s ease-in-out infinite;transform-origin:50% 0}"
    "@keyframes breathe{0%,100%{transform:scaleY(1)}50%{transform:scaleY(1.012)}}"
    "@keyframes hop{0%,55%,100%{transform:translateY(0)}28%{transform:translateY(-14px)}}"
    "@keyframes sway{0%,100%{transform:rotate(-1.2deg)}50%{transform:rotate(1.2deg)}}"
)
REDUCED = "@media (prefers-reduced-motion:reduce){*{animation:none!important}.still{opacity:1}}"
SNORE_CSS = (
    ".z{font:700 30px ui-monospace,monospace;fill:#8b9bb4;opacity:0;"
    "animation:float 3s ease-out infinite}.z2{animation-delay:1s}.z3{animation-delay:2s}"
    "@keyframes float{0%{opacity:0;transform:translate(0,0) scale(.6)}25%{opacity:1}"
    "100%{opacity:0;transform:translate(26px,-70px) scale(1.2)}}"
)
SNORE = "".join(f'<text class="z{extra}" x="285" y="150">z</text>' for extra in ("", " z2", " z3"))


def embed(image: Image.Image, scale: float) -> tuple[str, int, int]:
    width, height = round(image.width * scale), round(image.height * scale)
    # Keep twice the display size so it stays sharp on high-density screens.
    stored = image.resize((min(image.width, width * 2), min(image.height, height * 2)), Image.LANCZOS)
    buffer = io.BytesIO()
    stored.save(buffer, "WEBP", quality=82, method=6)
    return f"data:image/webp;base64,{base64.b64encode(buffer.getvalue()).decode()}", width, height


def tag(image: Image.Image, scale: float, classes: str = "") -> str:
    href, width, height = embed(image, scale)
    cls = f' class="{classes}"' if classes else ""
    return (
        f'<image{cls} href="{href}" x="{(SIZE - width) / 2:g}" y="{SIZE - height}" '
        f'width="{width}" height="{height}"/>'
    )


def svg(label: str, css: str, body: str, motion: str, extra: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" role="img" '
        f'aria-label="{label}"><style>{MOTION}{css}{REDUCED}</style>'
        f'<g class="body {motion}">{body}</g>{extra}</svg>\n'
    )


def keyframes(name: str, spans: list[tuple[int, int]]) -> str:
    stops = {0: 0, 100: 0}
    for start, end in spans:
        stops[start] = 1
        stops.setdefault(end, 0)
    if any(start == 0 for start, _ in spans):
        stops[100] = 1
    body = "".join(f"{pct}%{{opacity:{value}}}" for pct, value in sorted(stops.items()))
    return f"@keyframes {name}{{{body}}}.{name}{{animation-name:{name}}}"


def wave(sprites: Path) -> str:
    poses: dict[str, list[tuple[int, int]]] = {}
    for pose, start, end in WAVE:
        poses.setdefault(pose, []).append((start, end))
    css = (
        f"image{{opacity:0;animation-duration:{LOOP_SECONDS}s;"
        "animation-iteration-count:infinite;animation-timing-function:step-end}"
    )
    images = []
    for index, (pose, spans) in enumerate(poses.items()):
        css += keyframes(pose, spans)
        image = Image.open(sprites / f"{pose}.png").convert("RGBA")
        images.append(tag(image, WAVE_SCALE, pose + (" still" if index == 0 else "")))
    return svg("Dayan waving", css, "".join(images), "breathe")


def asleep(sprites: Path) -> str:
    image = Image.open(sprites / "dormido.png").convert("RGBA")
    return svg("Dayan asleep", SNORE_CSS, tag(image, WAVE_SCALE), "breathe", SNORE)


def cells(sheet: Path) -> list[Image.Image]:
    image = Image.open(sheet).convert("RGBA")
    # The generator leaves colour under fully transparent pixels and stops just
    # short of full opacity; snap both ends so no halo shows on any background.
    alpha = image.getchannel("A").point(lambda a: 0 if a < 24 else 255 if a >= 224 else a)
    image.putalpha(alpha)
    width, height = image.width // SHEET_COLS, image.height // SHEET_ROWS
    out = []
    for index in range(SHEET_COLS * SHEET_ROWS):
        col, row = index % SHEET_COLS, index // SHEET_COLS
        cell = image.crop((col * width, row * height, (col + 1) * width, (row + 1) * height))
        out.append(cell.crop(cell.getbbox()))
    return out


def main() -> None:
    sprites, sheet = Path(sys.argv[1]), Path(sys.argv[2])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "wave.svg").write_text(wave(sprites), encoding="utf-8")
    (OUT / "asleep.svg").write_text(asleep(sprites), encoding="utf-8")
    for (state, label, motion), cell in zip(SHEET, cells(sheet)):
        scale = min((SIZE - 16) / cell.width, (SIZE - 16) / cell.height)
        (OUT / f"{state}.svg").write_text(svg(label, "", tag(cell, scale), motion), encoding="utf-8")


if __name__ == "__main__":
    main()
