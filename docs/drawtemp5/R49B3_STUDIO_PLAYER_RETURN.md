# R49.B3 — Cycle de playtest Studio → Player → Studio

**Statut : code en PR empilée après R49.B2. Gate R49.6 = PARTIEL ; R49 global = OPEN.**

## Limite identifiée dans le code existant

Le Studio lançait `QProcess.startDetached(sys.executable, ...)`, validait le simple
lancement et créditait immédiatement l'étape du guide. L'API détachée ne
permettait ni de connaître le code de sortie, ni de diagnostiquer les échecs,
ni de bloquer un double démarrage, ni de revenir à la ressource d'origine.

## Implémentation R49.B3

- Nouveau `drawtemp/studio/r49_playtest.py` **sans Qt** : contrat d'identité
  du contexte édité (workspace R18, identifiants ressources R2, zone de focus
  R49.B1, identité de session et chemin du document), état du run
  `starting/running/stopping/finished/failed/stopped` et code de sortie.
  Seul `started() + finished(exit_code=0, crashed=False)` peut conduire
  à `successful=True`. Un arrêt demandé, un crash, un exit non nul ou un
  échec de démarrage ne valide jamais le parcours.
- Le Studio supervise le processus enfant via **QProcess propriétaire** avec
  `started`, `errorOccurred`, `finished`, `readyReadStandardOutput`
  et `readyReadStandardError`. Le point d'exécution reste **fixé par
  le Studio** : `sys.executable -m drawtemp.player.qt_app --content <path>`.
  Aucune commande shell, URL distante ou exécutable depuis Content/GameProject.
- **Un seul Player** à la fois. Lancement refusé si brouillon de propriété non
  appliqué. Ouverture/fermeture/changement de projet, sauvegarde, sauvegarde
  sous et export bloqués tant que le Player est actif pour conserver une
  paire disque déterministe. Navigation entre ateliers toujours possible.
- Menu Fichier : **Playtest**, **Arrêter le playtest**, **Revenir à l'édition
  testée**, **Diagnostics du dernier playtest**. La page Publication expose
  aussi jouer/arrêter.
- **Arrêt gracieux** par `terminate()` ; repli `kill()` après 2,5 secondes
  si le processus ignore l'arrêt. Un `stopped` ne vaut pas `finished`.
- Diagnostics stdout/stderr en mémoire bornée (4 096 caractères par canal,
  troncature annoncée), consultables en lecture seule. Aucune télémétrie,
  pièce jointe, sidecar, création de sauvegarde ou mutation de gameplay par
  ce contrôleur. Les logs peuvent malgré tout contenir des chemins locaux :
  ne pas les publier sans revue.
- **Retour explicite** au workspace, aux clés de ressources encore présentes
  et à la zone de focus précédents. Le retour est indisponible si le document
  ou sa session a changé ; aucune restauration automatique intrusive si
  l'auteur est en train de travailler ailleurs. Une ressource supprimée est
  signalée comme retour partiel, pas réinventée.
- `_guide_mark("playtest")` est effectué uniquement à la **fin normale
  (exit code 0)**. Cela prouve une exécution de processus, **pas**
  la réussite d'un combat ou la certification du jeu exporté.

## Vérifications ajoutées

```sh
python -m unittest -v \
  tests_standalone.test_r49_playtest_lifecycle \
  tests_standalone.test_r49_inspector_integrity \
  tests_standalone.test_drawtemp5_r18b \
  tests_standalone.test_r49_workspace_focus \
  tests_standalone.test_r49_creator_ux \
  tests_standalone.test_r49_experience
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.studio.qt_shell --smoke
```

Les tests unitaires couvrent transitions, échec de démarrage, code non nul,
arrêt volontaire, sortie précoce, UTF-8 partiel, limite de logs, durée de vie
du contexte et validations d'entrée. Les tests Qt lancent de **vrais enfants
Python inoffensifs** pour éprouver les signaux et le retour à une ressource du
Studio ; ils **ne simulent pas** qu'un vrai Player graphique a fonctionné.

## Gate manuel obligatoire / non réalisé

1. Sur Windows, Linux et macOS, créer/ouvrir une paire Content +
   GameProject valide, sauver puis lancer le **vrai** Player Qt.
2. Lancer une mission et plusieurs actions tactiques ; vérifier sons,
   rendu, clôture et code de sortie, ainsi que les diagnostics accessibles.
3. Pendant l'exécution, vérifier le blocage d'un second Player, d'une
   sauvegarde ambiguë et d'une fermeture du Studio ; naviguer entre ateliers.
4. Terminer puis choisir « Revenir à l'édition testée » : vérifier l'atelier,
   la bonne mission et la sélection, sans divergence de ressources.
5. Forcer un crash, un Player manquant et un arrêt volontaire ; aucun ne
   valide le playtest. Contrôler les cas de refus/retour partiel.
6. Vérifier la CI et le rendu **onscreen**, les lecteurs d'écran et le
   packaging du Player sur poste propre.

**Gate R49.6 : partiel tant que le vrai Player n'a pas été exécuté et revu.
R49.C / VS-49 : non certifiés.**
