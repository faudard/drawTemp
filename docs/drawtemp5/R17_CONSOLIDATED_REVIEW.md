# DrawTemp R17 — PR de consolidation des lots #277 à #284

Cette branche est partie du commit de R17.D (#282), lui-même descendant
de R17.C2 (#281) et R17.C1 (#280), puis a intégré explicitement les commits
de #277 (audit), #278 (fallback d'animation R7), #279 (syntaxe certification),
#283 (export natif R15/R17.8) et #284 (parité Studio/Player R17.5).

Le commit d'intégration est un merge avec tous les heads comme parents. Ainsi,
le contenu ne dépend **d'aucune fusion préalable sur master**, et les 8
historiques sont conservés. Il ne faut pas fusionner séparément les branches
intermédiaires après cette PR.

## Résolution des chevauchements

- `drawtemp/render/qt_viewport.py` : inclut **à la fois** les marqueurs
  R9.C (viewport isométrique) et les correctifs R7 contre les sprites périmés.
  `_visual_base_items` garde une base R4 détachée de chaque frame R7.
- `docs/DRAWTEMP_5_0_TO_6_0_DETAILED_ROADMAP.md` : un état de
  consolidation unique, plus l'addendum d'audit R17.A ; les annonces
  intermédiaires divergentes ne sont pas empilées.
- Toutes les autres modifications sont reprises via les SHA des blobs
  Git originaux, **pas** par copie approximative d'un patch.

## Inventaire des PR regroupées

| PR | Contrat livré |
|---|---|
| #277 | Merge ledger réel + tests Git synthétiques |
| #278 | Sprite R7 : fallback propre d'atlas/pose |
| #279 | Réparation P0 de certification et test AST |
| #280 | R9.D Core/Event Pages et replay |
| #281 | R9.C graphe Qt, catalogue, marqueurs, UI des pages |
| #282 | R17.D parcours Studio→Player→save/reprise |
| #283 | Export natif, atlas partagés, archives contrôlées |
| #284 | Parité réelle R3 des scènes, QML, pixels et picking |

## Vérification d'intégration

La CI R17 consolidée exige les tests headless (Python 3.10 et 3.12) et les
tests Qt/QML Windows, Linux et macOS ; les workflows spécialisés R3/R7/R9/R12/
R14/R15 restent en service. Les pipelines rouges doivent être examinés,
pas ignorés par une apparence de fusion réussie.

**Sortie non certifiée** : signature des exécutables, licences de
redistribution, mesure GPU matérielle, revue des goldens, tests sur PC vierge
et autres gates R17 P0. Une CI logicielle verte ne signifie pas que la version
5.0 est releasable.

### Consigne de fusion

Fusionner **uniquement cette PR** sur `master`, une fois les critères
de vérification satisfaits. Les PR originales doivent être clôturées en tant
que « remplacées par la consolidation », et non marquées manuellement
comme fusionnées dans `master`.
