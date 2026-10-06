"""Pick the avatar that matches what Dayan is doing right now.

    avatar_state.py

Looks at the latest public pushes and the time in Havana, copies the matching
assets/avatar/<state>.svg to assets/avatar.svg and rewrites the STATUS and
LATELY blocks.
"""

import json
import os
import re
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from readme_block import replace_block

ROOT = Path(__file__).resolve().parent.parent
USER = "DayanCabrera2003"
HAVANA = ZoneInfo("America/Havana")
VACATION_AFTER_HOURS = 7 * 24
LATELY_COUNT = 4
REPO_NAME = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")


def recent_pushes() -> list[tuple[str, datetime]]:
    """Public pushes, newest first, as (owner/repo, time)."""
    request = urllib.request.Request(
        f"https://api.github.com/users/{USER}/events/public?per_page=100",
        headers={"Accept": "application/vnd.github+json"},
    )
    if token := os.environ.get("GITHUB_TOKEN"):
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=20) as response:
        events = json.load(response)
    return [
        (event["repo"]["name"], datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")))
        for event in events
        if event.get("type") == "PushEvent"
    ]


def lately(pushes: list[tuple[str, datetime]]) -> str:
    """The latest few repositories pushed to, leaving out this profile itself."""
    seen: dict[str, datetime] = {}
    for repo, when in pushes:
        if repo != f"{USER}/{USER}" and REPO_NAME.match(repo):
            seen.setdefault(repo, when)
    if not seen:
        return "_Quiet lately._"
    return "\n".join(
        f"- [`{repo.split('/', 1)[1]}`](https://github.com/{repo}) · pushed {when.astimezone(HAVANA):%b %-d}"
        for repo, when in list(seen.items())[:LATELY_COUNT]
    )


def pick_state(hours: float | None, havana_hour: int) -> str:
    night = havana_hour >= 23 or havana_hour < 7
    if hours is None or hours >= VACATION_AFTER_HOURS:
        return "vacation"
    if hours < 1.5:
        return "shipped"
    if night:
        return "night" if hours < 4 else "asleep"
    if havana_hour < 10 and hours >= 4:
        return "coffee"
    if hours < 24:
        return "coding"
    if hours < 72:
        return "wave"
    return "debugging"


def ago(hours: float) -> str:
    if hours < 1:
        return "minutes ago"
    if hours < 48:
        return f"{round(hours)}h ago"
    return f"{round(hours / 24)} days ago"


def caption(state: str, hours: float | None, now: datetime) -> str:
    clock = now.astimezone(HAVANA).strftime("%H:%M")
    last = f"last push {ago(hours)}" if hours is not None else "no recent pushes"
    return {
        "shipped": f"Just shipped a commit · {last}",
        "coding": f"Coding · {last}",
        "night": f"Late-night session · {clock} in Havana",
        "asleep": f"Asleep · {clock} in Havana",
        "coffee": f"First coffee of the day · {clock} in Havana",
        "wave": f"Around · {last}",
        "debugging": f"Figuring out the next thing · {last}",
        "vacation": f"On vacation · {last}",
    }[state]


def main() -> None:
    now = datetime.now(timezone.utc)
    pushes = recent_pushes()
    hours = (now - pushes[0][1]).total_seconds() / 3600 if pushes else None
    state = pick_state(hours, now.astimezone(HAVANA).hour)
    shutil.copyfile(ROOT / "assets" / "avatar" / f"{state}.svg", ROOT / "assets" / "avatar.svg")
    replace_block("STATUS", f'<p align="center"><sub>{caption(state, hours, now)}</sub></p>')
    replace_block("LATELY", lately(pushes))
    print(state)


if __name__ == "__main__":
    main()
