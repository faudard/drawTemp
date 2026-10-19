# R49.B1 — Workspace focus, clavier & préflight Creator lisible

**Statut : code en PR empilée sur R49.A. Gate R49 = OPEN, non certifié.**

## Objectifs atteints en code

### R49.2 — navigation et focus par atelier (partiel)

- Mémorisation du **type de zone active** par workspace connu R18 : `workspace`, `search`, `resources`, `inspector`, `diagnostics`.
- Sauvegarde de ces seuls identifiants validés dans QSettings
  (`ux/r49/focus/{workspace}`). Aucun chemin, ID ressource, nom de widget,
  données de projet ou référence QObject n'est sérialisé.
- À la navigation, restauration uniquement d'un contrôle *existant, visible et
  activé*. Fallback conservateur vers l'atelier : pas d'ouverture implicite
  de panneau invisible ou de création de workspace par le système de focus.
- Raccourci `Ctrl+3` « Revenir au contenu de l'atelier » après navigation
  dans les docks/menus. Conserve les raccourcis R18 et les contrôles R49.A.
- Lors de la fermeture du shell, déconnexion du signal global Qt
  `focusChanged` pour éviter qu'une fenêtre fermée conserve un listener.

### R49.3 — création de projet sans manipulation de JSON (partiel)

- L'assistant R28/R15 existant reste le seul créateur de Content + GameProject.
- Préflight lisible : statut, genre, dossier, mode mouvement/combat/caméra,
  blocages explicites et limites de certification. Aucun dump de JSON demandé
  à l'auteur.
- **SRPG et narration** utilisent les modèles réellement disponibles en R15.
  **Action-aventure, RPG classique et hybride** restent bloqués tant que leurs
  contrats de création/runtime ne sont pas effectivement intégrés ; aucun
  template tactique mensonger n'est généré à leur place.
- Refus des destinations déjà existantes **et des symlinks cassés** avant
  création ; contrôle à la fois côté wizard et dans le factory R15.
- Pas de nouveau modèle RPG, ni modifications des sauvegardes ou replays Jeanne.

## Tests ajoutés

- `tests_standalone/test_r49_workspace_focus.py` : préférences invalides,
  confidentialité, conservation/migration des régions, restauration focus et
  raccourci Qt, absence de création paresseuse parasite.
- `tests_standalone/test_r49_creator_ux.py` : rapport clair, préflight des
  genres indisponibles, incompatibilités fail-closed et lien symbolique brisé.
- CI Linux/Windows/macOS Python 3.12, Qt offscreen et régressions R49.A/R28.
- Les tests offscreen ne valent pas certification UX onscreen ni GPU.

## Vérifier

```sh
python -m unittest -v \
  tests_standalone.test_r49_workspace_focus \
  tests_standalone.test_r49_creator_ux \
  tests_standalone.test_r49_experience \
  tests_standalone.test_r28_creator_workflow
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.studio.qt_shell --smoke
```

Parcours manuel requis : ouvrir le Studio, déplacer le focus Recherche puis
Publication, revenir sur Projet et constater le retour sur Recherche. Tester
`Ctrl+3`, le mode sombre, les lecteurs d'écran et le clavier AZERTY/QWERTY
avec une fenêtre visible. Ouvrir le wizard ; SRPG/narration doivent être
créables, les modes non disponibles explicitement bloqués sans fichier disque.

## R49.B restant et conditions de fermeture

- **R49.B2** : inspecteur commun source→usage avec erreurs inline et typage
  multi-ateliers ; focus granulaire dans les éditeurs, validation onscreen.
- **R49.B3** : playtest Studio→Player→Studio avec conservation contexte et
  diagnostics, sans retour fictif après `startDetached`.
- **R49.C** : test utilisateur tiers VS-49 (création→scène→règles→combat→
  playtest→export), fault injection, perf gros projets sur matériel cible,
  licences et Player clean-machine.

Aucun point P0 n'est clos par la seule présence de code en PR ; les gates
dépendent de tests exécutés et de preuves sur le SHA intégré dans `master`.
