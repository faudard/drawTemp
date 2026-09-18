@tool
class_name SporeCinematicTimelineEditor
extends VBoxContainer

const CardScript = preload("res://addons/sporebound_studio/cinematic_timeline_card.gd")

signal item_selected(index: int)
signal move_requested(from_index: int, to_index: int)
signal duplicate_requested(index: int)
signal delete_requested(index: int)
signal play_from_requested(index: int)
signal play_sequence_requested

var _scroll: ScrollContainer
var _cards: VBoxContainer
var _empty_label: Label
var _status_label: Label
var _actions: Array = []
var _selected_index: int = -1
var _playing_action_id: String = ""


func _ready() -> void:
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	custom_minimum_size = Vector2(350.0, 300.0)
	_build_ui()


func _build_ui() -> void:
	if _cards != null:
		return

	var toolbar: HBoxContainer = HBoxContainer.new()
	toolbar.add_theme_constant_override("separation", 6)
	add_child(toolbar)

	var play_all: Button = Button.new()
	play_all.text = "▶ LIRE TOUT"
	play_all.focus_mode = Control.FOCUS_NONE
	play_all.tooltip_text = "Prévisualiser la timeline entière"
	play_all.pressed.connect(
		func() -> void:
			play_sequence_requested.emit()
	)
	toolbar.add_child(play_all)

	var help: Label = Label.new()
	help.text = "glisser-déposer pour réordonner"
	help.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	help.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	help.add_theme_font_size_override("font_size", 10)
	help.add_theme_color_override(
		"font_color",
		Color(0.62, 0.70, 0.80, 1.0)
	)
	toolbar.add_child(help)

	_scroll = ScrollContainer.new()
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_child(_scroll)

	_cards = VBoxContainer.new()
	_cards.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_cards.add_theme_constant_override("separation", 6)
	_scroll.add_child(_cards)

	_empty_label = Label.new()
	_empty_label.text = "Aucune action. Utilise + Action pour commencer."
	_empty_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_empty_label.add_theme_color_override(
		"font_color",
		Color(0.62, 0.68, 0.76, 1.0)
	)
	_cards.add_child(_empty_label)

	_status_label = Label.new()
	_status_label.text = ""
	_status_label.add_theme_font_size_override("font_size", 10)
	_status_label.add_theme_color_override(
		"font_color",
		Color(1.0, 0.82, 0.38, 1.0)
	)
	add_child(_status_label)


func clear() -> void:
	_actions.clear()
	_selected_index = -1
	_playing_action_id = ""
	_rebuild()


func set_actions(actions: Array, selected_index: int = -1) -> void:
	_actions = actions.duplicate()
	_selected_index = selected_index
	_rebuild()


func select(index: int) -> void:
	_selected_index = index
	_update_card_states()


func set_playing_action(action_id: String) -> void:
	_playing_action_id = action_id
	_status_label.text = "Lecture : %s" % action_id if not action_id.is_empty() else ""
	_update_card_states()


func clear_playing_action() -> void:
	_playing_action_id = ""
	_status_label.text = ""
	_update_card_states()


func _rebuild() -> void:
	if _cards == null:
		_build_ui()

	for child: Node in _cards.get_children():
		child.queue_free()

	if _actions.is_empty():
		_empty_label = Label.new()
		_empty_label.text = "Aucune action. Utilise + Action pour commencer."
		_empty_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_empty_label.add_theme_color_override(
			"font_color",
			Color(0.62, 0.68, 0.76, 1.0)
		)
		_cards.add_child(_empty_label)
		return

	for index: int in range(_actions.size()):
		var action: Resource = _actions[index] as Resource
		var card: SporeCinematicTimelineCard = CardScript.new() as SporeCinematicTimelineCard
		_cards.add_child(card)
		var action_id: String = String(action.get("id")) if action != null else ""
		card.configure(
			index,
			action,
			index == _selected_index,
			not _playing_action_id.is_empty() and action_id == _playing_action_id
		)
		card.selected.connect(_on_card_selected)
		card.drop_requested.connect(_on_card_drop)
		card.duplicate_requested.connect(
			func(card_index: int) -> void:
				duplicate_requested.emit(card_index)
		)
		card.delete_requested.connect(
			func(card_index: int) -> void:
				delete_requested.emit(card_index)
		)
		card.play_from_requested.connect(
			func(card_index: int) -> void:
				play_from_requested.emit(card_index)
		)


func _update_card_states() -> void:
	if _cards == null:
		return
	for child: Node in _cards.get_children():
		if not (child is SporeCinematicTimelineCard):
			continue
		var card: SporeCinematicTimelineCard = child as SporeCinematicTimelineCard
		card.set_selected(card.action_index == _selected_index)
		card.set_playing(
			not _playing_action_id.is_empty()
			and card.action_id == _playing_action_id
		)


func _on_card_selected(index: int) -> void:
	_selected_index = index
	_update_card_states()
	item_selected.emit(index)


func _on_card_drop(from_index: int, to_index: int) -> void:
	if from_index == to_index:
		return
	move_requested.emit(from_index, to_index)
