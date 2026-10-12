# 3.7.13 — Façades, toitures et pivots d'architecture isométrique

Le Map Builder 2.5D gagne un rendu architectural **procédural stylisé** qui ne
modifie **aucune règle de combat** et n'introduit **aucun champ JSON**.

## Fonctionnalités

- Les plans `Maison`, `Tour` et `Ruines` de la 3.7.12 sont **reconnus
  depuis leurs tuiles** : à la sauvegarde/relecture, les façades et les
  toitures sont reconstruites à partir du contenu existant.
- Deux calques indépendants **Bâtiments** (façades) et **Toitures**
  permettent de masquer le décor architectural pendant la création.
- Une toiture (Maison en tuiles terracotta, Tour en ardoise) est dessinée en
  projection isométrique avec arêtes et quatre pans. Les ruines gardent des
  murs incomplets, sans toiture entière.
- **Coupe automatique** : si une case du bâtiment est sélectionnée ou si une
  unité vivante occupe son emprise, le toit opaque devient un contour pointillé
  afin de conserver la visibilité. L'outil de sélection reste au premier plan.
- **Porte alternative** : dans la palette des structures, `Entrée A`
  conserve les plans historiques ; `Entrée B` déplace l'entrée de la
  Maison ou des Ruines sur une deuxième case praticable.
- **Pivot de placement** : `Coin` (coin supérieur gauche, comportement
  historique), `Centre` (ancrage au centre) et `Porte` (ancrage sur la case
  de la porte) restent corrects après une rotation à 90/180/270°.

## Méthode et garanties

Les façades sont **déduites de modèles complets** : si un auteur peint par
dessus une maison et rompt sa structure, le calque architectural disparaît,
mais les tuiles restent intactes. Cela évite des objets de bâtiment fantômes,
ou des métadonnées persistantes invalides après un copier/coller, une édition
JSON, un rechargement ou une annulation.

Le rendu n'utilise ni Tk dans les tests headless, ni dépendance externe.
L'éditeur Tk dessine des polygones à la volée, dans un style architectural
original mais qui reste provisoire : **les façades/toits ne sont pas encore
des PNG peints à la main**. Les toits sont une surcouche visuelle sans impact
sur visibilité tactique, déplacements, collisions, capacités de saut ou CT.

La pose continue de passer par `structure_template`,
`validate_structure_placement`, `paste_terrain` et
`Document.replace`. Les unités, objectifs et objets ne sont pas déplacés.

## Tests

```sh
python -m unittest discover -s tests_standalone -p test_iso_architecture_3713.py -v
python -m unittest discover -s tests_standalone -p test_iso_structures_3712.py -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_map_editor_gui.py -v
```

L'intégration doit aussi vérifier la matrice GitHub Actions Linux, Windows
et macOS (Python 3.10, 3.12 et 3.14) et la distribution Python.

## Limites

Pas encore de toiture dont le plan est modifiable case par case ou de
bâtiment 3D avec orientation caméra libre. La détection des bâtiments exige
un plan de structure intact ; l'édition manuelle des murs peut volontairement
faire disparaître la toiture. Ce comportement est préférable à la création
silencieuse de nouveaux objets de simulation ou d'anciens formats incompatibles.
