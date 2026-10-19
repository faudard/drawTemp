# R29.B — Gameplay Lab : replay action et détection de softlocks

**Statut : code proposé ; certification R29 encore NO-GO.**

Cette tranche poursuit [R29.A](R29_MULTI_GENRE_QA.md) et la [roadmap R29](../DRAWTEMP_MULTI_GENRE_CREATOR_ROADMAP.md). Les PR [R26 #300](https://github.com/faudard/drawTemp/pull/300) et [R27 #304](https://github.com/faudard/drawTemp/pull/304) sont toujours indépendantes : aucun faux adaptateur runtime n'est créé.

## Livrables et preuve

1. R29.9 : exploration BFS bornée des états (cellule, objets ouverts, inventaire) pour le schéma des scènes R26. Maximum 12 objets interactifs et 200 000 états. Modèle statique des murs, coffres à récompense unique, clés consommables, portes et objectifs. Tous les scénarios sont parcourus sans mutation de la scène source.
2. Pour chaque objectif atteint, un témoin de chemin abstrait est enregistré. Les sorties inaccessibles et états atteignables n'ayant **plus aucun chemin** vers une sortie, y compris après consommation d'une clé sur la mauvaise porte, fournissent des contre-exemples explicites.
3. Budget dépassé : résultat INCONCLUSIVE, jamais réussite. Une scène avec ennemis indique clairement que combats/IA/collisions ne sont pas modélisés.
4. R29.1/R29.3 : audit_action_replay utilise la vraie classe sporebound.action_runtime.ActionRuntime lorsqu'elle existe. Le journal de commandes est rejoué et vérifié par reconstruction à chaque checkpoint et en fin de trace. Avant intégration de #300 : BLOCKED, sans faux vert.
5. Adaptateur R27 : audit_dungeon_puzzle consomme un vrai DungeonStudio.puzzle_report, conserve résultats et limites de cette analyse déjà en R27.
6. La sortie JSON indique toujours release_ready=false et decision=no-go, même si les tests statiques sont verts.

## Utilisation

Exécuter les tests :

    python -m unittest tests_standalone.test_r29b_gameplay -v

Analyser la scène de démonstration issue du contrat R26 :

    python scripts/audit_r29b_gameplay.py --scene tests_standalone/fixtures/r29b_action_ruins.json --goal 4,2 --require-solved --report build/r29b/ruins.json

Options : plusieurs arguments --goal X,Y pour les sorties, --state-budget N pour borner l'exploration, --commands inputs.json pour les entrées tick R26 réelles. Un objectif se termine dès qu'il est atteint ; chacune des sorties demandées est aussi auditée individuellement. Les objectifs doivent être explicitement déclarés.

Codes de sortie : 0 = chemin possible dans le modèle statique, mais **pas certification du Player** ; 1 = risque de softlock ou entrée invalide ; 2 = inconclusif, dépendance replay manquante, budget dépassé. --require-solved refuse également les ennemis exclus de l'analyse statique.

## CI

Le workflow drawtemp-r29b-gameplay.yml déclenche neuf tests de régression sur Ubuntu, Windows, macOS et exécute la fixture headless. Il produit un rapport téléchargeable sans annoncer GPU/Player/export certifiés.

## Limites et suite

Le BFS travaille à l'échelle des cases, et ses commandes sont des diagnostics, pas des inputs de simulation. Il exclut collisions de mouvement continu, vitesse/FPS, IA, combats, dénouements de quêtes, CT, transitions de scènes, Player graphique et sauvegarde hybride. Il ne remplace pas les gates licences R4, GPU R14, export R15 ni les tests utilisateurs R29.7.

Prochaine étape après intégration R25/R26/R27/R28 : convertir les témoins abstraits en vrais ticks, valider reprise/crash et changement action→CT→action, compléter RPG classique et approuver des goldens multi-DPI ainsi que les bundles installés sur machines propres.
