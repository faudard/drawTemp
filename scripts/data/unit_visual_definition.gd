@tool
class_name SporeUnitVisualDefinition
extends Resource

## Visual-only definition for one unit or skin.
## Runtime falls back to procedural drawing when sprite_sheet_path is empty.
## Directional sheets can be authored as one row per view direction or as
## consecutive frame blocks per direction.

@export_group("Identity")
@export var id: String = "visual"
@export var display_name: String = "Visual"
@export var unit_id: String = ""

@export_group("Assets")
@export_file("*.png", "*.jpg", "*.jpeg", "*.webp", "*.svg") var portrait_path: String = ""
@export_file("*.png", "*.jpg", "*.jpeg", "*.webp") var sprite_sheet_path: String = ""
@export var use_sprite_sheet: bool = false
@export_range(0, 1024, 1) var frame_width: int = 0
@export_range(0, 1024, 1) var frame_height: int = 0
@export_range(0.1, 8.0, 0.05) var sprite_scale: float = 1.0
@export var sprite_offset: Vector2 = Vector2.ZERO
@export var flip_with_facing: bool = false

@export_group("Directional sprites")
@export_enum("single", "4_way", "8_way") var direction_mode: String = "single"
@export_enum("rows", "blocks") var direction_layout: String = "rows"
@export_range(0, 999, 1) var direction_stride_frames: int = 0
@export var four_direction_order: String = "front,right,back,left"
@export var eight_direction_order: String = "front,front_right,right,back_right,back,back_left,left,front_left"

@export_group("Fallback / Palette")
@export_enum("mushroom", "slime", "armored", "orb") var fallback_shape: String = "mushroom"
@export var primary_color: Color = Color.WHITE
@export var secondary_color: Color = Color("#f3e5c0")
@export var accent_color: Color = Color("#ffd166")
@export var outline_color: Color = Color("#251c32")
@export var tint_sprite_with_primary: bool = false

@export_group("Idle")
@export_range(0, 999, 1) var idle_start: int = 0
@export_range(1, 999, 1) var idle_count: int = 1
@export_range(0.1, 60.0, 0.1) var idle_fps: float = 4.0
@export var idle_loop: bool = true

@export_group("Move")
@export_range(0, 999, 1) var move_start: int = 0
@export_range(1, 999, 1) var move_count: int = 1
@export_range(0.1, 60.0, 0.1) var move_fps: float = 8.0
@export var move_loop: bool = true

@export_group("Attack")
@export_range(0, 999, 1) var attack_start: int = 0
@export_range(1, 999, 1) var attack_count: int = 1
@export_range(0.1, 60.0, 0.1) var attack_fps: float = 10.0
@export var attack_loop: bool = false

@export_group("Cast")
@export_range(0, 999, 1) var cast_start: int = 0
@export_range(1, 999, 1) var cast_count: int = 1
@export_range(0.1, 60.0, 0.1) var cast_fps: float = 10.0
@export var cast_loop: bool = false

@export_group("Hit")
@export_range(0, 999, 1) var hit_start: int = 0
@export_range(1, 999, 1) var hit_count: int = 1
@export_range(0.1, 60.0, 0.1) var hit_fps: float = 10.0
@export var hit_loop: bool = false

@export_group("KO")
@export_range(0, 999, 1) var ko_start: int = 0
@export_range(1, 999, 1) var ko_count: int = 1
@export_range(0.1, 60.0, 0.1) var ko_fps: float = 8.0
@export var ko_loop: bool = false

@export_group("Combat VFX")
@export var basic_attack_vfx_id: String = "default_hit"


func clip_data(state: String) -> Dictionary:
	match state:
		"move":
			return {"start": move_start, "count": move_count, "fps": move_fps, "loop": move_loop}
		"attack":
			return {"start": attack_start, "count": attack_count, "fps": attack_fps, "loop": attack_loop}
		"cast":
			return {"start": cast_start, "count": cast_count, "fps": cast_fps, "loop": cast_loop}
		"hit":
			return {"start": hit_start, "count": hit_count, "fps": hit_fps, "loop": hit_loop}
		"ko":
			return {"start": ko_start, "count": ko_count, "fps": ko_fps, "loop": ko_loop}
		_:
			return {"start": idle_start, "count": idle_count, "fps": idle_fps, "loop": idle_loop}


func frame_index(state: String, elapsed: float) -> int:
	var clip: Dictionary = clip_data(state)
	var count: int = maxi(1, int(clip["count"]))
	var safe_elapsed: float = maxf(0.0, elapsed)
	var fps: float = maxf(0.1, float(clip["fps"]))
	var frame: int = int(floor(safe_elapsed * fps))
	if bool(clip["loop"]):
		frame %= count
	else:
		frame = mini(frame, count - 1)
	return int(clip["start"]) + frame


func clip_duration(state: String) -> float:
	var clip: Dictionary = clip_data(state)
	return float(maxi(1, int(clip["count"]))) / maxf(0.1, float(clip["fps"]))


func direction_count() -> int:
	match direction_mode:
		"4_way": return 4
		"8_way": return 8
		_: return 1


func direction_names() -> PackedStringArray:
	if direction_mode == "8_way":
		return _validated_direction_order(
			eight_direction_order,
			PackedStringArray(["front", "front_right", "right", "back_right", "back", "back_left", "left", "front_left"]),
			8
		)
	if direction_mode == "4_way":
		return _validated_direction_order(
			four_direction_order,
			PackedStringArray(["front", "right", "back", "left"]),
			4
		)
	return PackedStringArray(["front"])


func direction_index(direction_name: String) -> int:
	var names: PackedStringArray = direction_names()
	var index: int = names.find(direction_name)
	if index >= 0:
		return index
	# Diagonal views gracefully collapse to their nearest four-way direction.
	var collapsed: String = direction_name
	match direction_name:
		"front_right": collapsed = "right"
		"back_right": collapsed = "right"
		"back_left": collapsed = "left"
		"front_left": collapsed = "left"
	index = names.find(collapsed)
	return maxi(0, index)


func atlas_frame_coordinates(
	state: String,
	elapsed: float,
	direction_name: String,
	texture_size: Vector2i
) -> Vector2i:
	var fw: int = maxi(1, frame_width)
	var fh: int = maxi(1, frame_height)
	var columns: int = maxi(1, floori(float(texture_size.x) / float(fw)))
	var rows: int = maxi(1, floori(float(texture_size.y) / float(fh)))
	var base_frame: int = maxi(0, frame_index(state, elapsed))
	var dir_index: int = direction_index(direction_name)
	if direction_mode == "single":
		return Vector2i(base_frame % columns, mini(rows - 1, floori(float(base_frame) / float(columns))))
	if direction_layout == "rows":
		return Vector2i(mini(columns - 1, base_frame), mini(rows - 1, dir_index))
	var total_frames: int = columns * rows
	var stride: int = direction_stride_frames
	if stride <= 0:
		stride = maxi(1, floori(float(total_frames) / float(maxi(1, direction_count()))))
	var flat_frame: int = clampi(dir_index * stride + base_frame, 0, total_frames - 1)
	return Vector2i(flat_frame % columns, floori(float(flat_frame) / float(columns)))


func _validated_direction_order(raw: String, fallback: PackedStringArray, expected: int) -> PackedStringArray:
	var result: PackedStringArray = PackedStringArray()
	for entry: String in raw.split(","):
		var cleaned: String = entry.strip_edges().to_lower()
		if not cleaned.is_empty():
			result.append(cleaned)
	if result.size() != expected:
		return fallback
	return result
