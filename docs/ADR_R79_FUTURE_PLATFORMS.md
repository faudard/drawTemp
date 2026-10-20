# ADR R79.A/C — Future Platforms & Rendering Research

**Statut au 20/10/2026 : étude, NO-GO pour tout nouveau support produit ou activation forcée de backend.** Aucune certification matériel, licence ou release induite par cette PR. Ce lot est optionnel pour R80.

## Décision

Conserver le Player PC, son moteur **2D/2.5D**, le renderer Qt Quick R3 partagé, le picking R52, le Core headless CT/tick fixe et les save/replays historiques. **Ne pas créer de second renderer, ne pas forcer une nouvelle API graphique par défaut, ne pas rendre le PC dépendant de Web/mobile.**

R79.A formalise les variantes/risques et un protocole de preuve; R79.C fournit le rapport de décision reproductible. R79.B est un spike P2 **non activé**, limité à une branche de recherche après revue séparée. Les dépendances R39 (packaging), R52 (rendu/picking), R68 (Web/mobile) et R76 (performance/qualité) doivent être attestées sur `master`, pas simplement supposées d'après les titres des PR.

## Matrice de faisabilité (hypothèses, aucun benchmark mesuré)

| Candidat | OS / API étudiés | Risques majeurs | Packaging / licence | Maintenance prévisionnelle qualitative | Décision initiale |
|---|---|---|---|---|---|
| `qtquick-rhi-adaptive` | Windows: D3D11/12, Vulkan, OpenGL; Linux: Vulkan/OpenGL; macOS: Metal/OpenGL (disponibilité par version/appareil à tester) | Divergences shader, picking/HUD, DPI, pilotes, fallback | Exports R39, Qt/PySide, dépendances natives, SBOM | Moyenne; support OS × drivers × matériels | **NO-GO** pour forçage de backend; recherche PC prioritaire |
| `android-touch` | Android: Vulkan/OpenGL selon configuration | Input tactile, cycle de vie, pause/reprise, sauvegarde, performances réelles | APK/AAB, chaîne Qt/PySide, droits et obligations licences | Élevée; appareils/OS/packaging | **NO-GO**, attendre la décision R68 |
| `web-wasm` | Navigateurs et WebGL; WebGPU seulement si runtime réellement compatible | Qt WebAssembly n'implique **pas** que le Player Python/PySide6 soit portable; threads/sandbox/stockage | Emscripten, modules, hébergement, contraintes licence/static linking | Très élevée et incertaine | **NO-GO**, attendre la décision R68 |
| iOS / consoles / moteur 3D généraliste | Aucune cible engagée | SDK/distribution/contrôles non étudiés | Coûts et obligations inconnus | Non chiffrée | **Hors périmètre / NO-GO** |

Ces coûts sont **des hypothèses**, pas des heures mesurées. L'outil R79 recueille un coût explicite `maintenance_hours_per_quarter` et une justification `cost_basis` par plateforme. L'acceptabilité du budget reste une décision humaine.

## Contrat d'évidence R79.C

Programme **stdlib/headless** : `tools/r79_platform_gate.py`. Il ne détecte pas de GPU, ne démarre pas Qt, ne modifie pas le Player et ne télécharge rien.

```sh
python tools/r79_platform_gate.py \
  --candidate qtquick-rhi-adaptive \
  --revision 0123456789abcdef0123456789abcdef01234567 \
  --evidence-root ./evidence-r79 \
  --output ./r79-report.json
```

Placer `--output` **hors** du dossier `--evidence-root`. Le mode `--require-review-ready` renvoie un code de sortie 1 tant que les préconditions de **revue** ne sont pas réunies, sans prétendre effectuer une certification.

Chaque fichier `*.json` du dossier `evidence-r79` décrit une seule plateforme (schéma **1** à clés exactes) :

```json
{
  "schema": 1,
  "candidate": "qtquick-rhi-adaptive",
  "revision": "0123456789abcdef0123456789abcdef01234567",
  "platform": "linux",
  "renderer_backend": "vulkan",
  "physical_device": true,
  "device_id": "machine-du-laboratoire",
  "os_version": "version-exacte",
  "qt_version": "version-exacte",
  "driver_version": "version-exacte",
  "benchmarks": {
    "frame_ms": [15.1, 16.0, 16.2],
    "cold_start_ms": 900,
    "peak_memory_mib": 256
  },
  "checks": {
    "picking": true,
    "studio_player_parity": true,
    "save_replay": true,
    "input": true,
    "packaging": true,
    "license_review": true,
    "rollback": true
  },
  "maintenance_hours_per_quarter": 20,
  "cost_basis": "hypothèses, propriétaire et protocole de collecte documentés",
  "artifacts": [{"path": "linux-trace.log", "sha256": "<hash réel>"}]
}
```

**L'exemple est volontairement incomplet :** les `frame_ms` exigent entre **30 et 10 000 échantillons** positifs et finis, un SHA256 réel pour chaque artefact, et le fichier réellement présent. Les chemins doivent être de simples noms de fichiers locaux ; symlinks, hashes invalides, duplications, fichiers surdimensionnés, révisions incohérentes, flags `false`, backends non prévus, mesures non finies et plateformes manquantes provoquent un blocage de la revue.

La matrice PC demande une déclaration pour **Windows, Linux et macOS sur le même SHA**. Pour Android et Web, la matrice instrumentale est distincte et ne remplace jamais le gate R68. Le rapport contient les SHA256 des manifestes, les valeurs p50/p95/p99 frame-time (*nearest rank*), mémoire maximale, démarrage à froid et coût déclaré.

**Limite critique :** `physical_device=true`, `license_review=true` et les autres attestations sont *auto-déclarés*. Le contrôle ne prouve ni origine GPU physique, ni intégrité d'un binaire exécuté, ni provenance signée, ni conformité légale, ni seuils de performance. Même si `review_ready=true`, la sortie est **toujours `decision: NO-GO` et `release_certified: false`**. Une ADR signée, la validation indépendante des artefacts, l'audit juridique et les tests hardware sont nécessaires pour changer cette décision.

## Protocole de qualification / prochain GO ou REDUCE

1. Figer SHA, version Qt/PySide, OS, GPU, pilote, jeu/scène/seed, backend **effectivement observé** (pas seulement demandé), profil caméra, paquet et historique R39/R52.
2. Sur matériel physique, lancer Studio et Player pour les mêmes fixtures, saisir logs GPU et captures; répéter p50/p95/p99, démarrage/mémoire, picking, transitions, CT/replay, input tactile/clavier/manette, pause/reprise si applicable.
3. Contrôler export, cold-install, mises à jour/rollback, accessibilité, origine/licences des assets et Qt, provenance hashes, protocole de signature des preuves.
4. Définir **avant l'évaluation** les budgets et le corpus R76, comparer qualité et performance au renderer de production, chiffrer le coût de support OS/drivers/trimestre. Aucun seuil universel de FPS n'est considéré comme mesuré ici.
5. Rédiger un **GO / REDUCE / NO-GO humain par cible**, avec reviewer identifié, sources et limites ; seulement après GO ouvrir un spike R79.B indépendant. Le PC reste cible garantie et R80 n'est pas suspendu à l'étude R79.

**État actuel : R79.A contrat/matrice proposés dans cette PR; R79.C contrôles de preuves proposés; R79.B non démarré; aucun dossier matériel certifié et aucun GO.**

## Références

- [Qt Quick Scene Graph Adaptations](https://doc.qt.io/qt-6/qtquick-visualcanvas-adaptations.html) et [QQuickWindow](https://doc.qt.io/qt-6.8/qquickwindow.html) : RHI, choix du backend **avant** la première fenêtre.
- [Qt for WebAssembly](https://doc.qt.io/qt-6/wasm.html) : limites modules, navigateur, thread et distribution.
- [Qt Android deployment](https://doc.qt.io/qt-6/deployment-android.html) : formats APK/AAB/AAR.
- [Qt Licensing](https://doc.qt.io/qt-6/licensing.html), [Qt LGPL/GPL obligations](https://www.qt.io/development/open-source-lgpl-obligations) : audit de conformité par module/cible, sans avis juridique.
- Internes : [R39](R39_PUBLISHING.md), [R52](ADR_R52A_SHARED_DEPTH_PIPELINE.md), [roadmap R51–R80](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md).

## Vérification locale

```sh
python -m unittest discover -s tests_standalone -p test_r79_platform_gate.py -v
```

Les **9 tests utilisent des fixtures synthétiques** et ne certifient ni GPU, ni OS, ni compatibilité Web/Android. La CI R79 est strictement un contrôle de contrat headless sur trois OS et deux versions Python.
