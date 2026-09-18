class_name SporeStatusCatalog
extends RefCounted

## Runtime access to data/statuses/*.tres. Status state is stored in unit["statuses"] as
## { status_id: {"remaining": int, "remaining_clockticks": int, "stacks": int} }. Legacy entries are tolerated.

const STATUS_DIR := "res://data/statuses/"


static func definition(status_id: String) -> Resource:
	var path := STATUS_DIR + status_id + ".tres"
	return load(path) if ResourceLoader.exists(path) else null


static func all_status_ids() -> PackedStringArray:
	var result := PackedStringArray()
	var dir := DirAccess.open(STATUS_DIR)
	if dir == null:
		return result
	for file_name in dir.get_files():
		if file_name.ends_with(".tres"):
			result.append(file_name.get_basename())
	result.sort()
	return result


static func vfx_id(status_id: String) -> String:
	var data := definition(status_id)
	return String(data.vfx_id) if data != null else ""


static func has(unit: Dictionary, status_id: String) -> bool:
	var statuses: Dictionary = unit.get("statuses", {})
	return statuses.has(status_id)


static func state(unit: Dictionary, status_id: String) -> Dictionary:
	var statuses: Dictionary = unit.get("statuses", {})
	if not statuses.has(status_id):
		return {}
	var value: Variant = statuses[status_id]
	if typeof(value) == TYPE_DICTIONARY:
		return value
	var data := definition(status_id)
	return {
		"remaining": int(data.duration_activations) if data != null else 0,
		"remaining_clockticks": int(data.duration_clockticks) if data != null else 0,
		"stacks": 1,
	}


static func apply(unit: Dictionary, status_id: String, duration_override: int = -1, stacks_to_add: int = 1) -> void:
	if status_id.is_empty():
		return
	var statuses: Dictionary = unit.get("statuses", {})
	var data := definition(status_id)
	var duration := duration_override
	if duration < 0:
		duration = int(data.duration_activations) if data != null else 1
	var clockticks: int = int(data.duration_clockticks) if data != null else 0
	if data != null and not String(data.opposed_status_id).is_empty():
		statuses.erase(String(data.opposed_status_id))
	var max_stacks := int(data.max_stacks) if data != null else 1
	var mode := String(data.stack_mode) if data != null else "refresh"
	var existing := state(unit, status_id)
	var stacks: int = mini(max_stacks, maxi(1, stacks_to_add))
	if not existing.is_empty():
		stacks = int(existing.get("stacks", 1))
		if mode == "stack":
			stacks = min(max_stacks, stacks + max(1, stacks_to_add))
		elif mode == "replace":
			stacks = min(max_stacks, max(1, stacks_to_add))
		else:
			stacks = max(stacks, min(max_stacks, max(1, stacks_to_add)))
	statuses[status_id] = {"remaining": duration, "remaining_clockticks": clockticks, "stacks": stacks}
	unit["statuses"] = statuses


static func remove(unit: Dictionary, status_id: String) -> void:
	var statuses: Dictionary = unit.get("statuses", {})
	statuses.erase(status_id)
	unit["statuses"] = statuses


static func active_ids(unit: Dictionary) -> PackedStringArray:
	var result := PackedStringArray()
	var statuses: Dictionary = unit.get("statuses", {})
	for status_id in statuses.keys():
		result.append(String(status_id))
	result.sort()
	return result


static func stacks(unit: Dictionary, status_id: String) -> int:
	var status_state := state(unit, status_id)
	return max(1, int(status_state.get("stacks", 1))) if not status_state.is_empty() else 0


static func remaining(unit: Dictionary, status_id: String) -> int:
	var status_state := state(unit, status_id)
	return int(status_state.get("remaining", 0)) if not status_state.is_empty() else 0


static func remaining_clockticks(unit: Dictionary, status_id: String) -> int:
	var status_state := state(unit, status_id)
	return int(status_state.get("remaining_clockticks", 0)) if not status_state.is_empty() else 0


static func ct_rate_percent(unit: Dictionary) -> int:
	var rate: int = 100
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data != null and int(data.ct_rate_percent) != 100:
			rate = int(data.ct_rate_percent)
	return clampi(rate, 0, 200)


static func prevents_reaction(unit: Dictionary) -> bool:
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data != null and bool(data.prevents_reaction):
			return true
	return false




static func next_clock_expiry_ticks(unit: Dictionary) -> int:
	var best: int = 999999
	for status_id in active_ids(unit):
		var remaining_ticks: int = remaining_clockticks(unit, status_id)
		if remaining_ticks > 0:
			best = mini(best, remaining_ticks)
	return best


static func tick_clock(unit: Dictionary, ticks: int) -> PackedStringArray:
	var expired := PackedStringArray()
	if ticks <= 0:
		return expired
	var statuses: Dictionary = unit.get("statuses", {})
	for status_id in active_ids(unit):
		var status_state := state(unit, status_id)
		var remaining_ticks: int = int(status_state.get("remaining_clockticks", 0))
		if remaining_ticks <= 0:
			continue
		remaining_ticks -= ticks
		if remaining_ticks <= 0:
			statuses.erase(status_id)
			expired.append(status_id)
		else:
			status_state["remaining_clockticks"] = remaining_ticks
			statuses[status_id] = status_state
	unit["statuses"] = statuses
	return expired


static func status_modifier(unit: Dictionary, status_id: String, property_name: String) -> int:
	if not has(unit, status_id):
		return 0
	var data := definition(status_id)
	if data == null:
		return 0
	var value := 0
	match property_name:
		"attack_delta": value = int(data.attack_delta)
		"magic_defense_delta": value = int(data.magic_defense_delta)
		"physical_defense_delta": value = int(data.physical_defense_delta)
		"magic_power_delta": value = int(data.magic_power_delta)
		"movement_delta": value = int(data.movement_delta)
		"range_delta": value = int(data.range_delta)
		"initiative_delta": value = int(data.initiative_delta)
		"accuracy_delta": value = int(data.accuracy_delta)
		"evasion_delta": value = int(data.evasion_delta)
		"outgoing_damage_delta": value = int(data.outgoing_damage_delta)
		"incoming_damage_delta": value = int(data.incoming_damage_delta)
		_: value = 0
	return value * stacks(unit, status_id)


static func modifier(unit: Dictionary, property_name: String) -> int:
	var total := 0
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data == null:
			continue
		var value := 0
		match property_name:
			"attack_delta": value = int(data.attack_delta)
			"magic_power_delta": value = int(data.magic_power_delta)
			"physical_defense_delta": value = int(data.physical_defense_delta)
			"magic_defense_delta": value = int(data.magic_defense_delta)
			"movement_delta": value = int(data.movement_delta)
			"range_delta": value = int(data.range_delta)
			"initiative_delta": value = int(data.initiative_delta)
			"accuracy_delta": value = int(data.accuracy_delta)
			"evasion_delta": value = int(data.evasion_delta)
			"outgoing_damage_delta": value = int(data.outgoing_damage_delta)
			"incoming_damage_delta": value = int(data.incoming_damage_delta)
			_: value = 0
		total += value * stacks(unit, status_id)
	return total


static func prevents_movement(unit: Dictionary) -> bool:
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data != null and bool(data.prevents_movement):
			return true
	return false


static func prevents_action(unit: Dictionary) -> bool:
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data != null and bool(data.prevents_action):
			return true
	return false


static func display_text(unit: Dictionary) -> String:
	var labels: Array[String] = []
	for status_id in active_ids(unit):
		var data := definition(status_id)
		var label := String(data.display_name).to_upper() if data != null else status_id.to_upper()
		var count := stacks(unit, status_id)
		var remain_ticks: int = remaining_clockticks(unit, status_id)
		var remain := remaining(unit, status_id)
		if count > 1:
			label += " x%d" % count
		if remain_ticks > 0:
			label += "[%dt]" % remain_ticks
		elif remain > 0:
			label += "[%d]" % remain
		labels.append(label)
	return ", ".join(labels)


static func phase_events(unit: Dictionary, phase: String) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data == null or String(data.tick_phase) != phase:
			continue
		var count := stacks(unit, status_id)
		if int(data.tick_damage) > 0:
			var tick_amount: int = int(data.tick_damage) * count
			if status_id == "poisoned":
				tick_amount = maxi(1, int(floor(float(int(unit.get("max_hp", 1))) / 8.0))) * count
			result.append({
				"type": "damage",
				"amount": tick_amount,
				"damage_type": String(data.tick_damage_type),
				"status_id": status_id,
				"color": data.color
			})
		if int(data.tick_heal) > 0:
			var heal_amount: int = int(data.tick_heal) * count
			if status_id == "regen":
				heal_amount = maxi(1, int(floor(float(int(unit.get("max_hp", 1))) / 8.0))) * count
			result.append({"type": "heal", "amount": heal_amount, "status_id": status_id, "color": data.color})
	return result


static func finish_activation(unit: Dictionary) -> PackedStringArray:
	var expired := PackedStringArray()
	var statuses: Dictionary = unit.get("statuses", {})
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data == null:
			continue
		var status_state := state(unit, status_id)
		if int(status_state.get("remaining_clockticks", 0)) > 0:
			continue
		var remaining_value := int(status_state.get("remaining", 0))
		if remaining_value <= 0:
			continue
		remaining_value -= 1
		if remaining_value <= 0:
			statuses.erase(status_id)
			expired.append(status_id)
		else:
			status_state["remaining"] = remaining_value
			statuses[status_id] = status_state
	unit["statuses"] = statuses
	return expired


static func remove_on_damage_taken(unit: Dictionary) -> PackedStringArray:
	var removed := PackedStringArray()
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data != null and bool(data.remove_on_damage_taken):
			remove(unit, status_id)
			removed.append(status_id)
	return removed


static func remove_on_attack(unit: Dictionary) -> PackedStringArray:
	var removed := PackedStringArray()
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data != null and bool(data.remove_on_attack):
			remove(unit, status_id)
			removed.append(status_id)
	return removed

static func prevents_evasion(unit: Dictionary) -> bool:
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data != null and bool(data.prevents_evasion):
			return true
	return false


static func freezes_ct(unit: Dictionary) -> bool:
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data != null and bool(data.freezes_ct):
			return true
	return false


static func silences_magic(unit: Dictionary) -> bool:
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data != null and bool(data.silences_magic):
			return true
	return false


static func treat_as_moved_for_ct(unit: Dictionary) -> bool:
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data != null and bool(data.treat_as_moved_for_ct):
			return true
	return false


static func treat_as_acted_for_ct(unit: Dictionary) -> bool:
	for status_id in active_ids(unit):
		var data := definition(status_id)
		if data != null and bool(data.treat_as_acted_for_ct):
			return true
	return false
