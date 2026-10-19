# R31.D — Débogueur visuel de logique, adossé au dispatcher R9

**Statut au 19 octobre 2026 :** incrément expérimental ajouté à la branche de consolidation de [PR #339](https://github.com/faudard/drawTemp/pull/339). **Non certifié** tant que la CI de la tête finale, les tests matériels/visuels et les parcours Studio→Player ne sont pas passés.

## Usage dans le Studio Qt

1. Ouvrir **Outils → Game Logic Studio R31…**, charger un graphe **déjà appliqué**. Un brouillon nouveau, non relié ou modifié ne peut pas être débogué : cliquer **Vérifier**, puis **Appliquer**.
2. Sous la barre de création de nœuds, choisir le scénario de test : **Initial**, **Condition satisfaite** ou **Condition non satisfaite**, plus un **tick logique** de départ. Les deux derniers sont des *préparations synthétiques*, jamais un replay authentifié.
3. **Démarrer debug** construit un \`EventDebugger\` sur un **Battle jetable**, utilisant les déclencheurs natifs R9 de ce graphe. Les graphes v2 chargent *ensemble* les deux événements \`_yes\` et \`_no\`; \`cancel_after\` reste appliqué par le vrai moteur.
4. Sélectionner le **nœud d'entrée** ou **Si / Sinon**, puis **Point d'arrêt** : arrêt **avant** toute action d'un événement R9, sans exécution silencieuse. Le point d'arrêt sur le nœud Si/Sinon correspond aux **deux** événements natifs. Un point d'arrêt *dans* une action est refusé explicitement ; ce niveau de granularité n'est pas encore pris en charge par R9.
5. **Pas événement** exécute **un événement complet**, actions dans l'ordre natif, sur le Battle jetable. **Continuer** utilise le point d'arrêt R9 le plus proche. **Inspecter** donne les résultats de vrais prédicats R9, le statut temporel (prêt, déclenché, annulé) et, sur une action, son payload R9.
6. Les cartes du graphe se colorent selon la progression et les points d'arrêt ; l'historique affiche les événements déclenchés, le tick, leurs nœuds R31 d'origine et les effets mesurés (PV, positions, dangers, etc.). Un événement annulé (branche non choisie) ne sera **jamais** montré comme action exécutée.
7. Toute modification/annulation/rétablissement du document **invalide** le diagnostic en cours via la révision R1. Redémarrer le diagnostic après cette modification.

## Architecture et sécurité

- \`sporebound/event_debugger.py\` : extension **opt-in** de sélection explicite d'événements natifs déjà compilés, avec contrôle des IDs et du budget. L'ancien workflow de débogage R9, dont la sélection par descendants, reste inchangé.
- \`drawtemp/studio/logic_debugger.py\` : adaptateur headless. Au démarrage, compare **chaque trigger R9 compilé** avec le document Content stocké et refuse toute divergence ou permutation. Chaque ID de nœud est relié aux événements natifs et aux indices d'actions. L'adaptateur **ne** réévalue **pas** les prédicats : \`EventDebugger.inspect\` et \`sporebound.temporal_events.temporal_status\` sont les autorités.
- \`drawtemp/studio/logic_graph_qt.py\` : panneau de contrôle, inspection, diagnostics, projection de statuts sur les cartes et confirmation qu'un débogueur n'écrit pas le projet.
- Aucun \`eval\`, aucun scheduler supplémentaire, aucune mutation de \`AuthoringSession\` par l'outil de debug, pas de persistance de l'état synthétique dans GameProject ni dans les sauvegardes du Player.
- Tous les rapports exposent \`isolated=true\` et \`replay_verified=None\`, la mention explicite **« Replay : NON ATTESTÉ »**, ainsi qu'une \`step_granularity="native_trigger"\`. Les traces sont des **copies détachées**.
- Lorsque l'auteur choisit un scénario « condition satisfaite », le debugger prépare un état **synthétique**. Il ne s'agit pas d'une certification de déterminisme de partie sauvegardée/reprise. Le profil d'exécution et la graine sont locaux au diagnostic.

## Tests / CI

    python -m unittest tests_standalone.test_drawtemp_r31_logic_debugger -v

    QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r31_logic_qt.VisualLogicQtTests -v

Le workflow \`.github/workflows/r31-visual-graph.yml\` relance aussi les contrats R1/R9/R31.A/B/C sur **Ubuntu, Windows et macOS** avec Python 3.12, et le chemin Qt \`offscreen\`. Des tests incluent : points d'arrêt pré-effets, progression à l'événement natif, deux branches concurrentes qui ne doivent pas se déclencher ensemble, modifications concurrentes, Undo invalidant la session, erreurs de typage et aucune modification du document R1.

## Limites et suite

Le débogueur est **événementiel**, pas un inspecteur pas-à-pas d'action ou de port de données arbitraire. Il ne fournit pas de replay certifié, de boucle/attente, de sous-graphe, de variables persistantes, de télémetrie de temps réel, ni de scénario d'export installé. Une granularité « action » imposerait d'étendre de manière instrumentée et réversible le dispatcher canonique R9 ; ce n'est **pas** activé ici.

**R31 gate : NO-GO.** Prochaines étapes suggérées : durcir les scénarios de debug issus de conditions complexes, valider la lecture du journal avant/après redémarrage, puis développer les **variables/attentes** et le scénario E2E joueur « PNJ → porte → combat → coffre → quête », avec test de replay authentifié.
