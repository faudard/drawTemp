# R13.6 — Encounter Designer 2.0 (première tranche)

**Branche :** `feat/drawtemp5-r13-encounter-designer-2` — base `master` après consolidation #237.

Cette tranche complète le prototype R13 de la PR #232 avec un flux
**modifier → prévisualiser → simuler A/B → appliquer → annuler/refaire → enregistrer**.

## Capacités implémentées

- **Objectifs** : sélection parmi les règles de victoire canoniques
  (`eliminate`, `survive`, `extract`, `hold`, `crown` et identifiants
  déjà présents dans le contenu), édition des cases d'objectif, ticks,
  unité protégée et position de la relique via l'API headless.
- **Unités** : sélection dans la table, clic sur la carte pour déplacer
  l'unité, coordonnées X/Y, arme et comportement IA.
- **Terrain** : API de variante pour coûts, hauteur, couvert, danger,
  blocage avec validation de la carte et des collisions.
- **Avant/après** : deux vrais `run_lab` avec seeds appariées et même limite,
  replay vérifié, PV/CT/commandes et comparaison des écarts. Si les conditions
  de victoire changent, le résultat est marqué **non comparable** et
  exige une nouvelle baseline et une revue humaine.
- **Édition persistante** : `preview_authoring()` produit un plan du SDK
  `AuthoringSession` R1. L'interface demande confirmation explicite pour
  `apply`, fournit `undo`/`redo`, et sauvegarde avec le mécanisme
  transactionnel **Content + GameProject** uniquement sur demande.
- **Sécurité** : tout calcul de variante utilise un clone de `Content`.
  Aucun worker ne lit l'UI Qt. Une prévisualisation obsolète, une mission
  différente et toute modification du formulaire après le calcul empêchent
  l'application. Les changements disque externes restent protégés par R1.
  L'outil avertit avant de fermer un projet modifié mais non enregistré.

## Exécution

```bash
python -m unittest tests_standalone.test_drawtemp5_r13_encounter_designer -v
python -m unittest tests_standalone.test_drawtemp5_r13_qt -v
python -m drawtemp.studio.r13_workbench \
  --content sporebound/content/jeanne.json
```

PySide6 6.8.3 sous Python 3.12 pour l'interface Qt, selon la qualification
R0. Les API SDK et les tests headless ne dépendent pas de Qt.

Le workbench tente d'ouvrir le projet R1 associé au Content. **Si la paire
Content/GameProject n'est pas disponible ou ne peut pas être validée**, il
reste en mode **prévisualisation seule** : pas de faux bouton de sauvegarde,
pas d'écriture implicite de Content.

### Exemple Python

```python
from drawtemp.sdk.r13_encounter_authoring import (
    build_encounter, compare_draft, preview_authoring,
)
from drawtemp.sdk.authoring import AuthoringSession

studio = AuthoringSession.open("sporebound/content/core.json")
edits = {
    "unit_positions": {"hero": [2, 3]},  # choisir un ID réellement présent
    "objective": "extract",
    "goal_cells": [[4, 4]],
    "unit_overrides": {"foe": {"weapon": "ranged", "attack_range": 3}},
}
# Plan purement illustratif : les IDs/cases doivent exister et être valides.
# candidate = build_encounter(content, mission_id, edits)
# report = compare_draft(content, mission_id, edits, seeds=(1, 7))
# plan = preview_authoring(studio, mission_id, edits)
# studio.apply(plan)   # confirmation utilisateur dans l'application
# studio.save()        # opération explicite et transactionnelle
```

## Validation et limites

**Tests ajoutés** : mutations non destructives, collisions/unités inconnues,
objectifs incompatibles, modification de terrain, équipements rejetés si
incorrects, seeds et replays vérifiés, comparaisons non pertinentes refusées,
historique R1 avec annulation/rétablissement et previews périmées.

**Restant en R13.6** : pinceau visuel pour toutes les cases de terrain,
manipulation directe des objectifs/reliques, édition de l'équipement complet,
liaison aux docks définitifs du Studio Qt et vérification graphique Windows /
macOS / Linux. Ce lot ne prétend pas certifier R13 en totalité.

Les résultats simulés mesurent des **ticks CT et commandes**, jamais des minutes
réelles. La collecte de playtests humains demeure strictement opt-in.
