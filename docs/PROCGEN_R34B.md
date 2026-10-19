# R34.B — liaison des prefabs et prévisualisation de seeds

**Statut du lot :** proposition de code en PR #351, à valider par la CI et par
un test Qt onscreen réel. Documentation de R34.A : [PROCGEN_R34A.md](PROCGEN_R34A.md).
Roadmap R34 complète : PR documentaire #303 (non fusionnée au moment de ce lot).

## Contrats

La bibliothèque de salles est un objet JSON autonome de *prévisualisation* :

- schema_version = 1
- prefabs : 1 à 64 définitions avec id unique (casse insensible), roles
  (entry/normal/key/goal/exit), biomes, ports (1 à 4 types de connexion),
  et tags optionnels ;
- mission_id optionnel : référence une mission existante de **Content** ;
- asset_id optionnel : référence un **sprite** existant de
  **GameProject.asset_registry()**. L'Asset Registry canonique vérifie la
  référence, mais aucune image ni licence n'est implicitement autorisée
  à l'export.

Les portes sont **des sockets topologiques** avec types identiques sur les
deux extrémités. Leur position réelle dans les coordonnées de la carte,
rotation, collision et instanciation de la salle ne sont pas encore produites.
Le sous-lot refuse toute bibliothèque impossible plutôt que fabriquer de
fausses portes praticables.

La bibliothèque n'est **pas** un nouveau référentiel sauvegardé à côté du
GameProject. L'import R34.C devra être intégré via l'AuthoringSession
existant avec preview/apply/undo et validation des documents. À ce stade,
la bibliothèque est seulement chargée en lecture et attachée à un
rapport exportable.

## Exemple Python headless

Depuis le répertoire racine :

    import json
    from pathlib import Path
    from drawtemp.sdk.procgen_prefabs import (
        generate_with_prefabs, preview_seeds, verify_with_prefabs,
    )

    library = json.loads(Path("examples/procgen_rooms_r34b.json").read_text())
    recipe = dict(seed=7, rooms=12, branches=3, locked_goal=True,
                  encounter_budget=4, loot_budget=3)
    proposal = generate_with_prefabs(recipe, library, biome="forest")
    assert verify_with_prefabs(recipe, library, proposal, biome="forest")
    print(proposal["digest"], proposal["route"])
    results = preview_seeds(recipe, library, list(range(100)), biome="ruins")
    assert all(x["passed"] for x in results)

L'exemple ne possède volontairement **aucune référence d'asset** :
ce sont des modèles topologiques, pas des salles graphiques produites.
Pour référencer des salles réellement authorées, ajouter des mission_id
et/ou asset_id valides et transmettre les objets Content/GameProject
canoniques à generate_with_prefabs et validate_library.

## UI Studio Qt

Dans le Studio Qt : **Outils > R34 • Prévisualiser des donjons procéduraux…**
(également dans la palette de commandes).

- Choisir seed, nombre de salles/branches, verrou, budgets et biome.
- Charger explicitement une bibliothèque JSON (taille plafonnée à 256 KiB).
- Générer la seed : graphe des salles, portes typées et empreintes SHA-256.
- Vérifier 25 seeds : rapport seed par seed avec les échecs et leurs codes.
- Exporter une reproduction JSON : chemin explicite ; aucun écrasement
  d'un fichier existant ; aucun enregistrement automatique du projet.

Le graphe Qt représente des **adjacences**, non une disposition spatiale
réelle à l'échelle des tiles. Les objets des salles ne sont pas jouables
dans le Player sans le futur pipeline d'instanciation.

## Vérification

    python -m unittest tests_standalone.test_procgen_r34 -v
    python -m unittest tests_standalone.test_procgen_prefabs_r34b -v
    QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_procgen_qt_r34b -v

Le test Qt est un **smoke offscreen**, pas une certification GPU réelle. La
matrice existante GitHub Actions Standalone exécute tous les
tests_standalone sur 3 OS et Python 3.10/3.12/3.14, sous réserve de succès
du workflow.

## À faire avant clôture de R34

- Instanciation physique de salles, coordonnées/directions des portes,
  biomes/terrains, collision, propriétés de prefab, validation des droits.
- Sauvegarde non destructive de la bibliothèque et gestion des références
  dans Content/GameProject, avec undo/redo via AuthoringSession.
- R34.C : état run/meta possédé uniquement par GameSession, checkpoints,
  récompenses exactement une fois, mort/restart, replay déterministe.
- Qt onscreen et GPU physique, performance/annulation des batchs longs,
  Player/Studio E2E et packaging multi-OS.

**No-go :** aucun export jouable ne peut être déclaré validé avec
le seul résultat de génération topologique ou un smoke Qt offscreen.
