"""Endless self-playing Tetris, rendered as a looping animated SVG.

    tetris.py [pieces]

Each run continues the same game from tetris/state.json: the bot places the
next batch of pieces and the animation shows that stretch on a loop. The bot
looks one piece ahead and keeps the stack low, so the game never ends.
Rewrites tetris/state.json, assets/tetris.svg and the TETRIS block in README.md.
"""

import json
import random
import sys
from pathlib import Path

from readme_block import replace_block

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "tetris" / "state.json"
SVG = ROOT / "assets" / "tetris.svg"

COLS, ROWS = 10, 20
CELL = 16
FRAME_SECONDS = 0.06
CLEAR_FRAMES = 5
END_FRAMES = 12
FADE_FRAMES = 8
PIECES_PER_RUN = 90

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
    y = landing_row(board, piece, rot, x)
    board = [row[:] for row in board]
    for cx, cy in cells(piece, rot, x, y):
        board[cy][cx] = piece
    return board


def clear(board: Board) -> tuple[Board, list[int]]:
    full = [index for index, row in enumerate(board) if "." not in row]
    kept = [row for row in board if "." in row]
    return [["."] * COLS for _ in full] + kept, full


def badness(board: Board, cleared: int) -> float:
    """Lower is better: penalise height, holes and a bumpy surface."""
    heights = []
    holes = 0
    for col in range(COLS):
        top = next((row for row in range(ROWS) if board[row][col] != "."), ROWS)
        heights.append(ROWS - top)
        holes += sum(1 for row in range(top, ROWS) if board[row][col] == ".")
    bumps = sum(abs(a - b) for a, b in zip(heights, heights[1:]))
    return 0.51 * sum(heights) + 0.36 * holes + 0.18 * bumps - 0.76 * cleared


def placements(board: Board, piece: str) -> list[tuple[int, int, Board, int]]:
    out = []
    for rot in range(len(PIECES[piece])):
        for x in range(-2, COLS):
            if fits(board, piece, rot, x, 0):
                after, full = clear(place(board, piece, rot, x))
                out.append((rot, x, after, len(full)))
    return out


def choose(board: Board, piece: str, upcoming: str) -> tuple[int, int] | None:
    """Best spot for `piece`, judged by the best follow-up with the next piece."""
    best = None
    for rot, x, after, cleared in placements(board, piece):
        follow = [badness(b, cleared + c) for _, _, b, c in placements(after, upcoming)]
        if not follow:
            continue
        score = min(follow)
        if best is None or score < best[0]:
            best = (score, rot, x)
    return (best[1], best[2]) if best else None


def next_piece(state: dict) -> str:
    """Pieces come from shuffled bags of all seven, reproducible from the state."""
    if not state["queue"]:
        bag = list(PIECES)
        random.Random(state["bags"]).shuffle(bag)
        state["queue"] = bag
        state["bags"] += 1
    return state["queue"].pop(0)


def play(state: dict, count: int) -> dict:
    """Place `count` pieces. Returns what the renderer needs to replay them."""
    board: Board = [list(row) for row in state["board"]]
    segments = [(0, board)]  # (first frame, settled board from that frame on)
    falls = []  # (first frame, piece, rot, x, landing row)
    flashes = []  # (first frame, row)
    frame = 0
    piece = state.get("piece") or next_piece(state)
    for _ in range(count):
        upcoming = next_piece(state)
        choice = choose(board, piece, upcoming)
        if choice is None:
            # Should not happen; start over rather than get stuck.
            board = [["."] * COLS for _ in range(ROWS)]
            segments.append((frame, board))
            choice = choose(board, piece, upcoming)
        rot, x = choice
        land = landing_row(board, piece, rot, x)
        falls.append((frame, piece, rot, x, land))
        frame += land + 1
        board = place(board, piece, rot, x)
        segments.append((frame, board))
        after, full = clear(board)
        if full:
            flashes += [(frame, row) for row in full]
            frame += CLEAR_FRAMES
            board = after
            segments.append((frame, board))
            state["lines"] += len(full)
        state["pieces"] += 1
        piece = upcoming
    state["piece"] = piece
    state["board"] = ["".join(row) for row in board]
    return {"segments": segments, "falls": falls, "flashes": flashes, "frames": frame + END_FRAMES}


def stamp(index: int, total: int) -> str:
    return f"{index / total:.5f}".rstrip("0").rstrip(".") or "0"


def animate(attribute: str, steps: list[tuple[int, str]], total: int, extra: str = "") -> str:
    """Discrete SMIL animation from (frame, value) steps; the first step must be frame 0."""
    return (
        f'<animate{extra} attributeName="{attribute}" calcMode="discrete" '
        f'dur="{total * FRAME_SECONDS:.2f}s" repeatCount="indefinite" '
        f'values="{";".join(value for _, value in steps)}" '
        f'keyTimes="{";".join(stamp(index, total) for index, _ in steps)}"/>'
    )


def square(col: int, row: int, piece: str) -> str:
    return (
        f'<rect class="{piece}" x="{col * CELL + 1}" y="{row * CELL + 1}" '
        f'width="{CELL - 2}" height="{CELL - 2}" rx="3"'
    )


def render(game: dict) -> str:
    total = game["frames"]
    width, height = COLS * CELL, ROWS * CELL
    duration = f"{total * FRAME_SECONDS:.2f}s"
    fade = stamp(FADE_FRAMES, total), stamp(total - FADE_FRAMES, total)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="A game of Tetris playing itself">',
        "<style>"
        + "".join(f".{piece}{{fill:{color}}}" for piece, color in COLORS.items())
        + ".f{fill:#fff}</style>",
        f'<path d="M0 0H{width}V{height}H0Z" fill="#808080" fill-opacity="0.12"/>',
        # Fade the whole board at the loop point so the restart is not a jump cut.
        f'<g><animate attributeName="opacity" dur="{duration}" repeatCount="indefinite" '
        f'values="0;1;1;0" keyTimes="0;{fade[0]};{fade[1]};1"/>',
    ]

    # Settled cells: one rect per (cell, colour) that is ever lit, toggled over time.
    lit: dict[tuple[int, int, str], list[tuple[int, str]]] = {}
    previous: Board = [["."] * COLS for _ in range(ROWS)]
    for start, board in game["segments"]:
        for row in range(ROWS):
            for col in range(COLS):
                before, now = previous[row][col], board[row][col]
                if before == now:
                    continue
                if before != ".":
                    lit[(col, row, before)].append((start, "0"))
                if now != ".":
                    lit.setdefault((col, row, now), []).append((start, "1"))
        previous = board
    for (col, row, piece), steps in sorted(lit.items()):
        merged: dict[int, str] = {0: "0"}
        for index, value in steps:
            merged[index] = value
        steps = sorted(merged.items())
        if len(steps) == 1:
            out.append(square(col, row, piece) + "/>")
        else:
            out.append(
                square(col, row, piece)
                + f' opacity="{steps[0][1]}">{animate("opacity", steps, total)}</rect>'
            )

    # Falling pieces: a group that appears at the top and steps down to its landing row.
    for start, piece, rot, x, land in game["falls"]:
        shown = [(0, "0"), (start, "1"), (start + land + 1, "0")] if start else [
            (0, "1"), (land + 1, "0")
        ]
        moves = [(0, "0 0")] + [(start + step, f"0 {step * CELL}") for step in range(1, land + 1)]
        out.append(
            f'<g opacity="{shown[0][1]}">{animate("opacity", shown, total)}'
            f'<animateTransform attributeName="transform" type="translate" calcMode="discrete" '
            f'dur="{duration}" repeatCount="indefinite" '
            f'values="{";".join(value for _, value in moves)}" '
            f'keyTimes="{";".join(stamp(index, total) for index, _ in moves)}"/>'
            + "".join(square(cx, cy, piece) + "/>" for cx, cy in cells(piece, rot, x, 0))
            + "</g>"
        )

    # Completed rows flash before they disappear.
    for start, row in game["flashes"]:
        steps = [(0, "0"), (start, ".85"), (start + 2, ".35"), (start + 3, ".85"),
                 (start + CLEAR_FRAMES, "0")]
        out.append(
            f'<rect class="f" y="{row * CELL}" width="{width}" height="{CELL}" opacity="0">'
            f'{animate("opacity", steps, total)}</rect>'
        )
    out += ["</g>", "</svg>"]
    return "\n".join(out) + "\n"


def load() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"board": ["." * COLS] * ROWS, "queue": [], "bags": 0, "pieces": 0, "lines": 0}


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else PIECES_PER_RUN
    state = load()
    game = play(state, count)
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    SVG.write_text(render(game), encoding="utf-8")
    replace_block(
        "TETRIS",
        f"One endless game · **{state['pieces']:,}** pieces placed · "
        f"**{state['lines']:,}** lines cleared so far",
    )
    print(f"pieces={state['pieces']} lines={state['lines']} frames={game['frames']}")


if __name__ == "__main__":
    main()
