# DrawTemp 5.0 — R1.B : authoring transactionnel sans interface

**PR dépendante de #220 (R0 + R1.A).** Ne pas fusionner cette branche sur
`master` avant la fondation; le code est construit sur l'API
`drawtemp.sdk.simulation` ajoutée par #220.

## Portée réellement implémentée

Cette tranche implémente le pont **R1.5 (Authoring Commands)** entre le futur
Studio Qt et les validateurs/commandes existants. Elle expose aussi les premières
primitives de **R1.8 (Persistence SDK)** pour l'édition de projets : save pair,
refus des écritures concurrentes et récupération de crash explicite. Elle ne
termine ni les migrations versionnées R1.6, ni les replays R1.7, ni les workers
R1.9 et la stabilisation API R1.10.

- Un seul modèle métier : `Content` et `GameProject` du runtime existant.
- Aucun import Qt ou Tk dans `drawtemp.sdk.authoring`.
- Commandes de carte typées **réutilisées** depuis
  `sporebound.editor_architecture`, via `command.transform`.
- Édition `GameProject` seule et édition atomique du couple de documents.
- Aperçu validé sur copies isolées, snapshot profondément immuable et
  révision monotone pour refuser les previews périmées, y compris après Undo.
- `StudioHistory` reste l'autorité pour Undo/Redo; **une édition
  cross-document = une transaction d'historique**.
- `StudioTransactionStore` reste l'autorité pour enregistrer
  `*.json` + `*.game.json`, avec empreintes de disque et journal de reprise.
- Aucune modification des sauvegardes et replays du Player.

## API expérimentale

```python
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.editor_architecture import EntityCommand

content, project = reference_project()
studio = AuthoringSession.new(content, project)
before = studio.snapshot()
command = EntityCommand(
    "edit", "actor", "jeanne", fields=(("name", "Jeanne — nouvelle tenue"),)
)

plan = studio.preview(command, MISSION)
assert studio.snapshot() == before  # Preview sans mutation

transition = studio.apply(plan)
assert transition.source_revision == before.revision
assert transition.snapshot.can_undo
studio.undo()
studio.redo()

# Nouveau projet seulement : ne remplace jamais un fichier existant.
studio.save_as("/tmp/jeanne.json")
reopened = AuthoringSession.open("/tmp/jeanne.json")
assert reopened.snapshot().content == studio.snapshot().content
```

Pour une ressource propre à `GameProject`, utiliser
`preview_project(transform)`. Pour une action devant changer les deux
documents simultanément (par exemple trigger + cinematic),
`preview_pair(transform)` exige un couple de dictionnaires validables.
Les transformeurs sont des fonctions Python *fiables* du code Studio et ne sont
pas des scripts fournis par un projet utilisateur.

Les `AuthoringTransition` contiennent la révision de départ, le nouveau
snapshot, le type d'édition et les vues concernées. L'interface Qt consomme ces
transitions côté thread GUI; aucune notification n'est envoyée depuis des
threads Python et aucun objet `Battle` mutable n'est exposé.

## Contrats et erreurs

| Situation | Résultat |
| --- | --- |
| Plan d'un autre handle | `AuthoringError(code="foreign_preview")` |
| Plan obsolète après mutation/Undo/Redo | `stale_revision` |
| Commande invalide ou document incohérent | `invalid_edit` |
| Opération sans changement | `unchanged`, aucun historique |
| Modification de fichier par un autre outil | Sauvegarde refusée, source préservée |
| `save_as` vers un document existant | Refus `destination_exists` |
| Crash entre les deux publications | Journal conservé; `open` refuse et demande récupération |
| Récupération | `AuthoringSession.recover(path, "complete" / "rollback")` explicite |

`save_as` crée uniquement un nouveau couple de documents; `save` vérifie
les empreintes disque retenues depuis la dernière ouverture/sauvegarde.
Les préférences locales de l'éditeur restent hors de ces documents.

La version de l'API **reste expérimentale** : le Studio Qt ne l'utilise pas
encore, et les éditions de carte/event complètes, sélection, contrôles du
renderer et providers async ne sont pas déclarés livrés par cette PR.

## Gates et validation

```sh
python -m unittest tests_standalone.test_drawtemp5_r1_authoring -v
python -m unittest tests_standalone.test_drawtemp5_r0 \
  tests_standalone.test_drawtemp5_r1 \
  tests_standalone.test_drawtemp5_r1_authoring -v
python scripts/audit_drawtemp5.py --check --strict
```

Couverture : vraies commandes `EntityCommand`, snapshots détachés,
prévisualisation pure, refus inter-handles et ABA, paire cross-document,
Undo/Redo, sauvegarde/rechargement, partie Jeanne passant par `Simulation`,
concurrence disque, interruption contrôlée, récupération et import sans Tk/Qt.

**CI de branche à exécuter** : Python 3.10/3.12/3.14. Aucun résultat
exécuté n'est déclaré dans cette documentation; suivre les checks de la PR.

## Suite

- **R1.6 :** migrations versionnées et prévisualisation non destructive.
- **R1.7 :** certification élargie des scénarios, fronts, exploration et replay.
- **R1.8 suite :** gestionnaire de sauvegardes du Player, checkpoints longs.
- **R1.9 :** validation/simulation asynchrone et invalidation des calculs.
- **R2 :** premier Studio Qt ancré dans un vrai Resource Explorer et un inspecteur.
