# R1.A — cœur sans UI et première API de simulation

Suite de R0, intégrée dans la même PR #220 tant que la fondation reste ouverte.
Cette tranche couvre **R1.1–R1.4 sur le parcours mission standard** : séparation
des dépendances graphiques, façade de simulation, snapshots immuables et
événements de présentation. Elle réutilise les sauvegardes et replays existants.
Elle ne clôture pas les dix lots de R1.

## Ce qui change

- Les identités et l'inférence de bâtiments vivent dans `architecture_model`,
  indépendamment du dessin et des atlas Tk. Les imports historiques depuis
  `iso_architecture` restent compatibles grâce aux réexports.
- Les outils de structures/groupes utilisent le module de données. Le graphe
  statique de **tous les imports connus**, même différés, ne présente plus de
  chemin de `drawtemp.core` / `drawtemp.sdk` vers Tk/Qt.
- `audit_drawtemp5.py --strict` rend cette absence obligatoire en CI. Le test
  dynamique bloque également les imports graphiques pendant les modifications
  de structures et une simulation complète.
- `Simulation` possède une copie privée de `GameSession` ; aucun `Battle`,
  `Campaign` ou acteur mutable n'est retourné aux clients.
- `GameSession.load` conserve désormais le type `IncompatibleSaveError` au lieu
  de le transformer en erreur de syntaxe générique. Il reste un `RuleError` :
  les anciens gestionnaires d'erreurs continuent donc de fonctionner.

## API expérimentale

```python
from drawtemp.sdk.reference import reference_project, MISSION
from drawtemp.sdk.simulation import Simulation, SimulationError

content, project = reference_project()
simulation = Simulation.new(content, project, "main", seed=17)
simulation.choose_story_option("enter")
simulation.start_mission(MISSION)

state = simulation.snapshot()
command = {"kind": "interact", "unit": "jeanne", "object": "lever"}
preview = simulation.preview(command, expected_revision=state.revision)
# La prévisualisation est isolée. On transmet la révision SOURCE pour appliquer.
transition = simulation.execute(command, expected_revision=preview.source_revision)
for event in transition.events:
    print(event.kind, event.tick, event.payload)

simulation.save("reference.session.json")
resumed = Simulation.load("reference.session.json", content, project)
# Simulation IA bornée et isolée : ne fait pas progresser resumed.
result = resumed.simulate(max_steps=700)
assert result.battle["result"] == "victory"
```

La façade R0 `SessionAdapter` est conservée : `snapshot()` y signifie encore
recording canonique, tandis que `Simulation.snapshot()` retourne un objet de
présentation. Le harnais R0 et sa référence gelée restent inchangés.

## Contrats

| Opération | Résultat / garantie |
| --- | --- |
| `new`, `load` | Handle indépendant ; règles et contenus validés par GameSession |
| `snapshot` | `StateSnapshot` frozen ; dictionnaires récursivement read-only et listes converties en tuples |
| `snapshot().to_dict()` | Copie JSON modifiable pour un bridge Qt ; aucun lien mutable avec le moteur |
| `choose_story_option`, `choose_tactical_story_option`, `start_mission`, `execute`, `return_to_campaign` | `Transition(source_revision, snapshot, events)` après réussite |
| `preview` | Exécute une commande dans une copie isolée ; aucun changement de la session source |
| `simulate` | Jusqu'à 1 000 commandes IA dans une copie ; arrêt au résultat, dialogue ou budget |
| `recording`, `save` | Format canonique actuel, avec ses contrôles de replay et son écriture atomique |
| `expected_revision` | Refus avant exécution si la révision fournie est obsolète |

Les révisions sont locales à un handle, repartent à zéro après chargement et ne
sont pas ajoutées aux sauvegardes. Ne jamais réutiliser un aperçu d'un autre
handle. Les snapshots contiennent campagne, missions disponibles, scène active,
état tactique complet, objectif et dimensions de carte. Ils ne sont pas un nouveau
format de sauvegarde et ne sont pas encore optimisés pour une production à 60 Hz.

Les `GameEvent` sont des enveloppes typées, immuables (`revision`, `index`, `kind`,
`tick`, `payload`). `kind` garde le nom du moteur, extensible selon ses règles.
Chaque transition retourne uniquement les nouveaux événements de sa bataille,
puis un événement `session.<opération>`. Les index sont locaux à la transition.
Le chargement ne rejoue pas d'animations automatiquement. Les demandes
d'animation spécifiques et le routage audio seront ajoutés avec la présentation.

Une action refusée restaure la session et conserve sa révision. Les erreurs de
règle sont des `SimulationError` avec codes `invalid_action`, `stale_revision`,
`invalid_session`, `invalid_save`, `incompatible_save`, `invalid_budget` ou
`io_error`. Les erreurs de programmation inattendues sont propagées après
rollback, pour ne pas les masquer sous un message utilisateur générique.

## CI Qt R0 : correction du prérequis Linux

La première exécution R0 a réussi sous Python 3.10/3.12/3.14 et pour Qt sur
Windows/macOS. Le job Qt Ubuntu a échoué au chargement de `libEGL.so.1`.
Le workflow installe désormais `libegl1` et `libopengl0` avant le smoke Qt.
Le mode offscreen/software ne supprime pas ces dépendances natives du loader.
Cette correction doit encore être confirmée sur le runner GitHub.

## Validation et suite

Tests : parité legacy/SDK jusqu'à victoire, sauvegarde/reprise et replay,
snapshots profondément immuables, payloads d'événements non modifiables,
prévisualisation sans effet de bord, refus des révisions périmées, rollback,
simulation bornée et détection d'incompatibilité. Les anciens tests de géométrie,
édition et groupes de structures restent exécutés.

Restent pour R1.B et suivants : commandes d'authoring/Undo-Redo (R1.5), migrations
versionnées (R1.6), certification élargie replay/persistance (R1.7–R1.8), worker
et annulation (R1.9), API publique stabilisée (R1.10). Les flux exploration, monde
et sièges restent disponibles dans GameSession mais ne sont pas encore exposés
par cette nouvelle façade. La CI historique conserve ses échecs recensés dans
R0 ; cette tranche ne prétend pas les avoir tous corrigés.

Validation locale : **84 tests ciblés réussis**, référence R0 inchangée et
parité également vérifiée depuis le package installé hors du dépôt. Audit actuel :
265 modules, zéro chemin UI initial ou différé depuis core/sdk. Les fonctions
d’identité/inférence extraites sont identiques à leurs versions historiques
(comparaison AST).
