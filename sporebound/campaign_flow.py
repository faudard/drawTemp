"""R5.B Campaign Flow: project-owned conditions and verified cross-mission effects.

Keeps Content.next_missions and StoryBook as the canonical routing/choice engines.
No effects are run inside Battle; only authenticated mission settlement commits them.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from .model import require
from .narrative import _condition, _effect, matches


def definition_digest(flow):
    if not flow:
        return ""
    return hashlib.sha256(json.dumps(flow, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_flow(flow, content):
    require(isinstance(flow, dict) and set(flow) <= {"gates", "outcomes", "endings"},
            "Campaign flow must contain gates, outcomes and/or endings")
    require(len(flow.get("gates", {})) <= 256 and
            len(flow.get("outcomes", {})) <= 256 and
            len(flow.get("endings", {})) <= 64, "Campaign flow exceeds authoring limits")
    gates, outcomes, endings = (flow.get(key, {}) for key in
                               ("gates", "outcomes", "endings"))
    require(all(isinstance(x, dict) for x in (gates, outcomes, endings)),
            "Campaign flow sections must be objects")
    for mission, condition in gates.items():
        require(mission in content.missions, "Unknown gated mission: " + str(mission))
        _condition(condition, content)
    from .character_growth31 import WOUNDS
    heroes = {unit.id for mission in content.missions.values()
              for unit in mission.units if unit.team == "player"}
    for mission, results in outcomes.items():
        require(mission in content.missions and isinstance(results, dict) and
                bool(results) and set(results) <= {"victory", "defeat"},
                "Invalid mission consequence")
        for outcome, effects in results.items():
            require(isinstance(effects, list) and len(effects) <= 20,
                    "Invalid consequence effects")
            for effect in effects:
                require(isinstance(effect, dict), "Consequence must be an object")
                if effect.get("kind") in {"wound", "heal_wound"}:
                    require(set(effect) == {"kind", "hero", "wound"} and
                            effect["hero"] in heroes and effect["wound"] in WOUNDS,
                            "Unknown hero or wound in campaign consequence")
                else:
                    _effect(effect, content)
    for ending, condition in endings.items():
        require(isinstance(ending, str) and 0 < len(ending) <= 64 and
                all(c.isalnum() or c in "-_" for c in ending),
                "Invalid campaign ending id")
        _condition(condition, content)


def verify_save(progress, flow):
    """Legacy slots remain valid for legacy projects; newly authored flows
    require an explicit migration, never a silent reinterpretation of a slot.
    """
    require(progress.flow_digest == definition_digest(flow),
            "Campaign flow differs from saved campaign; explicit migration required")
    require(all(isinstance(key, str) and key.count(":") == 1 and
                key.rsplit(":", 1)[1] in {"victory", "defeat"}
                for key in progress.flow_ledger), "Invalid campaign consequence ledger")


def available_missions(progress, flow):
    gates = flow.get("gates", {})
    return [mid for mid in progress.unlocked if mid not in progress.completed
            and (mid not in gates or matches(gates[mid], progress))]


def _apply_effect(progress, effect, content):
    kind = effect["kind"]
    if kind == "set_flag":
        progress.story_flags[effect["flag"]] = deepcopy(effect["value"])
    elif kind == "add_flag":
        before = progress.story_flags.get(effect["flag"], 0)
        require(type(before) is int, "Cannot add to a non-numeric campaign flag")
        updated = before + effect["amount"]
        require(-1000000 <= updated <= 1000000, "Campaign flag out of bounds")
        progress.story_flags[effect["flag"]] = updated
    elif kind == "gold":
        updated = progress.gold + effect["amount"]
        require(0 <= updated <= 1000000, "Campaign gold out of bounds")
        progress.gold = updated
    elif kind == "grant_item":
        name = effect["item"]
        amount = progress.inventory.get(name, 0) + effect["quantity"]
        require(amount <= 1000000, "Campaign inventory out of bounds")
        progress.inventory[name] = amount
    elif kind == "unlock_mission":
        if effect["mission"] not in progress.unlocked:
            progress.unlocked.append(effect["mission"])
    elif kind == "recruit_hero":
        uid = effect["hero"]
        require(not progress.story_flags.get("recruited_" + uid, False),
                "Campaign hero already recruited")
        progress.hero(uid)
        progress.story_flags["recruited_" + uid] = True
    elif kind == "equip_hero":
        uid = effect["hero"]
        require(content is not None, "Equipment consequence requires Content")
        require(not any("recruit:" + uid in unit.tags
                        for mission in content.missions.values()
                        for unit in mission.units)
                or progress.story_flags.get("recruited_" + uid) is True,
                "Hero has not been recruited")
        progress.equip(content, uid, effect["item"])
    elif kind in {"wound", "heal_wound"}:
        wounds = progress.hero(effect["hero"]).wounds
        if kind == "wound":
            if effect["wound"] not in wounds:
                require(len(wounds) < 2, "Maximum persistent hero wounds reached")
                wounds.append(effect["wound"])
        elif effect["wound"] in wounds:
            wounds.remove(effect["wound"])


def settle(progress, flow, mission, result, *, content=None):
    """Return a new progress snapshot; never mutate the provided live campaign.

    A defeat may precede a later victory, but each outcome is committed at most
    once per mission. The outer GameSession/PlayerSession persists atomically.
    """
    verify_save(progress, flow)
    require(result in {"victory", "defeat"}, "Campaign outcome is not final")
    effects = flow.get("outcomes", {}).get(mission, {}).get(result, [])
    key = mission + ":" + result
    if key in progress.flow_ledger or not effects:
        return progress
    updated = deepcopy(progress)
    for effect in effects:
        _apply_effect(updated, effect, content)
    require(len(updated.flow_ledger) < 512, "Campaign consequence ledger exhausted")
    updated.flow_ledger.append(key)
    return updated


def inspect_campaign(progress, flow):
    """Read-only inspector shared by Studio, CLI and independent Player."""
    verify_save(progress, flow)
    flags = deepcopy(progress.story_flags)
    prefixes = {
        "reputation": ("reputation_", "trust_"),
        "supplies": ("supplies_", "provisions_"),
        "fortifications": ("fortification_", "gate_", "wall_"),
        "allies": ("allies_", "recruited_"),
        "enemies": ("enemy_",),
    }
    return {
        "variables": flags,
        "reputation": {k: v for k, v in flags.items() if k.startswith(prefixes["reputation"])},
        "resources": {"gold": progress.gold, "inventory": deepcopy(progress.inventory),
                      "supplies": {k: v for k, v in flags.items()
                                   if k.startswith(prefixes["supplies"])}},
        "companions": {k: {"job": h.job, "morale": h.morale,
                            "wounds": list(h.wounds)}
                       for k, h in sorted(progress.heroes.items())},
        "fortifications": {k: v for k, v in flags.items()
                           if k.startswith(prefixes["fortifications"])},
        "allies": {k: v for k, v in flags.items() if k.startswith(prefixes["allies"])},
        "enemies": {k: v for k, v in flags.items() if k.startswith(prefixes["enemies"])},
        "missions": {"unlocked": list(progress.unlocked),
                     "available": available_missions(progress, flow),
                     "completed": list(progress.completed),
                     "blocked": [mid for mid in progress.unlocked
                                 if mid not in progress.completed
                                 and mid not in available_missions(progress, flow)]},
        "endings": [eid for eid, condition in flow.get("endings", {}).items()
                    if matches(condition, progress)],
        "consequences": list(progress.flow_ledger),
    }


def audit_campaign(content, project, campaign_id, *, max_states=384, max_depth=32):
    """Explore *candidate* mission/story branches with bounded symbolic victories.

    This is not tactical verification: only an actual recorded GameSession
    replay proves a victory, trigger or offscreen multi-front resolution.
    Every report explicitly states this coverage boundary.
    """
    from collections import deque
    from dataclasses import asdict
    from .campaign import Campaign
    from .campaign_graph import inspect_graph
    from .model import RuleError
    from .narrative import StoryBook

    project.validate(content)
    campaign = project.campaign(campaign_id)
    require(campaign is not None, "Unknown campaign")
    require(type(max_states) is int and 1 <= max_states <= 4096 and
            type(max_depth) is int and 1 <= max_depth <= 128,
            "Invalid campaign QA search limits")
    graph = inspect_graph(content, [campaign["start_mission"]])
    flow = project.campaign_flow
    reachable = set(graph["reachable"])
    gates = flow.get("gates", {})
    gated = sorted(set(gates) & reachable)
    endings = flow.get("endings", {})
    # This particular gate can never open until its own locked mission is done.
    impossible = sorted(mid for mid in gated
                        if gates[mid].get("completed_mission") == mid)
    errors = [f"Mission requires its own completion: {mid}" for mid in impossible]
    warnings = [f"Graph-unreachable gated mission: {mid}"
                for mid in sorted(set(gates) - reachable)]
    initial = project.new_game(campaign_id, content)
    Campaign.from_dict({"version": 1, **asdict(initial)})
    story = StoryBook(project.story, content, project.campaigns)
    queue = deque([(initial, [])])
    explored = set()
    possible_missions = set()
    possible_unlocks = set(initial.unlocked)
    ending_paths = {}
    duplicate_rewards = []
    truncated = False
    blocked_effects = set()

    def fingerprint(progress):
        # No random IDs, timestamps or non-gameplay history.
        values = {
            "unlocked": progress.unlocked, "completed": progress.completed,
            "flags": progress.story_flags, "pending": progress.story_pending,
            "gold": progress.gold, "inventory": progress.inventory,
            "ledger": progress.flow_ledger,
            "wounds": {uid: hero.wounds for uid, hero in progress.heroes.items()},
        }
        return json.dumps(values, ensure_ascii=False, sort_keys=True)

    while queue:
        if len(explored) >= max_states:
            truncated = True
            break
        progress, path = queue.popleft()
        identity = fingerprint(progress)
        if identity in explored:
            continue
        explored.add(identity)
        possible_unlocks.update(progress.unlocked)
        for ending, condition in endings.items():
            if ending not in ending_paths and matches(condition, progress):
                ending_paths[ending] = path
        if len(path) >= max_depth:
            truncated = truncated or bool(available_missions(progress, flow) or
                                          progress.story_pending)
            continue
        if progress.story_pending:
            for choice in story.choices(progress):
                try:
                    updated = story.choose(progress, choice["id"])
                except RuleError as exc:
                    blocked_effects.add(str(exc))
                    continue
                queue.append((updated, path + [
                    "choice:" + progress.story_pending + "/" + choice["id"]]))
            continue
        for mid in available_missions(progress, flow):
            possible_missions.add(mid)
            updated = deepcopy(progress)
            updated.completed.append(mid)
            updated.gold += content.missions[mid].reward  # Symbolic victory; loot unknown.
            if mid in story.after:
                story.after_victory(updated, mid)
            else:
                for successor in content.missions[mid].next_missions:
                    if successor not in updated.unlocked:
                        updated.unlocked.append(successor)
            try:
                updated = settle(updated, flow, mid, "victory", content=content)
                twice = settle(updated, flow, mid, "victory", content=content)
                if twice != updated:
                    duplicate_rewards.append(mid)
            except RuleError as exc:
                blocked_effects.add(str(exc))
                continue
            queue.append((updated, path + [mid + ":victory"]))
            if flow.get("outcomes", {}).get(mid, {}).get("defeat"):
                try:
                    defeated = settle(progress, flow, mid, "defeat", content=content)
                    if defeated != progress:
                        queue.append((defeated, path + [mid + ":defeat"]))
                except RuleError as exc:
                    blocked_effects.add(str(exc))

    never_unlocked = sorted(set(content.missions) - possible_unlocks)
    unplayed = sorted(possible_unlocks - possible_missions)
    unreachable_endings = sorted(set(endings) - set(ending_paths))
    if truncated:
        warnings.append("Exploration bounded; missing paths are not certified unreachable")
    if unreachable_endings:
        warnings.append("Endings not witnessed by symbolic routes: " +
                        ", ".join(unreachable_endings))
    if blocked_effects:
        warnings.append("Some symbolic effects require runtime setup: " +
                        "; ".join(sorted(blocked_effects)[:4]))
    if duplicate_rewards:
        errors.append("Repeated consequence rewards: " + ", ".join(duplicate_rewards))
    return {
        "campaign": campaign_id, "start": campaign["start_mission"],
        "reachable": sorted(reachable), "unreachable": graph["unreachable"],
        "terminal": [mid for mid in graph["terminal"] if mid in reachable],
        "cycles": graph["cycles"], "gated": gated, "endings": sorted(endings),
        "possible_missions": sorted(possible_missions),
        "never_unlocked_in_preview": never_unlocked,
        "unplayed_in_preview": unplayed,
        "ending_witnesses": ending_paths,
        "unreachable_endings_in_preview": unreachable_endings,
        "duplicated_outcomes": duplicate_rewards,
        "states_explored": len(explored),
        "truncated": truncated,
        "save_contract": "campaign flow fingerprint + verified once-only ledger",
        "errors": errors, "warnings": warnings,
        "scope": "Bounded symbolic routes, not tactical victory or full GameSession replay",
    }


def check_campaign_save(path, content, project, campaign_id, *, kind, rules=None):
    """Read and validate a user-owned save without rewriting it.

    Legacy slots retain their campaign v1 envelope; unified checkpoints use
    SessionStore's digest, project identity, rules and tactical replay checks.
    Recovery from a valid backup is disclosed explicitly to the caller.
    """
    from pathlib import Path
    from .campaign import Campaign
    from .game_session import GameSession
    from .narrative import StoryBook
    from .persistence import SessionStore

    project.validate(content)
    require(project.campaign(campaign_id) is not None, "Unknown save campaign")
    require(kind in {"slot", "session"}, "Unknown campaign save kind")
    path = Path(path)
    if kind == "slot":
        progress = Campaign.load(path, ruleset=rules)
        verify_save(progress, project.campaign_flow)
        require(set(progress.unlocked + progress.completed) <= set(content.missions),
                "Saved campaign references missing missions")
        # Story.initialize only modifies this disposable snapshot.
        StoryBook(project.story, content, project.campaigns).initialize(
            progress, campaign_id)
        source = "legacy_slot"
        sequence = None
    else:
        result = SessionStore(path).load_with_status(
            content, project, rules=rules)
        require(result.session.campaign_id == campaign_id,
                "Session checkpoint belongs to a different campaign")
        progress = result.session.progress
        verify_save(progress, project.campaign_flow)
        source = result.source
        sequence = result.sequence
    return {
        "path": str(path), "kind": kind, "campaign": campaign_id,
        "compatible": True, "source": source, "sequence": sequence,
        "completed": list(progress.completed), "ledger": list(progress.flow_ledger),
    }
