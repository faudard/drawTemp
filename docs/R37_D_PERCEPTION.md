# R37.D — Perception déterministe, bruit, poursuite et capteurs visuels

**État : implémentation poussée sur PR #371 ; exécution des tests et gate global R37 encore non certifiés.**

## Autorité des données

- Capteurs optionnels dans le même `GameProject.extensions['org.drawtemp.advancedai']` R37, par PNJ temps réel : `sensor = {'version': 1, 'facing': 'west', 'vision_range': 5, 'hearing_range': 6}`.
- Chaque PNJ muni d'un capteur doit être un PNJ *positionné* par R35 sur toutes ses étapes d'horaire. Aucun registre de position secondaire n'est introduit.
- La grille `GameProject.exploration` existante est la seule source des obstacles. La position du héros vient des flags de campagne / état R25 et celle du PNJ de `LivingWorld.npc_pose`.
- La vision applique une limite de portée Manhattan (1–16) et un cône cardinal de 90° (`north/south/east/west`) ou `omni`, avec lancer de rayon *supercover* entier. Les coins bloqués des deux côtés empêchent de voir à travers les diagonales.
- L'audition suit le chemin BFS 4-voisins déterministe R35 jusqu'à 16 cases **lorsque la dernière commande de déplacement non nulle est issue du journal R25 validé**. Aucune simulation de niveau sonore/décibels ou propagation d'ondes n'est revendiquée. Un input contre un mur peut être considéré audible : il s'agit d'une **intention de mouvement**, pas de la preuve d'un pas accompli.
- Navigation : `shortest_path` R35 est réutilisé, sans nouveau navmesh ; le rapport fournit `path`, `path_length`, `next_step`, `reachable`. Aucun déplacement de PNJ n'est appliqué par le diagnostic.

## Mémoire et explication

- `GameSession.ai_perception_preview(actor_id)` retourne un rapport read-only : `visible`, `within_cone`, `within_vision_range`, `los_clear`, `heard`, `alert`, `signal`, cause de décision et trajet potentiel.
- Les faits du contexte R37 exposent `enemy_visible`, `noise_heard`, `alert`, `target_reachable` **uniquement pour les agents qui déclarent un capteur**. Les projets R37.A/B/C qui n'en ont pas conservent leurs contrats.
- `GameSession.ai_observe(actor_id)` est une **commande explicite**, autorisée seulement lorsque le PNJ est dans la scène d'exploration active. Elle enregistre sa mémoire via le journal de blackboard R37.B et ne peut être déclenchée qu'une fois par acteur et par tick R35.
- Une observation visuelle met `suspicion=3`, une observation sonore à `2`, chaque nouvelle observation explicite sans signal diminue d'un cran jusqu'à zéro. Pas de timer visuel ni de compte à rebours caché.
- La dernière position connue est mémorisée sous `last_known_x` et `last_known_y` (valeurs entières portables) et peut définir le chemin quand la cible n'est plus perceptible. La position courante de la cible **n'est pas révélée** quand il n'y a ni signal ni mémoire active.
- Le checkpoint `GameSession` reste le v1 existant, avec le journal de mémoire opt-in ; son rejeu refuse une mémoire divergente ou des ticks futurs. L'analyse de perception ne modifie jamais le journal tactique.

## Studio

- **Outils → Perception & Navigation R37.D…** ouvre `AISensorDialog`.
- Réglages : orientation de vision, distance maximale de vision, distance d'audition, scénario de mouvement audible.
- **Prévisualiser** simule **uniquement un scénario authored** (premier arrêt du PNJ et cellule de départ de la scène), explicitement identifié comme simulation. Ce n'est pas une perception effective pendant un playtest.
- **Valider puis Appliquer** passe exclusivement par `AuthoringSession.preview_project` / `apply` ; l'historique R1 offre Undo/Redo, refus des valeurs invalides et détection des prévisualisations obsolètes.

## Exemple

```python
project.extensions['org.drawtemp.advancedai']['data']['agents'][0]['sensor'] = {
    'version': 1, 'facing': 'west',
    'vision_range': 5, 'hearing_range': 6,
}
project.validate(content)
game = GameSession.new(content, project, 'main', seed=29)
report = game.ai_perception_preview('traveler')   # pure
observation = game.ai_observe('traveler')           # écrit le blackboard
decision = game.ai_decision_preview('traveler')    # pure, aucune action lancée
```

## Gates / limitations

```bash
python -m unittest tests_standalone.test_r37_perception -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r37_perception_qt -v
python -m unittest tests_standalone.test_r37_ai_decision tests_standalone.test_r37_ai_session tests_standalone.test_r37_behavior_tree -v
```

Couverture voulue : angles morts, ray-casting des coins, occlusion, champ de vision, impossibilité de traverser une carte coupée, bruit fondé sur journal R25, suspension en combat, mémoire atomique, checkpoint/replay, validation auteur, Undo/Redo, Qt offscreen.

**Non implémenté dans ce lot** : orientation dynamique des PNJ liée aux déplacements, émission de sons par attaques/dialogues, distribution des alertes à une escouade, exécution des commandes de poursuite, plateformer/physique R32, véritables boss à phases et vérification visuelle en jeu. Cela relève des lots R37.D suivants / R37.E. L'IA CT historique est inchangée.
