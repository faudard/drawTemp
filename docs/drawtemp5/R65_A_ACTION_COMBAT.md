# R65.A — Action Systems Pro: déterminisme du combat d'action

Statut : implémentation headless candidate, **gate R65 = NO-GO**.

## Portée

ActionCombatR65 (sporebound/action_combat_r65.py) est une extension optionnelle de ActionRuntime R26 : il garde le même auteur de vérité pour positions, PV, collisions, IA, inventaire, butin, interactions et compteur de ticks. Les modes tactiques CT, GameSession, Player et sauvegardes R26 historiques v1 ne sont pas modifiés. Le nouveau replay R65 est explicitement v2 et refuse les versions inconnues.

R65.A ajoute des combos de 1 à 4 coups (windup, active, recovery, range, damage, stagger, burn_ticks), la file de combo uniquement pendant le recovery, les télégraphies comme événements, et une hitbox orientée avec test de mur/porte et un seul impact par cible et par coup. Projectiles à déplacements entiers et collision balayée par sous-pas de 80 unités maximum, TTL/cadence bornés, plafond de 24 projectiles. Parade avec fenêtre et cooldown en ticks, coût d'endurance et stagger; l'esquive, la garde et l'IA R26 demeurent intactes. Effet burn avec tick périodique, mort et récompense idempotente.

Les entrées additionnelles fire et parry sont des booléens stricts, comme attack, dodge et guard. Le rendu (0, 1, 2 ou davantage d'images pour chaque tick) ne commande jamais le gameplay. Tous les délais sont des entiers au tick fixe de 60 Hz; les positions/distances sont en millièmes de case. Les règles sont des dictionnaires à clés exactes, entiers bornés, sans scripts ni callbacks. Le snapshot exposé à l'affichage est détaché.

## Utilisation

    from sporebound.action_combat_r65 import ActionCombatR65
    rules = {
        "version": 1,
        "combo": [
            {"windup": 1, "active": 2, "recovery": 2, "range": 1250,
             "damage": 2, "stagger": 5, "burn_ticks": 25},
            {"windup": 1, "active": 1, "recovery": 3, "range": 1300,
             "damage": 3, "stagger": 8, "burn_ticks": 0},
        ],
        "projectile": {"speed": 900, "ttl": 12, "cooldown": 8,
                       "damage": 2, "stagger": 4, "burn_ticks": 0}
    }
    runtime = ActionCombatR65(existing_r26_scene, rules)
    runtime.step({"tick": 1, "dx": 1, "attack": True})
    runtime.step({"tick": 2, "fire": True})
    runtime.save("r65.json")
    restored = ActionCombatR65.load(
        "r65.json", expected_scene=existing_r26_scene, expected_rules=rules)
    assert restored.digest() == runtime.digest()

Les checkpoints enregistrent scène, règles, commandes, inventaire initial et empreintes; ils sont reconstruits par replay et contrôlés sur l'état final. La transaction est annulée entièrement en cas de commande invalide/interactions impossibles.

## Contrôles

- python -m unittest -v tests_standalone.test_action_combat_r65
- python -m unittest -v tests_standalone.test_action_runtime_r26 tests_standalone.test_game_session
- CI proposée : .github/workflows/r65-action-combat.yml (Python 3.10/3.12, Ubuntu).
- Le test d'indépendance du nombre de snapshots ne constitue pas une certification graphique physique 30/60/120 FPS.

## Reste à livrer

**R65.B :** Combat Composer Qt transactionnel, séquences et preview de hitboxes, télégraphies/patterns boss, Undo/Redo, Player, accessibilité et mouvement réduit.

**R65.C :** arène réellement jouable avec adversaires coordonnés et boss à deux phases, sauvegarde/reprise multi-phase, playtest humain, certification Qt/GPU et exports 3 OS. Dépendances R36/R53 sur la consolidation #412 à prouver avant toute certification.
