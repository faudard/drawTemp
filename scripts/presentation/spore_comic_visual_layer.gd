class_name SporeComicVisualLayer
extends CanvasLayer

@export var enabled: bool = true
@export_range(0.0, 1.0, 0.01) var grayscale_strength: float = 0.94
@export_range(0.0, 2.0, 0.01) var ink_strength: float = 0.72
@export_range(2.0, 12.0, 1.0) var poster_levels: float = 6.0
@export_range(0.0, 0.12, 0.001) var grain_strength: float = 0.022
@export_range(0.0, 1.0, 0.01) var selective_color_strength: float = 1.0

const COMIC_SHADER: Shader = preload("res://assets/shaders/comic_selective_color.gdshader")

var _screen_pass: ColorRect


func _ready() -> void:
	layer = 0
	_build_screen_pass()
	_apply_parameters()


func _build_screen_pass() -> void:
	if _screen_pass != null:
		return
	_screen_pass = ColorRect.new()
	_screen_pass.name = "ComicSelectiveColorPass"
	_screen_pass.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_screen_pass.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_screen_pass.color = Color.WHITE
	var material := ShaderMaterial.new()
	material.shader = COMIC_SHADER
	_screen_pass.material = material
	add_child(_screen_pass)


func _apply_parameters() -> void:
	if _screen_pass == null:
		return
	_screen_pass.visible = enabled
	var material := _screen_pass.material as ShaderMaterial
	if material == null:
		return
	material.set_shader_parameter("grayscale_strength", grayscale_strength)
	material.set_shader_parameter("ink_strength", ink_strength)
	material.set_shader_parameter("poster_levels", poster_levels)
	material.set_shader_parameter("grain_strength", grain_strength)
	material.set_shader_parameter("selective_color_strength", selective_color_strength)
