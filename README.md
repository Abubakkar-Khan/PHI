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
   - [What is PHI Focus?](#what-is-phi-focus)
   - [Core Principles](#core-principles)
   - [Key Features](#key-features)
2. [Tech Stack](#tech-stack)
   - [Technology Overview](#technology-overview)
   - [Component Breakdown](#component-breakdown)
   - [Why These Technologies?](#why-these-technologies)
3. [System Architecture](#system-architecture)
   - [High-Level Architecture](#high-level-architecture)
   - [Component Diagram](#component-diagram)
   - [Process Overview](#process-overview)
4. [Data Flow](#data-flow)
   - [Monitoring Loop Sequence](#monitoring-loop-sequence)
   - [Browser Extension Communication](#browser-extension-communication)
   - [Nudge Popup Flow](#nudge-popup-flow)
   - [UI Rendering Pipeline](#ui-rendering-pipeline)
5. [Database Design](#database-design)
   - [Entity Relationship Diagram](#entity-relationship-diagram)
   - [Table Specifications](#table-specifications)
   - [Query Patterns](#query-patterns)
6. [Project Structure](#project-structure)
   - [Directory Layout](#directory-layout)
   - [Module Responsibilities](#module-responsibilities)
7. [Installation & Setup](#installation--setup)
   - [Prerequisites](#prerequisites)
   - [Quick Start](#quick-start)
   - [Configuration](#configuration)
8. [Browser Extension](#browser-extension)
   - [Extension Architecture](#extension-architecture)
   - [API Protocol](#api-protocol)
   - [Security Model](#security-model)
9. [Privacy & Security](#privacy--security)
   - [Data Collection Policy](#data-collection-policy)
   - [Local Storage](#local-storage)
   - [Security Guarantees](#security-guarantees)
10. [Development Roadmap](#development-roadmap)
    - [Current Status](#current-status)
    - [Completed Features](#completed-features)
    - [Upcoming Features](#upcoming-features)
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

```
┌─────────────────────────────────────────────────────────────────┐
│                        KEY FEATURES                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📊 REAL-TIME MONITORING                                        │
│  ├── Track active desktop applications                          │
│  ├── Monitor website usage via browser extension                │
│  ├── Detect idle time automatically                             │
│  └── Distinguish active vs passive time (audio detection)       │
│                                                                  │
│  🎬 YOUTUBE SHORTS DETECTION                                    │
│  ├── Identify Shorts playback instantly                         │
│  ├── Count swipe gestures within feeds                          │
│  ├── Session-based and daily limits                             │
│  └── Visual timeline of usage patterns                           │
│                                                                  │
│  💬 SMART NUDGE SYSTEM                                          │
│  ├── Gentle popup reminders when limits exceeded                │
│  ├── Configurable actions (stop, extend, pause, bypass)         │
│  ├── Mascot animations for positive reinforcement               │
│  └── Event logging for self-reflection                          │
│                                                                  │
│  📈 ANALYTICS DASHBOARD                                         │
│  ├── Today view with greeting and real-time status              │
│  ├── 7-day activity charts and timelines                        │
│  ├── Top apps and sites breakdown                               │
│  └── Day-over-day comparisons                                   │
│                                                                  │
│  ⚙️ FULLY CUSTOMIZABLE                                          │
│  ├── Custom site limits with per-domain settings                │
│  ├── Exclusion list for productivity sites                      │
│  ├── Adjustable idle threshold                                  │
│  └── Toggle app tracking on/off                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Technology Overview

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              TECHNOLOGY STACK                                   │
└────────────────────────────────────────────────────────────────────────────────┘

    USER INTERFACE LAYER
    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │    ┌──────────────────┐    ┌──────────────────┐                    │
    │    │   PySide6 (Qt)   │    │  Custom Widgets  │                    │
    │    │                  │    │                  │                    │
    │    │  • QMainWindow   │    │  • Panel         │                    │
    │    │  • QTimer        │    │  • PixelChart    │                    │
    │    │  • Signals/Slots │    │  • Timeline      │                    │
    │    │  • Animations    │    │  • StatCard      │                    │
    │    └──────────────────┘    └──────────────────┘                    │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
    APPLICATION LOGIC LAYER
    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │    ┌──────────────────┐    ┌──────────────────┐                    │
    │    │     Engine       │    │     Bridge       │                    │
    │    │   (Monitor)      │    │    (HTTP API)    │                    │
    │    │                  │    │                  │                    │
    │    │  • State machine │    │  • /heartbeat    │                    │
    │    │  • Limit checks  │    │  • /ping         │                    │
    │    │  • Nudge logic   │    │  • Command queue │                    │
    │    └──────────────────┘    └──────────────────┘                    │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
    DATA PERSISTENCE LAYER
    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │    ┌──────────────────┐    ┌──────────────────┐                    │
    │    │     Store        │    │    Settings      │                    │
    │    │   (SQLite)       │    │   (Key-Value)    │                    │
    │    │                  │    │                  │                    │
    │    │  • Usage buckets │    │  • User config   │                    │
    │    │  • Events log    │    │  • Subscriptions │                    │
    │    │  • WAL journal   │    │  • JSON storage  │                    │
    │    └──────────────────┘    └──────────────────┘                    │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
    SYSTEM INTEGRATION LAYER
    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │    ┌──────────────────┐    ┌──────────────────┐                    │
    │    │    Win32 API     │    │    Registry      │                    │
    │    │   (ctypes)       │    │  (Autostart)     │                    │
    │    │                  │    │                  │                    │
    │    │  • user32.dll    │    │  • HKCU\Run      │                    │
    │    │  • kernel32.dll  │    │  • Start on boot │                    │
    │    └──────────────────┘    └──────────────────┘                    │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘

    EXTERNAL COMPONENTS
    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │    ┌──────────────────────────────────────────────────────────┐    │
    │    │              BROWSER EXTENSION                            │    │
    │    │                                                          │    │
    │    │   TypeScript/JavaScript  →  Chrome/Firefox Extension API │    │
    │    │                                                          │    │
    │    │   • Content Script  → Page detection, Shorts detection   │    │
    │    │   • Background      → Heartbeat to local server          │    │
    │    │   • Tabs API        → Close tab commands                 │    │
    │    └──────────────────────────────────────────────────────────┘    │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
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

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         TECHNOLOGY DECISIONS                                │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WHY PYSIDE6 (QT)?                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ • Native Windows look and feel                                       │   │
│  │ • Rich animation framework for smooth UI                             │   │
│  │ • Excellent signal/slot mechanism for async updates                  │   │
│  │ • No external dependencies beyond Python                             │   │
│  │ • Cross-platform potential for future releases                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  WHY SQLITE?                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ • Zero-configuration, serverless database                            │   │
│  │ • Single file for easy backup and portability                        │   │
│  │ • WAL mode for concurrent reads and writes                           │   │
│  │ • Perfect for single-user desktop applications                       │   │
│  │ • No external database server required                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  WHY LOCAL HTTP FOR EXTENSION?                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ • Browser extensions cannot access native APIs directly              │   │
│  │ • HTTP is language-agnostic and easy to debug                        │   │
│  │ • 127.0.0.1 only = no network exposure                               │   │
│  │ • Simple request/response model fits heartbeat pattern               │   │
│  │ • Extension origin validation prevents spoofing                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  WHY NO AI/ML?                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ • Deterministic rules are more predictable and trustworthy           │   │
│  │ • No training data or model updates required                         │   │
│  │ • User has full control over what triggers a nudge                   │   │
│  │ • Simpler to understand, debug, and modify                           │   │
│  │ • Lower resource usage and faster execution                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## System Architecture

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              PHI FOCUS - SYSTEM ARCHITECTURE                          │
└──────────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                              USER'S COMPUTER                                     │
    │                                                                                  │
    │                                                                                  │
    │   ┌─────────────────────────────────────────────────────────────────────────┐   │
    │   │                         DESKTOP APPLICATION                              │   │
    │   │                                                                          │   │
    │   │   ┌─────────────────────────────────────────────────────────────────┐    │   │
    │   │   │                      PRESENTATION LAYER                          │    │   │
    │   │   │                                                                  │    │   │
    │   │   │   ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────┐    │    │   │
    │   │   │   │   Today   │ │   Apps    │ │ Settings  │ │ Nudge Popup │    │    │   │
    │   │   │   │   Page    │ │   Page    │ │   Page    │ │   (Modal)   │    │    │   │
    │   │   │   └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └──────┬──────┘    │    │   │
    │   │   │         │             │             │              │            │    │   │
    │   │   │         └─────────────┴──────┬──────┴──────────────┘            │    │   │
    │   │   │                                │                                │    │   │
    │   │   │                        ┌───────▼────────┐                       │    │   │
    │   │   │                        │  Theme/Widgets │                       │    │   │
    │   │   │                        └────────────────┘                       │    │   │
    │   │   │                                                                  │    │   │
    │   │   └──────────────────────────────┬───────────────────────────────────┘    │   │
    │   │                                  │                                        │   │
    │   │                                  ▼                                        │   │
    │   │   ┌─────────────────────────────────────────────────────────────────┐    │   │
    │   │   │                      APPLICATION LAYER                           │    │   │
    │   │   │                                                                  │    │   │
    │   │   │   ┌─────────────────┐    ┌─────────────────┐                    │    │   │
    │   │   │   │     ENGINE      │    │     BRIDGE      │                    │    │   │
    │   │   │   │                 │    │                 │                    │    │   │
    │   │   │   │ ┌─────────────┐ │    │ ┌─────────────┐ │                    │    │   │
    │   │   │   │ │   Monitor   │ │    │ │ HTTP Server │ │                    │    │   │
    │   │   │   │ │   Thread    │ │    │ │  (Thread)   │ │                    │    │   │
    │   │   │   │ └─────────────┘ │    │ └─────────────┘ │                    │    │   │
    │   │   │   │                 │    │                 │                    │    │   │
    │   │   │   │ ┌─────────────┐ │    │ ┌─────────────┐ │                    │    │   │
    │   │   │   │ │   QTimer    │ │    │ │ Mailbox     │ │                    │    │   │
    │   │   │   │ │  (1s tick)  │◄├────┤►│ (Thread-safe│ │                    │    │   │
    │   │   │   │ └─────────────┘ │    │ │  queue)     │ │                    │    │   │
    │   │   │   │                 │    │ └─────────────┘ │                    │    │   │
    │   │   │   │ ┌─────────────┐ │    │                 │                    │    │   │
    │   │   │   │ │   Nudge     │ │    │                 │                    │    │   │
    │   │   │   │ │   Emitter   │ │    │                 │                    │    │   │
    │   │   │   │ └─────────────┘ │    │                 │                    │    │   │
    │   │   │   └────────┬────────┘    └────────┬────────┘                    │    │   │
    │   │   │            │                      │                             │    │   │
    │   │   └────────────┼──────────────────────┼─────────────────────────────┘    │   │
    │   │                │                      │                                  │   │
    │   │                ▼                      ▼                                  │   │
    │   │   ┌─────────────────────────────────────────────────────────────────┐    │   │
    │   │   │                        DATA LAYER                                │    │   │
    │   │   │                                                                  │    │   │
    │   │   │   ┌─────────────────────────────────────────────────────────┐   │    │   │
    │   │   │   │                     STORE (SQLite)                       │   │    │   │
    │   │   │   │                                                         │   │    │   │
    │   │   │   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │   │    │   │
    │   │   │   │   │   usage     │  │   events    │  │  settings   │    │   │    │   │
    │   │   │   │   │   table     │  │   table     │  │   table     │    │   │    │   │
    │   │   │   │   └─────────────┘  └─────────────┘  └─────────────┘    │   │    │   │
    │   │   │   │                                                         │   │    │   │
    │   │   │   │              phi.db (WAL mode)                          │   │    │   │
    │   │   │   └─────────────────────────────────────────────────────────┘   │    │   │
    │   │   │                                                                  │    │   │
    │   │   └──────────────────────────────────────────────────────────────────┘    │   │
    │   │                                                                             │   │
    │   └─────────────────────────────────────────────────────────────────────────────┘   │
    │                                                                                      │
    │                                                                                      │
    │   ┌──────────────────────────────────┐    ┌────────────────────────────────────┐   │
    │   │       WINDOWS OPERATING SYSTEM    │    │         WEB BROWSER                │   │
    │   │                                   │    │                                    │   │
    │   │  ┌──────────────────────────────┐ │    │  ┌──────────────────────────────┐ │   │
    │   │  │        Win32 API Layer       │ │    │  │    Browser Extension         │ │   │
    │   │  │                              │ │    │  │                              │ │   │
    │   │  │  • GetForegroundWindow()     │ │    │  │  ┌────────────────────────┐ │ │   │
    │   │  │  • GetLastInputInfo()        │ │    │  │  │    Content Scripts     │ │ │   │
    │   │  │  • GetWindowThreadProcessId()│ │    │  │  │    (per-tab)           │ │ │   │
    │   │  │  • QueryFullProcessImageName│ │    │  │  └────────────────────────┘ │ │   │
    │   │  │                              │ │    │  │                              │ │   │
    │   │  └──────────────────────────────┘ │    │  │  ┌────────────────────────┐ │ │   │
    │   │                                   │    │  │  │    Background Worker   │ │ │   │
    │   │  ┌──────────────────────────────┐ │    │  │  │    (heartbeat loop)    │ │ │   │
    │   │  │      Windows Registry        │ │    │  │  └────────────────────────┘ │ │   │
    │   │  │                              │ │    │  │                              │ │   │
    │   │  │  HKCU\Software\Microsoft\    │ │    │  └──────────────┬───────────────┘ │   │
    │   │  │  Windows\CurrentVersion\Run  │ │    │                 │                 │   │
    │   │  │                              │ │    └─────────────────┼─────────────────┘   │
    │   │  └──────────────────────────────┘ │                      │                     │
    │   │                                   │                      │                     │
    │   └───────────────────────────────────┘                      │                     │
    │                                                                │                     │
    │                                     HTTP (localhost:47615)   │                     │
    │                                                                │                     │
    └────────────────────────────────────────────────────────────────────────────────────┘
                                                                                         │
                                                                                         │
    ┌────────────────────────────────────────────────────────────────────────────────────┐
    │                                    FILE SYSTEM                                      │
    │                                                                                     │
    │   %APPDATA%/PHI/                                                                    │
    │   ├── phi.db           (SQLite database)                                            │
    │   ├── phi.db-wal       (Write-ahead log)                                            │
    │   └── phi.db-shm       (Shared memory)                                              │
    │                                                                                     │
    └────────────────────────────────────────────────────────────────────────────────────┘
```

### Component Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              COMPONENT INTERACTION DIAGRAM                            │
└──────────────────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────────┐
                        │       USER          │
                        └──────────┬──────────┘
                                   │
                                   │ interacts with
                                   ▼
    ┌──────────────────────────────────────────────────────────────────────────────────┐
    │                               UI COMPONENTS                                       │
    │                                                                                   │
    │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
    │  │  TodayPage     │  │   AppsPage     │  │ SettingsPage   │  │  NudgePopup    │ │
    │  │                │  │                │  │                │  │                │ │
    │  │  - greeting    │  │  - charts      │  │  - toggles     │  │  - message     │ │
    │  │  - stat cards  │  │  - timeline    │  │  - steppers    │  │  - actions     │ │
    │  │  - timeline    │  │  - list view   │  │  - inputs      │  │  - mascot      │ │
    │  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘ │
    │          │                   │                   │                   │          │
    │          └─────────┬─────────┴─────────┬─────────┘                   │          │
    │                    │                   │                             │          │
    │                    ▼                   ▼                             │          │
    │          ┌──────────────────────────────────────┐                    │          │
    │          │         Signal/Slot System           │                    │          │
    │          │                                      │                    │          │
    │          │  snapshot ──────────────► UI update  │                    │          │
    │          │  nudge ────────────────► Show popup  │                    │          │
    │          │  celebrated ───────────► Animation   │                    │          │
    │          └──────────────────┬───────────────────┘                    │          │
    │                             │                                        │          │
    └─────────────────────────────┼────────────────────────────────────────┼──────────┘
                                  │                                        │
                                  ▼                                        │
    ┌─────────────────────────────────────────────────────────────────────┼──────────┐
    │                            APPLICATION CORE                          │          │
    │                                                                      │          │
    │  ┌───────────────────────────────────────────────────────────────┐   │          │
    │  │                         ENGINE                                │   │          │
    │  │                                                               │   │          │
    │  │  state: monitoring | paused | shorts | idle | excluded       │   │          │
    │  │                                                               │   │          │
    │  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐        │   │          │
    │  │  │   _tick()   │──►│  _add()     │──►│ flush()     │        │   │          │
    │  │  │  (loop)     │   │  (record)   │   │  (persist)  │        │   │          │
    │  │  └──────┬──────┘   └─────────────┘   └─────────────┘        │   │          │
    │  │         │                                                      │   │          │
    │  │         ▼                                                      │   │          │
    │  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐        │   │          │
    │  │  │ _on_shorts()│──►│_can_nudge() │──►│_emit_nudge()│────────┼───┘          │
    │  │  │             │   │             │   │             │        │              │
    │  │  └─────────────┘   └─────────────┘   └─────────────┘        │              │
    │  │                                                               │              │
    │  │  ┌────────────────────────────────────────────────────────┐  │              │
    │  │  │                    resolve(action)                      │  │              │
    │  │  │                                                        │  │              │
    │  │  │  action: stop | more | pause | bypass | dismiss       │  │              │
    │  │  └────────────────────────────────────────────────────────┘  │              │
    │  └───────────────────────────────────────────────────────────────┘              │
    │                                   │                                              │
    │                                   │ reads/writes                                 │
    │                                   ▼                                              │
    │  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐          │
    │  │     SETTINGS     │    │      STORE       │    │     BRIDGE       │          │
    │  │                  │    │                  │    │                  │          │
    │  │  - get(key)      │    │  - add_usage()   │    │  - push(event)   │          │
    │  │  - set(key,val)  │    │  - day_totals()  │    │  - fresh(max_age)│          │
    │  │  - subscribe()   │    │  - log_event()   │    │  - queue_cmd()   │          │
    │  │                  │    │  - delete_all()  │    │                  │          │
    │  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘          │
    │           │                       │                       │                     │
    └───────────┼───────────────────────┼───────────────────────┼─────────────────────┘
                │                       │                       │
                │                       │                       │
    ┌───────────┼───────────────────────┼───────────────────────┼─────────────────────┐
    │           │                       │                       │                     │
    │  ┌────────▼────────┐    ┌────────▼────────┐    ┌────────▼────────┐            │
    │  │    SETTINGS     │    │     SQLITE      │    │  HTTP SERVER    │            │
    │  │     TABLE       │    │     (phi.db)    │    │  (127.0.0.1)    │            │
    │  │                 │    │                 │    │                 │            │
    │  │  key | value    │    │  usage table    │    │  /v1/heartbeat  │            │
    │  │  (JSON values)  │    │  events table   │    │  /v1/ping       │            │
    │  │                 │    │                 │    │                 │            │
    │  └─────────────────┘    └─────────────────┘    └────────┬────────┘            │
    │                                                         │                      │
    └─────────────────────────────────────────────────────────┼──────────────────────┘
                                                              │
                                                              │ HTTP POST
                                                              │
    ┌─────────────────────────────────────────────────────────┼──────────────────────┐
    │                                                  BROWSER EXTENSION              │
    │                                                          │                      │
    │  ┌──────────────────────────────────────────────────────▼──────────────────┐   │
    │  │                        BACKGROUND SERVICE WORKER                          │   │
    │  │                                                                           │   │
    │  │  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐         │   │
    │  │  │   heartbeat()  │    │  sendCommand() │    │  handleResp()  │         │   │
    │  │  │   (setInterval)│    │                │    │                │         │   │
    │  │  └───────┬────────┘    └────────────────┘    └────────────────┘         │   │
    │  │          │                                                                │   │
    │  │          │ collects from                                                 │   │
    │  │          ▼                                                                │   │
    │  │  ┌────────────────────────────────────────────────────────────────────┐  │   │
    │  │  │                      CONTENT SCRIPTS                               │  │   │
    │  │  │                                                                    │  │   │
    │  │  │  YouTube Shorts:                                                   │  │   │
    │  │  │  - Detect /shorts/ URL pattern                                    │  │   │
    │  │  │  - Count swipes via scroll observer                               │  │   │
    │  │  │  - Check audio state                                               │  │   │
    │  │  │                                                                    │  │   │
    │  │  │  All Sites:                                                        │  │   │
    │  │  │  - Extract hostname                                                │  │   │
    │  │  │  - Check tab active state                                         │  │   │
    │  │  │  - Detect incognito mode                                          │  │   │
    │  │  └────────────────────────────────────────────────────────────────────┘  │   │
    │  │                                                                           │   │
    │  └───────────────────────────────────────────────────────────────────────────┘   │
    │                                                                                   │
    └───────────────────────────────────────────────────────────────────────────────────┘
```

### Process Overview

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              PROCESS THREAD MODEL                                     │
└──────────────────────────────────────────────────────────────────────────────────────┘

    MAIN THREAD (Qt Event Loop)
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                  │
    │   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐          │
    │   │   QApplication  │────►│   QMainWindow   │────►│     Pages       │          │
    │   │   (event loop)  │     │   (container)   │     │   (UI state)    │          │
    │   └─────────────────┘     └─────────────────┘     └─────────────────┘          │
    │                                                                                  │
    │   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐          │
    │   │    QTimer       │     │    Animations   │     │    Signals      │          │
    │   │   (1000ms tick) │     │    (Qt-based)   │     │    (slots)      │          │
    │   └────────┬────────┘     └─────────────────┘     └─────────────────┘          │
    │            │                                                                     │
    │            │ triggers                                                            │
    │            ▼                                                                     │
    │   ┌─────────────────┐                                                           │
    │   │  Engine._tick() │                                                           │
    │   │                 │                                                           │
    │   │  • Check state  │                                                           │
    │   │  • Record usage │                                                           │
    │   │  • Check limits │                                                           │
    │   │  • Emit signals │                                                           │
    │   └─────────────────┘                                                           │
    │                                                                                  │
    └──────────────────────────────────────────────────────────────────────────────────┘

    BACKGROUND THREADS
    ┌──────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                   │
    │   ┌──────────────────────────────────────────────────────────────────────────┐   │
    │   │                     HTTP Server Thread (daemon)                           │   │
    │   │                                                                            │   │
    │   │   ThreadingHTTPServer on 127.0.0.1:47615                                  │   │
    │   │                                                                            │   │
    │   │   Request → parse → Bridge.push() → Response                              │   │
    │   │                                                                            │   │
    │   │   Thread-safe communication via Bridge._lock (threading.Lock)            │   │
    │   │                                                                            │   │
    │   └────────────────────────────────────────────────────────────────────────────┘   │
    │                                                                                   │
    │   ┌──────────────────────────────────────────────────────────────────────────┐   │
    │   │                     Database Writes (synchronous)                         │   │
    │   │                                                                            │   │
    │   │   Store uses threading.RLock for thread-safe SQLite access               │   │
    │   │                                                                            │   │
    │   │   WAL mode allows concurrent reads from UI while engine writes           │   │
    │   │                                                                            │   │
    │   └────────────────────────────────────────────────────────────────────────────┘   │
    │                                                                                   │
    └───────────────────────────────────────────────────────────────────────────────────┘


    INTER-THREAD COMMUNICATION
    ┌──────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                   │
    │   HTTP Thread                          Main Thread                               │
    │   ────────────                         ───────────                               │
    │                                                                                   │
    │   ┌─────────────┐                      ┌─────────────┐                          │
    │   │   Bridge    │───── _latest ───────►│   Engine    │                          │
    │   │   .push()   │      (thread-safe)   │   ._tick()  │                          │
    │   └─────────────┘                      └─────────────┘                          │
    │                                                                                   │
    │   ┌─────────────┐                      ┌─────────────┐                          │
    │   │   Bridge    │◄──── _commands ──────│   Engine    │                          │
    │   │  .pop_cmd() │      (thread-safe)   │  .resolve() │                          │
    │   └─────────────┘                      └─────────────┘                          │
    │                                                                                   │
    │   ┌─────────────┐                      ┌─────────────┐                          │
    │   │   Store     │◄──── add_usage ──────│   Engine    │                          │
    │   │  (SQLite)   │      (RLock)         │   .flush()  │                          │
    │   └─────────────┘                      └─────────────┘                          │
    │                                                                                   │
    └───────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Monitoring Loop Sequence

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                           MONITORING LOOP - SEQUENCE DIAGRAM                          │
└──────────────────────────────────────────────────────────────────────────────────────┘

    Engine          WinAPI          Bridge          Store           UI
      │               │               │               │              │
      │  ┌───────────────────────────────┐            │              │
      │  │ QTimer fires (every 1000ms)   │            │              │
      │  └───────────────────────────────┘            │              │
      │               │               │               │              │
      │   _tick()     │               │               │              │
      │──────────────►│               │               │              │
      │               │               │               │              │
      │               │ foreground()  │               │              │
      │               │──────────────►│               │              │
      │               │               │               │              │
      │               │  GetForegroundWindow()        │              │
      │               │  GetWindowThreadProcessId()   │              │
      │               │  QueryFullProcessImageName()  │              │
      │               │               │               │              │
      │               │◄──────────────│               │              │
      │               │  {exe, pid}   │               │              │
      │               │               │               │              │
      │               │ idle_seconds()│               │              │
      │               │──────────────►│               │              │
      │               │               │               │              │
      │               │  GetLastInputInfo()           │              │
      │               │               │               │              │
      │               │◄──────────────│               │              │
      │               │  seconds      │               │              │
      │               │               │               │              │
      │◄──────────────│               │               │              │
      │  {exe, pid,   │               │               │              │
      │   idle}       │               │               │              │
      │               │               │               │              │
      │               │               │ fresh(9)      │              │
      │               │               │──────────────►│              │
      │               │               │               │              │
      │               │               │◄──────────────│              │
      │               │               │ heartbeat or  │              │
      │               │               │ None          │              │
      │               │               │               │              │
      │  ┌─────────────────────────────────────────────────────┐     │
      │  │ DETERMINE STATE:                                     │     │
      │  │                                                       │     │
      │  │  if tracking_paused → "paused"                       │     │
      │  │  elif fg is None → "idle"                            │     │
      │  │  elif browser + heartbeat + shorts → "shorts"        │     │
      │  │  elif browser + heartbeat + site → "active (site)"   │     │
      │  │  elif app → "active (app)"                           │     │
      │  │  else → "monitoring"                                 │     │
      │  └─────────────────────────────────────────────────────┘     │
      │               │               │               │              │
      │  ┌─────────────────────────────────────────────────────┐     │
      │  │ RECORD TIME:                                          │     │
      │  │                                                       │     │
      │  │  _add(hour, "total", "*", dt)                        │     │
      │  │  if site: _add(hour, "site", domain, dt)             │     │
      │  │  if app: _add(hour, "app", exe, dt)                  │     │
      │  │  if shorts: _add(hour, "shorts", "youtube", dt)      │     │
      │  └─────────────────────────────────────────────────────┘     │
      │               │               │               │              │
      │  ┌─────────────────────────────────────────────────────┐     │
      │  │ CHECK LIMITS:                                         │     │
      │  │                                                       │     │
      │  │  session_limit = cfg["shorts_limit_min"] * 60        │     │
      │  │  daily_limit = cfg["shorts_daily_min"] * 60          │     │
      │  │                                                       │     │
      │  │  if session >= session_limit + extra_session:        │     │
      │  │      → nudge("shorts")                               │     │
      │  │                                                       │     │
      │  │  if today >= daily_limit + extra_daily:              │     │
      │  │      → nudge("daily")                                │     │
      │  │                                                       │     │
      │  │  for site in watched_sites:                          │     │
      │  │      if used >= limit + extra:                       │     │
      │  │          → nudge("site", domain)                     │     │
      │  └─────────────────────────────────────────────────────┘     │
      │               │               │               │              │
      │   flush() (every 10s)         │               │              │
      │───────────────────────────────────────────────►│              │
      │               │               │               │              │
      │               │               │  add_usage()  │              │
      │               │               │               │              │
      │               │               │               │  INSERT/UPDATE
      │               │               │               │  usage table
      │               │               │               │              │
      │   snapshot.emit()             │               │              │
      │───────────────────────────────────────────────────────────────►
      │               │               │               │              │
      │               │               │               │   update()   │
      │               │               │               │              │
      │               │               │               │              │
      ▼               ▼               ▼               ▼              ▼

```

### Browser Extension Communication

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                      BROWSER EXTENSION - COMMUNICATION FLOW                           │
└──────────────────────────────────────────────────────────────────────────────────────┘

    Browser Tab       Content Script    Background Worker    HTTP Bridge      Engine
         │                  │                  │                 │              │
         │                  │                  │                 │              │
         │  User visits     │                  │                 │              │
         │  youtube.com     │                  │                 │              │
         │  /shorts/...     │                  │                 │              │
         │                  │                  │                 │              │
         │                  │  DOM loaded      │                 │              │
         │                  │  Run detection   │                 │              │
         │                  │                  │                 │              │
         │                  │  ┌────────────────────────────┐    │              │
         │                  │  │ DETECT YOUTUBE SHORTS:     │    │              │
         │                  │  │                            │    │              │
         │                  │  │ URL pattern match:         │    │              │
         │                  │  │   /shorts/ → shorts = true │    │              │
         │                  │  │                            │    │              │
         │                  │  │ Swipe counter:             │    │              │
         │                  │  │   observe scroll events    │    │              │
         │                  │  │   count = n                │    │              │
         │                  │  │                            │    │              │
         │                  │  │ Audio check:               │    │              │
         │                  │  │   video.muted ?            │    │              │
         │                  │  │   video.paused ?           │    │              │
         │                  │  └────────────────────────────┘    │              │
         │                  │                  │                 │              │
         │                  │  Extract data:   │                 │              │
         │                  │  - hostname      │                 │              │
         │                  │  - shorts flag   │                 │              │
         │                  │  - swipe count   │                 │              │
         │                  │  - audio state   │                 │              │
         │                  │                  │                 │              │
         │                  │  sendMessage()   │                 │              │
         │                  │─────────────────►│                 │              │
         │                  │  {host, shorts,  │                 │              │
         │                  │   swipes, audio} │                 │              │
         │                  │                  │                 │              │
         │                  │                  │  setInterval()  │              │
         │                  │                  │  (4 seconds)    │              │
         │                  │                  │                 │              │
         │                  │                  │  POST heartbeat │              │
         │                  │                  │────────────────►│              │
         │                  │                  │                 │              │
         │                  │                  │  Request:       │              │
         │                  │                  │  ┌────────────────────────────┐│
         │                  │                  │  │ POST /v1/heartbeat         ││
         │                  │                  │  │ Headers:                   ││
         │                  │                  │  │   X-PHI: 1                 ││
         │                  │                  │  │   Origin: chrome-ext://... ││
         │                  │                  │  │ Body:                      ││
         │                  │                  │  │   {                        ││
         │                  │                  │  │     "tabId": 123,          ││
         │                  │                  │  │     "host": "youtube.com", ││
         │                  │                  │  │     "shorts": true,        ││
         │                  │                  │  │     "swipes": 47,          ││
         │                  │                  │  │     "audible": true,       ││
         │                  │                  │  │     "active": true,        ││
         │                  │                  │  │     "incognito": false     ││
         │                  │                  │  │   }                        ││
         │                  │                  │  └────────────────────────────┘│
         │                  │                  │                 │              │
         │                  │                  │                 │  Validate:   │
         │                  │                  │                 │  - X-PHI == 1
         │                  │                  │                 │  - origin OK│
         │                  │                  │                 │  - size OK  │
         │                  │                  │                 │              │
         │                  │                  │                 │  bridge.push()
         │                  │                  │                 │──────────────►
         │                  │                  │                 │              │
         │                  │                  │                 │  Response:   │
         │                  │                  │◄────────────────│              │
         │                  │                  │  ┌────────────────────────────┐│
         │                  │                  │  │ {                          ││
         │                  │                  │  │   "ok": true,              ││
         │                  │                  │  │   "commands": []           ││
         │                  │                  │  │ }                          ││
         │                  │                  │  └────────────────────────────┘│
         │                  │                  │                 │              │
         │                  │                  │                 │              │
         │                  │                  │                 │              │
         │  ===== USER CLICKS "STOP" ON NUDGE POPUP =====        │              │
         │                  │                  │                 │              │
         │                  │                  │                 │              │
         │                  │                  │                 │  Engine sets │
         │                  │                  │                 │  close cmd   │
         │                  │                  │                 │◄─────────────│
         │                  │                  │                 │              │
         │                  │                  │  Next heartbeat:│              │
         │                  │                  │────────────────►│              │
         │                  │                  │                 │              │
         │                  │                  │  Response:      │              │
         │                  │                  │◄────────────────│              │
         │                  │                  │  ┌────────────────────────────┐│
         │                  │                  │  │ {                          ││
         │                  │                  │  │   "ok": true,              ││
         │                  │                  │  │   "commands": [            ││
         │                  │                  │  │     {                      ││
         │                  │                  │  │       "type": "close",     ││
         │                  │                  │  │       "match": "shorts"    ││
         │                  │                  │  │     }                      ││
         │                  │                  │  │   ]                        ││
         │                  │                  │  │ }                          ││
         │                  │                  │  └────────────────────────────┘│
         │                  │                  │                 │              │
         │                  │                  │  Process command│              │
         │                  │                  │  ┌────────────────────────────┐│
         │                  │                  │  │ Find tabs matching:        ││
         │                  │                  │  │   url: "*youtube.com/shorts*"│
         │                  │                  │  │                            ││
         │                  │                  │  │ chrome.tabs.remove(id)     ││
         │                  │                  │  └────────────────────────────┘│
         │                  │                  │                 │              │
         │  Tab closed ◄────┼──────────────────┤                 │              │
         │                  │                  │                 │              │
         ▼                  ▼                  ▼                 ▼              ▼
```

### Nudge Popup Flow

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              NUDGE POPUP - STATE FLOW                                 │
└──────────────────────────────────────────────────────────────────────────────────────┘

         ENGINE                        NUDGE POPUP                    USER
            │                               │                          │
            │                               │                          │
            │  Limit exceeded               │                          │
            │  _can_nudge() == true         │                          │
            │                               │                          │
            │  _emit_nudge(payload)         │                          │
            │──────────────────────────────►│                          │
            │                               │                          │
            │  payload:                     │                          │
            │  ┌─────────────────────────┐  │                          │
            │  │ kind: "shorts"          │  │                          │
            │  │ seconds: 1200           │  │                          │
            │  │ label: "YouTube Shorts" │  │                          │
            │  │ domain: "youtube.com"   │  │                          │
            │  └─────────────────────────┘  │                          │
            │                               │                          │
            │                               │  Show popup              │
            │                               │  with mascot             │
            │                               │                          │
            │                               │  ┌─────────────────────┐ │
            │                               │  │  ┌───────────────┐  │ │
            │                               │  │  │   MASCOT      │  │ │
            │                               │  │  │   (animated)  │  │ │
            │                               │  │  └───────────────┘  │ │
            │                               │  │                     │ │
            │                               │  │  You've been on     │ │
            │                               │  │  YouTube Shorts     │ │
            │                               │  │  for 20 minutes     │ │
            │                               │  │                     │ │
            │                               │  │  [STOP] [MORE]      │ │
            │                               │  │  [PAUSE] [BYPASS]   │ │
            │                               │  │                     │ │
            │                               │  └─────────────────────┘ │
            │                               │                          │
            │                               │─────────────────────────►│
            │                               │                          │
            │                               │                          │ User clicks
            │                               │                          │
            │                               │◄─────────────────────────┤
            │                               │   action = "stop"        │
            │                               │                          │
            │  resolve(payload, "stop")     │                          │
            │◄──────────────────────────────│                          │
            │                               │                          │
            │  ┌─────────────────────────────────────────────────────┐│
            │  │ RESOLUTION LOGIC:                                    ││
            │  │                                                       ││
            │  │  if action == "stop":                                ││
            │  │      bridge.queue_command({                          ││
            │  │          type: "close",                              ││
            │  │          match: "shorts"                             ││
            │  │      })                                              ││
            │  │      celebrated.emit()  # mascot celebrates         ││
            │  │                                                       ││
            │  │  elif action == "more":                              ││
            │  │      extra_session += extend_min * 60                ││
            │  │      extra_daily += extend_min * 60                  ││
            │  │                                                       ││
            │  │  elif action == "pause":                             ││
            │  │      reminders_paused_until = now + pause_min * 60   ││
            │  │                                                       ││
            │  │  elif action == "bypass":                            ││
            │  │      bypass_until = now + bypass_min * 60            ││
            │  │                                                       ││
            │  │  store.log_event(now, day, action, kind)             ││
            │  └─────────────────────────────────────────────────────┘│
            │                               │                          │
            │  nudge_open = False           │                          │
            │                               │                          │
            │  Close popup                  │                          │
            │──────────────────────────────►│                          │
            │                               │                          │
            │  celebrated.emit()            │                          │
            │  (mascot animation)           │                          │
            │                               │                          │
            ▼                               ▼                          ▼


    ACTION SUMMARY:
    ┌────────────────────────────────────────────────────────────────────────────────────┐
    │  ACTION      │  RESULT                                                           │
    │──────────────┼────────────────────────────────────────────────────────────────────│
    │  STOP        │  Close distracting tab, trigger celebration animation             │
    │  MORE        │  Extend current session and daily limits by extend_min minutes    │
    │  PAUSE       │  Silence all reminders for pause_min minutes                      │
    │  BYPASS      │  Mark as "important work" for bypass_min minutes (no nudges)      │
    │  DISMISS     │  Acknowledge without action, extend limits slightly               │
    └────────────────────────────────────────────────────────────────────────────────────┘
```

### UI Rendering Pipeline

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                            UI RENDERING PIPELINE                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘

    Engine              Store              TodayPage           Widgets
       │                  │                    │                   │
       │                  │                    │                   │
       │  snapshot.emit() │                    │                   │
       │─────────────────────────────────────►│                   │
       │                  │                    │                   │
       │  {status, label,│                    │                   │
       │   mood, link...} │                    │                   │
       │                  │                    │                   │
       │                  │                    │  update_status()  │
       │                  │                    │──────────────────►│
       │                  │                    │                   │
       │                  │                    │  StatusChip       │
       │                  │                    │  .set_state()     │
       │                  │                    │                   │
       │                  │                    │                   │
       │  QTimer (periodic refresh)            │                   │
       │                  │                    │                   │
       │                  │                    │  refresh()        │
       │                  │                    │                   │
       │                  │  flush()           │                   │
       │◄─────────────────│                    │                   │
       │                  │                    │                   │
       │                  │  day_totals()      │                   │
       │                  │◄───────────────────│                   │
       │                  │                    │                   │
       │                  │  {("total","*"):   │                   │
       │                  │   5421.0,          │                   │
       │                  │   ("shorts","yt"): │                   │
       │                  │   1842.0, ...}     │                   │
       │                  │───────────────────►│                   │
       │                  │                    │                   │
       │                  │                    │  Update stats:    │
       │                  │                    │                   │
       │                  │                    │  c_active.set_data()
       │                  │                    │──────────────────►│
       │                  │                    │                   │
       │                  │                    │                   │ Animate
       │                  │                    │                   │ number
       │                  │                    │                   │ count
       │                  │                    │                   │
       │                  │                    │  c_shorts.set_data()
       │                  │                    │──────────────────►│
       │                  │                    │                   │
       │                  │                    │                   │ Animate
       │                  │                    │                   │ bars
       │                  │                    │                   │
       │                  │  hourly()          │                   │
       │                  │◄───────────────────│                   │
       │                  │                    │                   │
       │                  │  [0, 0, 0, ...,    │                   │
       │                  │   1800, 2400, ...] │                   │
       │                  │───────────────────►│                   │
       │                  │                    │                   │
       │                  │                    │  timeline.set_rows()
       │                  │                    │──────────────────►│
       │                  │                    │                   │
       │                  │                    │                   │ Render
       │                  │                    │                   │ 24-hour
       │                  │                    │                   │ grid
       │                  │                    │                   │
       │                  │  by_name()         │                   │
       │                  │◄───────────────────│                   │
       │                  │                    │                   │
       │                  │  [("site",         │                   │
       │                  │    "youtube.com",  │                   │
       │                  │    1842.0),        │                   │
       │                  │   ("app",          │                   │
       │                  │    "code.exe",     │                   │
       │                  │    1200.0), ...]   │                   │
       │                  │───────────────────►│                   │
       │                  │                    │                   │
       │                  │                    │  _fill_top()      │
       │                  │                    │──────────────────►│
       │                  │                    │                   │
       │                  │                    │                   │ Create
       │                  │                    │                   │ TopRow
       │                  │                    │                   │ widgets
       │                  │                    │                   │
       │                  │                    │                   │ Fade-in
       │                  │                    │                   │ animation
       │                  │                    │                   │
       ▼                  ▼                    ▼                   ▼


    WIDGET ANIMATION TIMELINE:
    ┌────────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                     │
    │  StatCard:                                                                          │
    │  ┌─────────────────────────────────────────────────────────────────────────────┐   │
    │  │  0ms        200ms       400ms       600ms       700ms                        │   │
    │  │   │           │           │           │           │                          │   │
    │  │   │ count: 0 ─┼───────────┼───────────┼───► 1842  │                          │   │
    │  │   │           │           │           │           │                          │   │
    │  │   │ bars: 0 ──┼───────────┼───────────┼───────────┼──► full height           │   │
    │  └─────────────────────────────────────────────────────────────────────────────┘   │
    │                                                                                     │
    │  TopRow:                                                                            │
    │  ┌─────────────────────────────────────────────────────────────────────────────┐   │
    │  │  delay=0ms        delay=70ms      delay=140ms     delay=210ms               │   │
    │  │     │                  │               │               │                     │   │
    │  │     │ opacity: 0 ──────┼───────────────┼───────────────┼──► 1.0             │   │
    │  │     │     │            │               │               │                     │   │
    │  │   Row 1   │          Row 2           Row 3           Row 4                   │   │
    │  └─────────────────────────────────────────────────────────────────────────────┘   │
    │                                                                                     │
    │  Timeline:                                                                          │
    │  ┌─────────────────────────────────────────────────────────────────────────────┐   │
    │  │  Reveal animation: columns fade in left-to-right over 900ms                 │   │
    │  │                                                                               │   │
    │  │  hour:  0   1   2   3   4   5   6   ...  22  23                              │   │
    │  │         │   │   │   │   │   │   │   │      │   │                             │   │
    │  │         ▼   ▼   ▼   ▼   ▼   ▼   ▼   ▼      ▼   ▼                             │   │
    │  │       [████████████████████████████████████████]  ← reveal wave              │   │
    │  └─────────────────────────────────────────────────────────────────────────────┘   │
    │                                                                                     │
    └────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Database Design

### Entity Relationship Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                         ENTITY RELATIONSHIP DIAGRAM                                   │
└──────────────────────────────────────────────────────────────────────────────────────┘


                                    ┌─────────────────────────┐
                                    │       SETTINGS          │
                                    │     (Key-Value Store)   │
                                    ├─────────────────────────┤
                                    │                         │
                                    │  PK  key      TEXT      │
                                    │      value   TEXT       │
                                    │      (JSON encoded)     │
                                    │                         │
                                    └─────────────────────────┘


    ┌──────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                    │
    │                                                                                    │
    │                              USAGE TABLE                                           │
    │                                                                                    │
    │        Stores time buckets aggregated by day, hour, kind, and name                │
    │                                                                                    │
    │   ┌────────────────────────────────────────────────────────────────────────────┐  │
    │   │                                                                            │  │
    │   │   ┌─────────────────────────────────────────────────────────────────────┐  │  │
    │   │   │                          USAGE                                       │  │  │
    │   │   ├─────────────────────────────────────────────────────────────────────┤  │  │
    │   │   │                                                                     │  │  │
    │   │   │   PK  day        TEXT        (YYYY-MM-DD format)                   │  │  │
    │   │   │   PK  hour       INTEGER     (0-23)                                 │  │  │
    │   │   │   PK  kind       TEXT        (total | site | app | shorts | swipes)│  │  │
    │   │   │   PK  name       TEXT        (* | domain | exe | youtube | shorts) │  │  │
    │   │   │       seconds    REAL        (accumulated time in seconds)         │  │  │
    │   │   │                                                                     │  │  │
    │   │   │   PRIMARY KEY (day, hour, kind, name)                              │  │  │
    │   │   │                                                                     │  │  │
    │   │   └─────────────────────────────────────────────────────────────────────┘  │  │
    │   │                                                                            │  │
    │   │   KIND VALUES:                                                             │  │
    │   │   ┌─────────────────────────────────────────────────────────────────────┐  │  │
    │   │   │  kind      │  name values        │  description                    │  │  │
    │   │   ├────────────┼─────────────────────┼─────────────────────────────────┤  │  │
    │   │   │  total     │  "*"                │  Total active time              │  │  │
    │   │   │  site      │  "youtube.com"      │  Time on specific website       │  │  │
    │   │   │  app       │  "code.exe"         │  Time in desktop application    │  │  │
    │   │   │  shorts    │  "youtube"          │  YouTube Shorts time            │  │  │
    │   │   │  swipes    │  "shorts"           │  Swipe count (stored as float)  │  │  │
    │   │   └─────────────────────────────────────────────────────────────────────┘  │  │
    │   │                                                                            │  │
    │   └────────────────────────────────────────────────────────────────────────────┘  │
    │                                                                                    │
    └────────────────────────────────────────────────────────────────────────────────────┘


    ┌──────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                    │
    │                                                                                    │
    │                              EVENTS TABLE                                          │
    │                                                                                    │
    │        Stores user interaction events (nudges shown, actions taken)               │
    │                                                                                    │
    │   ┌────────────────────────────────────────────────────────────────────────────┐  │
    │   │                                                                            │  │
    │   │   ┌─────────────────────────────────────────────────────────────────────┐  │  │
    │   │   │                          EVENTS                                       │  │  │
    │   │   ├─────────────────────────────────────────────────────────────────────┤  │  │
    │   │   │                                                                     │  │  │
    │   │   │   PK  id        INTEGER     AUTOINCREMENT                          │  │  │
    │   │   │       ts        REAL        (Unix timestamp with microseconds)      │  │  │
    │   │   │       day       TEXT        (YYYY-MM-DD)                            │  │  │
    │   │   │       kind      TEXT        (nudge | stop | more | pause | bypass)  │  │  │
    │   │   │       detail    TEXT        (Optional JSON payload)                 │  │  │
    │   │   │                                                                     │  │  │
    │   │   │   INDEX: idx_events_day (day, kind)                                │  │  │
    │   │   │                                                                     │  │  │
    │   │   └─────────────────────────────────────────────────────────────────────┘  │  │
    │   │                                                                            │  │
    │   │   KIND VALUES:                                                             │  │
    │   │   ┌─────────────────────────────────────────────────────────────────────┐  │  │
    │   │   │  kind      │  description                                         │  │  │
    │   │   ├────────────┼────────────────────────────────────────────────────────┤  │  │
    │   │   │  nudge     │  Popup was shown to user                             │  │  │
    │   │   │  stop      │  User clicked "Stop" (tab closed)                    │  │  │
    │   │   │  more      │  User clicked "Give me more"                         │  │  │
    │   │   │  pause     │  User clicked "Pause reminders"                      │  │  │
    │   │   │  bypass    │  User clicked "It's for something important"         │  │  │
    │   │   │  dismiss   │  User dismissed the popup without action             │  │  │
    │   │   └─────────────────────────────────────────────────────────────────────┘  │  │
    │   │                                                                            │  │
    │   └────────────────────────────────────────────────────────────────────────────┘  │
    │                                                                                    │
    └────────────────────────────────────────────────────────────────────────────────────┘


    RELATIONSHIPS:
    ┌────────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                     │
    │   USAGE.day ──────────────► EVENTS.day  (temporal relationship, not FK)           │
    │                                                                                     │
    │   No foreign keys are used because:                                                │
    │     • Data is append-only (no updates/deletes across tables)                       │
    │     • Queries are simple aggregations                                              │
    │     • SQLite WAL mode handles concurrency                                          │
    │                                                                                     │
    └────────────────────────────────────────────────────────────────────────────────────┘
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

**Sample Data**:
```
┌────────────┬──────┬─────────┬──────────────┬─────────┐
│    day     │ hour │  kind   │     name     │ seconds │
├────────────┼──────┼─────────┼──────────────┼─────────┤
│ 2024-01-15 │  14  │ total   │ *            │  3421.0 │
│ 2024-01-15 │  14  │ site    │ youtube.com  │  1842.0 │
│ 2024-01-15 │  14  │ shorts  │ youtube      │  1200.0 │
│ 2024-01-15 │  14  │ app     │ code.exe     │   842.0 │
│ 2024-01-15 │  14  │ swipes  │ shorts       │    47.0 │
└────────────┴──────┴─────────┴──────────────┴─────────┘
```

#### EVENTS Table

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `id` | INTEGER | Auto-increment ID | `1`, `2`, `3` |
| `ts` | REAL | Unix timestamp | `1705324800.123` |
| `day` | TEXT | ISO date | `"2024-01-15"` |
| `kind` | TEXT | Event type | `"nudge"`, `"stop"` |
| `detail` | TEXT | JSON payload (optional) | `{"domain": "youtube.com"}` |

**Sample Data**:
```
┌────┬───────────────┬────────────┬─────────┬──────────────────────────┐
│ id │      ts       │    day     │  kind   │         detail           │
├────┼───────────────┼────────────┼─────────┼──────────────────────────┤
│ 1  │ 1705328400.0  │ 2024-01-15 │ nudge   │ "shorts"                 │
│ 2  │ 1705328432.5  │ 2024-01-15 │ stop    │ "shorts"                 │
│ 3  │ 1705332000.0  │ 2024-01-15 │ nudge   │ "site"                   │
│ 4  │ 1705332021.3  │ 2024-01-15 │ more    │ "instagram.com"          │
└────┴───────────────┴────────────┴─────────┴──────────────────────────┘
```

#### SETTINGS Table

| Column | Type | Description |
|--------|------|-------------|
| `key` | TEXT | Setting name (primary key) |
| `value` | TEXT | JSON-encoded value |

**Default Settings Schema**:
```json
{
  "name": "",
  "reminders": true,
  "shorts_limit_min": 20,
  "shorts_daily_min": 60,
  "extend_min": 5,
  "pause_min": 60,
  "bypass_min": 30,
  "idle_threshold_s": 120,
  "track_apps": true,
  "autostart": true,
  "retention_days": 90,
  "watched_sites": [
    {"domain": "instagram.com", "limit": 15, "enabled": true},
    {"domain": "reddit.com", "limit": 15, "enabled": true},
    {"domain": "tiktok.com", "limit": 15, "enabled": false}
  ],
  "excluded_sites": []
}
```

### Query Patterns

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              COMMON QUERY PATTERNS                                    │
└──────────────────────────────────────────────────────────────────────────────────────┘

    TODAY'S TOTALS BY KIND
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  SELECT kind, name, SUM(seconds) as total                                      │
    │  FROM usage                                                                     │
    │  WHERE day = DATE('now')                                                        │
    │  GROUP BY kind, name                                                            │
    │  ORDER BY total DESC;                                                           │
    │                                                                                 │
    │  Result: [("site", "youtube.com", 1842.0),                                     │
    │           ("app", "code.exe", 1200.0),                                         │
    │           ("shorts", "youtube", 800.0), ...]                                   │
    └────────────────────────────────────────────────────────────────────────────────┘

    HOURLY BREAKDOWN FOR A SITE
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  SELECT hour, SUM(seconds) as total                                            │
    │  FROM usage                                                                     │
    │  WHERE day = DATE('now')                                                        │
    │    AND kind = 'site'                                                            │
    │    AND name = 'youtube.com'                                                     │
    │  GROUP BY hour                                                                  │
    │  ORDER BY hour;                                                                 │
    │                                                                                 │
    │  Result: [(9, 120.0), (10, 842.0), (14, 1842.0), ...]                          │
    └────────────────────────────────────────────────────────────────────────────────┘

    7-DAY TREND FOR SHORTS
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  SELECT day, SUM(seconds) as total                                             │
    │  FROM usage                                                                     │
    │  WHERE day >= DATE('now', '-6 days')                                            │
    │    AND kind = 'shorts'                                                          │
    │  GROUP BY day                                                                   │
    │  ORDER BY day;                                                                  │
    │                                                                                 │
    │  Result: [("2024-01-09", 1200.0),                                              │
    │           ("2024-01-10", 1800.0),                                              │
    │           ...,                                                                  │
    │           ("2024-01-15", 1842.0)]                                              │
    └────────────────────────────────────────────────────────────────────────────────┘

    NUDGE EVENTS TODAY
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  SELECT COUNT(*) as count                                                      │
    │  FROM events                                                                    │
    │  WHERE day = DATE('now')                                                        │
    │    AND kind = 'nudge';                                                          │
    │                                                                                 │
    │  Result: [(3,)]                                                                │
    └────────────────────────────────────────────────────────────────────────────────┘

    TOP 5 APPS THIS WEEK
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  SELECT name, SUM(seconds) as total                                            │
    │  FROM usage                                                                     │
    │  WHERE day >= DATE('now', '-6 days')                                            │
    │    AND kind = 'app'                                                             │
    │  GROUP BY name                                                                  │
    │  ORDER BY total DESC                                                            │
    │  LIMIT 5;                                                                       │
    │                                                                                 │
    │  Result: [("code.exe", 18420.0),                                               │
    │           ("chrome.exe", 12000.0),                                             │
    │           ("spotify.exe", 8400.0), ...]                                        │
    └────────────────────────────────────────────────────────────────────────────────┘

    PURGE OLD DATA
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  DELETE FROM usage WHERE day < DATE('now', '-90 days');                        │
    │  DELETE FROM events WHERE day < DATE('now', '-90 days');                       │
    │  VACUUM;                                                                        │
    └────────────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

### Directory Layout

```
PHI_FOCUS/
│
├── phi/                              # Main Python package
│   │
│   ├── __init__.py                   # Package metadata, version, port constant
│   │
│   ├── engine.py                     # Core monitoring loop and state machine
│   │   └── class Engine              # QTimer-driven monitor with limit checking
│   │
│   ├── db.py                         # SQLite database and settings management
│   │   ├── class Store               # Database operations (usage, events)
│   │   └── class Settings            # Key-value settings with subscriptions
│   │
│   ├── server.py                     # HTTP bridge for browser extension
│   │   ├── class Bridge              # Thread-safe mailbox for events
│   │   └── class BridgeServer        # ThreadingHTTPServer wrapper
│   │
│   ├── winapi.py                     # Windows API bindings via ctypes
│   │   ├── foreground()              # Get active window exe and pid
│   │   └── idle_seconds()            # Get seconds since last input
│   │
│   ├── utils.py                      # Formatting and normalization helpers
│   │   ├── normalize_host()          # Extract domain from hostname
│   │   ├── host_matches()            # Check if host matches domain pattern
│   │   ├── fmt_dur()                 # Format seconds as "1h 23m"
│   │   └── pretty_site/app()         # Human-readable names
│   │
│   ├── autostart.py                  # Windows registry autostart
│   │   └── set_enabled()             # Add/remove from HKCU\Run
│   │
│   └── ui/                           # PySide6 UI components
│       │
│       ├── __init__.py
│       │
│       ├── theme.py                  # Design tokens (colors, fonts)
│       │   ├── BG, SURFACE, INK...   # Color constants
│       │   ├── sans(), mono()        # Font factories
│       │   └── GLOBAL_QSS            # Global stylesheet
│       │
│       ├── widgets.py                # Custom Qt widgets
│       │   ├── Panel                 # Rounded card with hover effect
│       │   ├── PillButton            # Rounded action button
│       │   ├── Toggle                # Animated toggle switch
│       │   ├── Stepper               # Increment/decrement control
│       │   ├── Segmented             # Tab-like selector
│       │   ├── StatusChip            # Pulsing status indicator
│       │   ├── StatCard              # Statistic with chart
│       │   ├── Timeline              # 24-hour dot matrix
│       │   ├── PixelChart            # Bar chart with pixels
│       │   └── UsageRow              # List item with progress
│       │
│       ├── pages.py                  # Main application pages
│       │   ├── TodayPage             # Dashboard with greeting, stats, timeline
│       │   ├── AppsPage              # Analytics with charts and breakdown
│       │   └── SettingsPage          # Configuration controls
│       │
│       └── mascot.py                 # Animated mascot widget
│           └── Mascot                # QPainter-based sprite animation
│
├── extension/                        # Browser extension (to be implemented)
│   │
│   ├── manifest.json                 # Extension manifest (v3)
│   │
│   ├── background.js                 # Service worker
│   │   ├── heartbeat()               # POST to localhost every 4s
│   │   └── handleCommands()          # Process close directives
│   │
│   ├── content.js                    # Content script (injected into pages)
│   │   ├── detectShorts()            # YouTube Shorts detection
│   │   ├── countSwipes()             # Scroll-based swipe counter
│   │   └── checkAudio()              # Audio state detection
│   │
│   ├── popup/                        # Extension popup UI (optional)
│   │   ├── popup.html
│   │   └── popup.js
│   │
│   └── icons/                        # Extension icons
│       ├── icon16.png
│       ├── icon48.png
│       └── icon128.png
│
├── tools/                            # Development utilities
│   │
│   ├── mascots.png                   # Mascot spritesheet
│   │
│   └── preview_mascot.py             # Preview mascot animations
│       └── Standalone window for testing sprites
│
├── .venv/                            # Python virtual environment
│
├── requirements.txt                  # Python dependencies
│   └── PySide6>=6.6.0
│
├── run_phi.pyw                       # Entry point (to be created)
│   └── Silent startup (pythonw) with tray icon
│
└── README.md                         # This file
```

### Module Responsibilities

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              MODULE RESPONSIBILITY MATRIX                             │
└──────────────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┬───────────────────────────────────────────────────────────────────┐
    │   MODULE     │                         RESPONSIBILITY                            │
    ├──────────────┼───────────────────────────────────────────────────────────────────┤
    │              │                                                                   │
    │  engine.py   │  • QTimer-driven monitoring loop (1 second interval)             │
    │              │  • State management: monitoring, paused, shorts, idle            │
    │              │  • Time bucket aggregation (by day, hour, kind, name)            │
    │              │  • Limit checking (session, daily, per-site)                     │
    │              │  • Nudge emission when limits exceeded                            │
    │              │  • Action resolution (stop, more, pause, bypass, dismiss)        │
    │              │                                                                   │
    ├──────────────┼───────────────────────────────────────────────────────────────────┤
    │              │                                                                   │
    │   db.py      │  • SQLite connection management with WAL mode                    │
    │              │  • Usage table operations (add_usage, day_totals, hourly)        │
    │              │  • Event logging (log_event, event_count, event_series)          │
    │              │  • Settings persistence (load_settings, save_setting)            │
    │              │  • Data retention (purge_older_than, delete_all)                 │
    │              │  • Thread-safe access via RLock                                  │
    │              │                                                                   │
    ├──────────────┼───────────────────────────────────────────────────────────────────┤
    │              │                                                                   │
    │  server.py   │  • HTTP server on 127.0.0.1:47615                                │
    │              │  • POST /v1/heartbeat endpoint (extension → app)                 │
    │              │  • GET /v1/ping endpoint (health check)                           │
    │              │  • Origin validation (chrome-extension://, moz-extension://)      │
    │              │  • X-PHI header check (prevent spoofing)                          │
    │              │  • Thread-safe bridge mailbox (push, fresh, queue_command)       │
    │              │                                                                   │
    ├──────────────┼───────────────────────────────────────────────────────────────────┤
    │              │                                                                   │
    │  winapi.py   │  • GetForegroundWindow() → active window handle                  │
    │              │  • GetWindowThreadProcessId() → pid from handle                  │
    │              │  • QueryFullProcessImageNameW() → exe path from pid              │
    │              │  • GetLastInputInfo() → idle time in seconds                     │
    │              │  • Process pid caching for performance                            │
    │              │  • Windows-only (returns None on other platforms)                │
    │              │                                                                   │
    ├──────────────┼───────────────────────────────────────────────────────────────────┤
    │              │                                                                   │
    │  utils.py    │  • normalize_host() → extract registrable domain                │
    │              │  • host_matches() → wildcard domain matching                      │
    │              │  • clean_domain() → extract domain from URL                      │
    │              │  • fmt_dur() → format seconds as "1h 23m" or "45m"              │
    │              │  • fmt_clock() → format as "01:23:45"                            │
    │              │  • pretty_site() → human-readable site name                      │
    │              │  • pretty_app() → human-readable app name                        │
    │              │                                                                   │
    ├──────────────┼───────────────────────────────────────────────────────────────────┤
    │              │                                                                   │
    │ autostart.py │  • set_enabled(True/False) → manage HKCU\Run registry key       │
    │              │  • Uses pythonw.exe for silent startup                           │
    │              │  • Passes --background flag to run minimized                     │
    │              │  • Windows-only (no-op on other platforms)                       │
    │              │                                                                   │
    ├──────────────┼───────────────────────────────────────────────────────────────────┤
    │              │                                                                   │
    │  ui/theme.py │  • Color tokens: BG, SURFACE, PAPER, INK, GRAY, RED, LINE, SOFT │
    │              │  • Font families: SANS (Geist, Inter, Segoe UI),                 │
    │              │    MONO (Geist Mono, JetBrains Mono, Cascadia)                   │
    │              │  • Font factories: sans(px, weight), mono(px, weight, spacing)  │
    │              │  • Color utilities: qc(color, alpha), mix(a, b, t)              │
    │              │  • GLOBAL_QSS: default styles for tooltips, scrollbars, menus   │
    │              │                                                                   │
    ├──────────────┼───────────────────────────────────────────────────────────────────┤
    │              │                                                                   │
    │ ui/widgets.py│  • Panel: rounded card with hover darkening                      │
    │              │  • PillButton: primary/secondary button with icon               │
    │              │  • Toggle: animated switch with signal dot                       │
    │              │  • Stepper: increment/decrement with min/max/step               │
    │              │  • Segmented: multi-option tab selector                          │
    │              │  • StatusChip: pulsing dot + label (on/alert/off)               │
    │              │  • StatCard: stat with 7-day pixel bars                          │
    │              │  • Timeline: 24-hour dot-matrix grid                             │
    │              │  • PixelChart: column chart with stacked squares                │
    │              │  • UsageRow: list item with progress dots                        │
    │              │                                                                   │
    ├──────────────┼───────────────────────────────────────────────────────────────────┤
    │              │                                                                   │
    │  ui/pages.py │  • TodayPage: greeting, status chip, stat cards, timeline       │
    │              │  • AppsPage: range/kind selectors, chart, scrollable list        │
    │              │  • SettingsPage: toggles, steppers, site management, data controls│
    │              │  • refresh() methods: update from store/engine                   │
    │              │  • Animation triggers on data changes                            │
    │              │                                                                   │
    └──────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## Installation & Setup

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Windows** | 10/11 | Required for Win32 API calls |
| **Python** | 3.11+ | For async features and type hints |
| **pip** | Latest | Python package manager |

### Quick Start

```powershell
# 1. Clone the repository
git clone https://github.com/yourusername/PHI_FOCUS.git
cd PHI_FOCUS

# 2. Create virtual environment
python -m venv .venv

# 3. Activate (PowerShell)
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install PySide6

# 5. Run the application
python -m phi
```

### Configuration

**Settings Location**: `%APPDATA%\PHI\phi.db`

**Default Settings**:

```
┌──────────────────────────┬─────────┬────────────────────────────────────────┐
│         Setting          │ Default │              Description               │
├──────────────────────────┼─────────┼────────────────────────────────────────┤
│ shorts_limit_min         │    20   │ Minutes of Shorts before nudge        │
│ shorts_daily_min         │    60   │ Total daily Shorts budget             │
│ extend_min               │     5   │ "Give me more" duration (minutes)     │
│ pause_min                │    60   │ Pause reminders duration (minutes)    │
│ bypass_min               │    30   │ Bypass mode duration (minutes)        │
│ idle_threshold_s         │   120   │ Idle detection threshold (seconds)    │
│ track_apps               │  true   │ Track non-browser applications        │
│ autostart                │  true   │ Start with Windows                    │
│ retention_days           │    90   │ Data retention period (days)          │
└──────────────────────────┴─────────┴────────────────────────────────────────┘
```

**Environment Variables**:

| Variable | Purpose |
|----------|---------|
| `PHI_DATA_DIR` | Override data directory location |
| `PHI_NO_AUTOSTART` | Disable autostart registration |

---

## Browser Extension

### Extension Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                          BROWSER EXTENSION ARCHITECTURE                               │
└──────────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                              MANIFEST V3                                          │
    │                                                                                   │
    │  {                                                                                │
    │    "manifest_version": 3,                                                         │
    │    "name": "PHI Focus Bridge",                                                   │
    │    "version": "1.0.0",                                                            │
    │    "permissions": [                                                               │
    │      "tabs",                                                                      │
    │      "activeTab",                                                                 │
    │      "scripting"                                                                  │
    │    ],                                                                             │
    │    "host_permissions": [                                                          │
    │      "<all_urls>"                                                                 │
    │    ],                                                                             │
    │    "background": {                                                                │
    │      "service_worker": "background.js"                                           │
    │    },                                                                             │
    │    "content_scripts": [{                                                          │
    │      "matches": ["<all_urls>"],                                                  │
    │      "js": ["content.js"],                                                        │
    │      "run_at": "document_idle"                                                    │
    │    }]                                                                             │
    │  }                                                                                │
    │                                                                                   │
    └───────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                           CONTENT SCRIPT                                          │
    │                           (Runs in each tab)                                      │
    │                                                                                   │
    │  DETECTION LOGIC:                                                                 │
    │  ┌────────────────────────────────────────────────────────────────────────────┐  │
    │  │  YouTube Shorts:                                                            │  │
    │  │    URL pattern: /shorts/ in pathname                                        │  │
    │  │    Swipe counter: IntersectionObserver on video elements                   │  │
    │  │    Audio check: document.querySelector('video').muted/paused               │  │
    │  │                                                                              │  │
    │  │  General Sites:                                                              │  │
    │  │    hostname: window.location.hostname                                       │  │
    │  │    active: document.hasFocus() && !document.hidden                          │  │
    │  │    incognito: N/A (detected in background)                                  │  │
    │  └────────────────────────────────────────────────────────────────────────────┘  │
    │                                                                                   │
    │  COMMUNICATION:                                                                   │
    │  ┌────────────────────────────────────────────────────────────────────────────┐  │
    │  │  // Send data to background worker                                          │  │
    │  │  chrome.runtime.sendMessage({                                               │  │
    │  │    type: 'tab-update',                                                      │  │
    │  │    hostname: window.location.hostname,                                      │  │
    │  │    shorts: isShortsPage(),                                                  │  │
    │  │    swipes: getSwipeCount(),                                                 │  │
    │  │    audible: isAudible()                                                     │  │
    │  │  });                                                                         │  │
    │  └────────────────────────────────────────────────────────────────────────────┘  │
    │                                                                                   │
    └───────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                         BACKGROUND SERVICE WORKER                                 │
    │                                                                                   │
    │  HEARTBEAT LOOP (every 4 seconds):                                               │
    │  ┌────────────────────────────────────────────────────────────────────────────┐  │
    │  │  async function sendHeartbeat() {                                           │  │
    │  │    const tab = await getActiveTab();                                        │  │
    │  │    if (!tab) return;                                                        │  │
    │  │                                                                              │  │
    │  │    const data = tabData.get(tab.id) || {};                                  │  │
    │  │                                                                              │  │
    │  │    const response = await fetch('http://127.0.0.1:47615/v1/heartbeat', {  │  │
    │  │      method: 'POST',                                                         │  │
    │  │      headers: {                                                              │  │
    │  │        'Content-Type': 'application/json',                                  │  │
    │  │        'X-PHI': '1'                                                          │  │
    │  │      },                                                                       │  │
    │  │      body: JSON.stringify({                                                  │  │
    │  │        tabId: tab.id,                                                        │  │
    │  │        host: data.hostname,                                                  │  │
    │  │        shorts: data.shorts || false,                                        │  │
    │  │        swipes: data.swipes || 0,                                             │  │
    │  │        audible: data.audible || false,                                      │  │
    │  │        active: tab.active,                                                   │  │
    │  │        incognito: tab.incognito                                              │  │
    │  │      })                                                                       │  │
    │  │    });                                                                        │  │
    │  │                                                                              │  │
    │  │    const result = await response.json();                                    │  │
    │  │    processCommands(result.commands);                                        │  │
    │  │  }                                                                           │  │
    │  └────────────────────────────────────────────────────────────────────────────┘  │
    │                                                                                   │
    │  COMMAND PROCESSING:                                                              │
    │  ┌────────────────────────────────────────────────────────────────────────────┐  │
    │  │  function processCommands(commands) {                                       │  │
    │  │    for (const cmd of commands) {                                            │  │
    │  │      if (cmd.type === 'close') {                                            │  │
    │  │        if (cmd.match === 'shorts') {                                        │  │
    │  │          chrome.tabs.query(                                                 │  │
    │  │            {url: '*://*.youtube.com/shorts/*'},                             │  │
    │  │            (tabs) => tabs.forEach(t => chrome.tabs.remove(t.id))           │  │
    │  │          );                                                                   │  │
    │  │        } else {                                                               │  │
    │  │          // Close by domain match                                           │  │
    │  │        }                                                                      │  │
    │  │      }                                                                        │  │
    │  │    }                                                                          │  │
    │  │  }                                                                           │  │
    │  └────────────────────────────────────────────────────────────────────────────┘  │
    │                                                                                   │
    └───────────────────────────────────────────────────────────────────────────────────┘
```

### API Protocol

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              HTTP API SPECIFICATION                                   │
└──────────────────────────────────────────────────────────────────────────────────────┘

    POST /v1/heartbeat
    ─────────────────────────────────────────────────────────────────────────────────
    
    DESCRIPTION:
      Receive usage data from browser extension, return any pending commands.
    
    REQUEST:
      Headers:
        Content-Type: application/json
        X-PHI: 1
        Origin: chrome-extension://<extension-id>
      
      Body:
        {
          "tabId": number,        // Chrome tab ID
          "host": string,         // e.g., "youtube.com"
          "shorts": boolean,      // Is this a Shorts page?
          "swipes": number,       // Swipe counter
          "audible": boolean,     // Is audio playing?
          "active": boolean,      // Is tab in foreground?
          "incognito": boolean    // Is this an incognito tab?
        }
    
    RESPONSE:
      Status: 200 OK
      Body:
        {
          "ok": true,
          "commands": [
            {"type": "close", "match": "shorts"},
            {"type": "close", "match": "instagram.com"}
          ]
        }
    
    ERROR RESPONSES:
      400 Bad Request   → Invalid JSON or missing fields
      403 Forbidden     → Invalid X-PHI header or Origin
      413 Payload Too Large → Body exceeds 4KB

    ─────────────────────────────────────────────────────────────────────────────────

    GET /v1/ping
    ─────────────────────────────────────────────────────────────────────────────────
    
    DESCRIPTION:
      Health check endpoint.
    
    REQUEST:
      No body required.
    
    RESPONSE:
      Status: 200 OK
      Body:
        {
          "app": "phi",
          "v": 1
        }

    ─────────────────────────────────────────────────────────────────────────────────

    OPTIONS /v1/heartbeat
    ─────────────────────────────────────────────────────────────────────────────────
    
    DESCRIPTION:
      CORS preflight request.
    
    RESPONSE:
      Status: 204 No Content
      Headers:
        Access-Control-Allow-Origin: chrome-extension://...
        Access-Control-Allow-Headers: content-type, x-phi
        Access-Control-Allow-Methods: POST, GET
```

### Security Model

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              SECURITY MODEL                                           │
└──────────────────────────────────────────────────────────────────────────────────────┘

    LAYER 1: NETWORK ISOLATION
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │   Server binds ONLY to 127.0.0.1 (localhost)                                   │
    │                                                                                 │
    │   ✗ Not accessible from network                                                │
    │   ✗ Not accessible from other machines                                         │
    │   ✓ Only local processes can connect                                           │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘

    LAYER 2: ORIGIN VALIDATION
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │   Request must include valid Origin header:                                    │
    │                                                                                 │
    │   ✓ chrome-extension://<extension-id>                                          │
    │   ✓ moz-extension://<extension-id>                                             │
    │                                                                                 │
    │   ✗ http://malicious-site.com                                                  │
    │   ✗ https://evil.com                                                           │
    │   ✗ Missing Origin header                                                      │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘

    LAYER 3: HEADER VALIDATION
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │   Request must include:                                                        │
    │                                                                                 │
    │   X-PHI: 1                                                                      │
    │                                                                                 │
    │   This prevents:                                                                │
    │   ✗ CSRF attacks from regular web pages                                        │
    │   ✗ Accidental requests from other extensions                                 │
    │   ✗ Automated scanners                                                         │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘

    LAYER 4: PAYLOAD VALIDATION
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │   • Max body size: 4KB                                                         │
    │   • Required fields validated                                                  │
    │   • Types checked (string, number, boolean)                                    │
    │   • Strings truncated to safe lengths                                          │
    │                                                                                 │
    │   hostname max: 253 characters (DNS limit)                                     │
    │   tabId: must be valid integer                                                 │
    │   swipes: must be non-negative integer                                         │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘

    LAYER 5: DATA MINIMIZATION
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │   Extension NEVER sends:                                                       │
    │   ✗ Full URLs                                                                  │
    │   ✗ Page titles                                                                │
    │   ✗ Page content                                                               │
    │   ✗ Form data                                                                  │
    │   ✗ Cookies or tokens                                                          │
    │   ✗ User credentials                                                           │
    │                                                                                 │
    │   Extension ONLY sends:                                                        │
    │   ✓ Hostname (e.g., "youtube.com")                                            │
    │   ✓ Booleans (shorts, audible, active, incognito)                             │
    │   ✓ Swipe count (integer)                                                      │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘
```

---

## Privacy & Security

### Data Collection Policy

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA COLLECTION POLICY                                   │
└──────────────────────────────────────────────────────────────────────────────────────┘

    ✅ WHAT PHI COLLECTS
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │   • Application executable names                                                │
    │     Example: "code.exe", "chrome.exe"                                          │
    │                                                                                 │
    │   • Website hostnames                                                           │
    │     Example: "youtube.com", "github.com"                                       │
    │     NOT: full URLs, page paths, query strings                                  │
    │                                                                                 │
    │   • Time durations (seconds)                                                    │
    │     Example: 1842.5 seconds on YouTube                                         │
    │                                                                                 │
    │   • User settings and preferences                                               │
    │     Example: shorts_limit_min = 20                                             │
    │                                                                                 │
    │   • Interaction events                                                          │
    │     Example: nudge shown at 14:32, user clicked "stop"                         │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘

    ❌ WHAT PHI DOES NOT COLLECT
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │   ✗ Keystrokes or keypresses                                                   │
    │   ✗ Mouse movements, clicks, or scroll positions                               │
    │   ✗ Screenshots or screen recordings                                           │
    │   ✗ Full URLs or page content                                                  │
    │   ✗ Page titles                                                                │
    │   ✗ Form data or input values                                                  │
    │   ✗ Passwords or credentials                                                   │
    │   ✗ Authentication tokens or cookies                                           │
    │   ✗ Browser history                                                            │
    │   ✗ File system contents                                                       │
    │   ✗ Any personally identifiable information (PII)                              │
    │   ✗ Email addresses, names, phone numbers                                      │
    │   ✗ Location data                                                              │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘
```

### Local Storage

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              LOCAL STORAGE                                            │
└──────────────────────────────────────────────────────────────────────────────────────┘

    FILE LOCATION
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │   Windows: %APPDATA%\PHI\phi.db                                                 │
    │   Override: Set PHI_DATA_DIR environment variable                               │
    │                                                                                 │
    │   Typical path:                                                                 │
    │   C:\Users\<username>\AppData\Roaming\PHI\phi.db                               │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘

    FILE CONTENTS
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │   phi.db         → SQLite database (usage, events, settings)                   │
    │   phi.db-wal     → Write-ahead log (for crash recovery)                        │
    │   phi.db-shm     → Shared memory index (for concurrent access)                 │
    │                                                                                 │
    │   Total size: Typically < 10MB after months of use                             │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘

    DATA RETENTION
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │   Default: 90 days                                                              │
    │   Configurable: 7 to 730 days                                                   │
    │   Auto-purge: Runs on startup                                                   │
    │                                                                                 │
    │   Purge is irreversible (unless you backed up phi.db)                          │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘

    BACKUP
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │   To backup: Copy phi.db to a safe location                                    │
    │   To restore: Replace phi.db with your backup                                  │
    │                                                                                 │
    │   Settings → "Open folder" button shows the directory                          │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘
```

### Security Guarantees

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              SECURITY GUARANTEES                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘

    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │  ✓ NO NETWORK TRANSMISSION                                                     │
    │    All data stays on your computer. No data is sent to any server.            │
    │                                                                                 │
    │  ✓ NO USER ACCOUNTS                                                            │
    │    No login, no passwords, no authentication tokens.                           │
    │                                                                                 │
    │  ✓ NO TELEMETRY                                                                │
    │    No usage statistics, no crash reports, no "phone home."                     │
    │                                                                                 │
    │  ✓ NO THIRD-PARTY SERVICES                                                     │
    │    No analytics, no CDNs, no external APIs.                                    │
    │                                                                                 │
    │  ✓ NO AUTOMATIC UPDATES                                                        │
    │    You control when (or if) to update.                                         │
    │                                                                                 │
    │  ✓ OPEN SOURCE (if applicable)                                                 │
    │    Code is auditable. No hidden functionality.                                 │
    │                                                                                 │
    │  ✓ LOCALHOST-ONLY COMMUNICATION                                                │
    │    Browser extension only talks to 127.0.0.1.                                  │
    │                                                                                 │
    │  ✓ MINIMAL PERMISSIONS                                                         │
    │    Extension only requests necessary permissions.                              │
    │                                                                                 │
    │  ✓ NO ADMIN RIGHTS REQUIRED                                                    │
    │    Installs and runs in user space.                                            │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘
```

---

## Development Roadmap

### Current Status

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              DEVELOPMENT STATUS                                       │
└──────────────────────────────────────────────────────────────────────────────────────┘

    OVERALL PROGRESS: ████████████████░░░░░░░░  70% Complete

    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  COMPONENT                    │  STATUS  │  PROGRESS                            │
    ├────────────────────────────────────────────────────────────────────────────────┤
    │  Core Engine                  │  Done    │  █████████████████████████████████  │
    │  Database Layer               │  Done    │  █████████████████████████████████  │
    │  Windows Integration          │  Done    │  █████████████████████████████████  │
    │  HTTP Bridge                  │  Done    │  █████████████████████████████████  │
    │  UI Widgets                   │  Done    │  █████████████████████████████████  │
    │  UI Pages                     │  Done    │  █████████████████████████████████  │
    │  Theme System                 │  Done    │  █████████████████████████████████  │
    │  Browser Extension            │  TODO    │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
    │  System Tray Icon             │  TODO    │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
    │  Nudge Popup Window           │  TODO    │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
    │  Main Entry Point             │  TODO    │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
    │  Mascot Animations            │  TODO    │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
    │  Packaging/Installer          │  TODO    │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
    └────────────────────────────────────────────────────────────────────────────────┘
```

### Completed Features

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              COMPLETED FEATURES                                       │
└──────────────────────────────────────────────────────────────────────────────────────┘

    ✅ CORE MONITORING ENGINE (engine.py)
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  ✓ QTimer-driven monitoring loop (1 second interval)                           │
    │  ✓ State machine: monitoring, paused, shorts, idle, excluded                  │
    │  ✓ Time bucket aggregation by (day, hour, kind, name)                          │
    │  ✓ Session-based and daily limit checking                                      │
    │  ✓ Per-site limit checking with watched_sites                                  │
    │  ✓ Nudge emission with payload                                                │
    │  ✓ Action resolution (stop, more, pause, bypass, dismiss)                     │
    │  ✓ Extra time tracking for "give me more"                                     │
    │  ✓ Swipe counting from extension data                                         │
    │  ✓ Idle detection integration                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘

    ✅ DATABASE LAYER (db.py)
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  ✓ SQLite with WAL journaling                                                 │
    │  ✓ Usage table operations (add, query, aggregate)                             │
    │  ✓ Events logging and querying                                                │
    │  ✓ Settings persistence with JSON encoding                                    │
    │  ✓ Settings subscription system (change callbacks)                            │
    │  ✓ Data retention (purge_older_than)                                          │
    │  ✓ Delete all data (with confirmation)                                        │
    │  ✓ Thread-safe access via RLock                                               │
    └────────────────────────────────────────────────────────────────────────────────┘

    ✅ WINDOWS INTEGRATION (winapi.py, autostart.py)
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  ✓ Foreground window detection (exe name, pid)                                │
    │  ✓ Idle time detection (GetLastInputInfo)                                     │
    │  ✓ Process ID caching for performance                                         │
    │  ✓ Registry autostart (HKCU\Run)                                              │
    │  ✓ Silent startup with pythonw.exe                                            │
    └────────────────────────────────────────────────────────────────────────────────┘

    ✅ HTTP BRIDGE (server.py)
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  ✓ ThreadingHTTPServer on 127.0.0.1:47615                                     │
    │  ✓ POST /v1/heartbeat endpoint                                                │
    │  ✓ GET /v1/ping endpoint                                                      │
    │  ✓ Origin validation (chrome-extension, moz-extension)                        │
    │  ✓ X-PHI header validation                                                    │
    │  ✓ CORS preflight handling                                                    │
    │  ✓ Thread-safe mailbox (Bridge class)                                         │
    │  ✓ Command queuing for extension                                              │
    └────────────────────────────────────────────────────────────────────────────────┘

    ✅ UI WIDGET LIBRARY (ui/widgets.py)
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  ✓ Panel: rounded card with hover effect                                      │
    │  ✓ PillButton: primary/secondary button with icon                             │
    │  ✓ Toggle: animated switch with signal dot                                    │
    │  ✓ Stepper: increment/decrement control                                       │
    │  ✓ Segmented: tab-like selector                                               │
    │  ✓ StatusChip: pulsing status indicator                                       │
    │  ✓ StatCard: statistic with 7-day pixel bars                                  │
    │  ✓ Timeline: 24-hour dot-matrix grid                                          │
    │  ✓ PixelChart: column chart with stacked squares                              │
    │  ✓ UsageRow: list item with progress dots                                     │
    │  ✓ All widgets include smooth animations                                      │
    └────────────────────────────────────────────────────────────────────────────────┘

    ✅ UI PAGES (ui/pages.py)
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  ✓ TodayPage: greeting, status, stats, timeline                               │
    │  ✓ AppsPage: charts, breakdown, filtering                                     │
    │  ✓ SettingsPage: all configuration options                                    │
    │  ✓ Day-over-day comparison                                                    │
    │  ✓ 7-day trend visualization                                                   │
    │  ✓ Dynamic updates from engine                                                │
    └────────────────────────────────────────────────────────────────────────────────┘

    ✅ THEME SYSTEM (ui/theme.py)
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │  ✓ Warm paper color palette                                                   │
    │  ✓ Font family fallbacks (Geist, Inter, Segoe UI)                             │
    │  ✓ Mono font fallbacks (Geist Mono, JetBrains, Cascadia)                      │
    │  ✓ Color utilities (mix, qc)                                                  │
    │  ✓ Global QSS stylesheet                                                      │
    └────────────────────────────────────────────────────────────────────────────────┘
```

### Upcoming Features

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              UPCOMING FEATURES                                        │
└──────────────────────────────────────────────────────────────────────────────────────┘

    🚧 IN PROGRESS
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │  BROWSER EXTENSION                                                             │
    │  ├── manifest.json (Manifest V3)                                               │
    │  ├── background.js (service worker, heartbeat loop)                            │
    │  ├── content.js (Shorts detection, swipe counting)                             │
    │  └── popup UI (optional)                                                       │
    │                                                                                 │
    │  MAIN ENTRY POINT                                                              │
    │  ├── run_phi.pyw (silent startup)                                              │
    │  ├── System tray icon with menu                                                │
    │  └── Window state management (minimize to tray)                                │
    │                                                                                 │
    │  NUDGE POPUP WINDOW                                                            │
    │  ├── Frameless window with mascot                                              │
    │  ├── Message display                                                           │
    │  ├── Action buttons (Stop, More, Pause, Bypass)                                │
    │  └── Celebration animation on "Stop"                                           │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘

    📋 PLANNED
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │  PHASE 2                                                                        │
    │  ├── Mascot sprite animations (idle, alert, celebrate)                         │
    │  ├── Sound notifications (optional)                                            │
    │  ├── Custom nudge messages                                                     │
    │  └── Focus mode (block distracting sites temporarily)                          │
    │                                                                                 │
    │  PHASE 3                                                                        │
    │  ├── Weekly report generation                                                  │
    │  ├── Data export (JSON, CSV)                                                   │
    │  ├── Multiple mascot designs                                                   │
    │  └── Custom themes                                                             │
    │                                                                                 │
    │  PHASE 4                                                                        │
    │  ├── macOS support                                                             │
    │  ├── Linux support                                                             │
    │  └── Installer/package distribution                                            │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘

    📊 FEATURE PRIORITY
    ┌────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │  Priority 1 (Required for MVP):                                                │
    │  ┌─────────────────────────────────────────────────────────────────────────┐   │
    │  │  1. Browser extension → Without this, no website tracking               │   │
    │  │  2. Main entry point + Tray icon → User needs way to run the app        │   │
    │  │  3. Nudge popup → Core feature, currently missing                        │   │
    │  └─────────────────────────────────────────────────────────────────────────┘   │
    │                                                                                 │
    │  Priority 2 (Important):                                                        │
    │  ┌─────────────────────────────────────────────────────────────────────────┐   │
    │  │  4. Mascot animations → Enhances user experience                        │   │
    │  │  5. Sound notifications → Makes nudges more noticeable                   │   │
    │  │  6. Focus mode → Adds proactive blocking                                 │   │
    │  └─────────────────────────────────────────────────────────────────────────┘   │
    │                                                                                 │
    │  Priority 3 (Nice to have):                                                     │
    │  ┌─────────────────────────────────────────────────────────────────────────┐   │
    │  │  7. Weekly reports → Self-reflection tool                                │   │
    │  │  8. Data export → Data portability                                       │   │
    │  │  9. Cross-platform → Wider audience                                      │   │
    │  └─────────────────────────────────────────────────────────────────────────┘   │
    │                                                                                 │
    └────────────────────────────────────────────────────────────────────────────────┘
```

---

## Contributing

We welcome contributions! Please follow these guidelines:

### Code Style

- **Python**: Follow PEP 8
- **Type Hints**: Use type annotations for all function signatures
- **Docstrings**: Use triple-quoted docstrings for classes and public methods
- **UI Components**: Match existing patterns in `ui/widgets.py`

### Development Setup

```powershell
# Clone and setup
git clone https://github.com/yourusername/PHI_FOCUS.git
cd PHI_FOCUS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install PySide6 pytest

# Run tests
pytest tests/

# Preview mascot
python tools/preview_mascot.py
```

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Privacy Requirements

**IMPORTANT**: Never add:
- Telemetry or analytics
- Network calls to external servers
- Data collection beyond what's specified in the privacy policy
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


---

## Build the exe and installer

```powershell
.\build.ps1    # -> dist\PHI\PHI.exe and installer_output\PHI-Setup.exe (needs Inno Setup 6)
```

The installer is per-user (no admin), adds Start Menu shortcuts, and copies the `extension` folder next to the app.
