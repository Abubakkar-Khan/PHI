"""Small shared helpers: formatting and name normalisation."""
from __future__ import annotations

SITE_LABELS = {
    "youtube.com": "YouTube",
    "instagram.com": "Instagram",
    "reddit.com": "Reddit",
    "tiktok.com": "TikTok",
    "x.com": "X",
    "twitter.com": "X",
    "facebook.com": "Facebook",
    "github.com": "GitHub",
    "google.com": "Google",
    "stackoverflow.com": "Stack Overflow",
    "linkedin.com": "LinkedIn",
    "netflix.com": "Netflix",
    "twitch.tv": "Twitch",
    "wikipedia.org": "Wikipedia",
    "chatgpt.com": "ChatGPT",
    "notion.so": "Notion",
}

APP_LABELS = {
    "code.exe": "VS Code",
    "windowsterminal.exe": "Terminal",
    "explorer.exe": "File Explorer",
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "firefox.exe": "Firefox",
    "brave.exe": "Brave",
    "devenv.exe": "Visual Studio",
    "winword.exe": "Word",
    "excel.exe": "Excel",
    "powerpnt.exe": "PowerPoint",
    "spotify.exe": "Spotify",
    "discord.exe": "Discord",
    "slack.exe": "Slack",
    "kiro.exe": "Kiro",
    "pwsh.exe": "PowerShell",
    "powershell.exe": "PowerShell",
    "cmd.exe": "Command Prompt",
    "notepad.exe": "Notepad",
    "python.exe": "Python",
    "pythonw.exe": "Python",
}

_SECOND_LEVEL = {"co", "com", "org", "gov", "ac", "net", "edu"}


def normalize_host(host: str) -> str:
    """Collapse a hostname to its registrable-ish domain (music.youtube.com -> youtube.com)."""
    host = (host or "").strip().lower().rstrip(".")
    if not host or host.replace(".", "").isdigit() or ":" in host:
        return host
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if len(parts[-1]) == 2 and parts[-2] in _SECOND_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def host_matches(host: str, domain: str) -> bool:
    host, domain = host.lower(), domain.lower().strip()
    return bool(domain) and (host == domain or host.endswith("." + domain))


def clean_domain(text: str) -> str:
    """Accept 'https://www.Reddit.com/r/x' or 'reddit.com' and return 'reddit.com'."""
    t = (text or "").strip().lower()
    for prefix in ("https://", "http://"):
        if t.startswith(prefix):
            t = t[len(prefix):]
    t = t.split("/")[0].split("?")[0]
    if t.startswith("www."):
        t = t[4:]
    return t


def pretty_site(domain: str) -> str:
    if domain in SITE_LABELS:
        return SITE_LABELS[domain]
    base = domain.split(".")[0] if domain else "Unknown"
    return base.capitalize()


def pretty_app(exe: str) -> str:
    key = exe.lower()
    if key in APP_LABELS:
        return APP_LABELS[key]
    stem = key[:-4] if key.endswith(".exe") else key
    return stem.replace("_", " ").replace("-", " ").title() or "Unknown"


def fmt_dur(seconds: float) -> str:
    s = int(round(seconds))
    if s < 60:
        return f"{s}s" if s > 0 else "0m"
    m = s // 60
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def fmt_clock(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def minutes_text(seconds: float) -> str:
    m = max(1, int(round(seconds / 60)))
    return f"{m} minute{'s' if m != 1 else ''}"
