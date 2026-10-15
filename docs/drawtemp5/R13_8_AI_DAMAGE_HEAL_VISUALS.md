# DrawTemp 5.0 — R13.8 Visual Battle Lab : décisions IA, dégâts & soins

Cette tranche prolonge les **graphiques comparatifs A/B** déjà intégrés
à `master` via #243. Elle n'ajoute **aucune autre IA** et n'infère **aucune**
décision non observée.

## Utilisation

```bash
python -m drawtemp.studio.r13_workbench --content sporebound/content/jeanne.json
```

1. Choisir une mission dans le Studio R13 et cliquer **Simuler + vérifier les replays**.
2. Ouvrir **Décisions IA · dégâts / soins**.
3. Le premier graphique présente les **commandes réellement exécutées**,
   groupées par action (déplacer, attaquer, finir le tour, etc.) et par équipe ;
   sélectionner **Joueurs**, **Ennemis** ou **Toutes** pour filtrer.
4. Le second graphique affiche, commande après commande, les cumuls
   **dégâts reçus** et **PV restaurés** d'après les événements
   `damage`/`heal` du moteur. Filtrer par équipe ou par unité :
   une invocation/renfort est disponible si le replay la contient.
5. Survoler la courbe pour voir la commande et les cumuls exacts.
   Cliquer dans la courbe pour sélectionner la **commande correspondante**
   dans la timeline du Battle Lab et revoir les positions du vrai replay.
6. Les signaux heuristiques IA (`move_without_displacement`, `backtrack`,
   `repeat_idle`, etc.) utilisent les diagnostics existants. Les consulter
   comme des **indices à investiguer**, pas comme une preuve que la décision
   était incorrecte. Les entrées de preuve disponibles sont cliquables.

## Architecture et fidélité

- Modèle sans Qt : `drawtemp/sdk/r13_ai_combat_visuals.py` expose
  `build_combat_visuals(trace)`. L'entrée est un
  `sporebound.battle_diagnostics.trace_seed()` marqué
  `replay_verified=True`, limité à **5000 commandes**.
- `sporebound.encounter_balance6.ai_decision_analytics` est réutilisé
  pour les compteurs et signaux IA. L'adaptateur refuse des compteurs
  d'actions divergents ; il ne recalcule pas un autre classement IA.
- Les dégâts et soins affichés sont les **quantités effectivement émises**
  (soins nets, dégâts après résolution), attribuées à la **cible** et
  à son équipe : ils ne représentent ni une estimation DPS, ni
  nécessairement les dégâts infligés par l'acteur actif.
- Les valeurs sont **cumulatives par commande**, et non par seconde.
  Le `tick` CT reste dans les données pour vérification ; la timeline
  est synchronisée avec les indices de commandes réels.
- La simulation multi-seeds continue d'afficher les indicateurs A/B
  agrégés. La vue IA/PV montre **une seule seed tracée et vérifiée**
  (première seed de la simulation), et indique explicitement son numéro.
  Aucune moyenne de trajectoire ni événement fictif n'est créé.
- Le SDK refuse les replays non vérifiés, index de commande incohérent,
  montants négatifs/non entiers et cibles introuvables.
- Les unités mortes ne sont pas réaffichées artificiellement :
  l'affichage des positions dans la timeline utilise les unités vivantes
  réellement observées dans chaque frame.

## Tests & CI

```bash
python -m unittest tests_standalone.test_drawtemp5_r13_ai_combat_visuals -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp5_r13_ai_combat_qt -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp5_r13_qt -v
```

Les tests headless vérifient la parité avec un **véritable replay canonique**,
le JSON, les équipes, la conservation des données et les rejets de données
incohérentes. Les tests Qt offscreen vérifient le rendu, les filtres et
la navigation. La CI cible Windows, Linux et macOS pour le SDK, ainsi
que Linux/Qt 6 pour le rendu hors écran.

## Encore ouvert

Le rendu isométrique définitif, les cartes de chaleur multiétages, les
courbes d'évolution par seed A/B (nécessitant **deux traces complètes**),
les réponses de l'IA face aux scénarios contrefactuels, les budgets de
performance graphique et la validation visuelle humaine restent hors de
cette tranche. Les tests automatisés ne certifient pas l'ergonomie finale.
