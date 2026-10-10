"""Tactical RPG 3.0 opt-in bundle.

Usage:
    rules = tactical_rpg_rules()
    battle = Battle(content, "mission", rules=rules)
    replayed = Battle.replay(battle.recording(), rules=rules)

Unmodified default_rules() intentionally retains all legacy replay manifests.
"""
from __future__ import annotations


def tactical_rpg_rules(base=None):
    from .rules import default_rules
    from .rules.registry import BehaviorRule
    from .coordinated_ai import coordinated_command
    from .formations3 import install_formations
    from .synergies3 import install_synergies
    from .bosses3 import install_bosses, phase_boss_command

    rules = base if base is not None else default_rules()
    original_tactical = rules.behaviors.get("tactical").choose

    def tactical_with_roles(battle):
        actor = battle.active
        # Starting roles authored in the Studio opt in without changing the
        # stored legacy "tactical" behavior. Preserve custom patrol routes.
        if (actor is not None and not actor.patrol_route
                and any(tag in actor.tags for tag in ("medic", "healer", "protector"))):
            return coordinated_command(battle)
        return original_tactical(battle)

    rules = rules.with_family("behaviors", rules.behaviors.with_rule(
        "tactical", BehaviorRule(tactical_with_roles, version="2.7.1-role"),
        replace_existing=True))
    rules = rules.with_family("behaviors", rules.behaviors.with_rule(
        "coordinated", BehaviorRule(coordinated_command, version="2.7.1")))
    rules = rules.with_family("behaviors", rules.behaviors.with_rule(
        "phase_boss", BehaviorRule(phase_boss_command, version="2.7.5")))
    rules = install_formations(rules)
    rules = install_synergies(rules)
    rules = install_bosses(rules)
    return rules
