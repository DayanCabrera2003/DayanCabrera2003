"""Build the typed tagline SVG.

    build_decor.py

Writes assets/typing.svg.
"""

from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

PHRASES = [
    "I write compilers in Rust.",
    "I cluster 10K news articles a day.",
    "I send chat over raw Ethernet frames.",
    "Run my compiler right below.",
]
WIDTH, HEIGHT = 600, 44
FONT_SIZE = 24
CHAR = FONT_SIZE * 0.6
SLOT_SECONDS = 4.5


def typing() -> str:
    total = SLOT_SECONDS * len(PHRASES)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        f'aria-label="{" ".join(PHRASES)}">',
        f"<style>text{{font:600 {FONT_SIZE}px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;"
        "fill:#2f81f7}.c{fill:#2f81f7}"
        "</style>",
    ]
    for index, phrase in enumerate(PHRASES):
        length = len(phrase) * CHAR
        left = (WIDTH - length) / 2
        start = index * SLOT_SECONDS
        # Type in, hold, delete, then stay hidden until this phrase's next turn.
        marks = [0, start, start + 1.5, start + 3.6, start + 4.2, total]
        reveal = [0, 0, length, length, 0, 0]
        shown = ["0", "1", "1", "1", "0", "0"]
        if start == 0:
            # Key times must strictly increase, so the first phrase has no lead-in.
            marks, reveal, shown = marks[1:], reveal[1:], shown[1:]
        times = ";".join(f"{mark / total:.4f}" for mark in marks)
        widths = ";".join(f"{value:g}" for value in reveal)
        cursor = ";".join(f"{left + value + 3:g}" for value in reveal)
        shown = ";".join(shown)
        common = f'dur="{total:g}s" repeatCount="indefinite" keyTimes="{times}"'
        out += [
            f'<clipPath id="p{index}"><rect x="{left:g}" y="0" height="{HEIGHT}" width="0">'
            f'<animate attributeName="width" values="{widths}" {common}/></rect></clipPath>',
            f'<text x="{left:g}" y="30" textLength="{length:g}" clip-path="url(#p{index})">'
            f"{phrase}</text>",
            f'<rect class="c" y="8" width="3" height="28" opacity="0">'
            f'<animate attributeName="x" values="{cursor}" {common}/>'
            f'<animate attributeName="opacity" calcMode="discrete" values="{shown}" {common}/></rect>',
        ]
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    (ASSETS / "typing.svg").write_text(typing(), encoding="utf-8")


if __name__ == "__main__":
    main()
