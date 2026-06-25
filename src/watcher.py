"""
watcher.py

Tails Zwift's live Log.txt from the moment this script starts (no
backward scan — by design, per project decision: if you were already
in a pen before this started, that reminder is simply missed, and
the next event will be caught normally).

Detection logic, confirmed against a real Group Ride pen-join on
2026-06-22 (see project notes):

  [HH:MM:SS] Got Notable Moment: JOINED_EVENT
  ...
  [HH:MM:SS] INFO LEVEL: [Group Events] Player received a paddock slot=...
      ... and start time - event start=MM/DD/YYYY HH:MM:SS AM/PM, ...

Both lines appear together at pen-join. We watch for JOINED_EVENT,
then parse the "event start=" timestamp from the paddock-slot line
that accompanies it, to compute exactly when T-30s is.

SAFETY NOTE: This script only ever READS Log.txt. It never writes to
it or touches the Zwift process in any way. Any error here is caught
and logged; it must never crash in a way that could cascade into
unexpected behavior. Worst case if this script dies: no reminder
popup appears. That is an acceptable failure mode. A Zwift hang or
crash is not, and this script has no mechanism to cause one.
"""

import re
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_config, get_zwift_log_path  # noqa: E402

JOINED_EVENT_MARKER = "Got Notable Moment: JOINED_EVENT"
EVENT_START_PATTERN = re.compile(
    r"event start=(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} [AP]M)"
)

LOG_FILE = Path(__file__).resolve().parent.parent / "watcher_runtime.log"

# Rotate log when it exceeds this size. Keeps the oldest half of
# entries so there's always meaningful history without unbounded growth.
LOG_MAX_BYTES = 200 * 1024  # 200 KB


def _rotate_log_if_needed(log_path: Path):
    """
    If the log file exceeds LOG_MAX_BYTES, discard the oldest half of
    its lines and rewrite it. This keeps recent history while bounding
    file size to roughly LOG_MAX_BYTES.
    """
    try:
        if not log_path.exists():
            return
        if log_path.stat().st_size < LOG_MAX_BYTES:
            return
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        # Keep the most recent half
        keep = lines[len(lines) // 2:]
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"[log rotated — older entries trimmed]\n")
            f.writelines(keep)
    except Exception:
        pass  # Never let log rotation crash the main process


def log(message: str):
    try:
        _rotate_log_if_needed(LOG_FILE)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


def get_pythonw() -> str:
    """
    Returns path to pythonw.exe if available (no console window),
    otherwise falls back to the current interpreter.
    """
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    return str(pythonw) if pythonw.exists() else sys.executable


def spawn_popup(checklist: list, auto_close_seconds: int):
    """
    Launches the popup in its own process. Using a separate process
    (not just a thread) keeps Tkinter's mainloop fully isolated from
    the log-tailing loop -- if the popup process has any issue, the
    watcher keeps running unaffected, and vice versa.

    Uses pythonw.exe (no console window) so the popup appears cleanly
    on top without a terminal window interfering with z-order.
    """
    import subprocess
    popup_script = Path(__file__).resolve().parent / "popup.py"
    interpreter = get_pythonw()
    try:
        subprocess.Popen(
            [interpreter, str(popup_script)],
            cwd=str(popup_script.parent),
        )
    except Exception:
        log("Failed to spawn popup process:\n" + traceback.format_exc())


def parse_event_start(line: str):
    match = EVENT_START_PATTERN.search(line)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        return None


def schedule_reminder(event_start: datetime, threshold_seconds: int,
                       checklist: list, auto_close_seconds: int):
    now = datetime.now()
    seconds_until_start = (event_start - now).total_seconds()

    # Zwift recurring events log the original occurrence start time,
    # not the current one -- so the timestamp can be many hours in the
    # past. If the event start is more than 1 hour stale, treat the
    # timestamp as unreliable and show the popup anyway.
    STALE_THRESHOLD_SECONDS = -3600  # 1 hour in the past
    if seconds_until_start < STALE_THRESHOLD_SECONDS:
        log(
            f"Event start timestamp ({event_start}) appears stale "
            f"({seconds_until_start:.0f}s). Likely a recurring event with "
            f"an outdated timestamp -- showing reminder anyway."
        )
        spawn_popup(checklist, auto_close_seconds)
        return

    if seconds_until_start < threshold_seconds:
        log(
            f"Event starts in {seconds_until_start:.0f}s, below the "
            f"{threshold_seconds}s threshold -- skipping reminder per spec."
        )
        return

    log(f"Event start detected: {event_start}. Showing reminder now "
        f"({seconds_until_start:.0f}s before start).")
    spawn_popup(checklist, auto_close_seconds)


def open_log(log_path: Path):
    """Opens log_path and seeks to end. Returns the file handle."""
    f = open(log_path, "r", encoding="utf-8", errors="replace")
    f.seek(0, 2)
    return f


def log_was_rotated(f, log_path: Path) -> bool:
    """
    Returns True if Zwift has recreated Log.txt since we opened it.
    Detection: if the file on disk is smaller than our current read
    position, the file was truncated/replaced.
    """
    try:
        current_size = log_path.stat().st_size
        current_pos = f.tell()
        return current_size < current_pos
    except OSError:
        return False


def tail_log(log_path: Path, config: dict):
    """
    Main tailing loop. Starts at end-of-file (no backward scan) and
    watches for JOINED_EVENT + the accompanying event-start line.

    Handles Zwift's log rotation: Zwift recreates Log.txt on each
    launch. We detect this by comparing the file size on disk against
    our read position -- if the file shrank, it was replaced. We then
    reopen it and seek to the start (since the new file's content is
    all fresh from this Zwift session).
    """
    checklist = config.get("checklist", [])
    threshold_seconds = config.get("reminder_threshold_seconds", 30)
    auto_close_seconds = config.get("popup_auto_close_seconds", 10)

    # How many lines to keep checking, after JOINED_EVENT, for the
    # accompanying "event start=" timestamp before giving up on
    # that particular join. In the confirmed sample this appears
    # on the very next structured-event line, so a generous window
    # costs nothing and protects against minor log-format drift.
    LOOKAHEAD_LINES = 25

    # How often (in read iterations) to check for log rotation.
    # At 0.5s sleep per empty read, this checks roughly every 5s.
    ROTATION_CHECK_EVERY = 10

    log(f"Watching: {log_path}")

    f = open_log(log_path)
    pending_join_lines_left = 0
    idle_ticks = 0

    try:
        while True:
            line = f.readline()
            if not line:
                idle_ticks += 1
                if idle_ticks >= ROTATION_CHECK_EVERY:
                    idle_ticks = 0
                    if log_was_rotated(f, log_path):
                        log("Log rotation detected -- Zwift recreated Log.txt. Reopening.")
                        f.close()
                        # Wait briefly for Zwift to finish writing the new file
                        time.sleep(1.0)
                        f = open_log(log_path)
                        # New file: read from start, not end -- all content
                        # is fresh from this Zwift session.
                        f.seek(0)
                        pending_join_lines_left = 0
                        log("Reopened Log.txt after rotation. Scanning from start.")
                time.sleep(0.5)
                continue

            idle_ticks = 0

            if JOINED_EVENT_MARKER in line:
                log("JOINED_EVENT detected. Watching for event start time...")
                pending_join_lines_left = LOOKAHEAD_LINES
                continue

            if pending_join_lines_left > 0:
                event_start = parse_event_start(line)
                if event_start:
                    pending_join_lines_left = 0
                    schedule_reminder(
                        event_start, threshold_seconds, checklist, auto_close_seconds
                    )
                else:
                    pending_join_lines_left -= 1
                    if pending_join_lines_left == 0:
                        log("Gave up waiting for event-start timestamp "
                            "after JOINED_EVENT (no match within lookahead window).")
    finally:
        f.close()


def main():
    try:
        config = load_config()
        log_path = get_zwift_log_path(config)

        if not log_path.exists():
            log(f"ERROR: Log file not found at {log_path}. Exiting.")
            return

        tail_log(log_path, config)

    except Exception:
        log("Unhandled exception in watcher main():\n" + traceback.format_exc())


if __name__ == "__main__":
    main()