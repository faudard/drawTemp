class_name SporeUnitActor3D
extends Node3D

const VisualCatalog = preload("res://scripts/catalogs/visual_catalog.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")
const StatusCatalog = preload("res://scripts/catalogs/status_catalog.gd")
const VfxCatalog = preload("res://scripts/catalogs/vfx_catalog.gd")
const CombatMechanics = preload("res://scripts/core/combat_mechanics.gd")

@export_group("Identity")
@export var unit_id: String = "momo"
@export var display_name: String = "Unit"
@export_enum("player", "enemy") var team: String = "player"
@export var cell: Vector2i = Vector2i.ZERO

@export_group("Combat")
@export var max_hp: int = 10
@export var hp: int = 10
@export var attack_power: int = 2
@export var magic_power: int = 1
@export var physical_defense: int = 0
@export var magic_defense: int = 0
@export var move_range: int = 4
@export var attack_range: int = 1
@export var attack_min_range: int = 1
@export var threat_min_range: int = 1
@export var threat_max_range: int = 1
@export var weapon_family: String = "unarmed"
@export var can_opportunity_attack: bool = true
@export var basic_attack_damage_type: String = "physical"
@export_range(0, 100, 1) var shield_block_chance: int = 0
@export_range(0, 8, 1) var shield_block_reduction: int = 0
@export var initiative: int = 5
@export var accuracy: int = 0
@export var evasion: int = 0
@export var max_focus: int = 2
@export var focus: int = 2
@export var primary_skill: String = ""
@export var secondary_skill: String = ""
@export var facing: Vector2i = Vector2i.DOWN
@export_enum("none", "counter", "opportunity", "intercept") var reaction_type: String = "none"
@export_range(1, 6, 1) var reaction_range: int = 1
@export_range(0, 6, 1) var reaction_damage_bonus: int = 0
@export var end_ct_bonus: int = 0
@export var basic_attack_damage_bonus: int = 0
@export var basic_attack_accuracy_bonus: int = 0
@export var flat_damage_reduction: int = 0
@export var focus_regen_bonus: int = 0
@export var revive_hp_bonus: int = 0
@export var jump_up_bonus: int = 0
@export var jump_down_bonus: int = 0
@export var ignore_opportunity: bool = false

@export_group("Visual")
@export var primary_color: Color = Color(0.95, 0.48, 0.45, 1.0)
@export var secondary_color: Color = Color(0.95, 0.90, 0.75, 1.0)
@export var accent_color: Color = Color(1.0, 0.82, 0.4, 1.0)
@export var outline_color: Color = Color(0.14, 0.11, 0.20, 1.0)
@export var visual_id: String = ""
@export var basic_attack_vfx_id: String = "default_hit"

var alive: bool = true
var moved_this_activation: bool = false
var acted_this_activation: bool = false
var cooldowns: Dictionary = {}
var statuses: Dictionary = {}
var reaction_ready: bool = false
var reaction_used_this_round: bool = false
var ct: int = 0
var casting: Dictionary = {}
var waited_this_activation: bool = false
var downed: bool = false
var downed_countdown: int = 0
var removed_from_battle: bool = false

var _sprite: Sprite3D
var _label: Label3D
var _shadow: MeshInstance3D
var _selection_disc: MeshInstance3D
var _turn_marker: MeshInstance3D
var _facing_marker: MeshInstance3D
var _vitals_sprite: Sprite3D
var _status_vfx_root: Node3D
var _status_vfx_nodes: Dictionary = {}
var _current_map: SporeMap3D = null
var _selected: bool = false
var _turn_active: bool = false
var _presentation_time: float = 0.0
var _presentation_locked: bool = false
var _idle_phase: float = 0.0
var _visual_definition: Resource = null
var _sprite_sheet_texture: Texture2D = null
var _sprite_frame_texture: AtlasTexture = null
var _uses_sprite_sheet: bool = false
var _animation_state: String = "idle"
var _animation_elapsed: float = 0.0
var _last_sprite_frame: Vector2i = Vector2i(-999, -999)
var _last_view_direction: String = "front"
var _sprite_art_scale: float = 1.0
var _sprite_art_offset: Vector2 = Vector2.ZERO


func _ready() -> void:
	_idle_phase = float((cell.x * 17 + cell.y * 31) % 19) * 0.27
	_ensure_visual_nodes()
	_refresh_visuals()


func _process(delta: float) -> void:
	_presentation_time += delta
	_animation_elapsed += delta
	if not alive and _animation_state != "ko":
		return
	_update_directional_sprite()
	_update_sprite_animation()
	if alive and _sprite != null and not _presentation_locked:
		var bob: float = sin(_presentation_time * 2.6 + _idle_phase) * 0.022
		var base_position: Vector3 = _sprite_base_position()
		_sprite.position = Vector3(base_position.x, base_position.y + bob, base_position.z)
		var breathe: float = 1.0 + sin(_presentation_time * 2.1 + _idle_phase) * 0.012
		_sprite.scale = Vector3(_sprite_art_scale * breathe, _sprite_art_scale * breathe, _sprite_art_scale)
	if _selection_disc != null and _selection_disc.visible:
		var selected_pulse: float = 1.0 + sin(_presentation_time * 5.2) * 0.07
		_selection_disc.scale = Vector3(selected_pulse, 1.0, selected_pulse)
	if _turn_marker != null and _turn_marker.visible:
		var turn_pulse: float = 1.0 + sin(_presentation_time * 4.0) * 0.09
		_turn_marker.scale = Vector3(turn_pulse, 1.0, turn_pulse)
	_update_status_vfx_animation()


func configure_from_unit_data(
	unit_data: Resource,
	cell_value: Vector2i,
	map: SporeMap3D,
	team_value: String = "player",
	overrides: Dictionary = {}
) -> void:
	if unit_data != null:
		unit_id = String(unit_data.get("id"))
		display_name = String(unit_data.get("display_name"))
		var raw_unit_color: Variant = unit_data.get("color")
		if raw_unit_color is Color:
			primary_color = raw_unit_color
		max_hp = int(unit_data.get("max_hp"))
		attack_power = int(unit_data.get("attack"))
		magic_power = int(unit_data.get("magic_power"))
		physical_defense = int(unit_data.get("physical_defense"))
		magic_defense = int(unit_data.get("magic_defense"))
		move_range = int(unit_data.get("movement"))
		attack_range = int(unit_data.get("attack_range"))
		attack_min_range = maxi(1, int(unit_data.get("attack_min_range")))
		threat_min_range = maxi(1, int(unit_data.get("threat_min_range")))
		threat_max_range = maxi(threat_min_range, int(unit_data.get("threat_max_range")))
		weapon_family = String(unit_data.get("weapon_family"))
		can_opportunity_attack = bool(unit_data.get("can_opportunity_attack"))
		basic_attack_damage_type = String(unit_data.get("basic_attack_damage_type"))
		initiative = int(unit_data.get("initiative"))
		accuracy = int(unit_data.get("accuracy"))
		evasion = int(unit_data.get("evasion"))
		max_focus = int(unit_data.get("max_focus"))
		primary_skill = String(unit_data.get("primary_skill"))
		secondary_skill = String(unit_data.get("secondary_skill"))
		reaction_type = String(unit_data.get("reaction_type"))
		reaction_range = maxi(1, int(unit_data.get("reaction_range")))
		reaction_damage_bonus = maxi(0, int(unit_data.get("reaction_damage_bonus")))
		visual_id = String(unit_data.get("visual_id"))
		var visual: Resource = VisualCatalog.definition(visual_id)
		_visual_definition = visual
		if visual != null:
			var raw_secondary: Variant = visual.get("secondary_color")
			var raw_accent: Variant = visual.get("accent_color")
			var raw_outline: Variant = visual.get("outline_color")
			var raw_primary: Variant = visual.get("primary_color")
			if raw_secondary is Color:
				secondary_color = raw_secondary
			if raw_accent is Color:
				accent_color = raw_accent
			if raw_outline is Color:
				outline_color = raw_outline
			if raw_primary is Color:
				primary_color = raw_primary
			basic_attack_vfx_id = String(visual.get("basic_attack_vfx_id"))
			_sprite_art_scale = maxf(0.1, float(visual.get("sprite_scale")))
			var raw_offset: Variant = visual.get("sprite_offset")
			if raw_offset is Vector2:
				_sprite_art_offset = raw_offset
	if int(overrides.get("hp", -1)) >= 0:
		max_hp = int(overrides.get("hp", max_hp))
	if int(overrides.get("attack", -1)) >= 0:
		attack_power = int(overrides.get("attack", attack_power))
	if overrides.has("magic_power"):
		magic_power = maxi(0, int(overrides.get("magic_power", magic_power)))
	if overrides.has("physical_defense"):
		physical_defense = maxi(0, int(overrides.get("physical_defense", physical_defense)))
	if overrides.has("magic_defense"):
		magic_defense = maxi(0, int(overrides.get("magic_defense", magic_defense)))
	if int(overrides.get("move", -1)) >= 0:
		move_range = int(overrides.get("move", move_range))
	if int(overrides.get("range", -1)) >= 0:
		attack_range = int(overrides.get("range", attack_range))
	attack_min_range = maxi(1, int(overrides.get("attack_min_range", attack_min_range)))
	threat_min_range = maxi(1, int(overrides.get("threat_min_range", threat_min_range)))
	threat_max_range = maxi(threat_min_range, int(overrides.get("threat_max_range", threat_max_range)))
	weapon_family = String(overrides.get("weapon_family", weapon_family))
	can_opportunity_attack = bool(overrides.get("can_opportunity_attack", can_opportunity_attack))
	basic_attack_damage_type = String(overrides.get("basic_attack_damage_type", basic_attack_damage_type))
	shield_block_chance = clampi(int(overrides.get("shield_block_chance", 0)), 0, 100)
	shield_block_reduction = maxi(0, int(overrides.get("shield_block_reduction", 0)))
	if overrides.has("initiative"):
		initiative = int(overrides.get("initiative", initiative))
	if overrides.has("accuracy"):
		accuracy = int(overrides.get("accuracy", accuracy))
	if overrides.has("evasion"):
		evasion = int(overrides.get("evasion", evasion))
	if overrides.has("max_focus"):
		max_focus = maxi(0, int(overrides.get("max_focus", max_focus)))
	if overrides.has("primary_skill"):
		primary_skill = String(overrides.get("primary_skill", primary_skill))
	if overrides.has("secondary_skill"):
		secondary_skill = String(overrides.get("secondary_skill", secondary_skill))
	if overrides.has("reaction_type"):
		reaction_type = String(overrides.get("reaction_type", reaction_type))
	if overrides.has("reaction_range"):
		reaction_range = maxi(1, int(overrides.get("reaction_range", reaction_range)))
	if overrides.has("reaction_damage_bonus"):
		reaction_damage_bonus = maxi(0, int(overrides.get("reaction_damage_bonus", reaction_damage_bonus)))
	end_ct_bonus = int(overrides.get("end_ct_bonus", 0))
	basic_attack_damage_bonus = int(overrides.get("basic_attack_damage_bonus", 0))
	basic_attack_accuracy_bonus = int(overrides.get("basic_attack_accuracy_bonus", 0))
	flat_damage_reduction = maxi(0, int(overrides.get("flat_damage_reduction", 0)))
	focus_regen_bonus = int(overrides.get("focus_regen_bonus", 0))
	revive_hp_bonus = int(overrides.get("revive_hp_bonus", 0))
	jump_up_bonus = maxi(0, int(overrides.get("jump_up_bonus", 0)))
	jump_down_bonus = maxi(0, int(overrides.get("jump_down_bonus", 0)))
	ignore_opportunity = bool(overrides.get("ignore_opportunity", false))
	team = team_value
	cell = cell_value
	_animation_state = "idle"
	_animation_elapsed = 0.0
	facing = Vector2i.DOWN if team == "player" else Vector2i.UP
	hp = max_hp
	focus = max_focus
	cooldowns.clear()
	statuses.clear()
	_sync_status_vfx()
	reaction_ready = false
	reaction_used_this_round = false
	ct = 0
	casting.clear()
	waited_this_activation = false
	downed = false
	downed_countdown = 0
	removed_from_battle = false
	alive = true
	_current_map = map
	_ensure_visual_nodes()
	_refresh_visuals()
	place_on_map(map, cell)


func begin_activation() -> void:
	moved_this_activation = false
	acted_this_activation = false
	waited_this_activation = false
	set_turn_active(true)


func effective_physical_power() -> int:
	return maxi(0, attack_power + status_modifier("attack_delta"))


func effective_magic_power() -> int:
	return maxi(0, magic_power + status_modifier("magic_power_delta"))


func effective_physical_defense() -> int:
	return maxi(0, physical_defense + status_modifier("physical_defense_delta"))


func effective_magic_defense() -> int:
	return maxi(0, magic_defense + status_modifier("magic_defense_delta"))


func effective_basic_attack_power() -> int:
	return effective_physical_power() if basic_attack_damage_type == "physical" else effective_magic_power()


func effective_defense_for_damage_type(damage_type: String) -> int:
	return effective_physical_defense() if damage_type == "physical" else effective_magic_defense()


func effective_speed() -> int:
	return CombatMechanics.speed_from_initiative(initiative + status_modifier("initiative_delta"))


func effective_accuracy() -> int:
	return accuracy + status_modifier("accuracy_delta")


func effective_evasion() -> int:
	return evasion + status_modifier("evasion_delta")


func is_casting() -> bool:
	return not casting.is_empty()


func interrupt_cast() -> String:
	if casting.is_empty() or not bool(casting.get("interrupt_on_damage", true)):
		return ""
	var skill_id: String = String(casting.get("skill_id", ""))
	casting.clear()
	_refresh_label()
	return skill_id


func refresh_mechanics_label() -> void:
	_refresh_label()


func end_activation() -> void:
	set_turn_active(false)


func reset_round_reaction() -> void:
	reaction_used_this_round = false


func reaction_available() -> bool:
	return alive and reaction_type != "none" and (not reaction_used_this_round or reaction_ready)


func consume_reaction() -> void:
	if reaction_used_this_round and reaction_ready:
		reaction_ready = false
	else:
		reaction_used_this_round = true
	_refresh_label()


func place_on_map(map: SporeMap3D, new_cell: Vector2i) -> void:
	_current_map = map
	cell = new_cell
	if map == null:
		return
	position = map.cell_top_local(cell) + Vector3(0.0, 0.16, 0.0)


func move_to_cell(map: SporeMap3D, new_cell: Vector2i, duration: float = 0.24) -> Tween:
	_current_map = map
	_set_animation_state("move")
	var old_cell: Vector2i = cell
	var tween: Tween = create_tween()
	if map == null:
		cell = new_cell
		_finish_move_animation()
		return tween
	var direction: Vector2i = new_cell - old_cell
	if direction != Vector2i.ZERO:
		set_facing(direction)
	var old_height: int = map.elevation_at(old_cell)
	var new_height: int = map.elevation_at(new_cell)
	var target: Vector3 = map.cell_top_local(new_cell) + Vector3(0.0, 0.16, 0.0)
	cell = new_cell
	tween.set_trans(Tween.TRANS_SINE)
	tween.set_ease(Tween.EASE_OUT)
	if old_height != new_height:
		var midpoint: Vector3 = (position + target) * 0.5
		midpoint.y = maxf(position.y, target.y) + 0.38 + float(absi(new_height - old_height)) * 0.08
		tween.tween_property(self, "position", midpoint, duration * 0.48)
		tween.tween_property(self, "position", target, duration * 0.52)
	else:
		tween.tween_property(self, "position", target, duration)
	tween.tween_callback(_finish_move_animation)
	return tween


func _finish_move_animation() -> void:
	if alive and _animation_state == "move":
		_set_animation_state("idle")


func set_facing(direction: Vector2i) -> void:
	if direction == Vector2i.ZERO:
		return
	if absi(direction.x) >= absi(direction.y):
		facing = Vector2i(1 if direction.x > 0 else -1, 0)
	else:
		facing = Vector2i(0, 1 if direction.y > 0 else -1)
	_update_facing_visual()


func face_cell(target_cell: Vector2i) -> void:
	set_facing(target_cell - cell)


func rotate_facing_quarter(turns: int = 1) -> void:
	var directions: Array[Vector2i] = [Vector2i.UP, Vector2i.RIGHT, Vector2i.DOWN, Vector2i.LEFT]
	var index: int = directions.find(facing)
	if index < 0:
		index = 2
	index = (index + turns) % directions.size()
	if index < 0:
		index += directions.size()
	facing = directions[index]
	_update_facing_visual()


func facing_name() -> String:
	match facing:
		Vector2i.UP:
			return "Nord"
		Vector2i.RIGHT:
			return "Est"
		Vector2i.DOWN:
			return "Sud"
		Vector2i.LEFT:
			return "Ouest"
	return "?"


func can_use_skill(skill_id: String) -> bool:
	if not alive or skill_id.is_empty():
		return false
	var skill: Resource = SkillCatalog.definition(skill_id)
	if skill == null:
		return false
	return focus >= int(skill.get("focus_cost")) and int(cooldowns.get(skill_id, 0)) <= 0 and not acted_this_activation


func spend_skill(skill_id: String) -> void:
	var skill: Resource = SkillCatalog.definition(skill_id)
	if skill == null:
		return
	focus = maxi(0, focus - int(skill.get("focus_cost")))
	cooldowns[skill_id] = int(skill.get("cooldown_rounds"))
	acted_this_activation = true
	_refresh_label()


func tick_skill_resources() -> void:
	focus = mini(max_focus, focus + maxi(0, 1 + focus_regen_bonus))
	for skill_key: Variant in cooldowns.keys():
		var skill_id: String = String(skill_key)
		cooldowns[skill_id] = maxi(0, int(cooldowns.get(skill_id, 0)) - 1)
	_refresh_label()


func skill_cooldown(skill_id: String) -> int:
	return int(cooldowns.get(skill_id, 0))


func heal(amount: int) -> int:
	if not alive:
		return 0
	var before: int = hp
	hp = mini(max_hp, hp + maxi(0, amount))
	_refresh_label()
	return hp - before


func change_focus(amount: int) -> int:
	var before: int = focus
	focus = clampi(focus + amount, 0, max_focus)
	_refresh_label()
	return focus - before


func apply_status(status_id: String, duration_override: int = -1, stacks_to_add: int = 1) -> bool:
	if status_id.is_empty() or not alive:
		return false
	var data: Resource = StatusCatalog.definition(status_id)
	if data == null:
		return false
	var duration: int = duration_override if duration_override >= 0 else int(data.get("duration_activations"))
	var max_stacks_value: int = maxi(1, int(data.get("max_stacks")))
	var stack_mode: String = String(data.get("stack_mode"))
	var state: Dictionary = {}
	var existing: Variant = statuses.get(status_id, {})
	if existing is Dictionary:
		state = (existing as Dictionary).duplicate(true)
	var stacks: int = clampi(stacks_to_add, 1, max_stacks_value)
	if not state.is_empty():
		var previous_stacks: int = int(state.get("stacks", 1))
		if stack_mode == "stack":
			stacks = mini(max_stacks_value, previous_stacks + maxi(1, stacks_to_add))
		elif stack_mode == "replace":
			stacks = clampi(stacks_to_add, 1, max_stacks_value)
		else:
			stacks = maxi(previous_stacks, clampi(stacks_to_add, 1, max_stacks_value))
	statuses[status_id] = {"remaining": duration, "stacks": stacks}
	_sync_status_vfx()
	_refresh_label()
	return true


func remove_status(status_id: String) -> void:
	statuses.erase(status_id)
	_sync_status_vfx()
	_refresh_label()


func status_modifier(property_name: String) -> int:
	var total: int = 0
	for status_key: Variant in statuses.keys():
		var status_id: String = String(status_key)
		var data: Resource = StatusCatalog.definition(status_id)
		if data == null:
			continue
		var state_value: Variant = statuses.get(status_id, {})
		var stacks: int = 1
		if state_value is Dictionary:
			stacks = maxi(1, int((state_value as Dictionary).get("stacks", 1)))
		var delta: int = 0
		match property_name:
			"attack_delta": delta = int(data.get("attack_delta"))
			"magic_power_delta": delta = int(data.get("magic_power_delta"))
			"physical_defense_delta": delta = int(data.get("physical_defense_delta"))
			"magic_defense_delta": delta = int(data.get("magic_defense_delta"))
			"movement_delta": delta = int(data.get("movement_delta"))
			"range_delta": delta = int(data.get("range_delta"))
			"initiative_delta": delta = int(data.get("initiative_delta"))
			"accuracy_delta": delta = int(data.get("accuracy_delta"))
			"evasion_delta": delta = int(data.get("evasion_delta"))
			"outgoing_damage_delta": delta = int(data.get("outgoing_damage_delta"))
			"incoming_damage_delta": delta = int(data.get("incoming_damage_delta"))
			_: delta = 0
		total += delta * stacks
	return total


func status_prevents_movement() -> bool:
	for status_key: Variant in statuses.keys():
		var data: Resource = StatusCatalog.definition(String(status_key))
		if data != null and bool(data.get("prevents_movement")):
			return true
	return false


func status_prevents_action() -> bool:
	for status_key: Variant in statuses.keys():
		var data: Resource = StatusCatalog.definition(String(status_key))
		if data != null and bool(data.get("prevents_action")):
			return true
	return false


func status_display_text() -> String:
	var labels: Array[String] = []
	for status_key: Variant in statuses.keys():
		var status_id: String = String(status_key)
		var data: Resource = StatusCatalog.definition(status_id)
		var label: String = String(data.get("display_name")) if data != null else status_id
		var state_value: Variant = statuses.get(status_id, {})
		if state_value is Dictionary:
			var state: Dictionary = state_value as Dictionary
			var stacks: int = int(state.get("stacks", 1))
			var remaining: int = int(state.get("remaining", 0))
			if stacks > 1:
				label += " x%d" % stacks
			if remaining > 0:
				label += "[%d]" % remaining
		labels.append(label)
	labels.sort()
	return ", ".join(labels)


func phase_status_events(phase: String) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for status_key: Variant in statuses.keys():
		var status_id: String = String(status_key)
		var data: Resource = StatusCatalog.definition(status_id)
		if data == null or String(data.get("tick_phase")) != phase:
			continue
		var state_value: Variant = statuses.get(status_id, {})
		var stacks: int = 1
		if state_value is Dictionary:
			stacks = maxi(1, int((state_value as Dictionary).get("stacks", 1)))
		if int(data.get("tick_damage")) > 0:
			result.append({"type": "damage", "amount": int(data.get("tick_damage")) * stacks, "status_id": status_id})
		if int(data.get("tick_heal")) > 0:
			result.append({"type": "heal", "amount": int(data.get("tick_heal")) * stacks, "status_id": status_id})
	return result


func finish_status_activation() -> PackedStringArray:
	var expired: PackedStringArray = PackedStringArray()
	for status_key: Variant in statuses.keys():
		var status_id: String = String(status_key)
		var state_value: Variant = statuses.get(status_id, {})
		if not (state_value is Dictionary):
			continue
		var state: Dictionary = (state_value as Dictionary).duplicate(true)
		var remaining: int = int(state.get("remaining", 0))
		if remaining <= 0:
			continue
		remaining -= 1
		if remaining <= 0:
			statuses.erase(status_id)
			expired.append(status_id)
		else:
			state["remaining"] = remaining
			statuses[status_id] = state
	_sync_status_vfx()
	_refresh_label()
	return expired


func remove_statuses_on_damage_taken() -> PackedStringArray:
	var removed: PackedStringArray = PackedStringArray()
	for status_key: Variant in statuses.keys():
		var status_id: String = String(status_key)
		var data: Resource = StatusCatalog.definition(status_id)
		if data != null and bool(data.get("remove_on_damage_taken")):
			statuses.erase(status_id)
			removed.append(status_id)
	_sync_status_vfx()
	_refresh_label()
	return removed


func remove_statuses_on_attack() -> PackedStringArray:
	var removed: PackedStringArray = PackedStringArray()
	for status_key: Variant in statuses.keys():
		var status_id: String = String(status_key)
		var data: Resource = StatusCatalog.definition(status_id)
		if data != null and bool(data.get("remove_on_attack")):
			statuses.erase(status_id)
			removed.append(status_id)
	_sync_status_vfx()
	_refresh_label()
	return removed


func battle_present() -> bool:
	return alive or (downed and not removed_from_battle)


func enter_downed() -> void:
	hp = 0
	alive = false
	downed = true
	downed_countdown = CombatMechanics.DOWNED_COUNTDOWN_ACTIVATIONS
	removed_from_battle = false
	casting.clear()
	ct = 0
	moved_this_activation = true
	acted_this_activation = true
	_refresh_label()


func advance_downed_countdown() -> int:
	if not downed or removed_from_battle:
		return 0
	downed_countdown = CombatMechanics.downed_tick_remaining(downed_countdown)
	ct = 0
	if downed_countdown <= 0:
		downed = false
		removed_from_battle = true
	_refresh_label()
	return downed_countdown


func revive(flat_bonus: int = 0) -> int:
	if not downed or removed_from_battle:
		return 0
	var restored: int = CombatMechanics.revive_hp(max_hp, flat_bonus)
	hp = restored
	alive = true
	downed = false
	downed_countdown = 0
	removed_from_battle = false
	ct = 0
	reaction_ready = false
	reaction_used_this_round = false
	_animation_state = "idle"
	_animation_elapsed = 0.0
	_presentation_locked = false
	scale = Vector3.ONE
	if _sprite != null:
		_sprite.modulate = _sprite_base_modulate()
		_sprite.scale = Vector3.ONE * _sprite_art_scale
	if _shadow != null:
		_shadow.scale = Vector3.ONE
	if _facing_marker != null:
		_facing_marker.visible = true
	if _vitals_sprite != null:
		_vitals_sprite.visible = true
	if _status_vfx_root != null:
		_status_vfx_root.visible = true
	_refresh_visuals()
	return restored


func take_damage(amount: int) -> int:
	if not alive:
		return 0
	var applied: int = mini(maxi(0, amount), hp)
	hp -= applied
	_refresh_label()
	_play_hit_flash()
	if hp <= 0:
		enter_downed()
	return applied


func set_selected(value: bool) -> void:
	_selected = value
	_update_selection_visuals()


func set_turn_active(value: bool) -> void:
	_turn_active = value
	_update_selection_visuals()


func label_text() -> String:
	var status_text: String = status_display_text()
	var reaction_text: String = ""
	if reaction_type != "none":
		reaction_text = "R:%s%s" % [reaction_type.to_upper(), "+" if reaction_ready else ""]
	var base: String = "%s  HP %d/%d  FP %d/%d\nPUI.P %d • PUI.M %d • DEF.P %d • DEF.M %d\nMOV %d • RNG %d-%d • CT %d" % [display_name, hp, max_hp, focus, max_focus, effective_physical_power(), effective_magic_power(), effective_physical_defense(), effective_magic_defense(), move_range, attack_min_range, attack_range, ct]
	var extras: PackedStringArray = PackedStringArray()
	if downed:
		extras.append("K.O. %d" % downed_countdown)
	if is_casting():
		extras.append("CAST:%s %dt" % [SkillCatalog.display_name(String(casting.get("skill_id", ""))), maxi(0, int(casting.get("remaining_ticks", 0)))])
	if not reaction_text.is_empty():
		extras.append(reaction_text)
	if not status_text.is_empty():
		extras.append(status_text)
	return base if extras.is_empty() else base + "\n" + " • ".join(extras)


func play_attack(target_world_position: Vector3) -> Tween:
	_set_animation_state("attack")
	var origin: Vector3 = position
	if _current_map != null:
		var target_local: Vector3 = _current_map.to_local(target_world_position)
		face_cell(_current_map.local_to_cell(target_local))
	var direction: Vector3 = target_world_position - origin
	direction.y = 0.0
	if direction.length_squared() > 0.001:
		direction = direction.normalized()
	var lunge: Vector3 = origin + direction * 0.24
	_presentation_locked = true
	if _sprite != null:
		_sprite.position = _sprite_base_position()
	var tween: Tween = create_tween()
	tween.set_trans(Tween.TRANS_SINE)
	tween.tween_property(self, "position", lunge, 0.085)
	tween.tween_property(self, "position", origin, 0.12)
	tween.tween_callback(_end_presentation_lock)
	if _sprite != null:
		var sprite_tween: Tween = create_tween()
		sprite_tween.set_trans(Tween.TRANS_SINE)
		sprite_tween.tween_property(_sprite, "scale", Vector3(_sprite_art_scale * 1.14, _sprite_art_scale * 0.88, _sprite_art_scale), 0.085)
		sprite_tween.tween_property(_sprite, "scale", Vector3.ONE * _sprite_art_scale, 0.12)
	return tween


func play_cast(target_world_position: Vector3) -> Tween:
	_set_animation_state("cast")
	if _current_map != null:
		var target_local: Vector3 = _current_map.to_local(target_world_position)
		face_cell(_current_map.local_to_cell(target_local))
	_presentation_locked = true
	var tween: Tween = create_tween()
	tween.tween_interval(0.26)
	tween.tween_callback(_end_presentation_lock)
	if _sprite != null:
		var base_position: Vector3 = _sprite_base_position()
		_sprite.position = base_position
		var rise_tween: Tween = create_tween()
		rise_tween.set_trans(Tween.TRANS_SINE)
		rise_tween.tween_property(_sprite, "position:y", base_position.y + 0.16, 0.11)
		rise_tween.tween_property(_sprite, "position:y", base_position.y, 0.15)
		var scale_tween: Tween = create_tween()
		scale_tween.set_trans(Tween.TRANS_SINE)
		scale_tween.tween_property(_sprite, "scale", Vector3.ONE * (_sprite_art_scale * 1.10), 0.11)
		scale_tween.tween_property(_sprite, "scale", Vector3.ONE * _sprite_art_scale, 0.15)
	return tween


func _end_presentation_lock() -> void:
	_presentation_locked = false
	if alive and _animation_state in ["attack", "cast"]:
		_set_animation_state("idle")


func play_ko() -> Tween:
	_set_animation_state("ko")
	if not downed:
		enter_downed()
	set_selected(false)
	set_turn_active(false)
	var tween: Tween = create_tween()
	tween.set_parallel(true)
	tween.tween_property(self, "scale", Vector3(0.82, 0.34, 0.82), 0.28)
	if _sprite != null:
		tween.tween_property(_sprite, "modulate", Color(0.72, 0.72, 0.78, 0.48), 0.28)
	if _shadow != null:
		tween.tween_property(_shadow, "scale", Vector3(0.3, 1.0, 0.3), 0.28)
	if _facing_marker != null:
		_facing_marker.visible = false
	if _vitals_sprite != null:
		_vitals_sprite.visible = false
	if _status_vfx_root != null:
		_status_vfx_root.visible = false
	return tween


func _play_hit_flash() -> void:
	if _sprite == null:
		return
	_set_animation_state("hit")
	_sprite.modulate = Color(1.0, 0.38, 0.38, 1.0)
	var color_tween: Tween = create_tween()
	color_tween.tween_property(_sprite, "modulate", _sprite_base_modulate(), 0.18)
	color_tween.tween_callback(_finish_hit_animation)
	var scale_tween: Tween = create_tween()
	scale_tween.tween_property(_sprite, "scale", Vector3(_sprite_art_scale * 0.90, _sprite_art_scale * 1.08, _sprite_art_scale), 0.07)
	scale_tween.tween_property(_sprite, "scale", Vector3.ONE * _sprite_art_scale, 0.11)


func _finish_hit_animation() -> void:
	if alive and _animation_state == "hit":
		_set_animation_state("idle")


func _ensure_visual_nodes() -> void:
	if _shadow == null:
		_shadow = get_node_or_null("Shadow") as MeshInstance3D
	if _shadow == null:
		_shadow = MeshInstance3D.new()
		_shadow.name = "Shadow"
		add_child(_shadow)
		var shadow_mesh: CylinderMesh = CylinderMesh.new()
		shadow_mesh.top_radius = 0.28
		shadow_mesh.bottom_radius = 0.36
		shadow_mesh.height = 0.02
		_shadow.mesh = shadow_mesh
		var shadow_material: StandardMaterial3D = StandardMaterial3D.new()
		shadow_material.albedo_color = Color(0.0, 0.0, 0.0, 0.34)
		shadow_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		shadow_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_shadow.material_override = shadow_material
		_shadow.position = Vector3(0.0, 0.01, 0.0)

	if _sprite == null:
		_sprite = get_node_or_null("Sprite") as Sprite3D
	if _sprite == null:
		_sprite = Sprite3D.new()
		_sprite.name = "Sprite"
		add_child(_sprite)
		_sprite.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		_sprite.pixel_size = 0.016
		_sprite.no_depth_test = false
		_sprite.position = _sprite_base_position()

	if _selection_disc == null:
		_selection_disc = get_node_or_null("SelectionDisc") as MeshInstance3D
	if _selection_disc == null:
		_selection_disc = MeshInstance3D.new()
		_selection_disc.name = "SelectionDisc"
		add_child(_selection_disc)
		var selection_mesh: CylinderMesh = CylinderMesh.new()
		selection_mesh.top_radius = 0.40
		selection_mesh.bottom_radius = 0.40
		selection_mesh.height = 0.025
		_selection_disc.mesh = selection_mesh
		_selection_disc.position = Vector3(0.0, 0.035, 0.0)
		var selection_material: StandardMaterial3D = StandardMaterial3D.new()
		selection_material.albedo_color = Color(1.0, 0.91, 0.48, 0.82)
		selection_material.emission_enabled = true
		selection_material.emission = Color(1.0, 0.91, 0.48, 1.0)
		selection_material.emission_energy_multiplier = 0.35
		selection_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_selection_disc.material_override = selection_material

	if _turn_marker == null:
		_turn_marker = get_node_or_null("TurnMarker") as MeshInstance3D
	if _turn_marker == null:
		_turn_marker = MeshInstance3D.new()
		_turn_marker.name = "TurnMarker"
		add_child(_turn_marker)
		var turn_mesh: CylinderMesh = CylinderMesh.new()
		turn_mesh.top_radius = 0.48
		turn_mesh.bottom_radius = 0.48
		turn_mesh.height = 0.012
		_turn_marker.mesh = turn_mesh
		_turn_marker.position = Vector3(0.0, 0.018, 0.0)
		var turn_material: StandardMaterial3D = StandardMaterial3D.new()
		turn_material.albedo_color = Color(0.34, 0.83, 1.0, 0.36)
		turn_material.emission_enabled = true
		turn_material.emission = Color(0.34, 0.83, 1.0, 1.0)
		turn_material.emission_energy_multiplier = 0.20
		turn_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_turn_marker.material_override = turn_material

	if _facing_marker == null:
		_facing_marker = get_node_or_null("FacingMarker") as MeshInstance3D
	if _facing_marker == null:
		_facing_marker = MeshInstance3D.new()
		_facing_marker.name = "FacingMarker"
		add_child(_facing_marker)
		var facing_mesh: BoxMesh = BoxMesh.new()
		facing_mesh.size = Vector3(0.10, 0.035, 0.30)
		_facing_marker.mesh = facing_mesh
		var facing_material: StandardMaterial3D = StandardMaterial3D.new()
		facing_material.albedo_color = Color(0.40, 0.82, 1.0, 0.92) if team == "player" else Color(1.0, 0.44, 0.38, 0.92)
		facing_material.emission_enabled = true
		facing_material.emission = facing_material.albedo_color
		facing_material.emission_energy_multiplier = 0.28
		_facing_marker.material_override = facing_material
	_update_facing_visual()

	if _vitals_sprite == null:
		_vitals_sprite = get_node_or_null("Vitals") as Sprite3D
	if _vitals_sprite == null:
		_vitals_sprite = Sprite3D.new()
		_vitals_sprite.name = "Vitals"
		add_child(_vitals_sprite)
		_vitals_sprite.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		_vitals_sprite.pixel_size = 0.0065
		_vitals_sprite.no_depth_test = true
		_vitals_sprite.position = Vector3(0.0, 1.30, 0.0)

	if _status_vfx_root == null:
		_status_vfx_root = get_node_or_null("StatusVfx") as Node3D
	if _status_vfx_root == null:
		_status_vfx_root = Node3D.new()
		_status_vfx_root.name = "StatusVfx"
		add_child(_status_vfx_root)

	if _label == null:
		_label = get_node_or_null("Label") as Label3D
	if _label == null:
		_label = Label3D.new()
		_label.name = "Label"
		add_child(_label)
		_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		_label.no_depth_test = true
		_label.outline_size = 8
		_label.font_size = 24
		_label.position = Vector3(0.0, 1.62, 0.0)


func _refresh_visuals() -> void:
	_ensure_visual_nodes()
	_configure_sprite_source()
	_refresh_label()
	_update_selection_visuals()
	_update_facing_visual()
	_sync_status_vfx()


func _configure_sprite_source() -> void:
	_uses_sprite_sheet = false
	_sprite_sheet_texture = null
	_sprite_frame_texture = null
	_last_sprite_frame = Vector2i(-999, -999)
	_last_view_direction = _view_direction_name()
	if _visual_definition != null:
		_sprite_art_scale = maxf(0.1, float(_visual_definition.get("sprite_scale")))
		var raw_offset: Variant = _visual_definition.get("sprite_offset")
		if raw_offset is Vector2:
			_sprite_art_offset = raw_offset
		var sheet_path: String = String(_visual_definition.get("sprite_sheet_path"))
		var fw: int = int(_visual_definition.get("frame_width"))
		var fh: int = int(_visual_definition.get("frame_height"))
		if bool(_visual_definition.get("use_sprite_sheet")) and fw > 0 and fh > 0 and not sheet_path.is_empty() and ResourceLoader.exists(sheet_path):
			var loaded_sheet: Resource = load(sheet_path)
			if loaded_sheet is Texture2D:
				_sprite_sheet_texture = loaded_sheet as Texture2D
				_sprite_frame_texture = AtlasTexture.new()
				_sprite_frame_texture.atlas = _sprite_sheet_texture
				_sprite.texture = _sprite_frame_texture
				_uses_sprite_sheet = true
	_sprite.position = _sprite_base_position()
	_sprite.scale = Vector3.ONE * _sprite_art_scale
	_sprite.modulate = _sprite_base_modulate()
	if _uses_sprite_sheet:
		_update_sprite_animation(true)
	else:
		_sprite.texture = _build_texture(_last_view_direction)


func _set_animation_state(state: String, restart: bool = true) -> void:
	if state.is_empty():
		state = "idle"
	if _animation_state == state and not restart:
		return
	_animation_state = state
	if restart:
		_animation_elapsed = 0.0
	_last_sprite_frame = Vector2i(-999, -999)
	_update_sprite_animation(true)


func animation_state() -> String:
	return _animation_state


func _update_sprite_animation(force: bool = false) -> void:
	if _sprite == null:
		return
	if _visual_definition == null or not _uses_sprite_sheet or _sprite_sheet_texture == null or _sprite_frame_texture == null:
		return
	var direction_name: String = _view_direction_name()
	var texture_size_raw: Vector2 = _sprite_sheet_texture.get_size()
	var texture_size: Vector2i = Vector2i(roundi(texture_size_raw.x), roundi(texture_size_raw.y))
	var coords_value: Variant = _visual_definition.call("atlas_frame_coordinates", _animation_state, _animation_elapsed, direction_name, texture_size)
	var coords: Vector2i = coords_value if coords_value is Vector2i else Vector2i.ZERO
	if not force and coords == _last_sprite_frame:
		return
	_last_sprite_frame = coords
	var fw: int = maxi(1, int(_visual_definition.get("frame_width")))
	var fh: int = maxi(1, int(_visual_definition.get("frame_height")))
	_sprite_frame_texture.region = Rect2(coords.x * fw, coords.y * fh, fw, fh)
	_sprite.flip_h = bool(_visual_definition.get("flip_with_facing")) and direction_name in ["left", "front_left", "back_left"]
	_sprite.modulate = _sprite_base_modulate()
	var clip_value: Variant = _visual_definition.call("clip_data", _animation_state)
	var clip: Dictionary = {}
	if clip_value is Dictionary:
		clip = clip_value as Dictionary
	if not bool(clip.get("loop", false)):
		var duration: float = float(_visual_definition.call("clip_duration", _animation_state))
		if _animation_elapsed >= duration and alive and not _presentation_locked and _animation_state in ["hit", "attack", "cast"]:
			_set_animation_state("idle")


func _update_directional_sprite() -> void:
	var direction_name: String = _view_direction_name()
	if direction_name == _last_view_direction:
		return
	_last_view_direction = direction_name
	_last_sprite_frame = Vector2i(-999, -999)
	if _uses_sprite_sheet:
		_update_sprite_animation(true)
	elif _sprite != null:
		_sprite.texture = _build_texture(direction_name)


func _view_direction_name() -> String:
	var camera: Camera3D = get_viewport().get_camera_3d()
	if camera == null:
		return "front"
	var to_camera_3d: Vector3 = camera.global_position - global_position
	var to_camera: Vector2 = Vector2(to_camera_3d.x, to_camera_3d.z)
	if to_camera.length_squared() < 0.0001:
		return "front"
	to_camera = to_camera.normalized()
	var face: Vector2 = Vector2(float(facing.x), float(facing.y))
	if face.length_squared() < 0.0001:
		face = Vector2.DOWN
	face = face.normalized()
	var dot_value: float = clampf(face.dot(to_camera), -1.0, 1.0)
	var cross_value: float = face.x * to_camera.y - face.y * to_camera.x
	var angle: float = atan2(cross_value, dot_value)
	var mode: String = String(_visual_definition.get("direction_mode")) if _visual_definition != null else "4_way"
	if mode == "8_way":
		var sector8: int = roundi(angle / (PI / 4.0)) % 8
		if sector8 < 0:
			sector8 += 8
		var names8: PackedStringArray = PackedStringArray(["front", "right", "back_right", "back", "back_left", "left", "front_left", "front_right"])
		return names8[sector8]
	var sector4: int = roundi(angle / (PI / 2.0)) % 4
	if sector4 < 0:
		sector4 += 4
	var names4: PackedStringArray = PackedStringArray(["front", "right", "back", "left"])
	return names4[sector4]


func _sprite_base_position() -> Vector3:
	const PIXEL_TO_WORLD: float = 0.016
	return Vector3(_sprite_art_offset.x * PIXEL_TO_WORLD, 0.58 - _sprite_art_offset.y * PIXEL_TO_WORLD, 0.0)


func _sprite_base_modulate() -> Color:
	if _visual_definition != null and bool(_visual_definition.get("tint_sprite_with_primary")) and _uses_sprite_sheet:
		return primary_color
	return Color.WHITE


func _sync_status_vfx() -> void:
	if _status_vfx_root == null:
		return
	var active_ids: Dictionary = {}
	for key: Variant in statuses.keys():
		active_ids[String(key)] = true
	for key: Variant in _status_vfx_nodes.keys():
		var existing_id: String = String(key)
		if active_ids.has(existing_id):
			continue
		var old_node: Node3D = _status_vfx_nodes.get(existing_id, null) as Node3D
		if old_node != null and is_instance_valid(old_node):
			old_node.queue_free()
		_status_vfx_nodes.erase(existing_id)
	for key: Variant in statuses.keys():
		var status_id: String = String(key)
		if _status_vfx_nodes.has(status_id):
			continue
		var status_node: Node3D = _create_status_vfx_node(status_id)
		if status_node != null:
			_status_vfx_root.add_child(status_node)
			_status_vfx_nodes[status_id] = status_node
	_status_vfx_root.visible = alive and not statuses.is_empty()


func _create_status_vfx_node(status_id: String) -> Node3D:
	var status_data: Resource = StatusCatalog.definition(status_id)
	if status_data == null:
		return null
	var vfx_id: String = String(status_data.get("vfx_id"))
	var vfx_data: Resource = VfxCatalog.definition(vfx_id)
	var primary: Color = status_data.get("color") if status_data.get("color") is Color else Color.WHITE
	var secondary: Color = primary.lightened(0.22)
	var kind: String = "aura"
	if vfx_data != null:
		if vfx_data.get("primary_color") is Color:
			primary = vfx_data.get("primary_color")
		if vfx_data.get("secondary_color") is Color:
			secondary = vfx_data.get("secondary_color")
		kind = String(vfx_data.get("kind"))
	var root: Node3D = Node3D.new()
	root.name = "Status_%s" % status_id
	root.set_meta("status_id", status_id)
	root.set_meta("vfx_id", vfx_id)
	root.set_meta("kind", kind)
	if vfx_id == "guard_aura":
		root.set_meta("style", "shield")
		_add_status_disc(root, primary, 0.47, 0.10)
		_add_status_disc(root, secondary, 0.34, 0.62)
	elif vfx_id == "burn_aura":
		root.set_meta("style", "flame")
		for index: int in range(4):
			_add_status_orb(root, primary if index % 2 == 0 else secondary, 0.075 + 0.01 * float(index % 2), index)
	elif vfx_id == "poison_aura":
		root.set_meta("style", "orbit")
		for index: int in range(5):
			_add_status_orb(root, primary if index % 2 == 0 else secondary, 0.055, index)
	elif kind == "ring":
		root.set_meta("style", "ring")
		_add_status_disc(root, primary, 0.36, 0.12)
	else:
		root.set_meta("style", "orbit")
		for index: int in range(3):
			_add_status_orb(root, primary if index % 2 == 0 else secondary, 0.05, index)
	return root


func _add_status_disc(root: Node3D, color: Color, radius: float, y: float) -> void:
	var disc: MeshInstance3D = MeshInstance3D.new()
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = 0.018
	disc.mesh = mesh
	disc.position.y = y
	disc.material_override = _status_material(color, 0.36)
	root.add_child(disc)


func _add_status_orb(root: Node3D, color: Color, radius: float, index: int) -> void:
	var orb: MeshInstance3D = MeshInstance3D.new()
	var mesh: SphereMesh = SphereMesh.new()
	mesh.radius = radius
	mesh.height = radius * 2.0
	orb.mesh = mesh
	orb.material_override = _status_material(color, 0.78)
	orb.set_meta("orbit_index", index)
	root.add_child(orb)


func _status_material(color: Color, alpha_scale: float) -> StandardMaterial3D:
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = Color(color.r, color.g, color.b, clampf(color.a * alpha_scale, 0.08, 1.0))
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.emission_enabled = true
	material.emission = Color(color.r, color.g, color.b, 1.0)
	material.emission_energy_multiplier = 0.65
	return material


func _update_status_vfx_animation() -> void:
	if _status_vfx_root == null or not alive:
		return
	for key: Variant in _status_vfx_nodes.keys():
		var root: Node3D = _status_vfx_nodes.get(String(key), null) as Node3D
		if root == null or not is_instance_valid(root):
			continue
		var style: String = String(root.get_meta("style", "orbit"))
		var children: Array[Node] = root.get_children()
		for index: int in range(children.size()):
			var child: Node3D = children[index] as Node3D
			if child == null:
				continue
			var phase: float = _presentation_time * 3.0 + float(index) * 1.37 + _idle_phase
			match style:
				"shield":
					var pulse: float = 1.0 + sin(phase * 1.4) * 0.08
					child.scale = Vector3(pulse, 1.0, pulse)
				"flame":
					var flame_angle: float = phase + float(index) * 1.1
					child.position = Vector3(cos(flame_angle) * 0.24, 0.35 + fmod(_presentation_time * 0.72 + float(index) * 0.23, 0.62), sin(flame_angle) * 0.18)
					var flame_scale: float = 0.75 + sin(phase * 2.3) * 0.22
					child.scale = Vector3(flame_scale, 1.25 + flame_scale * 0.25, flame_scale)
				"ring":
					var ring_pulse: float = 0.92 + sin(phase * 1.8) * 0.10
					child.scale = Vector3(ring_pulse, 1.0, ring_pulse)
				_:
					var angle: float = phase + TAU * float(index) / float(maxi(1, children.size()))
					child.position = Vector3(cos(angle) * 0.30, 0.42 + sin(phase * 1.7) * 0.10, sin(angle) * 0.30)


func _refresh_label() -> void:
	if _label != null:
		_label.text = label_text()
	_refresh_vitals_bar()


func _update_selection_visuals() -> void:
	if _selection_disc != null:
		_selection_disc.visible = _selected and alive
	if _turn_marker != null:
		_turn_marker.visible = _turn_active and alive
	if _label != null:
		_label.visible = (_selected or _turn_active) and alive
	if _vitals_sprite != null:
		_vitals_sprite.visible = alive
	if _sprite != null and alive:
		var base_modulate: Color = _sprite_base_modulate()
		_sprite.modulate = base_modulate.lightened(0.12) if _selected else base_modulate


func _update_facing_visual() -> void:
	if _facing_marker == null:
		return
	var material: StandardMaterial3D = _facing_marker.material_override as StandardMaterial3D
	if material != null:
		var facing_color: Color = Color(0.40, 0.82, 1.0, 0.92) if team == "player" else Color(1.0, 0.44, 0.38, 0.92)
		material.albedo_color = facing_color
		material.emission = facing_color
	_facing_marker.visible = alive
	_facing_marker.position = Vector3(float(facing.x) * 0.31, 0.052, float(facing.y) * 0.31)
	if facing == Vector2i.RIGHT:
		_facing_marker.rotation.y = PI * 0.5
	elif facing == Vector2i.LEFT:
		_facing_marker.rotation.y = -PI * 0.5
	elif facing == Vector2i.UP:
		_facing_marker.rotation.y = PI
	else:
		_facing_marker.rotation.y = 0.0


func _refresh_vitals_bar() -> void:
	if _vitals_sprite == null:
		return
	_vitals_sprite.texture = _build_vitals_texture()
	_vitals_sprite.visible = alive


func _build_vitals_texture() -> Texture2D:
	const WIDTH: int = 128
	const HEIGHT: int = 30
	var image: Image = Image.create(WIDTH, HEIGHT, false, Image.FORMAT_RGBA8)
	image.fill(Color(0.0, 0.0, 0.0, 0.0))
	_fill_rect(image, Rect2i(2, 2, 124, 12), Color(0.05, 0.06, 0.08, 0.92))
	_fill_rect(image, Rect2i(4, 4, 120, 8), Color(0.18, 0.08, 0.08, 0.96))
	var hp_ratio: float = float(maxi(0, hp)) / float(maxi(1, max_hp))
	var hp_width: int = roundi(120.0 * hp_ratio)
	var hp_color: Color = Color(0.34, 0.86, 0.45, 1.0)
	if hp_ratio <= 0.25:
		hp_color = Color(1.0, 0.29, 0.24, 1.0)
	elif hp_ratio <= 0.50:
		hp_color = Color(1.0, 0.69, 0.25, 1.0)
	if hp_width > 0:
		_fill_rect(image, Rect2i(4, 4, hp_width, 8), hp_color)

	_fill_rect(image, Rect2i(2, 17, 124, 9), Color(0.05, 0.06, 0.08, 0.92))
	_fill_rect(image, Rect2i(4, 19, 120, 5), Color(0.10, 0.12, 0.22, 0.96))
	var focus_ratio: float = float(maxi(0, focus)) / float(maxi(1, max_focus))
	var focus_width: int = roundi(120.0 * focus_ratio)
	if focus_width > 0:
		_fill_rect(image, Rect2i(4, 19, focus_width, 5), Color(0.37, 0.68, 1.0, 1.0))
	return ImageTexture.create_from_image(image)


func portrait_texture() -> Texture2D:
	if _visual_definition != null:
		var portrait_path: String = String(_visual_definition.get("portrait_path"))
		if not portrait_path.is_empty() and ResourceLoader.exists(portrait_path):
			var loaded_portrait: Resource = load(portrait_path)
			if loaded_portrait is Texture2D:
				return loaded_portrait as Texture2D
	return _build_texture("front")


func _build_texture(direction_name: String = "front") -> Texture2D:
	var width: int = 96
	var height: int = 128
	var image: Image = Image.create(width, height, false, Image.FORMAT_RGBA8)
	image.fill(Color(0.0, 0.0, 0.0, 0.0))

	_fill_ellipse(image, Vector2(48.0, 85.0), Vector2(21.0, 24.0), outline_color)
	_fill_ellipse(image, Vector2(48.0, 82.0), Vector2(18.0, 21.0), secondary_color)
	_fill_ellipse(image, Vector2(48.0, 49.0), Vector2(33.0, 22.0), outline_color)
	_fill_ellipse(image, Vector2(48.0, 46.0), Vector2(30.0, 19.0), primary_color)
	_fill_ellipse(image, Vector2(48.0, 40.0), Vector2(20.0, 7.0), primary_color.lightened(0.18))
	_fill_ellipse(image, Vector2(34.0, 44.0), Vector2(6.0, 4.0), accent_color)
	_fill_ellipse(image, Vector2(61.0, 42.0), Vector2(5.0, 4.0), accent_color)
	_fill_ellipse(image, Vector2(49.0, 54.0), Vector2(5.0, 3.0), accent_color)
	if direction_name == "back":
		_fill_ellipse(image, Vector2(39.0, 72.0), Vector2(4.0, 3.0), accent_color.darkened(0.12))
		_fill_ellipse(image, Vector2(57.0, 72.0), Vector2(4.0, 3.0), accent_color.darkened(0.12))
	elif direction_name in ["right", "front_right", "back_right"]:
		_fill_ellipse(image, Vector2(56.0, 79.0), Vector2(3.0, 5.0), outline_color)
		_fill_ellipse(image, Vector2(57.0, 77.5), Vector2(1.0, 2.0), Color.WHITE)
	elif direction_name in ["left", "front_left", "back_left"]:
		_fill_ellipse(image, Vector2(40.0, 79.0), Vector2(3.0, 5.0), outline_color)
		_fill_ellipse(image, Vector2(41.0, 77.5), Vector2(1.0, 2.0), Color.WHITE)
	else:
		_fill_ellipse(image, Vector2(42.0, 79.0), Vector2(3.0, 5.0), outline_color)
		_fill_ellipse(image, Vector2(54.0, 79.0), Vector2(3.0, 5.0), outline_color)
		_fill_ellipse(image, Vector2(43.0, 77.5), Vector2(1.0, 2.0), Color.WHITE)
		_fill_ellipse(image, Vector2(55.0, 77.5), Vector2(1.0, 2.0), Color.WHITE)

	var trim: Color = Color("#61c8ff") if team == "player" else Color("#ff7f6e")
	_fill_rect(image, Rect2i(32, 96, 32, 6), trim)
	_fill_rect(image, Rect2i(28, 96, 4, 12), trim.darkened(0.12))
	return ImageTexture.create_from_image(image)


func _fill_rect(image: Image, rect: Rect2i, color: Color) -> void:
	for y: int in range(rect.position.y, rect.position.y + rect.size.y):
		for x: int in range(rect.position.x, rect.position.x + rect.size.x):
			if x >= 0 and y >= 0 and x < image.get_width() and y < image.get_height():
				image.set_pixel(x, y, color)


func _fill_ellipse(image: Image, center: Vector2, radii: Vector2, color: Color) -> void:
	var left: int = floori(center.x - radii.x)
	var right: int = ceili(center.x + radii.x)
	var top: int = floori(center.y - radii.y)
	var bottom: int = ceili(center.y + radii.y)
	for y: int in range(top, bottom + 1):
		for x: int in range(left, right + 1):
			if x < 0 or y < 0 or x >= image.get_width() or y >= image.get_height():
				continue
			var nx: float = (float(x) - center.x) / maxf(radii.x, 0.001)
			var ny: float = (float(y) - center.y) / maxf(radii.y, 0.001)
			if nx * nx + ny * ny <= 1.0:
				image.set_pixel(x, y, color)
