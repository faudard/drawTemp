# Sporebound Tactics — gameplay autonome 2.0 alpha

**Le développement actif quitte Godot.** Le moteur tactique, les données et notre
éditeur sont désormais dans `sporebound/`, en Python 3.10+ sans dépendance tierce.
L’interface Tk est volontairement utilitaire : la priorité est aux règles,
aux scénarios, à l’équilibrage et aux tests.

Les anciens scripts/scènes/assets Godot sont conservés comme sources de référence.
Ils ne sont ni chargés ni nécessaires au nouveau runtime. Cette version est une
base jouable substantielle, **pas encore une conversion intégrale** de l’ancien jeu.
Voir [la migration et ses limites](docs/GAMEPLAY.md#migration-de-godot).

## Démarrer

Depuis la racine du dépôt :

```sh
python -m sporebound editor
python -m sporebound player # client de jeu indépendant de l’éditeur
```

Tk/Tcl doit être disponible pour l’éditeur (`python -m tkinter` permet de vérifier).
Sous Linux, installer le paquet `python3-tk` si nécessaire. Le moteur, les tests,
le terminal et les simulations fonctionnent sans Tk ni écran.

```sh
python -m sporebound validate
python -m sporebound play --mission garden
python -m sporebound simulate --mission crown --seed 42 --save saves/battle.json
python -m sporebound replay --load saves/battle.json
python -m sporebound play --load saves/battle.json
python -m sporebound balance --mission garden --runs 20
python -m unittest discover -s tests_standalone -v
```

Installation facultative : `python -m pip install .`, puis `sporebound editor`.
Le paquet inclut les données JSON ; il fonctionne hors du dépôt. Aucun téléchargement
ni exécutable Godot n’est requis.

## Gameplay disponible

- Initiative CT, ordre stable, déplacement/action dans les deux ordres, attente et orientation.
- Dijkstra pondéré, obstacles, occupation, relief, saut, téléportation, dangers,
  poussée/traction, dégâts de chute, lignes de vue sans fuite entre deux murs.
- Attaques par famille d’arme, Brave/Faith, évasion directionnelle, résistances,
  supports et réactions : Counter, Opportunity, Blade Grasp, Auto-Potion, MP Switch.
- 21 compétences, zones d’effet avec tirs alliés, incantations, ciblage case/unité,
  paiement MP à résolution, interruptions, soin, résurrection et consommables.
- Poison, Regen, Haste, Slow, Protect, Shell, Silence, Sleep, Stop, Don't Move,
  Don't Act et Guard ; zones persistantes, portes, interrupteurs, coffres et triggers.
- Objectifs élimination, survie, extraction, contrôle de zone et récupération de
  couronne ; protection d’un personnage et défaite prioritaire.
- IA utilitaire déterministe, soins prioritaires à faibles PV, évaluation des dégâts
  alliés, placement, objectifs et prévisions utilisant les mêmes règles que le joueur.
- Campagne : XP, niveaux, maîtrise des classes, déblocages, boutique, équipement,
  récompenses uniques et missions suivantes.
- Sauvegardes JSON atomiques et replays vérifiés avec contenu embarqué, seed et journal
  des commandes. Les entrées illégales ne consomment ni action ni hasard.

Quatre scénarios de travail (`garden`, `escape`, `hold`, `crown`), quatre classes et
trois équipements sont fournis. Ils servent de terrain d’essai ; l’équilibrage
et les valeurs sont propres au prototype autonome.

## Studio de création (cartes et jeu complet)

Lancer `python -m sporebound editor`. Le studio comprend maintenant :

- **Carte et combat** : peinture de cases, positionnement, prévisions, playtest isolé.
- **Carte vierge** : assistant de nouvelle mission avec dimensions et acteurs de base.
- **Personnages et événements** : ajouter/supprimer personnages et monstres,
  objets interactifs, conditions et actions de triggers simples, sans écrire du JSON.
- **Mission** : titre, objectif, récompense, progression vers les missions suivantes
  et redimensionnement sûr de carte.
- **Jeu, campagnes et sauvegardes** : écran titre, configuration audio/langue/plein
  écran, plusieurs campagnes, partie nouvelle ou chargée, 1 à 9 slots et
  lancement de mission avec progression `Campaign`.

Les modifications de gameplay sont validées avant d'être inscrites dans
l'historique undo/redo. Le `*.game.json` de présentation reste indépendant du
fichier des missions ; les sauvegardes de campagne n'écrasent pas les replays.
**Playtest** ne modifie pas la progression, contrairement à **Jouer campagne**.
Pour les règles, équipements, vagues et acteurs complexes, l'onglet **Données JSON**
reste disponible. L'écran titre est à ce stade un **aperçu interactif Tk** et
non un frontend de jeu autonome finalisé.

Voir le [guide détaillé du Studio](docs/STUDIO.md) pour les actions disponibles,
les conventions de sauvegarde et les limites.

## Studio avancé et client joueur

Trois onglets d'authoring supplémentaires sont disponibles :

- **Graphe des missions** : afficher les nœuds, relier/délier deux missions,
  repérer les cycles et les missions inaccessibles depuis une campagne ;
  la navigation vers une mission actualise la carte tactique.
- **Bibliothèque d'acteurs** : définir des archétypes de personnages/monstres,
  capturer une unité existante, puis instancier le modèle sur plusieurs cartes.
  Les unités placées sont des copies de données et restent indépendantes.
- **Événements par blocs** : créer une condition et des actions ordonnées
  (message, danger, statut, apparition depuis un archétype, disparition).
  Le moteur valide toutes les références lors de l'application.

Une application joueur distincte est également disponible :

```sh
python -m sporebound player
python -m sporebound player --content chemin/jeu.json --project chemin/jeu.game.json
```

Le joueur choisit une campagne et un emplacement, lance les missions
débloquées et combat sur la grille Tk avec le moteur `Battle`.
Les victoires et défaites sont enregistrées dans le slot de campagne ;
une bataille interrompue n'est pas enregistrée comme terminée.
Par défaut, les profils sont écrits dans
`~/.sporebound/<nom-du-projet>_saves/`, et non dans le package installé.

Voir [le guide Studio et Player](docs/STUDIO.md). Les embranchements du graphe
sont pour l'instant les `next_missions` existants : après une victoire,
tous les successeurs déclarés sont débloqués. Les choix conditionnels,
dialogues/cinématiques et renderer/audio dédiés restent à développer.

## Campagne et équipement

```sh
python -m sporebound play --campaign --mission garden --save saves/current.json
python -m sporebound play --campaign --load saves/current.json
python -m sporebound roster
python -m sporebound roster --buy rhythm_boots --hero ziggy --equip rhythm_boots
python -m sporebound roster --hero ziggy --job spore_maestro
python -m sporebound roster --hero ziggy --unequip accessory
```

Les achats nécessitent de l’or ; les classes avancées demandent Brave niveau 2.
`campaign --mission garden` permet aussi une simulation automatique avec progression.
Par défaut, la campagne est dans `saves/campaign.json` ; `--campaign-file` la remplace.
Les récompenses ne sont accordées qu’une fois par mission, même après rechargement.

## Siège et logistique multi-fronts

```sh
python -m examples.siege_fronts
python -m unittest discover -s tests_standalone -p test_logistics.py -v
```

Cet exemple relie les remparts, la herse, la cour, le ravitaillement
et le trône : les actions tactiques influencent les autres secteurs.
Les réserves sont finies ; les déplacements d'escouades entre fronts
consomment des tours stratégiques. Les sauvegardes multi-fronts v3
rejouent exactement les transferts, arrivées et pertes.

## Centre de commandement multi-fronts

```sh
python -m examples.siege_command                # vue d'ensemble du siège
python -m examples.siege_command --gui          # fenêtre de commandement Tk
python -m examples.siege_command --interactive  # ordres et timeline en terminal
python -m examples.siege_command --demo         # embuscade + secours
python -m examples.siege_command --rescue-demo  # vrai combat : victoire + replay
python -m examples.siege_command --choices-demo # évacuation + poursuite + replay
python -m examples.siege_strategy_demo         # négociation, cour partielle, trône
python -m examples.siege_routes_demo          # 3 chemins jouables / replay
python -m examples.siege_command --gui --paths
python -m unittest discover -s tests_standalone -p test_siege_routes.py -v
python -m examples.siege_command --gui --campaign
python -m unittest discover -s tests_standalone -p test_siege_campaign.py -v
python -m unittest discover -s tests_standalone -p test_command_center.py -v
python -m unittest discover -s tests_standalone -p test_convoy_rescue.py -v
```

Le tableau Tk et le terminal présentent tous les fronts, convois et ETA.
Routes dangereuses, escorte limitée et provisions sont facultatives.
Le sauvetage d'un convoi peut désormais devenir une **vraie mission tactique** :
protéger un chariot, négocier, évacuer les survivants, récupérer un butin
partiel, poursuivre les pillards ou abandonner le convoi.
La campagne multi-fronts optionnelle verrouille aussi le trône jusqu'aux
victoires requises ou aux négociations et conquêtes partielles autorisées.
Le mode `--paths` ajoute trois routes (porte, souterrains, assaut direct),
des trêves conditionnelles et une mission de reconquête d'un secteur perdu.
Les opérations et les batailles sont vérifiées par replay v5.

## Documentation

- [Contrats du moteur et règles détaillées](docs/GAMEPLAY.md)
- [Architecture autonome](ARCHITECTURE.md)
- [Règles modulaires, personnages et monstres](docs/MODULAR_ENGINE.md)
- [Exemple de siège multi-fronts avec logistique, reserves et transferts](examples/siege_fronts.py)
- [Chronologie stratégique, fronts et replays](docs/MULTI_FRONT.md)
- [Studio de création de cartes, campagnes et écrans de jeu](docs/STUDIO.md)
- [Roadmap gameplay et éditeur](ROADMAP.md)
- Historique Godot : [README](docs/legacy/GODOT_README.md),
  [architecture](docs/legacy/GODOT_ARCHITECTURE.md), documents `FFT_*` à la racine.

La CI vérifie Python 3.10/3.12/3.14 sur Windows/Linux/macOS, les règles, les replays
et l’installation. Un job Linux teste l’interface Tk réelle sous Xvfb.
