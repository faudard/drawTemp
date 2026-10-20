# R76.A — Asset & Build Optimization: auditeur headless (11.6)

**Statut : PR de développement, gate R76 = NO-GO.** Cette tranche ne
certifie ni optimisation réelle, ni qualité visuelle, ni performance GPU.
La source de la roadmap est
[`DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md`](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md).
La PR documentaire #289 concerne R25–R30 et était déjà fusionnée.

## Périmètre réellement implémenté

`drawtemp.assets.optimization_audit` produit un rapport JSON reproductible
**en lecture seule**, sans modifier le `GameProject`, les images, les
animations, les projets, les sauvegardes ni les replays. Il utilise
`sporebound.assets.AssetRegistry` comme unique vérité pour les chemins,
IDs, animations, régions et bindings.

- Graphe des liens animation → sprite (chaque frame) et binding → asset,
  ordonné et stable. Les images partagées par un atlas sont comptées **une seule
  fois par chemin physique**, jamais une fois par région/sprite.
- Empreinte SHA-256 calculée en streaming avec limite de 256 MiB par fichier,
  taille des octets encodés et repérage des contenus rigoureusement identiques.
  Les doublons sont **candidats** à expertise, non une promesse de réduction de
  taille ou un ordre de suppression.
- Estimation `width × height × 4` à partir d'un en-tête PNG pour un éventuel
  staging RGBA décompressé ; cette valeur **n'est pas** une mesure mémoire
  observée du CPU ou du GPU. Aucun décodeur PNG/Pillow n'est invoqué ; l'audit
  ne compare pas les pixels affichés.
- Contrôle d'en-tête PNG / RIFF WAV / Ogg ; détection de fichiers manquants,
  symlinks (même dans le projet), collisions de casse, changements observables
  durant la lecture et limites de dimensions.
- Réutilisation de `drawtemp.export.r15.preflight(..., require_licenses=True)`
  sur le Content + `*.game.json` canonique. Aucun nouvel algorithme d'approbation
  juridique : l'index `asset-licenses.json` et les preuves de droits R15 restent
  obligatoires et contrôlés **sur les octets originaux**.
- Politique de compression **déclarée version 1** : PNG conservé (candidats
  lossless seulement), WAV/OGG conservés, aucun shader importable via le
  registre v1, aucune transformation automatique. Le rapport garde
  `release_certified=false`.

## CLI

Exécuter depuis la racine du dépôt, avec un projet réel composé de
`game.json` (Content) et `game.game.json` (GameProject) :

```sh
python -m drawtemp.assets.optimization_audit \
  --content /chemin/projet/game.json \
  --report /chemin/hors-projet/r76a-audit.json
```

Le JSON est toujours affiché sur stdout. Sortie `0` : inventaire lisible et
préflight R15 strict passé. Sortie `1` : inventaire ou droits bloqués.
Un problème empêchant même de charger les manifests produit un diagnostic
`invalid_project`, pas une approbation. `--report` dans le dossier du
projet est rejeté pour empêcher une modification accidentelle de l'original.

```sh
python -m unittest -v tests_standalone.test_r76_asset_audit
```

Comparer les rapports sur les **mêmes entrées**, les mêmes scènes, matériels
et builds. Les sorties sont indépendantes des horodatages et chemins absolus ;
les nombres SHA et tailles sont des mesures de fichier, pas des mesures
d'exécution.

## Gates restantes avant R76 certifié

| Sous-lot | État | Bloqueurs |
|---|---|---|
| R76.A | Implémentation initiale | Provenance R15 réelle sur projet témoin, intégration aux audits des packs et vérification de shaders hors registre, mesure de qualité visuelle des médias |
| R76.B | À faire | Comparaison avant/après approuvée, goldens Qt/Player, inspecteur side-by-side, plan de transformation et Undo transactionnel |
| R76.C | À faire | Corpus fixé, bench démarrage / bundle / mémoire réelle / GPU, p50/p95/p99 + variance, Linux/Windows/macOS et matériel versionné |

**Gate NO-GO** tant que les améliorations n'ont pas été mesurées sur une scène
étalon avec preuve avant/après, sans régression visuelle/gameplay et avec droits
de redistribution applicables à l'asset transformé. Les tests CI ne remplacent
pas les preuves GPU, artistiques ni juridiques.
