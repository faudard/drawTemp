#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sporebound correction patcher
=============================

Purpose
-------
Repairs the regressions introduced by the broken push around commit f4a900a6
without reverting the newer Hero Creator / Guided Kit work.

Run from the root of the drawTemp repository:

    python sporebound_fix_broken_push.py

Useful options:

    python sporebound_fix_broken_push.py --dry-run
    python sporebound_fix_broken_push.py --root C:\\path\\to\\drawTemp
    python sporebound_fix_broken_push.py --no-backup
    python sporebound_fix_broken_push.py --keep-godot-tracked

What it restores
----------------
- FFT unit stats (magic power, defenses, weapon profiles, Brave/Faith, etc.)
- FFT skill timing/accuracy/no-cooldown data
- FFT clocktick statuses (Haste/Slow/Poison/etc.)
- Job/equipment combat fields
- Library portrait-billboard mappings for units other than the newer Momo flow
- Godot 4.7 project feature declaration
- .gitignore entry for .godot/

The patcher is content-guarded:
- if a hunk still matches the known broken state, it is applied;
- if the corrected hunk is already present, it is skipped;
- if neither state matches, the script stops instead of guessing.

Backups are written under:
    .sporebound_patch_backup/<timestamp>/
"""

from __future__ import annotations

import argparse
import datetime as _dt
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


EXPECTED_BROKEN_COMMIT_PREFIX = "f4a900a6"

PATCH_TEXT = r"""
diff --git a/data/units/archiviste.tres b/data/units/archiviste.tres
--- a/data/units/archiviste.tres
+++ b/data/units/archiviste.tres
@@ -12,9 +12,25 @@ team = "enemy"
 color = Color(0.831373, 0.549020, 1.000000, 1)
 max_hp = 15
 attack = 3
+magic_power = 3
+physical_defense = 2
+magic_defense = 2
 movement = 3
 attack_range = 2
+weapon_family = "focus"
+weapon_power = 1
+attack_min_range = 1
+threat_min_range = 1
+threat_max_range = 1
+can_opportunity_attack = false
+basic_attack_damage_type = "prism"
 initiative = 6
+accuracy = 6
+evasion = 4
+brave = 75
+faith = 75
+zodiac_sign = "serpentarius"
+sex = "monster"
 max_focus = 3
 primary_skill = ""
 secondary_skill = ""
diff --git a/data/units/baveux.tres b/data/units/baveux.tres
--- a/data/units/baveux.tres
+++ b/data/units/baveux.tres
@@ -12,9 +12,25 @@ team = "enemy"
 color = Color(0.952941, 0.650980, 0.352941, 1)
 max_hp = 7
 attack = 2
+magic_power = 1
+physical_defense = 0
+magic_defense = 0
 movement = 3
 attack_range = 1
+weapon_family = "melee"
+weapon_power = 1
+attack_min_range = 1
+threat_min_range = 1
+threat_max_range = 1
+can_opportunity_attack = true
+basic_attack_damage_type = "physical"
 initiative = 6
+accuracy = 0
+evasion = 1
+brave = 72
+faith = 38
+zodiac_sign = "scorpio"
+sex = "monster"
 max_focus = 2
 ai_profile = "aggressive"
 primary_skill = "corrode"
diff --git a/data/units/choriste.tres b/data/units/choriste.tres
--- a/data/units/choriste.tres
+++ b/data/units/choriste.tres
@@ -12,9 +12,25 @@ team = "enemy"
 color = Color(0.447059, 0.788235, 0.529412, 1)
 max_hp = 7
 attack = 2
+magic_power = 2
+physical_defense = 0
+magic_defense = 1
 movement = 4
 attack_range = 2
+weapon_family = "spear"
+weapon_power = 1
+attack_min_range = 1
+threat_min_range = 1
+threat_max_range = 2
+can_opportunity_attack = true
+basic_attack_damage_type = "physical"
 initiative = 7
+accuracy = 4
+evasion = 5
+brave = 64
+faith = 68
+zodiac_sign = "taurus"
+sex = "female"
 max_focus = 2
 primary_skill = ""
 secondary_skill = ""
diff --git a/data/units/comptable.tres b/data/units/comptable.tres
--- a/data/units/comptable.tres
+++ b/data/units/comptable.tres
@@ -12,9 +12,25 @@ team = "enemy"
 color = Color(0.886275, 0.811765, 0.388235, 1)
 max_hp = 10
 attack = 2
+magic_power = 2
+physical_defense = 1
+magic_defense = 1
 movement = 2
 attack_range = 3
+weapon_family = "ranged"
+weapon_power = 1
+attack_min_range = 2
+threat_min_range = 1
+threat_max_range = 1
+can_opportunity_attack = false
+basic_attack_damage_type = "physical"
 initiative = 4
+accuracy = 7
+evasion = 2
+brave = 70
+faith = 60
+zodiac_sign = "capricorn"
+sex = "male"
 max_focus = 2
 ai_profile = "tactical"
 primary_skill = "mark"
diff --git a/data/units/dj_morille.tres b/data/units/dj_morille.tres
--- a/data/units/dj_morille.tres
+++ b/data/units/dj_morille.tres
@@ -12,9 +12,25 @@ team = "enemy"
 color = Color(0.858824, 0.435294, 0.568627, 1)
 max_hp = 7
 attack = 2
+magic_power = 3
+physical_defense = 0
+magic_defense = 1
 movement = 3
 attack_range = 2
+weapon_family = "focus"
+weapon_power = 1
+attack_min_range = 1
+threat_min_range = 1
+threat_max_range = 1
+can_opportunity_attack = false
+basic_attack_damage_type = "spore"
 initiative = 7
+accuracy = 6
+evasion = 6
+brave = 66
+faith = 70
+zodiac_sign = "libra"
+sex = "female"
 max_focus = 2
 ai_profile = "aggressive"
 primary_skill = "funk"
diff --git a/data/units/grincheux.tres b/data/units/grincheux.tres
--- a/data/units/grincheux.tres
+++ b/data/units/grincheux.tres
@@ -12,9 +12,25 @@ team = "enemy"
 color = Color(0.603922, 0.482353, 0.878431, 1)
 max_hp = 8
 attack = 2
+magic_power = 1
+physical_defense = 1
+magic_defense = 0
 movement = 3
 attack_range = 1
+weapon_family = "melee"
+weapon_power = 1
+attack_min_range = 1
+threat_min_range = 1
+threat_max_range = 1
+can_opportunity_attack = true
+basic_attack_damage_type = "physical"
 initiative = 5
+accuracy = 1
+evasion = 0
+brave = 78
+faith = 42
+zodiac_sign = "cancer"
+sex = "male"
 max_focus = 2
 ai_profile = "defensive"
 primary_skill = "taunt"
diff --git a/data/units/luma.tres b/data/units/luma.tres
--- a/data/units/luma.tres
+++ b/data/units/luma.tres
@@ -12,9 +12,25 @@ team = "player"
 color = Color(0.466667, 0.717647, 1.000000, 1)
 max_hp = 9
 attack = 2
+magic_power = 3
+physical_defense = 0
+magic_defense = 1
 movement = 4
 attack_range = 3
+weapon_family = "ranged"
+weapon_power = 1
+attack_min_range = 2
+threat_min_range = 1
+threat_max_range = 1
+can_opportunity_attack = false
+basic_attack_damage_type = "physical"
 initiative = 7
+accuracy = 10
+evasion = 6
+brave = 62
+faith = 72
+zodiac_sign = "sagittarius"
+sex = "female"
 max_focus = 2
 primary_skill = "flare"
 secondary_skill = "prism_lance"
diff --git a/data/units/momo.tres b/data/units/momo.tres
--- a/data/units/momo.tres
+++ b/data/units/momo.tres
@@ -12,9 +12,25 @@ team = "player"
 color = Color(0.949020, 0.482353, 0.447059, 1)
 max_hp = 13
 attack = 3
+magic_power = 1
+physical_defense = 1
+magic_defense = 0
 movement = 4
 attack_range = 1
+weapon_family = "melee"
+weapon_power = 1
+attack_min_range = 1
+threat_min_range = 1
+threat_max_range = 1
+can_opportunity_attack = true
+basic_attack_damage_type = "physical"
 initiative = 5
+accuracy = 5
+evasion = 2
+brave = 74
+faith = 58
+zodiac_sign = "aries"
+sex = "male"
 max_focus = 2
 primary_skill = "hat"
 secondary_skill = "taunt"
diff --git a/data/units/pipo.tres b/data/units/pipo.tres
--- a/data/units/pipo.tres
+++ b/data/units/pipo.tres
@@ -12,9 +12,25 @@ team = "player"
 color = Color(0.423529, 0.772549, 0.788235, 1)
 max_hp = 10
 attack = 2
+magic_power = 2
+physical_defense = 1
+magic_defense = 1
 movement = 4
 attack_range = 1
+weapon_family = "melee"
+weapon_power = 1
+attack_min_range = 1
+threat_min_range = 1
+threat_max_range = 1
+can_opportunity_attack = true
+basic_attack_damage_type = "physical"
 initiative = 6
+accuracy = 2
+evasion = 5
+brave = 68
+faith = 64
+zodiac_sign = "leo"
+sex = "male"
 max_focus = 2
 primary_skill = "heal"
 secondary_skill = "mist"
diff --git a/data/units/ziggy.tres b/data/units/ziggy.tres
--- a/data/units/ziggy.tres
+++ b/data/units/ziggy.tres
@@ -12,9 +12,25 @@ team = "player"
 color = Color(0.760784, 0.482353, 0.878431, 1)
 max_hp = 8
 attack = 2
+magic_power = 3
+physical_defense = 0
+magic_defense = 1
 movement = 3
 attack_range = 3
+weapon_family = "focus"
+weapon_power = 1
+attack_min_range = 1
+threat_min_range = 1
+threat_max_range = 1
+can_opportunity_attack = true
+basic_attack_damage_type = "spore"
 initiative = 8
+accuracy = 4
+evasion = 3
+brave = 58
+faith = 76
+zodiac_sign = "gemini"
+sex = "male"
 max_focus = 2
 primary_skill = "funk"
 secondary_skill = "spore_orbit"
diff --git a/data/equipment/crown_core.tres b/data/equipment/crown_core.tres
--- a/data/equipment/crown_core.tres
+++ b/data/equipment/crown_core.tres
@@ -20,5 +20,16 @@ movement_bonus = 0
 range_bonus = 0
 initiative_bonus = 0
 focus_bonus = 1
+weapon_family = "spear"
+attack_min_range = 1
+attack_max_range = 2
+threat_min_range = 1
+threat_max_range = 2
+can_opportunity_attack = true
+basic_attack_damage_type = "physical"
+magic_power_bonus = 1
+basic_attack_damage_bonus = 1
 start_status_id = ""
 resistances = Array[Resource]([SubResource("Res_1")])
+weapon_power = 2
+physical_weapon_evasion = 4
diff --git a/data/equipment/echo_lens.tres b/data/equipment/echo_lens.tres
--- a/data/equipment/echo_lens.tres
+++ b/data/equipment/echo_lens.tres
@@ -14,5 +14,16 @@ movement_bonus = 0
 range_bonus = 1
 initiative_bonus = 0
 focus_bonus = 0
+weapon_family = "ranged"
+attack_min_range = 2
+attack_max_range = 4
+threat_min_range = 1
+threat_max_range = 1
+can_opportunity_attack = false
+basic_attack_damage_type = "physical"
+magic_power_bonus = 1
+basic_attack_accuracy_bonus = 10
 start_status_id = ""
 resistances = Array[Resource]([])
+weapon_power = 2
+physical_weapon_evasion = 2
diff --git a/data/equipment/hot_capacitor.tres b/data/equipment/hot_capacitor.tres
--- a/data/equipment/hot_capacitor.tres
+++ b/data/equipment/hot_capacitor.tres
@@ -14,5 +14,7 @@ movement_bonus = 0
 range_bonus = 0
 initiative_bonus = 0
 focus_bonus = 1
+focus_regen_bonus = 1
+magic_power_bonus = 1
 start_status_id = ""
 resistances = Array[Resource]([])
diff --git a/data/equipment/moss_charm.tres b/data/equipment/moss_charm.tres
--- a/data/equipment/moss_charm.tres
+++ b/data/equipment/moss_charm.tres
@@ -20,5 +20,9 @@ movement_bonus = 0
 range_bonus = 0
 initiative_bonus = 1
 focus_bonus = 0
+revive_hp_bonus = 1
+magic_defense_bonus = 1
 start_status_id = ""
 resistances = Array[Resource]([SubResource("Res_1")])
+physical_accessory_evasion = 5
+magic_accessory_evasion = 8
diff --git a/data/equipment/mycelium_plate.tres b/data/equipment/mycelium_plate.tres
--- a/data/equipment/mycelium_plate.tres
+++ b/data/equipment/mycelium_plate.tres
@@ -20,5 +20,12 @@ movement_bonus = 0
 range_bonus = 0
 initiative_bonus = 0
 focus_bonus = 0
+flat_damage_reduction = 1
+physical_defense_bonus = 1
+magic_defense_bonus = 1
+shield_block_chance = 25
+shield_block_reduction = 2
 start_status_id = "guarded"
 resistances = Array[Resource]([SubResource("Res_1")])
+physical_shield_evasion = 15
+magic_shield_evasion = 10
diff --git a/data/equipment/phase_compass.tres b/data/equipment/phase_compass.tres
--- a/data/equipment/phase_compass.tres
+++ b/data/equipment/phase_compass.tres
@@ -14,5 +14,9 @@ movement_bonus = 0
 range_bonus = 1
 initiative_bonus = 1
 focus_bonus = 0
+end_ct_bonus = 5
+magic_power_bonus = 1
 start_status_id = ""
 resistances = Array[Resource]([])
+physical_accessory_evasion = 4
+magic_accessory_evasion = 4
diff --git a/data/equipment/thorn_ring.tres b/data/equipment/thorn_ring.tres
--- a/data/equipment/thorn_ring.tres
+++ b/data/equipment/thorn_ring.tres
@@ -14,5 +14,15 @@ movement_bonus = 0
 range_bonus = 0
 initiative_bonus = 0
 focus_bonus = 0
+weapon_family = "melee"
+attack_min_range = 1
+attack_max_range = 1
+threat_min_range = 1
+threat_max_range = 1
+can_opportunity_attack = true
+basic_attack_damage_type = "physical"
+basic_attack_damage_bonus = 1
 start_status_id = ""
 resistances = Array[Resource]([])
+weapon_power = 2
+physical_weapon_evasion = 5
diff --git a/data/jobs/brave.tres b/data/jobs/brave.tres
--- a/data/jobs/brave.tres
+++ b/data/jobs/brave.tres
@@ -115,6 +115,9 @@ unlock_level = 1
 next_job_ids = PackedStringArray("bulwark")
 hp_bonus = 1
 attack_bonus = 1
+magic_power_bonus = 0
+physical_defense_bonus = 1
+magic_defense_bonus = 0
 movement_bonus = 0
 range_bonus = 0
 initiative_bonus = 0
diff --git a/data/jobs/bulwark.tres b/data/jobs/bulwark.tres
--- a/data/jobs/bulwark.tres
+++ b/data/jobs/bulwark.tres
@@ -121,6 +121,9 @@ unlock_level = 3
 next_job_ids = PackedStringArray()
 hp_bonus = 3
 attack_bonus = 0
+magic_power_bonus = 0
+physical_defense_bonus = 2
+magic_defense_bonus = 1
 movement_bonus = -1
 range_bonus = 0
 initiative_bonus = -1
diff --git a/data/jobs/field_medic.tres b/data/jobs/field_medic.tres
--- a/data/jobs/field_medic.tres
+++ b/data/jobs/field_medic.tres
@@ -115,6 +115,9 @@ unlock_level = 1
 next_job_ids = PackedStringArray("moss_warden")
 hp_bonus = 0
 attack_bonus = 0
+magic_power_bonus = 1
+physical_defense_bonus = 0
+magic_defense_bonus = 1
 movement_bonus = 0
 range_bonus = 0
 initiative_bonus = 1
diff --git a/data/jobs/flare_gunner.tres b/data/jobs/flare_gunner.tres
--- a/data/jobs/flare_gunner.tres
+++ b/data/jobs/flare_gunner.tres
@@ -120,6 +120,9 @@ unlock_level = 3
 next_job_ids = PackedStringArray()
 hp_bonus = 1
 attack_bonus = 1
+magic_power_bonus = 2
+physical_defense_bonus = 0
+magic_defense_bonus = 0
 movement_bonus = 0
 range_bonus = 0
 initiative_bonus = 1
diff --git a/data/jobs/groove_runner.tres b/data/jobs/groove_runner.tres
--- a/data/jobs/groove_runner.tres
+++ b/data/jobs/groove_runner.tres
@@ -120,6 +120,9 @@ unlock_level = 3
 next_job_ids = PackedStringArray()
 hp_bonus = 0
 attack_bonus = 0
+magic_power_bonus = 1
+physical_defense_bonus = 0
+magic_defense_bonus = 0
 movement_bonus = 1
 range_bonus = 0
 initiative_bonus = 3
diff --git a/data/jobs/moss_warden.tres b/data/jobs/moss_warden.tres
--- a/data/jobs/moss_warden.tres
+++ b/data/jobs/moss_warden.tres
@@ -120,6 +120,9 @@ unlock_level = 3
 next_job_ids = PackedStringArray()
 hp_bonus = 2
 attack_bonus = 0
+magic_power_bonus = 1
+physical_defense_bonus = 1
+magic_defense_bonus = 1
 movement_bonus = 0
 range_bonus = 0
 initiative_bonus = 0
diff --git a/data/jobs/prism_ranger.tres b/data/jobs/prism_ranger.tres
--- a/data/jobs/prism_ranger.tres
+++ b/data/jobs/prism_ranger.tres
@@ -115,6 +115,9 @@ unlock_level = 1
 next_job_ids = PackedStringArray("flare_gunner")
 hp_bonus = 0
 attack_bonus = 0
+magic_power_bonus = 2
+physical_defense_bonus = 0
+magic_defense_bonus = 1
 movement_bonus = 0
 range_bonus = 1
 initiative_bonus = 2
diff --git a/data/jobs/spore_maestro.tres b/data/jobs/spore_maestro.tres
--- a/data/jobs/spore_maestro.tres
+++ b/data/jobs/spore_maestro.tres
@@ -115,6 +115,9 @@ unlock_level = 1
 next_job_ids = PackedStringArray("groove_runner")
 hp_bonus = 0
 attack_bonus = 0
+magic_power_bonus = 2
+physical_defense_bonus = 0
+magic_defense_bonus = 1
 movement_bonus = 0
 range_bonus = 0
 initiative_bonus = 2
diff --git a/data/skills/corrode.tres b/data/skills/corrode.tres
--- a/data/skills/corrode.tres
+++ b/data/skills/corrode.tres
@@ -30,9 +30,15 @@ id = "corrode"
 display_name = "Basse corrosive"
 description = "Dégâts et AFFAIBLI."
 focus_cost = 1
+cooldown_rounds = 0
-cooldown_rounds = 2
 range = 3
 target_mode = "enemy"
+interrupt_on_damage = false
+cast_time_ticks = 2
+silence_affected = true
+fft_status_modifier = 160
+accuracy = 88
+uses_accuracy = true
 effects = Array[Resource]([SubResource("Effect_1"), SubResource("Effect_2")])
 vfx_id = "corrode_wave"
 effect_tags = PackedStringArray("damage", "weaken")
diff --git a/data/skills/flare.tres b/data/skills/flare.tres
--- a/data/skills/flare.tres
+++ b/data/skills/flare.tres
@@ -9,6 +9,7 @@ effect_type = "damage"
 damage_type = "prism"
 amount = 1
 use_attack_stat = true
+fft_spell_power_q = 4
 status_id = ""
 radius = 0
 area_shape = "single"
@@ -20,9 +21,14 @@ id = "flare"
 display_name = "Tir prismatique"
 description = "Tir à distance qui ignore la pénalité de couverture."
 focus_cost = 1
+cooldown_rounds = 0
-cooldown_rounds = 2
 range = 4
 target_mode = "enemy"
+interrupt_on_damage = false
+cast_time_ticks = 0
+silence_affected = true
+accuracy = 90
+uses_accuracy = true
 effects = Array[Resource]([SubResource("Effect_1")])
 vfx_id = "prism_projectile"
 effect_tags = PackedStringArray("damage", "ranged", "ignore_cover")
diff --git a/data/skills/funk.tres b/data/skills/funk.tres
--- a/data/skills/funk.tres
+++ b/data/skills/funk.tres
@@ -40,9 +40,15 @@ id = "funk"
 display_name = "Spore Funk"
 description = "Zone en croix : dégâts, RALENTI et poussée."
 focus_cost = 1
+cooldown_rounds = 0
-cooldown_rounds = 3
 range = 4
 target_mode = "ground"
+interrupt_on_damage = false
+cast_time_ticks = 3
+silence_affected = true
+fft_status_modifier = 180
+accuracy = 88
+uses_accuracy = true
 effects = Array[Resource]([SubResource("Effect_1"), SubResource("Effect_2"), SubResource("Effect_3")])
 vfx_id = "spore_burst"
 effect_tags = PackedStringArray("damage", "slow", "push", "aoe")
diff --git a/data/skills/hat.tres b/data/skills/hat.tres
--- a/data/skills/hat.tres
+++ b/data/skills/hat.tres
@@ -30,9 +30,13 @@ id = "hat"
 display_name = "Coup de chapeau"
 description = "Dégâts de mêlée puis poussée."
 focus_cost = 1
+cooldown_rounds = 0
-cooldown_rounds = 2
 range = 1
 target_mode = "unit"
+interrupt_on_damage = false
+cast_time_ticks = 0
+accuracy = 92
+uses_accuracy = true
 effects = Array[Resource]([SubResource("Effect_1"), SubResource("Effect_2")])
 vfx_id = "default_hit"
 effect_tags = PackedStringArray("damage", "push")
diff --git a/data/skills/heal.tres b/data/skills/heal.tres
--- a/data/skills/heal.tres
+++ b/data/skills/heal.tres
@@ -39,9 +39,14 @@ id = "heal"
 display_name = "Sauvetage élastique"
 description = "Soigne un allié, lui donne GARDE et peut le tirer."
 focus_cost = 1
+cooldown_rounds = 0
-cooldown_rounds = 2
 range = 3
 target_mode = "ally"
+interrupt_on_damage = false
+cast_time_ticks = 2
+silence_affected = true
+accuracy = 100
+uses_accuracy = false
 effects = Array[Resource]([SubResource("Effect_1"), SubResource("Effect_2"), SubResource("Effect_3")])
 vfx_id = "heal_bloom"
 effect_tags = PackedStringArray("heal", "guard", "pull")
diff --git a/data/skills/mark.tres b/data/skills/mark.tres
--- a/data/skills/mark.tres
+++ b/data/skills/mark.tres
@@ -19,9 +19,15 @@ id = "mark"
 display_name = "Balise prismatique"
 description = "Marque la cible pour amplifier le prochain dégât reçu."
 focus_cost = 1
+cooldown_rounds = 0
-cooldown_rounds = 3
 range = 4
 target_mode = "enemy"
+interrupt_on_damage = false
+cast_time_ticks = 1
+silence_affected = true
+fft_status_modifier = 190
+accuracy = 95
+uses_accuracy = true
 effects = Array[Resource]([SubResource("Effect_1")])
 vfx_id = "mark_ring"
 effect_tags = PackedStringArray("mark")
diff --git a/data/skills/mist.tres b/data/skills/mist.tres
--- a/data/skills/mist.tres
+++ b/data/skills/mist.tres
@@ -29,9 +29,14 @@ id = "mist"
 display_name = "Brume tonique"
 description = "Soin de zone et GARDE."
 focus_cost = 2
+cooldown_rounds = 0
-cooldown_rounds = 3
 range = 2
 target_mode = "self"
+interrupt_on_damage = false
+cast_time_ticks = 3
+silence_affected = true
+accuracy = 100
+uses_accuracy = false
 effects = Array[Resource]([SubResource("Effect_1"), SubResource("Effect_2")])
 vfx_id = "heal_bloom"
 effect_tags = PackedStringArray("heal", "guard", "aoe")
diff --git a/data/skills/prism_lance.tres b/data/skills/prism_lance.tres
--- a/data/skills/prism_lance.tres
+++ b/data/skills/prism_lance.tres
@@ -9,6 +9,7 @@ effect_type = "damage"
 damage_type = "prism"
 amount = 0
 use_attack_stat = true
+fft_spell_power_q = 4
 status_id = ""
 radius = 4
 area_shape = "line"
@@ -20,9 +21,14 @@ id = "prism_lance"
 display_name = "Lance prismatique"
 description = "Trace une ligne lumineuse depuis Luma et frappe tous les ennemis sur son axe."
 focus_cost = 1
+cooldown_rounds = 0
-cooldown_rounds = 3
 range = 4
 target_mode = "ground"
+interrupt_on_damage = false
+cast_time_ticks = 4
+silence_affected = true
+accuracy = 90
+uses_accuracy = true
 effects = Array[Resource]([SubResource("Effect_1")])
 vfx_id = "prism_beam"
 effect_tags = PackedStringArray("damage", "ranged", "aoe", "ignore_cover")
diff --git a/data/skills/spore_field.tres b/data/skills/spore_field.tres
--- a/data/skills/spore_field.tres
+++ b/data/skills/spore_field.tres
@@ -23,9 +23,14 @@ id = "spore_field"
 display_name = "Flaque corrosive"
 description = "Crée une zone de spores corrosives qui blesse les ennemis au début de leur activation pendant plusieurs rounds."
 focus_cost = 1
+cooldown_rounds = 0
-cooldown_rounds = 3
 range = 3
 target_mode = "ground"
+interrupt_on_damage = false
+cast_time_ticks = 2
+silence_affected = true
+accuracy = 100
+uses_accuracy = false
 effects = Array[Resource]([SubResource("EffectZone")])
 effect_tags = PackedStringArray("persistent_zone")
 vfx_id = "corrode_wave"
diff --git a/data/skills/spore_orbit.tres b/data/skills/spore_orbit.tres
--- a/data/skills/spore_orbit.tres
+++ b/data/skills/spore_orbit.tres
@@ -30,9 +30,15 @@ id = "spore_orbit"
 display_name = "Orbite sporale"
 description = "Explosion circulaire de spores : dégâts et RALENTI dans un rayon de 2 cases."
 focus_cost = 2
+cooldown_rounds = 0
-cooldown_rounds = 3
 range = 3
 target_mode = "ground"
+interrupt_on_damage = false
+cast_time_ticks = 3
+silence_affected = true
+fft_status_modifier = 180
+accuracy = 88
+uses_accuracy = true
 effects = Array[Resource]([SubResource("Effect_1"), SubResource("Effect_2")])
 vfx_id = "spore_burst"
 effect_tags = PackedStringArray("damage", "slow", "aoe")
diff --git a/data/skills/taunt.tres b/data/skills/taunt.tres
--- a/data/skills/taunt.tres
+++ b/data/skills/taunt.tres
@@ -39,9 +39,13 @@ id = "taunt"
 display_name = "Provocation myco"
 description = "GARDE, réaction rechargée et gêne les ennemis adjacents."
 focus_cost = 1
+cooldown_rounds = 0
-cooldown_rounds = 2
 range = 0
 target_mode = "self"
+interrupt_on_damage = false
+cast_time_ticks = 0
+accuracy = 100
+uses_accuracy = false
 effects = Array[Resource]([SubResource("Effect_1"), SubResource("Effect_2"), SubResource("Effect_3")])
 vfx_id = "guard_aura"
 effect_tags = PackedStringArray("guard", "taunt")
diff --git a/data/statuses/burning.tres b/data/statuses/burning.tres
--- a/data/statuses/burning.tres
+++ b/data/statuses/burning.tres
@@ -6,10 +6,11 @@
 script = ExtResource("1")
 id = "burning"
 display_name = "Brûlure"
+description = "Subit 2 dégâts en fin d’AT pendant 24 clockticks."
-description = "Subit 2 dégâts en fin d’activation pendant 2 activations."
 color = Color(1, 0.52, 0.26, 1)
 vfx_id = "burn_aura"
+duration_activations = 0
-duration_activations = 2
 tick_phase = "activation_end"
 tick_damage_type = "fire"
 tick_damage = 2
+duration_clockticks = 24
diff --git a/data/statuses/haste.tres b/data/statuses/haste.tres
--- a/data/statuses/haste.tres
+++ b/data/statuses/haste.tres
@@ -6,8 +6,11 @@
 script = ExtResource("1")
 id = "haste"
 display_name = "Tempo+"
+description = "CT +50% pendant 32 clockticks."
-description = "+1 MVT pendant 2 activations."
 color = Color(0.43, 0.92, 0.93, 1)
 vfx_id = "spore_burst"
+duration_activations = 0
+movement_delta = 0
+duration_clockticks = 32
+ct_rate_percent = 150
+opposed_status_id = "slowed"
-duration_activations = 2
-movement_delta = 1
diff --git a/data/statuses/poisoned.tres b/data/statuses/poisoned.tres
--- a/data/statuses/poisoned.tres
+++ b/data/statuses/poisoned.tres
@@ -6,10 +6,13 @@
 script = ExtResource("1")
 id = "poisoned"
 display_name = "Poison"
+description = "Poison FFT : dégâts en fin d’AT, durée 36 clockticks."
-description = "Subit 1 dégât en fin d’activation pendant 3 activations."
 color = Color(0.48, 0.85, 0.42, 1)
 vfx_id = "poison_aura"
+duration_activations = 0
-duration_activations = 3
 tick_phase = "activation_end"
 tick_damage_type = "toxin"
 tick_damage = 1
+duration_clockticks = 36
+
+opposed_status_id = "regen"
diff --git a/data/statuses/slowed.tres b/data/statuses/slowed.tres
--- a/data/statuses/slowed.tres
+++ b/data/statuses/slowed.tres
@@ -6,8 +6,11 @@
 script = ExtResource("1")
 id = "slowed"
 display_name = "Ralenti"
+description = "CT divisé par deux pendant 24 clockticks."
-description = "-1 MVT pendant une activation."
 color = Color(0.55, 0.76, 0.96, 1)
 vfx_id = "spore_burst"
+duration_activations = 0
+movement_delta = 0
+duration_clockticks = 24
+ct_rate_percent = 50
+opposed_status_id = "haste"
-duration_activations = 1
-movement_delta = -1
diff --git a/data/statuses/stunned.tres b/data/statuses/stunned.tres
--- a/data/statuses/stunned.tres
+++ b/data/statuses/stunned.tres
@@ -6,9 +6,11 @@
 script = ExtResource("1")
 id = "stunned"
 display_name = "Étourdi"
+description = "Impossible de se déplacer, agir ou réagir pendant 12 clockticks."
-description = "Impossible de se déplacer ou d’agir pendant une activation."
 color = Color(1, 0.85, 0.35, 1)
 vfx_id = "stun_ring"
+duration_activations = 0
-duration_activations = 1
 prevents_movement = true
 prevents_action = true
+duration_clockticks = 12
+prevents_reaction = true
diff --git a/data/statuses/weakened.tres b/data/statuses/weakened.tres
--- a/data/statuses/weakened.tres
+++ b/data/statuses/weakened.tres
@@ -6,8 +6,9 @@
 script = ExtResource("1")
 id = "weakened"
 display_name = "Affaibli"
+description = "-1 dégât infligé pendant 24 clockticks."
-description = "-1 dégât infligé pendant une activation."
 color = Color(0.75, 0.57, 0.9, 1)
 vfx_id = "corrode_wave"
+duration_activations = 0
-duration_activations = 1
 outgoing_damage_delta = -1
+duration_clockticks = 24
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,3 +1,8 @@
+
+## V1.27 — Library Art Runtime
+
+La mission 1 utilise maintenant directement les personnages haute qualité de la bibliothèque Sporebound grâce au mode `portrait_billboard`. Les 39 personnages sont disponibles comme skins `lib_*` dans **Sporebound Studio > Visuals**. Ce rendu remplace le fallback procédural pour les unités associées, sans attendre la production des atlas 4 directions définitifs. Voir `LIBRARY_ASSETS.md`.
+
 # Sporebound Tactics — V1.9.6 First Tactical 2.5D Map
 
 ## Première map 2.5D / 3D
diff --git a/data/visuals/units/archiviste.tres b/data/visuals/units/archiviste.tres
--- a/data/visuals/units/archiviste.tres
+++ b/data/visuals/units/archiviste.tres
@@ -7,13 +7,14 @@ script = ExtResource("1_visual")
 id = "archiviste"
 display_name = "L'Archiviste"
 unit_id = "archiviste"
+render_mode = "portrait_billboard"
+portrait_path = "res://assets/portraits/library/shadow_duelist.png"
-portrait_path = ""
 sprite_sheet_path = ""
 use_sprite_sheet = false
 frame_width = 0
 frame_height = 0
+sprite_scale = 0.21
+sprite_offset = Vector2(0, -18)
-sprite_scale = 1.0
-sprite_offset = Vector2(0, 0)
 flip_with_facing = false
 direction_mode = "4_way"
 direction_layout = "rows"
diff --git a/data/visuals/units/baveux.tres b/data/visuals/units/baveux.tres
--- a/data/visuals/units/baveux.tres
+++ b/data/visuals/units/baveux.tres
@@ -7,13 +7,16 @@ script = ExtResource("1_visual")
 id = "baveux"
 display_name = "Baveux"
 unit_id = "baveux"
+render_mode = "portrait_billboard"
+portrait_path = "res://assets/portraits/library/toxic_mage.png"
+attack_pose_path = "res://assets/action_poses/library/toxic_mage_attack.png"
+cast_pose_path = "res://assets/action_poses/library/toxic_mage_attack.png"
-portrait_path = ""
 sprite_sheet_path = ""
 use_sprite_sheet = false
 frame_width = 0
 frame_height = 0
+sprite_scale = 0.20
+sprite_offset = Vector2(0, -18)
-sprite_scale = 1.0
-sprite_offset = Vector2(0, 0)
 flip_with_facing = false
 direction_mode = "4_way"
 direction_layout = "rows"
diff --git a/data/visuals/units/choriste.tres b/data/visuals/units/choriste.tres
--- a/data/visuals/units/choriste.tres
+++ b/data/visuals/units/choriste.tres
@@ -7,13 +7,14 @@ script = ExtResource("1_visual")
 id = "choriste"
 display_name = "Choriste Moisi"
 unit_id = "choriste"
+render_mode = "portrait_billboard"
+portrait_path = "res://assets/portraits/library/spore_shepherd.png"
-portrait_path = ""
 sprite_sheet_path = ""
 use_sprite_sheet = false
 frame_width = 0
 frame_height = 0
+sprite_scale = 0.20
+sprite_offset = Vector2(0, -18)
-sprite_scale = 1.0
-sprite_offset = Vector2(0, 0)
 flip_with_facing = false
 direction_mode = "4_way"
 direction_layout = "rows"
diff --git a/data/visuals/units/comptable.tres b/data/visuals/units/comptable.tres
--- a/data/visuals/units/comptable.tres
+++ b/data/visuals/units/comptable.tres
@@ -7,13 +7,14 @@ script = ExtResource("1_visual")
 id = "comptable"
 display_name = "Le Comptable"
 unit_id = "comptable"
+render_mode = "portrait_billboard"
+portrait_path = "res://assets/portraits/library/spore_alchemist.png"
-portrait_path = ""
 sprite_sheet_path = ""
 use_sprite_sheet = false
 frame_width = 0
 frame_height = 0
+sprite_scale = 0.20
+sprite_offset = Vector2(0, -18)
-sprite_scale = 1.0
-sprite_offset = Vector2(0, 0)
 flip_with_facing = false
 direction_mode = "4_way"
 direction_layout = "rows"
diff --git a/data/visuals/units/dj_morille.tres b/data/visuals/units/dj_morille.tres
--- a/data/visuals/units/dj_morille.tres
+++ b/data/visuals/units/dj_morille.tres
@@ -7,13 +7,14 @@ script = ExtResource("1_visual")
 id = "dj_morille"
 display_name = "DJ Morille"
 unit_id = "dj_morille"
+render_mode = "portrait_billboard"
+portrait_path = "res://assets/portraits/library/coral_monk.png"
-portrait_path = ""
 sprite_sheet_path = ""
 use_sprite_sheet = false
 frame_width = 0
 frame_height = 0
+sprite_scale = 0.20
+sprite_offset = Vector2(0, -18)
-sprite_scale = 1.0
-sprite_offset = Vector2(0, 0)
 flip_with_facing = false
 direction_mode = "4_way"
 direction_layout = "rows"
diff --git a/data/visuals/units/grincheux.tres b/data/visuals/units/grincheux.tres
--- a/data/visuals/units/grincheux.tres
+++ b/data/visuals/units/grincheux.tres
@@ -7,13 +7,15 @@ script = ExtResource("1_visual")
 id = "grincheux"
 display_name = "Grincheux"
 unit_id = "grincheux"
+render_mode = "portrait_billboard"
+portrait_path = "res://assets/portraits/library/spike_fighter.png"
+attack_pose_path = "res://assets/action_poses/library/spike_fighter_attack.png"
-portrait_path = ""
 sprite_sheet_path = ""
 use_sprite_sheet = false
 frame_width = 0
 frame_height = 0
+sprite_scale = 0.20
+sprite_offset = Vector2(0, -18)
-sprite_scale = 1.0
-sprite_offset = Vector2(0, 0)
 flip_with_facing = false
 direction_mode = "4_way"
 direction_layout = "rows"
diff --git a/data/visuals/units/luma.tres b/data/visuals/units/luma.tres
--- a/data/visuals/units/luma.tres
+++ b/data/visuals/units/luma.tres
@@ -7,13 +7,15 @@ script = ExtResource("1_visual")
 id = "luma"
 display_name = "Luma"
 unit_id = "luma"
+render_mode = "portrait_billboard"
+portrait_path = "res://assets/portraits/library/rifle_ranger.png"
+attack_pose_path = "res://assets/action_poses/library/rifle_ranger_attack.png"
-portrait_path = ""
 sprite_sheet_path = ""
 use_sprite_sheet = false
 frame_width = 0
 frame_height = 0
+sprite_scale = 0.20
+sprite_offset = Vector2(0, -18)
-sprite_scale = 1.0
-sprite_offset = Vector2(0, 0)
 flip_with_facing = false
 direction_mode = "4_way"
 direction_layout = "rows"
diff --git a/data/visuals/units/pipo.tres b/data/visuals/units/pipo.tres
--- a/data/visuals/units/pipo.tres
+++ b/data/visuals/units/pipo.tres
@@ -7,13 +7,14 @@ script = ExtResource("1_visual")
 id = "pipo"
 display_name = "Pipo"
 unit_id = "pipo"
+render_mode = "portrait_billboard"
+portrait_path = "res://assets/portraits/library/flower_healer.png"
-portrait_path = ""
 sprite_sheet_path = ""
 use_sprite_sheet = false
 frame_width = 0
 frame_height = 0
+sprite_scale = 0.19
+sprite_offset = Vector2(0, -18)
-sprite_scale = 1.0
-sprite_offset = Vector2(0, 0)
 flip_with_facing = false
 direction_mode = "4_way"
 direction_layout = "rows"
diff --git a/data/visuals/units/ziggy.tres b/data/visuals/units/ziggy.tres
--- a/data/visuals/units/ziggy.tres
+++ b/data/visuals/units/ziggy.tres
@@ -7,13 +7,15 @@ script = ExtResource("1_visual")
 id = "ziggy"
 display_name = "Ziggy"
 unit_id = "ziggy"
+render_mode = "portrait_billboard"
+portrait_path = "res://assets/portraits/library/spore_gunslinger.png"
+attack_pose_path = "res://assets/action_poses/library/spore_gunslinger_attack.png"
-portrait_path = ""
 sprite_sheet_path = ""
 use_sprite_sheet = false
 frame_width = 0
 frame_height = 0
+sprite_scale = 0.20
+sprite_offset = Vector2(0, -18)
-sprite_scale = 1.0
-sprite_offset = Vector2(0, 0)
 flip_with_facing = false
 direction_mode = "4_way"
 direction_layout = "rows"
diff --git a/project.godot b/project.godot
--- a/project.godot
+++ b/project.godot
@@ -11,6 +11,7 @@ config/name="Sporebound Tactics - V1.28 Guided Kit Library"
 config/use_custom_user_dir=true
 config/custom_user_dir_name="SporeboundTactics"
 run/main_scene="res://main.tscn"
+config/features=PackedStringArray("4.7")
 
 [display]
 
diff --git a/.gitignore b/.gitignore
new file mode 100644
--- /dev/null
+++ b/.gitignore
@@ -0,0 +1,2 @@
+# Godot editor/import cache: local machine state, never source data.
+.godot/
"""


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]


@dataclass
class FilePatch:
    path: str
    is_new: bool
    hunks: list[Hunk]


def _parse_range(token: str) -> tuple[int, int]:
    token = token.strip()
    if "," in token:
        a, b = token.split(",", 1)
        return int(a), int(b)
    return int(token), 1


def parse_patch(text: str) -> list[FilePatch]:
    lines = text.splitlines()
    result: list[FilePatch] = []
    current: FilePatch | None = None
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) < 4:
                raise RuntimeError(f"Malformed diff header: {line}")
            bpath = parts[3]
            if not bpath.startswith("b/"):
                raise RuntimeError(f"Unexpected target path: {bpath}")
            current = FilePatch(path=bpath[2:], is_new=False, hunks=[])
            result.append(current)
            i += 1
            continue

        if current is None:
            i += 1
            continue

        if line.startswith("new file mode "):
            current.is_new = True
            i += 1
            continue

        if line.startswith("@@ "):
            # Example: @@ -12,9 +12,25 @@ optional text
            try:
                header = line.split("@@", 2)[1].strip()
                old_tok, new_tok, *_ = header.split()
                old_start, old_count = _parse_range(old_tok[1:])
                new_start, new_count = _parse_range(new_tok[1:])
            except Exception as exc:
                raise RuntimeError(f"Malformed hunk header: {line}") from exc

            hunk_lines: list[str] = []
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.startswith("diff --git ") or nxt.startswith("@@ "):
                    break
                if nxt.startswith((" ", "+", "-", "\\")):
                    hunk_lines.append(nxt)
                else:
                    # Metadata after a hunk is unusual but harmless.
                    if nxt.startswith(("index ", "--- ", "+++ ", "new file mode ")):
                        break
                    hunk_lines.append(" " + nxt)
                i += 1

            current.hunks.append(
                Hunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    lines=hunk_lines,
                )
            )
            continue

        i += 1

    return result


def _old_sequence(hunk: Hunk) -> list[str]:
    return [line[1:] for line in hunk.lines if line and line[0] in (" ", "-")]


def _new_sequence(hunk: Hunk) -> list[str]:
    return [line[1:] for line in hunk.lines if line and line[0] in (" ", "+")]


def _find_sequence(
    haystack: list[str],
    needle: list[str],
    expected_index: int,
    radius: int = 80,
) -> int | None:
    if not needle:
        return 0

    n = len(needle)
    if n > len(haystack):
        return None

    expected_index = max(0, min(expected_index, len(haystack) - n))

    lo = max(0, expected_index - radius)
    hi = min(len(haystack) - n, expected_index + radius)

    # Prefer the area around the hunk's expected location.
    for idx in range(lo, hi + 1):
        if haystack[idx : idx + n] == needle:
            return idx

    # Then search globally. This tolerates unrelated lines inserted earlier.
    for idx in range(0, len(haystack) - n + 1):
        if haystack[idx : idx + n] == needle:
            return idx

    return None


def _read_lines(path: Path) -> tuple[list[str], bool]:
    raw = path.read_text(encoding="utf-8")
    trailing_newline = raw.endswith("\n")
    return raw.splitlines(), trailing_newline


def _write_lines(path: Path, lines: list[str], trailing_newline: bool = True) -> None:
    payload = "\n".join(lines)
    if trailing_newline:
        payload += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")


def _copy_backup(root: Path, source: Path, backup_root: Path) -> None:
    rel = source.relative_to(root)
    target = backup_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def apply_file_patch(
    root: Path,
    fp: FilePatch,
    *,
    dry_run: bool,
    backup_root: Path | None,
) -> tuple[str, int]:
    path = root / fp.path

    if path.exists():
        lines, trailing_newline = _read_lines(path)
    elif fp.is_new:
        lines, trailing_newline = [], True
    else:
        raise RuntimeError(f"Required file does not exist: {fp.path}")

    original_lines = list(lines)
    changed_hunks = 0
    skipped_hunks = 0
    offset = 0

    for hunk_no, hunk in enumerate(fp.hunks, start=1):
        old_seq = _old_sequence(hunk)
        new_seq = _new_sequence(hunk)
        expected = max(0, hunk.old_start - 1 + offset)

        old_pos = _find_sequence(lines, old_seq, expected)
        if old_pos is not None:
            lines[old_pos : old_pos + len(old_seq)] = new_seq
            offset += len(new_seq) - len(old_seq)
            changed_hunks += 1
            continue

        # Idempotence: if the corrected state already exists, skip this hunk.
        new_expected = max(0, hunk.new_start - 1 + offset)
        new_pos = _find_sequence(lines, new_seq, new_expected)
        if new_pos is not None:
            skipped_hunks += 1
            continue

        context_preview = "\n".join(old_seq[:8])
        raise RuntimeError(
            f"{fp.path}: hunk {hunk_no} does not match the broken state "
            f"and is not already corrected.\n"
            f"Refusing to guess.\nExpected old fragment begins with:\n{context_preview}"
        )

    if changed_hunks == 0:
        return "already-corrected", skipped_hunks

    if not dry_run:
        if path.exists() and backup_root is not None:
            _copy_backup(root, path, backup_root)
        _write_lines(path, lines, trailing_newline or fp.is_new)

    return "changed", changed_hunks


def _git_head(root: Path) -> str | None:
    try:
        cp = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        if cp.returncode == 0:
            return cp.stdout.strip()
    except OSError:
        pass
    return None


def _untrack_godot_cache(root: Path, dry_run: bool) -> None:
    git_dir = root / ".git"
    if not git_dir.exists():
        print("[INFO] No .git directory found; skipping git-index cleanup for .godot/")
        return

    cmd = ["git", "rm", "-r", "--cached", "--ignore-unmatch", ".godot"]
    if dry_run:
        print("[DRY] Would run:", " ".join(cmd))
        return

    try:
        cp = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        print("[WARN] git executable not found; .gitignore is fixed, but .godot may remain tracked.")
        return

    if cp.returncode == 0:
        if cp.stdout.strip():
            print("[OK] Removed .godot/ from Git index (local cache files are kept on disk).")
    else:
        print("[WARN] Could not untrack .godot/:")
        print(cp.stderr.strip())


def _validate_root(root: Path) -> None:
    required = [
        root / "project.godot",
        root / "data",
        root / "scripts",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise RuntimeError(
            "This does not look like the Sporebound repository root.\n"
            "Missing: " + ", ".join(missing)
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repair the Sporebound broken push safely.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate all changes without writing files",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create .sporebound_patch_backup copies",
    )
    parser.add_argument(
        "--keep-godot-tracked",
        action="store_true",
        help="Do not run 'git rm --cached .godot' after applying the patch",
    )
    args = parser.parse_args(argv)

    root = args.root.expanduser().resolve()
    _validate_root(root)

    head = _git_head(root)
    if head:
        print(f"[INFO] Git HEAD: {head}")
        if not head.startswith(EXPECTED_BROKEN_COMMIT_PREFIX):
            print(
                "[WARN] HEAD is not the exact broken commit that was originally analysed. "
                "The script will continue only because every hunk is content-guarded."
            )

    patches = parse_patch(PATCH_TEXT)
    print(f"[INFO] Loaded {len(patches)} targeted file corrections.")

    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = None
    if not args.no_backup and not args.dry_run:
        backup_root = root / ".sporebound_patch_backup" / timestamp

    changed: list[str] = []
    already_ok: list[str] = []

    try:
        for fp in patches:
            status, count = apply_file_patch(
                root,
                fp,
                dry_run=args.dry_run,
                backup_root=backup_root,
            )
            if status == "changed":
                changed.append(fp.path)
                print(f"[{'DRY' if args.dry_run else 'OK '}] {fp.path} ({count} hunk(s))")
            else:
                already_ok.append(fp.path)
                print(f"[SKIP] {fp.path} already corrected")
    except Exception as exc:
        print("\n[ERROR] Patch stopped safely:")
        print(exc)
        print("\nNo further files were modified.")
        if backup_root and backup_root.exists():
            print(f"Backups of files modified before the stop are in: {backup_root}")
        return 2

    if not args.keep_godot_tracked:
        _untrack_godot_cache(root, args.dry_run)

    print("\n=== Sporebound correction summary ===")
    print(f"Changed:           {len(changed)}")
    print(f"Already corrected: {len(already_ok)}")
    print(f"Dry run:           {'yes' if args.dry_run else 'no'}")
    if backup_root is not None:
        print(f"Backups:           {backup_root}")

    print("\nRecommended verification:")
    print("  git diff --check")
    print("  git status")
    print("  git diff -- data/units data/skills data/statuses data/jobs data/equipment")
    print("\nThen open Godot and let it regenerate .godot/ locally.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
