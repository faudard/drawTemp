# R25.C — Free movement headless / fixed tick replay

**Statut :** tranche R25.C proposée, empilée sur [R25.B #314](https://github.com/faudard/drawTemp/pull/314), elle-même dépendante de [R25.A #298](https://github.com/faudard/drawTemp/pull/298). Pas de certification Qt/GPU.

## Architecture

La simulation libre réutilise **uniquement** les cartes `GameProject.exploration`, les routes `scene_routes`, le `Campaign.story_flags` et le `GameSession` existants. Aucun monde parallèle, aucune deuxième gestion d'objets ou de progression n'est ajouté.

- `sporebound.fixed_realtime.FreeMovement` : collision headless déterministe sur les obstacles de l'Exploration historique. Chaque case = **256 sous-unités entières** ; vitesse axiale = 32/tick, diagonale = 23/tick, bloquage ou glissement le long des murs, prévention des diagonales à travers un angle bloqué. Physique point/centre uniquement ; hitbox et obstacles dynamiques sont **hors périmètre**.
- `GameSession.route_realtime_step(dx,dy)` : un tick logique fixe (60 Hz), avec une commande `{"kind":"move","dx":-1..1,"dy":-1..1}` pour le héros. Rien n'est fondé sur la fréquence de rendu, le temps système, ni des nombres flottants.
- `FixedTickJournal` (R25.A) est raccordé au segment courant d'exploration. La séquence, les snapshots et leur SHA-256 permettent de **rejouer** les mouvements d'une session neuve sur exactement la même définition de carte.
- `GameSession.route_realtime_state()` expose `{scene, position:[x,y], cell:[cx,cy], tick}` pour de futurs viewports Qt. Les positions sont copiées, sans autorisation de modifier l'état du Core depuis l'interface.
- `route_move()`, ancien mouvement cardinal, reste disponible **avant** la première simulation subcellulaire. Mélanger les deux commandes après démarrage des ticks est explicitement rejeté.
- Le changement de scène R25.B conserve la progression et les flags : l'état subcellulaire local est ensuite réinitialisé sur le nouveau spawn ou sur l'arène CT. Le combat passe toujours par le moteur Battle/CT authentique.

## Replay / persistance

Dans les projets avec `scene_routes` activé, la sauvegarde `GameSession.recording()` peut embarquer `scene_realtime: {version, scene, origin, position, journal}` **uniquement après le premier tick**. Ce document optionnel complète le checkpoint **canonique**, plutôt que créer un fichier de partie à part.

Lors du chargement, le moteur vérifie :
1. Identité de projet, contenu, règles et checksum `GameSession` existants ;
2. Profil FREE_REALTIME et scène d'exploration connue ;
3. Origine centrale dans une case valide et absence d'obstacle ;
4. Chaque commande du journal, sa séquence, les empreintes d'état recalculées et l'identité de la session ;
5. Position subcellulaire reconstruite et accord avec la position canonique `Campaign.story_flags`.

Aucune conversion silencieuse des sauvegardes `GameSession` v1 historiques : les nouveaux champs ne sont jamais ajoutés aux projets sans routing. Le nouveau journal est réinitialisé lorsque l'on quitte la scène ; **la continuité d'un replay complet traversant plusieurs scènes reste un gate R25.E**.

Ce sont des contrôles d'intégrité, pas une signature cryptographique authentifiant l'auteur d'un fichier.

## Limites et étapes restantes

Ce lot n'est **pas** le runtime action-adventure R26 : pas de vitesse analogique, accélération, corps physique, collision dynamique, ennemis, attaque, manette ni commandes Qt. Pas encore de rendu top-down ni de picking/caméra, d'interface no-JSON ni de vérification matérielle GPU.

Suite : R25.D, projection TOP_DOWN et caméra partagées Studio/Player (picking, DPI, zoom), puis R25.E (checkpoint transactionnel et replay aux frontières de modes). Toute UX/gameplay réelle doit être testée sur Player et Studio Qt, et validée sur machines cibles.

## CI ciblée

```sh
python -m unittest tests_standalone.test_r25_fixed_realtime -v
python -m unittest tests_standalone.test_r25_scene_router -v
python -m unittest tests_standalone.test_r25_foundation -v
python -m unittest tests_standalone.test_game_session -v
```

Workflow : `.github/workflows/r25-fixed-realtime.yml`, Python 3.12 trois OS + Python 3.10/3.14 sur Ubuntu. La création de ce workflow ne vaut **pas** validation : ne marquer vert qu'après inspection des jobs du SHA final.
