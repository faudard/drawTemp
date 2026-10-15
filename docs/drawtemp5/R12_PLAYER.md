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
| R12.5 Combat HUD | Timeline CT moteur, roster PV/PM, sélection, compétences et objets, cible détaillée, prévisions ; portraits artistiques et UX avancée à compléter |
| R12.6 Tactical Feedback | Portées, cases accessibles, coûts, LOS, probabilités, dangers et réactions, sorts programmés et charges possibles projetés par R1 sur R3 ; polish à certifier |
| R12.7 Animation Controller | Clips événementiels de déplacement, attaque, dégâts, soins et interruptions sur R3 ; animation artistique et synchronisation sonore à compléter |
| R12.8 Input & Keybinding | Profils AZERTY/QWERTY persistants, remappage contextuel avec contrôle des conflits ; manette et variantes spécifiques à compléter |
| R12.9 Menus & Options | Options Qt persistantes : contraste, taille, plein écran, grille et hauteurs ; configuration audio à connecter à R11 |
| R12.10 Save Manager | Slots canoniques, reprise, sauvegarde de secours vérifiée ; UI conflits à enrichir |
| R12.11 Cinematic Runtime | À connecter à R11 |
| R12.12 Accessibility | Premier contraste/échelle ; navigation complète à auditer |
| R12.13 Combat Presentation | Figurines de repérage ; assets/FX/animations production à venir |
| R12.14 Player Polish | États de base ; test de sessions longues et interruptions à faire |
| R12.15 Controller Support | Hors première tranche, priorité P2 |

**Gate R12 reste ouverte** tant que le flux complet titre → Jeanne →
exploration → combat → victoire → résultat → sauvegarde → reprise n'a pas été
certifié en test intégré Qt réel, avec graphismes partagés finalisés.

### Viewport partagé R3 (PR #237)

Le Player n'a plus son moteur Canvas QML. `TacticalBoard.qml` conserve les propriétés `battle`, `exploration`, `selected` et le signal `cellSelected`, tout en déléguant entièrement le rendu et le picking à `IsoViewport.qml`. `scene_for_player` projette la bataille via `scene_from_mission` ou l'exploration via `scene_from_exploration`, exclusivement depuis la session R1. Le zoom/pan et les textures sont les mêmes que dans l'éditeur R5. Les futures intégrations de sprites/animations et les performances GPU sont à certifier séparément.

### R12.8–R12.9 — Commandes et préférences (tranche suivante)

Le Player conserve désormais ses réglages **indépendamment** des checkpoints
`GameSession`, dans `~/.drawtemp/player5/jeanne/player-preferences.json`
(`--save-dir` permet de choisir un autre profil local). Le document est
versionné (`version: 1`) et remplacé atomiquement. Les fichiers corrompus ou
de version inconnue ne sont jamais migrés silencieusement : chargement des
valeurs par défaut en mémoire et préservation du fichier brut dans
`player-preferences.json.invalid` lors de la première modification explicite.

#### Commandes

| Action | AZERTY | QWERTY | Portée |
|---|---|---|---|
| Explorer haut / gauche / bas / droite | Z / Q / S / D | W / A / S / D | Exploration |
| Sélection tactique | Flèches | Flèches | Combat |
| Déplacer / attaquer / terminer | M / A / Espace | M / A / Espace | Combat |
| Sauvegarde / pause | F5 / Échap | F5 / Échap | Global (hors titre) |

Le menu **Options** comporte un sélecteur AZERTY/QWERTY et un sélecteur de
touche pour chacune des commandes. Chaque profil conserve ses propres
personnalisations. Les flèches directionnelles restent accessibles pour
déplacement/sélection même après personnalisation. Un même raccourci ne peut
pas être affecté deux fois au sein du même contexte ou entre une commande
globale et une commande contextuelle. En cas de collision, aucune modification
n'est sauvegardée ; le joueur voit l'erreur dans Options. Le bouton
« Réinitialiser les touches » restaure le profil actif uniquement.

Les raccourcis passent par des `Shortcut` Qt de portée fenêtre,
automatiquement désactivés pendant les popups, pour ne pas capturer les
flèches/lettres d'un champ d'options. Aucune règle tactique ni revision de
simulation n'est modifiée par un réglage.

#### Affichage et accessibilité

Les réglages taille des textes (85–135 %), contraste, plein écran,
quadrillage et affichage des hauteurs sont maintenant persistants.
Le quadrillage/les hauteurs utilisent directement les options du viewport
partagé R3. La configuration des volumes ne sera ajoutée qu'avec un runtime
audio réellement raccordé (R11), pour éviter des curseurs factices.

#### Validation ciblée

```bash
python -m unittest tests_standalone.test_drawtemp5_r12_preferences -v
python -m unittest tests_standalone.test_drawtemp5_r12 -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.player.qt_app --smoke --smoke-scene exploration
```

Le smoke Qt ne remplace pas la validation manuelle d'une session longue et
du rendu GPU. Le **Gate R12 demeure ouvert**.

### R12.5–R12.6 — HUD et projection tactique autoritative

La nouvelle API `Simulation.tactical_presentation(cell, skill_id,
expected_revision=...)` expose exclusivement une projection **immuable et
détachée** calculée à partir du `Battle` canonique. Elle se fonde sur :

- `sporebound.presentation.battle_frame` et `combat_hud` pour les PV/PM,
  objectifs, roster, sélection, CT estimé et avertissements ;
- `Battle.reachable` pour les cases accessibles, chemins et coûts ;
- `Battle.movement_threats` pour les réactions et engagements possibles
  sur un chemin (elles peuvent ne pas se déclencher) ;
- `Battle.forecast` et `Battle.line_of_sight` pour la visibilité et
  les effets probabilistes d'une compétence sélectionnée ;
- `sporebound.tactical_intents` pour les zones de terrain dangereux,
  réactions armées, sorts programmés et charges seulement *possibles*.

La projection ne consomme aucun tirage RNG : elle copie le combat avant les
requêtes et renvoie sa révision source pour rejeter les affichages périmés.
Les chances d'impact/quantités sont des **prévisions**, non des résultats
garantis et la timeline CT suppose les vitesses inchangées. Il n'y a ni
simulation cachée du futur comportement IA ni formule tactique réinventée
dans le QML.

Le composant `TacticalBoard.qml` continue d'étendre le viewport partagé
`IsoViewport.qml` de R3. Ses losanges de portées/dangers utilisent la
projection caméra/hauteur identique au terrain existant ; ils ne capturent
aucune entrée souris. Les charges hypothétiques sont en pointillés.
`Main.qml` présente la prévision de la compétence inspectée, les chances,
le LOS, le risque du chemin, les tours CT, charges et sorts programmés.
Un bouton permet de masquer les surcouches.

Tests headless : `tests_standalone.test_drawtemp5_r12_tactical` vérifie
l'immutabilité/revision, la parité avec le moteur, la pureté des prévisions,
les erreurs de sélection, le mouvement et un parcours de référence
**combat → victoire → sauvegarde → reprise → campagne**. Ce dernier test
utilise la politique IA canonique comme pilote de test, jamais comme
automatisme du Player livré au joueur.

```bash
python -m unittest tests_standalone.test_drawtemp5_r12_tactical -v
```

Le test moteur ne clôt pas encore le gate de jeu GUI réel. R12.7
(animation), les portraits/sprites de production et le rendu artistique
restent des axes ouverts.

### R12.7 — Contrôleur d'animation événementiel (octobre 2026)

Le Player Qt Quick utilise désormais un seul `AnimationDirector` headless,
`drawtemp.player.animation_controller`, avec des clips construits à partir des
**événements effectivement commis** dans la journalisation du moteur. Les
événements ne sont pas réécrits et les clips ne sont pas inclus dans le format
de sauvegarde.

- **Déplacement** : interpolation de l'acteur entre les positions
  `start`/`end` validées par l'événement `move` du combat ;
  aucune route intermédiaire n'est inventée si le journal ne la fournit pas.
- **Attaque** : amorce visuelle vers la case ciblée à l'événement `skill`,
  distincte du dégât réellement résolu.
- **Impact / soin** : bulle animée et quantité **uniquement** après
  l'émission des événements `damage` ou `heal`. Une esquive ne peut pas
  provoquer de faux nombre de dégâts.
- **Interruption** : indicateur distinct pour
  `charge_interrupted`, `cast_failed` et `prepared_cancelled`.
- **Timing** : chaque clip dure 200–380 ms et n'a aucun effet sur
  l'ordonnancement CT, le gameplay, les chances de toucher ou le RNG.
- **Annulation** : série de génération croissante ; toute nouvelle action
  commise, nouveau jeu, chargement, restauration, changement de campagne ou
  retour au titre invalide instantanément les clips précédents.
  La sélection de case n'interrompt pas le mouvement en cours.
- **Limites de sécurité** : pas plus de 100 événements incrémentaux
  transformés par transition, 80 clips maximum, préfixe du journal et
  révision strictement vérifiés. Aucun ancien événement n'est rejoué au
  chargement d'une sauvegarde.
- **Renderer partagé** : `TacticalBoard.qml` anime un avatar/effet visuel sur
  la même projection isométrique et caméra que `IsoViewport.qml` (R3).
  Le renderer ne masque la figurine statique que pendant le mouvement/attaque
  correspondant. Le Studio n'anime rien par défaut.

Les mouvements sont actuellement interpolés entre les **positions
vérifiées** ; le journal moteur ne fournit pas encore toutes les étapes
du chemin pour les déplacements à virages. La résolution exacte des trajectoires,
les sprite sheets artistiques de R4/R7, les VFX définitifs et l'audio
synchrone R11 restent à certifier. Aucun faux asset d'animation de production
n'est revendiqué.

#### Tests de R12.7

```bash
python -m unittest tests_standalone.test_drawtemp5_r12_animation -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
    python -m drawtemp.player.qt_app --reference --smoke --smoke-scene battle
```

Cette suite couvre les journaux incrémentaux, l'ordre
move → skill → damage/heal, les esquives, les interruptions, la limite de
clips, l'annulation sur nouvelle génération, l'isolation du gameplay et la
sauvegarde/reprise. Le smoke Qt charge le QML, **sans certifier** la fluidité
ni la synchronisation audiovisuelle du Player réel.
