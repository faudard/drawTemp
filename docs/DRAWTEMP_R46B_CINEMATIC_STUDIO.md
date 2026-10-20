# DrawTemp R46.B1 — Cinematic Studio Pro : montage Qt multipiste

**Statut : implémentation de premier incrément R46.B en PR ; non certifiée.**

Dépendances : timeline canonique R11, CinematicDocument / AuthoringSession
(R1), prévisualisation unique Qt Quick Studio/Player. Ce sous-lot est
indépendant du nouveau ledger logique R46.A, toujours en PR #380.
L'objectif global R46.1–R46.10 reste celui de
[DRAWTEMP_8_1_TO_9_0_DETAILED_ROADMAP_R41_R50.md](DRAWTEMP_8_1_TO_9_0_DETAILED_ROADMAP_R41_R50.md).

## Fonctions développées

- **Zoom timeline** 50 %, 100 %, 200 %, 400 %, 800 % :
  `TimelineScale` projette les mêmes timestamps sur un espace horizontal
  de largeur variable ; des graduations adaptatives évitent une règle de
  180 secondes surchargée. Le zoom ne touche jamais au document.
- **Rognage de piste par poignée droite** : prévisualisation lors du geste
  puis appel asynchrone unique de `CinematicDocument.trim_event()` après
  relâchement, avec contrôle de révision. Les images-clés existantes sont
  recalées par les règles R11 ; les fondus audio incompatibles sont refusés,
  sans changement partiel et avec un seul pas Undo.
- **Scrub / playhead** : le positionnement horizontal utilise le même
  `TimelineScale` que l'affichage. Les modes lecture/pause R11 et le
  curseur audio existant ne sont pas recréés.
- **Sous-titres et pistes voix en lecture seule** : affichés depuis
  `CinematicStage.bridge.frame` et `audio_payload()` partagés avec le
  Player. Le texte reste l'événement `dialogue` canonique et la voix
  reste un `sound` du bus `voice` R11. Aucune nouvelle table de texte,
  locale parallèle ou média importé.

## Vérifications ajoutées

```bash
python -m unittest tests_standalone.test_drawtemp_r46b_cinematic_studio.R46BTimelineCoreTests -v
```

Le workflow `drawtemp-r46b-cinematic.yml` cible Linux, Windows et macOS
sur Python 3.12 pour les contrats headless, puis un smoke Qt Quick logiciel
sur Linux (option `DRAWTEMP_QT_GUI_SMOKE=1`). Les tests couvrent :

- invariance des timestamps selon le zoom et graduation longue durée ;
- rognage des keyframes, cycle Undo/Redo et rejet des révisions obsolètes ;
- limites de durée, fondu audio incompatible, échec sans mutation ;
- widget Qt, réglage de zoom, même frame Player/Studio, affichage du dialogue
  et identification de la voix sans side-effect.

## Gates encore requis

**R46.B2** : langage/localisation avec identifiants stables, référence média et
preuve de licence, édition avancée des plans/cadres, drag-test réel de poignée,
tests d'accessibilité/onscreen et QA de synchronisation audio réelle.

**R46.C** : branchements interactifs via StoryBook/GameSession, R46.A intégré,
seek/skip/reload atomique avec fault injection, cinématique de 90 secondes à deux
issues, Player packagé Windows/Linux/macOS, performances GPU réel et validation
humaine. Les jobs Qt software ne prouvent pas le rendu matériel ni la lecture
audio sur périphériques physiques.

Aucune release 8.6 ni gate R46 complet n'est déclarée.
