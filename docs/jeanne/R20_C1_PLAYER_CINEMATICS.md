# R20.C.1 — Cinématiques automatiques dans le Player Qt

## Comportement livré

Le Player QML `drawtemp.player.qt_app` affiche automatiquement les clips
validés avec `trigger = {"kind":"scene", "target": scene_id}` lorsqu'il
atteint la scène narrative. L'overlay s'appuie sur les **mêmes frames
calculées par `drawtemp.cinematics.projection.frame_payload`** que le
Studio/preview, et sur le `CinematicTransport` existant.

Sont intégrés : caméra 2D/zoom, acteurs (sprites s'ils sont liés), nom et
dialogue, fondus/transitions simples, lecture automatique, pause/reprise,
recherche temporelle et saut via Échap ou bouton. Le HUD tactique et
l'exploration sont derrière l'overlay, sans être modifiés par son rendu.

Le lecteur Tk historique et les projets sans clips restent inchangés.

## Authentification et sauvegarde

- Le **moteur** `GameSession.pending_scene_cinematic()` ne renvoie que
  le premier clip non acquitté de la scène **actuelle**. Aucun trigger
  `tactical_event` ou `before_mission` n'est usurpé.
- `GameSession.acknowledge_scene_cinematic(id)` refuse un mauvais ID,
  un clip déjà acquitté, une autre scène et tout appel sans clip actif.
  Son seul effet est un booléen `cine_<sha256-prefix>` dans
  `Campaign.story_flags`, avec un identifiant dérivé de la campagne,
  de la scène, du clip et du nombre de choix et missions déjà terminés.
- `Simulation.acknowledge_scene_cinematic` est
  **revision-checked, atomique, rollback-safe**, utilise les sauvegardes
  et digests ordinaires ; aucun nouveau format ni deuxième ledger.
- Le Player bloque les commandes de dialogue, exploration et entrée
  en combat tant qu'une cinématique est due. Il ne peut pas « sauter »
  le clip pour valider un choix narratif ou gagner une potion.
- En sauvegardant **avant** la fin d'un clip, une reprise en cours
  le relit depuis le début : le timecode est volontairement de
  la **présentation éphémère** et non du gameplay. Sauvegarder/après
  skip ou lecture complète enregistre l'acquittement ; ce clip **ne
  se rejoue pas** à la reprise, les suivants éventuels restent à voir.
- Les données `jeanne.json`, `jeanne.game.json`,
  `jeanne.r20b.game.json` et `jeanne.r20c.game.json` ne sont pas
  retouchées. Seuls les clips liés aux scènes du projet choisi
  s'affichent. L'absence de clip ne crée pas de nouveau drapeau.

## Tester

```bash
python -m unittest tests_standalone.test_r20c1_player_scene_cinematics -v
python -m unittest tests_standalone.test_r20c_jeanne_cinematics \
  tests_standalone.test_r20b_jeanne_playable \
  tests_standalone.test_jeanne_acte1 \
  tests_standalone.test_jeanne_prologue -v

# Player Qt R20.C (avec PySide6/Qt6)
python -m drawtemp.player.qt_app \
  --content sporebound/content/jeanne.json \
  --project sporebound/content/jeanne.r20c.game.json \
  --campaign jeanne
```

Tests nouveaux : entrée dans le vrai prologue, lecture/pause/seek sans
mutation du gameplay, blocage du mouvement et des choix pendant un clip,
acquittement authentifié exactement une fois, rejet de mauvais ID ou
révision, sauvegarde avant/après skip, retour via le PlayerSlots et
l'autosauvegarde, aucun nouveau flag pour le pack historique.

## Limites assumées

Ce lot crée un **rendu QML fonctionnel** dans le Player, sans affirmer
une parité artistique pixel-à-pixel avec `CinematicStage`. Les
effets graphiques complexes (particules FX, wipe), la spatialisation
audio, les portraits et le doublage nécessitent du matériel et des
assets sous licence. Le transport audio/FX de `CinematicStage` n'est
pas encore câblé dans cette fenêtre QML. Les triggers
`before_mission`, `after_mission` et `tactical_event` ne sont **pas**
pris en charge par cet overlay ; il n'affiche que `scene`.

Le [lot R20.D](R20_D_E2E_AND_DEMO_RELEASE.md) ajoute des parcours complets de la nouvelle partie jusqu'à Vaucouleurs, un smoke Qt offscreen et la préparation de démo. Les métriques GPU sur écran réel, les licences et la validation utilisateur complète restent nécessaires. Ne pas confondre CI verte (à confirmer) et
certification de livraison.
