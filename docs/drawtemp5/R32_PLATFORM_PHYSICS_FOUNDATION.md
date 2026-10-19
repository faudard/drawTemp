# R32.A–B — Side-view Physics & Movement (7.2), tranche headless expérimentale

**État : implémentation partielle sur PR d'intégration #339 ; pas de certification R32.**
Source fonctionnelle : `sporebound/platform_physics.py`. La roadmap normative
est `docs/DRAWTEMP_7_1_TO_8_0_DETAILED_ROADMAP.md` (R32.1–R32.12).
Cette tranche ne rend **pas** un platformer auteur-éditable ni exportable.

## Décision d'architecture R32.1 (ADR, portée limitée)

- Conserver **un seul Core** et les propriétaires de progression
  `GameSession`/Content/GameProject. `PlatformPhysics` est un adapter
  headless opt-in : il ne remplace jamais `Battle` CT, `FreeMovement` R25
  ni `ActionRuntime` R26.
- Pas de dépendance Box2D/native ajoutée : le besoin actuel est un contrôleur
  cinématique déterministe (AABB, plateforme sens unique, triggers) et non une
  simulation rigide générale. Réévaluer moteur physique externe seulement
  avec mesure comparative réelle et dossier API/maintenance/licences.
- Positions et vitesses en **entiers, 1/1000 de case**, 60 Hz logique.
  Gravité et impulsion exprimées par **tick** (non en secondes flottantes).
  Les inputs incluent `tick` strictement croissant ; le rendu lit un snapshot
  **détaché** et ne possède aucune horloge de règles.
- Balayage AABB d'abord horizontal puis vertical, collision solide filtrée par
  `layer` / `mask` (acteur layer=1). Les triggers non bloquants génèrent
  `trigger_enter` et `trigger_exit` triés. Plateformes traversables
  uniquement vers le haut ; contact à la descente. Collision continue par axe :
  pas de tunnel à travers les obstacles AABB dans les cas pris en charge.
- Les plateaux mobiles de cette tranche sont **horizontaux**, à vitesse et
  bornes entières, sens unique ; leur mouvement précède le personnage et
  transporte le personnage déjà posé dessus. Les collisions entre plateformes
  ou entre plusieurs corps mobiles ne sont pas modélisées.
- Le format de scène et le checkpoint `version=1` sont **préliminaires et
  séparés** des documents métier historiques. Ce sont des données de
  simulation **transitoires**, pas une nouvelle source de vérité de projet.
  N'attacher ce moteur à une scène que via un futur mode/profil R25 validé
  et le `GameSession` canonique (gates R31/R32.C). Aucun `GameSession`
  existant ne voit son format modifié par ce lot.

## Contrat actuel

```python
from sporebound.platform_physics import PlatformPhysics

room = {
    "id": "platform_demo", "width": 12000, "height": 6000,
    "gravity": 40,
    "hero": {
        "pos": [1000, 4200], "size": [500, 800],
        "speed": 240, "jump": 520, "max_fall": 900, "coyote": 4,
    },
    "colliders": [
        {"id": "floor", "rect": [0, 5000, 12000, 1000],
         "layer": 1, "mask": 1, "trigger": False, "one_way": False},
    ],
}
game = PlatformPhysics(room)
game.step({"tick": 1, "move": 1, "jump": True})
snapshot = game.snapshot()  # affichage seul
checkpoint = game.recording()
same_state = PlatformPhysics.from_recording(checkpoint, expected_scene=room)
assert same_state.digest() == game.digest()
```

Le checkpoint est l'enveloppe `{version, scene, commands, state_digest,
digest}`. Le digest est un contrôle d'intégrité reproductible **non signé**,
pas une preuve de confiance ou d'authenticité. Au chargement, on valide
le schéma, l'identité de la scène et **chaque commande rejouée**, puis on
compare les états. Les entrées invalide sont rejetées avant mutation.

## R32 : couverture vérifiable et reste à faire

| ID | Statut dans cette tranche | Preuve / manque |
|---|---|---|
| R32.1 | ADR partiel | Choix adapter entiers ; benchmark/licences API comparatif encore requis |
| R32.2 | Partiel | AABB/layers/masks/triggers ; segments, polygones et collisions de formes restent à faire |
| R32.3 | Partiel | Corps cinématique 1 héros ; pas de corps dynamiques, friction/accélération |
| R32.4 | Partiel | Marche/saut/chute/réception/coyote ; course et profils Studio restent à faire |
| R32.5 | Partiel | Collision AABB balayée par axe, cas thin-wall ; couples dynamiques non couverts |
| R32.6 | Partiel | Plateformes horizontales mobiles/one-way ; pentes, échelles et verticales à faire |
| R32.7 | Partiel | Triggers et sol ; liaison R31, capteurs mur/eau à faire |
| R32.8 | À faire | Editeur de collisions Qt, Undo/Redo, preview et overlay |
| R32.9 | À faire (P1) | Poussée, rebond, contraintes, vent |
| R32.10 | À faire | Animation, hitbox/hurtbox et R26 synchronisés |
| R32.11 | Partiel | Replay/snapshot/checkpoint isolé ; intégration sauvegarde atomique GameSession à faire |
| R32.12 | À faire | Mesures p95/p99 CPU/GPU, QA onscreen/hardware |

## Conditions de sortie et dépendances

1. L'atelier R32.C doit écrire des colliders dans le même document
   versionné que les autres scenes, transactionnellement avec Undo/Redo.
   Les conditions et événements R31 utilisent le bus métier commun,
   jamais un second état de quête indépendant.
2. Intégrer `PlatformPhysics` sous `GameSession` et `SceneRouter` avec
   contrôle des profils, transitions, sauvegardes et replays mixtes.
   Certifier que `Jeanne` CT et `ActionRuntime` R26 sont inchangés.
3. Exécuter les tests headless R32 + gameplay existant sur 3 OS. Réserver
   un gate Qt onscreen sur vrai Player/Studio et un gate GPU physique avec
   métriques p95/p99 ; aucun test headless ne remplace ces preuves.
4. Gate R32 complet : personnage saute sur une plateforme mobile, active
   un interrupteur R31, sort/revient d'une scène, reprend après save/load
   depuis le même état ; même logique avec rendu 30/60/120 Hz.

**Vérification locale conseillée :**

```sh
python -m unittest tests_standalone.test_platform_physics_r32 -v
python -m unittest tests_standalone.test_action_runtime_r26 -v
python -m unittest tests_standalone.test_game_session -v
```

## R32.C — Progression Studio : colliders transactionnels

L'atelier **Gameplay → Colliders 2D (R32)** contient maintenant :
- un sélecteur de scène référencée par le Content/GameProject canonique ;
- la création d'un modèle AABB, la modification/suppression des formes,
  le snapping des champs numériques (100 sous-unités), les masques/couches,
  les triggers et les plateformes horizontales mobiles ;
- un **aperçu de diagnostic QGraphicsView** (ce n'est pas le rendu Player R3) ;
- Prévisualiser → Appliquer : une transaction R1 avec révision, Undo/Redo,
  sauvegarde double-document et reprise selon le gestionnaire R1 existant.

`sporebound/physics_scenes.py` définit l'enveloppe typée facultative
`GameProject.extensions["drawtemp.physics"]`, avec
`{schema_version:1, data:{scenes:{...}}}`. Au chargement du GameProject,
`validate_physics_catalog` refuse toute référence de scène inconnue et
toute géométrie malformée ; les sauvegardes de projets historiques sans
extension sont inchangées. Aucune clé de sauvegarde gameplay R17/R25 n'est
ajoutée. Le modèle accepte à ce stade 8 scènes expérimentales, sous la limite
de taille R24 des extensions.

Les scènes peuvent être rattachées aux identités de missions, scènes
narratives ou explorations déjà créées. **Cela ne change pas leur mode réel
dans GameSession** : le Player doit encore obtenir un routage physique explicite
et lier les triggers aux événements R31 avant qu'un platformer soit jouable.

Tests ciblés :
```sh
python -m unittest tests_standalone.test_platform_physics_r32 -v
python -m unittest tests_standalone.test_platform_collider_authoring_r32 -v
QT_QPA_PLATFORM=offscreen python -m drawtemp.studio.qt_shell --smoke --workspace gameplay
```

Les gates R32.C ne sont **pas** clos tant que le routeur/Player, l'édition
visuelle avancée, la reprise interscène, la validation Qt onscreen et les
tests utilisateurs/hardware n'ont pas été exécutés.
