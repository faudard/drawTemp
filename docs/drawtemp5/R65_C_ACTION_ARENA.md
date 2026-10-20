# R65.C — Arène d'action, boss à deux phases et replay v3

**Périmètre : prototype vertical slice opt-in** — ni fusion de release, ni certification complète de R65 ou de DrawTemp 11.0.

## Architecture et compatibilité

- `sporebound.action_arena_r65.ActionArenaR65` dérive de `ActionCombatR65` (R65.A). Les PV, déplacements, obstacles, dégâts, stamina, esquive, parade, cooldowns et récompenses continuent d'être gérés par le **même runtime headless**. La logique d'action ne dépend pas du renderer.
- Le catalogue source est celui de **R65.B** : les `boss_patterns` validés du preset déterminent réellement l'enchaînement des attaques du boss. Deux rôles flanc gauche/droit sont explicitement assignés à des IDs d'ennemis existants.
- Un combat requiert **exactement trois ennemis** distincts (deux flankers et un boss), deux patterns boss (phases 1/2, un chacun) et un seuil de phase 2 strictement inférieur à 100 %. Validation stricte/fail-closed à l'instanciation et au replay.
- Tick logique fixe **60 Hz**, sans horloge de rendu transmise à la simulation ; les pollings UI 30/60/120 peuvent produire le même nombre de ticks. IA en ordre d'ID stable. Pas de RNG ni scripts.
- Les flankers visent des positions opposées autour du héros puis exécutent des attaques **télégraphiées sur 5 ticks**. Les collisions acteurs restent celles de R26.
- Le boss lit chaque pattern R65.B, émet des télégraphies, temporise la fenêtre de lancement, exécute `melee`, `projectile` ou `dodge`, répète et avance. La phase 2 est déclenchée par ses PV **réels** et émet un événement `boss_phase`.
- Les tirs hostiles ont une trajectoire entière, des collisions balayées (≤80 unités par sous-pas), un TTL borné, une limite de 24 missiles, et infligent des dégâts via `_hurt_hero` (esquive/invulnérabilité/parade respectées). L'intégrateur des projectiles du héros reste celui de R65.A.
- La condition de victoire est la survie du héros après la mort des **trois ennemis** ; les récompenses sont celles de R65.A, une seule fois par ennemi. Aucune deuxième monnaie ni logique de progression n'est créée.
- `snapshot()["arena"]` expose phase, actions, flancs, projectiles, IDs et victoire. Toute projection est une copie, jamais un état modifiable par QML.

## Sauvegarde/replay

- Format **R65.C v3** indépendant de R26 v1 et R65.A v2. Le checkpoint JSON contient scène, preset, configuration, inventaire initial, commandes horodatées et empreintes SHA des entrées et de l'état final.
- `ActionArenaR65.load` rejoue les commandes depuis le tick 0 puis vérifie le digest. Les corruptions, commandes illégales, changements de règles/scène/IDs, versions inconnues sont refusés. L'intégralité de l'état du boss, flancs et projectiles figure dans le snapshot/digest.
- Le contrôleur Player remplace son runtime **uniquement après vérification complète** du checkpoint. La sauvegarde est atomique, via `write_json`. Les états hérités du combat R65 sont rollback en cas d'échec de step et les champs d'arène supplémentaires sont restaurés par la transaction externe.
- Il s'agit d'un **slot prototype propre à l'arène**, pas d'une sauvegarde GameSession / R50 canonique. Aucun transfert implicite de PV, or, équipement ou objets vers CT n'est revendiqué.

## Lancement PC

```bash
python -m drawtemp.player.r65_arena_app
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m drawtemp.player.r65_arena_app --smoke
```

L'application charge un scénario original de démonstration (arène des pierres). Elle exploite le renderer **TopDownViewport R3** partagé. Les projectiles sont affichés par une surcouche purement visuelle, sans seconde gestion des collisions. Touches : ZQSD/WASD/flèches mouvement, Espace combo, F tir, C parade, Maj esquive, Ctrl garde, P pause, F5 sauvegarde, F9 reprise, R respawn après défaite, M ou case à cocher réduction des mouvements.

Pour consommer explicitement un preset produit par le **Combat Composer R65.B**, fournir un couple valide Content/GameProject et son identifiant :

```bash
python -m drawtemp.player.r65_arena_app --content mission.json --project mission.game.json --preset mon_preset
```

Le preset choisi doit avoir les deux patterns de boss requis par l'arène ; aucune adaptation/migration silencieuse n'est faite. Les sources Content/GameProject sont validées avant l'ouverture de l'UI. **La démonstration garde sa carte et ses trois IDs d'ennemis fixes** ; charger une scène auteur externe est un chantier ultérieur.

## Tests et gates

```bash
python -m unittest -v tests_standalone.test_r65c_action_arena tests_standalone.test_r65c_arena_qt
python -m unittest -v tests_standalone.test_action_combat_r65 tests_standalone.test_r65b_combat_composer
python -m unittest -v tests_standalone.test_action_runtime_r26 tests_standalone.test_game_session
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m drawtemp.player.r65_arena_app --smoke
```

Ces commandes sont les **tests à exécuter**, et non une preuve que la CI a réussi. Les tests 30/60/120 portent sur le tick logique et les snapshots : ils ne certifient **pas** les performances GPU ni le rythme de rendu réel.

**R65 / 11.0 = NO-GO** tant que ne sont pas vérifiés : CI du SHA exact, vraie session Player avec boucle humaine, contrôleur clavier/manette sur matériel réel, compatibilité animation R36/audio, visuels lisibles et a11y du mouvement, crash-restart à chaque phase, goldens GPU 30/60/120, consommation p95/p99 et bundles propres Windows/Linux/macOS. La consolidation #446 et les intégrations R36/R53 doivent également être contrôlées avant la promotion vers `master`.
