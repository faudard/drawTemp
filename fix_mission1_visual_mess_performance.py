#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()
MAP = ROOT / "maps" / "mission_1_map.tscn"
TILE = ROOT / "scripts" / "maps" / "spore_tactical_tile_3d.gd"

for p in (MAP, TILE):
    if not p.exists():
        print(f"[ERROR] Missing: {p}")
        print("Run this script from the drawTemp repository root.")
        sys.exit(1)


def backup(path: Path) -> None:
    dst = path.with_suffix(path.suffix + ".visual_cleanup_backup")
    if not dst.exists():
        dst.write_bytes(path.read_bytes())


backup(MAP)
backup(TILE)

# -----------------------------------------------------------------------------
# 1) Remove the art layers that duplicate geometry / produce camera artifacts.
# -----------------------------------------------------------------------------
map_text = MAP.read_text(encoding="utf-8")

remove_scene_paths = {
    "res://scenes/environment/mission1_tile_material_field_3d.tscn",
    "res://scenes/environment/mission1_painterly_polish_3d.tscn",
    "res://scenes/environment/mission1_backdrop_pretty_3d.tscn",
    "res://scenes/environment/mission1_stage_lighting_pretty_3d.tscn",
    # This duplicates the shrine/DJ composition already present in Dressing.
    "res://scenes/environment/mission1_hero_art_polish_3d.tscn",
}
remove_nodes = {
    "TileMaterialField",
    "PainterlyPolish",
    "StageBackdrop",
    "StageLighting",
    "HeroArtPolish",
}

kept_lines: list[str] = []
for line in map_text.splitlines():
    if line.startswith("[ext_resource ") and any(path in line for path in remove_scene_paths):
        continue
    if line.startswith("[node "):
        match = re.search(r'name="([^"]+)"', line)
        if match and match.group(1) in remove_nodes:
            continue
    kept_lines.append(line)

# compact excessive blank lines created by previous patch stacking
map_text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines).strip() + "\n")
MAP.write_text(map_text, encoding="utf-8", newline="\n")

# -----------------------------------------------------------------------------
# 2) Rework the REAL tile materials instead of drawing a second board on top.
# -----------------------------------------------------------------------------
tile = TILE.read_text(encoding="utf-8")

# Use a procedural material on the actual tile body/top.
tile = tile.replace(
    "\tbody.material_override = _material(_side_color())",
    "\tbody.material_override = _surface_material(_side_color(), 0.022, 0.0)",
)
tile = tile.replace(
    "\ttop.material_override = _material(_top_color())",
    "\ttop.material_override = _surface_material(_top_color(), 0.050, _surface_emission())",
)

# The extra rim is another full mesh per tile and is visually redundant.
old_rim_end = "\trim.material_override = _material(_side_color().darkened(0.10))"
if old_rim_end in tile:
    tile = tile.replace(
        old_rim_end,
        old_rim_end + "\n\trim.visible = false",
        1,
    )

# Runtime micro-props on every few cells add many draw calls. Keep them as editor
# helpers only; the authored Dressing scene carries runtime decoration.
anchor = '''\tfor child: Node in root.get_children():
\t\tchild.free()

\tif terrain_type != "ground":'''
replacement = '''\tfor child: Node in root.get_children():
\t\tchild.free()

\t# PERF_CLEANUP: runtime decoration lives in Mission1Dressing.
\t# These tiny procedural mushrooms/moss remain useful only while authoring.
\tif not Engine.is_editor_hint():
\t\troot.visible = false
\t\treturn

\tif terrain_type != "ground":'''
if anchor in tile:
    tile = tile.replace(anchor, replacement, 1)

# Replace the neon-ish palette with a quieter earthy palette. Semantics remain
# readable, but gameplay cells no longer glow like a debug visualization.
start = tile.find("func _top_color() -> Color:")
end = tile.find("\n\nfunc _side_color() -> Color:", start)
if start != -1 and end != -1:
    new_top = '''func _top_color() -> Color:
\tmatch terrain_type:
\t\t"obstacle":
\t\t\treturn Color("#615f55")
\t\t"cover":
\t\t\treturn Color("#705a39")
\t\t"hazard":
\t\t\treturn Color("#65436f")
\t\t"extraction":
\t\t\treturn Color("#386b55")
\t\t"bonus":
\t\t\treturn Color("#41677a")
\t\t"crown":
\t\t\treturn Color("#806b38")
\t\t_:
\t\t\tvar elevation_light: float = minf(0.055, float(elevation) * 0.018)
\t\t\tvar hash_value: int = absi(cell.x * 92821 + cell.y * 68917)
\t\t\tvar variation: float = float(hash_value % 7) * 0.006 - 0.018
\t\t\treturn Color(
\t\t\t\t0.245 + elevation_light + variation,
\t\t\t\t0.385 + elevation_light + variation,
\t\t\t\t0.255 + elevation_light + variation * 0.45,
\t\t\t\t1.0
\t\t\t)'''
    tile = tile[:start] + new_top + tile[end:]

# Add one shared procedural shader for actual tile surfaces. No transparency,
# no extra mesh layer, no z-fighting. The pattern is intentionally subtle.
insert_before = "\n\nfunc _material(color: Color) -> StandardMaterial3D:"
if "func _surface_material(" not in tile and insert_before in tile:
    helper = r'''


static var _tile_surface_shader_cache: Shader = null


func _tile_surface_shader() -> Shader:
	if _tile_surface_shader_cache != null:
		return _tile_surface_shader_cache

	var shader: Shader = Shader.new()
	shader.code = """
shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

uniform vec4 base_color : source_color = vec4(0.3, 0.45, 0.3, 1.0);
uniform float variation = 0.04;
uniform float emission_strength = 0.0;

void fragment() {
	float broad = sin(UV.x * 8.0 + UV.y * 5.0) * 0.5 + 0.5;
	float fine = sin(UV.x * 31.0 - UV.y * 23.0) * 0.5 + 0.5;
	float grain = ((broad - 0.5) * 0.65 + (fine - 0.5) * 0.35) * variation;
	vec3 c = clamp(base_color.rgb * (1.0 + grain), vec3(0.0), vec3(1.0));
	ALBEDO = c;
	ROUGHNESS = 0.94;
	METALLIC = 0.0;
	EMISSION = c * emission_strength;
}
"""
	_tile_surface_shader_cache = shader
	return shader


func _surface_material(color: Color, variation: float, emission_strength: float) -> ShaderMaterial:
	var material: ShaderMaterial = ShaderMaterial.new()
	material.shader = _tile_surface_shader()
	material.set_shader_parameter("base_color", color)
	material.set_shader_parameter("variation", variation)
	material.set_shader_parameter("emission_strength", emission_strength)
	return material


func _surface_emission() -> float:
	match terrain_type:
		"hazard":
			return 0.055
		"extraction":
			return 0.045
		"bonus":
			return 0.035
		"crown":
			return 0.075
	return 0.0
'''
    tile = tile.replace(insert_before, helper + insert_before, 1)

TILE.write_text(tile, encoding="utf-8", newline="\n")

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
new_map = MAP.read_text(encoding="utf-8")
for node in remove_nodes:
    if f'name="{node}"' in new_map:
        print(f"[ERROR] Node cleanup failed: {node}")
        sys.exit(2)
for path in remove_scene_paths:
    if path in new_map:
        print(f"[ERROR] Resource cleanup failed: {path}")
        sys.exit(3)

new_tile = TILE.read_text(encoding="utf-8")
if "func _surface_material(" not in new_tile:
    print("[ERROR] Tile surface material patch was not installed.")
    sys.exit(4)

print("[OK] Mission 1 visual cleanup/performance patch applied.")
print()
print("Removed from the map:")
print("  - TileMaterialField (misaligned duplicate board, 1.0 spacing vs real 1.4)")
print("  - PainterlyPolish ground overlays")
print("  - StageBackdrop giant camera-facing/world plane")
print("  - StageLighting duplicate light rig")
print("  - HeroArtPolish duplicate shrine/DJ setpiece")
print()
print("Kept:")
print("  - the real authored tactical tiles")
print("  - Mission1Dressing")
print("  - StageDioramaBase")
print("  - gameplay landmarks and actors")
print()
print("Changed:")
print("  - terrain color/material is now applied directly to the real tiles")
print("  - subtle opaque procedural variation, no transparent ground layers")
print("  - runtime per-tile micro-props disabled")
print("  - per-tile rim mesh hidden")
print("  - semantic terrain colors toned down")
print()
print("No physical sky/backdrop is used by this cleanup.")
print("Backups: *.visual_cleanup_backup")
