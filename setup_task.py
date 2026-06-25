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
elevation is required -- this creates a per-user scheduled task,
which is a normal, low-privilege operation.
"""

import os
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

    # pythonw.exe avoids a console window flashing at every logon.
    # Fall back to the regular interpreter if pythonw.exe isn't present.
    pythonw = Path(python_exe).parent / "pythonw.exe"
    interpreter = str(pythonw) if pythonw.exists() else python_exe

    command = f'"{interpreter}" "{watchdog_path}"'

    # /RU "" means "run as the currently logged-in user" — required on
    # some Windows UAC configurations to avoid "Access is denied".
    current_user = os.environ.get("USERNAME", "")

    result = subprocess.run(
        [
            "schtasks", "/Create",
            "/TN", TASK_NAME,
            "/TR", command,
            "/SC", "ONLOGON",
            "/RU", current_user,  # explicitly bind to current user
            "/RL", "LIMITED",     # not elevated — normal user privilege
            "/F",                 # overwrite if task already exists
        ],
        capture_output=True, text=True,
    )

    if result.returncode == 0:
        print(f"Success: scheduled task '{TASK_NAME}' created.")
        print()
        print("The watchdog will start automatically next time you log in.")
        print("To start it right now without logging out, run:")
        print(f'    schtasks /Run /TN "{TASK_NAME}"')
    else:
        print("Failed to create scheduled task.")
        print(result.stdout)
        print(result.stderr)
        print()
        print("If you see 'Access is denied', try running this script from")
        print("a command prompt opened as Administrator (right-click →")
        print("'Run as administrator'), then run it once to register the")
        print("task. The task itself will still run as a normal user.")


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