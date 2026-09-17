@tool
class_name SporeHeroCustomizerEditor
extends VBoxContainer

signal library_changed

const APPEARANCE_DEFINITION_SCRIPT = preload("res://scripts/data/hero_appearance_definition.gd")
const HERO_COMPOSITOR_SCRIPT = preload("res://scripts/visual/hero_compositor.gd")
const PREVIEW_SCRIPT = preload("res://addons/sporebound_studio/hero_customizer_preview.gd")

const UNIT_DIR := "res://data/units/"
const APPEARANCE_DIR := "res://data/hero_appearances/"
const PRESET_DIR := "res://data/hero_presets/"
const EXPORT_DIR := "res://data/hero_exports/"
const PALETTE_DIR := "res://data/hero_palettes/"
const FAVORITES_CONFIG := "user://sporebound_hero_creator_favorites.cfg"
const HISTORY_LIMIT := 30
const OPTIONAL_CATEGORIES := ["head_pattern", "ears", "horns", "hair", "iris", "pupil", "brows", "nose", "mouth", "teeth", "facial_hair", "skin_spots", "mark", "mark_2", "mark_3", "earrings", "jewelry", "accessory", "accessory_2", "accessory_3", "weapon"]
const PART_SPECS := [
	["body", "Corps"],
	["head_shape", "Forme du spore"],
	["head_pattern", "Motif / 2e couleur"],
	["ears", "Oreilles"],
	["horns", "Cornes"],
	["hair", "Cheveux / pousse"],
	["eyes", "Forme des yeux"],
	["iris", "Iris"],
	["pupil", "Pupilles"],
	["brows", "Sourcils"],
	["nose", "Nez"],
	["skin_spots", "Taches / peau"],
	["mouth", "Bouche / expression"],
	["teeth", "Dents / crocs"],
	["facial_hair", "Barbe / moustache"],
	["mark", "Cicatrice / marque 1"],
	["mark_2", "Cicatrice / marque 2"],
	["mark_3", "Cicatrice / marque 3"],
	["earrings", "Boucles d’oreilles"],
	["jewelry", "Bijou / pendentif"],
	["top", "Vêtement haut"],
	["bottom", "Vêtement bas"],
	["accessory", "Accessoire 1"],
	["accessory_2", "Accessoire 2"],
	["accessory_3", "Accessoire 3"],
	["weapon", "Arme"],
]
const COLOR_SPECS := [
	["skin_color", "Peau / pied"],
	["head_primary_color", "Spore — couleur 1"],
	["head_secondary_color", "Spore — couleur 2"],
	["ears_color", "Oreilles"],
	["horns_color", "Cornes"],
	["hair_color", "Cheveux / pousse"],
	["eyes_color", "Blanc / forme des yeux"],
	["iris_color", "Iris"],
	["pupil_color", "Pupilles"],
	["brows_color", "Sourcils"],
	["nose_color", "Nez"],
	["skin_spots_color", "Taches / peau"],
	["mouth_color", "Bouche"],
	["teeth_color", "Dents / crocs"],
	["facial_hair_color", "Barbe"],
	["mark_color", "Marque 1"],
	["mark_2_color", "Marque 2"],
	["mark_3_color", "Marque 3"],
	["earrings_color", "Boucles d’oreilles"],
	["jewelry_color", "Bijou / pendentif"],
	["top_color", "Haut"],
	["bottom_color", "Bas"],
	["accessory_color", "Accessoire 1"],
	["accessory_2_color", "Accessoire 2"],
	["accessory_3_color", "Accessoire 3"],
	["weapon_color", "Arme"],
	["global_tint", "Teinte globale"],
]
const MORPH_SPECS := [
	["global_scale", "Taille fine", 0.70, 1.35],
	["body_width_scale", "Largeur corps", 0.65, 1.45],
	["body_height_scale", "Hauteur corps", 0.70, 1.35],
	["head_scale", "Taille tête / spore", 0.70, 1.45],
	["head_width_scale", "Largeur tête / spore", 0.65, 1.55],
]
const OFFSET_SPECS := [
	["body_offset", "Corps"],
	["head_offset", "Tête / spore"],
	["face_offset", "Visage"],
	["accessory_offset", "Accessoire"],
	["weapon_offset", "Arme"],
]
const DIRECT_TRANSFORM_SPECS := [
	["body", "Corps", "body_offset", "body_transform_scale", "body_rotation_degrees", "body_locked"],
	["head", "Tête / spore", "head_offset", "head_transform_scale", "head_rotation_degrees", "head_locked"],
	["face", "Visage", "face_offset", "face_transform_scale", "face_rotation_degrees", "face_locked"],
	["accessory", "Accessoire", "accessory_offset", "accessory_transform_scale", "accessory_rotation_degrees", "accessory_locked"],
	["weapon", "Arme", "weapon_offset", "weapon_transform_scale", "weapon_rotation_degrees", "weapon_locked"],
]
const EDIT_GROUP_OPTIONS := [
	["Corps", "body"],
	["Tête / spore", "head"],
	["Visage", "face"],
	["Accessoire", "accessory"],
	["Arme", "weapon"],
]
const DIRECTIONAL_OVERRIDE_SPECS := [
	["hair", "Cheveux / pousse"],
	["ears", "Oreilles"],
	["horns", "Cornes"],
	["earrings", "Boucles d’oreilles"],
	["accessory", "Accessoire 1"],
	["accessory_2", "Accessoire 2"],
	["accessory_3", "Accessoire 3"],
	["weapon", "Arme"],
]
const SMART_PALETTES := [
	{"head1": "#f27a72", "head2": "#ffd166", "skin": "#f3e5c0", "top": "#45a3c7", "bottom": "#44506b", "accent": "#ffd166"},
	{"head1": "#8b5cf6", "head2": "#67e8f9", "skin": "#eadcf8", "top": "#312e81", "bottom": "#1f2937", "accent": "#f0abfc"},
	{"head1": "#65a30d", "head2": "#facc15", "skin": "#e9ddb8", "top": "#4d7c0f", "bottom": "#365314", "accent": "#bef264"},
	{"head1": "#dc2626", "head2": "#fb923c", "skin": "#f1d3ad", "top": "#7f1d1d", "bottom": "#292524", "accent": "#fde047"},
	{"head1": "#0891b2", "head2": "#a5f3fc", "skin": "#d9f0e9", "top": "#155e75", "bottom": "#164e63", "accent": "#22d3ee"},
	{"head1": "#d946ef", "head2": "#86efac", "skin": "#f5dfc7", "top": "#7e22ce", "bottom": "#3b0764", "accent": "#f0abfc"},
]
const PRESENTATIONS := [
	["Masculin", "masculine"],
	["Féminin", "feminine"],
	["Neutre", "neutral"],
	["Créature", "creature"],
]
const ARCHETYPES := [
	["Aventurier", "adventurer"],
	["Mage", "mage"],
	["Guerrier", "warrior"],
	["Voleur", "rogue"],
	["Funky", "funky"],
	["Ancien", "ancient"],
	["Mécanique", "mechanical"],
]
const SIZE_PRESETS := [
	["Petit", "small"],
	["Moyen", "medium"],
	["Grand", "large"],
]
const SILHOUETTE_PRESETS := [
	["Équilibré", "balanced"],
	["Chibi", "chibi"],
	["Colosse", "colossus"],
	["Élancé", "slender"],
	["Gros spore", "big_spore"],
	["Tank", "tank"],
]
const EXPRESSIONS := [
	["Base", "base"],
	["Joyeux", "cheerful"],
	["Concentré", "focused"],
	["Agressif", "angry"],
	["Mystique", "mystic"],
	["Blessé", "hurt"],
	["KO", "ko"],
	["Héroïque", "heroic"],
	["Malicieux", "mischief"],
]
const EXPRESSION_SPECS := [
	["idle_expression", "Idle"],
	["move_expression", "Move"],
	["attack_expression", "Attack"],
	["cast_expression", "Cast"],
	["hit_expression", "Hit"],
	["ko_expression", "KO"],
	["portrait_expression", "Portrait"],
]
const PORTRAIT_DIRECTIONS := [
	["Face", "front"], ["Droite", "right"], ["Dos", "back"], ["Gauche", "left"],
]
const FRIENDLY_NAMES := {
	"classic": "Classique", "stout": "Trapu", "tall": "Grand", "slim": "Fin", "curvy": "Courbes", "rugged": "Robuste",
	"round": "Rond", "wide": "Très large", "pointed": "Pointu", "droopy": "Retombant", "flat": "Plat", "thick": "Épais", "noble": "Noble", "mutant": "Mutant",
	"spots": "Taches", "dense_spots": "Taches denses", "stripes": "Rayures", "rim": "Bord coloré", "split_two_tone": "Bicolore", "underside_dark": "Dessous coloré",
	"friendly": "Amicaux", "big": "Grands", "narrow": "Fins", "angry": "Agressifs", "sleepy": "Fatigués", "cute": "Mignons", "cyclops": "Cyclope", "robotic": "Mécaniques",
	"large": "Large", "ring": "Anneau", "star": "Étoile", "glow": "Luminescent", "slit": "Fendue", "square": "Carrée", "cross": "Croix", "diamond": "Diamant",
	"soft": "Doux", "straight": "Droits", "arched": "Arquées", "bushy": "Épais",
	"button": "Bouton", "hooked": "Crochu", "tiny": "Petit",
	"smile": "Sourire", "neutral": "Neutre", "grin": "Grand sourire", "stern": "Sévère", "fang": "Crocs",
	"single_fang": "Un croc", "double_fang": "Deux crocs", "buck": "Dents de lapin", "grin_teeth": "Rangée de dents",
	"freckles": "Taches de rousseur", "cheek_spots": "Taches aux joues", "speckles": "Moucheté", "blush": "Rouge aux joues",
	"moustache": "Moustache", "goatee": "Bouc", "short_beard": "Barbe courte", "long_beard": "Barbe longue", "moss_beard": "Barbe mousse",
	"tuft": "Touffe", "bob": "Carré", "crest": "Crête", "braids": "Tresses", "mohawk": "Iroquoise", "long": "Longs",
	"leaf": "Feuille", "mechanical": "Mécanique", "short": "Courtes", "curved": "Courbées", "antler": "Bois", "crystal": "Cristal", "devil": "Démon",
	"scar_left": "Cicatrice gauche", "scar_right": "Cicatrice droite", "cheek_slash": "Griffure joue", "stitched": "Cousue", "tribal": "Marque tribale", "crack": "Fissure",
	"stud": "Clous", "hoop": "Anneaux", "drop": "Pendantes", "pendant": "Pendentif", "mushroom_pin": "Broche champignon", "amulet": "Amulette", "chain": "Chaîne",
	"vest": "Gilet", "hoodie": "Sweat", "armor": "Armure", "poncho": "Poncho", "shorts": "Short", "trousers": "Pantalon", "kilt": "Kilt",
	"scarf": "Écharpe", "goggles": "Lunettes", "badge": "Badge", "backpack": "Sac à dos",
	"sword": "Épée", "rifle": "Fusil", "wand": "Baguette", "hammer": "Marteau", "none": "Aucun",
}

var hero_select: OptionButton
var display_name_edit: LineEdit
var presentation_select: OptionButton
var archetype_select: OptionButton
var size_preset_select: OptionButton
var silhouette_preset_select: OptionButton
var proportions_lock_check: CheckBox
var expression_controls: Dictionary = {}
var expressions_enabled_check: CheckBox
var portrait_direction_select: OptionButton
var portrait_zoom_edit: SpinBox
var portrait_offset_x: SpinBox
var portrait_offset_y: SpinBox
var preview_state_select: OptionButton
var palette_select: OptionButton
var palette_name_edit: LineEdit
var part_controls: Dictionary = {}
var color_controls: Dictionary = {}
var morph_controls: Dictionary = {}
var offset_controls: Dictionary = {}
var direct_transform_controls: Dictionary = {}
var gallery_grids: Dictionary = {}
var gallery_buttons: Dictionary = {}
var favorite_controls: Dictionary = {}
var favorite_parts: Dictionary = {}
var direction_select: OptionButton
var preview_zoom_edit: SpinBox
var edit_group_select: OptionButton
var preview
var scale_edit: SpinBox
var status_label: Label
var preset_select: OptionButton
var preset_name_edit: LineEdit
var copy_target_select: OptionButton
var compare_check: CheckBox
var reference_appearance: Resource = null
var undo_button: Button
var redo_button: Button
var undo_stack: Array[Resource] = []
var redo_stack: Array[Resource] = []
var history_suspended: bool = false
var export_select: OptionButton
var export_name_edit: LineEdit
var asymmetry_check: CheckBox
var direction_override_controls: Dictionary = {}
var current: Resource = null
var current_path: String = ""
var dirty: bool = false
var loading: bool = false


func _ready() -> void:
	name = "Hero Creator Expressions & Profiles"
	_load_favorites()
	_build_ui()
	refresh()


func has_unsaved_data() -> bool:
	return dirty


func save_external_data() -> void:
	_save_definition(false)


func refresh() -> void:
	if dirty:
		_save_definition(false)
	_refresh_heroes()
	_refresh_presets()
	_refresh_exports()
	_refresh_palettes()


func _build_ui() -> void:
	var split: HSplitContainer = HSplitContainer.new()
	split.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(split)

	var left: VBoxContainer = VBoxContainer.new()
	left.custom_minimum_size.x = 650.0
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split.add_child(left)

	var title: Label = Label.new()
	title.text = "HERO CREATOR EXPRESSIONS & PROFILES — V1.26"
	title.add_theme_font_size_override("font_size", 18)
	left.add_child(title)
	var intro: Label = Label.new()
	intro.text = "V1.26 donne une vraie personnalité animée au héros : expressions différentes pour Idle/Move/Attack/Cast/Hit/KO, portrait configurable, silhouettes fortes, verrou de proportions et profils de palette réutilisables."
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.add_child(intro)

	var identity_row: GridContainer = GridContainer.new()
	identity_row.columns = 2
	left.add_child(identity_row)
	_add_label(identity_row, "Héros")
	hero_select = OptionButton.new()
	hero_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hero_select.item_selected.connect(_on_hero_selected)
	identity_row.add_child(hero_select)
	_add_label(identity_row, "Nom de l'apparence")
	display_name_edit = LineEdit.new()
	display_name_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	display_name_edit.text_changed.connect(_on_live_changed)
	identity_row.add_child(display_name_edit)

	var tabs: TabContainer = TabContainer.new()
	tabs.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	left.add_child(tabs)
	_build_identity_tab(tabs)
	_build_morphology_tab(tabs)
	_build_expressions_tab(tabs)
	_build_direct_edit_tab(tabs)
	_build_parts_tab(tabs, "Tête / Spore", ["head_shape", "head_pattern", "ears", "horns", "hair"], ["head_primary_color", "head_secondary_color", "ears_color", "horns_color", "hair_color"])
	_build_asymmetry_tab(tabs)
	_build_parts_tab(tabs, "Visage — yeux", ["eyes", "iris", "pupil", "brows", "nose"], ["eyes_color", "iris_color", "pupil_color", "brows_color", "nose_color"])
	_build_parts_tab(tabs, "Visage — détails", ["skin_spots", "mouth", "teeth", "facial_hair", "mark", "mark_2", "mark_3", "earrings"], ["skin_spots_color", "mouth_color", "teeth_color", "facial_hair_color", "mark_color", "mark_2_color", "mark_3_color", "earrings_color"])
	_build_parts_tab(tabs, "Corps / Équipement", ["body", "jewelry", "top", "bottom", "accessory", "accessory_2", "accessory_3", "weapon"], ["skin_color", "jewelry_color", "top_color", "bottom_color", "accessory_color", "accessory_2_color", "accessory_3_color", "weapon_color"])
	_build_global_tab(tabs)
	_build_palette_tab(tabs)
	_build_presets_tab(tabs)

	var history_row: HBoxContainer = HBoxContainer.new()
	left.add_child(history_row)
	undo_button = Button.new()
	undo_button.text = "↶ Annuler"
	undo_button.pressed.connect(_undo)
	history_row.add_child(undo_button)
	redo_button = Button.new()
	redo_button.text = "↷ Rétablir"
	redo_button.pressed.connect(_redo)
	history_row.add_child(redo_button)
	var history_note: Label = Label.new()
	history_note.text = "Historique local : 30 états"
	history_note.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	history_note.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	history_row.add_child(history_note)
	_update_history_buttons()

	var buttons: HBoxContainer = HBoxContainer.new()
	left.add_child(buttons)
	var random_button: Button = Button.new()
	random_button.text = "Aléatoire intelligent"
	random_button.pressed.connect(_randomize)
	buttons.add_child(random_button)
	var reset_button: Button = Button.new()
	reset_button.text = "Réinitialiser"
	reset_button.pressed.connect(_reset_current)
	buttons.add_child(reset_button)
	var save_button: Button = Button.new()
	save_button.text = "Sauver"
	save_button.pressed.connect(_save_definition.bind(false))
	buttons.add_child(save_button)
	var generate_button: Button = Button.new()
	generate_button.text = "GÉNÉRER / APPLIQUER AU HÉROS"
	generate_button.pressed.connect(_save_definition.bind(true))
	generate_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	buttons.add_child(generate_button)

	status_label = Label.new()
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.add_child(status_label)

	var right: VBoxContainer = VBoxContainer.new()
	right.custom_minimum_size.x = 500.0
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split.add_child(right)
	var preview_title: Label = Label.new()
	preview_title.text = "APERÇU COMPOSÉ"
	preview_title.add_theme_font_size_override("font_size", 18)
	right.add_child(preview_title)
	var preview_controls: GridContainer = GridContainer.new()
	preview_controls.columns = 2
	right.add_child(preview_controls)
	_add_label(preview_controls, "Direction")
	direction_select = OptionButton.new()
	for direction: String in HERO_COMPOSITOR_SCRIPT.DIRECTIONS:
		direction_select.add_item(_direction_label(direction))
		direction_select.set_item_metadata(direction_select.item_count - 1, direction)
	direction_select.item_selected.connect(_on_direction_selected)
	preview_controls.add_child(direction_select)
	_add_label(preview_controls, "État / expression")
	preview_state_select = OptionButton.new()
	for state_name: String in HERO_COMPOSITOR_SCRIPT.STATES:
		preview_state_select.add_item(state_name.to_upper())
		preview_state_select.set_item_metadata(preview_state_select.item_count - 1, state_name)
	preview_state_select.item_selected.connect(_on_preview_state_selected)
	preview_controls.add_child(preview_state_select)
	_add_label(preview_controls, "Zoom aperçu")
	preview_zoom_edit = SpinBox.new()
	preview_zoom_edit.min_value = 0.65
	preview_zoom_edit.max_value = 1.8
	preview_zoom_edit.step = 0.05
	preview_zoom_edit.value = 1.0
	preview_zoom_edit.value_changed.connect(_on_preview_zoom_changed)
	preview_controls.add_child(preview_zoom_edit)
	_add_label(preview_controls, "Couche à éditer")
	edit_group_select = _metadata_option(EDIT_GROUP_OPTIONS)
	_select_metadata(edit_group_select, "head")
	edit_group_select.item_selected.connect(_on_edit_group_selected)
	preview_controls.add_child(edit_group_select)
	_add_label(preview_controls, "Avant / Après")
	var compare_row: HBoxContainer = HBoxContainer.new()
	preview_controls.add_child(compare_row)
	compare_check = CheckBox.new()
	compare_check.text = "Comparer"
	compare_check.toggled.connect(_on_compare_toggled)
	compare_row.add_child(compare_check)
	var capture_reference_button: Button = Button.new()
	capture_reference_button.text = "Capturer référence"
	capture_reference_button.pressed.connect(_capture_reference)
	compare_row.add_child(capture_reference_button)
	preview = PREVIEW_SCRIPT.new()
	preview.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	preview.size_flags_vertical = Control.SIZE_EXPAND_FILL
	preview.transform_delta_requested.connect(_on_preview_transform_delta)
	preview.edit_group_selected.connect(_on_preview_group_selected)
	preview.group_reset_requested.connect(_reset_edit_group)
	right.add_child(preview)
	var help: Label = Label.new()
	help.text = "ÉDITION DIRECTE : clique/glisse pour déplacer, poignées pour resize/rotation. V1.26 : sélectionne aussi Idle/Move/Attack/Cast/Hit/KO pour prévisualiser l’expression réellement bake dans chaque colonne de l’atlas."
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(help)


func _build_identity_tab(tabs: TabContainer) -> void:
	var panel: VBoxContainer = _tab_panel(tabs, "Identité / Style")
	var grid: GridContainer = GridContainer.new()
	grid.columns = 2
	panel.add_child(grid)
	_add_label(grid, "Présentation")
	presentation_select = _metadata_option(PRESENTATIONS)
	presentation_select.item_selected.connect(_on_presentation_changed)
	grid.add_child(presentation_select)
	_add_label(grid, "Style général")
	archetype_select = _metadata_option(ARCHETYPES)
	archetype_select.item_selected.connect(_on_archetype_changed)
	grid.add_child(archetype_select)
	var note: Label = Label.new()
	note.text = "Présentation et style appliquent un preset visible, mais ne verrouillent rien : tu peux ensuite changer librement le corps, les yeux, la barbe, les proportions ou l'équipement."
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(note)


func _build_expressions_tab(tabs: TabContainer) -> void:
	var panel: VBoxContainer = _tab_panel(tabs, "Expressions / États")
	var intro: Label = Label.new()
	intro.text = "Chaque colonne de l’atlas peut maintenant utiliser une expression différente sans dupliquer toute l’apparence. Les overrides concernent uniquement les couches du visage."
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(intro)
	expressions_enabled_check = CheckBox.new()
	expressions_enabled_check.text = "Expressions animées activées"
	expressions_enabled_check.toggled.connect(_on_live_changed)
	panel.add_child(expressions_enabled_check)
	var grid: GridContainer = GridContainer.new()
	grid.columns = 2
	panel.add_child(grid)
	for spec: Array in EXPRESSION_SPECS:
		var property_name: String = String(spec[0])
		_add_label(grid, String(spec[1]))
		var option: OptionButton = _metadata_option(EXPRESSIONS)
		option.item_selected.connect(_on_live_changed)
		grid.add_child(option)
		expression_controls[property_name] = option
	_add_label(grid, "Direction portrait")
	portrait_direction_select = _metadata_option(PORTRAIT_DIRECTIONS)
	portrait_direction_select.item_selected.connect(_on_live_changed)
	grid.add_child(portrait_direction_select)
	_add_label(grid, "Zoom portrait")
	portrait_zoom_edit = SpinBox.new()
	portrait_zoom_edit.min_value = 0.80
	portrait_zoom_edit.max_value = 1.60
	portrait_zoom_edit.step = 0.05
	portrait_zoom_edit.value_changed.connect(_on_live_changed)
	grid.add_child(portrait_zoom_edit)
	_add_label(grid, "Décalage portrait")
	var portrait_offset_row: HBoxContainer = HBoxContainer.new()
	grid.add_child(portrait_offset_row)
	portrait_offset_x = SpinBox.new()
	portrait_offset_x.min_value = -48.0
	portrait_offset_x.max_value = 48.0
	portrait_offset_x.step = 1.0
	portrait_offset_x.prefix = "X "
	portrait_offset_x.value_changed.connect(_on_live_changed)
	portrait_offset_row.add_child(portrait_offset_x)
	portrait_offset_y = SpinBox.new()
	portrait_offset_y.min_value = -48.0
	portrait_offset_y.max_value = 48.0
	portrait_offset_y.step = 1.0
	portrait_offset_y.prefix = "Y "
	portrait_offset_y.value_changed.connect(_on_live_changed)
	portrait_offset_row.add_child(portrait_offset_y)
	var buttons: HBoxContainer = HBoxContainer.new()
	panel.add_child(buttons)
	var dynamic_button: Button = Button.new()
	dynamic_button.text = "Preset combat dynamique"
	dynamic_button.pressed.connect(_apply_expression_preset.bind("dynamic"))
	buttons.add_child(dynamic_button)
	var calm_button: Button = Button.new()
	calm_button.text = "Tout = apparence de base"
	calm_button.pressed.connect(_apply_expression_preset.bind("base"))
	buttons.add_child(calm_button)
	var heroic_button: Button = Button.new()
	heroic_button.text = "Héroïque / cinématique"
	heroic_button.pressed.connect(_apply_expression_preset.bind("heroic"))
	buttons.add_child(heroic_button)
	var note: Label = Label.new()
	note.text = "Le runtime reste inchangé : la génération bake simplement le visage correspondant dans les colonnes Idle, Move, Attack, Cast, Hit et KO."
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(note)


func _build_morphology_tab(tabs: TabContainer) -> void:
	var panel: VBoxContainer = _tab_panel(tabs, "Morphologie")
	var grid: GridContainer = GridContainer.new()
	grid.columns = 2
	panel.add_child(grid)
	_add_label(grid, "Taille générale")
	size_preset_select = _metadata_option(SIZE_PRESETS)
	size_preset_select.item_selected.connect(_on_size_preset_changed)
	grid.add_child(size_preset_select)
	_add_label(grid, "Silhouette forte")
	silhouette_preset_select = _metadata_option(SILHOUETTE_PRESETS)
	silhouette_preset_select.item_selected.connect(_on_silhouette_preset_changed)
	grid.add_child(silhouette_preset_select)
	_add_label(grid, "Proportions")
	proportions_lock_check = CheckBox.new()
	proportions_lock_check.text = "Verrouiller largeur/hauteur"
	proportions_lock_check.toggled.connect(_on_proportions_lock_toggled)
	grid.add_child(proportions_lock_check)
	for spec: Array in MORPH_SPECS:
		var property_name: String = String(spec[0])
		_add_label(grid, String(spec[1]))
		var spin: SpinBox = SpinBox.new()
		spin.min_value = float(spec[2])
		spin.max_value = float(spec[3])
		spin.step = 0.05
		spin.value_changed.connect(_on_morph_value_changed.bind(property_name))
		grid.add_child(spin)
		morph_controls[property_name] = spin
	var separator: HSeparator = HSeparator.new()
	panel.add_child(separator)
	var offset_title: Label = Label.new()
	offset_title.text = "PLACEMENT FIN (pixels)"
	offset_title.add_theme_font_size_override("font_size", 14)
	panel.add_child(offset_title)
	var offset_grid: GridContainer = GridContainer.new()
	offset_grid.columns = 2
	panel.add_child(offset_grid)
	for spec: Array in OFFSET_SPECS:
		var property_name: String = String(spec[0])
		_add_label(offset_grid, String(spec[1]))
		var row: HBoxContainer = HBoxContainer.new()
		offset_grid.add_child(row)
		var x_spin: SpinBox = SpinBox.new()
		x_spin.min_value = -48.0
		x_spin.max_value = 48.0
		x_spin.step = 1.0
		x_spin.prefix = "X "
		x_spin.value_changed.connect(_on_live_changed)
		row.add_child(x_spin)
		var y_spin: SpinBox = SpinBox.new()
		y_spin.min_value = -48.0
		y_spin.max_value = 48.0
		y_spin.step = 1.0
		y_spin.prefix = "Y "
		y_spin.value_changed.connect(_on_live_changed)
		row.add_child(y_spin)
		offset_controls[property_name] = {"x": x_spin, "y": y_spin}
	var reset_offsets: Button = Button.new()
	reset_offsets.text = "Recentrer tous les offsets"
	reset_offsets.pressed.connect(_reset_offsets)
	panel.add_child(reset_offsets)
	var note: Label = Label.new()
	note.text = "La tête, les yeux, la bouche, la barbe et les cicatrices partagent le même repère morphologique. Les offsets restent éditables numériquement jusqu’à ±48 px et sont synchronisés avec le glisser-déposer de l’aperçu V1.22."
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(note)


func _build_direct_edit_tab(tabs: TabContainer) -> void:
	var panel: VBoxContainer = _tab_panel(tabs, "Édition directe")
	var title: Label = Label.new()
	title.text = "TRANSFORMATIONS PAR GROUPE"
	title.add_theme_font_size_override("font_size", 14)
	panel.add_child(title)
	var grid: GridContainer = GridContainer.new()
	grid.columns = 5
	panel.add_child(grid)
	_add_label(grid, "Groupe")
	_add_label(grid, "Scale")
	_add_label(grid, "Rotation")
	_add_label(grid, "Verrou")
	_add_label(grid, "Action")
	for spec: Array in DIRECT_TRANSFORM_SPECS:
		var edit_group: String = String(spec[0])
		_add_label(grid, String(spec[1]))
		var scale_spin: SpinBox = SpinBox.new()
		scale_spin.min_value = 0.50
		scale_spin.max_value = 1.75
		scale_spin.step = 0.05
		scale_spin.value = 1.0
		scale_spin.value_changed.connect(_on_live_changed)
		grid.add_child(scale_spin)
		var rotation_spin: SpinBox = SpinBox.new()
		rotation_spin.min_value = -20.0
		rotation_spin.max_value = 20.0
		rotation_spin.step = 0.5
		rotation_spin.suffix = "°"
		rotation_spin.value_changed.connect(_on_live_changed)
		grid.add_child(rotation_spin)
		var lock_check: CheckBox = CheckBox.new()
		lock_check.text = "Bloqué"
		lock_check.toggled.connect(_on_live_changed)
		grid.add_child(lock_check)
		var reset_button: Button = Button.new()
		reset_button.text = "Reset"
		reset_button.pressed.connect(_reset_edit_group.bind(edit_group))
		grid.add_child(reset_button)
		direct_transform_controls[edit_group] = {"scale": scale_spin, "rotation": rotation_spin, "lock": lock_check}
	var reset_all: Button = Button.new()
	reset_all.text = "Réinitialiser toutes les transformations directes"
	reset_all.pressed.connect(_reset_direct_transforms)
	panel.add_child(reset_all)
	var note: Label = Label.new()
	note.text = "Ces valeurs sont les mêmes que celles manipulées graphiquement dans l’aperçu. Les proportions de Morphologie restent indépendantes : elles définissent la silhouette, tandis que l’édition directe sert à ajuster la composition finale."
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(note)


func _build_asymmetry_tab(tabs: TabContainer) -> void:
	var panel: VBoxContainer = _tab_panel(tabs, "Asymétrie G/D")
	asymmetry_check = CheckBox.new()
	asymmetry_check.text = "Activer les variantes indépendantes gauche / droite"
	asymmetry_check.toggled.connect(_on_live_changed)
	panel.add_child(asymmetry_check)
	var note: Label = Label.new()
	note.text = "Vide = même pièce que la base. 'Aucun' masque explicitement cette couche sur un profil. Les vues Face/Dos utilisent toujours la pièce de base."
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(note)
	var grid: GridContainer = GridContainer.new()
	grid.columns = 3
	panel.add_child(grid)
	_add_label(grid, "Couche")
	_add_label(grid, "Vue gauche")
	_add_label(grid, "Vue droite")
	for spec: Array in DIRECTIONAL_OVERRIDE_SPECS:
		var category: String = String(spec[0])
		_add_label(grid, String(spec[1]))
		var left_option: OptionButton = _direction_override_option(category)
		left_option.item_selected.connect(_on_live_changed)
		grid.add_child(left_option)
		var right_option: OptionButton = _direction_override_option(category)
		right_option.item_selected.connect(_on_live_changed)
		grid.add_child(right_option)
		direction_override_controls[category] = {"left": left_option, "right": right_option}


func _direction_override_option(category: String) -> OptionButton:
	var option: OptionButton = OptionButton.new()
	option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	option.add_item("Même que base")
	option.set_item_metadata(0, "")
	option.add_item("Aucun")
	option.set_item_metadata(1, "none")
	for part_id: String in HERO_COMPOSITOR_SCRIPT.available_part_ids(category):
		if part_id == "none":
			continue
		option.add_item(_friendly_name(part_id))
		option.set_item_metadata(option.item_count - 1, part_id)
	return option


func _build_parts_tab(tabs: TabContainer, tab_name: String, categories: Array[String], colors: Array[String]) -> void:
	var panel: VBoxContainer = _tab_panel(tabs, tab_name)
	var parts_grid: GridContainer = GridContainer.new()
	parts_grid.columns = 2
	panel.add_child(parts_grid)
	for category: String in categories:
		var label_text: String = _part_label(category)
		_add_label(parts_grid, label_text)
		var option_row: HBoxContainer = HBoxContainer.new()
		parts_grid.add_child(option_row)
		var option: OptionButton = OptionButton.new()
		option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		option.item_selected.connect(_on_part_option_changed.bind(category))
		option_row.add_child(option)
		part_controls[category] = option
		var favorite_button: Button = Button.new()
		favorite_button.toggle_mode = true
		favorite_button.text = "☆"
		favorite_button.tooltip_text = "Ajouter / retirer la pièce active des favoris"
		favorite_button.toggled.connect(_on_favorite_toggled.bind(category))
		option_row.add_child(favorite_button)
		favorite_controls[category] = favorite_button
	for category: String in categories:
		var gallery_title: Label = Label.new()
		gallery_title.text = "Galerie — %s" % _part_label(category)
		gallery_title.add_theme_font_size_override("font_size", 14)
		panel.add_child(gallery_title)
		var gallery_scroll: ScrollContainer = ScrollContainer.new()
		gallery_scroll.custom_minimum_size.y = 122.0
		gallery_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		panel.add_child(gallery_scroll)
		var gallery: GridContainer = GridContainer.new()
		gallery.columns = 3
		gallery.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		gallery_scroll.add_child(gallery)
		gallery_grids[category] = gallery
	var colors_grid: GridContainer = GridContainer.new()
	colors_grid.columns = 2
	panel.add_child(colors_grid)
	for property_name: String in colors:
		_add_color_control(colors_grid, property_name)


func _build_global_tab(tabs: TabContainer) -> void:
	var panel: VBoxContainer = _tab_panel(tabs, "Rendu")
	var grid: GridContainer = GridContainer.new()
	grid.columns = 2
	panel.add_child(grid)
	_add_color_control(grid, "global_tint")
	_add_label(grid, "Échelle en combat")
	scale_edit = SpinBox.new()
	scale_edit.min_value = 0.1
	scale_edit.max_value = 2.0
	scale_edit.step = 0.05
	scale_edit.value_changed.connect(_on_live_changed)
	grid.add_child(scale_edit)
	var note: Label = Label.new()
	note.text = "La taille morphologique modifie le dessin dans son cadre 192×192. L'échelle en combat reste indépendante et contrôle la taille finale affichée par le runtime."
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(note)


func _build_palette_tab(tabs: TabContainer) -> void:
	var panel: VBoxContainer = _tab_panel(tabs, "Profils couleur")
	var intro: Label = Label.new()
	intro.text = "Les profils couleur enregistrent uniquement la palette : pièces, morphologie, asymétrie et identité du héros ne sont jamais modifiées lors de l’application."
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(intro)
	var grid: GridContainer = GridContainer.new()
	grid.columns = 2
	panel.add_child(grid)
	_add_label(grid, "Profil")
	palette_select = OptionButton.new()
	palette_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_child(palette_select)
	_add_label(grid, "Nom nouveau profil")
	palette_name_edit = LineEdit.new()
	palette_name_edit.placeholder_text = "Ex. Cuivre toxique"
	palette_name_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_child(palette_name_edit)
	var buttons: HBoxContainer = HBoxContainer.new()
	panel.add_child(buttons)
	var save_button: Button = Button.new()
	save_button.text = "Sauver palette"
	save_button.pressed.connect(_save_palette_profile)
	buttons.add_child(save_button)
	var apply_button: Button = Button.new()
	apply_button.text = "Appliquer palette"
	apply_button.pressed.connect(_apply_selected_palette)
	buttons.add_child(apply_button)
	var refresh_button: Button = Button.new()
	refresh_button.text = "Rafraîchir"
	refresh_button.pressed.connect(_refresh_palettes)
	buttons.add_child(refresh_button)


func _build_presets_tab(tabs: TabContainer) -> void:
	var panel: VBoxContainer = _tab_panel(tabs, "Presets / Duplication")
	var intro: Label = Label.new()
	intro.text = "Enregistre un look réutilisable, applique-le à un héros ou duplique directement l'apparence vers un autre héros joueur."
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(intro)
	var grid: GridContainer = GridContainer.new()
	grid.columns = 2
	panel.add_child(grid)
	_add_label(grid, "Preset enregistré")
	preset_select = OptionButton.new()
	preset_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_child(preset_select)
	_add_label(grid, "Nom du nouveau preset")
	preset_name_edit = LineEdit.new()
	preset_name_edit.placeholder_text = "Ex. Momo aventurier violet"
	preset_name_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_child(preset_name_edit)
	var preset_buttons: HBoxContainer = HBoxContainer.new()
	panel.add_child(preset_buttons)
	var save_preset: Button = Button.new()
	save_preset.text = "Sauver le look en preset"
	save_preset.pressed.connect(_save_user_preset)
	preset_buttons.add_child(save_preset)
	var apply_preset: Button = Button.new()
	apply_preset.text = "Appliquer le preset"
	apply_preset.pressed.connect(_apply_selected_preset)
	preset_buttons.add_child(apply_preset)
	var refresh_presets: Button = Button.new()
	refresh_presets.text = "Rafraîchir"
	refresh_presets.pressed.connect(_refresh_presets)
	preset_buttons.add_child(refresh_presets)
	var separator: HSeparator = HSeparator.new()
	panel.add_child(separator)
	var copy_title: Label = Label.new()
	copy_title.text = "DUPLIQUER L'APPARENCE VERS UN AUTRE HÉROS"
	copy_title.add_theme_font_size_override("font_size", 14)
	panel.add_child(copy_title)
	var copy_grid: GridContainer = GridContainer.new()
	copy_grid.columns = 2
	panel.add_child(copy_grid)
	_add_label(copy_grid, "Héros cible")
	copy_target_select = OptionButton.new()
	copy_target_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	copy_grid.add_child(copy_target_select)
	var duplicate_button: Button = Button.new()
	duplicate_button.text = "Dupliquer + générer sur le héros cible"
	duplicate_button.pressed.connect(_duplicate_to_target)
	panel.add_child(duplicate_button)
	var exchange_separator: HSeparator = HSeparator.new()
	panel.add_child(exchange_separator)
	var exchange_title: Label = Label.new()
	exchange_title.text = "ÉCHANGE DE LOOKS (.tres)"
	exchange_title.add_theme_font_size_override("font_size", 14)
	panel.add_child(exchange_title)
	var exchange_grid: GridContainer = GridContainer.new()
	exchange_grid.columns = 2
	panel.add_child(exchange_grid)
	_add_label(exchange_grid, "Nom export")
	export_name_edit = LineEdit.new()
	export_name_edit.placeholder_text = "Ex. héros violet final"
	exchange_grid.add_child(export_name_edit)
	_add_label(exchange_grid, "Look disponible")
	export_select = OptionButton.new()
	export_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	exchange_grid.add_child(export_select)
	var exchange_buttons: HBoxContainer = HBoxContainer.new()
	panel.add_child(exchange_buttons)
	var export_button: Button = Button.new()
	export_button.text = "Exporter le look"
	export_button.pressed.connect(_export_current_look)
	exchange_buttons.add_child(export_button)
	var import_button: Button = Button.new()
	import_button.text = "Importer le look"
	import_button.pressed.connect(_import_selected_look)
	exchange_buttons.add_child(import_button)
	var refresh_exports_button: Button = Button.new()
	refresh_exports_button.text = "Rafraîchir"
	refresh_exports_button.pressed.connect(_refresh_exports)
	exchange_buttons.add_child(refresh_exports_button)

	var note: Label = Label.new()
	note.text = "Presets et exports conservent pièces, couleurs, morphologie, offsets et transformations. À l’import, l’identité et les chemins de sortie du héros actif sont protégés."
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(note)


func _tab_panel(tabs: TabContainer, tab_name: String) -> VBoxContainer:
	var scroll: ScrollContainer = ScrollContainer.new()
	scroll.name = tab_name
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tabs.add_child(scroll)
	var panel: VBoxContainer = VBoxContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(panel)
	return panel


func _metadata_option(entries: Array) -> OptionButton:
	var option: OptionButton = OptionButton.new()
	option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for entry: Array in entries:
		option.add_item(String(entry[0]))
		option.set_item_metadata(option.item_count - 1, String(entry[1]))
	return option


func _add_color_control(parent: Control, property_name: String) -> void:
	_add_label(parent, _color_label(property_name))
	var picker: ColorPickerButton = ColorPickerButton.new()
	picker.custom_minimum_size = Vector2(150.0, 34.0)
	picker.color_changed.connect(_on_live_changed)
	parent.add_child(picker)
	color_controls[property_name] = picker


func _refresh_heroes() -> void:
	var wanted: String = "momo"
	if hero_select.item_count > 0 and hero_select.selected >= 0:
		wanted = String(hero_select.get_item_metadata(hero_select.selected))
	hero_select.clear()
	var paths: Array[String] = _resource_files(UNIT_DIR)
	for path: String in paths:
		var unit: Resource = load(path)
		if unit == null or String(unit.get("team")) != "player":
			continue
		var hero_id: String = String(unit.get("id"))
		hero_select.add_item("%s [%s]" % [String(unit.get("display_name")), hero_id])
		hero_select.set_item_metadata(hero_select.item_count - 1, hero_id)
	var selected_index: int = _metadata_index(hero_select, wanted)
	if selected_index < 0:
		selected_index = _metadata_index(hero_select, "momo")
	if selected_index < 0 and hero_select.item_count > 0:
		selected_index = 0
	if selected_index >= 0:
		hero_select.select(selected_index)
		_on_hero_selected(selected_index)
	_refresh_copy_targets()


func _refresh_copy_targets() -> void:
	if copy_target_select == null:
		return
	var current_id: String = ""
	if hero_select.item_count > 0 and hero_select.selected >= 0:
		current_id = String(hero_select.get_item_metadata(hero_select.selected))
	copy_target_select.clear()
	for index: int in range(hero_select.item_count):
		var hero_id: String = String(hero_select.get_item_metadata(index))
		copy_target_select.add_item(hero_select.get_item_text(index))
		copy_target_select.set_item_metadata(copy_target_select.item_count - 1, hero_id)
	if copy_target_select.item_count > 1:
		for index: int in range(copy_target_select.item_count):
			if String(copy_target_select.get_item_metadata(index)) != current_id:
				copy_target_select.select(index)
				break


func _on_hero_selected(index: int) -> void:
	if loading or index < 0 or index >= hero_select.item_count:
		return
	if dirty:
		_save_definition(false)
	var hero_id: String = String(hero_select.get_item_metadata(index))
	current_path = APPEARANCE_DIR + hero_id + ".tres"
	if ResourceLoader.exists(current_path):
		current = load(current_path)
	else:
		current = _new_appearance(hero_id)
	if current != null and current.has_method("migrate_legacy_fields"):
		current.call("migrate_legacy_fields")
	_populate_part_options()
	_load_current_into_ui()
	_clear_history()
	_capture_reference(false)
	_refresh_copy_targets()
	_refresh_exports()


func _new_appearance(hero_id: String) -> Resource:
	var appearance: Resource = APPEARANCE_DEFINITION_SCRIPT.new()
	appearance.set("hero_id", hero_id)
	appearance.set("target_visual_id", hero_id)
	appearance.set("display_name", "%s personnalisé" % hero_id.capitalize())
	appearance.set("generated_sprite_sheet_path", "res://assets/generated/heroes/%s_custom.png" % hero_id)
	appearance.set("generated_portrait_path", "res://assets/generated/heroes/%s_custom_portrait.png" % hero_id)
	return appearance


func _populate_part_options() -> void:
	for spec: Array in PART_SPECS:
		var category: String = String(spec[0])
		var option: OptionButton = part_controls.get(category) as OptionButton
		if option == null:
			continue
		option.clear()
		if OPTIONAL_CATEGORIES.has(category):
			option.add_item("Aucun")
			option.set_item_metadata(option.item_count - 1, "none")
		var ids: PackedStringArray = HERO_COMPOSITOR_SCRIPT.available_part_ids(category)
		for part_id: String in ids:
			if part_id == "none":
				continue
			option.add_item(_friendly_name(part_id))
			option.set_item_metadata(option.item_count - 1, part_id)
		_populate_gallery(category)


func _populate_gallery(category: String) -> void:
	var gallery: GridContainer = gallery_grids.get(category) as GridContainer
	var option: OptionButton = part_controls.get(category) as OptionButton
	if gallery == null or option == null:
		return
	for child: Node in gallery.get_children():
		gallery.remove_child(child)
		child.queue_free()
	var buttons: Array = []
	var ordered_indices: Array[int] = []
	for index: int in range(option.item_count):
		if String(option.get_item_metadata(index)) == "none":
			ordered_indices.append(index)
	for index: int in range(option.item_count):
		var candidate_id: String = String(option.get_item_metadata(index))
		if candidate_id != "none" and _is_favorite(category, candidate_id):
			ordered_indices.append(index)
	for index: int in range(option.item_count):
		var candidate_id: String = String(option.get_item_metadata(index))
		if candidate_id != "none" and not _is_favorite(category, candidate_id):
			ordered_indices.append(index)
	for index: int in ordered_indices:
		var part_id: String = String(option.get_item_metadata(index))
		var button: Button = Button.new()
		button.toggle_mode = true
		button.custom_minimum_size = Vector2(185.0, 102.0)
		button.text = ("★ " if _is_favorite(category, part_id) else "") + _friendly_name(part_id)
		button.tooltip_text = "%s — %s" % [_part_label(category), _friendly_name(part_id)]
		button.set_meta("part_id", part_id)
		if part_id != "none":
			var image: Image = HERO_COMPOSITOR_SCRIPT.compose_part_thumbnail(category, part_id, "front", Color.WHITE)
			button.icon = ImageTexture.create_from_image(image)
		button.pressed.connect(_on_gallery_part_pressed.bind(category, part_id))
		gallery.add_child(button)
		buttons.append(button)
	gallery_buttons[category] = buttons
	_sync_gallery_selection(category)


func _on_gallery_part_pressed(category: String, part_id: String) -> void:
	if loading:
		return
	_select_part(category, part_id)
	_sync_gallery_selection(category)
	_on_live_changed()


func _on_part_option_changed(_index: int, category: String) -> void:
	if loading:
		return
	_sync_gallery_selection(category)
	_on_live_changed()


func _sync_gallery_selection(category: String) -> void:
	var option: OptionButton = part_controls.get(category) as OptionButton
	if option == null or option.item_count == 0 or option.selected < 0:
		return
	var selected_id: String = String(option.get_item_metadata(option.selected))
	var buttons: Array = gallery_buttons.get(category, [])
	for raw_button: Variant in buttons:
		var button: Button = raw_button as Button
		if button != null:
			button.button_pressed = String(button.get_meta("part_id")) == selected_id
	_sync_favorite_control(category)


func _sync_all_galleries() -> void:
	for spec: Array in PART_SPECS:
		_sync_gallery_selection(String(spec[0]))


func _load_current_into_ui() -> void:
	if current == null:
		return
	loading = true
	display_name_edit.text = String(current.get("display_name"))
	_select_metadata(presentation_select, String(current.get("presentation_style")))
	_select_metadata(archetype_select, String(current.get("archetype_style")))
	_select_metadata(size_preset_select, String(current.get("size_preset")))
	_select_metadata(silhouette_preset_select, String(current.get("silhouette_preset")))
	if proportions_lock_check != null:
		proportions_lock_check.button_pressed = bool(current.get("proportions_locked"))
	if expressions_enabled_check != null:
		expressions_enabled_check.button_pressed = bool(current.get("expressions_enabled"))
	for spec: Array in EXPRESSION_SPECS:
		var expression_property: String = String(spec[0])
		var expression_option: OptionButton = expression_controls.get(expression_property) as OptionButton
		if expression_option != null:
			_select_metadata(expression_option, String(current.get(expression_property)))
	if portrait_direction_select != null:
		_select_metadata(portrait_direction_select, String(current.get("portrait_direction")))
	if portrait_zoom_edit != null:
		portrait_zoom_edit.value = _float_resource_property(current, "portrait_zoom", 1.10)
	var portrait_offset_value: Variant = current.get("portrait_offset")
	var portrait_offset: Vector2 = portrait_offset_value if portrait_offset_value is Vector2 else Vector2(0.0, 6.0)
	if portrait_offset_x != null:
		portrait_offset_x.value = portrait_offset.x
	if portrait_offset_y != null:
		portrait_offset_y.value = portrait_offset.y
	for spec: Array in PART_SPECS:
		var category: String = String(spec[0])
		var option: OptionButton = part_controls.get(category) as OptionButton
		var value: String = String(current.call("part_id", category))
		_select_metadata(option, value)
	for spec: Array in COLOR_SPECS:
		var property_name: String = String(spec[0])
		var picker: ColorPickerButton = color_controls.get(property_name) as ColorPickerButton
		var color_value: Variant = current.get(property_name)
		if picker != null and color_value is Color:
			picker.color = color_value
	for spec: Array in MORPH_SPECS:
		var property_name: String = String(spec[0])
		var spin: SpinBox = morph_controls.get(property_name) as SpinBox
		if spin != null:
			spin.value = float(current.get(property_name))
	for spec: Array in OFFSET_SPECS:
		var property_name: String = String(spec[0])
		var controls: Dictionary = offset_controls.get(property_name, {})
		var value: Variant = current.get(property_name)
		var offset: Vector2 = value if value is Vector2 else Vector2.ZERO
		var x_spin: SpinBox = controls.get("x") as SpinBox
		var y_spin: SpinBox = controls.get("y") as SpinBox
		if x_spin != null:
			x_spin.value = offset.x
		if y_spin != null:
			y_spin.value = offset.y
	for spec: Array in DIRECT_TRANSFORM_SPECS:
		var edit_group: String = String(spec[0])
		var transform_controls: Dictionary = direct_transform_controls.get(edit_group, {})
		var scale_spin: SpinBox = transform_controls.get("scale") as SpinBox
		var rotation_spin: SpinBox = transform_controls.get("rotation") as SpinBox
		var lock_check: CheckBox = transform_controls.get("lock") as CheckBox
		if scale_spin != null:
			scale_spin.value = _float_resource_property(current, String(spec[3]), 1.0)
		if rotation_spin != null:
			rotation_spin.value = _float_resource_property(current, String(spec[4]), 0.0)
		if lock_check != null:
			lock_check.button_pressed = bool(current.get(String(spec[5])))
	if asymmetry_check != null:
		asymmetry_check.button_pressed = bool(current.get("asymmetry_enabled"))
	for spec: Array in DIRECTIONAL_OVERRIDE_SPECS:
		var category: String = String(spec[0])
		var controls: Dictionary = direction_override_controls.get(category, {})
		for side: String in ["left", "right"]:
			var option: OptionButton = controls.get(side) as OptionButton
			if option != null:
				_select_metadata(option, String(current.get("%s_%s_style" % [side, category])))
	scale_edit.value = float(current.get("sprite_scale"))
	loading = false
	dirty = false
	_sync_all_galleries()
	preview.set_appearance(current)
	_sync_preview_locks()
	if edit_group_select != null:
		preview.set_selected_edit_group(_selected_metadata(edit_group_select))
	_set_status("Prêt — V1.26. Expressions par état, portraits, silhouettes fortes et palettes réutilisables sont actifs.", false)


func _write_ui_to_current() -> void:
	if current == null:
		return
	current.set("display_name", display_name_edit.text.strip_edges())
	current.set("presentation_style", _selected_metadata(presentation_select))
	current.set("archetype_style", _selected_metadata(archetype_select))
	current.set("size_preset", _selected_metadata(size_preset_select))
	current.set("silhouette_preset", _selected_metadata(silhouette_preset_select))
	current.set("proportions_locked", proportions_lock_check.button_pressed if proportions_lock_check != null else false)
	current.set("expressions_enabled", expressions_enabled_check.button_pressed if expressions_enabled_check != null else true)
	for spec: Array in EXPRESSION_SPECS:
		var expression_property: String = String(spec[0])
		var expression_option: OptionButton = expression_controls.get(expression_property) as OptionButton
		if expression_option != null:
			current.set(expression_property, _selected_metadata(expression_option))
	if portrait_direction_select != null:
		current.set("portrait_direction", _selected_metadata(portrait_direction_select))
	if portrait_zoom_edit != null:
		current.set("portrait_zoom", float(portrait_zoom_edit.value))
	if portrait_offset_x != null and portrait_offset_y != null:
		current.set("portrait_offset", Vector2(float(portrait_offset_x.value), float(portrait_offset_y.value)))
	for spec: Array in PART_SPECS:
		var category: String = String(spec[0])
		var option: OptionButton = part_controls.get(category) as OptionButton
		if option == null or option.item_count == 0 or option.selected < 0:
			continue
		var value: String = String(option.get_item_metadata(option.selected))
		match category:
			"body": current.set("body_style", value)
			"head_shape": current.set("head_shape_style", value)
			"head_pattern": current.set("head_pattern_style", value)
			"ears": current.set("ears_style", value)
			"horns": current.set("horns_style", value)
			"hair": current.set("hair_style", value)
			"eyes": current.set("eyes_style", value)
			"iris": current.set("iris_style", value)
			"pupil": current.set("pupil_style", value)
			"brows": current.set("brows_style", value)
			"nose": current.set("nose_style", value)
			"skin_spots": current.set("skin_spots_style", value)
			"mouth": current.set("mouth_style", value)
			"teeth": current.set("teeth_style", value)
			"facial_hair": current.set("facial_hair_style", value)
			"mark": current.set("mark_style", value)
			"mark_2": current.set("mark_2_style", value)
			"mark_3": current.set("mark_3_style", value)
			"earrings": current.set("earrings_style", value)
			"jewelry": current.set("jewelry_style", value)
			"top": current.set("top_style", value)
			"bottom": current.set("bottom_style", value)
			"accessory": current.set("accessory_style", value)
			"accessory_2": current.set("accessory_2_style", value)
			"accessory_3": current.set("accessory_3_style", value)
			"weapon": current.set("weapon_style", value)
	for spec: Array in COLOR_SPECS:
		var property_name: String = String(spec[0])
		var picker: ColorPickerButton = color_controls.get(property_name) as ColorPickerButton
		if picker != null:
			current.set(property_name, picker.color)
	for spec: Array in MORPH_SPECS:
		var property_name: String = String(spec[0])
		var spin: SpinBox = morph_controls.get(property_name) as SpinBox
		if spin != null:
			current.set(property_name, float(spin.value))
	for spec: Array in OFFSET_SPECS:
		var property_name: String = String(spec[0])
		var controls: Dictionary = offset_controls.get(property_name, {})
		var x_spin: SpinBox = controls.get("x") as SpinBox
		var y_spin: SpinBox = controls.get("y") as SpinBox
		if x_spin != null and y_spin != null:
			current.set(property_name, Vector2(float(x_spin.value), float(y_spin.value)))
	for spec: Array in DIRECT_TRANSFORM_SPECS:
		var edit_group: String = String(spec[0])
		var transform_controls: Dictionary = direct_transform_controls.get(edit_group, {})
		var scale_spin: SpinBox = transform_controls.get("scale") as SpinBox
		var rotation_spin: SpinBox = transform_controls.get("rotation") as SpinBox
		var lock_check: CheckBox = transform_controls.get("lock") as CheckBox
		if scale_spin != null:
			current.set(String(spec[3]), float(scale_spin.value))
		if rotation_spin != null:
			current.set(String(spec[4]), float(rotation_spin.value))
		if lock_check != null:
			current.set(String(spec[5]), lock_check.button_pressed)
	if asymmetry_check != null:
		current.set("asymmetry_enabled", asymmetry_check.button_pressed)
	for spec: Array in DIRECTIONAL_OVERRIDE_SPECS:
		var category: String = String(spec[0])
		var controls: Dictionary = direction_override_controls.get(category, {})
		for side: String in ["left", "right"]:
			var option: OptionButton = controls.get(side) as OptionButton
			if option != null:
				current.set("%s_%s_style" % [side, category], _selected_metadata(option))
	current.set("sprite_scale", float(scale_edit.value))


func _on_live_changed(_value: Variant = null) -> void:
	if loading or current == null:
		return
	_push_undo_snapshot()
	_write_ui_to_current()
	dirty = true
	preview.set_appearance(current)
	_sync_preview_locks()
	_set_status("Modifications non enregistrées.", false)


func _on_presentation_changed(index: int) -> void:
	if loading or index < 0:
		return
	_apply_presentation_preset(_selected_metadata(presentation_select))
	_sync_all_galleries()
	_on_live_changed()


func _apply_presentation_preset(style: String) -> void:
	match style:
		"masculine":
			_select_part("body", "rugged")
			_set_morph_value("body_width_scale", 1.08)
			_set_morph_value("head_scale", 0.98)
		"feminine":
			_select_part("body", "curvy")
			_set_morph_value("body_width_scale", 0.92)
			_set_morph_value("head_scale", 1.05)
		"creature":
			_select_part("body", "stout")
			_select_part("head_shape", "mutant")
			_set_morph_value("body_width_scale", 1.12)
			_set_morph_value("head_scale", 1.12)
			_set_morph_value("head_width_scale", 1.12)
		_:
			_select_part("body", "classic")
			_set_morph_value("body_width_scale", 1.0)
			_set_morph_value("head_scale", 1.0)


func _on_archetype_changed(index: int) -> void:
	if loading or index < 0:
		return
	_apply_archetype_preset(_selected_metadata(archetype_select))
	_sync_all_galleries()
	_on_live_changed()


func _apply_archetype_preset(style: String) -> void:
	match style:
		"mage":
			_select_part("top", "poncho")
			_select_part("weapon", "wand")
			_select_part("eyes", "big")
			_select_part("iris", "glow")
			_select_part("pupil", "diamond")
		"warrior":
			_select_part("top", "armor")
			_select_part("weapon", "sword")
			_select_part("eyes", "angry")
			_select_part("brows", "angry")
			_select_part("mark", "scar_left")
		"rogue":
			_select_part("top", "hoodie")
			_select_part("weapon", "sword")
			_select_part("eyes", "narrow")
			_select_part("pupil", "slit")
		"funky":
			_select_part("top", "poncho")
			_select_part("accessory", "goggles")
			_select_part("eyes", "cute")
			_select_part("iris", "star")
			_select_part("earrings", "hoop")
		"ancient":
			_select_part("top", "poncho")
			_select_part("weapon", "wand")
			_select_part("facial_hair", "long_beard")
			_select_part("brows", "bushy")
			_select_part("jewelry", "amulet")
		"mechanical":
			_select_part("top", "armor")
			_select_part("weapon", "rifle")
			_select_part("eyes", "robotic")
			_select_part("pupil", "square")
			_select_part("jewelry", "chain")
		_:
			_select_part("top", "vest")
			_select_part("weapon", "sword")


func _on_size_preset_changed(index: int) -> void:
	if loading or index < 0:
		return
	var preset: String = _selected_metadata(size_preset_select)
	match preset:
		"small":
			_set_morph_value("global_scale", 0.95)
			_set_morph_value("head_scale", 1.08)
		"large":
			_set_morph_value("global_scale", 1.05)
			_set_morph_value("head_scale", 0.96)
		_:
			_set_morph_value("global_scale", 1.0)
	_on_live_changed()


func _on_silhouette_preset_changed(index: int) -> void:
	if loading or index < 0:
		return
	_apply_silhouette_preset(_selected_metadata(silhouette_preset_select))
	_on_live_changed()


func _apply_silhouette_preset(preset: String) -> void:
	var was_loading: bool = loading
	loading = true
	match preset:
		"chibi":
			_set_morph_value("global_scale", 0.90)
			_set_morph_value("body_width_scale", 0.95)
			_set_morph_value("body_height_scale", 0.82)
			_set_morph_value("head_scale", 1.28)
			_set_morph_value("head_width_scale", 1.15)
		"colossus":
			_set_morph_value("global_scale", 1.18)
			_set_morph_value("body_width_scale", 1.22)
			_set_morph_value("body_height_scale", 1.18)
			_set_morph_value("head_scale", 0.90)
			_set_morph_value("head_width_scale", 1.00)
		"slender":
			_set_morph_value("global_scale", 1.04)
			_set_morph_value("body_width_scale", 0.78)
			_set_morph_value("body_height_scale", 1.18)
			_set_morph_value("head_scale", 0.96)
			_set_morph_value("head_width_scale", 0.90)
		"big_spore":
			_set_morph_value("global_scale", 1.00)
			_set_morph_value("body_width_scale", 0.95)
			_set_morph_value("body_height_scale", 0.95)
			_set_morph_value("head_scale", 1.25)
			_set_morph_value("head_width_scale", 1.35)
		"tank":
			_set_morph_value("global_scale", 1.08)
			_set_morph_value("body_width_scale", 1.35)
			_set_morph_value("body_height_scale", 0.92)
			_set_morph_value("head_scale", 1.02)
			_set_morph_value("head_width_scale", 1.18)
		_:
			_set_morph_value("global_scale", 1.00)
			_set_morph_value("body_width_scale", 1.00)
			_set_morph_value("body_height_scale", 1.00)
			_set_morph_value("head_scale", 1.00)
			_set_morph_value("head_width_scale", 1.00)
	loading = was_loading


func _on_proportions_lock_toggled(_enabled: bool) -> void:
	if loading:
		return
	_on_live_changed()


func _on_morph_value_changed(value: float, property_name: String) -> void:
	if loading:
		return
	if proportions_lock_check != null and proportions_lock_check.button_pressed:
		loading = true
		match property_name:
			"body_width_scale": _set_morph_value("body_height_scale", value)
			"body_height_scale": _set_morph_value("body_width_scale", value)
			"head_scale": _set_morph_value("head_width_scale", value)
			"head_width_scale": _set_morph_value("head_scale", value)
		loading = false
	_on_live_changed()


func _apply_expression_preset(preset: String) -> void:
	if current == null:
		return
	_push_undo_snapshot()
	var values: Dictionary = {}
	match preset:
		"base":
			values = {"idle_expression":"base", "move_expression":"base", "attack_expression":"base", "cast_expression":"base", "hit_expression":"base", "ko_expression":"base", "portrait_expression":"base"}
		"heroic":
			values = {"idle_expression":"heroic", "move_expression":"focused", "attack_expression":"angry", "cast_expression":"mystic", "hit_expression":"hurt", "ko_expression":"ko", "portrait_expression":"heroic"}
		_:
			values = {"idle_expression":"heroic", "move_expression":"focused", "attack_expression":"angry", "cast_expression":"mystic", "hit_expression":"hurt", "ko_expression":"ko", "portrait_expression":"cheerful"}
	loading = true
	for property_name: String in values.keys():
		var option: OptionButton = expression_controls.get(property_name) as OptionButton
		if option != null:
			_select_metadata(option, String(values[property_name]))
	if expressions_enabled_check != null:
		expressions_enabled_check.button_pressed = true
	loading = false
	_on_live_changed()
	_set_status("Preset d’expressions appliqué.", false)


func _on_direction_selected(index: int) -> void:
	if index < 0 or index >= direction_select.item_count:
		return
	preview.set_direction(String(direction_select.get_item_metadata(index)))


func _on_preview_state_selected(index: int) -> void:
	if preview_state_select == null or index < 0 or index >= preview_state_select.item_count:
		return
	preview.set_state(String(preview_state_select.get_item_metadata(index)))


func _on_preview_zoom_changed(value: float) -> void:
	preview.set_zoom(value)


func _on_edit_group_selected(index: int) -> void:
	if index < 0 or edit_group_select == null or index >= edit_group_select.item_count:
		return
	preview.set_selected_edit_group(String(edit_group_select.get_item_metadata(index)))


func _on_preview_group_selected(edit_group: String) -> void:
	_select_metadata(edit_group_select, edit_group)
	preview.set_selected_edit_group(edit_group)
	_set_status("Groupe '%s' sélectionné pour l’édition directe." % _edit_group_label(edit_group), false)


func _on_preview_transform_delta(edit_group: String, offset_delta: Vector2, scale_factor: float, rotation_delta: float) -> void:
	if current == null:
		return
	var spec: Array = _direct_transform_spec(edit_group)
	if spec.is_empty():
		return
	var transform_controls: Dictionary = direct_transform_controls.get(edit_group, {})
	var lock_check: CheckBox = transform_controls.get("lock") as CheckBox
	if lock_check != null and lock_check.button_pressed:
		return
	var was_loading: bool = loading
	loading = true
	var offset_property: String = String(spec[2])
	var offset_ui: Dictionary = offset_controls.get(offset_property, {})
	var x_spin: SpinBox = offset_ui.get("x") as SpinBox
	var y_spin: SpinBox = offset_ui.get("y") as SpinBox
	if x_spin != null and y_spin != null and not offset_delta.is_equal_approx(Vector2.ZERO):
		x_spin.value = clampf(float(x_spin.value) + offset_delta.x, float(x_spin.min_value), float(x_spin.max_value))
		y_spin.value = clampf(float(y_spin.value) + offset_delta.y, float(y_spin.min_value), float(y_spin.max_value))
	var scale_spin: SpinBox = transform_controls.get("scale") as SpinBox
	if scale_spin != null and not is_equal_approx(scale_factor, 1.0):
		scale_spin.value = clampf(float(scale_spin.value) * scale_factor, float(scale_spin.min_value), float(scale_spin.max_value))
	var rotation_spin: SpinBox = transform_controls.get("rotation") as SpinBox
	if rotation_spin != null and not is_zero_approx(rotation_delta):
		rotation_spin.value = clampf(float(rotation_spin.value) + rotation_delta, float(rotation_spin.min_value), float(rotation_spin.max_value))
	loading = was_loading
	if not loading:
		_on_live_changed()


func _sync_preview_locks() -> void:
	if preview == null:
		return
	for spec: Array in DIRECT_TRANSFORM_SPECS:
		var edit_group: String = String(spec[0])
		var controls: Dictionary = direct_transform_controls.get(edit_group, {})
		var lock_check: CheckBox = controls.get("lock") as CheckBox
		preview.set_group_locked(edit_group, lock_check != null and lock_check.button_pressed)


func _save_definition(generate: bool = false) -> void:
	if current == null or current_path.is_empty():
		return
	_write_ui_to_current()
	var absolute_dir: String = ProjectSettings.globalize_path(APPEARANCE_DIR)
	if not DirAccess.dir_exists_absolute(absolute_dir):
		DirAccess.make_dir_recursive_absolute(absolute_dir)
	var save_error: Error = ResourceSaver.save(current, current_path)
	if save_error != OK:
		_set_status("Erreur de sauvegarde de l'apparence (%d)." % int(save_error), true)
		return
	dirty = false
	if not generate:
		_set_status("Apparence V1.26 enregistrée dans %s" % current_path, false)
		return
	var result: Dictionary = HERO_COMPOSITOR_SCRIPT.apply_to_visual(current)
	if not bool(result.get("ok", false)):
		var raw_errors: Variant = result.get("errors", PackedStringArray())
		var errors: PackedStringArray = raw_errors if raw_errors is PackedStringArray else PackedStringArray([String(raw_errors)])
		_set_status("ERREUR : " + " • ".join(errors), true)
		return
	if Engine.is_editor_hint():
		var filesystem: EditorFileSystem = EditorInterface.get_resource_filesystem()
		if filesystem != null:
			var generated_paths: PackedStringArray = PackedStringArray([
				String(current.get("generated_sprite_sheet_path")),
				String(current.get("generated_portrait_path")),
			])
			if not filesystem.is_importing():
				for generated_path: String in generated_paths:
					filesystem.update_file(generated_path)
				filesystem.reimport_files(generated_paths)
			else:
				filesystem.scan()
	_set_status("Héros généré : look V1.26 appliqué au visuel '%s'." % String(current.get("target_visual_id")), false)
	library_changed.emit()


func _randomize() -> void:
	if current == null:
		return
	loading = true
	presentation_select.select(randi_range(0, presentation_select.item_count - 1))
	archetype_select.select(randi_range(0, archetype_select.item_count - 1))
	size_preset_select.select(randi_range(0, size_preset_select.item_count - 1))
	silhouette_preset_select.select(randi_range(0, silhouette_preset_select.item_count - 1))
	_apply_presentation_preset(_selected_metadata(presentation_select))
	_apply_archetype_preset(_selected_metadata(archetype_select))
	_apply_silhouette_preset(_selected_metadata(silhouette_preset_select))
	var expression_choices: Array[String] = ["heroic", "cheerful", "mischief"]
	var idle_expression_choice: String = expression_choices[randi_range(0, expression_choices.size() - 1)]
	var expression_values: Dictionary = {
		"idle_expression": idle_expression_choice,
		"move_expression": "focused",
		"attack_expression": "angry",
		"cast_expression": "mystic",
		"hit_expression": "hurt",
		"ko_expression": "ko",
		"portrait_expression": idle_expression_choice,
	}
	for expression_property: String in expression_values.keys():
		var expression_option: OptionButton = expression_controls.get(expression_property) as OptionButton
		if expression_option != null:
			_select_metadata(expression_option, String(expression_values[expression_property]))
	if expressions_enabled_check != null:
		expressions_enabled_check.button_pressed = true
	_random_select_part("head_shape", false)
	_random_select_part("head_pattern", false)
	_random_select_part("ears", true, 0.45)
	_random_select_part("horns", true, 0.55)
	_random_select_part("hair", true, 0.18)
	_random_select_part("eyes", false)
	_random_select_part("iris", true, 0.08)
	_random_select_part("pupil", true, 0.08)
	_random_select_part("brows", true, 0.15)
	_random_select_part("nose", true, 0.22)
	_random_select_part("skin_spots", true, 0.58)
	_random_select_part("mouth", true, 0.12)
	_random_select_part("teeth", true, 0.72)
	_random_select_part("facial_hair", true, 0.42)
	_random_select_part("mark", true, 0.38)
	_random_select_part("mark_2", true, 0.78)
	_random_select_part("mark_3", true, 0.90)
	_random_select_part("earrings", true, 0.65)
	_random_select_part("jewelry", true, 0.62)
	_random_select_part("bottom", false)
	_random_select_part("accessory", true, 0.45)
	_random_select_part("accessory_2", true, 0.68)
	_random_select_part("accessory_3", true, 0.82)
	var palette: Dictionary = SMART_PALETTES[randi_range(0, SMART_PALETTES.size() - 1)]
	_set_color_value("head_primary_color", Color(String(palette["head1"])))
	_set_color_value("head_secondary_color", Color(String(palette["head2"])))
	_set_color_value("skin_color", Color(String(palette["skin"])))
	_set_color_value("top_color", Color(String(palette["top"])))
	_set_color_value("bottom_color", Color(String(palette["bottom"])))
	_set_color_value("accessory_color", Color(String(palette["accent"])))
	_set_color_value("accessory_2_color", Color(String(palette["head2"])))
	_set_color_value("accessory_3_color", Color(String(palette["head1"])))
	_set_color_value("ears_color", Color(String(palette["skin"])))
	_set_color_value("horns_color", Color("#d6c6a5"))
	_set_color_value("hair_color", Color("#4b2f28"))
	_set_color_value("weapon_color", Color("#cbd5e1"))
	_set_color_value("eyes_color", Color("#f8fafc"))
	_set_color_value("iris_color", Color(String(palette["accent"])))
	_set_color_value("pupil_color", Color("#17111f"))
	_set_color_value("brows_color", Color("#3f2b2a"))
	_set_color_value("nose_color", Color(String(palette["skin"])).darkened(0.12))
	_set_color_value("skin_spots_color", Color(String(palette["head1"])).lerp(Color(String(palette["skin"])), 0.45))
	_set_color_value("mouth_color", Color("#251c32"))
	_set_color_value("teeth_color", Color("#fff8e7"))
	_set_color_value("facial_hair_color", Color("#604635"))
	_set_color_value("mark_color", Color("#8b2635"))
	_set_color_value("mark_2_color", Color("#6d2837"))
	_set_color_value("mark_3_color", Color("#9f3a48"))
	_set_color_value("earrings_color", Color(String(palette["accent"])))
	_set_color_value("jewelry_color", Color(String(palette["accent"])))
	_set_color_value("global_tint", Color.WHITE)
	for spec: Array in MORPH_SPECS:
		var property_name: String = String(spec[0])
		var spin: SpinBox = morph_controls.get(property_name) as SpinBox
		if spin != null:
			var jittered: float = float(spin.value) + randf_range(-0.05, 0.05)
			spin.value = clampf(snappedf(jittered, 0.05), float(spin.min_value), float(spin.max_value))
	_reset_offsets(false)
	_reset_direct_transforms(false)
	if asymmetry_check != null:
		asymmetry_check.button_pressed = randf() < 0.30
	for spec: Array in DIRECTIONAL_OVERRIDE_SPECS:
		var controls: Dictionary = direction_override_controls.get(String(spec[0]), {})
		for side: String in ["left", "right"]:
			var option: OptionButton = controls.get(side) as OptionButton
			if option != null:
				option.select(0)
	if asymmetry_check != null and asymmetry_check.button_pressed:
		for spec: Array in DIRECTIONAL_OVERRIDE_SPECS:
			var controls: Dictionary = direction_override_controls.get(String(spec[0]), {})
			for side: String in ["left", "right"]:
				var option: OptionButton = controls.get(side) as OptionButton
				if option != null and option.item_count > 2 and randf() < 0.35:
					option.select(randi_range(1, option.item_count - 1))
	loading = false
	_sync_all_galleries()
	_on_live_changed()
	_set_status("Look aléatoire V1.26 généré : visage détaillé, silhouette, expressions et palette restent modifiables.", false)


func _random_select_part(category: String, allow_none: bool, none_probability: float = 0.0) -> void:
	var option: OptionButton = part_controls.get(category) as OptionButton
	if option == null or option.item_count == 0:
		return
	if allow_none and randf() < none_probability:
		var none_index: int = _metadata_index(option, "none")
		if none_index >= 0:
			option.select(none_index)
			return
	var candidates: Array[int] = []
	for index: int in range(option.item_count):
		if String(option.get_item_metadata(index)) != "none":
			candidates.append(index)
	if not candidates.is_empty():
		option.select(candidates[randi_range(0, candidates.size() - 1)])


func _set_color_value(property_name: String, color: Color) -> void:
	var picker: ColorPickerButton = color_controls.get(property_name) as ColorPickerButton
	if picker != null:
		picker.color = color


func _reset_current() -> void:
	if hero_select.item_count == 0 or hero_select.selected < 0:
		return
	_push_undo_snapshot()
	var hero_id: String = String(hero_select.get_item_metadata(hero_select.selected))
	current = _new_appearance(hero_id)
	_populate_part_options()
	_load_current_into_ui()
	dirty = true
	_set_status("Valeurs V1.26 par défaut restaurées — non enregistrées.", false)


func _select_part(category: String, part_id: String) -> void:
	var option: OptionButton = part_controls.get(category) as OptionButton
	if option == null:
		return
	var index: int = _metadata_index(option, part_id)
	if index >= 0:
		option.select(index)


func _set_morph_value(property_name: String, value: float) -> void:
	var spin: SpinBox = morph_controls.get(property_name) as SpinBox
	if spin != null:
		spin.value = value


func _reset_offsets(mark_dirty: bool = true) -> void:
	var was_loading: bool = loading
	loading = true
	for spec: Array in OFFSET_SPECS:
		var property_name: String = String(spec[0])
		var controls: Dictionary = offset_controls.get(property_name, {})
		var x_spin: SpinBox = controls.get("x") as SpinBox
		var y_spin: SpinBox = controls.get("y") as SpinBox
		if x_spin != null:
			x_spin.value = 0.0
		if y_spin != null:
			y_spin.value = 0.0
	loading = was_loading
	if mark_dirty and not loading:
		_on_live_changed()


func _reset_edit_group(edit_group: String) -> void:
	var spec: Array = _direct_transform_spec(edit_group)
	if spec.is_empty():
		return
	var was_loading: bool = loading
	loading = true
	var offset_controls_for_group: Dictionary = offset_controls.get(String(spec[2]), {})
	var x_spin: SpinBox = offset_controls_for_group.get("x") as SpinBox
	var y_spin: SpinBox = offset_controls_for_group.get("y") as SpinBox
	if x_spin != null:
		x_spin.value = 0.0
	if y_spin != null:
		y_spin.value = 0.0
	var controls: Dictionary = direct_transform_controls.get(edit_group, {})
	var scale_spin: SpinBox = controls.get("scale") as SpinBox
	var rotation_spin: SpinBox = controls.get("rotation") as SpinBox
	if scale_spin != null:
		scale_spin.value = 1.0
	if rotation_spin != null:
		rotation_spin.value = 0.0
	loading = was_loading
	if not loading:
		_on_live_changed()
		_set_status("Transformation '%s' recentrée." % _edit_group_label(edit_group), false)


func _reset_direct_transforms(mark_dirty: bool = true) -> void:
	var was_loading: bool = loading
	loading = true
	for spec: Array in DIRECT_TRANSFORM_SPECS:
		var edit_group: String = String(spec[0])
		var controls: Dictionary = direct_transform_controls.get(edit_group, {})
		var scale_spin: SpinBox = controls.get("scale") as SpinBox
		var rotation_spin: SpinBox = controls.get("rotation") as SpinBox
		var lock_check: CheckBox = controls.get("lock") as CheckBox
		if scale_spin != null:
			scale_spin.value = 1.0
		if rotation_spin != null:
			rotation_spin.value = 0.0
		if lock_check != null:
			lock_check.button_pressed = false
	loading = was_loading
	_sync_preview_locks()
	if mark_dirty and not loading:
		_on_live_changed()


func _direct_transform_spec(edit_group: String) -> Array:
	for spec: Array in DIRECT_TRANSFORM_SPECS:
		if String(spec[0]) == edit_group:
			return spec
	return []


func _float_resource_property(resource: Resource, property_name: String, fallback: float) -> float:
	var value: Variant = resource.get(property_name)
	if value == null:
		return fallback
	return float(value)


func _edit_group_label(edit_group: String) -> String:
	for spec: Array in DIRECT_TRANSFORM_SPECS:
		if String(spec[0]) == edit_group:
			return String(spec[1])
	return edit_group.capitalize()


func _refresh_palettes() -> void:
	if palette_select == null:
		return
	var wanted_path: String = ""
	if palette_select.item_count > 0 and palette_select.selected >= 0:
		wanted_path = String(palette_select.get_item_metadata(palette_select.selected))
	palette_select.clear()
	for path: String in _resource_files(PALETTE_DIR):
		var palette: Resource = load(path)
		if palette == null:
			continue
		var palette_name: String = String(palette.get("display_name"))
		if palette_name.is_empty():
			palette_name = path.get_file().get_basename().replace("_", " ").capitalize()
		palette_select.add_item(palette_name)
		palette_select.set_item_metadata(palette_select.item_count - 1, path)
	var wanted_index: int = _metadata_index(palette_select, wanted_path)
	if wanted_index >= 0:
		palette_select.select(wanted_index)
	elif palette_select.item_count > 0:
		palette_select.select(0)


func _save_palette_profile() -> void:
	if current == null:
		return
	_write_ui_to_current()
	var absolute_dir: String = ProjectSettings.globalize_path(PALETTE_DIR)
	if not DirAccess.dir_exists_absolute(absolute_dir):
		DirAccess.make_dir_recursive_absolute(absolute_dir)
	var snapshot: Resource = current.duplicate(true) as Resource
	if snapshot == null:
		_set_status("Impossible de créer le profil couleur.", true)
		return
	var profile_name: String = palette_name_edit.text.strip_edges() if palette_name_edit != null else ""
	if profile_name.is_empty():
		profile_name = String(current.get("display_name")) + " — palette"
	snapshot.set("display_name", profile_name)
	var timestamp: int = int(Time.get_unix_time_from_system())
	var path: String = "%spalette_%d.tres" % [PALETTE_DIR, timestamp]
	var save_error: Error = ResourceSaver.save(snapshot, path)
	if save_error != OK:
		_set_status("Erreur de sauvegarde palette (%d)." % int(save_error), true)
		return
	_refresh_palettes()
	_select_metadata(palette_select, path)
	if palette_name_edit != null:
		palette_name_edit.text = ""
	_set_status("Profil couleur enregistré : %s" % profile_name, false)


func _apply_selected_palette() -> void:
	if current == null or palette_select == null or palette_select.item_count == 0 or palette_select.selected < 0:
		_set_status("Aucun profil couleur sélectionné.", true)
		return
	var path: String = String(palette_select.get_item_metadata(palette_select.selected))
	var palette: Resource = load(path)
	if palette == null:
		_set_status("Profil couleur introuvable : %s" % path, true)
		return
	_push_undo_snapshot()
	for spec: Array in COLOR_SPECS:
		var property_name: String = String(spec[0])
		current.set(property_name, palette.get(property_name))
	_load_current_into_ui()
	dirty = true
	_set_status("Palette appliquée sans modifier les pièces ni la morphologie.", false)


func _refresh_presets() -> void:
	if preset_select == null:
		return
	var wanted_path: String = ""
	if preset_select.item_count > 0 and preset_select.selected >= 0:
		wanted_path = String(preset_select.get_item_metadata(preset_select.selected))
	preset_select.clear()
	for path: String in _resource_files(PRESET_DIR):
		var preset: Resource = load(path)
		if preset == null:
			continue
		var preset_name: String = String(preset.get("display_name"))
		if preset_name.is_empty():
			preset_name = path.get_file().get_basename().replace("_", " ").capitalize()
		preset_select.add_item(preset_name)
		preset_select.set_item_metadata(preset_select.item_count - 1, path)
	var wanted_index: int = _metadata_index(preset_select, wanted_path)
	if wanted_index >= 0:
		preset_select.select(wanted_index)
	elif preset_select.item_count > 0:
		preset_select.select(0)


func _save_user_preset() -> void:
	if current == null:
		return
	_write_ui_to_current()
	var preset_name: String = preset_name_edit.text.strip_edges() if preset_name_edit != null else ""
	if preset_name.is_empty():
		preset_name = "%s — %s" % [String(current.get("display_name")), _selected_metadata(archetype_select).capitalize()]
	var absolute_dir: String = ProjectSettings.globalize_path(PRESET_DIR)
	if not DirAccess.dir_exists_absolute(absolute_dir):
		DirAccess.make_dir_recursive_absolute(absolute_dir)
	var timestamp: int = int(Time.get_unix_time_from_system())
	var preset_path: String = "%s%s_%d.tres" % [PRESET_DIR, String(current.get("hero_id")), timestamp]
	var snapshot: Resource = current.duplicate(true) as Resource
	if snapshot == null:
		_set_status("Impossible de dupliquer l'apparence pour le preset.", true)
		return
	snapshot.set("display_name", preset_name)
	var save_error: Error = ResourceSaver.save(snapshot, preset_path)
	if save_error != OK:
		_set_status("Erreur lors de la sauvegarde du preset (%d)." % int(save_error), true)
		return
	_refresh_presets()
	_select_metadata(preset_select, preset_path)
	if preset_name_edit != null:
		preset_name_edit.text = ""
	_set_status("Preset enregistré : %s" % preset_name, false)


func _apply_selected_preset() -> void:
	if current == null or preset_select == null or preset_select.item_count == 0 or preset_select.selected < 0:
		_set_status("Aucun preset sélectionné.", true)
		return
	var preset_path: String = String(preset_select.get_item_metadata(preset_select.selected))
	var preset: Resource = load(preset_path)
	if preset == null:
		_set_status("Preset introuvable : %s" % preset_path, true)
		return
	_push_undo_snapshot()
	_copy_appearance_fields(preset, current)
	_populate_part_options()
	_load_current_into_ui()
	dirty = true
	_set_status("Preset appliqué — encore non enregistré sur le héros.", false)


func _copy_appearance_fields(source: Resource, target: Resource) -> void:
	var protected: PackedStringArray = PackedStringArray([
		"hero_id", "target_visual_id", "display_name", "generated_sprite_sheet_path", "generated_portrait_path",
	])
	for property_info: Dictionary in source.get_property_list():
		var property_name: String = String(property_info.get("name", ""))
		var usage: int = int(property_info.get("usage", 0))
		if property_name.is_empty() or property_name == "script" or protected.has(property_name):
			continue
		if (usage & PROPERTY_USAGE_STORAGE) == 0:
			continue
		target.set(property_name, source.get(property_name))


func _duplicate_to_target() -> void:
	if current == null or copy_target_select == null or copy_target_select.item_count == 0 or copy_target_select.selected < 0:
		return
	_write_ui_to_current()
	var target_id: String = String(copy_target_select.get_item_metadata(copy_target_select.selected))
	if target_id.is_empty():
		return
	if target_id == String(current.get("hero_id")):
		_set_status("Choisis un héros cible différent du héros actif.", true)
		return
	var clone: Resource = current.duplicate(true) as Resource
	if clone == null:
		_set_status("Impossible de dupliquer l'apparence.", true)
		return
	clone.set("hero_id", target_id)
	clone.set("target_visual_id", target_id)
	clone.set("display_name", "%s — copie de %s" % [target_id.capitalize(), String(current.get("display_name"))])
	clone.set("generated_sprite_sheet_path", "res://assets/generated/heroes/%s_custom.png" % target_id)
	clone.set("generated_portrait_path", "res://assets/generated/heroes/%s_custom_portrait.png" % target_id)
	var target_path: String = APPEARANCE_DIR + target_id + ".tres"
	var save_error: Error = ResourceSaver.save(clone, target_path)
	if save_error != OK:
		_set_status("Erreur pendant la duplication vers %s (%d)." % [target_id, int(save_error)], true)
		return
	var result: Dictionary = HERO_COMPOSITOR_SCRIPT.apply_to_visual(clone)
	if not bool(result.get("ok", false)):
		_set_status("Apparence dupliquée mais génération du héros cible en erreur.", true)
		return
	_set_status("Look dupliqué et généré sur '%s'." % target_id, false)
	library_changed.emit()


func _load_favorites() -> void:
	favorite_parts.clear()
	var config: ConfigFile = ConfigFile.new()
	if config.load(FAVORITES_CONFIG) != OK:
		return
	for category: String in config.get_sections():
		var values: Variant = config.get_value(category, "parts", PackedStringArray())
		var parts: PackedStringArray = values if values is PackedStringArray else PackedStringArray()
		for part_id: String in parts:
			favorite_parts["%s/%s" % [category, part_id]] = true


func _save_favorites() -> void:
	var config: ConfigFile = ConfigFile.new()
	for spec: Array in PART_SPECS:
		var category: String = String(spec[0])
		var parts: PackedStringArray = PackedStringArray()
		for key: Variant in favorite_parts.keys():
			var string_key: String = String(key)
			if string_key.begins_with(category + "/") and bool(favorite_parts[key]):
				parts.append(string_key.trim_prefix(category + "/"))
		parts.sort()
		config.set_value(category, "parts", parts)
	config.save(FAVORITES_CONFIG)


func _is_favorite(category: String, part_id: String) -> bool:
	return bool(favorite_parts.get("%s/%s" % [category, part_id], false))


func _on_favorite_toggled(pressed: bool, category: String) -> void:
	if loading:
		return
	var option: OptionButton = part_controls.get(category) as OptionButton
	if option == null or option.selected < 0:
		return
	var part_id: String = String(option.get_item_metadata(option.selected))
	if part_id.is_empty() or part_id == "none":
		_sync_favorite_control(category)
		return
	favorite_parts["%s/%s" % [category, part_id]] = pressed
	_save_favorites()
	_populate_gallery(category)
	_set_status(("Ajouté aux favoris : " if pressed else "Retiré des favoris : ") + _friendly_name(part_id), false)


func _sync_favorite_control(category: String) -> void:
	var button: Button = favorite_controls.get(category) as Button
	var option: OptionButton = part_controls.get(category) as OptionButton
	if button == null or option == null or option.selected < 0:
		return
	var part_id: String = String(option.get_item_metadata(option.selected))
	var enabled: bool = not part_id.is_empty() and part_id != "none"
	var was_loading: bool = loading
	loading = true
	button.disabled = not enabled
	button.button_pressed = enabled and _is_favorite(category, part_id)
	button.text = "★" if button.button_pressed else "☆"
	loading = was_loading


func _push_undo_snapshot() -> void:
	if history_suspended or current == null:
		return
	var snapshot: Resource = current.duplicate(true) as Resource
	if snapshot == null:
		return
	undo_stack.append(snapshot)
	while undo_stack.size() > HISTORY_LIMIT:
		undo_stack.pop_front()
	redo_stack.clear()
	_update_history_buttons()


func _clear_history() -> void:
	undo_stack.clear()
	redo_stack.clear()
	_update_history_buttons()


func _update_history_buttons() -> void:
	if undo_button != null:
		undo_button.disabled = undo_stack.is_empty()
	if redo_button != null:
		redo_button.disabled = redo_stack.is_empty()


func _undo() -> void:
	if current == null or undo_stack.is_empty():
		return
	var redo_snapshot: Resource = current.duplicate(true) as Resource
	if redo_snapshot != null:
		redo_stack.append(redo_snapshot)
	var snapshot: Resource = undo_stack.pop_back()
	_restore_history_snapshot(snapshot, "Annulation appliquée.")


func _redo() -> void:
	if current == null or redo_stack.is_empty():
		return
	var undo_snapshot: Resource = current.duplicate(true) as Resource
	if undo_snapshot != null:
		undo_stack.append(undo_snapshot)
	var snapshot: Resource = redo_stack.pop_back()
	_restore_history_snapshot(snapshot, "Rétablissement appliqué.")


func _restore_history_snapshot(snapshot: Resource, message: String) -> void:
	if snapshot == null:
		return
	history_suspended = true
	current = snapshot.duplicate(true) as Resource
	_populate_part_options()
	_load_current_into_ui()
	dirty = true
	history_suspended = false
	_update_history_buttons()
	_set_status(message, false)


func _capture_reference(show_status: bool = true) -> void:
	if current == null:
		return
	_write_ui_to_current()
	reference_appearance = current.duplicate(true) as Resource
	if preview != null:
		preview.set_reference_appearance(reference_appearance)
	if show_status:
		_set_status("Référence Avant capturée pour la comparaison.", false)


func _on_compare_toggled(enabled: bool) -> void:
	if preview != null:
		preview.set_comparison_enabled(enabled)


func _refresh_exports() -> void:
	if export_select == null:
		return
	var wanted_path: String = ""
	if export_select.item_count > 0 and export_select.selected >= 0:
		wanted_path = String(export_select.get_item_metadata(export_select.selected))
	export_select.clear()
	for path: String in _resource_files(EXPORT_DIR):
		var look: Resource = load(path)
		if look == null:
			continue
		var look_name: String = String(look.get("display_name"))
		if look_name.is_empty():
			look_name = path.get_file().get_basename().replace("_", " ").capitalize()
		export_select.add_item(look_name)
		export_select.set_item_metadata(export_select.item_count - 1, path)
	var wanted_index: int = _metadata_index(export_select, wanted_path)
	if wanted_index >= 0:
		export_select.select(wanted_index)
	elif export_select.item_count > 0:
		export_select.select(0)


func _export_current_look() -> void:
	if current == null:
		return
	_write_ui_to_current()
	var absolute_dir: String = ProjectSettings.globalize_path(EXPORT_DIR)
	if not DirAccess.dir_exists_absolute(absolute_dir):
		DirAccess.make_dir_recursive_absolute(absolute_dir)
	var snapshot: Resource = current.duplicate(true) as Resource
	if snapshot == null:
		_set_status("Impossible de créer l’export du look.", true)
		return
	var export_name: String = export_name_edit.text.strip_edges() if export_name_edit != null else ""
	if export_name.is_empty():
		export_name = String(current.get("display_name")) + " — export"
	snapshot.set("display_name", export_name)
	var timestamp: int = int(Time.get_unix_time_from_system())
	var export_path: String = "%s%s_%d.tres" % [EXPORT_DIR, String(current.get("hero_id")), timestamp]
	var save_error: Error = ResourceSaver.save(snapshot, export_path)
	if save_error != OK:
		_set_status("Erreur export look (%d)." % int(save_error), true)
		return
	_refresh_exports()
	_select_metadata(export_select, export_path)
	if export_name_edit != null:
		export_name_edit.text = ""
	_set_status("Look exporté : %s" % export_path, false)


func _import_selected_look() -> void:
	if current == null or export_select == null or export_select.item_count == 0 or export_select.selected < 0:
		_set_status("Aucun look exporté sélectionné.", true)
		return
	var export_path: String = String(export_select.get_item_metadata(export_select.selected))
	var look: Resource = load(export_path)
	if look == null:
		_set_status("Look exporté introuvable : %s" % export_path, true)
		return
	_push_undo_snapshot()
	_copy_appearance_fields(look, current)
	_populate_part_options()
	_load_current_into_ui()
	dirty = true
	_set_status("Look importé — identité du héros actif conservée.", false)


func _resource_files(directory: String) -> Array[String]:
	var result: Array[String] = []
	var dir: DirAccess = DirAccess.open(directory)
	if dir == null:
		return result
	for file_name: String in dir.get_files():
		if file_name.ends_with(".tres"):
			result.append(directory + file_name)
	result.sort()
	return result


func _metadata_index(option: OptionButton, wanted: String) -> int:
	if option == null:
		return -1
	for index: int in range(option.item_count):
		if String(option.get_item_metadata(index)) == wanted:
			return index
	return -1


func _select_metadata(option: OptionButton, wanted: String) -> void:
	if option == null:
		return
	var index: int = _metadata_index(option, wanted)
	if index >= 0:
		option.select(index)
	elif option.item_count > 0:
		option.select(0)


func _selected_metadata(option: OptionButton) -> String:
	if option == null or option.item_count == 0 or option.selected < 0:
		return ""
	return String(option.get_item_metadata(option.selected))


func _friendly_name(part_id: String) -> String:
	if FRIENDLY_NAMES.has(part_id):
		return String(FRIENDLY_NAMES[part_id])
	return part_id.replace("_", " ").capitalize()


func _part_label(category: String) -> String:
	for spec: Array in PART_SPECS:
		if String(spec[0]) == category:
			return String(spec[1])
	return category.capitalize()


func _color_label(property_name: String) -> String:
	for spec: Array in COLOR_SPECS:
		if String(spec[0]) == property_name:
			return String(spec[1])
	return property_name.capitalize()


func _direction_label(direction: String) -> String:
	match direction:
		"front": return "Face"
		"right": return "Droite"
		"back": return "Dos"
		"left": return "Gauche"
		_: return direction.capitalize()


func _add_label(parent: Control, text: String) -> void:
	var label: Label = Label.new()
	label.text = text
	parent.add_child(label)


func _set_status(text: String, is_error: bool) -> void:
	if status_label == null:
		return
	status_label.text = text
	status_label.add_theme_color_override("font_color", Color("#ff9f7c") if is_error else Color("#8fe0ad"))
