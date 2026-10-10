# 2.6 — Player & Presentation

## Lancer et sauvegarder

```sh
python -m sporebound player
python -m sporebound player --content data/custom.json --project data/custom.game.json
python -m unittest discover -s tests_standalone -v
```

L'application utilise Tk/Tcl (sous Ubuntu : `python3-tk`).
L'option `--profile` choisit le **chemin de base** des sauvegardes.
Chaque campagne/slot dispose de son propre `*_session_saves/<campaign>/slot_N.json`
et de son éventuel `.bak`. La progression tactique en cours, les événements
narratifs et la timeline multi-fronts sont conservés via le journal rejouable
`GameSession` / `SessionStore` de 2.4. Les slots historiques
`*_saves/.../slot_N.json` de `PlayerSession` ne sont jamais écrasés.
Créer une nouvelle partie dans un slot existant demande une confirmation ;
le checkpoint précédent vérifié devient copie de secours.

## Parcours joueur

Écran titre → choix campagne/slot → intro narrative facultative → mission
→ déploiement éventuel → CT/combat → résultat → campagne/choix narratif.
Commandes disponibles dans l'interface : déplacement, attaque, compétences,
objets, interactions, armes de siège, fin de tour, activation IA.
Le bouton **Sauvegarder** et les sauvegardes après commandes réussies
fonctionnent sans terminal ni Studio. Un ordre refusé ne modifie pas la session
et ne publie pas de nouveau checkpoint.

Lorsque deux missions **débloquées** sont disponibles, l'écran campagne
permet de créer une session multi-fronts. La timeline affiche forces,
opposition, doctrines, focus et journal ; changer de front et avancer la
timeline passent par les APIs du moteur. La progression du front non suivi
reste décidée exclusivement par `MultiFrontSession`.

## Contrat architecture

- `presentation.py` fournit `BattleFrame`, `StrategyFrame` et `Camera` :
  snapshots en lecture seule ; déplacements possibles et prévisions viennent
  de `Battle.reachable` et `Battle.forecast`, jamais du renderer.
- `player_controller.py` exécute toutes les commandes dans `GameSession`,
  déclenche les décisions IA par `choose_command` puis `execute`,
  et écrit des checkpoints via `SessionStore`.
- `tk_renderer.py` dessine uniquement une scène : tiles, relief simplifié,
  objets, unités multicases, barres PV, zone accessible et sélection.
  Le zoom est ancré au pointeur et le bouton central déplace la caméra.
- `audio_stage.py` consomme les événements sans toucher aux règles.
  Les bindings `sound` sont facultatifs : `title`, `campaign`, `battle`
  pour les ambiances, ou directement un `event.kind` tel que
  `battle_end` et `activation`.
- Le registre `assets` d'un `*.game.json` peut lier des sprites au
  `unit.id` ou `unit.team`, et des portraits au nom de l'intervenant.
  Le rendu graphique basique/silencieux reste fonctionnel sans fichiers.

## Comparatif du rendu

| Option | Atouts | Coûts / limites | Position |
|---|---|---|---|
| Tk Canvas (déjà installé pour le Studio) | Python standard, faible maintenance, idéal pour MVP | Animation et volumes de sprites limités | Backend livré dans 2.6 |
| pygame-ce | Blit/audio/animation et plein écran optimisés | Dépendance/packaging externe, outils Widgets moins riches | Audio facultatif ; renderer futur |
| PySide6 | Desktop adaptatif, widgets et haut DPI | Wheels Qt6 volumineuses, app Qt complète distincte | Alternative à évaluer après le vertical slice |

Le moteur reste **sans dépendance de rendu**. Ajouter un backend ne doit pas
modifier les données de campagne, les règles ni les replays.

## Limites explicites de cette itération

Les cinématiques riches (vidéo, transitions multi-plans, lip-sync),
spritesheets directionnelles, effets particulaires et menus conçus dans
le Studio ne sont pas encore interprétés par le player.
Les dialogues typographiés, portraits et cues audio couvrent une première
présentation. L'éditeur visuel des assets/scènes relève de 2.5.
Les joueurs de 2.6 ne chargent pas automatiquement les anciens slots v1 :
la migration doit rester une opération explicite.
