extends SceneTree

const AppearanceDefinition = preload("res://scripts/data/hero_appearance_definition.gd")
const Compositor = preload("res://scripts/visual/hero_compositor.gd")
const VisualDefinition = preload("res://scripts/data/unit_visual_definition.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	test_part_library()
	test_compositor_contract()
	test_default_momo_binding()
	if failures.is_empty():
		print("[V1.19] Hero Creator smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_part_library() -> void:
	for category: String in ["body", "cap", "face", "top", "bottom", "accessory", "weapon"]:
		var ids: PackedStringArray = Compositor.available_part_ids(category)
		expect(not ids.is_empty(), "hero part category must not be empty: %s" % category)
	expect(Compositor.available_part_ids("cap").has("classic"), "classic cap available")
	expect(Compositor.available_part_ids("face").has("cyclops"), "cyclops face available")
	expect(Compositor.available_part_ids("weapon").has("rifle"), "rifle available")


func test_compositor_contract() -> void:
	var appearance: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	var front: Image = Compositor.compose_frame(appearance, "front")
	var atlas: Image = Compositor.compose_atlas(appearance)
	expect(front.get_size() == Compositor.FRAME_SIZE, "hero preview frame size")
	expect(atlas.get_size() == Vector2i(Compositor.FRAME_SIZE.x * 6, Compositor.FRAME_SIZE.y * 4), "hero atlas is six states x four directions")
	expect(front.detect_alpha() != Image.ALPHA_NONE, "hero frame keeps transparency")


func test_default_momo_binding() -> void:
	var appearance_path: String = "res://data/hero_appearances/momo.tres"
	var visual_path: String = "res://data/visuals/units/momo.tres"
	expect(ResourceLoader.exists(appearance_path), "Momo appearance resource exists")
	expect(ResourceLoader.exists(visual_path), "Momo visual exists")
	var visual: SporeUnitVisualDefinition = load(visual_path) as SporeUnitVisualDefinition
	if visual == null:
		failures.append("Momo visual cannot be loaded")
		return
	expect(visual.use_sprite_sheet, "Momo uses generated hero spritesheet")
	expect(visual.direction_mode == "4_way", "Momo generated visual uses four directions")
	expect(visual.frame_width == 192 and visual.frame_height == 192, "Momo generated frame size")
	expect(visual.idle_start == 0 and visual.move_start == 1 and visual.attack_start == 2, "generated state columns are mapped")
	expect(visual.cast_start == 3 and visual.hit_start == 4 and visual.ko_start == 5, "generated cast/hit/ko columns are mapped")
