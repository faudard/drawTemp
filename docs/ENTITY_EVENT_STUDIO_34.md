# Entity & Event Studio 3.4 — embranchements tactiques par choix

Cette tranche s'empile sur **#111 → #117 → #122 → #123**.
L'architecture reste unique : `StoryBook` autorise le choix, la
commande journalisée `Battle.execute(story_effects)` le consigne et
`rules.triggers.dispatch` exécute les effets des événements.

## Parcours d'authoring visuel

1. Dans **Story Studio**, créer une scène et au moins deux choix, par exemple
   « Attaquer » ou « Négocier ». Les choix conservent leurs conditions `when`,
   effets narratifs (`set_flag`, objets, déblocages) et effets tactiques
   (`open_door`, `hazard`, `status`, `wave`) déjà existants.
2. Depuis le graphe des événements, relier l'événement initial à cette scène
   grâce au lien tactique existant **Scène liée**.
3. Créer les événements correspondant aux deux conséquences, en conservant
   leur condition principale (par exemple `tick ≥ 0` ou `wave_capacity`).
4. Pour chacun, dans **Branchement par choix narratif**, sélectionner
   `scene/choice` puis **Lier au choix**. Le Studio ne propose que les scènes
   accessibles par les liens tactiques de cette mission.
5. Utiliser **+ Lier événement** pour exiger un prédécesseur et
   **+ OU rejoindre** pour faire converger un événement commun depuis
   l'une des deux branches incompatibles. Les liens OR sont visibles sur le
   même graphe. **Effacer choix** et **− OU retirer** restent annulables
   par l'historique habituel.
6. Sélectionner l'événement initial et **Simuler branches**. L'aperçu produit
   un résultat distinct pour chaque choix actuellement disponible :
   nouveaux événements, différences tactiques, drapeaux narratifs, scènes
   suivantes, cinématiques et chemins exclus.

La convergence permet aussi un « retour » sûr vers un événement commun
après des chemins alternatifs. **Les boucles de scènes narratives restent
interdites par le StoryBook** : le retour ne réintroduit pas de cycle de
séquences ni de réexécution infinie d'un trigger one-shot.

## Contrat de données

Tous les champs suivants sont **facultatifs**, dans les `Mission.triggers`
canoniques déjà validés :

```json
{
  "id": "branch_assault",
  "condition": "tick",
  "value": 0,
  "after": ["decision_point"],
  "after_choice": {"scene": "garrison_choice", "choice": "fight"},
  "actions": [{"kind": "hazard", "pos": [5, 5], "amount": 12}]
}
```

Pour le point de réunion des branches :

```json
{
  "id": "meet_again",
  "condition": "tick",
  "value": 0,
  "after_any": ["branch_assault", "branch_truce"],
  "actions": [{"kind": "message", "text": "Rassemblement"}]
}
```

- `after` = **ET**, tous les événements mentionnés doivent être exécutés.
- `after_any` = **OU**, au moins un événement doit être exécuté.
- `after_choice` = garde obligatoire sur l'événement `story_choice`
  effectivement enregistré (`scene`, `choice`).
- Les trois s'ajoutent à la condition `condition` et au `when` composite.
- `Content.validate` contrôle identifiants, arités, cycles mixtes
  (`after` + `after_any`) et structure `after_choice`.
- `GameProject.validate` vérifie la scène, la réponse et la
  **visibilité depuis un lien tactique dans la même mission**.
- Les missions sans `after_choice` conservent le timing antérieur des
  commandes `story_effects`, ainsi que les règles/replays historiques.

## Jouabilité et replay

Lorsqu'un joueur choisit une réponse dans `GameSession` :

1. `StoryBook.choices` confirme qu'elle est disponible (drapeaux narratifs).
2. `StoryBook.choose` enregistre ses effets et ses ramifications.
3. `Battle.execute(story_effects)` applique ses effets tactiques et émet
   `story_choice` dans la commande déjà journalisée.
4. **Si la mission déclare au moins un `after_choice`**, le dispatcher
   existant déclenche les branches admissibles et les réunions OR, dans
   le même point de commande.
5. `GameSession` détecte leurs éventuelles nouvelles scènes tactiques,
   les ajoute à sa file après la scène courante, et préserve la priorité
   d'un éventuel `next_scene` narratif.
6. `Battle.replay` et `GameSession.from_recording` attestent les
   vrais résultats du Player.

La commande `GameSession.execute` refuse toujours l'injection directe
de `story_effects` ; seul le choix de dialogue autorisé peut la créer.

**Précision sur la prévisualisation :** le Studio prépare parfois
artificiellement un tick ou un placement dans un `Battle` jetable.
La prévisualisation exécute les *vraies* commandes et les *vraies* actions
mais ne se présente **jamais** comme un replay certifié :
`replay_verified = None`. Les tests de jeu authentiques sont distincts.

## Tests

```bash
python -m unittest tests_standalone.test_event_choice_branches_34 -v
python -m unittest tests_standalone.test_event_chains_32 tests_standalone.test_event_debugger_33 tests_standalone.test_entity_event_studio_3 tests_standalone.test_event_condition_tree_31 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_event_graph_gui -v
```

Gate : « Attaquer » ne peut pas activer « Négocier » ; réciproquement
« Négocier » ne peut pas déclencher l'assaut. Chaque choix rejoint une
unique fois l'événement commun, et sauvegarde + reload + replay
reproduisent exactement le résultat tactique, les drapeaux narratifs
et les dialogues en attente.
