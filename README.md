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

## Utiliser notre éditeur

1. Choisir une mission ; peindre murs, relief, boue, dangers, couvert ou objectifs.
2. Choisir le pinceau `unit` et une unité pour déplacer son point de départ.
3. Dans **Données JSON**, modifier stats, compétences, IA via loadouts, objectifs,
   objets, triggers, classes et équipement ; **Valider et appliquer**.
4. **Playtest**, choisir une commande puis une case et **Exécuter**. Le panneau donne
   PV/MP/CT, disponibilité des actions et prévisions. **Fin** valide l’orientation.
5. **IA : 1 tour** délègue une activation ; le journal explique le déroulement.
6. **Éditer** revient au document intact. Annuler/rétablir, duplication de mission,
   ouverture/enregistrement et reprise de combat sont disponibles.

Le playtest n’écrit aucune progression de campagne. Les éditeurs spécialisés
(formulaires de compétences/classes et graphes de triggers) restent à construire ;
le JSON validé permet déjà de tout configurer sans modifier le code du moteur.

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

## Documentation

- [Contrats du moteur et règles détaillées](docs/GAMEPLAY.md)
- [Architecture autonome](ARCHITECTURE.md)
- [Roadmap gameplay et éditeur](ROADMAP.md)
- Historique Godot : [README](docs/legacy/GODOT_README.md),
  [architecture](docs/legacy/GODOT_ARCHITECTURE.md), documents `FFT_*` à la racine.

La CI vérifie Python 3.10/3.12/3.14 sur Windows/Linux/macOS, les règles, les replays
et l’installation. Un job Linux teste l’interface Tk réelle sous Xvfb.
