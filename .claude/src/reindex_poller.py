"""Background polling reindexer for the knowledge base.

Keeps the BM25 search index fresh without interrupting the user. It polls the
four KB dirs' mtime signature and rebuilds the index only once edits have been
**quiet** for a debounce window — so a burst of page creates/edits collapses into
a single rebuild, and nothing blocks while you work.

Design notes:
- **Pure stdlib** for the loop and the change check, so it runs under any Python
  even before project deps are installed. The actual rebuild shells out to
  ``retrieve_cli.py`` through ``sh .claude/src/pyrun`` (the env-agnostic launcher),
  which selects whatever interpreter has the deps (venv / uv / conda / system).
- **Cross-platform**: detaches via ``subprocess`` creation flags (no double-fork),
  and is stopped via a flag file (no Unix-only signals). Liveness is tracked with a
  heartbeat (the state file's mtime), so there's no OS-specific PID probing.

Typically launched by the ``SessionStart`` hook (``--start``) and stopped by the
``SessionEnd`` hook (``--stop``); both are idempotent.

Usage:
    sh .claude/src/pyrun .claude/src/reindex_poller.py --start    # spawn detached poller if none running
    sh .claude/src/pyrun .claude/src/reindex_poller.py --stop     # ask a running poller to exit
    sh .claude/src/pyrun .claude/src/reindex_poller.py --status   # report whether a poller is running
    sh .claude/src/pyrun .claude/src/reindex_poller.py --run      # run the loop in the foreground (internal)

Tunables (env vars):
    REINDEX_POLL_INTERVAL   seconds between checks            (default 60)
    REINDEX_QUIET_PERIOD    seconds of quiet before rebuild   (default 180)
    REINDEX_MAX_IDLE        seconds of inactivity before the
                            poller self-exits                 (default 3600 = 1h)
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # .claude/src/ -> .claude/ -> repo root

# KB dirs to watch per corpus — mirrors retrieve.index.CORPORA (kept in sync by hand;
# the set of dirs is stable). Flat dirs are scanned with glob; nested ones recursively.
# ``exclude_parts`` drops any path with one of those components, mirroring the index's
# library exclusion — so a per-course library/ edit (unindexed) does NOT trigger a no-op
# base reindex. (``explore_library`` is its own component, so it is unaffected.)
# Each corpus has its own index file, so we detect + rebuild them independently.
CORPUS_WATCH = {
    # personal base — sources/notes/papers/concepts + nested course docs (excl. library/)
    "base": {"flat": ("sources", "notes", "papers", "concepts"), "nested": ("course",),
             "exclude_parts": ("library",)},
    # standalone autoexplore corpus — explore_library/{sources,papers,concepts}/
    "explore": {"flat": (), "nested": ("explore_library",), "exclude_parts": ()},
}

STATE_DIR = REPO_ROOT / ".index"
STATE_FILE = STATE_DIR / "poller.json"   # {pid, poll}; its mtime is the heartbeat
STOP_FLAG = STATE_DIR / "poller.stop"
LOG_FILE = STATE_DIR / "poller.log"

POLL_INTERVAL = int(os.environ.get("REINDEX_POLL_INTERVAL", "60"))
QUIET_PERIOD = int(os.environ.get("REINDEX_QUIET_PERIOD", "180"))
MAX_IDLE = int(os.environ.get("REINDEX_MAX_IDLE", str(3600)))


def _log(msg: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as fh:
        fh.write(f"{stamp}  {msg}\n")


def _sig(flat: tuple, nested: tuple, exclude_parts: tuple = ()) -> dict:
    """``{path: mtime_ns}`` over the given dirs' ``*.md`` files (skipping templates).

    Any path with a component in ``exclude_parts`` is skipped (mirrors the index's
    ``library/`` exclusion).
    """
    sig = {}
    exclude = set(exclude_parts)
    scans = [((REPO_ROOT / d).glob("*.md")) for d in flat]
    scans += [((REPO_ROOT / d).rglob("*.md")) for d in nested]
    for paths in scans:
        for path in sorted(paths):
            if path.name.startswith("_"):
                continue
            if exclude and exclude.intersection(path.parts):
                continue
            try:
                sig[str(path)] = path.stat().st_mtime_ns
            except OSError:
                pass  # file vanished mid-scan; next tick will catch up
    return sig


def _signature_for(corpus: str) -> dict:
    w = CORPUS_WATCH[corpus]
    return _sig(w["flat"], w["nested"], w.get("exclude_parts", ()))


def _corpus_signature() -> dict:
    """Combined ``{path: mtime_ns}`` over all watched corpora — for change detection.

    Mirrors ``retrieve.index._corpus_signature`` but stdlib-only (the poller needs
    no third-party imports). Per-corpus signatures drive which index gets rebuilt.
    """
    sig: dict = {}
    for corpus in CORPUS_WATCH:
        sig.update(_signature_for(corpus))
    return sig


def _read_state() -> dict | None:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return None


def is_running() -> bool:
    """A poller is live if its state file exists and the heartbeat is fresh."""
    state = _read_state()
    if not state:
        return False
    poll = int(state.get("poll", POLL_INTERVAL))
    try:
        age = time.time() - STATE_FILE.stat().st_mtime
    except OSError:
        return False
    return age < max(3 * poll, 30)


def _run_reindex(corpus: str = "base") -> bool:
    try:
        # Route through pyrun so the rebuild runs under whatever environment has the
        # deps (venv / uv / conda / system / PKM_PYTHON), not just a repo-local .venv.
        proc = subprocess.run(
            ["sh", ".claude/src/pyrun", ".claude/src/retrieve_cli.py", "--corpus", corpus, "--reindex"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception as e:  # noqa: BLE001
        _log(f"reindex ({corpus}) failed to launch: {e}")
        return False
    if proc.returncode != 0:
        _log(f"reindex ({corpus}) exited {proc.returncode}: {proc.stdout.strip()}")
        return False
    return True


def run_loop() -> None:
    os.chdir(REPO_ROOT)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if STOP_FLAG.exists():
        STOP_FLAG.unlink()

    poll, quiet = POLL_INTERVAL, QUIET_PERIOD

    def heartbeat() -> None:
        STATE_FILE.write_text(json.dumps({"pid": os.getpid(), "poll": poll}))

    heartbeat()
    _log(f"poller started (pid {os.getpid()}, poll {poll}s, quiet {quiet}s)")

    last_sig = _corpus_signature()
    # per-corpus signatures of what's currently indexed (assume current at startup)
    indexed = {c: _signature_for(c) for c in CORPUS_WATCH}
    quiet_since = 0.0
    pending = False
    idle = 0.0

    while True:
        if STOP_FLAG.exists():
            _log("stop requested")
            break
        time.sleep(poll)
        heartbeat()

        cur = _corpus_signature()
        if cur != last_sig:
            last_sig = cur
            quiet_since = time.monotonic()
            pending = True
            idle = 0.0
            _log(f"change detected ({len(cur)} files); debouncing {quiet}s")
        elif pending and (time.monotonic() - quiet_since) >= quiet:
            # Rebuild only the corpora that actually changed since last indexed.
            for corpus in CORPUS_WATCH:
                sig = _signature_for(corpus)
                if sig != indexed[corpus]:
                    _log(f"quiet period elapsed; reindexing {corpus}")
                    if _run_reindex(corpus):
                        indexed[corpus] = sig
                        _log(f"reindex ({corpus}) complete")
            pending = False
        else:
            idle += poll
            if idle >= MAX_IDLE:
                _log("max idle reached; exiting")
                break

    # cleanup
    for f in (STATE_FILE, STOP_FLAG):
        try:
            f.unlink()
        except OSError:
            pass
    _log("poller stopped")


def start() -> None:
    if is_running():
        print("reindex poller already running")
        return
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for f in (STATE_FILE, STOP_FLAG):  # clear any stale runtime files
        try:
            f.unlink()
        except OSError:
            pass

    kwargs: dict = {}
    if os.name == "nt":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        kwargs["creationflags"] = 0x00000008 | 0x00000200
    else:
        kwargs["start_new_session"] = True

    log = open(LOG_FILE, "a")
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--run"],
        cwd=str(REPO_ROOT),
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        **kwargs,
    )
    print("reindex poller started")


def stop() -> None:
    if not is_running():
        print("reindex poller not running")
        # clear any stale files anyway
        for f in (STATE_FILE, STOP_FLAG):
            try:
                f.unlink()
            except OSError:
                pass
        return
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STOP_FLAG.write_text("")
    print("reindex poller stopping")


def status() -> None:
    print("running" if is_running() else "not running")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--start":
        start()
    elif arg == "--run":
        run_loop()
    elif arg == "--stop":
        stop()
    elif arg == "--status":
        status()
    else:
        print(__doc__.splitlines()[0])
        print("usage: sh .claude/src/pyrun .claude/src/reindex_poller.py --start | --stop | --status | --run")
        sys.exit(2)
