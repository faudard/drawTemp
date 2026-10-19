# R48.A — Project Collaboration & Versioning: contrats Core

**Statut : code en PR, non certifié.** Ce premier incrément R48 met en place
une collaboration locale *headless* sur les documents canoniques
**Content/GameProject**. Il ne livre ni l'interface Qt R48.B, ni une
certification deux-auteurs R48.C, ni une garantie d'authenticité cryptographique.

## Contrats

- `ProjectRevision` : snapshot validé et immuable (charge JSON en octets
  canoniques), SHA-256 stable, `schema=1`, auteur descriptif et un ou deux
  parents SHA-256 déclarés. `make_revision` refuse les parents invalides,
  cycles triviaux et documents non validables. Le champ auteur n'est pas signé.
- `CollaborationController.compare(base, local, incoming)` : exige que
  les deux branches déclarent **exactement** le digest du parent `base`,
  vérifie que le local correspond au snapshot actif d'`AuthoringSession`
  et fournit des conflits sans écrire sur disque. La parenté est **déclarative**,
  elle ne remplace pas la vérification de l'ancêtre Git de R30.D.
- `CollaborationController.apply(review, decisions)` : décisions obligatoires
  `local` ou `incoming` pour chaque conflit, revalidation des snapshots,
  protection contre changements de révision et cycles edit/undo ABA,
  validation du couple puis un seul `preview_pair/apply` du Studio.
  Aucun `save()` implicite, aucune mutation Git ni du runtime.
- `semantic_review(..., typed_sequences=True)` : réutilise l'algorithme R30
  pour les missions et étend les séquences d'objets à identifiant stable :
  `project.story.scenes`, `project.campaigns`, `project.cinematics`.
  Les champs indépendants d'un même objet peuvent fusionner; les ajouts
  *append-only* de deux auteurs sont combinés de manière déterministe,
  local puis distant. Suppression, insertion en milieu et réordonnancement
  concurrents restent des conflits de liste entière à trancher explicitement.
  Les séquences d'actions, unités, choix, triggers et listes non reconnues
  conservent le traitement atomique prudent de R30.
- Le mode `typed_sequences=False` reste **le comportement par défaut** des
  APIs R30 pour préserver les scénarios existants.

## Utilisation headless

```python
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import CollaborationController, make_revision

# content0/project0 : paire canonique commune de départ
base = make_revision(content0, project0, author="base")
local_session = AuthoringSession.new(content0, project0)
# ... modifications d'Alice dans local_session via preview/apply ...
snap = local_session.snapshot().to_dict()
local = make_revision(snap["content"], snap["project"],
                      author="alice", parents=(base.digest,))
# ... Bob a modifié indépendamment les mêmes documents de départ ...
incoming = make_revision(content_bob, project_bob,
                         author="bob", parents=(base.digest,))

controller = CollaborationController(local_session)
review = controller.compare(base, local, incoming)
# Une UI propose une décision pour *chaque* review.conflicts :
choices = {conflict.path: "incoming" for conflict in review.conflicts}
transition = controller.apply(review, choices)
# Le Studio conserve l'Undo/Redo ; save reste un geste explicite.
```

## Tests et limites de certification

```bash
python -m unittest tests_standalone.test_drawtemp_r48a_collaboration -v
python -m unittest tests_standalone.test_drawtemp_r30_creator -v
python -m unittest tests_standalone.test_drawtemp_r30c_review -v
python -m unittest tests_standalone.test_drawtemp_r30d_git -v
```

Les tests R48.A couvrent merges indépendants, scènes, ajouts concurrents,
résolutions manuelles, parents divergents, intégrité SHA-256, validation
canonique, ancien mode R30, ABA et transaction Undo. La CI doit confirmer
leurs résultats sur le SHA de la PR. Pas de claim GPU/Qt onscreen/tri-OS.

## Tranches restantes

- **R48.A2** : refactor global d'IDs et graphe de références Content/GameProject
  avec preview/impact/résolution explicite, audits append-only liés aux SHA,
  rebase multi-générations et tests adversariaux de reprise.
- **R48.B** : panneau Qt Project History & Review, détail des conflits,
  provenance et commentaires localisés aux IDs, QTest et review onscreen.
- **R48.C** : fixture deux auteurs (carte + dialogue/quête), tests perturbations,
  sauvegarde et replay, export reproductible et gate d'intégration final.
