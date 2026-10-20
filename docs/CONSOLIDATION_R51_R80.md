# Consolidation R51–R80 — suivi d'intégration

> Branche provisoire pour regrouper les PR vers `master`. Ne constitue pas un GO produit.

## Pull requests à intégrer

- [ ] #413
- [ ] #414
- [ ] #415
- [ ] #416
- [ ] #417
- [ ] #418
- [ ] #419
- [ ] #420
- [ ] #421
- [ ] #422
- [ ] #423
- [ ] #424
- [ ] #425
- [ ] #426
- [ ] #427
- [ ] #428
- [ ] #429
- [ ] #430
- [ ] #431
- [ ] #432
- [ ] #433
- [ ] #434
- [ ] #435
- [ ] #436
- [ ] #437
- [ ] #438
- [ ] #439
- [ ] #440
- [ ] #441
- [ ] #442
- [ ] #443
- [ ] #444
- [ ] #445

## Ordre de dépendance

- #423 (R62.A) avant #444 (R62.B.1)
- #430 (R65.A) avant #442 (R65.B)
- #436 (R78.A), puis #439 (R78.B), puis #440 (R78.C)
- #438 (R79.A/C) avant #443 (R79.B)

## Précautions

- Préserver les modifications existantes de `master`; ne pas écraser les changements concurrents dans `drawtemp/studio/qt_shell.py`, `sporebound/game_project.py`, `sporebound/game_session.py`, `drawtemp/player/Main.qml`, `drawtemp/player/qt_app.py`, `drawtemp/sdk/simulation.py` et la roadmap.
- Regrouper dans cette branche uniquement; ne pas fusionner dans `master` avant tests et revue.
- À chaque PR intégrée, documenter le commit de fusion et mettre à jour la checklist; les PR non intégrées restent ouvertes.
- Aucune preuve de CI, de GPU physique ou de release GO n'est présumée.
