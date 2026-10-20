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

## Gates à poursuivre

1. **R63.A :** compléter la preuve de cohérence avec d'autres opérations de Campaign (R45/R55), les restaurations hostiles et les limites de journal.
2. **R63.B :** Survival Designer Qt, placement de dangers et d'objets dans les cartes, HUD accessible et parcours Studio→Player réel.
3. **R63.C :** jouer et sauvegarder la VS-63 en Player Qt, tester des boucles d'échec/récupération et la balance multi-seeds.

Le gate complet n'est pas revendiqué tant que l'E2E Qt et les dépendances R61/R62 ne sont pas certifiés.
