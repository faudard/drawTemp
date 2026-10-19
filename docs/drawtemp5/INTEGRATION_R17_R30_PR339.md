# PR #339 — Consolidation R17–R30

## Objectif et provenance

Regrouper les 36 PR ouvertes en **une seule intégration** vers `master`. La PR #287 est couverte par la réintégration #293 ; les versions empilées sont reprises une seule fois dans l'ordre ci-dessous.

| Famille | PR d'origine |
|---|---|
| R17 | #287 → #293 ; #290 ; #311 |
| R18 | #302 → #310 → #322 |
| R19 | #301 → #309 → #320 |
| R20 | #295 → #307 → #323 |
| R21 | #291 → #308 → #317 |
| R22 | #294 ; #315 |
| R23 | #297 → #312 |
| R24 | #296 → #316 |
| R25 | #298 → #314 → #324 |
| R26 | #300 → #318 |
| R27 | #304 → #319 |
| R28 | #292 ; #298 → #306 → #321 |
| R29 | #299 → #313 |
| R30+ | #305 ; #303 |

## Résolutions d'intégration

- **Export natif :** cumuler les attestations et preuves de droits R17 avec les contrôles manifest et liens R23, sans revenir à un export permissif.
- **GameProject :** préserver `extensions` (R24) et les champs facultatifs `game_modes` / `scene_routes` (R25), sans migration forcée du format historique.
- **Studio Qt :** garder l'inspecteur validé R18, les plugins déclaratifs R24, les ateliers Profils de jeu et Gameplay R28, et les trois parcours de création (multi-genres, assistant canonique et modèle rapide). Les raccourcis Ctrl+N, Ctrl+Shift+N et Ctrl+Alt+N restent distincts.
- **Map Studio :** composer récupération transactionnelle R17, validation contextuelle R18, prévisualisation biome R22 et interactions de donjon R27. La sélection et la pose d'objets dans l'atelier Donjon restent un chemin distinct de la peinture de carte.
- **Player :** conserver récupération explicite et contrôle des empreintes R17, adapter les interactions d'action R26 et confirmer explicitement les cibles tactiques R18.

## Critères de revue avant fusion

1. Vérifier le diff final sur `master` et le SHA de la branche ; ne pas considérer les PR empilées comme fusionnées individuellement.
2. Exécuter les suites unitaires et les workflows concernés pour R17 à R30 sur Linux, Windows et macOS, en incluant Player/Studio Qt offscreen et replay/sauvegardes.
3. Faire les essais manuels de création de projet, de changement de modes, d'édition de cartes/donjons, d'export, de récupération et de déplacement tactique/action.
4. Maintenir les gates release **NO-GO** tant que les preuves GPU réel, licences, endurance, UX novice et installation machine propre ne sont pas réunies.
5. Ne clôturer les PR sources qu'après vérification de couverture, de CI et de revue de cette intégration.

**État :** brouillon d'intégration ; cette note n'est ni une certification R17–R30, ni un résultat de tests locaux.