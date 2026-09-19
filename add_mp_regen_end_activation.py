#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import sys

ROOT = Path.cwd()
BOARD = ROOT / "scripts" / "prototypes" / "spore_battle_board_3d.gd"

if not BOARD.exists():
    print(f"[ERROR] Fichier introuvable: {BOARD}")
    print("Lance ce script depuis la racine du projet SporeboundTactics.")
    sys.exit(1)

text = BOARD.read_text(encoding="utf-8")
backup = BOARD.with_suffix(BOARD.suffix + ".mp_regen_backup")
if not backup.exists():
    backup.write_text(text, encoding="utf-8", newline="\n")

changed = False

# 1) Expose the rule in the Inspector.
if "mp_regen_end_activation" not in text:
    anchor_candidates = [
        '@export var show_reachable_overlay: bool = true\n',
        '@export_range(0, 4, 1) var opportunity_damage_penalty: int = 1\n',
    ]
    inserted = False
    for anchor in anchor_candidates:
        if anchor in text:
            addition = (
                anchor
                + '@export_range(0, 10, 1) var mp_regen_end_activation: int = 1\n'
            )
            text = text.replace(anchor, addition, 1)
            inserted = True
            changed = True
            break
    if not inserted:
        raise RuntimeError("Impossible de trouver l'ancre des règles pour mp_regen_end_activation")

# 2) Regenerate MP exactly once when an activation ends.
regen_block = '''\t\tif active_actor.alive and mp_regen_end_activation > 0:\n\t\t\tvar restored_mp: int = active_actor.change_focus(mp_regen_end_activation)\n\t\t\tif restored_mp > 0:\n\t\t\t\t_show_floating_text(\n\t\t\t\t\tactive_actor.position + Vector3(0.0, 1.28, 0.0),\n\t\t\t\t\t\"MP +%d\" % restored_mp,\n\t\t\t\t\tColor(0.42, 0.72, 1.0, 1.0)\n\t\t\t\t)\n'''

if '"MP +%d" % restored_mp' not in text:
    anchor = '\t\tactive_actor.end_activation()\n\t\t_finalize_actor_timing(active_actor)\n'
    if anchor not in text:
        raise RuntimeError("Ancre de fin d'activation introuvable dans _start_next_activation()")
    replacement = regen_block + anchor
    text = text.replace(anchor, replacement, 1)
    changed = True

BOARD.write_text(text, encoding="utf-8", newline="\n")

# Basic structural verification.
final = BOARD.read_text(encoding="utf-8")
if final.count("mp_regen_end_activation") < 2:
    raise RuntimeError("Vérification échouée: règle MP non correctement installée")
if final.count('"MP +%d" % restored_mp') != 1:
    raise RuntimeError("Vérification échouée: bloc de régénération MP absent ou dupliqué")

print("[OK] Régénération MP de fin d'activation installée.")
print("     Règle par défaut : +1 MP à chaque fin d'activation.")
print("     Plafond : max_focus / MP max de l'unité.")
print("     Unités K.O. : aucun gain.")
print("     Joueurs et ennemis : même règle.")
print("     Inspector : mp_regen_end_activation (0..10).")
if not changed:
    print("[INFO] Le patch était déjà présent; aucune modification nécessaire.")
print(f"[BACKUP] {backup}")
