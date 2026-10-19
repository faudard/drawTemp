# R34.A — génération procédurale déterministe (premier incrément)

**Statut :** implémentation headless proposée, **non intégrée** dans le Player,
GameSession, le Studio Qt ni l'export. La roadmap R34 complète se trouve dans
la PR documentaire [#303](https://github.com/faudard/drawTemp/pull/303),
basée sur la roadmap multi-genres fusionnée en [#289](https://github.com/faudard/drawTemp/pull/289).

## Ce que livre le lot

- Contrat de recette **version 1**, algorithme explicite room-graph-v1, seed
  entière bornée et paramètres strictement validés (ProcGenRecipe).
- Graphe connexe avec entrée, objectif, sortie et branches ; degrés plafonnés
  à 4 ; porte de l'objectif optionnellement verrouillée et clé placée dans une
  branche accessible **avant** le verrou.
- Solveur exact à états (salle, clés, objectif visité) ; une génération
  impossible est rejetée avec un code ProcGenError, jamais corrigée
  silencieusement.
- Budgets bornés de **comptage** rencontres/loot et placement déterministe
  (pas encore de tables de drops, ennemis, prefabs ou équilibrage réels).
- Sérialisation JSON de la recette et du résultat, digest SHA-256 du contenu
  canonique (intégrité accidentelle, **pas** signature cryptographique).
- API headless generate, verify et generate_batch pour les diagnostics et
  corpus multi-seeds ; batch limité à 500 seeds, 64 salles, 256 placements.

## Exemple

Depuis la racine du dépôt :

    from drawtemp.sdk.procgen import ProcGenRecipe, generate, verify

    recipe = ProcGenRecipe(seed=42, rooms=12, branches=3, locked_goal=True)
    layout = generate(recipe)
    print(layout["digest"], layout["route"])
    assert verify(recipe, layout) == layout["route"]

Pour rejouer le même monde, conserver **toute** la recette, y compris
algorithm et schema_version. Des versions futures devront utiliser un
identifiant d'algorithme distinct si la sortie change.

## Tests

    python -m unittest discover -s tests_standalone -p 'test_procgen_r34.py' -v

Les tests de ce lot couvrent **100 seeds verrouillées + 100 non verrouillées**
répétées deux fois, les chemins entrée→objectif→sortie, les budgets, la
stabilité des digests, le refus des recettes incohérentes, la corruption et
l'isolation des objets produits. Cela **ne constitue pas** un gate R34
end-to-end, Qt, GPU, export ou sauvegarde.

## Travaux nécessaires pour fermer R34

1. **R34.B :** importer/valider des prefabs de Content/GameProject et
   Asset Registry, vérifier ports de portes/biomes, atteindre les contraintes
   de capacités R33, exposer l'éditeur/preview seed Qt et les diagnostics.
2. **R34.C :** connecter l'état du run à **GameSession** existant (sans second
   propriétaire de la vérité), séparer état run/meta, garantir transaction de
   récompense unique, save/replay/rollback/restart et parcours Player complet.
3. **R34 gate :** valider les seeds réelles avec contenus, quêtes et ennemis,
   réaliser les tests onscreen, CI multi-OS, performance, export natif et
   preuve de licence des assets.

Ce module **ne modifie aucun format de sauvegarde existant** et ne promet
aucune compatibilité avec les travaux R31–R33 non encore fusionnés.
