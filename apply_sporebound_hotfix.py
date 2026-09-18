#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Sporebound compile hotfix
#
# Usage:
#   python apply_sporebound_hotfix.py <racine_du_projet>
#
# Exemple:
#   python apply_sporebound_hotfix.py E:\Project\drawTemp

import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")

    if new in text:
        print(f"[OK] {label}: déjà appliqué")
        return

    if old not in text:
        raise RuntimeError(
            f"{label}: bloc attendu introuvable dans {path}\n"
            "Le fichier a probablement changé depuis la création du correctif."
        )

    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[PATCH] {label}")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python apply_sporebound_hotfix.py <racine_du_projet>")
        return 2

    root = Path(sys.argv[1]).expanduser().resolve()

    battle = root / "scripts" / "controllers" / "battle_controller.gd"
    skill_def = root / "scripts" / "data" / "skill_definition.gd"
    skill_catalog = root / "scripts" / "catalogs" / "skill_catalog.gd"

    missing = [p for p in (battle, skill_def, skill_catalog) if not p.is_file()]
    if missing:
        print("[ERREUR] Fichier(s) introuvable(s):")
        for p in missing:
            print(f"  - {p}")
        return 1

    print(f"Projet : {root}")

    old_make_hero = '''\
\t\tString(campaign.hero_jobs.get(hero_id, UnitCatalog.default_job(hero_id))),
\t\tcampaign.hero_job_xp.get(hero_id, {}),
\t\tcampaign.hero_equipment_slots.get(hero_id, {}),
\t\tcampaign.job_nodes(hero_id, String(campaign.hero_jobs.get(hero_id, UnitCatalog.default_job(hero_id)))),
\t\tcampaign.loadout_for(hero_id),
\t\tcampaign.hero_job_nodes.get(hero_id, {})
\t)
'''

    new_make_hero = '''\
\t\tString(campaign.hero_jobs.get(hero_id, UnitCatalog.default_job(hero_id))),
\t\tcampaign.hero_job_xp.get(hero_id, {}),
\t\tcampaign.hero_equipment_slots.get(hero_id, {}),
\t\tcampaign.job_nodes(hero_id, String(campaign.hero_jobs.get(hero_id, UnitCatalog.default_job(hero_id))))
\t)
'''

    replace_once(
        battle,
        old_make_hero,
        new_make_hero,
        "battle_controller.gd / make_hero() 9 -> 7 arguments",
    )

    old_cast_types = '''\
\t\tvar primary_cast := SkillCatalog.cast_time_ticks(primary_id)
\t\tvar secondary_cast := SkillCatalog.cast_time_ticks(secondary_id)
'''

    new_cast_types = '''\
\t\tvar primary_cast: int = SkillCatalog.cast_time_ticks(primary_id)
\t\tvar secondary_cast: int = SkillCatalog.cast_time_ticks(secondary_id)
'''

    replace_once(
        battle,
        old_cast_types,
        new_cast_types,
        "battle_controller.gd / cast_time type inference",
    )

    old_skill_definition = '''\
@export_group("Effects")
@export var effects: Array[Resource] = []
@export var effect_tags: PackedStringArray = PackedStringArray()

@export_group("Presentation")
'''

    new_skill_definition = '''\
@export_group("Effects")
@export var effects: Array[Resource] = []
@export var effect_tags: PackedStringArray = PackedStringArray()

@export_group("Tactical Resolution")
## Existing skills preserve their previous guaranteed-hit behavior unless enabled explicitly.
@export var uses_accuracy: bool = false
@export_range(5, 100, 1) var accuracy: int = 100
@export_range(0, 20, 1) var cast_time_ticks: int = 0
@export var interrupt_on_damage: bool = true

@export_group("Presentation")
'''

    replace_once(
        skill_def,
        old_skill_definition,
        new_skill_definition,
        "skill_definition.gd / tactical skill properties",
    )

    old_skill_catalog = '''\
static func has_effects(skill_id: String) -> bool:
\treturn not effects(skill_id).is_empty()


static func cooldown_left(unit: Dictionary, skill_id: String) -> int:
'''

    new_skill_catalog = '''\
static func has_effects(skill_id: String) -> bool:
\treturn not effects(skill_id).is_empty()


static func has_tag(skill_id: String, tag: String) -> bool:
\tvar data := definition(skill_id)
\tif data == null or tag.is_empty():
\t\treturn false
\treturn data.effect_tags.has(tag)


static func uses_accuracy(skill_id: String) -> bool:
\tvar data := definition(skill_id)
\treturn bool(data.uses_accuracy) if data != null else false


static func accuracy(skill_id: String) -> int:
\tvar data := definition(skill_id)
\tif data == null:
\t\treturn 100
\treturn clampi(int(data.accuracy), 5, 100)


static func cast_time_ticks(skill_id: String) -> int:
\tvar data := definition(skill_id)
\treturn maxi(0, int(data.cast_time_ticks)) if data != null else 0


static func interrupt_on_damage(skill_id: String) -> bool:
\tvar data := definition(skill_id)
\treturn bool(data.interrupt_on_damage) if data != null else true


static func cooldown_left(unit: Dictionary, skill_id: String) -> int:
'''

    replace_once(
        skill_catalog,
        old_skill_catalog,
        new_skill_catalog,
        "skill_catalog.gd / missing static API",
    )

    print()
    print("[TERMINE] Correctif appliqué.")
    print("Relance Godot pour reparcourir/reparser les scripts.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print()
        print(f"[ERREUR] {exc}")
        raise SystemExit(1)
