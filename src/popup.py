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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_config  # noqa: E402

try:
    import ctypes
    IS_WINDOWS = sys.platform == "win32"
except ImportError:
    IS_WINDOWS = False

# Win32 constants for the no-steal-focus topmost window trick
GWL_EXSTYLE      = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST    = 0x00000008
HWND_TOPMOST     = -1
SWP_NOMOVE       = 0x0002
SWP_NOSIZE       = 0x0001
SWP_NOACTIVATE   = 0x0010

# Colour palette
WHITE       = "#ffffff"
BLACK       = "#111111"
GREY        = "#666666"
ORANGE      = "#f47920"
ZWIFT_BLUE  = "#00b0f0"   # Zwift heading blue


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


def show_popup(checklist: list, auto_close_seconds: int = 10,
               title: str = "Pre-ride Checklist",
               subtitle: str = "Don't forget these!"):
    """
    Displays the reminder popup. Blocks until the popup closes
    (either by click or by the auto-close timer). Intended to be
    called from its own short-lived process/thread so it never
    blocks the log-watching loop.
    """
    try:
        root = tk.Tk()
        root.title("Zwift Pen Reminder")
        root.configure(bg=WHITE)
        root.overrideredirect(True)  # borderless
        root.attributes("-topmost", True)

        # --- Width: 28% of screen, min 360px ---
        # Height is NOT fixed — we let Tkinter measure its own content
        # after packing, then reposition to true centre. This prevents
        # the button being clipped when content is taller than expected.
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        width = max(360, int(screen_w * 0.28))

        # Font sizes scale with popup width
        font_title    = ("Segoe UI", max(14, width // 24), "bold")
        font_subtitle = ("Segoe UI", max(10, width // 36))
        font_item     = ("Segoe UI", max(11, width // 32))
        font_button   = ("Segoe UI", max(10, width // 36), "bold")

        pad_x  = int(width * 0.08)   # horizontal padding inside card
        pad_y  = 14                   # vertical gap between sections

        # --- Thin orange top accent bar ---
        tk.Frame(root, bg=ORANGE, height=4).pack(fill="x", side="top")

        # --- Content area ---
        content = tk.Frame(root, bg=WHITE)
        content.pack(fill="both", expand=True, padx=pad_x, pady=(pad_y, 0))

        # Header — Zwift blue, bold, left-aligned
        tk.Label(
            content,
            text=title,
            font=font_title,
            bg=WHITE, fg=ZWIFT_BLUE,
            anchor="w", justify="left",
        ).pack(fill="x", pady=(0, 4))

        # Subtitle — grey, left-aligned
        tk.Label(
            content,
            text=subtitle,
            font=font_subtitle,
            bg=WHITE, fg=GREY,
            anchor="w", justify="left",
        ).pack(fill="x", pady=(0, pad_y))

        # Checklist items — black, left-aligned, ✓ prefix
        for item in checklist:
            tk.Label(
                content,
                text=f"\u2713  {item}",
                font=font_item,
                bg=WHITE, fg=BLACK,
                anchor="w", justify="left",
            ).pack(fill="x", pady=3)

        # --- Dismiss button — centered, orange bg, white text ---
        bottom_frame = tk.Frame(root, bg=WHITE)
        bottom_frame.pack(fill="x", pady=pad_y, padx=pad_x)

        remaining = {"seconds": auto_close_seconds}

        dismiss_btn = tk.Button(
            bottom_frame,
            text=f"Dismiss ({remaining['seconds']}s)",
            font=font_button,
            bg=ORANGE, fg=WHITE,
            relief="flat",
            padx=int(width * 0.06),
            pady=8,
            cursor="hand2",
            command=lambda: root.destroy(),
        )
        dismiss_btn.pack()

        # --- Let Tkinter measure content, then set width + recentre ---
        # Must happen after all widgets are packed and before mainloop.
        root.update_idletasks()
        actual_h = root.winfo_reqheight()
        x = (screen_w - width) // 2
        y = (screen_h - actual_h) // 2
        root.geometry(f"{width}x{actual_h}+{x}+{y}")

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
    # Reads all settings from config.json (project root).
    # This is also the entry point when spawned as a subprocess by watcher.py.
    try:
        config = load_config()
        checklist = config.get("checklist", [])
        auto_close_seconds = config.get("popup_auto_close_seconds", 10)
        title = config.get("popup_title", "Pre-ride Checklist")
        subtitle = config.get("popup_subtitle", "Don't forget these!")
    except Exception:
        # If config loading fails, fall back to safe defaults so the
        # popup still appears rather than silently dying.
        checklist = ["Water", "Fan", "Towel", "Bike Frame & Wheels!"]
        auto_close_seconds = 10
        title = "Pre-ride Checklist"
        subtitle = "Don't forget these!"

    show_popup(checklist, auto_close_seconds, title, subtitle)