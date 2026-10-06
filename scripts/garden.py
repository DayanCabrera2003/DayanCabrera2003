"""Community Game of Life garden.

    garden.py plant   plants PATTERN for PLANTER (placement seeded by SEED), then grows
    garden.py tick    grows the garden a few generations

Both rewrite garden/state.json, assets/garden.svg and the GARDEN block in README.md.
"""

import hashlib
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path

from readme_block import replace_block

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "garden" / "state.json"
SVG = ROOT / "assets" / "garden.svg"

COLS, ROWS = 40, 24
CELL = 10
GROW_PER_EVENT = 6
FRAMES = 64
FRAME_SECONDS = 0.22
MAX_LOG = 5
GARDENER = "DayanCabrera2003"
LOGIN = re.compile(r"^[A-Za-z0-9-]{1,39}$")

PATTERNS = {
    "glider": [".#.", "..#", "###"],
    "spaceship": [".#..#", "#....", "#...#", "####."],
    "r-pentomino": [".##", "##.", ".#."],
    "acorn": [".#.....", "...#...", "##..###"],
    "pulsar": [
        "..###...###..",
        ".............",
        "#....#.#....#",
        "#....#.#....#",
        "#....#.#....#",
        "..###...###..",
        ".............",
        "..###...###..",
        "#....#.#....#",
        "#....#.#....#",
        "#....#.#....#",
        ".............",
        "..###...###..",
    ],
}

Cells = dict[tuple[int, int], str]


def load() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"generation": 0, "cells": [], "log": [], "planted": {}}


def to_cells(state: dict) -> Cells:
    return {(x, y): owner for x, y, owner in state["cells"]}


def step(cells: Cells) -> Cells:
    """One generation on a torus. A newborn cell belongs to whoever owns most of its parents."""
    parents: dict[tuple[int, int], list[str]] = {}
    for (x, y), owner in cells.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    parents.setdefault(((x + dx) % COLS, (y + dy) % ROWS), []).append(owner)
    nxt: Cells = {}
    for pos, owners in parents.items():
        if pos in cells and len(owners) in (2, 3):
            nxt[pos] = cells[pos]
        elif pos not in cells and len(owners) == 3:
            nxt[pos] = sorted(Counter(owners).items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return nxt


def stamp(cells: Cells, pattern: str, owner: str, rng: random.Random) -> None:
    rows = PATTERNS[pattern]
    if rng.random() < 0.5:
        rows = [row[::-1] for row in rows]
    if rng.random() < 0.5:
        rows = rows[::-1]
    ox, oy = rng.randrange(COLS), rng.randrange(ROWS)
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch == "#":
                cells[((ox + dx) % COLS, (oy + dy) % ROWS)] = owner


def color(owner: str) -> str:
    hue = int(hashlib.sha256(owner.encode()).hexdigest()[:4], 16) % 360
    return f"hsl({hue} 72% 56%)"


def render(cells: Cells) -> str:
    """Animated SVG looping over the next FRAMES generations."""
    alive: dict[tuple[int, int, str], list[int]] = {}
    for frame in range(FRAMES):
        for (x, y), owner in cells.items():
            alive.setdefault((x, y, owner), []).append(frame)
        cells = step(cells)

    width, height = COLS * CELL, ROWS * CELL
    duration = f"{FRAMES * FRAME_SECONDS:.2f}s"
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Community Game of Life garden">',
        f'<rect width="{width}" height="{height}" rx="8" fill="#808080" fill-opacity="0.10"/>',
    ]
    for (x, y, owner), frames in sorted(alive.items()):
        rect = (
            f'<rect x="{x * CELL + 1}" y="{y * CELL + 1}" width="{CELL - 2}" height="{CELL - 2}" '
            f'rx="2" fill="{color(owner)}"'
        )
        if len(frames) == FRAMES:
            out.append(rect + "/>")
            continue
        on = set(frames)
        values, times = [], []
        for frame in range(FRAMES):
            value = "1" if frame in on else "0"
            if not values or values[-1] != value:
                values.append(value)
                times.append(f"{frame / FRAMES:.4f}".rstrip("0").rstrip(".") or "0")
        out.append(
            f'{rect} opacity="{values[0]}"><animate attributeName="opacity" calcMode="discrete" '
            f'dur="{duration}" repeatCount="indefinite" values="{";".join(values)}" '
            f'keyTimes="{";".join(times)}"/></rect>'
        )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def link(user: str) -> str:
    return f"[@{user}](https://github.com/{user})"


def summary(state: dict, cells: Cells) -> str:
    owned = Counter(cells.values())
    lines = [f"Generation **{state['generation']}** · **{len(cells)}** living cells"]
    if owned:
        top = " · ".join(f"{link(user)} {count}" for user, count in owned.most_common(5))
        lines.append(f"Cells alive by gardener: {top}")
    if state["log"]:
        last = state["log"][-1]
        lines.append(f"Last planted: `{last['pattern']}` by {link(last['user'])}")
    return "\n\n".join(lines)


def main() -> None:
    action = sys.argv[1]
    state = load()
    cells = to_cells(state)

    if action == "plant":
        pattern = os.environ["PATTERN"].strip().lower()
        planter = os.environ["PLANTER"]
        if pattern not in PATTERNS:
            sys.exit(f"unknown pattern; choose one of: {', '.join(PATTERNS)}")
        if not LOGIN.match(planter):
            sys.exit("unexpected login")
        stamp(cells, pattern, planter, random.Random(os.environ.get("SEED", "")))
        state["log"] = (state["log"] + [{"user": planter, "pattern": pattern}])[-MAX_LOG:]
        state["planted"][planter] = state["planted"].get(planter, 0) + 1
    elif action != "tick":
        sys.exit(f"unknown action: {action}")

    for _ in range(GROW_PER_EVENT):
        cells = step(cells)
        state["generation"] += 1
    if not cells:
        # A dead garden gets reseeded so there is always something to watch.
        stamp(cells, "r-pentomino", GARDENER, random.Random(state["generation"]))

    state["cells"] = sorted([x, y, owner] for (x, y), owner in cells.items())
    STATE.write_text(json.dumps(state, separators=(",", ":")) + "\n", encoding="utf-8")
    SVG.write_text(render(cells), encoding="utf-8")
    replace_block("GARDEN", summary(state, cells))


if __name__ == "__main__":
    main()
