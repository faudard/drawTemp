# Map Builder 4.0J — Animated Environment Atlases

## Objectif

Remplacer les simples accents vectoriels de **3.7.32I** par des
**sprites animés RGBA en huit frames** pour l'herbe, les roseaux, les
feuillages et les ondulations d'eau. Le rendu doit rester cohérent avec les
matériaux aquarelle de **3.7.32G** et les raccords **3.7.32H**, aussi bien
dans le Studio que dans le Player.

Aucune modification de `Content`, `GameProject`, des règles tactiques,
de l'horloge CT, des collisions, des sauvegardes ou des replays.

## Formats et art

`sporebound/environment_atlas.py` contient le générateur graphique
déterministe : quatre **PNG RGBA 512×64**, un par famille visuelle,
composés de huit images transparentes **64×64** côte à côte.

| Famille | Visuel | Ancre stable dans le frame |
| --- | --- | --- |
| `grass` | Cinq brins aux pointes oscillantes et plusieurs pigments | Pied (32, 54) |
| `reeds` | Quatre tiges et massettes fléchissant au vent | Pied (32, 54) |
| `leaves` | Masses de feuillage transparentes ondulant au-dessus du prop existant | Centre (32, 32) |
| `water` | Trois anneaux subtils de reflets/ondulations | Centre (32, 32) |

Les frames utilisent des lavis de pigments semi-transparents, des
granulations déterministes et de fines bordures antialiasées. Les positions
des pieds des végétaux **ne changent jamais d'une frame à l'autre** ;
les détails s'animent à l'intérieur d'un canevas stable. Cela évite les
sprites qui « marchent » sur la case. L'animation de feuillage est un
**complément transparent** posé sur le prop `tree` / `bush`, pas une
déformation destructrice du sprite peint statique.

Ce sont des **sprites raster procéduraux dans un style aquarelle**, pas des
illustrations originales faites à la main ni des animations physiques.

### Export reproductible pour l'équipe artistique

```bash
python -m sporebound.environment_atlas --output-dir /tmp/animated-environment
```

La commande exporte `grass.png`, `reeds.png`, `leaves.png`,
`water.png` et `manifest.json` avec dimensions, pivots et empreintes
SHA-256 des PNG exacts utilisés par le runtime. La CI Editor conserve
également cet export dans l'artefact
`animated-environment-atlases-3732j`.

## Intégration technique

- `IsoEnvironmentAtlas` est un cache de `tk.PhotoImage` sans import Tk
  pendant la découverte des modules. **Une planche est décodée une fois**.
  Les sous-images à 24/54/96 px sont redimensionnées et conservées pendant
  la vie du Canvas. Aucune décompression ni régénération de pixels par tick.
- `render_isometric` appelle `ambient_kind` pour sélectionner une case
  décorative de façon déterministe et respecter le budget de densité de I.
  Il crée **un seul item image par case éligible** dans le groupe de tuile
  existant. Si aucun atlas n'est présent ou si Tk ne charge pas le PNG,
  les accents vectoriels de I restent disponibles.
- `TerrainAmbientAnimator` référence ces images et remplace uniquement leur
  propriété `image` dans `Canvas.itemconfigure`. Il continue à prendre
  en charge les traits vectoriels antérieurs dans les outils headless.
- Avant un rafraîchissement par `EditorRenderCache`, `restore()` rétablit
  les coordonnées **et les images de référence**, pour éviter de désynchroniser
  le cache retenu par des changements d'animation non éditoriaux. Les sprites
  partagent l'invalidation par groupe de tuile.
- Le Player utilise la même instance `IsoEnvironmentAtlas` pendant toutes
  les frames d'une scène. Les cadres de combat, les poses des acteurs,
  la caméra et l'horloge de gameplay ne sont pas modifiés.
- La case **Ambiance animée** du Studio (introduite en I) continue de
  fonctionner. Le mode désactivé ne crée aucun sprite et ne pollue pas le JSON.

## Validation

```bash
python -m unittest tests_standalone.test_environment_atlases_3732j -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_environment_atlases_3732j_gui -v
```

Critères de réussite :

1. Les 4 PNG ont des en-têtes et CRC valides ; ils contiennent huit frames
   RGBA transparentes, vérifiables par SHA, avec un pivot constant.
2. Aux zooms 24/54/96 px, les frames tiennent dans leur boîte et le cache
   réutilise le même `PhotoImage` pour un triplet
   `(famille, zoom, frame)`.
3. Huit ticks changent les images mais pas les identités ni les coordonnées
   des items Canvas. Un changement de zoom régénère seulement le **cache
   de sprites redimensionnés**, pas le contenu du jeu.
4. Le rendu statique du Studio après `restore` est identique au rendu de
   référence. En Player, les ticks d'ambiance ne reconstruisent pas la scène.
5. Le digest de `Battle` est inchangé et le fallback vectoriel fonctionne
   quand l'atlas est indisponible.

## Suite proposée

**3.7.32K — Animated Biome Composition** : composer plusieurs variantes
de décors animés selon contexte local (berge humide, clairière, sous-bois,
végétation dense), avant de générer automatiquement des biomes et des
routes/rivières à l'échelle d'une carte.
