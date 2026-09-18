extends SceneTree

const CombatMechanics = preload("res://scripts/core/combat_mechanics.gd")
const SkillCatalog = preload("res://scripts/catalogs/skill_catalog.gd")
const UnitActorScript = preload("res://scripts/maps/spore_unit_actor_3d.gd")
const BoardScript = preload("res://scripts/prototypes/spore_battle_board_3d.gd")

var failures: PackedStringArray = PackedStringArray()


func _init() -> void:
	_test_exact_fft_ct_spend()
	_test_no_skill_cooldown_gate()
	_test_cast_contract()
	_test_player_turn_contract()
	if failures.is_empty():
		print("[V1.28.0] FFT turn loop smoke test OK")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func _expect(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)


func _test_exact_fft_ct_spend() -> void:
	_expect(CombatMechanics.action_end_ct(100, true, true) == 0, "100 CT + Move+Act doit finir à 0.")
	_expect(CombatMechanics.action_end_ct(100, true, false) == 20, "100 CT + Move seul doit finir à 20.")
	_expect(CombatMechanics.action_end_ct(100, false, true) == 20, "100 CT + Act seul doit finir à 20.")
	_expect(CombatMechanics.action_end_ct(100, false, false) == 40, "100 CT + Wait doit finir à 40.")
	_expect(CombatMechanics.action_end_ct(108, true, true) == 8, "Le surplus CT au-dessus de 100 doit être conservé.")
	_expect(CombatMechanics.action_end_ct(145, false, false) == 60, "Le CT restant après le tour doit être plafonné à 60.")
	_expect(CombatMechanics.ticks_until_ready(40, 10) == 6, "40 CT à VIT 10 doit demander 6 ticks.")


func _test_no_skill_cooldown_gate() -> void:
	var unit: Dictionary = {"focus": 2, "max_focus": 2, "has_acted": false, "cooldowns": {"hat": 99}}
	_expect(SkillCatalog.cooldown_left(unit, "hat") == 0, "Les cooldowns legacy ne doivent plus bloquer une compétence.")
	_expect(SkillCatalog.can_use(unit, "hat"), "Une compétence disponible doit être limitée par Focus + Act, pas par CD.")
	SkillCatalog.spend(unit, "hat")
	_expect(bool(unit["has_acted"]), "Utiliser une compétence doit consommer Act.")
	_expect((unit.get("cooldowns", {}) as Dictionary).is_empty(), "Le runtime doit purger les anciens cooldowns.")


func _test_cast_contract() -> void:
	_expect(SkillCatalog.cast_time_ticks("hat") == 0, "Coup de chapeau doit être instantané.")
	_expect(SkillCatalog.cast_time_ticks("prism_lance") == 4, "Prism Lance doit conserver son cast de 4 ticks.")
	_expect(SkillCatalog.uses_accuracy("flare"), "Flare doit utiliser la précision.")
	_expect(SkillCatalog.has_tag("prism_lance", "aoe"), "Les tags de compétence doivent être exposés par le catalogue.")


func _test_player_turn_contract() -> void:
	var actor: Node = UnitActorScript.new()
	_expect(actor.has_method("begin_activation"), "L'acteur 3D doit exposer begin_activation().")
	_expect(actor.has_method("can_use_skill"), "L'acteur 3D doit exposer can_use_skill().")
	actor.free()
	var board: Node = BoardScript.new()
	_expect(board.has_method("_finish_activation_if_complete"), "Le plateau doit conserver la phase de fin/orientation après Move+Act.")
	_expect(board.has_method("_on_end_activation_pressed"), "Le plateau doit avoir un Wait/Fin explicite.")
	board.free()
