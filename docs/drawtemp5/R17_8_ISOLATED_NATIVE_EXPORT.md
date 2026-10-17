# R17.8 — Export autonome / vérification sur runner séparé

## Diagnostic du 17 octobre 2026

La CI de R15 (Windows/Linux/macOS) échouait sur **les trois plateformes** à
`Pre-export validation failed: Duplicate asset path: art/jeanne/jeanne_atlas.png`.
Plusieurs `sprite` nommés contiennent des régions différentes d'un **même atlas**
PNG ; ce ne sont pas deux fichiers d'export différents. Les tests R15 du
Creator échouaient également sur cette erreur amont.

## Correction apportée

Le préflight R15 conserve les validations *par asset ID* du registre
(`AssetRegistry.diagnostics`), mais **déduplique les chemins physiques exacts**
à empaqueter. Si deux références désignent `art/jeanne/jeanne_atlas.png`,
un seul fichier doit apparaître dans `game/` et dans le manifeste SHA-256.
Si deux noms de fichiers **diffèrent seulement par la casse** sur un export
portable, le préflight échoue au lieu d'écraser un fichier sur Windows/macOS.
Les erreurs de fichiers absents, sorties de répertoire, formats corrompus,
licences et R14 restent bloquantes selon leurs gates respectifs.

Régression : `test_multiple_sprite_regions_share_one_verified_atlas_file`
et la batterie R15 existante (tamper, R14 report refusé, destination non écrasée).

## Épreuve supplémentaire de relocation native

La workflow `drawtemp5-r15.yml` fait maintenant deux phases distinctes :

1. Sur **chaque OS**, construit un vrai Player PyInstaller natif, réalise
   `export_game`, vérifie le manifeste, lance les smokes, puis archive le
   répertoire `Jeanne` **avec les droits d'exécution préservés**.
2. Sur **un autre runner** de même OS, **sans checkout, setup-python, pip,
   Studio ni copie du dépôt**, télécharge *seulement* le bundle archivé,
   l'extrait sous `RUNNER_TEMP`, exécute le vrai binaire Player pour
   l'écran titre et l'exploration puis corrompt `game/jeanne.json`. Le
   Player doit refuser le lancement et expliquer l'échec d'intégrité.
   Tout succès inattendu, absence de manifeste ou échec de lancement est rouge.

L'artefact `r15-bundle-<OS>` est une prévisualisation à examiner :
**pas** une release signée. La vérification en runner séparé est une preuve de
relocation et d'absence de dépendances au *checkout*, pas un audit sur
poste utilisateur vierge ni un certificat de licence. Les runners GitHub
hébergés peuvent contenir Python ou d'autres dépendances système ; **ne pas
les déclarer absentes**.

## Commandes

```bash
python -m unittest tests_standalone.test_drawtemp5_r15 \
  tests_standalone.test_drawtemp5_r15_creator -v
python -m drawtemp.export.cli check --content sporebound/content/jeanne.json
```

## Gate restant ouvert

À vérifier avant R17 stable : signatures Windows/macOS, compatibilité Linux
`glibc` et paquets OS documentés, licence/redistribution vérifiée,
installation sur vrai poste vierge, R14 goldens/GPU et un projet
**réellement créé par le Studio** (pas uniquement la campagne livrée).
Ne pas fermer R17.8/R17.12 sur un simple offscreen CI.
