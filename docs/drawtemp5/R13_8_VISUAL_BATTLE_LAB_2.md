# DrawTemp 5.0 — R13.8 Visual Battle Lab 2.0 : graphiques comparatifs

Fonctionnalités de comparaison fusionnées dans **#243** ; la présente tranche ajoute l'export PNG complet et les notes d'exploitation.

## Fonctionnalités

Depuis `python -m drawtemp.studio.r13_workbench --content sporebound/content/jeanne.json`,
ouvrir une mission et :

1. Onglet **Encounter Designer** → éditer un placement, un objectif ou le
   comportement/arme, puis **Prévisualiser & simuler A/B**.
2. Onglet **Graphiques A/B** → consulter les **barres Avant / Après** des
   quatre indicateurs : victoire (%), ticks CT p95, commandes p95,
   activations CT moyennes par combat.
3. Comparer chaque **seed** pour les ticks CT, les commandes ou les
   activations (sélecteur). Les barres sont normalisées *à l'intérieur de
   chaque ligne*, uniquement pour faciliter la lecture ; les valeurs
   chiffrées affichées restent les valeurs exactes des simulations.
4. Cliquer sur une ligne → mise en évidence de la seed et synchronisation
   avec le tableau des résultats canoniques (onglet Battle Lab).
5. Pour les simulations normales, charger un ancien rapport Battle Lab via
   **Charger la référence** : la comparaison n'est affichée que si elle
   possède la même mission, la même liste ordonnée de seeds et le même
   budget de commandes. Sinon, l'interface affiche une simulation simple et
   un avertissement explicite sur l'incompatibilité de la référence.

Les sources sont exclusivement `sporebound.battle_lab.run_lab()`,
`drawtemp.sdk.r13_combat_lab.compare_encounters()` et
`drawtemp.sdk.r13_encounter_authoring.compare_draft()`. Aucune estimation
artificielle de décisions IA, d'actions ou de durée humaine n'est générée.

### Fiabilité et interprétation

- Un rapport ne peut produire de graphique qu'avec des samples canoniques
  cohérents et des `replay_verified == True` pour **toutes** les seeds.
- Une comparaison est **appariée** : pas de regroupement aléatoire ni de
  rapprochement entre seeds différentes.
- Le modèle visuel est du JSON pur, indépendant du framework UI, utile aux
  tests et autres présentations futures (`build_visual_comparison`).
- Une modification des conditions de victoire est marquée non comparable
  par R13.6 et le modèle visuel exige une nouvelle référence et une revue
  humaine. Un changement de contenu ou de règles nécessite également
  confirmation humaine.
- Le bouton **Exporter graphiques PNG** capture la totalité des deux
  graphiques, y compris les seeds non visibles dans le panneau défilant ;
  il refuse explicitement d'écraser un fichier existant.
- Les couleurs indiquent uniquement **avant/référence** et **après/
  candidat**, jamais une amélioration ou une dégradation implicite.
- Les métriques CT/commandes/activations proviennent du moteur et ne
  représentent **pas** le temps effectivement passé par un joueur.
- Le rendu utilise uniquement **Qt Widgets / QPainter**, sans module
  QtCharts supplémentaire.

### SDK

```python
from drawtemp.sdk.r13_visual_metrics import build_visual_comparison

single = build_visual_comparison(report)
paired = build_visual_comparison(before, after)
# Si l'objectif a changé :
review = build_visual_comparison(before, after, objective_changed=True)
# paired["series"] contient les valeurs observées agrégées et par seed.
# paired["comparison"] contient les alertes issues du gate R13.
```

### Tests

```bash
python -m unittest tests_standalone.test_drawtemp5_r13_visual_metrics -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp5_r13_visual_qt -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp5_r13_qt -v
```

La matrice GitHub Actions exécute la partie headless sur Python 3.10 et 3.12
(Windows, Linux, macOS) et les tests Qt en mode offscreen sur Linux/Python 3.12.

## Limites restantes R13.8

Cette tranche livre **les graphiques comparatifs, l'inspection par seed et la
liaison au Battle Lab**. Il reste notamment les graphes de décisions IA par
type de comportement, la chronologie des dégâts/soins par unité, les cartes de
chaleur des déplacements, la lecture animée du replay et des visualisations
multiniveaux intégrées au viewport isométrique. Le gate humain R13 complet
et les validations visuelles multi-plateformes sont toujours requis.
