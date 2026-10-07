# Architecture autonome

Le cœur ne dépend ni de Tk, ni de Godot, ni du filesystem. La même frontière
`Battle.execute(command)` est utilisée par le terminal, l’éditeur, l’IA et les replays.

| Module | Responsabilité |
| --- | --- |
| `model.py` | Contrats typés, contenu JSON versionné, validation des références et valeurs |
| `engine.py` | Horloge CT, commandes atomiques, règles, objectifs, événements, RNG et replay |
| `ai.py` | Évaluation déterministe des actions et positions avec les prévisions du moteur |
| `campaign.py` | Progression, jobs, achats, inventaire, loadouts et récompenses uniques |
| `storage.py` | Écriture JSON temporaire puis remplacement atomique, chargement vérifié |
| `editor.py` | Document validé, undo/redo, authoring de carte et interface Tk de playtest |
| `__main__.py` | CLI, simulation, équilibrage multi-seeds, parties manuelles et campagne |
| `content/core.json` | Contenu autonome de travail, embarqué dans le paquet |

## Source de vérité

Les positions sont des couples entiers `(x, y)`, les hauteurs des niveaux entiers.
La carte est clairsemée : une case absente a les propriétés par défaut. La sauvegarde
ne contient pas de widgets, textures, objets Godot ou références externes.
Les objets de mission et unités sont copiés dans chaque combat ; le document auteur
reste indépendant du playtest et de la progression.

## Commandes

Exemples :

```json
{"kind": "move", "cell": [2, 3]}
{"kind": "act", "skill": "flare", "cell": [5, 3]}
{"kind": "item", "item": "potion", "cell": [2, 3]}
{"kind": "interact", "object": "switch"}
{"kind": "end", "facing": [0, -1]}
```

Le champ optionnel `unit` doit correspondre à l’unité active. Toute commande illégale
restaure l’état, les événements, le journal et le RNG. Les interfaces doivent conserver
les identifiants plutôt que des références d’objets entre commandes : le rollback
peut remplacer les instances. Les commandes acceptées sont enregistrées pour le replay.

L’IA peut inspecter les règles mais n’a pas de chemin d’exécution privilégié. Les
prévisions n’avancent pas le RNG. Les égalités CT sont départagées par l’ordre initial
des unités ; les choix IA ont un départage explicite, sans dépendre des adresses mémoire.

## Sauvegarde et compatibilité

Une sauvegarde embarque le contenu initial, la mission, la seed, l’identifiant de
combat et les commandes. Le chargement reconstruit le combat puis compare le hash
SHA-256 de l’état, RNG et événements inclus. Il détecte les fichiers corrompus ou les
règles incompatibles. C’est un format de replay vérifié, pas une signature de sécurité.

Le format JSON est versionné. Les sauvegardes sont garanties pour les mêmes règles ;
une future modification des règles nécessite une migration/version de simulation.
Le chargement coûte le temps de rejouer la partie ; des checkpoints seront nécessaires
pour les très longues sessions. Le rollback copie actuellement l’état pour privilégier
la correction ; il devra être profilé avant de viser de très grandes batailles.

Les versions Godot sont des références historiques, sans import au runtime autonome.
