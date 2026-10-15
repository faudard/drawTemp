"""Opt-in R9.D event pages layered on the canonical tactical trigger journal.

An old trigger without pages is unchanged. Pages are priority-ordered views of
ONE event ID, not independent triggers. Activation toggles and repeated firings
are derived from Battle.events, which is reconstructed by the authenticated
command replay. No mutable sidecar state, save version or parallel scheduler.
"""
from __future__ import annotations

from copy import deepcopy
from .model import require
from .rules.registry import TriggerActionRule
from .rules.triggers import validate_composite, matches_composite

PAGE_KEYS = frozenset((
    "id", "priority", "enabled", "repeat", "cooldown_ticks", "condition",
    "value", "pos", "unit", "percent", "max_alive", "team", "object",
    "when", "actions",
))
MAX_PAGES = 8


def page_rules(rules):
    """Enable a single explicit action only for opted-in authored documents."""
    if "event_state" in rules.trigger_actions:
        return rules

    def validate(context, row):
        require(set(row) in ({"kind", "event", "enabled"},
                             {"kind", "event", "page", "enabled"}),
                "Invalid event_state fields")
        require(type(row["event"]) is str and bool(row["event"]),
                "event_state requires a target event")
        require(type(row["enabled"]) is bool,
                "event_state.enabled must be Boolean")
        if "page" in row:
            require(type(row["page"]) is str and bool(row["page"]),
                    "event_state.page must be a page id")

    def apply(battle, row):
        battle.emit("event_state", event=row["event"],
                    page=row.get("page", ""),
                    enabled=row["enabled"])

    registry = rules.trigger_actions.with_rule(
        "event_state", TriggerActionRule(apply, validate, version="5.0-r9d"))
    return rules.with_family("trigger_actions", registry)


def has_pages(data):
    return any("pages" in event or "enabled" in event or "repeat" in event or
               any(action.get("kind") == "event_state"
                   for action in event.get("actions", ())) or
               any(action.get("kind") == "event_state"
                   for page in event.get("pages", ())
                   for action in page.get("actions", ()))
               for mission in data.get("missions", ())
               for event in mission.get("triggers", ()))


def validate_pages(mission, context, rules):
    """Validate page-specific native conditions, actions, and cross-references."""
    events = mission.triggers
    refs = {row["id"]: row for row in events}
    for trigger in events:
        if "enabled" in trigger:
            require(type(trigger["enabled"]) is bool, "Invalid base page enabled")
        if "repeat" in trigger:
            require(type(trigger["repeat"]) is bool, "Invalid base page repeat")
        if "cooldown_ticks" in trigger:
            require(trigger.get("repeat") is True and
                    type(trigger["cooldown_ticks"]) is int and
                    1 <= trigger["cooldown_ticks"] <= 10000,
                    "Cooldown requires a repeated event")
        pages = trigger.get("pages", ())
        require(isinstance(pages, (tuple, list)) and len(pages) <= MAX_PAGES,
                "Too many event pages")
        seen = {"base"}
        for page in pages:
            require(isinstance(page, dict) and
                    {"id", "priority", "condition", "actions"} <= set(page) <= PAGE_KEYS,
                    "Invalid event page fields")
            pid = page["id"]
            require(type(pid) is str and 1 <= len(pid) <= 64 and
                    pid.isascii() and
                    all(ch.isalnum() or ch in "_-" for ch in pid) and
                    pid not in seen, "Invalid or duplicate event page ID")
            seen.add(pid)
            require(type(page["priority"]) is int and
                    -100 <= page["priority"] <= 100,
                    "Event page priority must be -100..100")
            require(type(page.get("enabled", True)) is bool and
                    type(page.get("repeat", False)) is bool,
                    "Invalid page activation/repeat flag")
            if "cooldown_ticks" in page:
                require(page.get("repeat") is True and
                        type(page["cooldown_ticks"]) is int and
                        1 <= page["cooldown_ticks"] <= 10000,
                        "Cooldown requires a repeated page")
            rules.trigger_conditions.get(page["condition"]).validate(
                context, page)
            if "when" in page:
                validate_composite(context, page["when"])
            require(isinstance(page["actions"], list) and page["actions"],
                    "A page needs at least one action")
            for action in page["actions"]:
                rules.trigger_actions.get(action["kind"]).validate(context, action)
        for page in (trigger, *pages):
            for action in page["actions"]:
                if action["kind"] != "event_state":
                    continue
                target = refs.get(action["event"])
                require(target is not None, "Unknown event_state target")
                target_pages = {"base"} | {
                    row["id"] for row in target.get("pages", ())}
                require(action.get("page", "base") in target_pages,
                        "Unknown event_state page")


def _override(battle, event_id, page_id, default):
    value = default
    for row in battle.events:
        if (row["kind"] == "event_state" and row["event"] == event_id and
                row.get("page", "") in ("", page_id) and
                (not row.get("page") or row["page"] == page_id)):
            value = row["enabled"]
    return value


def _matches(battle, page):
    if not battle.rules.trigger_conditions.get(
            page["condition"]).matches(battle, page):
        return False
    return "when" not in page or matches_composite(battle, page["when"])


def active_page(battle, trigger):
    """Highest-priority *matching* and enabled page, including implicit base."""
    base = {k: deepcopy(v) for k, v in trigger.items()
            if k not in ("pages", "after", "after_any", "cancel_after",
                         "after_choice")}
    base.update({"id": "base", "priority": 0,
                 "enabled": trigger.get("enabled", True),
                 "repeat": trigger.get("repeat", False),
                 "cooldown_ticks": trigger.get("cooldown_ticks", 1)})
    pages = [base] + deepcopy(trigger.get("pages", []))
    ordered = sorted(enumerate(pages),
                     key=lambda row: (-row[1].get("priority", 0), row[0]))
    for _, page in ordered:
        if not _override(battle, trigger["id"], page["id"],
                         page.get("enabled", True)):
            continue
        if _matches(battle, page):
            return page
    return None


def can_fire_page(battle, trigger, page):
    """One-shot per-page or bounded repeat, never more than once per tick."""
    previous = [row for row in battle.events
                if row["kind"] == "trigger" and row["id"] == trigger["id"]
                and row.get("page", "base") == page["id"]]
    if not previous:
        return True
    if not page.get("repeat", False):
        return False
    cooldown = page.get("cooldown_ticks", 1)
    return battle.tick - previous[-1]["tick"] >= cooldown


def page_snapshot(battle, event_id):
    """Deterministic inspection for both Studio debugger and Player."""
    trigger = next((row for row in battle.mission.triggers
                    if row["id"] == event_id), None)
    require(trigger is not None, "Unknown tactical event")
    current = active_page(battle, trigger)
    keys = ("base",) + tuple(page["id"] for page in trigger.get("pages", ()))
    return {
        "event_id": event_id,
        "active_page": current["id"] if current else None,
        "enabled": {page: _override(battle, event_id, page,
                      trigger.get("enabled", True) if page == "base" else
                      next(p.get("enabled", True) for p in trigger["pages"]
                           if p["id"] == page)) for page in keys},
        "fire_count": {page: sum(row["kind"] == "trigger" and
                               row["id"] == event_id and
                               row.get("page", "base") == page
                               for row in battle.events) for page in keys},
    }


def _edit(data, mission_id, event_id, callback):
    from .tactical_rpg3 import authored_rules_for_document
    from .model import Content
    updated = deepcopy(data)
    mission = next((mission for mission in updated["missions"]
                    if mission["id"] == mission_id), None)
    require(mission is not None, "Unknown event mission")
    event = next((row for row in mission["triggers"]
                  if row["id"] == event_id), None)
    require(event is not None, "Unknown event")
    callback(event)
    return Content.from_dict(
        updated, rules=authored_rules_for_document(updated)).to_dict()


def create_page(data, mission_id, event_id, *, page_id, priority,
                condition, actions, enabled=True, repeat=False,
                cooldown_ticks=1):
    def edit(event):
        require(not any(row["id"] == page_id for row in event.get("pages", ())),
                "Duplicate event page")
        require(type(repeat) is bool and type(enabled) is bool,
                "Invalid page state")
        page = {**deepcopy(condition), "id": page_id,
                "priority": priority, "enabled": enabled,
                "repeat": repeat, "actions": deepcopy(actions)}
        if repeat:
            page["cooldown_ticks"] = cooldown_ticks
        event.setdefault("pages", []).append(page)
    return _edit(data, mission_id, event_id, edit)


def update_page(data, mission_id, event_id, page_id, *, priority=None,
                enabled=None, repeat=None, cooldown_ticks=None):
    def edit(event):
        if page_id == "base":
            page = event
        else:
            page = next((row for row in event.get("pages", ())
                         if row["id"] == page_id), None)
        require(page is not None, "Unknown event page")
        if priority is not None:
            require(page_id != "base", "Base page has fixed priority zero")
            page["priority"] = priority
        if enabled is not None:
            page["enabled"] = enabled
        if repeat is not None:
            page["repeat"] = repeat
            if not repeat:
                page.pop("cooldown_ticks", None)
        if cooldown_ticks is not None:
            require(page.get("repeat", False), "Repeat must be enabled first")
            page["cooldown_ticks"] = cooldown_ticks
    return _edit(data, mission_id, event_id, edit)


def remove_page(data, mission_id, event_id, page_id):
    require(page_id != "base", "The base event page cannot be removed")
    def edit(event):
        pages = event.get("pages", [])
        before = len(pages)
        event["pages"] = [row for row in pages if row["id"] != page_id]
        require(len(event["pages"]) != before, "Unknown event page")
        if not event["pages"]:
            event.pop("pages")
    return _edit(data, mission_id, event_id, edit)


def update_page_commands(data, mission_id, event_id, page_id, *,
                         condition=None, actions=None):
    """Typed edit of a whole page: preserves R1 atomicity and strict validation."""
    def edit(event):
        require(page_id != "base", "Edit base through the existing event commands")
        page = next((row for row in event.get("pages", ())
                     if row["id"] == page_id), None)
        require(page is not None, "Unknown event page")
        if condition is not None:
            for key in ("condition", "value", "pos", "unit",
                        "percent", "max_alive", "team", "object"):
                page.pop(key, None)
            page.update(deepcopy(condition))
        if actions is not None:
            page["actions"] = deepcopy(actions)
    return _edit(data, mission_id, event_id, edit)
