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
        "    pip install psutil --break-system-packages\n"
        "(or just 'pip install psutil' in a normal Windows Python install)"
    )
    sys.exit(1)

ZWIFT_PROCESS_NAMES = {"zwift.exe", "zwiftlauncher.exe"}
POLL_INTERVAL_SECONDS = 7

WATCHER_SCRIPT = Path(__file__).resolve().parent / "watcher.py"
LOG_FILE = Path(__file__).resolve().parent.parent / "watchdog_runtime.log"


def log(message: str):
    try:
        from datetime import datetime
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


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