# Map Builder 4.0G — Matériaux aquarelle raccordables

## Objectif

Transformer le prototype d'AutoBlend de **3.7.32F** en un rendu de terrain
aux pigments aquarelle, **sans dépendre d'un nouveau format Content** et sans
attendre la génération complète de biomes.

Ce lot n'importe PAS directement les illustrations en forme de dioramas
(isolées avec des flancs épais) comme des cases jointives : leurs bords ne
permettent pas une juxtaposition propre. Il fournit au contraire un **kit
procédural reproductible de 16 textures** (8 surfaces × 2 variantes), chacune
avec une silhouette de dessus en losange 96×48, des taches de pigments
déterministes et des bordures chromatiques identiques entre les variantes
d'un même matériau.

## Implémentation

- `sporebound/terrain_watercolor.py` : moteur *pur Python*, sans Pillow,
  Tk ni RNG global. Deux couches de bruit cohérent, petites granulations,
  lavis de pigments et cache mémoire partagé. Le générateur encode un PNG
  **RGBA** standard en mémoire, avec IHDR/IDAT/IEND, CRC et compression zlib.
- `IsoTerrainAtlas` : la construction par défaut charge cet atlas aquarelle
  depuis les octets PNG, sans écrire dans le dossier de l'application et
  sans dépendre de la présence de l'archive de sprites V3. L'option
  `path=<atlas.png>` conserve l'ancien chargement PNG externe. En cas de
  problème du décodeur Tk, le rendu revient à l'atlas PNG embarqué existant.
- `render_isometric` (commun Studio/Player) : suppression de l'effet de
  quadrillage sombre aux frontières de cases lorsque l'atlas est activé.
  Les faces verticales du relief et les raccords berges/ponts continuent
  d'utiliser les mécanismes existants.
- Les bordures du dessus du losange ont exactement le **même pigment RGB**
  entre variantes, même après un changement de zoom. Les détails sont plus
  visibles au centre et progressivement atténués avant l'arête.
- Le rendu `AutoBlend` de 3.7.32F reste actif : le kit de pigments ne crée
  pas de système de transition parallèle; il remplace simplement la texture
  fondamentale des matériaux.

## Générer une planche PNG pour revue artistique

```bash
python -m sporebound.terrain_watercolor --output /tmp/terrain_watercolor.png
```

Cette commande exporte le même atlas que le Studio ou le Player, accompagné
de son SHA-256. Le PNG de 1536×48 peut être ouvert dans n'importe quel éditeur
graphique; il n'est pas nécessaire de régénérer le projet Content.
La CI Editor publie également ce **vrai fichier PNG** dans l'artefact GitHub
`terrain-watercolor-materials-3732g` pour revue visuelle avant fusion.

Pour utiliser explicitement **l'ancien atlas** dans un outil :

```python
from sporebound.iso_map import IsoTerrainAtlas, DEFAULT_TERRAIN_ATLAS
atlas = IsoTerrainAtlas(canvas, path=DEFAULT_TERRAIN_ATLAS)
```

## Validation

```bash
python -m unittest tests_standalone.test_terrain_watercolor_3732g -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_terrain_watercolor_3732g_gui -v
python -m unittest tests_standalone.test_terrain_autoblend_3732f -v
```

**Gates** : 16 images décodables, même SHA sur toute plateforme, même couleur
sur les bords de variantes, absence de coutures sombres, chargement Tk à
24/54/96 pixels, possibilité de revenir à l'atlas historique, et rendu
Studio/Player fondé sur les mêmes données visuelles.

### Limites connues

Il s'agit de **textures procedurales inspirées d'une aquarelle**, pas de
nouveaux originaux peints à la main ni d'animation. Les bords neutres et
le dégradé de pigments améliorent la continuité, mais le véritable
*multi-material alpha blending* et les raccords aux angles de trois surfaces
exigeront des masques peints / shaders logiciels dans un lot ultérieur.
Le kit n'ajoute pas non plus de rivière procédurale, végétation animée ni
génération de biomes.
