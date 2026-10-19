# R44.D — Player Qt World Atlas integration (PR #376)

**Statut : code poussé, non certifié.** Aucune seconde scène 3D/QML, aucune sauvegarde distincte.

- `GameSession.route_world_transition(route_id)` applique le hotspot R44 (portail à une case maximum), vérifie les conditions R25 via `WorldGraph.inspect_portal`, puis délègue exclusivement à `route_transition`.
- `Simulation.world_atlas_state()` fournit un **instantané gelé** d'une région, des sorties (condition vérifiée, proximité), des objets et de leurs flags, sans déplacer le joueur. Les nouvelles commandes `world_interact` / `world_transition` sont revision-guarded et rollback-safe par `Simulation._apply`.
- `PlayerController.world_interact` et `world_transition` assurent l'accès à la boucle Player, l'autosauvegarde et la compatibilité du slot R17. `explore_interact` délègue automatiquement aux objets R44 uniquement s'ils sont déclarés dans le WorldGraph.
- `qt_app.py` expose deux slots QML `worldInteract` et `worldTransition`. `Main.qml` affiche les sorties du World Atlas dans **l'écran d'exploration existant**, les conditions et distances, et utilise les commandes du bridge. Boutons nommés `r44Portal-<ID>` et `r44Object-<ID>` pour tests Qt.
- `scene_for_player` continue d'utiliser `scene_from_exploration` R3; aucun rendu parallèle n'est introduit.
- Les projets sans WorldGraph conservent les contrôles et actions classiques.

## Tests proposés

```bash
python -m unittest tests_standalone.test_r44d_player \
  tests_standalone.test_r44c_five_valleys \
  tests_standalone.test_r25_scene_router
python -m examples.r44_five_valleys --output /tmp/r44-five-valleys
QT_QPA_PLATFORM=offscreen python -m drawtemp.player.qt_app \
  --content /tmp/r44-five-valleys/five_valleys.json \
  --save-dir /tmp/r44-player-slots --smoke --smoke-scene exploration
```

Les tests Player vérifient la façade R1, le hotspot, le rejet d'une sortie verrouillée, les cinq régions, le retour sur une région visitée, le chargement d'un slot manuel et l'absence de régression de la référence Jeanne.

**Gate GUI réel restant** : interaction Qt/QML via souris/clavier sur une instance native, sauvegarde depuis les raccourcis, export Player R15 et mesure de performance sur les trois OS.

## Qt Quick GUI test (vraie interface)

```bash
# Utiliser deux dossiers qui n'existent pas encore.
python -m examples.r44_five_valleys --output /tmp/r44-five-valleys
QT_QPA_PLATFORM=offscreen python -m drawtemp.player.qt_app \
  --gui-world-journey \
  --content /tmp/r44-five-valleys/five_valleys.json \
  --save-dir /tmp/r44-player-gui-test
```

`--gui-world-journey` instancie le QML production, clique les boutons réels
`r44Object-relic` / `r44Portal-<route>` à chaque région, scrolle si nécessaire,
sauvegarde via F5, passe par le menu pause / écran titre / Continuer puis
vérifie le retour vers la crête avec un objet déjà activé. Une défaillance
renvoie un code de sortie non nul et affiche l'exception. Cette commande n'est
pas une preuve de qualification GPU tri-OS, mais constitue le gate GUI reproductible.
