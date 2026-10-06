"""Build the animated avatar SVGs from the chibi sprite poses.

    build_avatar.py <sprites/el directory>

Writes assets/avatar-day.svg and assets/avatar-night.svg. Each pose is embedded
as a WebP frame and shown in turn with CSS keyframes, so the result is a single
self-contained file that works inside an <img>.
"""

import base64
import io
import sys
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent.parent / "assets"
WIDTH, HEIGHT = 300, 490
LOOP_SECONDS = 9

# (pose, start %, end %) over one loop.
DAY = [
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
NIGHT = [("dormido", 0, 100)]


def frame(sprites: Path, pose: str) -> tuple[str, int, int]:
    image = Image.open(sprites / f"{pose}.png").convert("RGBA")
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=82, method=6)
    data = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/webp;base64,{data}", image.width, image.height


def keyframes(name: str, spans: list[tuple[int, int]]) -> str:
    stops = {0: 0, 100: 0}
    for start, end in spans:
        stops[start] = 1
        stops.setdefault(end, 0)
    if any(start == 0 for start, _ in spans):
        stops[100] = 1
    body = "".join(f"{pct}%{{opacity:{value}}}" for pct, value in sorted(stops.items()))
    return f"@keyframes {name}{{{body}}}"


def build(sprites: Path, timeline: list[tuple[str, int, int]], label: str, extra: str = "") -> str:
    poses: dict[str, list[tuple[int, int]]] = {}
    for pose, start, end in timeline:
        poses.setdefault(pose, []).append((start, end))

    css = [
        "image{opacity:0;animation-duration:%ds;animation-iteration-count:infinite;"
        "animation-timing-function:step-end}" % LOOP_SECONDS,
        ".body{animation:breathe 3s ease-in-out infinite;transform-origin:50% 100%}",
        "@keyframes breathe{0%,100%{transform:scaleY(1)}50%{transform:scaleY(1.012)}}",
        "@media (prefers-reduced-motion:reduce){.body,image,.z{animation:none!important}"
        ".still{opacity:1}}",
    ]
    images = []
    for index, (pose, spans) in enumerate(poses.items()):
        href, width, height = frame(sprites, pose)
        still = " still" if index == 0 else ""
        if len(timeline) == 1:
            css.append(f".{pose}{{opacity:1}}")
        else:
            css.append(keyframes(pose, spans))
            css.append(f".{pose}{{animation-name:{pose}}}")
        images.append(
            f'<image class="{pose}{still}" href="{href}" x="{(WIDTH - width) / 2:g}" '
            f'y="{HEIGHT - height}" width="{width}" height="{height}"/>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        f'aria-label="{label}"><style>{"".join(css)}{extra_css(extra)}</style>'
        f'<g class="body">{"".join(images)}</g>{extra}</svg>\n'
    )


def extra_css(extra: str) -> str:
    if not extra:
        return ""
    return (
        ".z{font:700 34px ui-monospace,monospace;fill:#8b9bb4;opacity:0;"
        "animation:float 3s ease-out infinite}"
        ".z2{animation-delay:1s}.z3{animation-delay:2s}"
        "@keyframes float{0%{opacity:0;transform:translate(0,0) scale(.6)}"
        "25%{opacity:1}100%{opacity:0;transform:translate(26px,-70px) scale(1.2)}}"
    )


SNORE = (
    '<text class="z" x="205" y="170">z</text>'
    '<text class="z z2" x="205" y="170">z</text>'
    '<text class="z z3" x="205" y="170">z</text>'
)


def main() -> None:
    sprites = Path(sys.argv[1])
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "avatar-day.svg").write_text(build(sprites, DAY, "Dayan waving"), encoding="utf-8")
    (ASSETS / "avatar-night.svg").write_text(
        build(sprites, NIGHT, "Dayan asleep", SNORE), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
