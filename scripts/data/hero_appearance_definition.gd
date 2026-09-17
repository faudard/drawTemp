@tool
class_name SporeHeroAppearanceDefinition
extends Resource

## V1.26 modular hero appearance authored by Sporebound Studio > Hero Creator Expressions & Profiles.
## Data-only resource. SporeHeroCompositor bakes it to the standard 4-direction
## spritesheet consumed by the existing battle runtime.

@export_group("Identity")
@export var hero_id: String = "momo"
@export var display_name: String = "Momo personnalisé"
@export var target_visual_id: String = "momo"
@export_enum("masculine", "feminine", "neutral", "creature") var presentation_style: String = "neutral"
@export_enum("adventurer", "mage", "warrior", "rogue", "funky", "ancient", "mechanical") var archetype_style: String = "adventurer"

@export_group("Morphology")
@export_enum("small", "medium", "large") var size_preset: String = "medium"
@export_range(0.70, 1.35, 0.05) var global_scale: float = 1.0
@export_range(0.65, 1.45, 0.05) var body_width_scale: float = 1.0
@export_range(0.70, 1.35, 0.05) var body_height_scale: float = 1.0
@export_range(0.70, 1.45, 0.05) var head_scale: float = 1.0
@export_range(0.65, 1.55, 0.05) var head_width_scale: float = 1.0
@export_enum("balanced", "chibi", "colossus", "slender", "big_spore", "tank") var silhouette_preset: String = "balanced"
@export var proportions_locked: bool = false

@export_group("Fine placement")
@export var body_offset: Vector2 = Vector2.ZERO
@export var head_offset: Vector2 = Vector2.ZERO
@export var face_offset: Vector2 = Vector2.ZERO
@export var accessory_offset: Vector2 = Vector2.ZERO
@export var weapon_offset: Vector2 = Vector2.ZERO

@export_group("Direct edit transforms")
@export_range(0.50, 1.75, 0.05) var body_transform_scale: float = 1.0
@export_range(-20.0, 20.0, 0.5) var body_rotation_degrees: float = 0.0
@export var body_locked: bool = false
@export_range(0.50, 1.75, 0.05) var head_transform_scale: float = 1.0
@export_range(-20.0, 20.0, 0.5) var head_rotation_degrees: float = 0.0
@export var head_locked: bool = false
@export_range(0.50, 1.75, 0.05) var face_transform_scale: float = 1.0
@export_range(-20.0, 20.0, 0.5) var face_rotation_degrees: float = 0.0
@export var face_locked: bool = false
@export_range(0.50, 1.75, 0.05) var accessory_transform_scale: float = 1.0
@export_range(-20.0, 20.0, 0.5) var accessory_rotation_degrees: float = 0.0
@export var accessory_locked: bool = false
@export_range(0.50, 1.75, 0.05) var weapon_transform_scale: float = 1.0
@export_range(-20.0, 20.0, 0.5) var weapon_rotation_degrees: float = 0.0
@export var weapon_locked: bool = false

@export_group("Parts — silhouette")
@export var body_style: String = "classic"
@export var head_shape_style: String = "round"
@export var head_pattern_style: String = "spots"
@export var ears_style: String = "none"
@export var horns_style: String = "none"
@export var hair_style: String = "tuft"

@export_group("Parts — face details")
@export var eyes_style: String = "friendly"
@export var iris_style: String = "round"
@export var pupil_style: String = "round"
@export var brows_style: String = "soft"
@export var nose_style: String = "button"
@export var mouth_style: String = "smile"
@export var teeth_style: String = "none"
@export var facial_hair_style: String = "none"
@export var skin_spots_style: String = "none"
@export var mark_style: String = "none"
@export var mark_2_style: String = "none"
@export var mark_3_style: String = "none"
@export var earrings_style: String = "none"

@export_group("Parts — equipment")
@export var jewelry_style: String = "none"
@export var top_style: String = "vest"
@export var bottom_style: String = "shorts"
@export var accessory_style: String = "none"
@export var accessory_2_style: String = "none"
@export var accessory_3_style: String = "none"
@export var weapon_style: String = "sword"

@export_group("Asymmetry / directional overrides")
@export var asymmetry_enabled: bool = false
@export var left_hair_style: String = ""
@export var right_hair_style: String = ""
@export var left_ears_style: String = ""
@export var right_ears_style: String = ""
@export var left_horns_style: String = ""
@export var right_horns_style: String = ""
@export var left_earrings_style: String = ""
@export var right_earrings_style: String = ""
@export var left_accessory_style: String = ""
@export var right_accessory_style: String = ""
@export var left_accessory_2_style: String = ""
@export var right_accessory_2_style: String = ""
@export var left_accessory_3_style: String = ""
@export var right_accessory_3_style: String = ""
@export var left_weapon_style: String = ""
@export var right_weapon_style: String = ""

@export_group("Expressions / animation states")
@export var expressions_enabled: bool = true
@export_enum("base", "cheerful", "focused", "angry", "mystic", "hurt", "ko", "heroic", "mischief") var idle_expression: String = "heroic"
@export_enum("base", "cheerful", "focused", "angry", "mystic", "hurt", "ko", "heroic", "mischief") var move_expression: String = "focused"
@export_enum("base", "cheerful", "focused", "angry", "mystic", "hurt", "ko", "heroic", "mischief") var attack_expression: String = "angry"
@export_enum("base", "cheerful", "focused", "angry", "mystic", "hurt", "ko", "heroic", "mischief") var cast_expression: String = "mystic"
@export_enum("base", "cheerful", "focused", "angry", "mystic", "hurt", "ko", "heroic", "mischief") var hit_expression: String = "hurt"
@export_enum("base", "cheerful", "focused", "angry", "mystic", "hurt", "ko", "heroic", "mischief") var ko_expression: String = "ko"
@export_enum("base", "cheerful", "focused", "angry", "mystic", "hurt", "ko", "heroic", "mischief") var portrait_expression: String = "heroic"
@export_enum("front", "right", "back", "left") var portrait_direction: String = "front"
@export_range(0.80, 1.60, 0.05) var portrait_zoom: float = 1.10
@export var portrait_offset: Vector2 = Vector2(0.0, 6.0)

@export_group("Palette — silhouette")
@export var skin_color: Color = Color("#f3e5c0")
@export var head_primary_color: Color = Color("#f27a72")
@export var head_secondary_color: Color = Color("#ffd166")
@export var ears_color: Color = Color("#f3e5c0")
@export var horns_color: Color = Color("#d6c6a5")
@export var hair_color: Color = Color("#4b2f28")

@export_group("Palette — face details")
@export var eyes_color: Color = Color("#f4f7ff")
@export var iris_color: Color = Color("#60a5fa")
@export var pupil_color: Color = Color("#17111f")
@export var brows_color: Color = Color("#3f2b2a")
@export var nose_color: Color = Color("#d99d8f")
@export var mouth_color: Color = Color("#251c32")
@export var teeth_color: Color = Color("#fff8e7")
@export var facial_hair_color: Color = Color("#6b4f3a")
@export var skin_spots_color: Color = Color("#c98379")
@export var mark_color: Color = Color("#8b2635")
@export var mark_2_color: Color = Color("#8b2635")
@export var mark_3_color: Color = Color("#8b2635")
@export var earrings_color: Color = Color("#fbbf24")

@export_group("Palette — equipment")
@export var jewelry_color: Color = Color("#fbbf24")
@export var top_color: Color = Color("#45a3c7")
@export var bottom_color: Color = Color("#44506b")
@export var accessory_color: Color = Color("#ffd166")
@export var accessory_2_color: Color = Color("#86efac")
@export var accessory_3_color: Color = Color("#f0abfc")
@export var weapon_color: Color = Color("#c7d4df")
@export var outline_color: Color = Color("#251c32")
@export var global_tint: Color = Color.WHITE

@export_group("Output")
@export_file("*.png") var generated_sprite_sheet_path: String = "res://assets/generated/heroes/momo_custom.png"
@export_file("*.png") var generated_portrait_path: String = "res://assets/generated/heroes/momo_custom_portrait.png"
@export_range(0.1, 2.0, 0.05) var sprite_scale: float = 0.5
@export var sprite_offset: Vector2 = Vector2.ZERO

@export_group("Legacy V1.19 compatibility")
@export var cap_style: String = "classic"
@export var face_style: String = "friendly"
@export var cap_color: Color = Color("#f27a72")
@export var legacy_migrated: bool = false


func part_id(category: String) -> String:
	match category:
		"body": return body_style
		"head_shape": return head_shape_style
		"head_pattern": return head_pattern_style
		"ears": return ears_style
		"horns": return horns_style
		"hair": return hair_style
		"eyes": return eyes_style
		"iris": return iris_style
		"pupil": return pupil_style
		"brows": return brows_style
		"nose": return nose_style
		"mouth": return mouth_style
		"teeth": return teeth_style
		"facial_hair": return facial_hair_style
		"skin_spots": return skin_spots_style
		"mark": return mark_style
		"mark_2": return mark_2_style
		"mark_3": return mark_3_style
		"earrings": return earrings_style
		"jewelry": return jewelry_style
		"top": return top_style
		"bottom": return bottom_style
		"accessory": return accessory_style
		"accessory_2": return accessory_2_style
		"accessory_3": return accessory_3_style
		"weapon": return weapon_style
		"cap": return cap_style
		"face": return face_style
		_: return ""


func directional_part_id(category: String, direction: String) -> String:
	var base: String = part_id(category)
	if not asymmetry_enabled or (direction != "left" and direction != "right"):
		return base
	var property_name: String = "%s_%s_style" % [direction, category]
	for info: Dictionary in get_property_list():
		if String(info.get("name", "")) != property_name:
			continue
		var override_value: String = String(get(property_name))
		return base if override_value.is_empty() else override_value
	return base


func part_color(category: String) -> Color:
	match category:
		"body": return skin_color
		"head_shape": return head_primary_color
		"head_pattern": return head_secondary_color
		"ears": return ears_color
		"horns": return horns_color
		"hair": return hair_color
		"eyes": return eyes_color
		"iris": return iris_color
		"pupil": return pupil_color
		"brows": return brows_color
		"nose": return nose_color
		"mouth": return mouth_color
		"teeth": return teeth_color
		"facial_hair": return facial_hair_color
		"skin_spots": return skin_spots_color
		"mark": return mark_color
		"mark_2": return mark_2_color
		"mark_3": return mark_3_color
		"earrings": return earrings_color
		"jewelry": return jewelry_color
		"top": return top_color
		"bottom": return bottom_color
		"accessory": return accessory_color
		"accessory_2": return accessory_2_color
		"accessory_3": return accessory_3_color
		"weapon": return weapon_color
		"cap": return cap_color
		"face": return outline_color
		_: return Color.WHITE


func expression_for_state(state: String) -> String:
	if not expressions_enabled:
		return "base"
	match state:
		"move": return move_expression
		"attack": return attack_expression
		"cast": return cast_expression
		"hit": return hit_expression
		"ko": return ko_expression
		"portrait": return portrait_expression
		_: return idle_expression


func expression_part_override(category: String, expression: String) -> String:
	## Empty string means "keep the authored base part". "none" explicitly hides it.
	match expression:
		"cheerful":
			match category:
				"eyes": return "cute"
				"brows": return "arched"
				"mouth": return "grin"
				_: return ""
		"focused":
			match category:
				"eyes": return "narrow"
				"brows": return "straight"
				"mouth": return "neutral"
				_: return ""
		"angry":
			match category:
				"eyes": return "angry"
				"brows": return "angry"
				"mouth": return "stern"
				_: return ""
		"mystic":
			match category:
				"eyes": return "big"
				"iris": return "glow"
				"pupil": return "diamond"
				"brows": return "arched"
				"mouth": return "neutral"
				_: return ""
		"hurt":
			match category:
				"eyes": return "sleepy"
				"brows": return "arched"
				"mouth": return "stern"
				_: return ""
		"ko":
			match category:
				"eyes": return "sleepy"
				"iris", "pupil": return "none"
				"brows": return "soft"
				"mouth": return "neutral"
				_: return ""
		"heroic":
			match category:
				"eyes": return "friendly"
				"brows": return "straight"
				"mouth": return "smile"
				_: return ""
		"mischief":
			match category:
				"eyes": return "narrow"
				"brows": return "arched"
				"mouth": return "grin"
				"teeth": return "single_fang"
				_: return ""
		_:
			return ""


func migrate_legacy_fields() -> void:
	if legacy_migrated:
		return
	if head_shape_style == "round" and cap_style != "classic":
		head_shape_style = legacy_cap_to_head_shape(cap_style)
	if eyes_style == "friendly" and face_style != "friendly":
		eyes_style = legacy_face_to_eyes(face_style)
	if head_primary_color == Color("#f27a72") and cap_color != Color("#f27a72"):
		head_primary_color = cap_color
	legacy_migrated = true


func legacy_cap_to_head_shape(value: String) -> String:
	match value:
		"flat": return "flat"
		"punk": return "pointed"
		"royal": return "noble"
		_: return "round"


func legacy_face_to_eyes(value: String) -> String:
	match value:
		"cyclops": return "cyclops"
		"determined": return "angry"
		"sleepy": return "sleepy"
		"masked": return "narrow"
		_: return "friendly"
