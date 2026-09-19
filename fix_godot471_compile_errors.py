#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix the Godot 4.7.1 parse errors reported after the recent Sporebound push.

Run from the repository root:
    python fix_godot471_compile_errors.py

The script is intentionally conservative on current runtime/editor code and more
permissive on old main_v0x prototype scripts, which Godot still parses globally.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()

REQUIRED = [
    ROOT / "scripts/prototypes/spore_battle_board_3d.gd",
    ROOT / "addons/sporebound_studio/campaign_canvas.gd",
    ROOT / "addons/sporebound_studio/map_canvas.gd",
    ROOT / "addons/sporebound_studio/studio_dock.gd",
    ROOT / "scripts/catalogs/loadout_ability_catalog.gd",
]

missing = [p for p in REQUIRED if not p.exists()]
if missing:
    print("[ERROR] Run this script from the drawTemp repository root.")
    for p in missing:
        print("  missing:", p.relative_to(ROOT) if p.is_absolute() else p)
    sys.exit(1)


def backup(path: Path) -> None:
    dst = path.with_suffix(path.suffix + ".godot471_compile_backup")
    if path.exists() and not dst.exists():
        dst.write_bytes(path.read_bytes())


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_checked(text: str, old: str, new: str, label: str, required: bool = False) -> str:
    if new in text:
        return text
    if old not in text:
        if required:
            raise RuntimeError(f"Anchor not found: {label}")
        print(f"[SKIP] {label} (already different or already fixed)")
        return text
    print(f"[FIX]  {label}")
    return text.replace(old, new, 1)


def remove_duplicate_top_level_function(text: str, name: str) -> tuple[str, int]:
    pattern = re.compile(
        rf"(?ms)^func {re.escape(name)}\([^\n]*\)(?: -> [^:\n]+)?:\n.*?(?=^func |\Z)"
    )
    matches = list(pattern.finditer(text))
    if len(matches) <= 1:
        return text, 0

    # Keep the first declaration. Remove later duplicates from back to front.
    removed = 0
    for m in reversed(matches[1:]):
        text = text[:m.start()] + text[m.end():]
        removed += 1
    return text, removed


# -----------------------------------------------------------------------------
# 1) Current 3D board: duplicate result function
# -----------------------------------------------------------------------------
board_path = ROOT / "scripts/prototypes/spore_battle_board_3d.gd"
backup(board_path)
board = read(board_path)
board, removed = remove_duplicate_top_level_function(board, "_show_battle_result")
if removed:
    print(f"[FIX]  spore_battle_board_3d.gd: removed {removed} duplicate _show_battle_result()")
write(board_path, board)


# -----------------------------------------------------------------------------
# 2) campaign_canvas.gd: Variant inference made strict by 4.7
# -----------------------------------------------------------------------------
path = ROOT / "addons/sporebound_studio/campaign_canvas.gd"
backup(path)
text = read(path)
repls = [
    ("\t\tvar hit := _node_at(event.position)", "\t\tvar hit: String = _node_at(event.position)", "campaign hover hit"),
    ("\t\t\tvar node := campaign.node_by_id(dragging_node_id)", "\t\t\tvar node: Resource = campaign.node_by_id(dragging_node_id) as Resource", "campaign dragging node"),
    ("\t\t\tvar hit := _node_at(event.position)", "\t\t\tvar hit: String = _node_at(event.position)", "campaign click hit"),
    ("\t\t\t\tvar node := campaign.node_by_id(hit)", "\t\t\t\tvar node: Resource = campaign.node_by_id(hit) as Resource", "campaign selected node"),
    ("\t\t\t\tvar index := campaign.nodes.find(node)", "\t\t\t\tvar index: int = campaign.nodes.find(node)", "campaign selected index"),
    ("\t\tvar from_rect := _node_rect(node, index)", "\t\tvar from_rect: Rect2 = _node_rect(node, index)", "campaign source rect"),
    ("\t\t\tvar target := campaign.node_by_id(target_id)", "\t\t\tvar target: Resource = campaign.node_by_id(String(target_id)) as Resource", "campaign edge target"),
    ("\t\t\tvar target_index := campaign.nodes.find(target)", "\t\t\tvar target_index: int = campaign.nodes.find(target)", "campaign edge target index"),
    ("\t\t\tvar to_rect := _node_rect(target, target_index)", "\t\t\tvar to_rect: Rect2 = _node_rect(target, target_index)", "campaign target rect"),
    ("\t\t\tvar from_point := Vector2(from_rect.end.x, from_rect.get_center().y)", "\t\t\tvar from_point: Vector2 = Vector2(from_rect.end.x, from_rect.get_center().y)", "campaign source point"),
    ("\t\t\tvar to_point := Vector2(to_rect.position.x, to_rect.get_center().y)", "\t\t\tvar to_point: Vector2 = Vector2(to_rect.position.x, to_rect.get_center().y)", "campaign target point"),
    ("\t\t\tvar direction := (to_point - from_point).normalized()", "\t\t\tvar direction: Vector2 = (to_point - from_point).normalized()", "campaign edge direction"),
    ("\t\t\t\tvar normal := Vector2(-direction.y, direction.x)", "\t\t\t\tvar normal: Vector2 = Vector2(-direction.y, direction.x)", "campaign edge normal"),
]
for old, new, label in repls:
    text = replace_checked(text, old, new, label)
write(path, text)


# -----------------------------------------------------------------------------
# 3) map_canvas.gd: actual indentation/scope bug
# -----------------------------------------------------------------------------
path = ROOT / "addons/sporebound_studio/map_canvas.gd"
backup(path)
text = read(path)
broken = '''\tfor cell in overlay_cells:
\t\tif is_cell_valid(cell):
\t\t\tvar overlay_rect := Rect2(board_origin + Vector2(cell) * cell_size, Vector2(cell_size, cell_size))
\t\t\tdraw_rect(overlay_rect.grow(-2.0), overlay_color, true)
\t\t\tvar overlay_edge := overlay_color
\t\toverlay_edge.a = 0.92
\t\tdraw_rect(overlay_rect.grow(-2.0), overlay_edge, false, 2.0)
'''
fixed = '''\tfor cell_value: Variant in overlay_cells:
\t\tif cell_value is Vector2i and is_cell_valid(cell_value):
\t\t\tvar cell: Vector2i = cell_value
\t\t\tvar overlay_rect: Rect2 = Rect2(board_origin + Vector2(cell) * cell_size, Vector2(cell_size, cell_size))
\t\t\tdraw_rect(overlay_rect.grow(-2.0), overlay_color, true)
\t\t\tvar overlay_edge: Color = overlay_color
\t\t\toverlay_edge.a = 0.92
\t\t\tdraw_rect(overlay_rect.grow(-2.0), overlay_edge, false, 2.0)
'''
text = replace_checked(text, broken, fixed, "map overlay scope/indentation", required=True)
write(path, text)


# -----------------------------------------------------------------------------
# 4) studio_dock.gd: specific strict inference failures
# -----------------------------------------------------------------------------
path = ROOT / "addons/sporebound_studio/studio_dock.gd"
backup(path)
text = read(path)
repls = [
    ("\tvar count := mission_current.enemy_positions.size()", "\tvar count: int = mission_current.enemy_positions.size()", "studio spawn count"),
    ("\tvar index := skill_current.effects.size() - 1", "\tvar index: int = skill_current.effects.size() - 1", "studio effect index"),
    ("\tvar node := campaign_current.node_by_id(node_id)", "\tvar node: Resource = campaign_current.node_by_id(node_id) as Resource", "studio campaign selected node"),
    ("\t\tvar current_id := queue.pop_front()", "\t\tvar current_id: String = String(queue.pop_front())", "studio graph queue id"),
    ("\t\tvar current := campaign_current.node_by_id(current_id)", "\t\tvar current: Resource = campaign_current.node_by_id(current_id) as Resource", "studio graph current node"),
    ("\tvar new_index := logic_mission_current.battle_triggers.size() - 1", "\tvar new_index: int = logic_mission_current.battle_triggers.size() - 1", "studio trigger new index"),
]
for old, new, label in repls:
    text = replace_checked(text, old, new, label)
write(path, text)


# -----------------------------------------------------------------------------
# 5) Missing loadout ability definition class
# -----------------------------------------------------------------------------
def_path = ROOT / "scripts/data/loadout_ability_definition.gd"
if not def_path.exists():
    print("[FIX]  creating scripts/data/loadout_ability_definition.gd")
    write(def_path, '''class_name SporeLoadoutAbilityDefinition
extends Resource

@export_group("Identity")
@export var id: String = ""
@export var display_name: String = "Ability"
@export_multiline var description: String = ""
@export_enum("reaction", "support", "movement") var slot: String = "support"

@export_group("Unlock")
@export var unlock_job_id: String = ""
@export_range(1, 99, 1) var required_job_level: int = 1

@export_group("Reaction")
@export var reaction_type: String = "none"
@export_range(1, 8, 1) var reaction_range: int = 1
@export_range(0, 20, 1) var reaction_damage_bonus: int = 0

@export_group("Support bonuses")
@export var hp_bonus: int = 0
@export var attack_bonus: int = 0
@export var initiative_bonus: int = 0
@export var accuracy_bonus: int = 0
@export var evasion_bonus: int = 0
@export var focus_bonus: int = 0
@export var focus_regen_bonus: int = 0
@export var end_ct_bonus: int = 0
@export var revive_hp_bonus: int = 0

@export_group("Movement bonuses")
@export var movement_bonus: int = 0
@export var jump_up_bonus: int = 0
@export var jump_down_bonus: int = 0
@export var ignore_opportunity: bool = false
''')
else:
    backup(def_path)

# Make catalog explicitly preload the type as well; global class discovery then has
# both a source file and an explicit dependency.
path = ROOT / "scripts/catalogs/loadout_ability_catalog.gd"
backup(path)
text = read(path)
if 'loadout_ability_definition.gd' not in text:
    text = text.replace(
        'const JobCatalog = preload("res://scripts/catalogs/job_catalog.gd")\n',
        'const JobCatalog = preload("res://scripts/catalogs/job_catalog.gd")\nconst LoadoutAbilityDefinition = preload("res://scripts/data/loadout_ability_definition.gd")\n',
        1,
    )
# Avoid depending on global-class scan order in annotations/casts.
text = text.replace('static func definition(id: String) -> SporeLoadoutAbilityDefinition:', 'static func definition(id: String) -> LoadoutAbilityDefinition:')
text = text.replace('(load(path) as SporeLoadoutAbilityDefinition)', '(load(path) as LoadoutAbilityDefinition)')
write(path, text)


# -----------------------------------------------------------------------------
# 6) Legacy 2D prototypes: remove strict local := inference.
# Godot parses them even though the current default game is the 3D mission.
# -----------------------------------------------------------------------------
legacy_files = [ROOT / "scripts/main.gd"] + sorted((ROOT / "scripts").glob("main_v*.gd"))
legacy_count = 0
legacy_re = re.compile(r'(?m)^(\s*)var ([A-Za-z_][A-Za-z0-9_]*) := ')
for path in legacy_files:
    if not path.exists():
        continue
    backup(path)
    text = read(path)
    new_text, count = legacy_re.subn(r'\1var \2 = ', text)
    if count:
        legacy_count += count
        print(f"[FIX]  {path.relative_to(ROOT)}: {count} legacy local := declarations made dynamic")
        write(path, new_text)
print(f"[INFO] legacy declarations adjusted: {legacy_count}")


# -----------------------------------------------------------------------------
# 7) Godot 4.7 test compatibility
# -----------------------------------------------------------------------------
# "Compositor" is now a native class name. Rename only the test constant/references.
for path in sorted((ROOT / "tests").glob("test_hero*.gd")):
    text = read(path)
    if re.search(r'\bCompositor\b', text):
        backup(path)
        new_text = re.sub(r'\bCompositor\b', 'HeroCompositor', text)
        if new_text != text:
            print(f"[FIX]  {path.relative_to(ROOT)}: Compositor -> HeroCompositor")
            write(path, new_text)

# PackedStringArray(...) constructor is not a constant expression in 4.7.
const_packed_re = re.compile(
    r'const\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*PackedStringArray)?\s*(?::=|=)\s*PackedStringArray\(\[\n(.*?)\n\]\)',
    re.S,
)
for path in sorted((ROOT / "tests").glob("*.gd")):
    text = read(path)
    new_text, count = const_packed_re.subn(lambda m: f'const {m.group(1)}: Array[String] = [\n{m.group(2)}\n]', text)
    if count:
        backup(path)
        print(f"[FIX]  {path.relative_to(ROOT)}: {count} PackedStringArray constant(s) -> Array[String]")
        write(path, new_text)


# -----------------------------------------------------------------------------
# 8) Sanity checks for the issues that caused the cascade
# -----------------------------------------------------------------------------
board = read(board_path)
show_result_count = len(re.findall(r'(?m)^func _show_battle_result\(', board))
if show_result_count != 1:
    raise RuntimeError(f"Expected one _show_battle_result(), found {show_result_count}")

map_canvas = read(ROOT / "addons/sporebound_studio/map_canvas.gd")
if '\t\toverlay_edge.a = 0.92' in map_canvas:
    raise RuntimeError("map_canvas overlay_edge is still outside the cell scope")

print()
print("[OK] Godot 4.7.1 compile-error pass applied.")
print("Backups use the suffix: .godot471_compile_backup")
print()
print("Next: reopen the project (or rescan scripts) and paste only the NEW remaining errors, if any.")
