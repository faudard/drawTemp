class_name SporeBattleHud
extends CanvasLayer

## Scene-first battle HUD.
## Layout and styling live in battle_hud_3d.tscn; the battle board only binds data.

@onready var turn_label: Label = %TurnLabel
@onready var info_label: Label = %InfoLabel
@onready var help_label: Label = %HelpLabel

@onready var move_button: Button = %MoveButton
@onready var attack_button: Button = %AttackButton
@onready var face_button: Button = %FaceButton
@onready var end_button: Button = %EndButton
@onready var primary_skill_button: Button = %PrimarySkillButton
@onready var secondary_skill_button: Button = %SecondarySkillButton

@onready var timeline_panel: Panel = %InitiativeRibbon
@onready var timeline_bar: HBoxContainer = %TimelineBar

@onready var log_label: Label = %LogLabel

@onready var preview_panel: Panel = %CombatPreview
@onready var preview_title: Label = %PreviewTitle
@onready var preview_body: Label = %PreviewBody
@onready var preview_confirm_button: Button = %PreviewConfirmButton
@onready var preview_cancel_button: Button = %PreviewCancelButton

@onready var unit_card_panel: Panel = %UnitDossier
@onready var unit_portrait: TextureRect = %UnitPortrait
@onready var unit_card_title: Label = %UnitTitle
@onready var unit_hp_bar: ProgressBar = %HpBar
@onready var unit_hp_text: Label = %HpText
@onready var unit_mp_bar: ProgressBar = %MpBar
@onready var unit_mp_text: Label = %MpText
@onready var unit_card_body: Label = %UnitBody

@onready var hero_panel: Panel = %HeroPanel
@onready var hero_portrait: TextureRect = %HeroPortrait
@onready var hero_name: Label = %HeroName

@onready var objective_panel: Panel = %ObjectiveBrief
@onready var objective_title: Label = %ObjectiveTitle
@onready var objective_body: Label = %ObjectiveBody

@onready var action_banner_panel: Panel = %ActionBanner
@onready var action_banner_title: Label = %ActionBannerTitle
@onready var action_banner_subtitle: Label = %ActionBannerSubtitle

@onready var facing_panel: Panel = %FacingSelector
@onready var facing_north: Button = %FacingNorth
@onready var facing_west: Button = %FacingWest
@onready var facing_south: Button = %FacingSouth
@onready var facing_east: Button = %FacingEast
@onready var facing_cancel: Button = %FacingCancel
@onready var facing_confirm: Button = %FacingConfirm
