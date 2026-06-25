"""
watchdog.py

Runs continuously (started by Task Scheduler at user logon). Polls
every few seconds for Zwift.exe or ZwiftLauncher.exe. When Zwift is
detected running and the reminder watcher isn't already running,
starts it. When Zwift is no longer running, stops the watcher.

Deliberately simple polling, not Windows event-based process
detection -- this avoids requiring the user to enable Windows audit
policy (Event ID 4688) just to install an open-source reminder tool.
That's a security-relevant setting most people shouldn't need to
touch for something like this, and polling every few seconds is
plenty fast for our purposes (the reminder only matters once you're
sitting in a pen with a countdown running, which is minutes after
Zwift launches).

SAFETY NOTE: this script only ever reads the OS process list
(read-only) and starts/stops our own helper scripts. It never
touches the Zwift process itself in any way that could affect it.
"""

import subprocess
import sys
import time
import traceback
from pathlib import Path

try:
    import psutil
except ImportError:
    print(
        "ERROR: the 'psutil' package is required. Install it with:\n"
        "    pip install psutil\n"
    )
    sys.exit(1)

ZWIFT_PROCESS_NAMES = {"zwift.exe", "zwiftlauncher.exe"}
POLL_INTERVAL_SECONDS = 7

WATCHER_SCRIPT = Path(__file__).resolve().parent / "watcher.py"
LOG_FILE = Path(__file__).resolve().parent.parent / "watchdog_runtime.log"

# Rotate log when it exceeds this size. Keeps the oldest half of
# entries so there's always meaningful history without unbounded growth.
LOG_MAX_BYTES = 200 * 1024  # 200 KB


def log(message: str):
    try:
        from datetime import datetime
        _rotate_log_if_needed(LOG_FILE)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


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


def is_zwift_running() -> bool:
    try:
        for proc in psutil.process_iter(["name"]):
            name = (proc.info.get("name") or "").lower()
            if name in ZWIFT_PROCESS_NAMES:
                return True
    except Exception:
        log("Error while checking process list:\n" + traceback.format_exc())
    return False


def main():
    log("Watchdog started.")
    watcher_process = None

    while True:
        try:
            zwift_running = is_zwift_running()

            if zwift_running and (watcher_process is None or watcher_process.poll() is not None):
                log("Zwift detected running. Starting reminder watcher.")
                watcher_process = subprocess.Popen(
                    [sys.executable, str(WATCHER_SCRIPT)],
                    cwd=str(WATCHER_SCRIPT.parent),
                )

            elif not zwift_running and watcher_process is not None and watcher_process.poll() is None:
                log("Zwift no longer running. Stopping reminder watcher.")
                watcher_process.terminate()
                watcher_process = None

        except Exception:
            log("Unhandled exception in watchdog loop:\n" + traceback.format_exc())

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()