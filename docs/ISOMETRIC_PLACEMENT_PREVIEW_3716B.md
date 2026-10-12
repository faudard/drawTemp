# 3.7.16B — Prévisualisation d'assets directement dans la scène

## Problème utilisateur

La palette 3.7.16A montre un PNG et une emprise, mais le créateur ne voyait
que des contours au-dessus de la carte avant de poser une maison, un pont
ou un rempart. Il fallait placer, inspecter, annuler et réessayer pour
juger de la composition et de l'échelle.

## Parcours livré

1. Dans le Studio, ouvrir **Bibliothèque d’assets**, choisir un sol, décor ou
   structure, puis **Utiliser sur la carte**.
2. Déplacer le pointeur sur la vue isométrique : l'asset PNG réel apparaît
   à l'emplacement de la future pose, sans modifier le document.
3. Les structures conservent leur orientation, pivot et choix d'entrée.
   La prévisualisation utilise le même gabarit, la même projection de toiture
   et le même point d'ancrage du PNG que le rendu après placement.
4. Les empreintes **vertes** sont autorisées ; les empreintes **rouges**
   signalent les cas refusés (hors carte, collision, zones protégées).
   Les contours restent visibles au-dessus de la prévisualisation.
5. Les sols utilisent la variante de l'atlas correspondant exactement à la
   cellule survolée (même formule déterministe que le renderer). Les décors
   respectent l'ancrage pied de sprite déjà utilisé.
6. En quittant le Canvas, les images temporaires disparaissent. En vue 2D,
   les anciens outils restent disponibles sans PNG isométrique.
7. Si un atlas manque ou est illisible, aucun ghost opaque n'est créé :
   les contours et le placement existants continuent de fonctionner.

La pose effective est toujours confiée aux commandes existantes :
validation, refus des positions dangereuses, undo/redo, sauvegarde et
rechargement. Le rendu anticipé d'un tampon correspond à l'atlas existant,
pas à quatre variantes graphiques distinctes : les quarts de tour opposés
partagent toujours une frame PNG.

## Architecture

- `sporebound/iso_architecture.py` :
  `preview_structure_sprite_position()` calcule sans Tk une instance
  éphémère à partir de `structure_template`, puis appelle
  `building_sprite_top_left` ou `fortification_sprite_top_left`.
  La signature ne crée aucun champ dans Content.
- `sporebound/editor.py` : prévisualisation sous le pointeur en
  réutilisant `IsoTerrainAtlas`, `IsoPropAtlas`, `IsoBuildingAtlas`
  et `IsoFortificationAtlas` déjà en mémoire ; aucune seconde cache
  ni registre de placements.
- `tests_standalone/test_iso_scene_preview_3716b.py` :
  géométrie de six familles, quatre rotations, variantes de porte, pivot
  et absence d'import de Tk/Pillow en mode headless.
- `tests_standalone/test_asset_palette_gui.py` :
  scénario existant étendu avec vrais événements de survol et sortie
  de carte avant chaque clic et sauvegarde.

Aucun changement du moteur, du CT, de l'IA, des collisions, du
pathfinding, du schéma JSON, des sauvegardes et des replays.

## Vérification demandée

```sh
python -m unittest discover -s tests_standalone -p test_iso_scene_preview_3716b.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover \
  -s tests_standalone -p test_asset_palette_gui.py -v
python -m unittest discover -s tests_standalone -v
```

CI attendue : matrice Python Linux/Windows/macOS et job GUI Tk/Xvfb
Linux. Une vraie revue visuelle humaine reste nécessaire pour juger les
occlusions complexes, le positionnement après zoom/relief et les rendus
sur écrans Windows/macOS. Aucun succès CI non vérifié n'est revendiqué.

## Hors périmètre

Ce lot ne propose pas encore l'import guidé des PNG du projet, les
variantes d'assets persistantes, les miroirs du PNG ni des modèles
multi-cellules artistiquement définitifs. Il ne modifie pas les
règles de hauteur ou le rendu des étages superposés.

**Suite recommandée :** village médiéval de référence 3.7.17A et audit
comparatif de la fidélité Player sur des scènes complexes.
