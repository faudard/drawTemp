# 3.7.15 — Fortification & Scenery Atlas

Ce jalon complète les six vues architecturales de la 3.7.14 avec six vues
supplémentaires en **PNG palettisé transparent original**. Les remparts,
escaliers et ponts sont désormais visibles comme assemblages isométriques
dessinés, au lieu de seules cases isolées.

## Livrables

| Modèle existant | Emprise d'origine | Deux frames |
| --- | --- | --- |
| Rempart | 5×1 | horizontal / vertical |
| Escalier | 2×4 | escalier montant selon l'axe x ou y |
| Pont | 3×2 | franchissement dans les deux orientations |

- `sporebound/content/art/iso/fortifications.png` : 2700×250 pixels,
  six frames de 450×250 pixels (index : rempart 0/1, escalier 0/1,
  pont 0/1). Palette avec canal alpha, pierre médiévale, pierre usée,
  végétation et eau.
- `sporebound/iso_fortification_atlas.py` : vérification stricte de la
  taille, cropping, adaptation au zoom (24–96), cache en mémoire et secours
  transparent quand l'atlas ne peut pas être lu.
- `sporebound/iso_architecture.py` : identification des plans complets
  existants à partir des **tuiles terrain**, sans nouvel objet de carte.
  Les plans tournés sont retrouvés même si leur première case n'est pas
  leur marqueur distinctif.
- `sporebound/iso_map.py` : silhouettes des acteurs et sélection au premier
  plan sur les nouveaux éléments décoratifs.
- `sporebound/editor.py` : atlas chargé uniquement par l'interface Tk.
- Tests headless PNG/CRC/alpha/six frames, récupération des modèles après
  rotation 0/90/180/270, placement/annulation/sauvegarde, zoom et masquage
  d'une structure sélectionnée. Test graphique Tk/Xvfb de trois structures.

## Comportement

Le catalogue **Structures multi-cases** de la 3.7.12 ne change pas. Poser un
rempart, escalier ou pont utilise toujours le `TerrainClipboard` validé,
les protections anti-écrasement et l'historique undo/redo. La nouvelle couche
`Bâtiments` contrôle l'affichage des nouveaux sprites ; le calque
`Toitures` concerne uniquement les bâtiments possédant un toit.

Un ouvrage dont l'emprise est sélectionnée ou occupée par un acteur passe
en mode d'affichage de secours sur tuiles/props pour garantir une lecture
tactique correcte. Les images décoratives n'influencent pas les cases bloquées,
les hauteurs, les pathfindings, les rivières, ni les règles de combat. Sans
PNG ou sur une version de Tk incompatible, les anciens rendus de cases
continuent de fonctionner.

## Compatibilité

- Schéma des cartes et sauvegardes inchangé.
- Aucune migration requise, aucun ID de structure injecté.
- Les anciennes cartes ne changent pas de gameplay.
- La détection dépend d'une **emprise de tampon intacte** : une construction
  modifiée case par case peut perdre son sprite sans altérer le terrain.
- L'atlas est inclus par le `pyproject.toml` actuel
  (`content/art/iso/*.png`).
- Les visuels sont une **première passe pixel-art**, pas des scènes 3D :
  ni intérieurs multi-étages jouables ni modifications des escaliers
  tactiques dans ce jalon.

## Validation

```sh
python -m unittest discover -s tests_standalone -p test_iso_fortification_atlas_3715.py -v
python -m unittest discover -s tests_standalone -p test_iso_building_atlas_3714.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_map_editor_gui.py -v
python -m unittest discover -s tests_standalone -v
```

Gates : tests éditeur avec Xvfb ; moteur Linux/Windows/macOS sous
Python 3.10/3.12/3.14 ; packaging Python sur les trois OS et inspection
visuelle à trois niveaux de zoom. Cette PR est empilée après #76.
