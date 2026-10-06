"""Community Tetris: every visitor move is one issue.

    tetris.py left | right | rotate | drop    a move by PLAYER
    tetris.py auto                            the bot places the current piece

Rewrites tetris/state.json, assets/tetris.svg and the TETRIS block in README.md.
"""

import json
import os
import random
import re
import sys
from pathlib import Path

from readme_block import replace_block

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "tetris" / "state.json"
SVG = ROOT / "assets" / "tetris.svg"

COLS, ROWS = 10, 20
CELL = 16
PANEL = 84
BOT = "the bot"
LOGIN = re.compile(r"^[A-Za-z0-9-]{1,39}$")
LINE_POINTS = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}
FALL_STEP_SECONDS = 0.14
REST_STEPS = 10

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


def empty_board() -> Board:
    return [["."] * COLS for _ in range(ROWS)]


def new_game(best: int = 0, games: int = 0) -> dict:
    state = {
        "board": ["." * COLS] * ROWS, "queue": [], "score": 0, "lines": 0, "pieces": 0,
        "best": best, "games": games, "players": {}, "last": None,
    }
    spawn(state)
    return state


def refill(state: dict) -> None:
    """Keep at least two pieces queued, drawn from shuffled bags of all seven."""
    while len(state["queue"]) < 2:
        bag = list(PIECES)
        random.Random(f"{state['games']}:{state['pieces']}:{len(state['queue'])}").shuffle(bag)
        state["queue"] += bag


def spawn(state: dict) -> None:
    refill(state)
    state["piece"] = state["queue"].pop(0)
    state["rot"], state["x"] = 0, 3
    refill(state)


def cells(piece: str, rot: int, x: int, y: int) -> list[tuple[int, int]]:
    return [(x + dx, y + dy) for dx, dy in PIECES[piece][rot % len(PIECES[piece])]]


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


def lock(board: Board, piece: str, rot: int, x: int) -> tuple[Board, int]:
    """Drop the piece, clear full rows; returns the new board and rows cleared."""
    y = landing_row(board, piece, rot, x)
    board = [row[:] for row in board]
    for cx, cy in cells(piece, rot, x, y):
        board[cy][cx] = piece
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


def best_placement(board: Board, piece: str) -> tuple[int, int]:
    options = []
    for rot in range(len(PIECES[piece])):
        for x in range(-2, COLS):
            if fits(board, piece, rot, x, 0):
                after, cleared = lock(board, piece, rot, x)
                options.append((badness(after, cleared), rot, x))
    _, rot, x = min(options)
    return rot, x


def apply(state: dict, action: str, player: str) -> str:
    """Apply one move and return a sentence describing what happened."""
    board = [list(row) for row in state["board"]]
    piece, rot, x = state["piece"], state["rot"], state["x"]
    note = ""

    if action in ("left", "right"):
        step = -1 if action == "left" else 1
        if fits(board, piece, rot, x + step, 0):
            state["x"] = x + step
            note = f"Moved the {piece} piece {action}."
        else:
            note = f"The {piece} piece is already against the {action} wall."
    elif action == "rotate":
        turned = (rot + 1) % len(PIECES[piece])
        for kick in (0, -1, 1, -2, 2):
            if fits(board, piece, turned, x + kick, 0):
                state["rot"], state["x"] = turned, x + kick
                note = f"Rotated the {piece} piece."
                break
        else:
            note = "No room to rotate there."
    else:
        if action == "auto":
            rot, x = best_placement(board, piece)
        board, cleared = lock(board, piece, rot, x)
        state["board"] = ["".join(row) for row in board]
        state["score"] += 10 + LINE_POINTS[cleared]
        state["lines"] += cleared
        state["pieces"] += 1
        note = f"Dropped the {piece} piece" + (f" and cleared {cleared} line(s)!" if cleared else ".")
        spawn(state)
        if not fits(board, state["piece"], 0, state["x"], 0):
            final = state["score"]
            fresh = new_game(max(state["best"], final), state["games"] + 1)
            fresh["players"] = {}
            state.clear()
            state.update(fresh)
            note += f" The stack reached the top: game over with {final} points. New game started."

    if player != BOT:
        state["players"][player] = state["players"].get(player, 0) + 1
    state["last"] = {"player": player, "action": action}
    return note


def block(x: float, y: float, piece: str, extra: str = "") -> str:
    return (
        f'<rect x="{x + 1:g}" y="{y + 1:g}" width="{CELL - 2}" height="{CELL - 2}" rx="3" '
        f'fill="{COLORS[piece]}"{extra}/>'
    )


def render(state: dict) -> str:
    board = [list(row) for row in state["board"]]
    piece, rot, x = state["piece"], state["rot"], state["x"]
    land = landing_row(board, piece, rot, x)
    width, height = COLS * CELL + PANEL, ROWS * CELL
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Community Tetris board">',
        "<style>text{font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace;fill:#8b949e}"
        ".n{font-size:15px;fill:#58a6ff}</style>",
        f'<rect width="{COLS * CELL}" height="{height}" rx="6" fill="#808080" fill-opacity="0.12"/>',
    ]
    for col in range(1, COLS):
        out.append(
            f'<path d="M{col * CELL} 0V{height}" stroke="#808080" stroke-opacity="0.12"/>'
        )
    for row in range(ROWS):
        for col in range(COLS):
            if board[row][col] != ".":
                out.append(block(col * CELL, row * CELL, board[row][col]))

    # Where the piece will land, then the piece itself falling there on a loop.
    for cx, cy in cells(piece, rot, x, land):
        out.append(block(cx * CELL, cy * CELL, piece, ' fill-opacity="0.22"'))
    steps = [f"0 {step * CELL}" for step in range(land + 1)] + [f"0 {land * CELL}"] * REST_STEPS
    out.append(
        '<g><animateTransform attributeName="transform" type="translate" calcMode="discrete" '
        f'dur="{len(steps) * FALL_STEP_SECONDS:.2f}s" repeatCount="indefinite" '
        f'values="{";".join(steps)}"/>'
    )
    out += [block(cx * CELL, cy * CELL, piece) for cx, cy in cells(piece, rot, x, 0)]
    out.append("</g>")

    left = COLS * CELL + 14
    out.append(f'<text x="{left}" y="16">NEXT</text>')
    nxt = state["queue"][0]
    out += [block(left + dx * CELL, 24 + dy * CELL, nxt) for dx, dy in PIECES[nxt][0]]
    for index, (label, value) in enumerate(
        [("SCORE", state["score"]), ("LINES", state["lines"]), ("BEST", state["best"])]
    ):
        top = 104 + index * 44
        out.append(f'<text x="{left}" y="{top}">{label}</text>')
        out.append(f'<text class="n" x="{left}" y="{top + 18}">{value}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def link(user: str) -> str:
    return user if user == BOT else f"[@{user}](https://github.com/{user})"


def summary(state: dict) -> str:
    lines = [
        f"Score **{state['score']}** · Lines **{state['lines']}** · Best **{state['best']}** · "
        f"Pieces placed **{state['pieces']}**"
    ]
    if state["last"]:
        lines.append(f"Last move: `{state['last']['action']}` by {link(state['last']['player'])}")
    if state["players"]:
        top = sorted(state["players"].items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        lines.append("Most moves this game: " + " · ".join(f"{link(u)} {n}" for u, n in top))
    return "\n\n".join(lines)


def main() -> None:
    action = sys.argv[1].strip().lower()
    if action not in ("left", "right", "rotate", "drop", "auto"):
        sys.exit("Unknown move. Use one of: left, right, rotate, drop.")
    player = BOT if action == "auto" else os.environ["PLAYER"]
    if player != BOT and not LOGIN.match(player):
        sys.exit("unexpected login")
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else new_game()
    print(apply(state, action, player))
    STATE.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    SVG.write_text(render(state), encoding="utf-8")
    replace_block("TETRIS", summary(state))


if __name__ == "__main__":
    main()
