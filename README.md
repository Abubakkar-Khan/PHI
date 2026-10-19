# PHI_

A tiny desktop companion that shows where your computer time goes and nudges you out of Shorts doom-scrolling.

## Run

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_phi.pyw        # add --background to start in the tray only
```

PHI lives in the system tray (pause tracking, pause reminders, open, quit). Closing the window hides it. "Start with Windows" is on by default and can be turned off in Settings.

## Browser extension (needed for sites and Shorts)

1. Open `chrome://extensions` or `edge://extensions`, enable Developer mode.
2. Load unpacked, choose the `extension` folder.
3. The Today screen shows `BROWSER LINK ● ONLINE` once connected. The toolbar icon shows `!` if PHI is not running.

Without the extension PHI still tracks desktop apps and treats browsers as plain apps.

## How the parts talk

```
Chrome/Edge extension  --POST /v1/heartbeat every 4s-->  PHI app (127.0.0.1:47615)
   {tabId, host, shorts, swipes, audible, active, incognito}   <-- {commands:[{type:"close", match}]}
PHI app (engine, 1s tick) --> SQLite  %APPDATA%\PHI\phi.db  (usage, events, settings)
PySide6 UI reads SQLite + live engine snapshots
```

- Only a hostname and a few booleans leave the browser. No URLs, titles, keystrokes or screenshots. Incognito tabs are never reported.
- The bridge only accepts requests with `X-PHI: 1` from an extension origin, so web pages cannot spoof it.
- Time counts only while there is keyboard/mouse input in the last 2 minutes (configurable), or audio playing in the active tab. Background tabs and unfocused windows do not count.

## Rules (no AI)

- Session nudge: continuous Shorts time reaches the session limit (default 20 min). A new session starts after 5 minutes away.
- Daily nudge: total Shorts time reaches the daily budget (default 60 min).
- Watched sites: daily limit per site, set in Settings.
- Popup choices: close Shorts (closes the tab), N more minutes, pause reminders, or "it's for something important" (no nudges for 30 min). The X button snoozes like "more minutes".
- Popups never steal keyboard focus and never stack.

## Layout

```
phi/winapi.py   foreground process + idle time (ctypes)
phi/engine.py   rules, recording, nudges
phi/server.py   local bridge
phi/db.py       SQLite store + settings
phi/ui/         theme, mascot, widgets, pages, popup, main window
extension/      MV3 extension
tools/make_icons.py   regenerates extension icons
```

Data lives in `%APPDATA%\PHI` (override with `PHI_DATA_DIR`). Delete everything from Settings > Data.
