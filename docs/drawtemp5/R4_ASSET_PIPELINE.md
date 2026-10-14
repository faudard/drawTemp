# DrawTemp 5.0 — R4 Asset Pipeline & Art Direction

**Branch:** feat/drawtemp5-r4-asset-pipeline  
**Baseline:** master @ 411e8da31c600db52b558f8defe2fbba9e03036c  
**Scope:** première intégration fonctionnelle de R4, réutilisant les contrats v1.

## Architecture

- **Source de vérité :** GameProject.assets → sporebound.assets.AssetRegistry. Les mêmes IDs de sprites et animations sont consommés par les adaptateurs Studio/Player. Aucune évolution du format Content, du modèle tactique ou des sauvegardes.
- **Import :** drawtemp.assets.atlas vérifie les chunks/CRC, dimensions, taille maximale 32 MiB, découpe via régions, orientations et poses. Chaque frame d'une animation référence une région du même PNG importé (pas de duplication de pixels). Import sans écrasement des fichiers existants.
- **Rendu :** AssetResolver fournit filename, rect, pivot, footprint et signature de modification de chaque frame. Une couche Qt Quick R3 peut ainsi charger une texture unique, partager le cache et sélectionner les frames sur son horloge visuelle; aucune logique CT dans l'adaptateur.
- **Annotations :** .drawtemp/r4-annotations.json est un sidecar optionnel, version 1, pour pivot, footprint, orientation, pose, provenance et licence. **Il ne contient ni nouveau contenu tactique ni chemin d'asset parallèle.** Toute référence doit exister dans le registre canonique.
- **Browser :** drawtemp.assets.qt_browser.AssetBrowser est un QWidget optionnel (PySide6). Vignettes, filtres, recherche sans accents, favoris, récents, preview des frames et MIME application/x-drawtemp-asset-id. Les frames utilisées par une animation sont masquées dans les collections au profit de la pose regroupée.
- **Terrains, autoblend et ambiance :** drawtemp.assets.terrain **réutilise** terrain_schema, terrain_autoblend et environment_atlas legacy. Les matériaux restent ceux de Content, le seed est déterministe, l'animation des quatre environnements est générée depuis des PNG RGBA huit frames existants. Il n'y a pas de second algorithme de terrain.

## Exemple d'import réel : Jeanne

Copier d'abord le fichier .game.json du projet vers un dossier d'essai, et utiliser le Content associé. L'import copie l'atlas sous assets/imported/jeanne.png près du manifeste et sauvegarde celui-ci avec GameProject.save.

```sh
python -m drawtemp.assets import-sheet \
  --project /tmp/jeanne/game.json \
  --content sporebound/content/core.json \
  --source sporebound/content/art/jeanne/jeanne_atlas.png \
  --id jeanne --bind-prefix jeanne --frame-size 64 64 --pivot 32 60 \
  --rows '{"idle":[0,1],"move":[2,3],"attack":[4,5],"hit":[6],"defeat":[7]}' \
  --license UNVERIFIED
```

Cette disposition crée 32 entrées sprite régionales, 20 animations directionnelles et 20 slots de binding (avec --bind-prefix) dans la structure actuelle de GameProject.assets. Le contenu de la source reste intact, et une deuxième importation du même ID est rejetée. Il appartient à l'auteur de remplacer UNVERIFIED par une licence vérifiée.

```sh
python -m drawtemp.assets validate --project /tmp/jeanne/game.json \
  --content sporebound/content/core.json
python -m pip install ".[qt6]" # Python 3.12 pour l'aperçu Qt qualifié
python -m drawtemp.assets browse --project /tmp/jeanne/game.json \
  --content sporebound/content/core.json
```

Pour une bande horizontale à huit images (herbe, feuilles, roseaux ou eau) :

```sh
python -m sporebound.environment_atlas --output-dir /tmp/env-art
python -m drawtemp.assets import-strip --project /tmp/jeanne/game.json \
  --content sporebound/content/core.json --source /tmp/env-art/grass.png \
  --id environment.grass --frame-size 64 64 --frames 8 \
  --pivot 32 54 --frame-ms 125 --license UNVERIFIED
```

L'import garde les pivots et la durée de chaque frame. Les ID existants ne sont jamais renommés.

## Validation

```sh
python -m unittest tests_standalone.test_drawtemp5_r4_assets -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp5_r4_qt -v
```

La première commande n'importe pas Tk, Qt, ni Pillow. Vérifications : PNG invalide/CRC, limites, dimensions, collisions (y compris casse), liens symboliques, région/frames, source modifiée, déterminisme seed/animation, conservation de l'ID, présentation headless, sauvegarde/réouverture de GameProject et licences non vérifiées. La seconde instancie réellement un QWidget avec aperçu/vignettes, filtre, favori et drag MIME.

## Périmètre et statut honnête

| Lot | Statut de cette tranche |
| --- | --- |
| R4.1 | Couverture initiale : index unifié branché sur les IDs v1, import explicite |
| R4.2 | Browser Qt utilisable seul; intégration au Studio R2 restant à faire |
| R4.3 | Import PNG atlas, découpage, validation structure/CRC; décodage GUI via Qt |
| R4.4 | Directions/poses, pivots/footprints et timing sauvegardés en annotations |
| R4.5–R4.6 | Réutilisation des matériaux/AutoBlend existants, pas une nouvelle implémentation |
| R4.7–R4.8 | Variantes seed et PNG animés existants exposés; effets GPU R3 en attente |
| R4.9 | Tests headless et Qt initiaux; revue visuelle et animation golden non certifiées |
| R4.10 | Plan de migration legacy à IDs conservés; migration de masse non automatique |
| R4.11 | Provenance et licences suivies; contrôle pré-export dédié R15 à raccorder |

**Gate R4 complet encore ouvert :** sans renderer GPU R3 réellement intégré au Studio *et* Player Qt, on ne peut pas certifier la parité d'affichage des atlas/positions ni un benchmark GPU. Cette PR livre un contrat commun et des tests d'import, mais **ne revendique pas R4 entièrement terminé**. Les ressources aquarelles historiquement absentes ne sont ni inventées ni considérées livrées.

## Garanties de migration et limites

- Le projet original peut être copié pour essai; aucune importation massive implicite. Le manifeste v1 est conservé et l'ancien outil reste disponible.
- Les erreurs ordinaires de l'import restaurent le précédent manifeste et le sidecar; une coupure brutale peut laisser une image orpheline non référencée. Les PNG sont créés en mode exclusif et jamais remplacés.
- L'analyse PNG vérifie la structure et le CRC sans constituer un décodage intégral (le decoder Qt lit les pixels dans la GUI). Les fichiers tiers restent des données non fiables.
- UNVERIFIED produit un diagnostic; il n'est **pas** une licence valable pour la distribution. Le propriétaire des assets doit vérifier et conserver la preuve des droits.
- La scène/isométrie R3, les tests GPU sur machine réelle, le packaging et la migration visuelle complète restent des jalons de suivi.
