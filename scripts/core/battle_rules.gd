class_name SporeBattleRules
extends RefCounted

## Pure battle helpers. They are deterministic and independent from the scene tree.


static func manhattan(a: Vector2i, b: Vector2i) -> int:
	return abs(a.x - b.x) + abs(a.y - b.y)


static func neighbours(cell: Vector2i) -> Array:
	return [
		cell + Vector2i(1, 0),
		cell + Vector2i(-1, 0),
		cell + Vector2i(0, 1),
		cell + Vector2i(0, -1),
	]


static func direction_from_to(from_cell: Vector2i, to_cell: Vector2i) -> Vector2i:
	var delta := to_cell - from_cell
	if delta == Vector2i.ZERO:
		return Vector2i(0, 1)
	if abs(delta.x) >= abs(delta.y):
		return Vector2i(1 if delta.x > 0 else -1, 0)
	return Vector2i(0, 1 if delta.y > 0 else -1)


static func is_back_attack(attacker: Dictionary, target: Dictionary) -> bool:
	var target_facing: Vector2i = target.get("facing", Vector2i(0, 1))
	var attack_side := direction_from_to(target["pos"], attacker["pos"])
	return attack_side == -target_facing


static func is_side_attack(attacker: Dictionary, target: Dictionary) -> bool:
	var target_facing: Vector2i = target.get("facing", Vector2i(0, 1))
	var attack_side := direction_from_to(target["pos"], attacker["pos"])
	return attack_side != target_facing and attack_side != -target_facing


static func line_cells(from_cell: Vector2i, to_cell: Vector2i) -> Array:
	var result: Array = []
	var x0: int = from_cell.x
	var y0: int = from_cell.y
	var x1: int = to_cell.x
	var y1: int = to_cell.y
	var dx: int = absi(x1 - x0)
	var sx: int = 1 if x0 < x1 else -1
	var dy: int = -absi(y1 - y0)
	var sy: int = 1 if y0 < y1 else -1
	var error: int = dx + dy
	while true:
		result.append(Vector2i(x0, y0))
		if x0 == x1 and y0 == y1:
			break
		var twice_error: int = 2 * error
		if twice_error >= dy:
			error += dy
			x0 += sx
		if twice_error <= dx:
			error += dx
			y0 += sy
	return result


static func add_status(unit: Dictionary, status_id: String) -> void:
	var statuses: Dictionary = unit.get("statuses", {})
	statuses[status_id] = true
	unit["statuses"] = statuses


static func remove_status(unit: Dictionary, status_id: String) -> void:
	var statuses: Dictionary = unit.get("statuses", {})
	statuses.erase(status_id)
	unit["statuses"] = statuses


static func has_status(unit: Dictionary, status_id: String) -> bool:
	var statuses: Dictionary = unit.get("statuses", {})
	return bool(statuses.get(status_id, false))


static func facing_label(unit: Dictionary) -> String:
	var facing: Vector2i = unit.get("facing", Vector2i(0, 1))
	if facing == Vector2i(0, -1):
		return "N"
	if facing == Vector2i(1, 0):
		return "E"
	if facing == Vector2i(0, 1):
		return "S"
	return "O"
