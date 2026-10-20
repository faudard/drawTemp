# R38.3A — Refactoring transactionnel des références typées

**Statut : implémentation dans la PR #377, validation CI en attente.**

## Domaine pris en charge

La première tranche du R38.3 permet le **renommage des identifiants d'objets et d'acteurs locaux à une mission**. Une identité est toujours le triplet `(famille, mission, ID)`, jamais une chaîne globale.

L'algorithme suit et met à jour exclusivement les références typées reconnues :

- ID canonique de l'objet/unité dans `Content.missions[].objects/units`.
- Liens entre objets (`link`), champ `protected_id`, appartenance `editor_groups.object_ids/unit_ids`, clé `unit_levels`, tags de formation `formation:escort:ID`.
- Conditions/actions R9 possédant des champs typés `object`, `object_id`, `unit`, `unit_id`, `actor_id` ; prédicats imbriqués inclus.
- Graphes R31 de la même mission, **avec vérification d'égalité des triggers R9 générés avant réécriture** puis recompilation via le compilateur R31 existant. Une modification R9 indépendante incompatible bloque le renommage.
- Provenance des instances R38.2 : mapping des IDs placés vers les nouvelles identités canoniques, sans modifier les IDs du prefab source.

Les projets sans extension R31/R38.2 conservent leur format. Les zones de dialogue et chemins de ressources ne sont jamais traités par remplacement de texte.

## API headless

~~~python
from drawtemp.sdk.r38_refactor import (
    preview_rename_identity, apply_rename_identity,
)
review = preview_rename_identity(session, "objects", mission_id, "gate", "gate_new")
for change in review.changes:
    print(change.path, change.before, "->", change.after)
# Aucune mutation avant cette validation explicite :
transition = apply_rename_identity(session, review)
# session.undo() et session.redo() restent les seules opérations historiques.
~~~

Le `RefactorReview` porte une liste déterministe de `RefactorChange` (chemin, avant, après) et un `AuthoringPlan` R1 attaché à sa révision. Un aperçu obtenu avant une autre modification, même si cette modification est annulée ensuite, est périmé et non applicable.

## Studio Qt

Menu **Outils → R38 • Renommer les références typées…**. Sélectionner la famille, la mission, l'ancienne ressource et le nouvel identifiant ; cliquer sur **Prévisualiser les impacts**. Après revue des chemins concernés, **Appliquer en une transaction** enregistre tout dans Content et GameProject avec un seul Undo/Redo.

## Garanties et restrictions

- Les nouveaux identifiants doivent être uniques dans la famille et la mission, de forme `[A-Za-z][A-Za-z0-9_-]{0,63}`.
- Aucun renommage inter-missions implicite ; d'autres missions peuvent conserver le même ID.
- Maximum 1024 impacts explicites par opération ; refus si dépassement.
- Validation de la paire Content/GameProject par le moteur canonique avant engagement. Les extensions opaques contenant des dépendances typées correspondantes sont refusées tant qu'un adaptateur explicite n'existe pas.
- Ce lot ne traite **pas encore** les ID de missions, assets, scènes, campagnes, cinématiques, quêtes, graphes et tous les espaces de noms personnalisés. Ce sont des chantiers R38.3B distincts.
- Une recherche textuelle peut révéler davantage d'usages ; elle ne suffit jamais à autoriser une transformation structurelle.

## Vérification

~~~sh
python -m unittest tests_standalone.test_drawtemp_r38_refactor.RefactorTests -v
python -m unittest tests_standalone.test_drawtemp_r38_refactor.RefactorQtTests -v
python -m unittest tests_standalone.test_drawtemp_r38_search -v
python -m unittest tests_standalone.test_drawtemp_r38_prefabs -v
~~~

Gates : atomicité preview/apply, isolation des missions, conservation des dialogues, références R9, recompilation R31, divergence R31/native, groupes, identifiants en collision, révision obsolète après Undo et navigation Qt. **Le code ajouté n'implique pas que les tests soient passés : vérifier les logs GitHub Actions avant fusion.**

Suite : R38.3B adaptateurs de renommage pour IDs de mission, assets et scènes, puis refactor inter-documents et projets multiples.
