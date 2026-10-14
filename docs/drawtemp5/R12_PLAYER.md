# DrawTemp 5 — R12 Player 5.0 (première tranche)

## Lancer le Player

Depuis la racine du dépôt (Python 3.12 requis pour l'extra Qt 6) :

```bash
python -m pip install -e ".[qt6]"
python -m drawtemp.player.qt_app
# ou après installation : drawtemp-player5
```

Ce lanceur **n'importe pas Tk**, n'ouvre jamais le Studio et ne requiert pas le
serveur de l'éditeur. La campagne par défaut est **Jeanne d'Arc — Les Cendres du
Royaume**, chargée depuis `sporebound/content/jeanne.json` et
`jeanne.game.json`. Les sauvegardes sont dans
`~/.drawtemp/player5/jeanne/slot_N.json` (dossier personnalisable par
`--save-dir`).

`python -m drawtemp.player.qt_app --reference` démarre la fixture de migration
R0 pour les régressions. `--smoke` vérifie l'initialisation du QML puis ferme
la fenêtre (en CI, utiliser `QT_QPA_PLATFORM=offscreen`).

## Écran et commandes

| Contexte | Interaction |
|---|---|
| Titre | Nouvelle partie, Continuer, emplacement et Charger |
| Prologue | Exploration isométrique par flèches / ZQSD / WASD, clic sur une case adjacente |
| Exploration | Interaction avec un point du décor ; action sur un habitant |
| Dialogue | Choix validés par le moteur narratif, non par un embranchement QML |
| Campagne | Mission déverrouillée → rencontre tactique |
| Combat | Clic pour sélectionner une case, déplacer, attaquer, compétence, objet, objet interactif, fin de tour |
| Combat | Aperçu action calculé par `Simulation.preview` ; la simulation ne mute jamais la session |
| Combat | Tour ennemi : `Simulation.auto_enemy_turn`, borné à 40 activations par demande |
| Résultat | Retour au carnet de campagne (pas de sortie anticipée du combat) |
| Global | Molette = zoom isométrique ; F5 = sauvegarde ; Échap = pause ; options de lecture/contraste |

Les règles de combat, les objets de mission, les choix narratifs, la progression
et les sauvegardes appartiennent **exclusivement** au `GameSession` historique.
Le Player ne contient pas un second `Battle` et ne réimplémente pas les
formules de dégâts. Les opérations exploratoires et ennemies passent par R1
(`drawtemp.sdk.simulation.Simulation`) avec `expected_revision`.

## Sauvegarde et restauration

Les slots utilisent le format canonique `GameSession` version 1 : aucun
nouveau format R12. Les slots existants sont **vérifiés** avant leur écrasement.
Un écrasement d'un slot valide conserve `slot_N.json.bak` pour récupération
**explicite** via « Restaurer secours » au menu titre. En cas d'incompatibilité
de contenu, règles ou projet, le fichier d'origine n'est ni migré ni écrasé.
Ne pas effacer le backup sans confirmation utilisateur.

## Validation

```bash
python -m unittest tests_standalone.test_drawtemp5_r12 -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.player.qt_app --smoke
```

La CI dédiée valide le cycle narratif de la fixture R0, l'exploration
réelle de Domrémy, la non-mutation lors d'une action rejetée, les slots et
les restitutions, ainsi que le chargement du QML sous Windows, Ubuntu et macOS.
Le smoke **n'est pas** une certification de qualité GPU.

## Matrice de R12

| Lot | Statut dans cette PR |
|---|---|
| R12.1 Player Foundation | Entrée Qt Quick autonome + pont canonique initial |
| R12.2 Title & Main Menu | Menu, pause, nouvelle partie, charger, quitter ; animation artistique à compléter |
| R12.3 Campaign Flow | Intro, exploration, dialogue, combat et résultat fonctionnels ; gate end-to-end complète à certifier |
| R12.4 Exploration UX | Déplacements, interactions, isométrie et zoom initial ; caméra avancée à compléter |
| R12.5 Combat HUD | Objectif, CT, roster, PV, PM, compétences/objets ; UX avancée non certifiée |
| R12.6 Tactical Feedback | Prévisualisation exacte d'actions ; zones LOS/danger/télégraphies à intégrer |
| R12.7 Animation Controller | À faire avec les pistes R3/R4 |
| R12.8 Input & Keybinding | Commandes de base ; remappage persistant à faire |
| R12.9 Menus & Options | Contraste et échelle de texte ; options audio/graphique à faire |
| R12.10 Save Manager | Slots canoniques, reprise, sauvegarde de secours vérifiée ; UI conflits à enrichir |
| R12.11 Cinematic Runtime | À connecter à R11 |
| R12.12 Accessibility | Premier contraste/échelle ; navigation complète à auditer |
| R12.13 Combat Presentation | Figurines de repérage ; assets/FX/animations production à venir |
| R12.14 Player Polish | États de base ; test de sessions longues et interruptions à faire |
| R12.15 Controller Support | Hors première tranche, priorité P2 |

**Gate R12 reste ouverte** tant que le flux complet titre → Jeanne →
exploration → combat → victoire → résultat → sauvegarde → reprise n'a pas été
certifié en test intégré Qt réel, avec graphismes partagés finalisés.
