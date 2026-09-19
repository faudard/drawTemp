extends SceneTree

const Appearance = preload("res://scripts/data/hero_appearance_definition.gd")
const HeroCompositor = preload("res://scripts/visual/hero_compositor.gd")

const NEW_CATEGORIES: Array[String] = [
	"iris", "pupil", "brows", "nose", "teeth", "skin_spots",
	"mark_2", "mark_3", "earrings", "jewelry",
]

func _init() -> void:
	var appearance: Resource = Appearance.new()
	appearance.set("eyes_style", "friendly")
	appearance.set("iris_style", "ring")
	appearance.set("pupil_style", "slit")
	appearance.set("brows_style", "soft")
	appearance.set("nose_style", "button")
	appearance.set("teeth_style", "single_fang")
	appearance.set("skin_spots_style", "freckles")
	appearance.set("mark_style", "scar_left")
	appearance.set("mark_2_style", "cheek_slash")
	appearance.set("mark_3_style", "crack")
	appearance.set("earrings_style", "stud")
	appearance.set("jewelry_style", "pendant")
	appearance.set("asymmetry_enabled", true)
	appearance.set("left_earrings_style", "none")
	appearance.set("right_earrings_style", "stud")
	assert(String(appearance.call("directional_part_id", "earrings", "left")) == "none")
	assert(String(appearance.call("directional_part_id", "earrings", "right")) == "stud")
	assert(String(appearance.call("directional_part_id", "earrings", "front")) == "stud")
	assert(String(appearance.call("part_id", "mark_2")) == "cheek_slash")
	assert(String(appearance.call("part_id", "mark_3")) == "crack")
	for category: String in NEW_CATEGORIES:
		assert(not HeroCompositor.available_part_ids(category).is_empty())
	for direction: String in HeroCompositor.DIRECTIONS:
		var frame: Image = HeroCompositor.compose_frame(appearance, direction)
		assert(frame != null)
		assert(frame.get_size() == HeroCompositor.FRAME_SIZE)
	var thumb_a: Image = HeroCompositor.compose_part_thumbnail("iris", "ring")
	var thumb_b: Image = HeroCompositor.compose_part_thumbnail("iris", "ring")
	assert(thumb_a.get_size() == Vector2i(96, 96))
	assert(thumb_b.get_size() == Vector2i(96, 96))
	print("[V1.25] Hero Creator Face Details smoke test OK")
	quit()
