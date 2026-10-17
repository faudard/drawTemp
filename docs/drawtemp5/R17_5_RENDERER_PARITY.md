# R17.5 — Équivalence du rendu entre Studio R5 et Player R12

## Objet du contrôle

Comparer **les vrais renderers R3** utilisés par les deux applications et
leurs deux façades QML réelles, sur la *même* mission Jeanne à caméra constante.

- **Contrat headless** : `scene_visual_payload` exige les données visuelles
  canoniques (tiles, élévations, collisions, objets, personnages, structures,
  intérieurs) et écarte uniquement la **révision R1** (non graphique).
- **Contrôleurs Qt** : `compare_controller_pair` inspecte directement
  `RendererController.items`, `displayItems`, `tileBatches`,
  `cameraState`, choix du terrain/picking `cellAt` sur les mêmes cellules.
  Les lignes conservent `zOrder`, atlas/pivots, relief, faces et couleurs ;
  ni le tri ni les frames ne sont « normalisés » artificiellement.
- **Caméra** : balayage à 60 %, 100 %, 175 %, 240 % de zoom, même centre,
  viewport 850×580, cellules sur terrain ordinaire et sur élévation.
- **Régression négative** : modifier l'altitude d'une case **doit**
  déclencher un diagnostic de désaccord des scènes et des délégués.
- **GUI réelle** : `MapWindow` R5 et `TacticalBoard.qml` R12, via
  `QQuickWidget`, avec la même scène issue de `reference_project`, viewport
  720×480, caméra identique. Désactivation uniquement de l'overlay
  **spécifique au joueur**, les deux composants QML de production subsistent.
  Les frames software Qt sont comparées avec `compare_png` et un diff
  PNG est produit. Tolérances explicites : 12 canaux, 1 % des pixels.
- **Traçabilité** : `parity.json`, `studio.png`, `player.png`,
  `studio-player-diff.png` sont publiés en artefacts Windows, Linux, macOS.
  Une CI capture n'est jamais copiée automatiquement dans un dossier
  `goldens` approuvé.

## Exécution

```sh
python -m unittest tests_standalone.test_r17_renderer_parity.RendererParityContracts -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  DRAWTEMP_R17_PARITY_DIR=artifacts/r17-parity \
  python -m unittest tests_standalone.test_r17_renderer_parity -v
```

## Gate de sortie

Une divergence des champs, de la caméra, des délégués triés, du picking,
du framebuffer ou un fichier absent **échoue**. Le mode logiciel peut
démontrer une divergence et aider à la corriger, pas donner une preuve
de qualité artistique ni de rendu GPU hardware. **R17.5 reste ouvert**
pour les captures approuvées par revue humaine, les systèmes multi-DPI,
et une épreuve physique GPU avec R17.9.

À combiner avec [R17.8 — export natif](R17_8_ISOLATED_NATIVE_EXPORT.md)
et [R17.D — Studio → Player](R17D_STUDIO_PLAYER_E2E.md) une fois leurs PR
intégrées à `master`.
