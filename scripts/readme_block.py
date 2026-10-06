"""Replace the text between <!-- NAME:START --> and <!-- NAME:END --> in README.md."""

from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"


def replace_block(name: str, body: str) -> None:
    start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    text = README.read_text(encoding="utf-8")
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    README.write_text(f"{head}{start}\n{body.strip()}\n{end}{tail}", encoding="utf-8")


def fenced(content: str, lang: str = "") -> str:
    """Wrap content in a code fence longer than any backtick run inside it."""
    longest = run = 0
    for ch in content:
        run = run + 1 if ch == "`" else 0
        longest = max(longest, run)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{lang}\n{content.rstrip()}\n{fence}"
