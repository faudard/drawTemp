# Entity & Event Studio 3.0 — conditions composites et effets multiples

La version 3.0 **étend** le flux contextualisé de 2.0, sans nouvel éditeur,
sans interpréteur de triggers, sans contournement de GameSession.

## Parcours depuis la carte

1. Dans **Personnages et événements → Objets interactifs**, sélectionner une
   porte existante et son levier (ou créer un levier lié).
2. Choisir la case du levier, la case du danger, l'ID de l'événement,
   la cinématique, éventuellement un **tick minimum**, et sélectionner une
   **scène narrative préexistante** du Story Studio.
3. **Créer et simuler** conserve l'édition atomique Content + GameProject.
4. Ouvrir le **Graphe des événements** préexistant : le type principal reste
   `interact(lever)`. Dans **Condition**, ajouter des contraintes par
   **+ ET**, **+ OU** ou **+ NON**, puis observer leur expression.
5. Dans **Actions**, ajouter, remplacer, supprimer ou réordonner autant
   d'effets moteur que nécessaire (message, danger, statut, renforts, etc.).
   Les limites et références sont validées par Content.
6. Dans **Contexte et prévisualisation**, simuler l'état satisfait ou non
   satisfait. Le moteur construit un Battle jetable, fournit les changements
   avant/après, l'ordre des effets et les événements effectivement produits.
   La cinématique ciblée par `tactical_event` reste celle du Player.
   La scène optionnelle est liée par
   `story_authoring.set_tactical_scene` / `during_tactical_event` et
   s'ouvre par la file narrative authentifiée de `GameSession`.

## Contrat canonique

Les triggers continuent d'utiliser `Mission.triggers` et le registre
`rules.trigger_conditions`. L'extension optionnelle `when` impose une
condition supplémentaire au prédicat principal :

```json
{
  "id": "gate_alarm",
  "condition": "interact",
  "object": "switch",
  "when": {
    "all": [
      {
        "any": [
          {"condition": "tick", "value": 3},
          {"condition": "wave_capacity", "team": "enemy", "max_alive": 2}
        ]
      },
      {"not": {"condition": "defeated", "unit": "momo"}}
    ]
  },
  "actions": [
    {"kind": "message", "text": "La porte est ouverte"},
    {"kind": "hazard", "pos": [5, 5], "amount": 7}
  ]
}
```

Une feuille doit être une condition tactique **existante**, validée et évaluée
par son `TriggerConditionRule`. Le moteur ne possède pas un second système
d'interprétation des feuilles. Les opérateurs `all` / `any` contiennent
2 à 8 enfants; `not` contient un enfant; profondeur maximale : 4,
budget maximal : 32 nœuds. Les contenus sans `when` et le manifeste des
règles d'origine restent inchangés.

Le prédicat racine est toujours requis : ajouter `OU` ne remplace donc pas
l'interaction avec le levier. Dans l'éditeur, `+ ET` et `+ OU` combinent
les **contraintes secondaires**; `+ NON` nie la nouvelle feuille, tandis
qu'**Effacer les ajouts** préserve le trigger principal et ses actions.

## Tests de régression

```bash
python -m unittest tests_standalone.test_entity_event_studio_3 -v
python -m unittest tests_standalone.test_entity_event_studio_2 tests_standalone.test_event_graph tests_standalone.test_event_context tests_standalone.test_game_session -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_event_graph_gui -v
```

Les scénarios couvrent validation atomique, conditions AND/OR/NOT,
prévisualisation véridique, effets ordonnés, clip acquitté une seule fois
et sérialisation / reprise par `GameSession`. Les tests CI doivent confirmer
l'intégration après ouverture de la PR.

### Limites

- La prévisualisation d'un état *satisfait* prépare les feuilles compatibles
  avec le scénario; un ensemble contradictoire reste inactif ou remonte une
  erreur moteur plutôt que de produire une preuve inventée.
- Les composites sont appliqués **au moment du dispatch**; une interaction
  moteur ouvre intrinsèquement la porte lorsque son comportement le prévoit,
  même si une action secondaire conditionnelle ne se déclenche pas.
- L'éditeur de cinématiques existant reste responsable de la mise en scène.
