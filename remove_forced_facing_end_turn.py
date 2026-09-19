#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import sys

ROOT = Path.cwd()
TARGET = ROOT / "scripts" / "prototypes" / "spore_battle_board_3d.gd"

if not TARGET.exists():
    print(f"[ERROR] Missing: {TARGET}")
    print("Run this script from the repository root.")
    sys.exit(1)

text = TARGET.read_text(encoding="utf-8")
backup = TARGET.with_suffix(TARGET.suffix + ".forced_facing_backup")
if not backup.exists():
    backup.write_text(text, encoding="utf-8", newline="\n")

old_confirm = '''func _confirm_facing_and_end() -> void:\n\tif not _facing_selection_active or active_actor == null:\n\t\treturn\n\n\tif _facing_panel != null and is_instance_valid(_facing_panel):\n\t\t_facing_panel.visible = false\n\n\t_facing_selection_active = false\n\tplayer_busy = false\n\n\tactive_actor.waited_this_activation = (\n\t\tnot active_actor.moved_this_activation\n\t\tand not active_actor.acted_this_activation\n\t)\n\n\tvar wait_note: String = ""\n\tif active_actor.is_casting() and not active_actor.acted_this_activation:\n\t\twait_note = " • préparation conservée"\n\n\t_log(\n\t\t"%s termine son tour • orientation %s%s."\n\t\t% [active_actor.display_name, active_actor.facing_name(), wait_note]\n\t)\n\t_start_next_activation()\n'''

new_confirm = '''func _finish_player_activation_keep_facing() -> void:\n\tif active_actor == null or battle_finished:\n\t\treturn\n\n\t_clear_pending_action()\n\tselected_skill_id = ""\n\tskill_preview_cells.clear()\n\tpreview_path_cells.clear()\n\n\tactive_actor.waited_this_activation = (\n\t\tnot active_actor.moved_this_activation\n\t\tand not active_actor.acted_this_activation\n\t)\n\n\tvar wait_note: String = ""\n\tif active_actor.is_casting() and not active_actor.acted_this_activation:\n\t\twait_note = " • préparation conservée"\n\n\t_log(\n\t\t"%s termine son tour • orientation %s conservée%s."\n\t\t% [active_actor.display_name, active_actor.facing_name(), wait_note]\n\t)\n\t_start_next_activation()\n\n\nfunc _confirm_facing_and_end() -> void:\n\tif active_actor == null:\n\t\treturn\n\n\tif _facing_panel != null and is_instance_valid(_facing_panel):\n\t\t_facing_panel.visible = false\n\n\t_facing_selection_active = false\n\tplayer_busy = false\n\t_finish_player_activation_keep_facing()\n'''

if old_confirm not in text:
    print("[ERROR] Could not find the expected _confirm_facing_and_end() block.")
    print("Your file may have changed since the inspected master revision.")
    sys.exit(2)

text = text.replace(old_confirm, new_confirm, 1)

old_end = '''func _on_end_activation_pressed() -> void:\n\tif _facing_selection_active:\n\t\t_confirm_facing_and_end()\n\t\treturn\n\tif not _player_can_input():\n\t\treturn\n\t_open_facing_selector()\n'''

new_end = '''func _on_end_activation_pressed() -> void:\n\t# Ending a turn no longer forces the facing selector. The actor simply keeps\n\t# its current orientation. Facing remains an explicit choice through F / ORIENT.\n\tif _facing_selection_active:\n\t\t_confirm_facing_and_end()\n\t\treturn\n\tif not _player_can_input():\n\t\treturn\n\t_finish_player_activation_keep_facing()\n'''

if old_end not in text:
    print("[ERROR] Could not find the expected _on_end_activation_pressed() block.")
    sys.exit(3)

text = text.replace(old_end, new_end, 1)

# Slightly clearer button label without changing behavior.
text = text.replace(
    '_end_button = _make_button(panel, "WAIT [ESPACE]", Vector2(312.0, 87.0), Vector2(104.0, 32.0))',
    '_end_button = _make_button(panel, "FIN [ESPACE]", Vector2(312.0, 87.0), Vector2(104.0, 32.0))',
    1,
)

TARGET.write_text(text, encoding="utf-8", newline="\n")

# Basic sanity checks.
result = TARGET.read_text(encoding="utf-8")
checks = [
    'func _finish_player_activation_keep_facing() -> void:',
    'func _on_end_activation_pressed() -> void:',
    '\t_finish_player_activation_keep_facing()',
    'FIN [ESPACE]',
]
for check in checks:
    if check not in result:
        print(f"[ERROR] Sanity check failed: {check}")
        sys.exit(4)

print("[OK] Forced facing selection at end of turn removed.")
print("  SPACE / FIN ends the activation immediately.")
print("  Current facing is preserved.")
print("  F / ORIENT. still opens the manual facing selector.")
print(f"  Backup: {backup}")
