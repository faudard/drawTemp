extends SceneTree

const VisualDefinition = preload("res://scripts/data/unit_visual_definition.gd")
const Actor3D = preload("res://scripts/maps/spore_unit_actor_3d.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	test_directional_atlas_rows()
	test_directional_atlas_blocks()
	test_cast_clip()
	test_actor_animation_contract()
	if failures.is_empty():
		print("[V1.18] Directional sprite / animation smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_directional_atlas_rows() -> void:
	var visual: SporeUnitVisualDefinition = VisualDefinition.new() as SporeUnitVisualDefinition
	visual.frame_width = 32
	visual.frame_height = 32
	visual.direction_mode = "4_way"
	visual.direction_layout = "rows"
	visual.idle_start = 1
	visual.idle_count = 2
	visual.idle_fps = 4.0
	var front: Vector2i = visual.atlas_frame_coordinates("idle", 0.0, "front", Vector2i(256, 128))
	var right: Vector2i = visual.atlas_frame_coordinates("idle", 0.0, "right", Vector2i(256, 128))
	var back: Vector2i = visual.atlas_frame_coordinates("idle", 0.0, "back", Vector2i(256, 128))
	expect(front == Vector2i(1, 0), "4-way rows: front must use row 0")
	expect(right == Vector2i(1, 1), "4-way rows: right must use row 1")
	expect(back == Vector2i(1, 2), "4-way rows: back must use row 2")


func test_directional_atlas_blocks() -> void:
	var visual: SporeUnitVisualDefinition = VisualDefinition.new() as SporeUnitVisualDefinition
	visual.frame_width = 32
	visual.frame_height = 32
	visual.direction_mode = "4_way"
	visual.direction_layout = "blocks"
	visual.direction_stride_frames = 8
	visual.attack_start = 2
	visual.attack_count = 2
	var left: Vector2i = visual.atlas_frame_coordinates("attack", 0.0, "left", Vector2i(256, 128))
	# left = direction index 3, 3*8 + frame 2 = flat frame 26 -> x2/y3 on an 8-column sheet.
	expect(left == Vector2i(2, 3), "4-way blocks: direction stride is applied")


func test_cast_clip() -> void:
	var visual: SporeUnitVisualDefinition = VisualDefinition.new() as SporeUnitVisualDefinition
	visual.cast_start = 12
	visual.cast_count = 4
	visual.cast_fps = 8.0
	visual.cast_loop = false
	expect(visual.frame_index("cast", 0.0) == 12, "cast starts on configured frame")
	expect(visual.frame_index("cast", 0.30) == 14, "cast advances using cast fps")
	expect(is_equal_approx(visual.clip_duration("cast"), 0.5), "cast duration comes from count/fps")


func test_actor_animation_contract() -> void:
	var actor: SporeUnitActor3D = Actor3D.new() as SporeUnitActor3D
	expect(actor.has_method("animation_state"), "3D actor exposes animation state")
	expect(actor.has_method("play_attack"), "3D actor exposes attack animation")
	expect(actor.has_method("play_cast"), "3D actor exposes cast animation")
	expect(actor.has_method("play_ko"), "3D actor exposes KO animation")
	actor.free()
