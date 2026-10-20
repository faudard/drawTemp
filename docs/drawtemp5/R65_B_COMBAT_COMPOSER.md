# R65.B — Combat Composer (Studio Qt / GameProject)

**État : lot R65.B à intégrer, certification R65 globale NO-GO.** Cette branche est volontairement empilée sur R65.A / PR #430 (elle ne suppose pas que R65.A est fusionnée).

## Architecture
- Données canoniques dans `GameProject.extensions["org.drawtemp.actioncombat"]`, enveloppe `schema_version=1`, payload `version=1` avec `presets[]` et `default`. Aucune base externe, script, sidecar ou second moteur d'action.
- Chaque preset contient `id`, `label`, `rules` R65.A (combo/projectile), des `telegraphs` (cue, kind, stage, lead_ticks) et des `boss_patterns` (ID, phase 1/2, seuil PV, étapes type/répétitions/attente).
- Contrats bornés : 12 presets, 24 cues/preset, 8 patterns/preset, 16 étapes/pattern, IDs uniques, entiers sans bool et schémas stricts. Aucun ancien projet dépourvu de l'extension n'est modifié.
- `GameProject.validate` refuse les catalogues R65 présents mais invalides, avant chargement et sauvegarde. Les futures versions sont explicitement rejetées, sans migration silencieuse.
- Le catalogue `sporebound.action_combat_catalog_r65` est consommable par `runtime_from_project(scene, project, preset_id=...)`. Ce point d'entrée construit le **runtime R65.A réel** avec les règles du projet, uniquement sur activation explicite. Le Player historique n'est pas activé implicitement.

## Studio
Depuis **Outils → R65 • Combat Composer action…**, la fenêtre `CombatComposerDialog` fournit :
- sélection/création des presets ; durée et puissance de chaque fenêtre `windup/active/recovery`, ordre des coups et cadence des projectiles ;
- tables des télégraphies et chorégraphies de boss, avec refus des valeurs invalides ;
- aperçu 9×9 de l'empreinte orientée de mêlée calculée par la géométrie R65.A et son test de mur/porte (centres de cases). Le choix du point de test ne constitue pas une animation native ni un vrai rendu GPU ;
- rapport de fenêtres en ticks, sans prétendre démontrer des animations/son/synchronisation R36 ;
- **Prévisualiser → Appliquer** sur `AuthoringSession.preview_project/apply` avec garde de révision, invalide la preview à chaque édition, Undo/Redo historique et refresh Studio. Le `Content`, les HP, le CT et les sauvegardes ne sont jamais modifiés par l'éditeur.

Le catalogue du boss est **des métadonnées inertes** tant que R65.C n'a pas branché un exécuteur de phases sur la GameSession. Les `telegraphs` sont des descriptions pour la preview (pas encore du VFX Player). Cette limitation est volontaire et validée par tests.

## Contrôles à exécuter

```bash
python -m unittest -v tests_standalone.test_r65b_combat_composer
QT_QPA_PLATFORM=offscreen python -m unittest -v tests_standalone.test_r65b_combat_composer_qt
python -m unittest -v tests_standalone.test_action_combat_r65 tests_standalone.test_action_runtime_r26
python -m unittest -v tests_standalone.test_game_session
```

La CI `.github/workflows/r65b-combat-composer.yml` prévoit Linux/Python 3.10 et 3.12, plus un smoke PySide6 offscreen. Les commandes et workflows sont des **gates proposés**, pas une preuve de tests exécutés ou passés. Exiger des résultats sur le SHA de la PR.

## R65.C — à livrer et à certifier

Un Player action réellement branché à ce catalogue et synchronisé au renderer/animations, la conduite des patterns par phase, deux ennemis coordonnés, une arène mêlée/distance, sauvegarde-reprise de phase, playtest humain, contraste/réduction des mouvements, preuves 30/60/120 FPS **sur matériel réel**, bundles Linux/Windows/macOS. De même, les dépendances R36 et R53 doivent être vérifiées sur leur état intégré après #412, pas considérées automatiquement certifiées.
