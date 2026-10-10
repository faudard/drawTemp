# Unified Game Session — 2.4.1

`GameSession` est une **façade headless** reliant les composants déjà existants.
Elle n'introduit pas de règles tactiques, ne dépend pas de Tk et ne remplace pas
`PlayerSession` dans le client actuel.

## Exemple d'API

```python
from pathlib import Path
from sporebound.model import Content
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession

content = Content.load("sporebound/content/core.json")
project = GameProject.load("sporebound/content/core.game.json", content)

session = GameSession.new(content, project, "main", seed=42)
if session.active_scene():
    session.choose_story_option(session.available_choices()[0]["id"])
battle = session.start_mission("garden")
session.execute({"kind": "end", "facing": [0, 1]})

# Sauvegarde cohérente, y compris pendant le combat.
session.save("saves/unified.session.json")
restored = GameSession.load("saves/unified.session.json", content, project)
assert restored.active_battle.digest() == session.active_battle.digest()
```

### Fronts stratégiques

```python
# Les missions doivent avoir été débloquées par la campagne.
session.start_fronts({"gate": "garden", "courtyard": "hold"}, "gate")
session.set_doctrine("courtyard", "assault")
session.advance_fronts()
session.switch_front("courtyard")
session.execute({"kind": "end", "facing": [0, 1]})
```

`start_fronts` préserve les héros/classes/équipements préparés par
`Campaign.prepare`, mais délègue les combats et l'horloge globale à
`MultiFrontSession`. Seules les **victoires tactiques effectivement jouées**
accordent des récompenses ; une victoire stratégique hors écran ne le fait pas.
Chaque front possède une mission distincte et déjà déverrouillée.

## Contrats

- `GameSession.progress` est le roster `Campaign` existant ; les choix
  `StoryBook` et leurs conséquences sont appliqués sur une copie.
- `GameSession.execute` appelle `Battle.execute` ou
  `MultiFrontSession.execute`, jamais un moteur alternatif. L'intégration
  est transactionnelle jusque dans la finalisation de campagne.
- Les récompenses sont engagées **une seule fois** par combat joué ; elles
  ne sont pas allouées automatiquement aux fronts résolus hors écran.
- `return_to_campaign()` exige une rencontre terminée.
  `abandon_encounter()` est un abandon explicite, non une victoire.
- `save(path)` produit un document de session v1, écrit atomiquement
  (fichier temporaire puis remplacement). `load(path, content, project)`
  vérifie les empreintes du contenu, du projet, des règles et des replays
  intégrés avant de restituer la session.
- Toute mutation manuelle hors commande sur une bataille ou un front n'est
  pas enregistrable de manière vérifiable : le replay doit reconstruire
  le même état et la même empreinte.

## Compatibilité et limites

- Aucune modification des formats historiques de `Campaign.save`,
  `Battle.recording`, `MultiFrontSession.recording` et des slots
  `PlayerSession`. Les fichiers unifiés ne sont **pas** des anciens slots ;
  ne pas remplacer un `slot_N.json` par une session unifiée.
- Les changements de schéma `GameProject`, `Content` ou de manifeste des
  règles invalident les checkpoints : migrations et correspondances de
  versions sont prévues en **2.4.2**.
- Le client Tk n'est pas encore raccordé à cette façade. La UI et l'éditeur
  actuels gardent leurs flux historiques jusqu'à une PR de migration dédiée.
- `ai_turn()` est proposé pour les combats mono-mission ; dans les fronts,
  les commandes IA doivent passer par `execute()` pour rester journalisées
  dans le replay stratégique.
- Cette étape privilégie une API et une persistance de preuve d'intégration,
  pas la gestion optimisée de checkpoints incrémentaux ou l'autosave.
