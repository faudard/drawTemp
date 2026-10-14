# Visual Battle Lab 3.8.3 — graphiques, CT et replay ciblé

## Ce qui est livré

Un onglet **Visual Battle Lab** est accessible depuis **Espace projet**,
**Battle Lab** et **Balance Matrix**. Il affiche sans nouvelle simulation :

- la répartition *victoire / défaite / nul / limite*, avec éventuel témoin ;
- les durées de **chaque seed en ticks CT** et en commandes IA, sans les
  présenter comme des minutes de jeu humain ;
- les dégâts, soins reçus, décisions, réactions ou **survie par classe**
  (sélecteur de métrique) ;
- les seeds à inspecter, triées par signaux reproductibles (non-résolution,
  stagnation possible, renversement d'issue, défaite, hausse des commandes) ;
- les deltas appariés **seed à seed**, uniquement pour la *même mission* ;
- une chronologie CT détaillée obtenue à la demande à partir du
  `trace_seed()` existant (3.8.1) ; marqueurs dégâts, soins et constats
  explicites, navigation vers le replay complet pas à pas.

Les graphiques proviennent uniquement des rapports `battle_lab` 3.8,
`balance_matrix` 3.8.2 et `battle_diagnostics` 3.8.1. Aucun nouveau
calcul de décision IA, objectif, dégâts, équilibrage ou interprétation
temporelle humaine n'est introduit.

## Depuis Battle Lab

1. Choisir mission, seeds et plafond, puis **Simuler**.
2. Sélectionner une seed (facultatif), cliquer **Visualiser résultats**.
3. Inspecter les graphiques et les seeds signalées. Cliquer une barre/point
   du graphe des durées ou une ligne du tableau pour cibler une seed.
4. Cliquer **Tracer seed sélectionnée** : le worker relance cette seed
   avec **le snapshot de contenu et les règles exacts de la simulation**.
5. Il compare le digest final, le nombre de commandes et l'issue au rapport
   d'origine ; en cas de divergence, il *refuse* le replay.
6. Utiliser le diagramme CT ou **Replay détaillé** pour ouvrir le lecteur
   de commandes de 3.8.1, avec états PV, objets, positions et anomalies.

Si le budget initial dépasse **5 000 commandes**, les graphiques agrégés
restent disponibles mais la trace détaillée est explicitement bloquée
(jusqu'à extension contrôlée de 3.8.1).

## Depuis Balance Matrix

1. Lancer les scénarios appariés habituels.
2. Sélectionner une ligne et cliquer **Visualiser scénario**.
3. Le Visual Lab présente la ligne sélectionnée et **son seul témoin de
   mission**, jamais un autre scénario ou une autre mission.
4. Les commandes/CT et les taux peuvent être comparés descriptivement.
   Pour le replay d'une variante, la copie du `Content` est reconstruite
   à partir de sa spécification et du snapshot original ; sa signature
   est vérifiée avant de lancer `trace_seed()`.

Le graphe affiche des **mesures**, pas la preuve que telle variation
de stats est causalement responsable d'une victoire. Les seuils de
régression CI restent définis et appliqués par `compare_reports()` /
`compare_matrices()`, non par l'interface graphique.

## Fichiers JSON hors session

**Charger rapport JSON** accepte soit un `battle_lab` v1, soit une
`balance_matrix` v1 exportée. Pour cette dernière, un sélecteur permet de
basculer entre les différents scénarios. Un rapport JSON importé
n'inclut pas, à lui seul, le snapshot complet exécutable de la mission
et des règles : **les graphiques restent accessibles, mais la
re-simulation est désactivée**, afin de ne pas produire un replay
différent sous une identité trompeuse.

## Scalabilité

Le modèle de visualisation est headless (`sporebound/battle_visual.py`)
et ne modifie jamais les sources. Pour une trace de plusieurs milliers de
commandes, la vue CT n'affiche qu'un échantillon borné à **240 points**,
en conservant strictement la première et la dernière commande et les
indices réels des étapes. Le replay 3.8.1 conserve, lui, **toutes** les
commandes : une sous-échantillonnage d'affichage ne supprime jamais une
décision du fichier source.

## Validation

```sh
python -m unittest tests_standalone.test_battle_visual_383 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
  tests_standalone.test_battle_visual_383_gui -v
```

- Rapports inchangés avant/après visualisation et répétabilité des modèles.
- Deltas CT et commandes exacts sur chaque paire de seeds.
- Rejet de toute comparaison de missions/seeds incompatibles.
- Variantes et témoins montrés dans leur mission effective.
- Traces issues du moteur canonique et validées par `Battle.replay`.
- Navigation GUI vérifiée du Battle Lab vers le Visual Lab puis replay.
- Gates historiques 3.8 et 3.8.2 non assouplis.
