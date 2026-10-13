# 3.7.21F — conséquences tactiques immédiates et rejouables

## Parcours Auteur → Player

1. Dans le **Graphe des événements**, créer un trigger de mission, par
   exemple `interact` sur le levier `switch`.
2. Dans **Scénario & dialogues**, lier une scène à `garden/<trigger>`
   via **Lier dialogue tactique** (3.7.21E), puis sélectionner un choix.
3. Sous **Effets tactiques rejouables**, sélectionner `open_door` et la porte
   `gate`, `status` et sa durée, `hazard` et sa case, ou `wave` avec
   un ID de renfort, un archétype, un camp et une case.
4. Cliquer **Ajouter effet tactique** et enregistrer le projet. L'undo/redo
   du Story Studio fonctionne via le même historique que les autres choix.
5. Lancer la mission dans le Player. Le dialogue interrompt le combat.
   Le choix peut attribuer des effets de campagne existants, mais applique
   aussi les conséquences tactiques immédiatement, puis reprend la Battle.
6. Sauvegarder et recharger : portes, états, dangers et renforts sont
   **recalculés par le journal de commandes**, pas restaurés à partir
   d'une copie non vérifiée du terrain.

## Format d'auteur

Les choix de scènes peuvent contenir un champ *optionnel* `tactical_effects` :

```json
{
  "id": "raise_gate",
  "label": "Levez la herse !",
  "effects": [{"kind":"set_flag","flag":"castle_breached","value":true}],
  "tactical_effects": [
    {"kind":"open_door","object":"gate"},
    {"kind":"status","unit":"ziggy","status":"haste","duration":10}
  ]
}
```

Types acceptés et strictement validés :

- `open_door` : ouvre et déverrouille la porte authentique ; met à jour
  la traversabilité sans simuler une interaction joueur fictive.
- `hazard` : change le danger d'une case par l'action des règles existantes.
- `status` : applique un statut à un acteur existant par le moteur.
- `wave` : déclenche des renforts avec les contrôles habituels de
  capacité et d'occupation ; maximum 8 renforts par effet.

Les références sont vérifiées **pour chaque mission** susceptible
d'atteindre une scène partagée par des embranchements `next_scene`.
Les choix tactiques non liés à une mission, les types d'effets arbitraires,
les portes inexistantes et les zones hors carte sont refusés avant sauvegarde.

## Contrat de replay et d'intégrité

- Une décision prise pendant une bataille écrit une commande
  `story_effects` dans `Battle.commands`, même si `tactical_effects`
  est vide. Ce type est réservé au chemin validé
  `GameSession.choose_tactical_story_option` ; le chemin public de
  commandes tactiques refuse son injection.
- La commande contient l'ID de scène, l'ID du choix et la liste exacte
  des effets validés. `Battle.execute` la traite atomiquement.
- `Battle.replay` exécute ces mêmes commandes et vérifie le digest
  final. Aucune dépendance à Tk, aucune modification du format de
  `Battle.recording` v3 ou du manifeste de règles.
- `GameSession.from_recording` vérifie en plus les choix par rapport
  à l'historique de campagne, les scènes atteignables depuis les
  événements réellement déclenchés et les effets auteurs du projet.
- Si une cible n'est plus disponible lors de l'application (un renfort
  avec un ID déjà utilisé, par exemple), **le choix entier échoue** :
  progression, journal de combat, état de carte et file narrative sont
  restaurés à l'état avant sélection.

## Limites

- Seulement les missions tactiques seules déjà couvertes en 3.7.21E ;
  pas de décision sur un front hors focus.
- Les modifications d'objectifs de mission et les transformations de
  morale systémique ne sont pas incluses ; `status` permet cependant
  de représenter un soutien ou un malus tactique avec les règles existantes.
- Le format de sauvegarde de session reste compatible avec les anciennes
  sauvegardes dépourvues de commandes de choix ; le replay vérifié conserve
  les règles d'origine.

## Tests

```sh
python -m unittest tests_standalone.test_replayable_story_effects \
  tests_standalone.test_tactical_dialogue tests_standalone.test_narrative \
  tests_standalone.test_game_session
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_narrative_gui
```
