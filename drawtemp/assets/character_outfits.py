"""R7.C read-only costume selection from canonical campaign equipment.

Equip/unequip is owned by Campaign and saved in HeroProgress. This module
projects *existing* hero equipment and wounds onto authored visual variants;
it never modifies the simulation, inventory, Content, save slots or replay.
"""
from __future__ import annotations

from collections.abc import Mapping

from .characters import CharacterError


def outfit_from_progress(progress, equipment, actor_id, available):
    """Derive a visual costume from existing R8 item slots and hero injuries.

    Rules: wounds -> wounded; equipped armor -> armor;
    weapon training/equipment -> apprentice; early campaign -> peasant.
    No new save fields. Unknown/deleted equipment never unlocks armor art.
    A missing authored variant falls back predictably to peasant/first.
    """
    variants = tuple(available)
    if not variants:
        raise CharacterError("Character pack has no authored outfits")
    if len(set(variants)) != len(variants):
        raise CharacterError("Duplicate outfit variants")
    if not isinstance(progress, Mapping) or not isinstance(equipment, Mapping):
        raise CharacterError("Invalid campaign/equipment snapshot")
    heroes = progress.get("heroes", {})
    if not isinstance(heroes, Mapping):
        raise CharacterError("Invalid hero roster")
    hero = heroes.get(actor_id, {})
    if not isinstance(hero, Mapping):
        raise CharacterError("Invalid hero progress")
    worn = hero.get("equipment", {})
    if not isinstance(worn, Mapping):
        raise CharacterError("Invalid equipped items")
    wounds = hero.get("wounds", ())
    if not isinstance(wounds, (list, tuple)):
        raise CharacterError("Invalid wounds")
    if wounds:
        desired = "wounded"
    elif any(isinstance(item, str)
             and item in equipment and isinstance(equipment[item], Mapping)
             and equipment[item].get("slot") == "armor"
             for slot, item in worn.items() if slot == "armor"):
        desired = "armor"
    elif (isinstance(worn.get("weapon"), str)
          and worn["weapon"] in equipment
          and isinstance(equipment[worn["weapon"]], Mapping)
          and equipment[worn["weapon"]].get("slot") == "weapon"):
        desired = "apprentice"
    else:
        desired = "peasant"
    return desired if desired in variants else (
        "peasant" if "peasant" in variants else variants[0])
