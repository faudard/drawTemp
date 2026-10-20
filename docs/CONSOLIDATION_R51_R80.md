# Consolidation R51–R80 — suivi d'intégration

> **Statut : 33/33 PR sources intégrées dans la branche de consolidation.** Cette intégration n'est pas un GO produit ni un accord de fusion vers `master`.

## Destination

- PR unique : [#446](https://github.com/faudard/drawTemp/pull/446) — **draft** vers `master`.
- Branche : `integration/consolidation-r51-r80-20261020`.
- Les PR sources ont été fusionnées **dans la branche d'intégration**, sans modifier `master`.

## Sources intégrées

- [x] [#413](https://github.com/faudard/drawTemp/pull/413)
- [x] [#414](https://github.com/faudard/drawTemp/pull/414)
- [x] [#415](https://github.com/faudard/drawTemp/pull/415)
- [x] [#416](https://github.com/faudard/drawTemp/pull/416)
- [x] [#417](https://github.com/faudard/drawTemp/pull/417)
- [x] [#418](https://github.com/faudard/drawTemp/pull/418)
- [x] [#419](https://github.com/faudard/drawTemp/pull/419)
- [x] [#420](https://github.com/faudard/drawTemp/pull/420)
- [x] [#421](https://github.com/faudard/drawTemp/pull/421)
- [x] [#422](https://github.com/faudard/drawTemp/pull/422)
- [x] [#423](https://github.com/faudard/drawTemp/pull/423)
- [x] [#424](https://github.com/faudard/drawTemp/pull/424)
- [x] [#425](https://github.com/faudard/drawTemp/pull/425)
- [x] [#426](https://github.com/faudard/drawTemp/pull/426)
- [x] [#427](https://github.com/faudard/drawTemp/pull/427)
- [x] [#428](https://github.com/faudard/drawTemp/pull/428)
- [x] [#429](https://github.com/faudard/drawTemp/pull/429)
- [x] [#430](https://github.com/faudard/drawTemp/pull/430)
- [x] [#431](https://github.com/faudard/drawTemp/pull/431)
- [x] [#432](https://github.com/faudard/drawTemp/pull/432)
- [x] [#433](https://github.com/faudard/drawTemp/pull/433)
- [x] [#434](https://github.com/faudard/drawTemp/pull/434)
- [x] [#435](https://github.com/faudard/drawTemp/pull/435)
- [x] [#436](https://github.com/faudard/drawTemp/pull/436)
- [x] [#437](https://github.com/faudard/drawTemp/pull/437)
- [x] [#438](https://github.com/faudard/drawTemp/pull/438)
- [x] [#439](https://github.com/faudard/drawTemp/pull/439)
- [x] [#440](https://github.com/faudard/drawTemp/pull/440)
- [x] [#441](https://github.com/faudard/drawTemp/pull/441)
- [x] [#442](https://github.com/faudard/drawTemp/pull/442)
- [x] [#443](https://github.com/faudard/drawTemp/pull/443)
- [x] [#444](https://github.com/faudard/drawTemp/pull/444)
- [x] [#445](https://github.com/faudard/drawTemp/pull/445)

## Dépendances résolues

- R62 : #423 (farming headless) est ancêtre de #444 (Farm Studio). L'intégration de #444 a inclus les deux.
- R65 : #430 (combat déterministe) puis #442 (Combat Composer).
- R78 : #436 → #439 → #440 (rôles, revues, vertical deux auteurs).
- R79 : #438 → #443 (ADR, RHI spike).

## Résolution des conflits

GitHub a fusionné les branches compatibles directement dans l'agrégat. Les PR conflictuelles ont été réunies par des commits de fusion à deux parents conservant l'ascendance et en combinant les ajouts sur les fichiers communs :

- #431 (R76) — commit `40f88a2` : entrée Optimizer Studio dans `drawtemp/studio/qt_shell.py` et fichiers propres.
- #435 (R75) — commit `155aebe` : entrée Narrative Assist dans le même shell et fichiers propres.
- #442 (R65.B) — commit `ff60452` : shell Qt et validation `GameProject` sans écraser les autres fonctionnalités.
- #423/#444 (R62) — commit `ac22176` : simulation, farming, catalogue Studio, extension projet, horloge unique et checkpoints.
- #427 (R63) — commit `9df255b` : Player QML, contrôleur, adaptateur Qt, simulation, Studio, validation projet, session et sauvegardes.

Les fusions conflictuelles combinent les changements textuels ; elles **ne prouvent pas** leur correction à l'exécution. Un audit métier de tous les écrans, commandes, sauvegardes et contrats R1 est requis.

## Gates avant fusion vers master

- [ ] CI complète sur le SHA final de #446 et matrice Linux/Windows/macOS.
- [ ] Tests unitaires et d'intégration `tests_standalone`, dont R62/R63/R65/R75/R76/R78/R79/R80.
- [ ] Vérifier la cohérence et le lancement de `drawtemp/studio/qt_shell.py`, `drawtemp/player/Main.qml`, `drawtemp/player/qt_app.py`, `drawtemp/player/controller.py`.
- [ ] Valider l'absence de doublon GameSession, la conservation du tick canonique, l'Undo/Redo et les commandes révisionnées.
- [ ] Éprouver sauvegarde/chargement/replay/migrations et isolation des extensions opt-in, y compris les combinaisons R61+R62+R63+R65.
- [ ] QA humaine Qt (Player et Studio), scénarios end-to-end et prévention des softlocks.
- [ ] Revoir les limites NO-GO propres aux recherches, plateformes futures et fonctionnalités expérimentales.
- [ ] Relecture des diffs, statuts de tests, licences et approbation de la fusion par une personne responsable.

**Ne pas fusionner la PR #446 vers `master` tant que ces cases ne sont pas traitées.** Les PR sources ne sont plus ouvertes, mais leurs clauses de non-certification restent applicables.
