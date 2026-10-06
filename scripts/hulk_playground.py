"""HULK playground: compile and run the program sent in an issue.

    hulk_playground.py run      reads ISSUE_BODY, writes result.json (untrusted job)
    hulk_playground.py publish  reads result.json, updates README.md and comment.md

`run` needs HULK_BIN (the `hulk` binary) and HULK_RUNTIME_DIR (the directory
holding libhulkruntime.a).
"""

import json
import os
import re
import resource
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from readme_block import fenced, replace_block

MAX_SOURCE_CHARS = 4000
MAX_OUTPUT_BYTES = 4000
MAX_OUTPUT_LINES = 40
COMPILE_TIMEOUT_S = 30
RUN_TIMEOUT_S = 3
RUN_MEMORY_BYTES = 512 * 1024 * 1024
RESULT = Path("result.json")
LOGIN = re.compile(r"^[A-Za-z0-9-]{1,39}(\[bot\])?$")


def extract_source(body: str) -> str:
    match = re.search(r"```(?:hulk)?[ \t]*\r?\n(.*?)```", body, re.DOTALL)
    return (match.group(1) if match else body).replace("\r\n", "\n").strip()


def limit_child() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (RUN_TIMEOUT_S, RUN_TIMEOUT_S))
    resource.setrlimit(resource.RLIMIT_AS, (RUN_MEMORY_BYTES, RUN_MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))


def clip(raw: bytes) -> tuple[str, bool]:
    text = raw[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    lines = text.splitlines()
    clipped = len(raw) > MAX_OUTPUT_BYTES or len(lines) > MAX_OUTPUT_LINES
    return "\n".join(lines[:MAX_OUTPUT_LINES]), clipped


def execute(binary: Path, workdir: Path) -> dict:
    """Run the compiled program with CPU, memory, time and output limits."""
    proc = subprocess.Popen(
        [str(binary)],
        cwd=workdir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={},
        preexec_fn=limit_child,
    )
    watchdog = threading.Timer(RUN_TIMEOUT_S + 1, proc.kill)
    watchdog.start()
    raw = b""
    try:
        # Read a bounded amount so a print loop cannot fill memory.
        while len(raw) <= MAX_OUTPUT_BYTES:
            chunk = proc.stdout.read1(4096)
            if not chunk:
                break
            raw += chunk
        flooded = len(raw) > MAX_OUTPUT_BYTES
        if flooded:
            proc.kill()
        code = proc.wait()
    finally:
        watchdog.cancel()
    output, clipped = clip(raw)
    if flooded or code == 0:
        status = "ok"
    elif code in (-signal.SIGKILL, -signal.SIGXCPU):
        status = "timeout"
    else:
        status = "runtime_error"
    return {"status": status, "output": output, "clipped": clipped}


def run() -> None:
    source = extract_source(os.environ.get("ISSUE_BODY", ""))
    result = {"source": source[:MAX_SOURCE_CHARS], "status": "ok", "output": "", "clipped": False}
    if not source:
        result |= {"status": "empty"}
    elif len(source) > MAX_SOURCE_CHARS:
        result |= {"status": "too_long"}
    else:
        hulk = Path(os.environ["HULK_BIN"]).resolve()
        runtime = Path(os.environ["HULK_RUNTIME_DIR"]).resolve()
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "main.hulk").write_text(source + "\n", encoding="utf-8")
            try:
                compiled = subprocess.run(
                    [str(hulk), "main.hulk"],
                    cwd=workdir,
                    capture_output=True,
                    timeout=COMPILE_TIMEOUT_S,
                    env={"PATH": os.environ.get("PATH", ""), "OUT_DIR": str(runtime)},
                )
            except subprocess.TimeoutExpired:
                result |= {"status": "compile_timeout"}
            else:
                binary = workdir / "output"
                if compiled.returncode != 0 or not binary.exists():
                    output, clipped = clip(compiled.stderr)
                    result |= {"status": "compile_error", "output": output, "clipped": clipped}
                else:
                    result |= execute(binary, workdir)
    RESULT.write_text(json.dumps(result), encoding="utf-8")
    print(result["status"])


HEADLINES = {
    "ok": "✅ Compiled and ran",
    "compile_error": "❌ The compiler rejected it",
    "runtime_error": "💥 Compiled, then crashed at runtime",
    "timeout": f"⏱️ Stopped after {RUN_TIMEOUT_S}s",
    "compile_timeout": "⏱️ Compilation took too long",
    "too_long": f"✂️ Programs are limited to {MAX_SOURCE_CHARS} characters",
    "empty": "🤔 No HULK code found in the issue",
}


def publish() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    status = result.get("status")
    if status not in HEADLINES:
        sys.exit(f"unexpected status: {status!r}")
    source = str(result.get("source", ""))[:MAX_SOURCE_CHARS]
    output, _ = clip(str(result.get("output", "")).encode("utf-8"))
    user = os.environ.get("ISSUE_USER", "")
    number = int(os.environ.get("ISSUE_NUMBER", "0"))
    if not LOGIN.match(user):
        sys.exit("unexpected login")

    parts = [f"**{HEADLINES[status]}**"]
    if output:
        label = "Compiler diagnostics" if status == "compile_error" else "Output"
        parts += [f"{label}:", fenced(output, "text")]
    elif status == "ok":
        parts.append("_The program printed nothing._")
    if result.get("clipped"):
        parts.append("_Output was cut short._")
    body = "\n\n".join(parts)

    Path("comment.md").write_text(
        body + "\n\nTry another one from the [playground](https://github.com/DayanCabrera2003#hulk-playground).\n",
        encoding="utf-8",
    )
    if status in ("empty", "too_long"):
        return
    replace_block(
        "HULK",
        "\n\n".join(
            [
                f"Last run: [#{number}](https://github.com/DayanCabrera2003/DayanCabrera2003/issues/{number}) "
                f"by [@{user}](https://github.com/{user})",
                fenced(source, "js"),
                body,
            ]
        ),
    )


if __name__ == "__main__":
    {"run": run, "publish": publish}[sys.argv[1]]()
