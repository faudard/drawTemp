# R68.B1 — Player tactile et suspension : spike isolé

**Statut (20 octobre 2026) : implémentation de prototype, NON certifiée Android/iOS/Web.** Ce lot ne fournit aucun APK/AAB, IPA, WASM, signature, binaire mobile ni preuve GPU. Il ne transforme pas R68.B ou R68.C en GO produit.

## Entrée et compatibilité

Le Player Qt Quick existant reste la seule surface d'exécution. Aucun second moteur, renderer, schéma de sauvegarde, tick, replay ou exporteur n'est ajouté. La nouveauté est l'adaptateur Python sans Qt `drawtemp.player.r68_touch`, branché dans `action_app.create_bridge`, plus un overlay Qt Quick en option. Le mode clavier PC par défaut conserve les mêmes commandes et le même accumulateur fixe R26.

Depuis un environnement **desktop Python 3.12** avec le Qt6 optionnel du projet :

```sh
python -m pip install -e '.[qt6]'
python -m drawtemp.player.action_app --touch-preview
python -m drawtemp.player.action_app --smoke --touch-preview
python -m unittest tests_standalone.test_r68_touch tests_standalone.test_action_player_r26b -v
```

Sous Windows, les guillemets du shell autour de `.[qt6]` peuvent être adaptés. Le smoke Qt hors écran est un test de chargement, **pas** une validation GPU physique.

## Contrats du prototype

- `MobileTouchOverlay.qml` : surface `MultiPointTouchArea` multipoints avec direction analogique simplifiée en -1/0/+1 et quatre actions (attaquer/parer maintenus, esquiver/interagir sur front montant); les coordonnées sont celles du viewport local et des zones fixes documentées par `_ACTION_CENTERS`.
- `TouchInput` refuse listes trop grandes, IDs dupliqués, NaN/Inf, records malformés, dimensions invalides; points déplacés hors viewport deviennent neutres. Les mises à jour validées ne touchent jamais au gameplay.
- `PortableActionDriver` reçoit clavier + tactile et appelle exclusivement `ActionPlayerController.step`, avec `ActionStepClock` entier à 60 Hz, max six ticks de rattrapage. Une impulsion esquive/interagir est conservée même lorsqu'un polling UI ne produit aucun tick.
- Le signal `QGuiApplication.applicationStateChanged` désactive le driver quand l'application n'est plus active; les touches, commandes différées et reliquats de temps sont effacés. À la reprise, pas de « 15 secondes de simulation » artificielles. La **pause manuelle n'est pas désactivée** par le système.
- La sauvegarde et le chargement utilisent encore `ActionRuntime.save/load` via le contrôleur R26; pas de nouveau fichier « mobile ». Le stockage `Path.home()/.drawtemp` actuel n'est **pas** un répertoire Android qualifié et reste à adapter avec tests de sandbox.
- La présence des boutons ne garantit ni cibles tactiles accessibles conformes aux standards ni gestion des encarts/safe areas sur appareil; ces obligations restent ouvertes.

## Plan d'essais sur matériel R68.B2 (non exécuté)

1. Valider la matrice exacte `Python/Qt6/PySide6/shiboken6/Android wheels/SDK/NDK`, la configuration `pyside6-android-deploy` et une installation APK sur deux **téléphones physiques** distincts. La version épinglée du dépôt (PySide6 6.8.3 pour Python 3.12) doit être vérifiée telle quelle, sans extrapoler d'une documentation plus récente.
2. Confirmer tactile **à deux doigts simultanés**, gestes de glissement, action maintenue, « tap » esquive avant tick, perte focus/app-switch, reprise après plusieurs minutes, fermeture forcée et récupération de la sauvegarde.
3. Mesurer sur version et SHA immuables : frame-time CPU/GPU p50/p95/p99, consommation mémoire, chauffe/batterie, chargement, taux de réussite d'installation, stabilité GPU, tailles/rotation, inputs externes et TalkBack.
4. Comparer `digest()`/replay avec le PC pour la même séquence de commandes, vérifier les chemins en stockage privé Android et conserver des preuves d'échec autant que de succès.
5. Vérifier SBOM/licences/droits de redistribution, surface d'attaque, permission de stockage et dépendances avant même une distribution de prévisualisation.

Aucun dossier d'évidence R68.A complet n'est produit par cette PR. Le statut de publication demeure **NO-GO** pour Android, iOS et Web, et le PC demeure la référence contractuelle.

## Limites explicites / non-objectifs

Ce lot ne porte pas le runtime sur Android ; il n'implémente pas les contrôles natifs Android, la protection contre des pertes de GPU réelles, la gestion d'orientation, VoiceOver, le packaging ou le stockage sandbox. Le prototype Web et le portage iOS restent des décisions indépendantes. R68.A (#420) doit être intégré ou réconcilié séparément ; les preuves de cette PR ne valent pas revue R68.C.

Références upstream :
- https://doc.qt.io/qtforpython-6.8/deployment/deployment-pyside6-android-deploy.html
- https://doc.qt.io/qt-6/qml-qtquick-multipointtoucharea.html
