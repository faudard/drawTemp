# R17 — Réintégration de #286, #287 et #288 sur master

**Base :** `500b1cb04adb594d1c41882e375d7838ee7e8efb` (19 octobre 2026). Cette branche applique successivement les patches de #286, #287 et #288 à `master`, en préservant les modifications déjà intégrées au tronc.

## Problème de provenance

- #285 (R17 consolidé) a été fusionnée vers `master`.
- #286 (R17.6 droits assets) et #287 (R17.7 sauvegardes) ont été fermées **sans fusion vers master**.
- #288 (R17.11 UX de récupération) a été fusionnée **dans #287**, pas vers `master`.
- #289 est une roadmap multi-genres R25–R30 ; elle ne remplace aucun gate R17.

## Code réintégré et gardes

| PR | Contrat | Tests |
|---|---|---|
| #286 | Release strictement refusée si droit, SHA-256, preuve documentaire ou redistribution manque ; preview séparée. | `test_r17_asset_rights` et R15 |
| #287 | Jamais de downgrade silencieux d'un checkpoint sain ; reprise idempotente après échec, conflit externe détecté. | `test_r17_persistence_recovery` et R1/R12 |
| #288 | Backup réellement vérifié seulement, confirmation modale, hashes primaire+secours contrôlés sous verrou avant restauration, messages et reset animation. | `test_r17_recovery_ux`, `test_r17_recovery_ux_qt` |

Les trois suites tournent **ensemble** sur Linux, Windows et macOS dans le workflow `drawtemp-r17-reintegration.yml`; les workflows spécialisés restent actifs. Le patch a été appliqué sans conflit textuel ; **aucun test n'a été exécuté localement**. La CI doit valider le nouveau SHA avant fusion.

```sh
python -m pip install .
python -m unittest -v tests_standalone.test_r17_asset_rights tests_standalone.test_r17_persistence_recovery tests_standalone.test_r17_recovery_ux tests_standalone.test_drawtemp5_r1d tests_standalone.test_drawtemp5_r1e tests_standalone.test_drawtemp5_r12_save_manager tests_standalone.test_drawtemp5_r15 tests_standalone.test_drawtemp5_r15_creator
python -m pip install '.[qt6]'
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest -v tests_standalone.test_r17_recovery_ux_qt tests_standalone.test_drawtemp5_r12_save_manager_qt
```

## Non certifié / suite R17

Les pièces de droits **réelles**, signatures, goldens humains, tests GPU physiques (R17.9), session transactionnelle multi-ateliers (R17.4), rollback legacy (R17.10), erreurs Studio et publication (fin R17.11), E2E complet R17.12 et dossier de release R17.13 restent à prouver. Ne pas attribuer le statut « 5.0 certifié » à ce lot ni aux fixtures synthétiques.
