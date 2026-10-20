# R43.B2 — Éditeur de formules compositionnelles et Balance Lab

**Statut : code proposé, PR empilée sur R43.B1 (#391) et R43.A (#373).
Gate R43 non validé.**

## Contrat partagé

Les nœuds `constant`, `stat`, `add`, `subtract`, `percent`
sont **exactement** l'AST de `drawtemp.sdk.ability_contracts` R43.A.
`drawtemp/studio/ability_formula_graph_r43.py` ne crée ni JSON de
formules alternatif ni nouvel interpréteur. `evaluate_formula` reste
l'unique évaluateur, avec entiers, saturation 0..10 000 et profondeur/nœuds
bornés. Pas de `eval` / `exec` / référence arbitraire / code utilisateur.

L'éditeur manipule un **arbre**, pas un DAG de références. Les nœuds ont
des chemins structurés `()`, `("left",)`, `("input",)`, etc.
Retaper un nœud est **explicite**, copy-on-write, avec validation du résultat
complet avant remplacement. Les sous-arbres non concernés restent intacts,
et un opérateur arithmétique conserve autant que possible ses entrées.

## Édition dans le Studio

Depuis R43.B1, sélectionner un effet puis **Éditer le graphe de formule** :

1. Sélectionner l'opérateur actuel dans l'arbre et son chemin.
2. Choisir un opérateur typé et ses paramètres dans l'inspecteur.
3. Remplacer le nœud; parcourir les ports enfants si nécessaire.
4. Voir les valeurs brutes de la formule sur trois profils.
5. Confirmer : le résultat reste dans `AbilityDraft`, sans écriture;
   **Prévisualiser**, puis **Appliquer (1 Undo)** valide la paire canonique.

Annuler le dialogue n'affecte ni le brouillon, ni Content, ni GameProject.
Changer d'effet ne doit plus écraser les AST avancés via les contrôles
simplifiés. Les anciens graphiques R43.A sont éditables sans migration.

Le graphe n'autorise aucun cycle, lien inter-compétence ou nœud externe
arbitraire. Toute extension exige une évolution explicite du contrat R43.A.

## Balance Lab : limites explicites

Le bouton **Balance Lab** calcule, pour chaque effet et trois profils de
statistiques `Faible`, `Référence`, `Élevé`, des puissances brutes
reproductibles et les sommes pour `damage`/`heal`. Aucun tirage RNG,
simulation multi-seeds, probabilité de touche, cible, réduction d'armure,
multiplicateur AoE, statut appliqué, combo ni temps réel. Les résultats
**ne représentent pas les dommages/soins réels** du runtime Battle/Player.

## Garde-fous et régressions

- 31 nœuds / profondeur 5 : mêmes budgets que R43.A;
- valeurs typées (les booléens ne sont pas des entiers acceptés);
- chemins structurés inconnus ou modification dépassant un budget : refus;
- AST source non muté après une opération échouée;
- champs complexes préservés dans `AbilityDraft`, même à travers
  preview/apply/undo/redo si le mode est déclaré compatible;
- **CT dynamique interdit** : le `compile_ct_skill` R43.A reste
  fail-closed sur tout opérateur autre que `constant`;
- action et RPG : plans déclaratifs, **sans execution Player** à ce stade.

## Tests à exécuter

```sh
python -m unittest tests_standalone.test_drawtemp_r43_ability_contracts tests_standalone.test_drawtemp_r43b_ability_draft tests_standalone.test_drawtemp_r43b2_formula_graph -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r43b_ability_qt tests_standalone.test_drawtemp_r43b2_formula_qt -v
```

CI `.github/workflows/r43b2-formula-graph.yml` : headless tri-OS et
Qt offscreen Linux. Les preuves de passage des jobs doivent être établies
après lancement réel; une CI sans jobs ne vaut **aucune certification**.

## Étapes restantes R43.B3 / R43.C

- Espace de ciblage natif R3 (cônes, LOS, entités, clavier/manette).
- Contrats de coûts calculés, ressources, duration/stacks/dispel combos;
  bridge explicite CT/Action/RPG avec choix de ticks, interruptions,
  cooldowns et persistance GameSession.
- Balance Lab multi-seeds tirant réellement sur les runtimes et traces R13;
  animation/FX R36 synchronisés, accessibilité.
- Slice 4 compétences (AoE + combo), save/replay, export Player, mesures
  30/60/120 FPS et tests GPU tri-OS.

**R43.B2 livre l'édition AST + la prévisualisation mathématique, pas un
Combat Designer 8.3 certifié.**
