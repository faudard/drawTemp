# R53.C1 — Le relais hybride (3 compagnons / 2 combats natifs)

**Statut : PR #400, code candidat, gate R53.C complet non certifié.**

## Déroulement vérifiable

Nouveau modèle R15 Creator : `hybrid_r53`. Dans le Studio : Nouveau projet → modèle **R53 • Hybride RPG / tactique CT — Le relais**. Il fabrique les deux documents canoniques Content et GameProject via la transaction/export R15 existante. Aucune sauvegarde sidecar.

La fabrique `drawtemp.creator_examples.r53_hybrid.build_relais_hybride_r53()` réutilise le monde R41 Le relais du village, trois compagnons **Elya, Oren et Mira** (groupe actif initial, leader Oren, positions `front`, `flank_left`, `support`). La compétence native `lame_claire` est autorisée pour Elya + Oren via le combo exécutable `lames_du_relais`.

Les routes R25 suivent réellement les moteurs existants :

1. **Village** : changement de leader et positions via le R53 journal / API `GameSession`, inventaire et XP sous Campaign.
2. **Bois** : combat `RPG_TURN` R41 contre le loup, combo R53 et récompense or canonique (+12), sauvegarde/reprise au milieu de la rencontre.
3. **Crypte** : second combat `RPG_TURN` contre le gardien, victoire (+24), puis portail `crypt_to_ct` ouvert uniquement par le flag de victoire.
4. **CT** : le portail R25 déclenche `Campaign.prepare → Battle` natifs sur `relais_ct_reference`, avec les trois personnages et l'IA/action CT. Le combat a une récompense de mission de +9 or, réglée uniquement par `Campaign.finish`, après victoire réelle. Aucun second moteur CT.
5. **Retour** : `return_to_campaign` puis lien `ct_victory_to_village` avec `completed_mission` comme condition, ou retraite explicite `ct_retreat_to_crypt` après abandon, sans prime CT. Au village, la quête R41 paie +25 or et +2 potions **une seule fois**.

Le scénario de réussite attendu génère 70 or (12+24+9+25) et 3 potions (1 de départ +2 de quête), en l'absence de consommation d'objets. Ces valeurs sont issues de l'authoring de ce seul exemple, pas de calculs d'un faux moteur. Les tests exécutent la vraie IA du moteur tactique et refont les sauvegardes à deux seeds pour confirmer ces attentes; ils **ne sont pas attestés réussis** tant que la CI n'a pas publié ses logs.

## Projection read-only et contrôle Player

`GameSession.party_hybrid_state()` lit le leader, la formation, les membres actifs, XP, progression, or, objets et route depuis les objets canoniques. PV/PM sont visibles **seulement pendant le combat natif**, avec `vitals_source` (`RPG_TURN` ou `TACTICAL_CT`), `unavailable` hors combat. Après le retour d'un CT vers une scène mission, la phase est `ROUTE_TRANSIT` jusqu'au prochain portail d'exploration.

`Simulation.party_hybrid_state` renvoie une projection gelée protégée par revision; `PlayerController.state().r53_hybrid` est une valeur d'affichage. Le Player QML affiche le leader et les positions actives, avec un bouton de choix d'un autre leader pendant l'exploration. `PlayerController.switch_party_leader` transmet à la transaction de simulation existante et reste inopérant en combat/dialogue.

## Certificat de non-régression demandé

```sh
python -m unittest -v tests_standalone.test_r53_hybrid_slice
python -m unittest -v tests_standalone.test_r53_party_orchestration tests_standalone.test_r53_combo_rpg tests_standalone.test_r53_party_composer tests_standalone.test_r53_party_composer_qt tests_standalone.test_r53_player_combo
python -m unittest -v tests_standalone.test_r41_vertical_slice tests_standalone.test_r25_scene_router tests_standalone.test_game_session
```

Le test R53.C1 inclut : création de modèle R15, changement de leader, trois acteurs jouables, combo de compétence, deux combats RPG, vrai CT avec IA et commands enregistrées, sauvegarde/chargement avant/après et pendant le CT, routes verrouillées, récompenses idempotentes, deux seeds, refus des checkpoints manipulés même après re-hash du digest externe, et retraite sans gain illégitime.

## Limite P0 restante (NO-GO R53.C2)

**L'état actuel de `Campaign.HeroProgress` ne stocke pas les PV/PM courants.** `ClassicEncounter` et le moteur CT préparent chacun les acteurs depuis les sources canoniques, mais ne synchronisent pas leurs ressources vivantes entre modes. R53.C1 **ne revendique pas** la persistance des PV/PM au-delà du combat. Il faut spécifier et intégrer un ledger de vitalité unique, versionné et vérifiable, sans seconde autorité. Il faut aussi certifier la fermeture/reprise après crash aux frontières et la parité du rendu Player Qt onscreen et des entrées accessibles. Ce NO-GO interdit d'annoncer le gate complet R53 ou la release 10.0.
