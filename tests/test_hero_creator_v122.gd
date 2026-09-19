extends SceneTree

const AppearanceDefinition = preload("res://scripts/data/hero_appearance_definition.gd")
const HeroCompositor = preload("res://scripts/visual/hero_compositor.gd")
const Preview = preload("res://addons/sporebound_studio/hero_customizer_preview.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	test_direct_transform_fields()
	test_group_bounds()
	test_scale_rotation_and_offset_change_output()
	test_preview_contract()
	if failures.is_empty():
		print("[V1.22] Hero Creator Direct Edit smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_direct_transform_fields() -> void:
	var appearance: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	expect(is_equal_approx(appearance.head_transform_scale, 1.0), "head direct scale defaults to 1")
	expect(is_zero_approx(appearance.head_rotation_degrees), "head rotation defaults to 0")
	expect(not appearance.head_locked, "head group starts unlocked")
	appearance.face_locked = true
	expect(appearance.face_locked, "group lock state is persistent data")


func test_group_bounds() -> void:
	var appearance: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	appearance.head_shape_style = "wide"
	appearance.head_pattern_style = "spots"
	appearance.eyes_style = "big"
	var head_bounds: Rect2 = HeroCompositor.edit_group_bounds(appearance, "head", "front")
	var face_bounds: Rect2 = HeroCompositor.edit_group_bounds(appearance, "face", "front")
	expect(head_bounds.size.x > 1.0 and head_bounds.size.y > 1.0, "head alpha bounds are available for selection handles")
	expect(face_bounds.size.x > 1.0 and face_bounds.size.y > 1.0, "face alpha bounds are available for selection handles")
	expect(HeroCompositor.edit_group_for_category("weapon") == "weapon", "weapon maps to direct edit group")
	expect(HeroCompositor.edit_group_for_category("eyes") == "face", "eyes map to face direct edit group")


func test_scale_rotation_and_offset_change_output() -> void:
	var appearance: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	appearance.head_shape_style = "pointed"
	appearance.head_pattern_style = "rim"
	appearance.eyes_style = "friendly"
	appearance.weapon_style = "sword"
	var base: Image = HeroCompositor.compose_frame(appearance, "front")
	appearance.head_transform_scale = 1.18
	var scaled: Image = HeroCompositor.compose_frame(appearance, "front")
	expect(base.get_data() != scaled.get_data(), "direct head scale changes composed frame")
	appearance.head_transform_scale = 1.0
	appearance.head_rotation_degrees = 8.0
	var rotated: Image = HeroCompositor.compose_frame(appearance, "front")
	expect(base.get_data() != rotated.get_data(), "direct head rotation changes composed frame")
	appearance.head_rotation_degrees = 0.0
	appearance.face_offset = Vector2(6, -4)
	var moved: Image = HeroCompositor.compose_frame(appearance, "front")
	expect(base.get_data() != moved.get_data(), "direct face drag offset changes composed frame")


func test_preview_contract() -> void:
	var preview: SporeHeroCustomizerPreview = Preview.new() as SporeHeroCustomizerPreview
	expect(preview != null, "direct-edit preview instantiates")
	if preview == null:
		return
	preview.set_selected_edit_group("weapon")
	expect(preview.selected_edit_group == "weapon", "preview exposes selected edit group")
	preview.set_group_locked("weapon", true)
	expect(bool(preview.locked_groups.get("weapon", false)), "preview receives lock state")
	preview.free()
