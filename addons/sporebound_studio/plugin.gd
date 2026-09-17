@tool
extends EditorPlugin

## V1.26.2: Hero Creator is isolated from the rest of Sporebound Studio.
## The plugin can therefore start even if an optional editor tool has a parser error.

const HERO_CREATOR_SCRIPT_PATH := "res://addons/sporebound_studio/hero_customizer_editor.gd"

var panel_control: Control
var bottom_button: Button


func _enter_tree() -> void:
	panel_control = _create_hero_creator()
	if panel_control == null:
		panel_control = _create_failure_panel()
	panel_control.name = "Hero Creator"
	panel_control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel_control.size_flags_vertical = Control.SIZE_EXPAND_FILL
	bottom_button = add_control_to_bottom_panel(panel_control, "Hero Creator")


func _exit_tree() -> void:
	if panel_control != null:
		remove_control_from_bottom_panel(panel_control)
		panel_control.queue_free()
	panel_control = null
	bottom_button = null


func _create_hero_creator() -> Control:
	var hero_script: Script = load(HERO_CREATOR_SCRIPT_PATH) as Script
	if hero_script == null:
		push_error("Hero Creator: impossible de charger %s" % HERO_CREATOR_SCRIPT_PATH)
		return null
	var instance: Variant = hero_script.new()
	if instance is Control:
		return instance as Control
	push_error("Hero Creator: le script ne crée pas un Control")
	return null


func _create_failure_panel() -> Control:
	var root := VBoxContainer.new()
	root.custom_minimum_size = Vector2(640.0, 240.0)
	var title := Label.new()
	title.text = "Hero Creator — échec de chargement"
	title.add_theme_font_size_override("font_size", 20)
	root.add_child(title)
	var text := Label.new()
	text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text.text = "Le bootstrap du plugin fonctionne. Regarde la première erreur rouge dans Sortie pour identifier le sous-script restant à corriger."
	root.add_child(text)
	return root


func _save_external_data() -> void:
	if panel_control != null and panel_control.has_method("save_external_data"):
		panel_control.call("save_external_data")


func _get_plugin_name() -> String:
	return "Sporebound Hero Creator"
