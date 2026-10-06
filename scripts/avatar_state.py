"""Pick the avatar that matches what Dayan is doing right now.

    avatar_state.py

Looks at the latest public push and the time in Havana, copies the matching
assets/avatar/<state>.svg to assets/avatar.svg and rewrites the STATUS block.
"""

import json
import os
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


def hours_since_last_push(now: datetime) -> float | None:
    """Hours since the latest public push, or None if there is none on record."""
    request = urllib.request.Request(
        f"https://api.github.com/users/{USER}/events/public?per_page=100",
        headers={"Accept": "application/vnd.github+json"},
    )
    if token := os.environ.get("GITHUB_TOKEN"):
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=20) as response:
        events = json.load(response)
    for event in events:
        if event.get("type") == "PushEvent":
            pushed = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
            return (now - pushed).total_seconds() / 3600
    return None


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
    hours = hours_since_last_push(now)
    state = pick_state(hours, now.astimezone(HAVANA).hour)
    shutil.copyfile(ROOT / "assets" / "avatar" / f"{state}.svg", ROOT / "assets" / "avatar.svg")
    replace_block("STATUS", f'<p align="center"><sub>{caption(state, hours, now)}</sub></p>')
    print(state)


if __name__ == "__main__":
    main()
