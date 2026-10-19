# R35.D2 — NPC transfers inter-scènes, Player vivant et charge

**Statut : code proposé sur la branche unique de la PR #339 ; pas encore fusionné dans master.** Ce document décrit le contrat implémenté. Le volet interactivité Player et les performances sont à certifier par CI et validation visuelle.

## Transferts entre deux scènes d'exploration

L'extension `GameProject.extensions["org.drawtemp.livingworld"]["data"]` peut déclarer une liste facultative de portails **orientés** :

```json
"transfers": [
  {
    "id": "village_to_forest",
    "from_scene": "village",
    "to_scene": "forest",
    "from_pos": [8, 4],
    "to_pos": [0, 3],
    "travel_minutes": 4
  },
  {
    "id": "forest_to_village",
    "from_scene": "forest",
    "to_scene": "village",
    "from_pos": [0, 3],
    "to_pos": [8, 4],
    "travel_minutes": 4
  }
]
```

- Maximum 64 passages par projet, durée 1–240 minutes du monde ; deux scènes distinctes existantes dans `GameProject.exploration`, cellules non bloquées.
- Un passage est directionnel. Pour revenir, créer un deuxième passage. Les doublons d'identifiant ou de direction sont rejetés.
- Lorsqu'un document `transfers` existe, **chaque saut inter-scènes d'un PNJ doté de coordonnées** doit posséder le passage correspondant. Les vieux projets sans `transfers` conservent l'ancien comportement `handoff_pending` sans trajectoire continue.
- Le temps minimal nécessaire est le nombre de cellules du chemin vers la sortie + `travel_minutes` + le nombre de cellules vers l'objectif dans la scène de destination. Un horaire irréalisable est refusé à la validation du projet, avant la sauvegarde.
- Le départ s'effectue aussi tard que possible pour arriver exactement à l'heure de l'arrêt suivant. Pendant le transit, `scene=null`, `pos=null`, `activity="travel"` : le PNJ est temporairement absent des deux zones, puis réapparaît à l'entrée du portail de destination. Aucune interpolation trans-scènes fictive, téléportation visible sur une carte ni tick mural.
- Les conditions narratives `when` peuvent rendre une activité `unavailable`, mais ne modifient jamais le chemin physique d'un PNJ déjà spatialisé. Aucun déplacement n'avance durant CT ou simplement parce que le rendu tourne.

## Productivité et mémoire

- `sporebound.living_world_transfers.compile_legs` compile les trajectoires à partir des scènes canoniques et conserve un cache de géométrie par trajet partagé. Les requêtes `LivingWorld.view` et `npc_pose` ne relancent plus de BFS, même hors focus.
- L'index interne `_npc_by_id` accélère la recherche d'un PNJ : lecture du monde bornée par le nombre de PNJ et d'arrêts, sans scan de toute la population pour chaque PNJ.
- Limites : 256 PNJ, 32 arrêts/PNJ, 64 portails, scènes 32 × 32, au plus 2048 entrées sur les historiques de commerce existants. Une compilation de grandes routes peut être coûteuse **au chargement**, mais pas dans la boucle de rendu.
- Aucun chiffre p95/p99 CPU, consommation mémoire ou FPS n'est revendiqué en l'absence de banc exécuté et d'un matériel de référence ; le gate R35.10 requiert encore ces mesures.

## Intégration dans le Player Qt

- `Simulation.living_world_state(scene=...)` donne une projection immuable ; `Simulation.living_world_advance` passe par la transition R1 et sa révision, avec rollback si refusée.
- `PlayerController.state()["living_world"]` présente l'heure, le jour, les PNJ de la scène. Le rendu R3 `scene_from_exploration(..., living_world=...)` ajoute des acteurs purement visuels avec un identifiant préfixé `world:`, sans modifier les véritables acteurs d'exploration ou les données de campagne.
- L'interface QML montre l'heure, les activités et une commande **Attendre 1 minute** qui prend le vrai `ticks_per_minute` du projet. Aucun minuteur graphique ne crée de ticks de simulation en arrière-plan.
- L'éditeur Qt Studio → Outils → Monde vivant permet de saisir et supprimer les passages dirigés (scènes, X/Y, durée) depuis les dialogues de l'atelier, puis de prévisualiser les trajets avant un apply Undo/Redo.
- Si une scène n'a pas de monde vivant, la présentation et les commandes classiques restent inchangées.

## Tests et certification

```bash
python -m unittest tests_standalone.test_r35_transfers -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r35_transfers_qt -v
```

Le premier scénario couvre le chemin détaillé entre deux scènes, le transit où le PNJ n'est affiché nulle part, le trajet inverse, minuit, 256 PNJ, l'absence de pathfinding par appel de rendu, les refus de données incohérentes et la projection Player SDK. Le second couvre la saisie Qt hors écran des passages et le fait que leur éditeur n'applique aucune mutation automatiquement.

**À venir :** certification du Player Qt onscreen, gestion de plusieurs portails distincts entre les mêmes scènes, chemin multi-scènes avec étapes, animation interpolée visuelle, collisions dynamiques entre PNJ/joueur, profils p95/p99 CI et validation de la démo joueur.
