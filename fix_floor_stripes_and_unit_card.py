#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()
MAP = ROOT / "maps" / "mission_1_map.tscn"
TILE = ROOT / "scripts" / "maps" / "spore_tactical_tile_3d.gd"
BOARD = ROOT / "scripts" / "prototypes" / "spore_battle_board_3d.gd"

for path in (MAP, TILE, BOARD):
    if not path.exists():
        print(f"[ERROR] Missing: {path}")
        print("Run this script from the repository root.")
        sys.exit(1)


def backup(path: Path) -> None:
    dest = path.with_suffix(path.suffix + ".clean_floor_ui_backup")
    if not dest.exists():
        dest.write_bytes(path.read_bytes())


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


for p in (MAP, TILE, BOARD):
    backup(p)

# -----------------------------------------------------------------------------
# 1) Mission 1: aggressively remove all old visual overlay layers which can
#    create stripes/z-fighting/overdraw. Keep authored Tiles + Dressing + base.
# -----------------------------------------------------------------------------
map_text = MAP.read_text(encoding="utf-8")

bad_scene_paths = [
    "res://scenes/environment/mission1_tile_material_field_3d.tscn",
    "res://scenes/environment/mission1_painterly_polish_3d.tscn",
    "res://scenes/environment/mission1_backdrop_pretty_3d.tscn",
    "res://scenes/environment/mission1_stage_lighting_pretty_3d.tscn",
    "res://scenes/environment/mission1_hero_art_polish_3d.tscn",
]

for scene_path in bad_scene_paths:
    # Remove the ext_resource declaration containing this exact path.
    map_text = re.sub(
        rf'^\[ext_resource[^\n]*path="{re.escape(scene_path)}"[^\n]*\]\n?',
        '',
        map_text,
        flags=re.MULTILINE,
    )

bad_nodes = {
    "TileMaterialField",
    "PainterlyPolish",
    "StageBackdrop",
    "StageLighting",
    "HeroArtPolish",
}

# These are instance-only node sections, so deleting their single header is enough.
for node_name in bad_nodes:
    map_text = re.sub(
        rf'^\[node name="{re.escape(node_name)}"[^\n]*\]\n(?:\n)?',
        '',
        map_text,
        flags=re.MULTILINE,
    )

# Clean excessive blank lines left by previous patch stacks.
map_text = re.sub(r'\n{4,}', '\n\n', map_text)
write(MAP, map_text)

# -----------------------------------------------------------------------------
# 2) Real tile material only. No procedural ground-detail stripes or per-cell
#    decoration at runtime. A StandardMaterial3D keeps this cheap and stable.
# -----------------------------------------------------------------------------
tile_text = TILE.read_text(encoding="utf-8")

# Make procedural per-cell ground detail an editor-only aid.
start = tile_text.find("func _rebuild_ground_detail(map: SporeMap3D) -> void:")
end = tile_text.find("\n\nfunc _rebuild_terrain_prop", start)
if start >= 0 and end > start:
    replacement = '''func _rebuild_ground_detail(map: SporeMap3D) -> void:\n\tvar root: Node3D = get_node_or_null("_EditorGroundDetail") as Node3D\n\tif root == null:\n\t\troot = Node3D.new()\n\t\troot.name = "_EditorGroundDetail"\n\t\tadd_child(root, false, Node.INTERNAL_MODE_BACK)\n\n\t# Runtime stays clean: no per-cell moss/mushroom geometry.\n\tif not Engine.is_editor_hint():\n\t\troot.visible = false\n\t\treturn\n\n\troot.visible = false\n'''
    tile_text = tile_text[:start] + replacement + tile_text[end:]

# Replace material function with a simple opaque material. This also removes any
# ShaderMaterial implementation that may have been introduced by older local patches.
start = tile_text.find("func _material(color: Color) -> StandardMaterial3D:")
end = tile_text.find("\n\nfunc _top_color()", start)
if start >= 0 and end > start:
    replacement = '''func _material(color: Color) -> StandardMaterial3D:\n\tvar material: StandardMaterial3D = StandardMaterial3D.new()\n\tmaterial.albedo_color = color\n\tmaterial.metallic = 0.0\n\tmaterial.roughness = 0.96\n\n\t# Only gameplay landmarks get a very restrained emissive cue.\n\tif terrain_type in ["hazard", "bonus", "crown", "extraction"]:\n\t\tmaterial.emission_enabled = true\n\t\tmaterial.emission = color.darkened(0.30)\n\t\tmaterial.emission_energy_multiplier = 0.08 if terrain_type != "crown" else 0.14\n\n\treturn material\n'''
    tile_text = tile_text[:start] + replacement + tile_text[end:]

# Calm the base palette: less fluorescent green, still readable tactically.
start = tile_text.find("func _top_color() -> Color:")
end = tile_text.find("\n\nfunc _side_color()", start)
if start >= 0 and end > start:
    replacement = '''func _top_color() -> Color:\n\tmatch terrain_type:\n\t\t"obstacle":\n\t\t\treturn Color("#57584f")\n\t\t"cover":\n\t\t\treturn Color("#6f5a3c")\n\t\t"hazard":\n\t\t\treturn Color("#684775")\n\t\t"extraction":\n\t\t\treturn Color("#356c59")\n\t\t"bonus":\n\t\t\treturn Color("#426b78")\n\t\t"crown":\n\t\t\treturn Color("#9a7938")\n\t\t_:\n\t\t\tvar elevation_light: float = minf(0.055, float(elevation) * 0.018)\n\t\t\tvar hash_value: int = absi(cell.x * 92821 + cell.y * 68917)\n\t\t\tvar variation: float = float(hash_value % 5) * 0.007 - 0.014\n\t\t\treturn Color(\n\t\t\t\t0.245 + elevation_light + variation,\n\t\t\t\t0.365 + elevation_light + variation,\n\t\t\t\t0.225 + elevation_light + variation * 0.5,\n\t\t\t\t1.0\n\t\t\t)\n'''
    tile_text = tile_text[:start] + replacement + tile_text[end:]

write(TILE, tile_text)

# -----------------------------------------------------------------------------
# 3) Unit card: give HP / MP / stats proper vertical separation.
# -----------------------------------------------------------------------------
board_text = BOARD.read_text(encoding="utf-8")

replacements = {
    '\t_unit_card_panel.size = Vector2(360.0, 170.0)': '\t_unit_card_panel.size = Vector2(372.0, 192.0)',
    '\t_unit_portrait.position = Vector2(12.0, 12.0)': '\t_unit_portrait.position = Vector2(14.0, 14.0)',
    '\t_unit_portrait.size = Vector2(82.0, 104.0)': '\t_unit_portrait.size = Vector2(88.0, 112.0)',
    '\t_unit_card_title = _make_label(_unit_card_panel, Vector2(104.0, 10.0), Vector2(244.0, 25.0), 17, Color(1.0, 0.82, 0.40, 1.0))': '\t_unit_card_title = _make_label(_unit_card_panel, Vector2(114.0, 12.0), Vector2(244.0, 25.0), 17, Color(1.0, 0.82, 0.40, 1.0))',
    '\t_unit_hp_bar.position = Vector2(104.0, 39.0)': '\t_unit_hp_bar.position = Vector2(114.0, 42.0)',
    '\t_unit_hp_bar.size = Vector2(244.0, 15.0)': '\t_unit_hp_bar.size = Vector2(244.0, 16.0)',
    '\t_unit_focus_bar.position = Vector2(104.0, 58.0)': '\t_unit_focus_bar.position = Vector2(114.0, 64.0)',
    '\t_unit_focus_bar.size = Vector2(244.0, 12.0)': '\t_unit_focus_bar.size = Vector2(244.0, 16.0)',
    '\t_unit_card_body = _make_label(_unit_card_panel, Vector2(104.0, 76.0), Vector2(244.0, 82.0), 10, Color(0.92, 0.93, 0.88, 1.0))': '\t_unit_card_body = _make_label(_unit_card_panel, Vector2(114.0, 90.0), Vector2(244.0, 92.0), 10, Color(0.92, 0.93, 0.88, 1.0))',
}

for old, new in replacements.items():
    if old in board_text:
        board_text = board_text.replace(old, new, 1)
    else:
        print(f"[WARN] UI anchor not found: {old.strip()[:70]}")

# Make the card text slightly easier to read and avoid any accidental clipping.
needle = '\t_unit_card_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART\n'
if needle in board_text and '\t_unit_card_body.clip_contents = false\n' not in board_text:
    board_text = board_text.replace(
        needle,
        needle + '\t_unit_card_body.clip_contents = false\n\t_unit_card_body.vertical_alignment = VERTICAL_ALIGNMENT_TOP\n',
        1,
    )

write(BOARD, board_text)

# -----------------------------------------------------------------------------
# Sanity checks.
# -----------------------------------------------------------------------------
final_map = MAP.read_text(encoding="utf-8")
for bad in bad_scene_paths:
    if bad in final_map:
        print(f"[ERROR] Overlay still present: {bad}")
        sys.exit(2)

final_board = BOARD.read_text(encoding="utf-8")
if 'Vector2(114.0, 90.0)' not in final_board:
    print("[ERROR] Unit-card layout was not updated.")
    sys.exit(3)

print("[OK] Floor stripes / overlay cleanup + unit-card layout fixed.")
print()
print("Removed from Mission 1 runtime:")
for p in bad_scene_paths:
    print("  -", p)
print()
print("Tile rendering:")
print("  - real authored tiles only")
print("  - opaque StandardMaterial3D")
print("  - no runtime per-cell moss/mushroom detail")
print("  - calmer forest palette")
print()
print("Unit card:")
print("  - HP bar y=42")
print("  - MP bar y=64")
print("  - stats start y=90")
print("  - larger card / portrait margins")
print()
print("Backups use suffix: .clean_floor_ui_backup")
