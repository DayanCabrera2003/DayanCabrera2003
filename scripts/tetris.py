"""Self-playing Tetris: generates one whole game as a looping animated SVG.

    tetris.py [seed]

A deliberately imperfect bot plays until the stack reaches the top, so every
seed gives a different game. Rewrites assets/tetris.svg and the TETRIS block
in README.md.
"""

import random
import sys
import time
from pathlib import Path

from readme_block import replace_block

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "tetris.svg"

COLS, ROWS = 10, 20
CELL = 16
FRAME_SECONDS = 0.07
CLEAR_FRAMES = 4
END_FRAMES = 40
MAX_PIECES = 140
# How often the bot ignores its own advice and drops the piece anywhere.
BLUNDER_RATE = 0.3

# Each piece: its rotations, each a list of (x, y) cells inside a 4x4 box.
PIECES = {
    "I": [[(0, 1), (1, 1), (2, 1), (3, 1)], [(2, 0), (2, 1), (2, 2), (2, 3)]],
    "O": [[(1, 0), (2, 0), (1, 1), (2, 1)]],
    "T": [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)],
    ],
    "S": [[(1, 0), (2, 0), (0, 1), (1, 1)], [(1, 0), (1, 1), (2, 1), (2, 2)]],
    "Z": [[(0, 0), (1, 0), (1, 1), (2, 1)], [(2, 0), (1, 1), (2, 1), (1, 2)]],
    "J": [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (0, 2), (1, 2)],
    ],
    "L": [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
    ],
}
COLORS = {
    "I": "#22b8cf", "O": "#f5b301", "T": "#a55eea", "S": "#37b24d",
    "Z": "#f03e3e", "J": "#4c6ef5", "L": "#f76707",
}

Board = list[list[str]]
Frame = dict[tuple[int, int], str]


def cells(piece: str, rot: int, x: int, y: int) -> list[tuple[int, int]]:
    return [(x + dx, y + dy) for dx, dy in PIECES[piece][rot]]


def fits(board: Board, piece: str, rot: int, x: int, y: int) -> bool:
    return all(
        0 <= cx < COLS and cy < ROWS and (cy < 0 or board[cy][cx] == ".")
        for cx, cy in cells(piece, rot, x, y)
    )


def landing_row(board: Board, piece: str, rot: int, x: int) -> int:
    y = 0
    while fits(board, piece, rot, x, y + 1):
        y += 1
    return y


def place(board: Board, piece: str, rot: int, x: int) -> Board:
    board = [row[:] for row in board]
    for cx, cy in cells(piece, rot, x, landing_row(board, piece, rot, x)):
        board[cy][cx] = piece
    return board


def clear(board: Board) -> tuple[Board, int]:
    kept = [row for row in board if "." in row]
    cleared = ROWS - len(kept)
    return [["."] * COLS for _ in range(cleared)] + kept, cleared


def badness(board: Board, cleared: int) -> float:
    """Lower is better: penalise height, holes and a bumpy surface."""
    heights = []
    holes = 0
    for col in range(COLS):
        column = [board[row][col] for row in range(ROWS)]
        top = next((row for row, value in enumerate(column) if value != "."), ROWS)
        heights.append(ROWS - top)
        holes += column[top:].count(".")
    bumps = sum(abs(a - b) for a, b in zip(heights, heights[1:]))
    return 0.51 * sum(heights) + 0.36 * holes + 0.18 * bumps - 0.76 * cleared


def choose(board: Board, piece: str, rng: random.Random) -> tuple[int, int] | None:
    options = []
    for rot in range(len(PIECES[piece])):
        for x in range(-2, COLS):
            if fits(board, piece, rot, x, 0):
                after, cleared = clear(place(board, piece, rot, x))
                options.append((badness(after, cleared), rot, x))
    if not options:
        return None
    _, rot, x = rng.choice(options) if rng.random() < BLUNDER_RATE else min(options)
    return rot, x


def snapshot(board: Board, falling: list[tuple[int, int]] = (), piece: str = "") -> Frame:
    frame = {(c, r): board[r][c] for r in range(ROWS) for c in range(COLS) if board[r][c] != "."}
    frame.update({(cx, cy): piece for cx, cy in falling if cy >= 0})
    return frame


def play(seed: int) -> tuple[list[Frame], int, int]:
    """Play one game; returns its frames, pieces placed and lines cleared."""
    rng = random.Random(seed)
    board: Board = [["."] * COLS for _ in range(ROWS)]
    frames: list[Frame] = []
    bag: list[str] = []
    placed = lines = 0
    while placed < MAX_PIECES:
        if not bag:
            bag = list(PIECES)
            rng.shuffle(bag)
        piece = bag.pop()
        choice = choose(board, piece, rng)
        if choice is None:
            break
        rot, x = choice
        for y in range(landing_row(board, piece, rot, x) + 1):
            frames.append(snapshot(board, cells(piece, rot, x, y), piece))
        board = place(board, piece, rot, x)
        placed += 1
        after, cleared = clear(board)
        if cleared:
            frames += [snapshot(board)] * CLEAR_FRAMES
            lines += cleared
        board = after
    frames += [snapshot(board)] * END_FRAMES
    return frames, placed, lines


def render(frames: list[Frame]) -> str:
    total = len(frames)
    on: dict[tuple[int, int, str], list[int]] = {}
    for index, frame in enumerate(frames):
        for (col, row), piece in frame.items():
            on.setdefault((col, row, piece), []).append(index)

    width, height = COLS * CELL, ROWS * CELL
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="A game of Tetris playing itself">',
        "<style>"
        + "".join(f".{piece}{{fill:{color}}}" for piece, color in COLORS.items())
        + "</style>",
        f'<path d="M0 0H{width}V{height}H0Z" fill="#808080" fill-opacity="0.12"/>',
    ]
    duration = f"{total * FRAME_SECONDS:.2f}s"
    for (col, row, piece), indexes in sorted(on.items()):
        lit = set(indexes)
        values, times = [], []
        for index in range(total):
            value = "1" if index in lit else "0"
            if not values or values[-1] != value:
                values.append(value)
                times.append(f"{index / total:.5f}".rstrip("0").rstrip(".") or "0")
        out.append(
            f'<rect class="{piece}" x="{col * CELL + 1}" y="{row * CELL + 1}" width="{CELL - 2}" '
            f'height="{CELL - 2}" rx="3" opacity="0">'
            f'<animate attributeName="opacity" calcMode="discrete" dur="{duration}" '
            f'repeatCount="indefinite" values="{";".join(values)}" keyTimes="{";".join(times)}"/>'
            "</rect>"
        )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else int(time.time())
    frames, placed, lines = play(seed)
    SVG.write_text(render(frames), encoding="utf-8")
    replace_block(
        "TETRIS",
        f"Game `#{seed}` · **{placed}** pieces · **{lines}** lines cleared · "
        "a new game is generated every few hours",
    )
    print(f"seed={seed} pieces={placed} lines={lines} frames={len(frames)}")


if __name__ == "__main__":
    main()
