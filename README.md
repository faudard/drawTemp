# Sporebound Tactics — gameplay autonome 2.0 alpha

**Le runtime actif est désormais 100 % Python 3.10+**, sans dépendance tierce pour
le moteur tactique. L'éditeur et le client joueur sont dans `sporebound/` et
utilisent Tk. La priorité reste aux règles, scénarios, tests et outils d'authoring.

Les sources, scènes, plug-ins, ressources et anciens tests Godot ont été supprimés
de la branche active. Leur historique reste consultable via Git, mais ils ne sont
plus exécutés ni maintenus. Les illustrations PNG/JPG et les kits réutilisables
sont conservés dans [`assets/`](assets/README.md) ; leur utilisation par un futur
renderer est un chantier distinct. La conversion des anciennes cartes et sauvegardes
n'est pas garantie. Voir [les limites de la migration](docs/GAMEPLAY.md#migration-de-godot).

## Player & Presentation 2.6

Le client `python -m sporebound player` utilise désormais `GameSession` et les
checkpoints `SessionStore` (sauvegarde/reprise des combats, scènes et fronts).
Une interface Tk 2D/2.5D apporte grille, caméra, preview du moteur,
déploiement, portraits optionnels, chronologie des fronts et commandes de siège.
Les données du gameplay restent headless. Les anciens slots `PlayerSession`
restent séparés et inchangés.

Les assets et sons sont entièrement facultatifs. Pour WAV/OGG :
`python -m pip install pygame-ce`. Voir [Player 2.6](docs/PLAYER_2_6.md).

## Session unifiée 2.4.1 (API headless)

La façade `sporebound.game_session.GameSession` orchestre campagne, narration,
combat standard et combats multi-fronts sans modifier les contrats existants :

```python
from sporebound.game_session import GameSession
session = GameSession.new(content, project, "main", seed=42)
session.start_mission("garden")
session.execute({"kind": "end", "facing": [0, 1]})
session.save("saves/session.json")
session = GameSession.load("saves/session.json", content, project)
```

Les checkpoints de session sont distincts des anciens slots `PlayerSession`.
Le nouveau client `sporebound player` utilise cette façade, tandis que l'ancien `player_shell` et ses slots sont conservés pour compatibilité.
Voir [contrats et exemples](docs/UNIFIED_SESSION.md).

## Persistence 2.0 — reprise et sauvegardes de secours

`sporebound.persistence.SessionStore` propose des checkpoints versionnés avec
une copie de secours vérifiée. Les sessions v1 sont migrées explicitement à la
prochaine écriture ; les anciens slots ne sont jamais remplacés automatiquement.

```python
from sporebound.persistence import SessionStore, AutosaveSession
store = SessionStore("saves/game.session.json")
store.save(session)
resumed = store.load_with_status(content, project)
print(resumed.source)   # primary ou backup
autosave = AutosaveSession(resumed.session, store)
```

Voir [le guide Persistence 2.0](docs/PERSISTENCE_2.md). L'autosave reste
**opt-in** et n'est pas encore connecté à l'interface joueur Tk.

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

- **Espace projet (2.5.5)** : inventaire central des campagnes, missions,
  dialogues, personnages, classes, compétences et assets ; navigation vers les
  panneaux existants, création de missions et campagnes, duplication contrôlée,
  vérification du registre d'assets.


- **Carte et combat** : peinture de cases, positionnement, prévisions, playtest isolé.
- **Map Editor 3.0 (2.5.1, fondation)** : sélection multiple, copie/collage
  validé des cases et objectifs, aperçu de collage, couches visibles,
  repositionnement d'unités/objets et édition des zones de déploiement.
  Voir [le guide de l'éditeur de cartes](docs/MAP_EDITOR_3.md).
- **Map Editor 3.0 — outils avancés** : rotation/symétrie, modèles de
  terrain portables, déplacement groupé validé, zoom et mini-carte cliquable.
  Voir [les outils avancés](docs/MAP_EDITOR_3_ADVANCED.md).
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
reste disponible. L'écran titre du Studio reste un aperçu de création ; la commande
`sporebound player` lance désormais le client autonome 2.6.

Voir aussi le [guide Project Workspace](docs/WORKSPACE.md).\nLe gate Studio 3.0 reste partiel : l'édition complète des ressources sans JSON\nest prévue dans les PR 2.5.1 à 2.5.4.\n\nVoir le [guide détaillé du Studio](docs/STUDIO.md) pour les actions disponibles,
les conventions de sauvegarde et les limites.

## Studio avancé et client joueur

Trois onglets d'authoring supplémentaires sont disponibles :

- **Graphe des missions** : afficher les nœuds, relier/délier deux missions,
  repérer les cycles et les missions inaccessibles depuis une campagne ;
  la navigation vers une mission actualise la carte tactique.
- **Synergy & Unlock Studio 2.5.3.2** : éditeur visuel des duos/trios,
  secrets, conditions ET/OU, compteurs et séquences de combat, avec
  simulateur sans effet de bord. Guide :
  [Synergies et déverrouillage](docs/SYNERGY_UNLOCK_STUDIO.md).
- **Class Progression & AI Studio 2.5.3.3** : deux graphes cliquables
  des classes et talents, création de spécialisations et édition des
  patrouilles sur la carte ; [guide dédié](docs/CLASS_AI_STUDIO.md).
- **Character & Rules Studio 2.5.3** : éditeur guidé des héros et monstres,
  archétypes, compétences multi-effets, classes et équipements ;
  validation transactionnelle et Undo/Redo. Voir
  [la documentation](docs/CHARACTER_RULES_STUDIO.md).
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
le client 2.6 ajoute dialogues, renderer Tk et audio optionnel ; les cinématiques
complexes et les assets animés avancés restent à développer.

## Arbre narratif — scènes réutilisables

Le studio contient aussi un onglet **Arbre narratif** où chaque embranchement
est déplié en occurrences. Si deux choix aboutissent à la même scène, elle
apparaît deux fois dans l'arbre, mais sa définition reste unique.

- Choix de la racine par campagne, victoire de mission ou scène.
- Cliquer un nœud ou une flèche pour inspecter les conditions, conséquences
  et scènes de destination.
- Créer et relier une nouvelle scène en une seule modification validée,
  raccorder plusieurs branches à une scène existante ou délier un choix.
- Replier individuellement un chemin, zoomer et accéder directement aux
  formulaires « Scénario & dialogues ».
- Protection contre les cycles et limitation du nombre d'occurrences
  affichées, sans aucune perte de données.

L'exemple `core.game.json` illustre des branches qui se rejoignent.
Voir [les instructions de l'arbre narratif](docs/STUDIO.md#arbre-narratif--scènes-partagées-dans-plusieurs-embranchements).

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

## Graphe d'événements tactiques — 2.5.2

Le Studio propose le **Graphe des événements** : conditions de mission,
actions ordonnées, apparition d'acteurs, vagues de renforts, réorganisation
de priorités et édition depuis les nœuds. Les actions utilisent les règles
existantes du moteur, avec validation et Undo/Redo.

Voir [le guide du graphe des événements](docs/TACTICAL_EVENT_GRAPH.md).

## Conditions narratives visuelles — 2.5.2

L’onglet **Conditions & variables** permet de composer les règles
**ET / OU / NON**, les comparaisons de flags, l’or et les missions
terminées, puis de prévisualiser la visibilité des choix sans modifier
une sauvegarde. L’arbre narratif propose désormais un accès direct
aux conditions de chaque branche.

Voir [le guide des conditions narratives](docs/NARRATIVE_CONDITIONS_3.md).

## Documentation

- [Contrats du moteur et règles détaillées](docs/GAMEPLAY.md)
- [Architecture autonome](ARCHITECTURE.md)
- [Règles modulaires, personnages et monstres](docs/MODULAR_ENGINE.md)
- [Exemple de siège multi-fronts avec logistique, reserves et transferts](examples/siege_fronts.py)
- [Chronologie stratégique, fronts et replays](docs/MULTI_FRONT.md)
- [Studio de création de cartes, campagnes et écrans de jeu](docs/STUDIO.md)
- [Roadmap gameplay et éditeur](ROADMAP.md)
- [Bibliothèque graphique réutilisable](assets/README.md) — images et catalogue JSON
- [Asset Pipeline 2.4.3](docs/ASSET_PIPELINE.md) — registre portable, animations,
  références typées et validation avec `validate --project chemin/game.json`.
- [Reliability 2.4.4](docs/RELIABILITY.md) — campagnes complètes déterministes,
  sauvegarde/reprise, tests d'interruption disque et rapports CI.
- Ancien projet Godot : consulter l'historique Git antérieur au nettoyage ;
  les fichiers de l'ancien moteur ne sont plus présents dans cette branche.

La CI vérifie Python 3.10/3.12/3.14 sur Windows/Linux/macOS, les règles, les replays
et l’installation. Un job Linux teste l’interface Tk réelle sous Xvfb.

### 2.8 — Castle Vertical Slice

Parcours château jouable : préparation, classes et équipement, choix du bélier / remparts / souterrains / négociation / assaut direct, fronts simultanés, salle du trône à phases, trois fins et reprise vérifiée.

```bash
python -m examples.castle_vertical_slice --save saves/castle-2.8.json
python -m examples.castle_vertical_slice --load saves/castle-2.8.json
```

Voir [le guide 2.8](docs/VERTICAL_SLICE_2_8.md). Le parcours 2.8 est pour l'instant jouable au terminal ; l'intégration graphique Player / Studio reste à réaliser.
