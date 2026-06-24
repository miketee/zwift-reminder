"""
setup_task.py

One-time setup script. Registers the watchdog (watchdog.py) to run
automatically at Windows logon via Task Scheduler, so the user never
has to manually launch anything.

Run this ONCE after installing dependencies:
    python setup_task.py

To remove the scheduled task later:
    python setup_task.py --uninstall

This uses Windows' built-in `schtasks` command-line tool. No admin
elevation or audit-policy changes are required -- this only creates
a per-user scheduled task, which is a normal, low-privilege
operation.
"""

import subprocess
import sys
from pathlib import Path

TASK_NAME = "ZwiftPenReminderWatchdog"


def get_watchdog_path() -> Path:
    return Path(__file__).resolve().parent / "src" / "watchdog.py"


def install():
    python_exe = sys.executable
    watchdog_path = get_watchdog_path()

    if not watchdog_path.exists():
        print(f"ERROR: could not find {watchdog_path}")
        sys.exit(1)

    # pythonw.exe (if available) avoids a console window popping up
    # at every logon. Fall back to the regular interpreter otherwise.
    pythonw = Path(python_exe).parent / "pythonw.exe"
    interpreter = str(pythonw) if pythonw.exists() else python_exe

    command = f'"{interpreter}" "{watchdog_path}"'

    result = subprocess.run(
        [
            "schtasks", "/Create",
            "/TN", TASK_NAME,
            "/TR", command,
            "/SC", "ONLOGON",
            "/RL", "LIMITED",  # explicitly NOT elevated/admin
            "/F",  # overwrite if it already exists
        ],
        capture_output=True, text=True,
    )

    if result.returncode == 0:
        print(f"Success: scheduled task '{TASK_NAME}' created.")
        print("The reminder watchdog will now start automatically the")
        print("next time you log into Windows. To start it immediately")
        print("without logging out, run:")
        print(f'    schtasks /Run /TN "{TASK_NAME}"')
    else:
        print("Failed to create scheduled task.")
        print(result.stdout)
        print(result.stderr)


def uninstall():
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"Scheduled task '{TASK_NAME}' removed.")
    else:
        print("Failed to remove scheduled task (it may not exist).")
        print(result.stdout)
        print(result.stderr)


if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        install()