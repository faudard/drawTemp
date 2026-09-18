# V1.28.0 — Guided Kit Library

- Added `forest_guardian` and `nature_mage` coherent 4-direction guided kits.
- Added `kit.json` metadata and automatic kit discovery validation.
- Added kit thumbnail + role/tags/description/combat-state coverage in Hero Creator.
- Guided mode now disables irrelevant expression-layer controls.
- Added explicit state fallback reporting: only real dedicated state art is used when present.
- Added Guardian and Nature Mage guided presets.
- Added `test_hero_creator_v128.gd`.

# V1.27 — Library-Grounded Hero Creator

- Nouveau mode **Guidé** basé sur des kits artistiques complets en quatre directions.
- Nouveau mode **Libre** conservant tout le compositeur modulaire V1.26.
- Détection automatique des kits sous `assets/hero_kits/`.
- Kit initial `forest_scout` aligné sur la nouvelle direction artistique de Momo.
- `AUTO-FIX LOOK` rétablit mode guidé, proportions sûres, offsets/transforms neutres et teinte désactivée.
- Les contrôles modulaires sont rendus non éditables en mode guidé pour éviter les réglages sans effet.
- Le compositeur accepte des variantes optionnelles par état (`front_attack.png`, etc.).
- Correction d'une double déclaration locale dans `apply_to_visual()`.
- Momo et ses assets générés sont préconfigurés en mode guidé.
- Smoke test `test_hero_creator_v127.gd`.

# V1.26.2 — Hero Creator parse fixes

- Isolated Hero Creator bootstrap from `studio_dock.gd`.
- Renamed `Compositor` constants to avoid shadowing Godot native `Compositor`.
- Replaced PackedStringArray constructor constants with constant Array literals.
- Fixed `index` parameter shadowing in `studio_dock.gd`.

# V1.26 — Hero Creator Expressions & Profiles

- Expressions bakeées par état : Idle / Move / Attack / Cast / Hit / KO.
- Aperçu de l’état sélectionné dans le Hero Creator.
- Portrait avec direction + expression indépendantes.
- Six presets de silhouette forte et verrou de proportions.
- Profils de palette sauvegardables/appliquables sans modifier le look.
- Quatre palettes fournies et randomizer V1.26 enrichi.
- Smoke test `test_hero_creator_v126.gd`.

# V1.25 — Hero Creator Face Details

- Iris et pupilles deviennent des couches séparées et recolorables.
- Ajout des sourcils, du nez, des dents et des taches de peau.
- Passage de 1 à 3 couches de cicatrices/marques simultanées.
- Ajout des boucles d’oreilles avec variantes gauche/droite.
- Ajout d’une couche bijou/pendentif.
- Cache mémoire des vignettes de galerie.
- Momo est préconfiguré avec iris bleu, pupille, sourcils, nez, freckles, deux marques, boucle d’oreille et pendentif.
- Conservation des fonctions V1.24 : asymétrie, 3 accessoires, édition directe, Undo/Redo, favoris, comparaison, presets, duplication et import/export.
