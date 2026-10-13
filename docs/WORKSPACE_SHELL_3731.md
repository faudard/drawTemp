# 3.7.31 — Workspace Shell consolidé (A–E)

Une seule interface autour du document Content, du GameProject, de
`StudioIndex` et des outils Tk existants. Aucun manifest supplémentaire,
aucune modification de schéma ni de comportement moteur.

## 3.7.31A — Navigation
- Les acteurs et objets **placés** apparaissent dans les deux arbres du
  Workspace, indexés par `map_actor:<mission>/<id>` et
  `map_object:<mission>/<id>`.
- Les groupes persistants issus de 3.7.25 (#116 désormais fusionnée)
  sont référencés par `editor_group:<mission>/<id>` sans duplication
  de schéma, avec liens vers mission, sous-groupes, acteurs et objets.
- Entrée ou double-clic sélectionne la mission, centre la sélection logique
  sur la case concernée et ouvre « Carte et combat ».
- La navigation vers les éditeurs spécialisés (campagne, scène, cinématique,
  événement stratégique) continue d'emprunter les routes existantes.

## 3.7.31B — Inspecteur partagé
`workspace_shell.inspect_map()` est une projection en lecture seule de la
même donnée que l'inspecteur sur la carte. Elle décrit cases, unités, objets
interactifs et sélection multiple de cases (groupe de sélection).
Les fiches détaillées d'entités restent dans le Studio.

L'inspecteur décrit également les **groupes hiérarchiques persistants**
de `Mission.editor_groups` (membres directs, descendants, emprise et
parent). Sélectionner un groupe du Workspace ouvre sa mission et sa
première case visible ; un groupe vide ouvre simplement sa mission.
L'édition de l'arbre, le déplacement et l'annulation demeurent dans
**Groupes et appartenances** de l'éditeur 3.7.25, leur source de vérité.

## 3.7.31C — Drag & drop
Un vrai geste pointeur sur la palette d'assets, la palette d'entités ou le
navigateur du Workspace dépose sur le canvas tactique visible. Les cibles hors
canvas et les mouvements involontaires sont ignorés ; les modifications JSON
en attente et le playtest empêchent le dépôt. L'opération réutilise les
callbacks de placement, la validation Content et l'undo/redo actuels.

Les références d'acteurs/objets d'une autre mission sont refusées pour éviter
une copie silencieuse entre missions. Pour les passages non entièrement
paramétrés, l'assistant de pose existant reste nécessaire.

## 3.7.31D — Problèmes navigables
Le panneau « Problèmes » affiche les diagnostics de `StudioIndex`, dont
les erreurs d'assets, plus un avertissement d'auteur **pour une porte sans
référence entrante** (levier, bélier ou catapulte). Cette dernière est une
alerte éditoriale, pas une erreur de validation du moteur.

Double-clic/Entrée → ressource ou case sur la carte. Après correction via
la palette, l'index est recalculé sur les documents courants et la ligne
disparaît, sans action « Rafraîchir ». Les items Tk ne sont repeints que
si la liste des diagnostics change.

**Gate reproductible :** ajouter une porte isolée, ouvrir le diagnostic,
naviguer vers la porte, placer un levier pointant sur son ID, constater la
disparition de l'avertissement. Annuler recrée l'alerte ; rétablir la résout.

## 3.7.31E — Disposition et clavier
- Splitters gauche/centre/droite et centre haut/bas sauvegardés dans
  `*.workspace.layout.json` (préférences UI séparées des données du jeu).
- Restaurer la disposition et l'onglet principal au démarrage.
- Alt+1 : Carte, Alt+2 : Workspace, Alt+3 / Ctrl+Maj+P : Problèmes,
  Ctrl+F : recherche projet ; Entrée sur une ligne de Problèmes : navigation.
- Historique : Undo/Redo existants. Console : messages du statut de Studio.
  Simulation : Playtest existant, sans second moteur.

## Validation
- `python -m unittest tests_standalone.test_workspace_shell_3731`
- `python -m unittest tests_standalone.test_editor_groups_3725`
- `SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_workspace_shell_3731_gui`
- Vérifier aussi `tests_standalone.test_workspace`,
  `tests_standalone.test_game_studio4` et
  `tests_standalone.test_workspace_shell_gui`.

Les éditions restent des opérations atomiques de `Document.replace` et ne
contournent jamais les règles Content existantes.
