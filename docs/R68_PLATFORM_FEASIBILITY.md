# R68.A — Alternative Platform Feasibility : dossier de cadrage

**Statut au 20 octobre 2026 : étude P0 en cours.** Aucun Player Web, Android ou iOS n'est certifié, disponible ou exportable via R39. PC Windows/Linux/macOS reste la seule cible de publication prévue. La présence d'outils upstream ne démontre pas la compatibilité DrawTemp.

## État des sources réellement inspectées

- `pyproject.toml` : Python >=3.10 et extra Qt6 conditionné à Python 3.12, `PySide6==6.8.3`. La documentation Qt plus récente ne prouve pas que cet environnement épinglé déploie sur mobile.
- `drawtemp/player/qt_app.py` : Player Qt Quick, pilotage Python, chemins de sauvegarde `Path.home()/.drawtemp`. Les ressources locales et le stockage doivent être adaptés aux sandbox OS.
- `drawtemp/player/action_app.py` : démo Qt Quick `QQmlApplicationEngine`, tick 60 Hz et raccourcis clavier; ni tactile, ni cycle de vie mobile prouvés.
- `drawtemp/export/publication_matrix.py` et `docs/R39_PUBLISHING.md` : publication PC uniquement, Web/mobile refusés. R39 ne doit pas être assoupli par R68.A.
- Dépendances R39/R57/R59/R60 : considérer les gates comme non certifiés tant qu'un artefact final de chaque gate n'est pas vérifié sur `master`.

## Matrice de risque et d'évidence

| Axe | Android | iOS | Navigateur Web |
|---|---|---|---|
| Runtime | PySide6 Android + CPython embarqué, **spike à réaliser** | PySide6 iOS + Python.xcframework + Xcode, **spike à réaliser** | Qt/WASM C++ existe, mais aucun chemin PySide6/WASM DrawTemp qualifié |
| Qt/distribution | `pyside6-android-deploy`, roues cibles, SDK/NDK, signature APK/AAB | `pyside6-ios-deploy`, roue iOS, linkage statique, codesign/provisioning | Emscripten + WebGL et navigateur; Python/Qt bridge à démontrer, ne pas supposer portable |
| Bundle/assets | Droits, inventaire, taille et démarrage à froid inconnus | Ressources intégrées + règles App Store et signatures inconnues | Téléchargement, offline, taille et politiques CSP/COOP/COEP à mesurer |
| Sauvegarde | Répertoire privé app, permissions, import/export explicites | Conteneur app + protection données, backup/reprise | IndexedDB/OPFS et quotas/effacement; pas de filesystem POSIX garanti |
| Cycle de vie | Pause/background, perte de contexte GPU, reprise sans double tick | Suspend/resume, destruction processus, restauration | `visibilitychange`, onglet suspendu, throttling, perte WebGL |
| Entrée/a11y | Tactile, gestes, manette, TalkBack, tailles cibles | Tactile, manette, VoiceOver, safe areas | Clavier/tactile, lecteurs d'écran, focus et fullscreen |
| Performance | FPS p50/p95/p99, RAM, chauffe, batterie, GPU réels | Idem, plusieurs générations de devices | WebGL, mémoire navigateur, bande passante, compilation initiale |
| Licences/coûts | Qt/PySide, SDK et inventaire tiers, store, maintenance | **Linkage statique** Qt/PySide à auditer juridiquement; Apple Developer Program, App Review | Qt/WASM, distribution des ressources, sécurité et hébergement |
| Preuve exigée | APK/AAB, installation + jeu/sauvegarde/reprise sur téléphone physique | Xcode build signé, installation + jeu/sauvegarde/reprise sur iPhone/iPad physique | Build reproductible, navigateur réel sur matériel documenté, jeu/reprise/stockage |
| Décision initiale | NO-GO produit; spike Android conditionnel | NO-GO produit; spike iOS conditionnel et juridique | NO-GO produit; étude runtime Python/WASM préalable |

Les cases « outil existant » signifient seulement **faisabilité technique potentielle**, pas fonctionnement du Player DrawTemp.

## Outil d'inventaire reproductible

```sh
python -m drawtemp.quality.r68_feasibility --root . > r68-baseline.json
python -m unittest tests_standalone.test_r68_feasibility -v
```

L'inventaire calcule des SHA-256 des fichiers clés et émet une décision `NO-GO` par cible tant que les preuves manquent. Des dossiers externes peuvent être confrontés à un SHA Git exact :

```sh
python -m drawtemp.quality.r68_feasibility --root . \
  --revision <sha-git-40-caracteres> --evidence chemin/android/evidence.json
```

Chaque preuve doit définir `schema: 1`, `kind: drawtemp-r68-probe-evidence`, `revision`, `target`, `environment` et `checks`. Chaque check doit contenir `status: passed`, `artifact` relatif sans traversée/symlink et `sha256` du fichier (max 4 Mio). Android/iOS requièrent `physical-device`, Web `real-browser-on-physical-hardware`. Le contrôle ne prouve **pas** qu'une attestation est vraie : il ne vérifie que sa forme, sa cohérence et l'intégrité des fichiers déclarés. Un dossier complet reste `MANUAL_REVIEW_REQUIRED`, jamais un GO automatique ni une certification de release.

## Plan R68.B : spike non bloquant et indépendant

1. **Android d'abord, uniquement après revue de la version Qt/PySide/CPython :** Player tactique minimal, scène/déplacement/touch, pause/reprise, sauvegarde R1, APK/AAB, deux téléphones physiques de profils GPU différents.
2. **iOS séparément :** macOS/Xcode, roues iOS concordantes, build/signature, appareil physique et analyse de conformité statique LGPL/GPL/commercial. Ne pas réutiliser un résultat Android pour iOS.
3. **Web après arbitrage du runtime :** prototype WASM ou route alternative explicitement architecturée, sans second moteur gameplay silencieux. Preuves de replay déterministe, stockage, browser reload, input et rendu GPU.
4. Collecter SHA source, versions toolchains, hash des bundles, vidéo/parcours reproduisible, CPU/GPU/RAM/fps, a11y, droits et coûts, résultats négatifs inclus. Mesures et résultats encore **absents** à R68.A.

## R68.C : décision, non prévue dans ce lot

**GO** exige build vérifié, équipement réel, saves/replays intègres, coût et maintenance acceptés, décision explicite indépendante et preuve légale. **REDUCE** limite le périmètre (par exemple prototype local non publié). **NO-GO** conserve toutes les plateformes alternatives hors du périmètre de release. Chaque cible a son propre ADR/GO ; aucune généralisation Web↔mobile. PC, R39 et sauvegardes historiques sont inchangés.

## Sources techniques externes (consultées le 20/10/2026)

- Qt for Python : Android — https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-android-deploy.html
- Qt for Python : iOS — https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-ios-deploy.html
- Qt for WebAssembly — https://doc.qt.io/qt-6/wasm.html
- Qt : Obligations LGPL/GPL — https://www.qt.io/development/open-source-lgpl-obligations
