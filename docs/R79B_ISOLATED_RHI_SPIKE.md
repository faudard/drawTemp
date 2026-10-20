# R79.B — Spike expérimental Qt Quick RHI (PC)

**Statut : recherche P2. Aucun GO matériel, backend imposé, Android/Web ou nouvelle plateforme distribuée.**

Dépendances : [R79.A/C](ADR_R79_FUTURE_PLATFORMS.md), R39 (package), R52 (viewport/picking partagé), R68 (plateformes alternatives), R76 (performance). R79 reste optionnel pour R80. Cette PR R79.B est empilée sur la branche de la PR #438.

## Architecture du spike

- Le parent stdlib lance **un unique sous-processus** Python borné (timeout, code de retour et diagnostics capturés), n'importe ni PySide6 ni le renderer, et ne modifie aucun réglage du Player.
- Le fils sélectionne `QQuickWindow.setGraphicsApi()` **avant sa première fenêtre Qt Quick**. Les variables `QSG_RHI_BACKEND` et `QT_QUICK_BACKEND` sont neutralisées **uniquement dans le fils**.
- Le fils ouvre le **renderer existant** `drawtemp.render.qt_viewport.create_view()`, la référence `drawtemp.sdk.reference.reference_project()`, `scene_from_mission()` et les projections **isometric** / **top_down**. Ni fork QML ni copie d'état métier.
- Après initialisation ou timeout, il observe `rendererInterface().graphicsApi()` (API effective), l'état QML/scenegraph, `frameSwapped`, trois centres de cellules via `RendererController.cellAt()` et une capture `grabWindow()` si disponible.
- Le parent valide le JSON et le **SHA256 du PNG**. Backend différent de celui demandé, backend inconnu, QML non prêt, absence de trame/capture ou picking incorrect => résultat `inconclusive`, sans retry automatique.
- Un résultat `status=observed` indique une **observation exploratoire locale**, pas un GPU prouvé ni un FPS mesuré. Le JSON conserve **toujours** `decision=NO-GO`, `release_certified=false`, `eligible_for_r79c=false`, `physical_gpu_verified=false`, `changes_player_defaults=false`.

## Essai manuel (machine équipée de Qt)

Utiliser **Python 3.12**, le Qt/PySide6 du projet et une session graphique réelle. Sur un clone correspondant à un **SHA complet vérifié** :

```sh
python -m pip install '.[qt6]'
python tools/r79_rhi_spike.py \
  --backend opengl \
  --projection isometric \
  --revision 0123456789abcdef0123456789abcdef01234567 \
  --output-dir ./r79b-opengl-iso
```

Remplacer le SHA d'exemple par le SHA réel. L'exécution crée un **nouveau dossier** contenant `spike-result.json` et, si réussie, `viewport.png` ; elle refuse d'écraser un dossier existant. Prévoir un autre dossier pour chaque essai. **Ne pas mélanger les rapports R79.B et le dossier d'attestations R79.C** : formats et niveaux de preuve distincts.

| OS | Backends possibles à *étudier* (aucune compatibilité présumée) |
|---|---|
| Windows | auto, d3d11, d3d12, vulkan, opengl, software |
| Linux | auto, vulkan, opengl, software |
| macOS | auto, metal, opengl, software |

`auto` conserve la sélection Qt sans imposer d'API. `software` n'est qu'un témoin diagnostique. `--projection top_down` utilise le viewport R3 alternatif. Le QPA `offscreen`, `minimal` ou `vnc` est refusé par défaut ; `--allow-headless` autorise un **diagnostic non certifiant**. Chaque invocation teste une seule API, dans un seul processus isolé ; aucun fallback implicite.

Code de retour : `0` = observation structurellement cohérente, **pas un GO** ; `1` = résultat inconclusif ; `2` = erreur d'arguments. Le timeout nominal est 5 s, borné entre 1 et 20 s avec une marge de supervision. **Une première trame observée ne constitue pas un benchmark p95/p99.**

## Gate : NO-GO produit

Pour envisager une décision humaine GO/REDUCE/NO-GO :

1. Essais sur GPU et appareils **physiques** Windows/Linux/macOS, avec GPU/pilote/version Qt/OS/SHA/DPI exacts et backend **réellement utilisé**.
2. Comparaison de la même scène dans Studio et Player, contrôles onscreen de picking, HUD, clavier/souris/manette et fallbacks.
3. R76 : corpus fixé à l'avance, performances p50/p95/p99, mémoire, démarrage, effets graphiques et stabilité; références CT/replay/saves intactes.
4. R39 : installation sur machine propre, packaging, provenance des binaires/asset manifests, droits, licences Qt/PySide et rollback.
5. Revue indépendante signée : coût de maintenance et compatibilité; le spike ne transforme jamais ses flags en attestations `physical_device=true` ou `checks=true`.

Le Player PC de production, ses sauvegardes/replays et les objectifs R80 ne dépendent **pas** de la réussite du spike.

## Tests headless

```sh
python -m unittest discover -s tests_standalone -p test_r79_rhi_spike.py -v
```

**11 contrats** couvrent sélection OS/API, sorties, schéma, isolation des variables, intégrité, erreur de QML, fallback, timeout, crash, refus headless et absence d'auto-GO. Les mocks **n'initialisent pas Qt**; seuls les essais manuels ci-dessus testent la création d'une fenêtre.

## Références

- [Qt 6.8 QQuickWindow::setGraphicsApi](https://doc.qt.io/qt-6.8/qquickwindow.html) : sélection avant la première fenêtre.
- [Qt for Python QSGRendererInterface](https://doc.qt.io/qtforpython-6/PySide6/QtQuick/QSGRendererInterface.html) : distinguer la demande et l'API effective du scenegraph.
