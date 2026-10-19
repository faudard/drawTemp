# R34.C — run roguelite et progression meta (GameSession)

**Statut :** implémentation sur la branche d'intégration de la PR #339 ;
**tests GitHub Actions/Qt onscreen à confirmer**. R34.A/B proviennent de la
PR #351, fermée sans fusion autonome et reprise dans la consolidation.
La roadmap R31–R40 demeure spécifiée par la PR documentaire #303.

## Le modèle de vérité

- **Configuration auteur** : uniquement
  GameProject.extensions["org.drawtemp.roguelite"], dans une enveloppe
  R24 {schema_version: 1, data: ...}. Son contenu version 1 est :
  version, recipe (R34.A), library (R34.B), biome et meta_reward (0..1000).
- **Édition** : drawtemp.sdk.roguelite_authoring.preview_roguelite_project
  crée un AuthoringPlan R1. Seul AuthoringSession.apply enregistre le
  changement en mémoire dans le projet canonique ; Undo/Redo et Save As
  gardent les garanties existantes. Le Studio affiche une confirmation
  explicite avant application.
- **Runtime** : RogueliteRun est détenu par GameSession (non par le Player,
  le Studio ou un stockage parallèle). Les API sont
  GameSession.roguelite_state/move/claim/checkpoint/die/restart.
  La façade SDK Simulation expose les équivalents révisionnés.
- **Save** : champ facultatif roguelite dans le GameSession version 1.
  Absent pour tous les projets anciens. Obligatoire si le projet active R34.
  Le même checksum GameSession couvre le run et le modèle Content/Project.
- **Replay** : journal borné de commandes {kind,value}. Au chargement le
  journal est exécuté sur la recette + le catalogue vérifiés puis le snapshot
  reconstruit (inventaire, clés, revendications, meta, position) est comparé
  strictement au snapshot enregistré. Changer un digest ne permet pas de créer
  artificiellement une récompense.
- **Mort et victoire** : gagner nécessite passer par l'objectif et atteindre
  la sortie ; meta_reward est créditée exactement **une fois**. Mourir
  conserve la meta deaths mais le restart remet à zéro clés/loot temporaires,
  cases visitées et checkpoint. La seed du prochain run est seed + index.
  Le run meta reste séparé du gold, XP et inventaire Campaign/Jeanne.
- **Limites** : 256 runs (indices 0..255) et 2048 événements journalisés.
  Le gameplay des rencontres/boss/loot reste un modèle de compteurs, pas un
  combat avec ennemis réels. Pas de nouvelle physique ni de rendu dédié.

## Exemple headless de création et reprise

    from drawtemp.sdk.procgen_prefabs import demo_library
    from sporebound.roguelite import EXTENSION
    from sporebound.game_session import GameSession

    # Avec content et project issus des documents GameProject existants :
    project.extensions[EXTENSION] = {
        "schema_version": 1,
        "data": {
            "version": 1,
            "recipe": {"seed": 42, "rooms": 8, "branches": 2,
                       "locked_goal": True, "loot_budget": 8},
            "library": demo_library(),
            "biome": "ruins", "meta_reward": 7,
        },
    }
    project.validate(content)
    session = GameSession.new(content, project, "main", seed=17)
    route = session.roguelite_state()["layout"]["route"]
    session.roguelite_checkpoint()
    for room in route[1:]:
        session.roguelite_move(room)
    assert session.roguelite_state()["meta"]["coins"] == 7
    session.save("run.json")
    restored = GameSession.load("run.json", content, project)
    assert restored.roguelite_state()["status"] == "won"
    restored.roguelite_restart()

Pour configurer sans édition JSON, ouvrir **Studio > Outils > R34** puis
cliquer sur **Activer R34 dans le projet** et confirmer. L'action est
annulable ; enregistrer ensuite le projet depuis le Studio.
Il n'existe pas encore de Player graphique roguelite.

## Tests et barrières de sortie

Tests ajoutés :

    python -m unittest tests_standalone.test_roguelite_r34c -v
    python -m unittest tests_standalone.test_game_session -v
    QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_procgen_qt_r34b -v

Le corpus comprend 100 seeds terminées et rejouées, la comparaison meta,
les checkpoints, sauvegardes compatibles ou incompatibles, les actions
erronées, les digests recomputés pour falsifier une récompense, les tests de
rôle CT et la révision stale du SDK. La matrice large inclut les tests
historiques GameSession et PlayerSession.

**NO-GO pour R34 complet :** le graphe de salles et ses portes ne sont
pas encore transformés en cartes jouables ; il reste l'instanciation et
la navigation physique, le raccordement aux systèmes R26/R33 (ennemis,
combat, événements, inventaire), le Player Qt, l'évaluation des coûts
p95/p99, les essais Qt onscreen/GPU physique et l'export natif multi-OS.
Aucun test offscreen ne constitue une certification GPU.
