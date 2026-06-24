\# Zwift Pen Reminder



A lightweight Windows background utility that solves "pen amnesia" —

forgetting to set the correct bike frame/wheels (and grab your water

bottle, towel, fan...) before a Zwift race or event starts.



When you join an event pen with at least 30 seconds until start, a

small reminder popup appears in the corner of your screen with your

checklist. It auto-closes after 10 seconds (or dismiss it early with

a click) and \*\*never steals keyboard focus from Zwift\*\* — see Safety

below.



\## How it works



1\. A small watchdog script runs in the background (started

&#x20;  automatically at Windows login via Task Scheduler) and checks

&#x20;  every few seconds whether Zwift is running.

2\. When Zwift launches, the watchdog starts the reminder watcher.

3\. The watcher tails Zwift's own log file (`Log.txt`) and looks for

&#x20;  the moment you join an event pen. Zwift logs both the join event

&#x20;  and the event's start time in the same place, so no guessing is

&#x20;  needed about when the event actually starts.

4\. If there's at least 30 seconds (configurable) until the event

&#x20;  starts, the checklist popup appears.

5\. When Zwift closes, the watcher stops automatically.



This tool only \*\*reads\*\* Zwift's log file. It never writes to it,

never injects into the Zwift process, and never touches Zwift's

window in any way that could affect gameplay.



\## Installation



\*\*Requirements:\*\* Python 3.9+ on Windows, with the `psutil` package.



```

pip install psutil

```



Then, one-time setup to register the background watchdog:



```

python setup\_task.py

```



This creates a per-user Windows Scheduled Task (no admin rights

needed) that starts the watchdog automatically every time you log

in. To start it immediately without logging out:



```

schtasks /Run /TN "ZwiftPenReminderWatchdog"

```



To remove it later:



```

python setup\_task.py --uninstall

```



\## Configuration



Edit `config.json` to customize:



\- `checklist` — the list of reminder items shown in the popup

\- `reminder\_threshold\_seconds` — minimum time-to-start required to

&#x20; show a reminder (default 30)

\- `popup\_auto\_close\_seconds` — how long the popup stays on screen

&#x20; (default 10)

\- `log\_path` — only set this if Zwift is installed somewhere

&#x20; non-standard; leave blank to auto-detect



\## Safety



This tool is built around one non-negotiable priority: \*\*it must

never cause Zwift to hang, crash, or behave differently\*\* — including

never stealing keyboard or window focus, which could otherwise

swallow a rider's live input (e.g. spacebar for a power-up) at the

worst possible moment.



To guarantee this:



\- The popup window uses the Windows `WS\_EX\_NOACTIVATE` style, so it

&#x20; can render on top of Zwift without ever becoming the focused

&#x20; window.

\- The popup has \*\*no keyboard bindings at all\*\* — it can only be

&#x20; dismissed with a mouse click.

\- The popup always auto-closes on a timer, with a visible countdown,

&#x20; regardless of whether you interact with it.

\- The log watcher only reads Zwift's log file; it never writes to it

&#x20; or touches the Zwift process.

\- The background watchdog only reads the OS process list to detect

&#x20; whether Zwift is running; it doesn't use Windows process-creation

&#x20; auditing (which would require enabling a security policy setting),

&#x20; it simply polls periodically.

\- Any unexpected error anywhere in this tool is caught and logged to

&#x20; a local `.log` file rather than being allowed to propagate or

&#x20; surface as a crash.



\## Known limitations



\- Detection is based on the log line patterns Zwift currently emits

&#x20; (confirmed against a Group Ride join). Zwift doesn't publish or

&#x20; guarantee this format, so a future Zwift client update could

&#x20; change it and silently break detection. If reminders stop

&#x20; appearing, check `watcher\_runtime.log` for clues.

\- If you're already sitting in a pen before Zwift launches the

&#x20; watchdog's startup conditions are met (e.g. the watchdog itself

&#x20; was just started), that specific reminder may be missed — the tool

&#x20; only watches for \*new\* log lines from the moment it starts.

\- This has only been confirmed against a Group Ride pen-join; Race

&#x20; pens are expected to behave the same way but haven't been

&#x20; separately verified.



\## Files



| File | Purpose |

|---|---|

| `setup\_task.py` | One-time installer (registers the Scheduled Task) |

| `config.json` | Your checklist and timing settings |

| `src/watchdog.py` | Polls for Zwift running, starts/stops the watcher |

| `src/watcher.py` | Tails Log.txt, detects pen-join, schedules the popup |

| `src/popup.py` | The reminder popup window itself |

| `src/common.py` | Shared config/path helpers |

