# R31.C — Expressions booléennes typées, Si / Sinon exclusif (R9)

**Statut :** implémentation expérimentale sur la branche de consolidation, PR #339. L'acceptation R31 (7.1) est **NON CERTIFIÉE** : attendre CI du SHA final, UI réels, replay et scénario Studio→Player complet.

## Fonctionnel

Depuis **Outils → Game Logic Studio R31…**, créer un graphe v1 (déclencheur + action), puis cliquer **+ Si / Sinon**. L'éditeur introduit un nœud de condition, conserve les actions de la première branche « SI » et ajoute un message « SINON ». L'auteur peut modifier le prédicat et les actions par des boîtes de dialogue typées.

- Déclencheur du graphe : tick ≥ n ou interaction d'objet, **pas** un nouvel événement arbitraire.
- Prédicat du nœud IF : tick ≥ entier, PV d'un acteur sous un pourcentage, acteur vaincu, nombre d'unités vivantes de l'équipe ≤ seuil. Les IDs d'acteurs et les bornes sont revalidés par Content/R9.
- Combinaisons **ET**, **OU** et **NON**, profondeur et cardinalité bornées. **Aucune** évaluation Python, expression arithmétique libre, accès OS, RNG ou appel réseau.
- Connexions étiquetées : une entrée \`flow\`, une sortie **true** et une sortie **false** ; deux séquences d'actions disjointes. Les boucles, branches imbriquées, connexions vers un autre IF, joins et actions avant l'IF sont interdites pour ce sous-lot. Les graphes incomplets restent uniquement en brouillon.
- Le graph schema **v1** reste pris en charge à l'identique ; le schema **v2** est opt-in et strict. \`GameProject.extensions["org.drawtemp.logic"]\` continue à contenir les documents auteurs ; aucun nouveau format de sauvegarde côté Player.

## Conformité moteur (point de sûreté)

Un graphe v2 se compile vers **deux événements R9 natifs** \`r31_{id}_yes\` et \`r31_{id}_no\`, portant le même déclencheur primaire. Le premier a \`when: predicate\` ; l'autre \`when: {"not": predicate}\`. Les deux ont \`cancel_after: [id_de_l_autre]\`.

Le modèle naïf \`when\` seul est **incorrect** : un \`SINON\` pourrait être exécuté à un tick puis, si la condition de jeu change, le \`SI\` serait également exécuté plus tard. La **mutuelle annulation** utilise \`temporal_status\` et le journal de déclencheurs du Battle R9 existant, qui rend la décision irrévocable même sur un prédicat d'HP/d'effectif variable.

Les déclencheurs pairés sont écrits et validés **ensemble**, car une sauvegarde séquentielle échouerait lorsque le premier \`cancel_after\` réfère au second ID encore absent. La transaction unique \`AuthoringSession.preview_pair\` atomise **Content+GameProject** ; la comparaison du dernier trigger compilé protège contre les modifications natives R9 concurrentes. Le passage v1→v2 remplace exactement le trigger R9 ancien et laisse les événements non concernés intacts. Les références étrangères devenues invalides font échouer le projet plutôt que supprimer silencieusement un lien.

Les deux bras utilisent le budget total de 64 nœuds de graphe. Le compilateur limite l'expression à 31 éléments et à 3 niveaux **avant** l'encapsulation \`NOT\` du bras SINON pour respecter les budgets réels R9 (32 éléments et profondeur 4). Déclenchements et actions respectent l'ordre normal de \`sporebound.rules.triggers.dispatch\` ; pas de second ordonnanceur.

## Entrées de code et tests

- \`drawtemp/sdk/logic_branches.py\` : validation récursive et compilation stricte vers deux triggers R9.
- \`drawtemp/sdk/logic_graph.py\` : version 1/2 et remplacement pairé atomique, API compatible \`compile_r9_trigger\` (v1), API \`compile_r9_triggers\` (v1/v2).
- \`drawtemp/studio/logic_graph_draft.py\` : upgrade v1→v2, édition de prédicats, connexions via ports explicites.
- \`drawtemp/studio/logic_graph_qt.py\` : carte \`Si/Sinon\`, courbes coloriées par port, dialogue typé booléen, diagnostic du couple de triggers.
- \`tests_standalone/test_drawtemp_r31_logic_branches.py\` : AST refusé, budget, graphe malformé, compilation, vraie exécution Battle (et persistance de l'exclusivité après changement de condition), migration, R1 Undo/Redo et save/reopen.
- \`tests_standalone/test_drawtemp_r31_logic_qt.py\` : conversion et édition de l'IF dans Qt offscreen.
- \`.github/workflows/r31-visual-graph.yml\` : headless et Qt offscreen Linux/Windows/macOS (Python 3.12), plus contrats R1 et R9 existants.

Exécutions locales :

    python -m unittest tests_standalone.test_drawtemp_r31_logic_graph tests_standalone.test_drawtemp_r31_logic_branches tests_standalone.test_drawtemp_r31_logic_qt.LogicDraftTests -v

    QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r31_logic_qt.VisualLogicQtTests -v

## Limites / suites

Cette réalisation **n'est pas** un interpréteur visuel général : pas de branchement multiples, jonction, attentes, fonction, variables de scène, inventaire/quête, debugger, boucle ou exécution de scripts libres. R31.D doit couvrir le debugger causal, les tests de replay/reprise et les sous-graphes/variables dans un contrat déterministe explicite. R31.12, la démonstration auteur sans JSON et les tests de perception GUI/Player restent ouverts.

**Gate R31 : NO-GO** tant que les preuves multisystème, les régressions R9/R1, la sauvegarde/reprise et un scénario complet ne sont pas validés.
