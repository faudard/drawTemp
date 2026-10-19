# R44.B — World Atlas Qt / Édition transactionnelle

**Statut : code sur PR #376 (non certifié, CI non concluante).**

## Entrée utilisateur

Studio Qt Widgets → **Outils → R44 • World Atlas 2.0…** (`drawtemp.studio.qt_shell`).

- Le volet gauche est un **diagramme d'authoring** QGraphicsView des régions, scènes et passages, pas un nouveau renderer de jeu. Le renderer partagé Studio/Player R3/R25 demeure inchangé.
- Le volet droit modifie l'affectation des scènes, les origines de carte, biomes et projections, ainsi que les portails déjà définis dans `GameProject.scene_routes`.
- Chaque portail atlas référence un ID R25 existant; les conditions R25 sont affichées en lecture seule. `travel_cost` n'avance aucune horloge et ne prélève aucune ressource.
- Un outil ajoute ou met à jour les déclarations de coffres, portes, switches et PNJ sur la scène. Les états réels restent dans `Campaign.story_flags` via les mécanismes du Player déjà existants.

## Validation et transaction

1. Lorsque `drawtemp.worldgraph` est absent, `default_world_atlas(session)` construit un brouillon à partir des scènes accessibles par les routes canoniques R25, sans modifier le projet. Les projets non routés sont explicitement refusés.
2. Toute modification de l'interface ne touche que ce **brouillon en mémoire**.
3. **Prévisualiser** utilise `AuthoringSession.preview_project`, qui revalide Content/GameProject avec `validate_world_graph` et rejette régions isolées, mauvais spawn, IDs inconnus, propriétés non bornées et versions incompatibles.
4. **Appliquer** enregistre **une seule** transaction Undo/Redo; un preview réutilisé ou dépassé est rejeté.
5. L'enregistrement sur disque reste l'opération commune du Studio (`AuthoringSession.save` / `save_as`) avec détection des conflits externes.

## Tests proposés

```bash
python -m unittest tests_standalone.test_r44_world_graph
python -m unittest tests_standalone.test_r44b_world_atlas
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r44b_world_atlas_qt
python -m unittest tests_standalone.test_r25_scene_router
```

Les cas couverts incluent amorçage mono-scène sans lien, prévisualisation sans effet, mutations de régions, coûts/conditions portails, objets, rejection de données non conformes, Undo/Redo et conflits de révision.

**Preuves restant nécessaires :** exécution CI effective, tests GUI onscreen, navigation clavier et ergonomie, captures GPU sur vrai poste, Player/export de la VS-44 à cinq régions. Les tests offscreen ne remplacent pas ces gates.
