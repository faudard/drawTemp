# 3.7.21A — Workspace UX : panneau de production de missions

Cette évolution assemble les composants d'édition existants. Elle ne crée pas
de format de sauvegarde, de règles de combat ni d'index persistant supplémentaire.

## Atelier Carte et combat

- **Projet** à gauche : même `StudioIndex` et même recherche que l'onglet
  **Espace projet**. Double-clic ou Entrée sur une ressource pour ouvrir son
  éditeur d'origine (carte, siège, récit, cinématique, etc.). La sélection est
  résolue dans le Workspace canonique, avec ses validations actuelles.
- **Carte** au centre : le canvas et ses commandes d'édition ne changent pas.
  Les deux séparateurs de `ttk.Panedwindow` permettent d'ajuster la largeur
  du navigateur et de l'inspecteur ; un troisième règle la hauteur du journal.
- **Inspecteur** à droite : identité de l'élément sous la sélection courante
  (terrain / acteur / objet), détails de terrain et d'état tactique, mini-carte,
  **boutons contextuels vers la fiche exacte du personnage ou de l'objet**.
  Ces boutons sont inactifs en playtest ou sans entité sélectionnée. Le panneau
  d'inspection et le journal sont en lecture seule.
- **Barre d'outils compacte** en quatre groupes : Carte & combat,
  Terrain & couches, Architecture, Sélection & modèles. Huit couches sont
  dans un menu plutôt qu'une rangée de cases qui déborde à 1280 px.
- **Recherche intégrée** partagée avec l'onglet Espace projet, compteur de
  résultats, synchronisation sur la mission active et restauration de la
  sélection des acteurs/objets lors des rafraîchissements.
- **Journal de combat** sous la carte, dans un onglet bas avec l'aide rapide.
  Les événements restent ceux du `Battle` exécuté ; le panneau ne les interprète
  pas.
- **Mode explicite** : `ÉDITION` ou `PLAYTEST (édition verrouillée)`.
  Le playtest continue à travailler sur la copie indépendante du `Document`.

Raccourcis : `Alt+1` carte, `Alt+2` Espace projet, `Ctrl+F` recherche
sur le projet, `Échap` efface la recherche. `Ctrl+C` et `Ctrl+V`
restent attachés au canvas pour la sélection des cases. Le démarrage
d'un playtest réactive automatiquement l'onglet Carte & combat.

## Préservation des contrats existants

Le navigateur intégré appelle `ProjectWorkspaceTab.open_key()` puis le
routage de `open_selected()`. Il n'introduit aucune modification parallèle
de `Content`, `GameProject`, `Document`, `Battle`, des atlas ou des
replays. Les validations de changement de campagne et les commandes existantes
restent donc exécutées au même endroit.

L'onglet Espace projet complet et les éditeurs individuels restent
accessibles. La sauvegarde du contenu et celle du projet restent **séparées** :
la commande atomique « Enregistrer tout » appartient à **3.7.21B**.

## Validation

```sh
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_workspace_gui \
  tests_standalone.test_workspace_shell_gui -v
python -m unittest discover -s tests_standalone
```

Vérifications UI à réaliser sur chaque OS : fenêtre 1280×850, redimensionner
les trois séparateurs, choisir deux missions depuis le navigateur, survoler et
sélectionner des objets, lancer / quitter le playtest, parcourir les onglets
Studio, conserver undo/redo et le contenu après sauvegarde/réouverture.

Le smoke test ne prouve pas l'esthétique du rendu sur Windows/macOS ni les
performances de manipulation sur très grandes cartes. Ces validations restent
ouvertes ; ne pas présenter la seule CI Python comme un gate UX final.
