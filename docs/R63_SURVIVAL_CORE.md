# R63 — Survival & Crafting: premier incrément headless

Statut : **implémentation R63.A et fondation d'authoring R63.B en PR**, pas une certification R63 complète.

## Positionnement

- Extension opt-in `org.drawtemp.survival` dans `GameProject.extensions`; enveloppe `schema_version: 1`, `references: []`.
- `GameSession` détient le runtime de survie et son journal. L'inventaire et les transferts d'objets utilisent exclusivement `Campaign.progress.inventory`.
- Inactif si l'extension est absente ; les sauvegardes historiques ne gagnent **aucune clé** `survival`.
- Un tick entier est avancé lors des commandes de mouvement routé R25/R32 (mise en scène préalable, puis commit avec les autres sous-systèmes). La commande explicite `survival_advance(ticks)` sert aux bonds déterministes hors mouvement.
- Aucune modification du combat CT, de la vitesse de simulation globale, du RNG ou du système de carte.

## Données et règles

Schéma strict : `version, needs, items, tools, nodes, recipes, shelters, foods`.

- **Besoins** : énergie, faim/satiété et chaleur de 0 à 100 ; drains entiers bornés.
- **Nœuds** : scène, stock fini, rendement, coût énergétique, froid, usure d'un outil optionnel. Pas de respawn implicite.
- **Recettes** : coût énergétique et intrants/extrants strictement positifs ; cycles de transmutation interdits (DAG) ; deux recettes fournies dans le fixture VS-63.
- **Refuges** : consomment un combustible/objet du Campaign, restituent de l'énergie et de la chaleur.
- **Nourriture** : consommation d'un article de Campaign pour reconstituer la satiété.
- **Commandes** : `survival_gather`, `survival_craft`, `survival_rest`, `survival_eat` exigent un identifiant de transaction idempotent ; rejet si insuffisance de matériaux, inventaire plein, mauvais lieu, épuisement d'outil ou de besoin.
- **Persistance** : `GameSession.recording()` encode les seuls besoins, stocks, outils et journal ; `restore()` reconstruit les états internes par replay avant d'accepter le checkpoint. L'inventaire reste vérifié dans le checkpoint de campagne, pas dupliqué dans un deuxième stockage.

## Studio (base R63.B)

`drawtemp.studio.survival_authoring.preview_survival_design()` propose la modification du **projet canonique** sans mutation silencieuse. `apply_survival_design()` passe par le plan `AuthoringSession`, avec Undo/Redo et détection de révision périmée. L'éditeur **Qt graphique**, ses inspections de carte et son HUD restent à implémenter.

## Vérification

```shell
python -m unittest tests_standalone.test_r63_survival -v
```

Le test `test_vertical_slice_two_recipes_environment_and_recovery` traverse collecte de bois/pierre/baies, fabrication d'un camp et d'une ration, consommation, refuge, vérification du risque de froid, restauration du journal et impossibilité de dupliquer une transaction.

## R63.B — Studio Qt + Player (branche de développement)

Fonctionnalités ajoutées :

- **Survival Designer Qt** via *Studio → Outils → Survival Designer R63* (également depuis la palette de commandes).
  Les 6 onglets déclaratifs éditent objets, outils, nœuds de récolte, recettes, refuges et aliments.
- **Besoins** : 6 champs bornés, énergie/satiété/température initiales et drains par tick, avec prévision déterministe à 8 ticks.
- **Placement sur grille** : les gisements et refuges acceptent un `pos: [x, y]` **optionnel**.
  Clic sur une case libre après sélection de la catégorie et de la ligne ; validation des bornes de la scène
  et des cases bloquées. Les anciennes définitions sans `pos` restent compatibles. L'éditeur
  graphique affiche des cartes jusqu'à 64 × 64 cellules ; les dimensions plus grandes restent
  valides dans le schéma, mais le placement par clic demande un autre outil.
- **Portée des interactions** : lorsqu'une position est déclarée, l'acteur doit être au
  plus à 1 case de Manhattan de la ressource / du refuge. Les actions hors portée sont
  refusées avant mutation ; le Player désactive leur bouton.
- **Brouillon non destructif** : Undo/Redo interne, validation à chaque modification,
  prévisualisation sans mutation et commit **unique** via `AuthoringSession`.
  Les IDs, cartes, quantités et graphes de recettes sont contrôlés avant enregistrement.
- **Player Qt Quick** : HUD énergie / satiété / chaleur, risque de froid,
  ressources locales et stock restant, recettes, abris, nourriture, action Attendre.
  Boutons clavier / lecteurs d'écran (étiquettes et noms accessibles pour les jauges).
  Les commandes passent par `PlayerController`, `Simulation` et `GameSession`.
  Aucun journal de transactions n'est transmis au moteur QML.
- **Compatibilité** : sans extension de survie, le HUD n'est pas visible et
  la sauvegarde historique n'obtient pas de champ `survival`.

### Démonstration sans JSON

1. Ouvrir un projet comportant une scène d'exploration ; menu **Outils → Survival Designer R63**.
2. Le document de départ est un *brouillon* contenant 2 recettes, 3 gisements dont un froid,
   1 refuge et 1 ration, sans exiger un outil initial pour récolter le bois.
3. Choisir **Ressources et dangers**, sélectionner la forêt, cliquer sur une case libre de sa scène.
   Placer également le refuge ; **Prévisualiser** pour examiner les besoins / les dangers.
4. **Appliquer au projet** : une transaction dans l'historique Studio.
   Lancer le Player dans la scène de départ, se déplacer près du bois / de la pierre,
   collecter, fabriquer le camp et la ration, se reposer, manger et sauvegarder.
5. Recharger la partie : les besoins, stocks, outils et reçus sont reconstruits sans
   générer de nouveau gain de matériaux.

### Tests ajoutés

```sh
python -m unittest tests_standalone.test_r63_survival tests_standalone.test_r63_player -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r63_survival_gui -v
```

La CI R63 lance les tests headless sous Python 3.10 / 3.12 et les tests Qt
sous 3.12, ainsi qu'un smoke QML. Ces tests ne constituent **pas** à eux seuls
une certification GPU ou une preuve d'accessibilité assistive sur machine réelle.

## Gates à poursuivre

1. **R63.A :** compléter la preuve de cohérence avec d'autres opérations de Campaign (R45/R55), les restaurations hostiles et les limites de journal.
2. **R63.B :** implémentation UI et tests ajoutés. Reste à qualifier le parcours
   Studio→Player sous Qt réel, les lecteurs d'écran et les cartes volumineuses ;
   CI en attente de jobs exécutés et réussis.
3. **R63.C :** jouer et sauvegarder la VS-63 en Player Qt, tester des boucles d'échec/récupération et la balance multi-seeds.

Le gate complet n'est pas revendiqué tant que l'E2E Qt et les dépendances R61/R62 ne sont pas certifiés.
