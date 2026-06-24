"""
popup.py

Shows the pen-reminder checklist popup.

==================================================================
SAFETY-CRITICAL DESIGN CONSTRAINT — DO NOT MODIFY WITHOUT READING
==================================================================
This popup must NEVER take keyboard or window focus away from Zwift.
If it does, a rider's live keypress (e.g. spacebar for a power-up,
steering input, etc.) could be swallowed by this popup instead of
reaching the game, at the worst possible moment (mid-event).

To guarantee this, the window is given the Win32 extended styles
WS_EX_NOACTIVATE and WS_EX_TOPMOST after creation. This makes it
render on top of everything (including a fullscreen Zwift window)
WITHOUT ever becoming the active/focused window.

Rules enforced by this file, all load-bearing for rider safety:
  - No .focus_force() / .focus_set() / .grab_set() / modal dialogs
  - No keyboard bindings of any kind (mouse-click dismiss only)
  - Auto-close timer is the dependable fallback no matter what else
    happens, so this window can never get stuck on screen
  - Any unexpected error inside this module is caught and logged,
    never allowed to propagate in a way that could leave a stray
    always-on-top window stuck over the game view
==================================================================
"""

import sys
import time
import tkinter as tk
import traceback
from pathlib import Path

try:
    import ctypes
    IS_WINDOWS = sys.platform == "win32"
except ImportError:
    IS_WINDOWS = False

# Win32 constants for the no-steal-focus topmost window trick
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010

NAVY_BG = "#2d3561"
ACCENT_BLUE = "#a0b0e8"
WHITE = "#ffffff"


def _apply_noactivate_topmost(root: tk.Tk):
    """
    Applies WS_EX_NOACTIVATE + WS_EX_TOPMOST via raw Win32 calls.
    This is what prevents the popup from stealing focus from Zwift.
    Safe no-op on non-Windows platforms (dev/testing only; this tool
    targets Windows).
    """
    if not IS_WINDOWS:
        return
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOPMOST
        )
        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        )
    except Exception:
        # If this fails for any reason, we deliberately do NOT crash.
        # Worst case the popup behaves like a normal topmost window;
        # it still must never call focus_force() etc. elsewhere in
        # this file, so the blast radius of this failing is small.
        log_error("Failed to apply NOACTIVATE/TOPMOST styles")


def log_error(message: str):
    """Errors here go to a local log file, never to a crash dialog."""
    try:
        log_path = Path(__file__).resolve().parent.parent / "popup_errors.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
            f.write(traceback.format_exc() + "\n")
    except Exception:
        pass  # If even logging fails, give up silently. Never raise.


def show_popup(checklist: list, auto_close_seconds: int = 10):
    """
    Displays the reminder popup. Blocks until the popup closes
    (either by click or by the auto-close timer). Intended to be
    called from its own short-lived process/thread so it never
    blocks the log-watching loop.
    """
    try:
        root = tk.Tk()
        root.title("Zwift Pen Reminder")
        root.configure(bg=NAVY_BG)
        root.overrideredirect(True)  # borderless
        root.attributes("-topmost", True)

        # Position: top-right corner, clear of typical Zwift HUD elements
        width, height = 340, 260
        screen_w = root.winfo_screenwidth()
        x = screen_w - width - 24
        y = 24
        root.geometry(f"{width}x{height}+{x}+{y}")

        # Header
        tk.Label(
            root, text="Pre-Race Checklist", font=("Segoe UI", 14, "bold"),
            bg=NAVY_BG, fg=WHITE, pady=10
        ).pack(fill="x")

        # Checklist items
        list_frame = tk.Frame(root, bg=NAVY_BG)
        list_frame.pack(fill="both", expand=True, padx=20)
        for item in checklist:
            tk.Label(
                list_frame, text=f"\u2022 {item}", font=("Segoe UI", 11),
                bg=NAVY_BG, fg=ACCENT_BLUE, anchor="w", justify="left"
            ).pack(fill="x", pady=2)

        # Dismiss button + countdown, mouse-only interaction
        bottom_frame = tk.Frame(root, bg=NAVY_BG)
        bottom_frame.pack(fill="x", pady=16, padx=20)

        remaining = {"seconds": auto_close_seconds}

        dismiss_btn = tk.Button(
            bottom_frame,
            text=f"Dismiss ({remaining['seconds']}s)",
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT_BLUE, fg=NAVY_BG,
            relief="flat", padx=12, pady=6,
            command=lambda: root.destroy(),
        )
        dismiss_btn.pack(side="right")

        def tick():
            remaining["seconds"] -= 1
            if remaining["seconds"] <= 0:
                root.destroy()
                return
            try:
                dismiss_btn.config(text=f"Dismiss ({remaining['seconds']}s)")
            except tk.TclError:
                return  # window already gone
            root.after(1000, tick)

        root.after(1000, tick)

        # Apply the safety-critical no-focus-steal styling once the
        # window actually exists on screen.
        root.update_idletasks()
        _apply_noactivate_topmost(root)

        # Belt-and-suspenders: hard fallback destroy in case the tick
        # loop is ever interrupted for any reason. Tkinter's `after`
        # is reliable, but this costs nothing and guarantees the
        # window cannot outlive auto_close_seconds + 1s.
        root.after((auto_close_seconds + 1) * 1000, lambda: _safe_destroy(root))

        root.mainloop()

    except Exception:
        log_error("Unhandled exception in show_popup")
        try:
            root.destroy()
        except Exception:
            pass


def _safe_destroy(root: tk.Tk):
    try:
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    # Manual test: run this file directly to preview the popup.
    show_popup(
        ["Water bottle", "Towel", "Fan on", "Correct frame & wheels for this race"],
        auto_close_seconds=10,
    )