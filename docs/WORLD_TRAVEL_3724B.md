# 3.7.24B — Continuous World Journey (first playable slice)

The 3.7.24A World Map (#109) already renders the canonical mission graph.
This follow-up adds a **real, persistent party cursor** traveling between
accessible locations. It deliberately does **not** add a new mission graph.

## Player contract

- Open **Carte du monde** from the campaign (no pending narrative dialogue).
- Click a reachable unlocked/completed destination. The party travels along
  the existing `Mission.next_missions` connections, including reverse trips.
- Movement is interpolated across each map edge; every step is checkpointed
  via the existing `PlayerController._apply` / `SessionStore`. Reopening a
  save mid-route restores the party's current interpolated position and goal.
- Click a mission **at the party's location**, with no journey in progress,
  to enter its normal cinematic, deployment and battle. Locked/completed nodes
  cannot launch a mission. Clicks on unrelated/locked nodes do not unlock them.
- The campaign mission list remains available for legacy projects and
  missions omitted from a partial map. Authored world destinations instead
  direct the party to the World screen before they can be entered.

## Data ownership and compatibility

`sporebound/world_travel.py` is headless. It derives the traversable roads
from the canonical campaign graph, filtering nodes against the saved
`Campaign.unlocked` and `Campaign.completed`. Four bounded story flags
(`world_walk_at`, `world_walk_goal`, `world_walk_via`,
`world_walk_step`) use the existing Campaign v1 save contract. They are
absent until first travel. No `tile.height`, battle coordinates, new
`.game.json` fields, schema migration or world-specific save file is used.

All reloaded journey states are validated, including route adjacency, allowed
missions and step range. The same map can be edited in Studio; world pin
positions remain cosmetic and excluded from the project fingerprint.

## Gates

```sh
python -m unittest tests_standalone.test_world_travel_3724b -v
python -m unittest tests_standalone.test_world_map_3724a -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_world_map_3724a_gui -v
```

## Remaining for continuous exploration 3.7.24C+

This slice is continuous **along authored world routes**, not unrestricted
free movement across a landscape. Off-road travel, authored waypoints,
contextual encounters, seamless entrance into existing exploration stages,
camera zoom/pan and geography-based region transitions remain to be designed
against the existing `Exploration` and `GameSession` contracts.

## 3.7.24C — Pathfinder-inspired events on canonical roads

Add an optional `events` list to the existing `world` manifest.
Each entry binds an existing road (two linked Mission IDs) to an existing
`story.scenes` scene, with an optional StoryBook `when` condition.
Several encounters may occupy the same road at distinct authored
`step` positions. Every event is once-only per campaign. Legacy encounters
without a `step` occur halfway through the road, in either direction.

```json
{
  "id": "caravane",
  "from": "garden",
  "to": "escape",
  "scene": "road_caravane",
  "when": {"completed_mission": "garden"}
}
```

The normal StoryBook choice UI takes over the Player; the party remains
positioned halfway along the route. The selected choice can apply any
existing validated narrative effects (gold, flags, unlocks, equipment, etc).
Once the choice resolves, travel resumes from its saved position. Mid-event
saves and recovery use the usual verified GameSession snapshot.

- `world_evt_<id>` marks each once-only encounter; `world_walk_event`
  tracks a paused root choice and `world_walk_reverse` the optional
  backtracking leg. No bespoke event log or dialogue/replay schema is introduced.
- Event specifications are gameplay content in the checkpoint fingerprint,
  while purely decorative world coordinates remain excluded.
- Projects without world events retain their pre-existing digest and saves.
- Use `python -m examples.world_route_events_3724c --output /tmp/roads.json`
  to generate a playable, choice-driven world journey with tactical consequences.
- Gate: `python -m unittest tests_standalone.test_world_events_3724c -v`.

Deferred: random event tables, encounter combat on routes, cooldowns/repeatable
events, branching physical roads and a dedicated event inspector in Studio.

## 3.7.24D — plusieurs événements et embranchements de voyage

Le même trajet peut contenir plusieurs événements ordonnés par la distance
`step` (1 à 7), sans superposition physique. Les anciennes définitions sans
`step` restent positionnées au milieu du segment (4/8).

Les choix de la **scène StoryBook existante** peuvent définir un `routes`
sur l'événement de voyage (clé = identifiant de choix de la scène) :

```json
{
  "id": "caravane",
  "from": "garden",
  "to": "escape",
  "scene": "scene_road_caravan",
  "step": 2,
  "routes": {
    "back": {"kind": "return"},
    "north": {"kind": "destination", "mission": "hold"},
    "south": {"kind": "destination", "mission": "crown"},
    "avoid": {"kind": "continue"}
  }
}
```

- **continue** (également valeur implicite) : reprendre le parcours prévu.
- **return** : parcourir les pas déjà franchis en sens inverse jusqu'au
  carrefour de départ, puis s'y arrêter.
- **destination** : parcourir les pas en sens inverse vers le carrefour,
  puis calculer le chemin canonique vers la destination choisie. La scène
  peut débloquer cette mission avec un effet narratif normal, sans que le
  voyage ne contourne les règles de déblocage.

L'événement est déclenché à un point géographique constant, même lorsque le
sens du trajet est inversé. Chaque événement est rencontré au plus une fois
par campagne. Un choix de détour erroné laisse le dialogue et la sauvegarde
inchangés. Le jeu conserve `world_walk_reverse` pendant le demi-tour et
`world_walk_event` tant que la scène initiale attend sa première décision.
La reprise après sauvegarde valide ces deux états comme le trajet aller.

La démo `world_route_events_3724c` présente désormais deux événements
sur la même route et deux embranchements authorés (`hold` et `crown`) ;
les nouvelles connexions sont ajoutées seulement à la copie du contenu
générée pour cette démonstration.

Gate : `python -m unittest tests_standalone.test_world_forks_3724d -v`.

## 3.7.24E — éditeur visuel des rencontres de voyage

L'onglet **Monde** existant possède maintenant un inspecteur latéral :
- cliquer sur le trait d'une route autorisée (liens canoniques
  `Mission.next_missions`), ou sur une pastille `!` d'un événement existant ;
- créer une rencontre, saisir son ID, sélectionner une **scène StoryBook
  existante** et la position 1..7/8 sur le tronçon ;
- afficher plusieurs rencontres d'une même route, les sélectionner,
  les modifier et les supprimer ;
- associer individuellement chaque choix réel de la scène à `continue`,
  `return` ou `destination` avec sélection de la destination sur la carte ;
- afficher le texte, les choix, leurs effets et les itinéraires dans un
  aperçu **sans mutation** ; continuer d'éditer le contenu narratif
  (conditions, dialogues, effets) dans l'éditeur de scènes existant.

Les mutations sont validées via `GameProject.from_dict` et consignées dans
le `StudioHistory` transversal. `Annuler`, `Rétablir` et `Enregistrer
tout` concernent une seule version de `GameProject.world`, sans toucher au
contenu tactique. Le renderer Player reste inchangé : les pastilles `!`
de l'éditeur ne divulguent pas les rencontres en jeu.

Validation :
```sh
python -m unittest tests_standalone.test_world_event_studio_3724e -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_world_event_studio_3724e_gui -v
```

Limite explicite : le panneau propose une **prévisualisation statique** de la
scène et du branchement configurés, pas une exécution de campagne. La
simulation narrative/tactique complète et le sélecteur visuel des conditions
composites restent des extensions ultérieures du Story Studio.

## 3.7.24F — Laboratoire de voyage interactif

L'onglet **Monde** propose un laboratoire isolé, utilisant `GameSession`
et `StoryBook` réels. Sélectionner campagne, départ et destination, puis :

1. **Initialiser** une simulation en mémoire (aucun slot de sauvegarde).
2. **Un pas** ou **Jusqu'au prochain événement** : avancer sur les routes
   canoniques et interrompre à la première scène narrative éligible.
3. **Décider** via l'ID d'un choix disponible, avec vérification des
   conditions, effets `gold`, drapeaux, déblocages et branchements.
4. Voir sur la carte un tracé azur et le curseur mobile, et dans le journal
   les lieux traversés, événements, décisions, demi-tours et écarts de
   progression (or, inventaire, flags, missions, recrutement).
5. **Nouvelle destination** après l'arrivée ou **Réinitialiser** pour
   retrouver un état initial. Les changements du projet dans le Studio
   invalident automatiquement la simulation en cours.

Le **mode auteur** (opt-in explicite à l'écran, activé par défaut)
n'accorde temporairement que les étapes de la *route initiale demandée*.
Les autres embranchements restent verrouillés, à moins qu'une décision
narrative ne les ouvre via les effets normaux du moteur. Pour tester les
contraintes d'une nouvelle campagne réelle, désactiver le mode auteur ;
les voyages vers des destinations encore verrouillées seront refusés.

Les introductions de campagne sont ignorées **uniquement dans une session
synthétique** et ce choix est consigné ; les autres scénarios narratifs sont
résolus normalement. Le simulateur n'enregistre jamais de contenu, n'altère
pas la `GameProject` ou `Campaign` d'origine, et ne modifie aucun replay.
Il ne prétend pas simuler les combats : les effets tactiques éventuels
restent à tester dans le Player.

Gates :
```sh
python -m unittest tests_standalone.test_world_travel_lab_3724f -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_world_travel_lab_3724f_gui -v
```
