# PHI Focus

<p align="center">
  <img src="tools/mascots.png" alt="PHI Mascot" width="200">
</p>

<p align="center">
  <b>A privacy-first attention companion that protects your focus.</b><br>
  <i>Stay intentional. Your time matters.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows-blue" alt="Platform">
  <img src="https://img.shields.io/badge/Language-Python%203.11+-yellow" alt="Python">
  <img src="https://img.shields.io/badge/Framework-PySide6%20(Qt)-green" alt="Framework">
  <img src="https://img.shields.io/badge/License-MIT-orange" alt="License">
</p>

---

## Table of Contents

1. [Introduction](#introduction)
2. [Tech Stack](#tech-stack)
3. [System Architecture](#system-architecture)
4. [Data Flow](#data-flow)
5. [Database Design](#database-design)
6. [Project Structure](#project-structure)
7. [Installation & Setup](#installation--setup)
8. [Browser Extension](#browser-extension)
9. [Privacy & Security](#privacy--security)
10. [Development Roadmap](#development-roadmap)
11. [Contributing](#contributing)
12. [License](#license)

---

## Introduction

### What is PHI Focus?

PHI Focus is a desktop application that runs quietly in your system tray, monitoring your app and website usage. When it detects you've been spending too much time on distracting content—particularly YouTube Shorts or other configured sites—it gently nudges you with a reminder to help you stay on track.

Named after the Greek letter Φ (Phi), representing the golden ratio and balance, PHI helps you maintain equilibrium between productive work and potentially time-wasting activities.

### Core Principles

| Principle | Description |
|-----------|-------------|
| 🔒 **Privacy First** | No keystrokes, no screenshots, no page content. Only app names, site domains, and time durations. |
| 💾 **Local Only** | Everything stays on your computer. No cloud, no accounts, no telemetry. |
| ⚙️ **Deterministic** | No AI making decisions—just simple, configurable rules you control. |
| 🎯 **Minimal** | Lightweight, unobtrusive, and respectful of system resources. |

### Key Features

- 📊 **Real-Time Monitoring** — Track active desktop applications and website usage via browser extension
- 🎬 **YouTube Shorts Detection** — Identify Shorts playback, count swipe gestures, enforce session/daily limits
- 💬 **Smart Nudge System** — Gentle popup reminders with configurable actions (stop, extend, pause, bypass)
- 📈 **Analytics Dashboard** — Today view, 7-day charts, timelines, top apps and sites breakdown
- ⚙️ **Fully Customizable** — Custom site limits, exclusion lists, adjustable thresholds

---

## Tech Stack

### Technology Overview

```mermaid
graph TB
    subgraph UI["User Interface Layer"]
        QT[PySide6 Qt]
        WIDGETS[Custom Widgets<br/>Panel, Charts, Timeline]
    end
    
    subgraph APP["Application Logic Layer"]
        ENGINE[Engine<br/>Monitor & State Machine]
        BRIDGE[Bridge<br/>HTTP API Server]
    end
    
    subgraph DATA["Data Persistence Layer"]
        STORE[Store<br/>SQLite Database]
        SETTINGS[Settings<br/>Key-Value Store]
    end
    
    subgraph SYS["System Integration Layer"]
        WIN32[Win32 API<br/>ctypes]
        REG[Registry<br/>Autostart]
    end
    
    subgraph EXT["External Components"]
        BROWSER[Browser Extension<br/>TypeScript/JavaScript]
    end
    
    UI --> APP
    APP --> DATA
    DATA --> SYS
    BROWSER -.->|HTTP localhost:47615| BRIDGE
    ENGINE -->|Qt Signals| UI
```

### Component Breakdown

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **UI Framework** | PySide6 (Qt for Python) | 6.6+ | Native cross-platform GUI |
| **Language** | Python | 3.11+ | Application logic |
| **Database** | SQLite | 3.x | Local data storage with WAL |
| **IPC Protocol** | HTTP (JSON) | - | Extension communication |
| **System APIs** | ctypes / Win32 | - | Windows integration |
| **Browser Extension** | TypeScript | - | Chrome/Firefox integration |

### Why These Technologies?

| Choice | Reason |
|--------|--------|
| **PySide6 (Qt)** | Native Windows look, rich animation framework, excellent signal/slot mechanism |
| **SQLite** | Zero-configuration, serverless, single file, WAL mode for concurrency |
| **Local HTTP** | Browser extensions can't access native APIs directly, HTTP is language-agnostic |
| **No AI/ML** | Deterministic rules are predictable, trustworthy, and user-controllable |

---

## System Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph USER_COMPUTER["User's Computer"]
        subgraph DESKTOP_APP["Desktop Application"]
            subgraph UI_LAYER["Presentation Layer"]
                TODAY[Today Page]
                APPS[Apps Page]
                SETTINGS_PG[Settings Page]
                NUDGE[Nudge Popup]
            end
            
            subgraph APP_LAYER["Application Layer"]
                ENGINE[Engine<br/>Monitor Thread]
                BRIDGE_SRV[Bridge Server<br/>HTTP Thread]
            end
            
            subgraph DATA_LAYER["Data Layer"]
                STORE[(Store<br/>SQLite)]
            end
        end
        
        subgraph OS["Windows Operating System"]
            WIN32[Win32 API]
            REGISTRY[Registry]
        end
        
        subgraph BROWSER["Web Browser"]
            EXT[Browser Extension]
            CONTENT[Content Scripts]
            BG[Background Worker]
        end
    end
    
    subgraph FS["File System"]
        DB[(phi.db)]
    end
    
    ENGINE -->|Qt Signals| UI_LAYER
    ENGINE --> STORE
    BRIDGE_SRV --> STORE
    ENGINE --> BRIDGE_SRV
    
    UI_LAYER -->|User Actions| ENGINE
    
    ENGINE -->|GetForegroundWindow| WIN32
    ENGINE -->|GetLastInputInfo| WIN32
    DESKTOP_APP -->|Autostart| REGISTRY
    
    CONTENT --> BG
    BG -->|POST /heartbeat| BRIDGE_SRV
    BRIDGE_SRV -->|Close commands| BG
    
    STORE --> DB
```

### Component Interaction

```mermaid
flowchart LR
    subgraph UI["UI Components"]
        TODAY_P[TodayPage]
        APPS_P[AppsPage]
        SETTINGS_P[SettingsPage]
        NUDGE_P[NudgePopup]
    end
    
    subgraph CORE["Application Core"]
        ENGINE[Engine]
        BRIDGE[Bridge]
        STORE[Store]
        SETTINGS[Settings]
    end
    
    subgraph PERSIST["Persistence"]
        SQLITE[(SQLite)]
        SETTINGS_TBL[(Settings Table)]
    end
    
    TODAY_P <-->|snapshot signal| ENGINE
    APPS_P <-->|query data| STORE
    SETTINGS_P <-->|get/set| SETTINGS
    NUDGE_P <-->|resolve action| ENGINE
    
    ENGINE -->|flush| STORE
    ENGINE <-->|mailbox| BRIDGE
    SETTINGS -->|save| SETTINGS_TBL
    STORE -->|write| SQLITE
```

### Process Thread Model

```mermaid
sequenceDiagram
    participant Main as Main Thread (Qt Event Loop)
    participant Timer as QTimer
    participant Engine as Engine
    participant HTTP as HTTP Thread
    participant Bridge as Bridge Mailbox
    participant SQLite as SQLite
    
    Main->>Timer: Start 1000ms interval
    loop Every Second
        Timer->>Engine: _tick()
        Engine->>Engine: Check foreground window
        Engine->>Engine: Check idle time
        Engine->>Bridge: fresh(9) - get extension data
        Bridge-->>Engine: heartbeat or None
        Engine->>Engine: Determine state
        Engine->>Engine: Record time bucket
        Engine->>Engine: Check limits
        alt Limit Exceeded
            Engine->>Main: nudge.emit()
        end
        Engine->>Main: snapshot.emit()
    end
    
    par HTTP Server
        HTTP->>Bridge: push(heartbeat)
        Bridge->>Bridge: Store with timestamp
        HTTP-->>HTTP: Response with commands
    end
    
    par Periodic Flush
        Engine->>SQLite: flush() every 10s
    end
```

---

## Data Flow

### Monitoring Loop Sequence

```mermaid
sequenceDiagram
    participant E as Engine
    participant W as WinAPI
    participant B as Bridge
    participant S as Store
    participant U as UI
    
    loop Every 1 Second
        E->>W: foreground()
        W-->>E: {exe, pid}
        E->>W: idle_seconds()
        W-->>E: seconds
        E->>B: fresh(9)
        B-->>E: heartbeat or None
        
        alt State = Shorts
            E->>E: _add(hour, "shorts", "youtube", dt)
            E->>E: Check session limit
            alt Limit exceeded
                E->>U: nudge.emit(payload)
            end
        else State = Site
            E->>E: _add(hour, "site", domain, dt)
            E->>E: Check site limit
        else State = App
            E->>E: _add(hour, "app", exe, dt)
        end
        
        E->>E: _add(hour, "total", "*", dt)
        
        alt Every 10 seconds
            E->>S: flush()
            S->>S: Write to SQLite
        end
        
        E->>U: snapshot.emit(state)
    end
```

### Browser Extension Communication

```mermaid
sequenceDiagram
    participant Tab as Browser Tab
    participant CS as Content Script
    participant BG as Background Worker
    participant HTTP as HTTP Bridge
    participant E as Engine
    
    Tab->>CS: Page loaded
    CS->>CS: Detect Shorts, count swipes
    CS->>BG: sendMessage({host, shorts, swipes})
    
    loop Every 4 seconds
        BG->>HTTP: POST /v1/heartbeat
        Note over BG,HTTP: {tabId, host, shorts, swipes,<br/>audible, active, incognito}
        HTTP->>HTTP: Validate X-PHI header
        HTTP->>HTTP: Validate Origin
        HTTP->>E: bridge.push(event)
        HTTP-->>BG: {ok: true, commands: []}
    end
    
    alt User clicks "Stop" on nudge
        E->>E: resolve(payload, "stop")
        E->>HTTP: queue_command({type: "close"})
        BG->>HTTP: POST /v1/heartbeat
        HTTP-->>BG: {ok: true, commands: [{type: "close", match: "shorts"}]}
        BG->>BG: tabs.remove(shortsTabId)
        BG->>Tab: Close tab
    end
```

### Nudge Popup Flow

```mermaid
stateDiagram-v2
    [*] --> Monitoring: App Started
    Monitoring --> Paused: User pauses
    Paused --> Monitoring: User resumes
    
    Monitoring --> Idle: No input > threshold
    Idle --> Monitoring: Input detected
    
    Monitoring --> Shorts: YouTube Shorts detected
    Monitoring --> Site: Watched site detected
    Monitoring --> App: Desktop app in focus
    
    Shorts --> CheckLimit: Time recorded
    Site --> CheckLimit: Time recorded
    
    CheckLimit --> Monitoring: Under limit
    CheckLimit --> NudgeShown: Over limit
    
    NudgeShown --> Stop: User clicks Stop
    NudgeShown --> More: User clicks More
    NudgeShown --> Pause: User clicks Pause
    NudgeShown --> Bypass: User clicks Bypass
    NudgeShown --> Dismiss: User dismisses
    
    Stop --> Monitoring: Tab closed, celebration
    More --> Monitoring: Limits extended
    Pause --> Monitoring: Reminders paused
    Bypass --> Monitoring: No nudges for N minutes
    Dismiss --> Monitoring: Acknowledged
```

### UI Rendering Pipeline

```mermaid
flowchart TD
    A[Engine._tick] --> B[snapshot.emit]
    B --> C[UI receives signal]
    C --> D[update_status]
    D --> E[StatusChip.set_state]
    
    F[QTimer periodic] --> G[refresh]
    G --> H[Store.day_totals]
    H --> I[Update StatCards]
    I --> J[Animate number count]
    I --> K[Animate bar growth]
    
    G --> L[Store.hourly]
    L --> M[Timeline.set_rows]
    M --> N[Render 24-hour grid]
    
    G --> O[Store.by_name]
    O --> P[Create TopRow widgets]
    P --> Q[Fade-in animations]
    
    style A fill:#e1f5ff
    style B fill:#e1f5ff
    style F fill:#fff3e0
    style G fill:#fff3e0
```

---

## Database Design

### Entity Relationship Diagram

```mermaid
erDiagram
    USAGE {
        TEXT day PK "YYYY-MM-DD"
        INTEGER hour PK "0-23"
        TEXT kind PK "total|site|app|shorts|swipes"
        TEXT name PK "*|domain|exe|youtube"
        REAL seconds "Accumulated time"
    }
    
    EVENTS {
        INTEGER id PK "Auto-increment"
        REAL ts "Unix timestamp"
        TEXT day "YYYY-MM-DD"
        TEXT kind "nudge|stop|more|pause|bypass"
        TEXT detail "JSON payload"
    }
    
    SETTINGS {
        TEXT key PK "Setting name"
        TEXT value "JSON encoded value"
    }
    
    USAGE ||--o{ EVENTS : "same day"
```

### Table Specifications

#### USAGE Table

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `day` | TEXT | ISO date (YYYY-MM-DD) | `"2024-01-15"` |
| `hour` | INTEGER | Hour of day (0-23) | `14` |
| `kind` | TEXT | Category of usage | `"site"`, `"shorts"` |
| `name` | TEXT | Specific identifier | `"youtube.com"` |
| `seconds` | REAL | Accumulated time | `1842.5` |

**Primary Key**: `(day, hour, kind, name)`

**Kind Values**:
- `total` / `*` — Total active time
- `site` / domain — Time on specific website
- `app` / exe — Time in desktop application
- `shorts` / `youtube` — YouTube Shorts time
- `swipes` / `shorts` — Swipe count

#### EVENTS Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment ID |
| `ts` | REAL | Unix timestamp |
| `day` | TEXT | ISO date |
| `kind` | TEXT | Event type |
| `detail` | TEXT | JSON payload |

**Event Types**: `nudge`, `stop`, `more`, `pause`, `bypass`, `dismiss`

### Query Patterns

```sql
-- Today's totals by kind
SELECT kind, name, SUM(seconds)
FROM usage
WHERE day = DATE('now')
GROUP BY kind, name
ORDER BY SUM(seconds) DESC;

-- Hourly breakdown for a site
SELECT hour, SUM(seconds)
FROM usage
WHERE day = DATE('now')
  AND kind = 'site'
  AND name = 'youtube.com'
GROUP BY hour;

-- 7-day trend for Shorts
SELECT day, SUM(seconds)
FROM usage
WHERE day >= DATE('now', '-6 days')
  AND kind = 'shorts'
GROUP BY day;

-- Nudge events today
SELECT COUNT(*)
FROM events
WHERE day = DATE('now')
  AND kind = 'nudge';
```

---

## Project Structure

```
PHI_FOCUS/
├── phi/                          # Main Python package
│   ├── __init__.py              # Package metadata
│   ├── __main__.py              # Entry point
│   ├── app.py                   # Application setup
│   ├── engine.py                # Monitoring engine
│   ├── db.py                    # SQLite store
│   ├── server.py                # HTTP bridge
│   ├── winapi.py                # Windows API
│   ├── utils.py                 # Helpers
│   ├── autostart.py             # Registry config
│   └── ui/                      # UI components
│       ├── theme.py             # Design tokens
│       ├── widgets.py           # Custom widgets
│       ├── pages.py             # Main pages
│       └── mascot.py            # Mascot animation
├── extension/                   # Browser extension (TODO)
├── tools/                       # Development tools
├── build/                       # Built executable
├── .venv/                       # Virtual environment
└── requirements.txt             # Dependencies
```

### Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `engine.py` | Monitoring loop, state machine, limit checking, nudge emission |
| `db.py` | SQLite operations, settings persistence, data retention |
| `server.py` | HTTP server, origin validation, command queuing |
| `winapi.py` | Foreground window detection, idle time tracking |
| `utils.py` | Domain normalization, time formatting, name prettification |
| `ui/pages.py` | Today, Apps, Settings pages with data binding |
| `ui/widgets.py` | Custom Qt widgets with animations |
| `ui/theme.py` | Colors, fonts, global styles |

---

## Installation & Setup

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Windows** | 10/11 | Required for Win32 API |
| **Python** | 3.11+ | For async features |
| **pip** | Latest | Package manager |

### Quick Start

```powershell
# Clone the repository
git clone https://github.com/yourusername/PHI_FOCUS.git
cd PHI_FOCUS

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run the application
python -m phi
```

### Run Built Executable

If you have the built executable:

```powershell
.\build\PHI\PHI.exe
```

### Configuration

**Settings Location**: `%APPDATA%\PHI\phi.db`

**Default Settings**:

| Setting | Default | Description |
|---------|---------|-------------|
| `shorts_limit_min` | 20 | Minutes of Shorts before nudge |
| `shorts_daily_min` | 60 | Total daily Shorts budget |
| `extend_min` | 5 | "Give me more" duration |
| `pause_min` | 60 | Pause reminders duration |
| `bypass_min` | 30 | Bypass mode duration |
| `idle_threshold_s` | 120 | Idle detection threshold |
| `track_apps` | true | Track desktop applications |
| `autostart` | true | Start with Windows |
| `retention_days` | 90 | Data retention period |

---

## Browser Extension

### Extension Architecture

```mermaid
graph TB
    subgraph EXT["Browser Extension"]
        MANIFEST[manifest.json<br/>Manifest V3]
        BG[Background<br/>Service Worker]
        CS[Content Scripts]
        POPUP[Popup UI]
    end
    
    subgraph PAGES["Web Pages"]
        YT[YouTube]
        OTHER[Other Sites]
    end
    
    subgraph APP["Desktop App"]
        HTTP[HTTP Server<br/>127.0.0.1:47615]
    end
    
    YT --> CS
    OTHER --> CS
    CS -->|sendMessage| BG
    BG -->|POST /heartbeat| HTTP
    HTTP -->|commands| BG
    BG -->|tabs.remove| YT
    
    MANIFEST --> BG
    MANIFEST --> CS
```

### API Protocol

**POST /v1/heartbeat**

```json
// Request
{
  "tabId": 123,
  "host": "youtube.com",
  "shorts": true,
  "swipes": 47,
  "audible": true,
  "active": true,
  "incognito": false
}

// Response
{
  "ok": true,
  "commands": [
    {"type": "close", "match": "shorts"}
  ]
}
```

**GET /v1/ping**

```json
// Response
{
  "app": "phi",
  "v": 1
}
```

### Security Model

```mermaid
flowchart TD
    A[Incoming Request] --> B{Origin valid?}
    B -->|No| C[403 Forbidden]
    B -->|Yes| D{X-PHI header?}
    D -->|No| C
    D -->|Yes| E{Body size < 4KB?}
    E -->|No| F[413 Too Large]
    E -->|Yes| G{Valid JSON?}
    G -->|No| H[400 Bad Request]
    G -->|Yes| I[Process heartbeat]
    I --> J[Return 200 OK]
    
    style C fill:#ffcccc
    style F fill:#ffcccc
    style H fill:#ffcccc
    style J fill:#ccffcc
```

**Security Layers**:
1. **Network Isolation** — Server binds only to 127.0.0.1
2. **Origin Validation** — Must be chrome-extension:// or moz-extension://
3. **Header Validation** — Must include `X-PHI: 1`
4. **Payload Validation** — Max 4KB, type checking
5. **Data Minimization** — Only hostnames and booleans, never URLs or content

---

## Privacy & Security

### Data Collection Policy

```mermaid
graph LR
    subgraph COLLECTED["✅ Collected"]
        A[App names<br/>code.exe]
        B[Site hostnames<br/>youtube.com]
        C[Time durations<br/>1842 seconds]
        D[Settings]
        E[Interaction events]
    end
    
    subgraph NOT_COLLECTED["❌ NOT Collected"]
        F[Keystrokes]
        G[Screenshots]
        H[Full URLs]
        I[Page content]
        J[Passwords]
        K[Personal info]
    end
```

### What PHI Collects

- Application executable names (e.g., `code.exe`, `chrome.exe`)
- Website hostnames only (e.g., `youtube.com`, not full URLs)
- Time durations in seconds
- User settings and preferences
- Interaction events (nudge shown, action taken)

### What PHI Does NOT Collect

- ❌ Keystrokes or keypresses
- ❌ Mouse movements or clicks
- ❌ Screenshots or screen recordings
- ❌ Full URLs, page paths, or query strings
- ❌ Page titles or content
- ❌ Form data or input values
- ❌ Passwords or credentials
- ❌ Authentication tokens or cookies
- ❌ Any personally identifiable information

### Security Guarantees

| Guarantee | Implementation |
|-----------|---------------|
| **No Network Transmission** | All data stays on your computer |
| **No User Accounts** | No login, passwords, or tokens |
| **No Telemetry** | No usage stats or crash reports |
| **No Third-Party Services** | No analytics, CDNs, or external APIs |
| **Localhost-Only Comm** | Extension only talks to 127.0.0.1 |
| **No Admin Rights** | Installs and runs in user space |

---

## Development Roadmap

### Current Status

```mermaid
pie title Development Progress (70% Complete)
    "Completed" : 70
    "In Progress" : 10
    "Planned" : 20
```

### Completed Features ✅

- [x] Core monitoring engine with QTimer loop
- [x] SQLite database with WAL journaling
- [x] Windows integration (foreground, idle, autostart)
- [x] HTTP bridge server for extension
- [x] Custom UI widget library
- [x] Three main pages (Today, Apps, Settings)
- [x] Theme and design system

### In Progress 🚧

- [ ] Browser extension (Chrome/Firefox)
- [ ] System tray icon
- [ ] Nudge popup window
- [ ] Main entry point refinement

### Planned 📋

**Phase 2**
- Mascot sprite animations
- Sound notifications
- Focus mode (block sites)

**Phase 3**
- Weekly reports
- Data export (JSON/CSV)
- Multiple mascot designs
- Custom themes

**Phase 4**
- macOS support
- Linux support
- Installer distribution

---

## Contributing

We welcome contributions!

### Code Style

- **Python**: Follow PEP 8
- **Type Hints**: Use type annotations
- **Docstrings**: Document all public methods
- **UI Components**: Match existing patterns

### Development Setup

```powershell
git clone https://github.com/yourusername/PHI_FOCUS.git
cd PHI_FOCUS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m phi
```

### Privacy Requirements

**IMPORTANT**: Never add:
- Telemetry or analytics
- Network calls to external servers
- Data collection beyond specified policy
- Any feature that compromises user privacy

---

## License

MIT License

Copyright (c) 2024 PHI Focus Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

<p align="center">
  <b>PHI Focus</b><br>
  <i>Stay intentional. Your time matters.</i>
</p>
