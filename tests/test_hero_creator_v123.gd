extends SceneTree

const AppearanceDefinition = preload("res://scripts/data/hero_appearance_definition.gd")
const Preview = preload("res://addons/sporebound_studio/hero_customizer_preview.gd")
const Editor = preload("res://addons/sporebound_studio/hero_customizer_editor.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	test_preview_comparison_contract()
	test_workflow_editor_contract()
	test_portable_look_copy_contract()
	if failures.is_empty():
		print("[V1.23] Hero Creator Workflow smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func test_preview_comparison_contract() -> void:
	var current: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	var reference: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	reference.head_shape_style = "wide"
	var preview: SporeHeroCustomizerPreview = Preview.new() as SporeHeroCustomizerPreview
	expect(preview != null, "workflow preview instantiates")
	if preview == null:
		return
	preview.set_appearance(current)
	preview.set_reference_appearance(reference)
	preview.set_comparison_enabled(true)
	expect(preview.reference_appearance == reference, "preview stores before reference")
	expect(preview.comparison_enabled, "preview enables before/after mode")
	preview.free()


func test_workflow_editor_contract() -> void:
	var editor: SporeHeroCustomizerEditor = Editor.new() as SporeHeroCustomizerEditor
	expect(editor != null, "workflow editor instantiates")
	if editor == null:
		return
	expect(editor.has_method("_undo"), "workflow exposes undo action")
	expect(editor.has_method("_redo"), "workflow exposes redo action")
	expect(editor.has_method("_capture_reference"), "workflow exposes before/after capture")
	expect(editor.has_method("_export_current_look"), "workflow exposes look export")
	expect(editor.has_method("_import_selected_look"), "workflow exposes look import")
	expect(editor.has_method("_on_favorite_toggled"), "workflow exposes piece favorites")
	editor.free()


func test_portable_look_copy_contract() -> void:
	var source: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	var target: SporeHeroAppearanceDefinition = AppearanceDefinition.new() as SporeHeroAppearanceDefinition
	source.hero_id = "portable_source"
	source.target_visual_id = "portable_source"
	source.display_name = "Look violet"
	source.head_shape_style = "mutant"
	source.head_primary_color = Color("#8b5cf6")
	target.hero_id = "momo"
	target.target_visual_id = "momo"
	target.display_name = "Momo"
	var editor: SporeHeroCustomizerEditor = Editor.new() as SporeHeroCustomizerEditor
	editor.call("_copy_appearance_fields", source, target)
	expect(target.hero_id == "momo", "portable copy protects hero identity")
	expect(target.target_visual_id == "momo", "portable copy protects target visual")
	expect(target.display_name == "Momo", "portable copy protects display name")
	expect(target.head_shape_style == "mutant", "portable copy imports visual parts")
	expect(target.head_primary_color == Color("#8b5cf6"), "portable copy imports palette")
	editor.free()
