"""Read-side helpers shared by the Today and Activity screens.

Websites are split three ways so the numbers mean what they say:
  * YouTube Shorts      (kind "shorts")
  * YouTube             (the youtube.com site total minus Shorts)
  * every other website (kind "site")
Desktop apps are kind "app".
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from .db import Store
from .utils import pretty_app, pretty_site

SCOPES = ("all", "apps", "sites")
MIN_SECONDS = 60          # anything under a minute is noise: never listed


@dataclass
class Item:
    kind: str        # app | site | shorts
    key: str         # exe, domain or "youtube"
    label: str
    tag: str         # small caption under the name
    seconds: float
    red: bool = False


def _scope_kinds(scope: str) -> tuple[str, ...]:
    return {"apps": ("app",), "sites": ("site",)}.get(scope, ("total",))


def hidden_pairs(cfg) -> frozenset:
    """The (kind, key) pairs the user chose to hide from every view."""
    out = set()
    for h in cfg.get("hidden_items") or []:
        try:
            out.add((h["kind"], h["key"]))
        except (KeyError, TypeError):
            continue
    return frozenset(out)


def hide_item(cfg, kind: str, key: str, label: str) -> None:
    cur = [h for h in cfg.get("hidden_items") or [] if (h.get("kind"), h.get("key")) != (kind, key)]
    cur.append({"kind": kind, "key": key, "label": label})
    cfg.set("hidden_items", cur)


def unhide_item(cfg, kind: str, key: str) -> None:
    cfg.set("hidden_items", [h for h in cfg.get("hidden_items") or [] if (h.get("kind"), h.get("key")) != (kind, key)])


def _in_scope(kind: str, scope: str) -> bool:
    return scope == "all" or (scope == "apps") == (kind == "app")


def breakdown(store: Store, d0: str, d1: str, scope: str = "all", hidden=frozenset()) -> list[Item]:
    """Ranked items between two ISO dates (inclusive)."""
    rows = store.by_name(d0, d1, ("app", "site"))
    shorts_total = sum(s for _k, _n, s in store.by_name(d0, d1, ("shorts",)))
    items: list[Item] = []
    for kind, name, secs in rows:
        if kind == "site" and name == "youtube.com":
            secs = max(0.0, secs - shorts_total)             # Shorts are listed on their own line
            if secs < MIN_SECONDS:
                continue
            items.append(Item("site", name, "YouTube", "WEBSITE · WITHOUT SHORTS", secs))
        elif kind == "site":
            items.append(Item("site", name, pretty_site(name), "WEBSITE", secs))
        else:
            items.append(Item("app", name, pretty_app(name), "APP", secs))
    if shorts_total >= MIN_SECONDS:
        items.append(Item("shorts", "youtube", "YouTube Shorts", "WEBSITE · SHORTS", shorts_total, True))
    items = [i for i in items if i.seconds >= MIN_SECONDS and (i.kind, i.key) not in hidden]
    if scope == "apps":
        items = [i for i in items if i.kind == "app"]
    elif scope == "sites":
        items = [i for i in items if i.kind != "app"]
    return sorted(items, key=lambda i: i.seconds, reverse=True)


def hourly_for(store: Store, day: str, item: Item) -> list[float]:
    if item.kind == "shorts":
        return store.hourly(day, "shorts", "youtube")
    hours = store.hourly(day, item.kind, item.key)
    if item.kind == "site" and item.key == "youtube.com":
        sh = store.hourly(day, "shorts", "youtube")
        hours = [max(0.0, a - b) for a, b in zip(hours, sh)]
    return hours


def hourly_scope(store: Store, day: str, scope: str, hidden=frozenset()) -> tuple[list[float], list[float]]:
    """(total per hour, Shorts per hour) for the chart of one day."""
    if scope == "all":
        total = store.hourly(day, "total", "*")
    else:
        total = store.hourly_kinds(day, _scope_kinds(scope))
    shorts = store.hourly(day, "shorts", "youtube") if scope != "apps" else [0.0] * 24
    for kind, key in hidden:
        if not _in_scope(kind, scope):
            continue
        h = hourly_for(store, day, Item(kind, key, key, "", 0))
        total = [max(0.0, a - b) for a, b in zip(total, h)]
        if kind == "shorts":
            shorts = [0.0] * 24
    return total, shorts


def daily_scope(store: Store, d0: date, d1: date, scope: str, hidden=frozenset()) -> tuple[dict[str, float], dict[str, float]]:
    """(total per day, Shorts per day) between two dates."""
    a, b = d0.isoformat(), d1.isoformat()
    if scope == "all":
        total = store.daily_kind_range(a, b, ("total",), "*")
    else:
        total = store.daily_kind_range(a, b, _scope_kinds(scope))
    shorts = store.daily_kind_range(a, b, ("shorts",), "youtube") if scope != "apps" else {}
    for kind, key in hidden:
        if not _in_scope(kind, scope):
            continue
        sub = store.daily_kind_range(a, b, (kind,), key)
        if kind == "site" and key == "youtube.com":
            sh = store.daily_kind_range(a, b, ("shorts",), "youtube")
            sub = {d: max(0.0, v - sh.get(d, 0.0)) for d, v in sub.items()}
        total = {d: max(0.0, v - sub.get(d, 0.0)) for d, v in total.items()}
        if kind == "shorts":
            shorts = {}
    return total, shorts


def period(mode: int, anchor: date) -> tuple[date, date]:
    """mode 0 = day, 1 = Monday-to-Sunday week, 2 = calendar month."""
    if mode == 0:
        return anchor, anchor
    if mode == 1:
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    last = calendar.monthrange(anchor.year, anchor.month)[1]
    return anchor.replace(day=1), anchor.replace(day=last)


def shift(mode: int, anchor: date, steps: int) -> date:
    if mode == 0:
        return anchor + timedelta(days=steps)
    if mode == 1:
        return anchor + timedelta(days=7 * steps)
    month = anchor.month - 1 + steps
    year = anchor.year + month // 12
    month = month % 12 + 1
    return anchor.replace(year=year, month=month, day=min(anchor.day, calendar.monthrange(year, month)[1]))


def period_label(mode: int, anchor: date) -> str:
    d0, d1 = period(mode, anchor)
    if mode == 0:
        return d0.strftime("%a %d %b %Y").upper()
    if mode == 1:
        return f"{d0.strftime('%d %b')} – {d1.strftime('%d %b %Y')}".upper()
    return d0.strftime("%B %Y").upper()
