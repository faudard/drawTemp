# Persistence 2.0 — Checkpoints et récupération

Cette étape est **empilée sur 2.4.1 GameSession**. Le stockage v2 est
optionnel et ne modifie ni le format des replays ni les anciens slots
`PlayerSession`. Aucune installation de Godot ni dépendance tierce.

## Checkpoints versionnés

```python
from sporebound.persistence import SessionStore, AutosaveSession

store = SessionStore("saves/campaign.session.json")
store.save(session)               # game_session v1 enveloppé en v2
session = store.load(content, project)

# Lorsque la reprise a eu lieu depuis la copie de secours :
outcome = store.load_with_status(content, project)
print(outcome.source, outcome.sequence, outcome.migrated_from_v1)
session = outcome.session
```

- **Version 2** : enveloppe `session_checkpoint` avec séquence monotone,
  empreinte SHA-256 et pointeur vers la génération antérieure.
- **Sous-document de jeu** : reste le replay vérifié `GameSession` v1 ;
  aucune mutation du contrat historique et aucune restauration directe
  d'états tactiques arbitraires.
- **Écriture atomique** : validation complète, copie de secours avec
  `write_json` et remplacement atomique du fichier principal.
- **Deux générations maximum** : `campaign.session.json` et
  `campaign.session.json.bak`. Aucun effacement d'une ancienne sauvegarde
  ne survient si la nouvelle ne passe pas la validation préalable.
- **Récupération** : charge le principal, sinon le secours *validé*.
  Le chargement ne réécrit jamais automatiquement un fichier endommagé :
  l'application peut indiquer `source="backup"` au joueur.
- **Sécurité de lecture** : taille limitée (64 Mio par défaut), version,
  structure, checksum, identité contenu/projet/règles et replay contrôlés.
  SHA-256 détecte des erreurs accidentelles ; ce n'est **pas** une signature
  cryptographique contre un attaquant disposant des fichiers locaux.

Ce modèle fournit des **checkpoints complets à deux générations**, pas
encore une chaîne de diffs incrémentaux. Les snapshots compacts sont un
chantier distinct à profiler sur de longues campagnes.

## Autosave explicite

```python
autosave = AutosaveSession(session, store)
autosave.perform("start_mission", "garden")
autosave.perform("execute", {"kind": "end", "facing": [0, 1]})
```

Seules les opérations autorisées et acceptées déclenchent un enregistrement.
Une commande invalide ne remplace aucun checkpoint. En cas d'erreur
d'écriture **après** une commande valide, la mutation en mémoire reste
effective et l'erreur remonte à l'appelant : le dernier checkpoint publié
demeure disponible. Les appels ne sont pas lancés en arrière-plan.

L'intégration automatique dans les boutons du joueur, la limitation
de fréquence et la prévisualisation « Reprendre après crash » restent
à faire lors de la migration du Player Shell.

## Migrer les anciens fichiers

```python
# Un fichier GameSession 2.4.1 v1 est lu tel quel puis converti à la
# prochaine sauvegarde explicite, avec conservation de la version v1 en .bak.
store = SessionStore("saves/ancien.session.json")
session = store.load(content, project)
store.save(session)

# Import non destructif d'un slot de campagne de l'ancien PlayerSession.
session = SessionStore.import_player_slot(
    "mon_jeu.game.json", project, content, "main", 1)
SessionStore("saves/import.session.json").save(session)
```

Une ancienne campagne **en cours de combat** ne peut pas être importée
comme bataille active si son slot n'enregistrait que la progression.
L'import n'invente pas un replay absent.

Le chargeur **refuse** les versions inconnues et les identités de projet
incompatibles. Aucune migration implicite des définitions de règles, de
contenu ou des futurs schémas n'est effectuée.

## Tests

```sh
python -m unittest discover -s tests_standalone -p test_persistence_v2.py -v
python -m unittest discover -s tests_standalone -v
```

Scénarios vérifiés : sauvegardes successives, interruption d'écriture,
principal tronqué, récupération du backup, refus de surécriture d'un
checkpoint corrompu, compatibilité v1, import de slot et échecs d'autosave.
