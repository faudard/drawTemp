# 3.7.20C1 — Navigation tactique entre étages (première tranche jouable)

## Objet

La PR empilée sur 3.7.20B livre des **unités tactiques présentes à des
niveaux différents**, des **escaliers bidirectionnels à coût explicite**,
la navigation contrôlée entre ces niveaux, et une première action de
combat adjacente à l'intérieur d'un même étage.

Elle ne ferme PAS le jalon complet 3.7.20C : les arcs de tir entre niveaux,
les attaques de zone verticales, les chutes, les réactions pendant la montée,
le pathfinding stratégique interétages pour toutes les IA et les grosses
unités attendent des règles explicites. Pas de physique 3D implicite.

## Parcours sans édition JSON

1. Dans le Map Editor, poser **Maison** (ou Tour/Ruines), puis ouvrir
   **Intérieurs** et créer le plateau N1 avec l'outil 3.7.20B.
2. Sélectionner une case praticable appartenant à la fois à N0 et à N1,
   et cliquer **Escalier N-1 ↔ N**. Le couple est directionnellement
   réversible ; aucune montée automatique n'existe sans cette liaison.
3. Sélectionner une unité et une case du plateau N1, puis
   **Placer unité à N**. Le moteur interdit une superposition d'unités
   sur le même niveau, mais autorise N0 et N1 aux mêmes XY.
4. Lancer le playtest/Player, sélectionner la commande **level_move**,
   choisir **Étage cible**, cliquer une destination sur la grille du
   niveau et exécuter. Le déplacement utilise le CT/Move standard et
   dépense une seule action de déplacement.
5. Pour vérifier l'attaque, placer un ennemi adjacent sur N1,
   monter sur N1 et utiliser **attack**. Depuis N0, cet ennemi n'est
   ni occupateur de terrain, ni cible valide.
6. Enregistrer le combat, rouvrir et rejouer les commandes : la séquence
   `level_move` conserve les niveaux et le digest déterministe.

Scène de test reproductible avec les API du Studio :
```sh
python -m examples.layered_house_3720c --output /tmp/layered_house.json
python -m sporebound editor --content /tmp/layered_house.json
```

## Contrat de données strictement facultatif (Content v1)

Dans une mission possédant des `interior_floors` (cf. 3.7.20B) :

```json
"unit_levels": {"ennemi_1": 1},
"level_links": [
  {"id": "stair_1", "from": [0, 4, 5], "to": [1, 4, 5], "cost": 1}
]
```

Les niveaux ne changent pas la structure `Unit.pos=(x,y)`, ni `Tile`.
Le champ `unit_levels` ne stocke que les unités initialement au-dessus
du sol ; le niveau zéro reste implicite. Les positions de combat courantes
restent dans `Battle.unit_levels`, et entrent dans le checkpoint/replay
uniquement pour les missions multi-niveaux.

Les liaisons exigent des cases praticables sur chaque plan, deux étages
adjacents et au maximum une case d'écart XY. Aucune liaison dupliquée ni
indice de niveau orphelin n'est accepté. Le solveur de navigation
`(level,x,y)` interdit les unités bloquantes **sur le même étage** ;
les liens ne créent pas de passage secret dans une cloison.

Le renderer du Player est partagé avec le Studio et affiche les sprites
surélevés à la hauteur du plateau actif, avec sélection par hit-test
dans l'étage choisi.

## Conservation du gameplay historique

- Les anciennes cartes sans `unit_levels` ni `level_links` conservent
  les mêmes champs sérialisés, la commande `move` et les mêmes digests.
- La commande `level_move` est exposée *uniquement* si la mission a des
  connexions. Elle n'est pas ajoutée au registre `default_commands`,
  afin de ne pas modifier le manifeste des règles des replays historiques.
- `Battle.execute` reste la frontière atomique ; une destination
  interdite restaure l'état complet et n'ajoute aucune commande.
- Les ennemis du dessus ne bloquent pas une case au sol ; la collecte
  d'une relique et les zones de danger du sol ne s'appliquent pas à N1.
- Les attaques du dessus sont actuellement limitées aux **attaques
  de base sur une cible adjacente du même niveau**. Pas de ciblage à
  travers les plafonds. Les skills, objets, sièges et réactions de
  traversée interétages exigent la phase suivante.
- `level_move` ne remplace pas les déplacements normaux N0→N0,
  qui conservent les interactions, dangers et réactions existants.

## Gate de livraison

- [ ] Tests headless :
  `python -m unittest tests_standalone.test_tactical_levels_3720c -v`
- [ ] Tk/Xvfb :
  `SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest
   tests_standalone.test_tactical_levels_3720c_gui -v`
- [ ] Installation hors dépôt et génération de la maison de référence
- [ ] Compatibilité ancien contenu, Digests/replay et rollback documentée
- [ ] Visuels 24/54/96 avec personnages à même XY sur étages distincts
- [ ] Intégration de PR #93 puis #95 dans `master` suivie de rebase
- [ ] Cross-PR #88 : déplacement/rotation de structures et
  recalcul contrôlé des escaliers/plateaux sans données orphelines
- [ ] Profiling éditeur/Player grande carte et revue Linux/Windows/macOS

Les tests sont versionnés dans cette PR, mais l'environnement de travail
ne permet pas de les exécuter localement : aucun statut de réussite n'est
affirmé avant retour effectif de la CI.
