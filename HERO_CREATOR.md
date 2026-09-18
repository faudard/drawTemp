# Sporebound Hero Creator — V1.28 Library-Grounded

V1.28 change la priorité du créateur : le rendu doit d'abord rester cohérent avec la direction artistique Sporebound.

## Deux modes

### Guidé — rendu bibliothèque

Le héros est rendu depuis un **kit artistique complet** en quatre directions. Les anciennes couches modulaires ne sont pas empilées dessus, ce qui évite les yeux/barbes/cornes/armes mal ancrés et l'effet « stickers ».

Le kit fourni est **Scout forestier** (`forest_scout`). Il reprend le langage visuel défini pour Momo : chapeau rouge-orangé à taches crème, corps compact, foulard/feuilles, cuir/bois et lance.

Le mode guidé conserve uniquement les réglages sûrs :

- kit bibliothèque ;
- Petit / Moyen / Grand ;
- échelle globale limitée par le compositeur ;
- léger décalage global du personnage ;
- portrait et échelle runtime ;
- teinte globale optionnelle, désactivée par défaut.

Le bouton **AUTO-FIX LOOK** revient immédiatement à ces valeurs sûres.

### Libre — couches modulaires

Le workflow V1.26 reste disponible : tête, yeux, iris, barbe, marques, vêtements, trois accessoires, arme, asymétrie, offsets, resize et rotation. Ce mode est volontairement permissif.

## Ajouter un kit de la bibliothèque

Créer `assets/hero_kits/<kit_id>/` avec :

- `front.png`
- `right.png`
- `back.png`
- `left.png`

Format recommandé : PNG RGBA 192×192, personnage centré et ancré vers le bas du cadre.

Des variantes d'état sont facultatives : `front_attack.png`, `right_cast.png`, `back_ko.png`, etc. Si une variante n'existe pas, le compositeur reprend automatiquement la vue directionnelle générique.

Les dossiers valides apparaissent automatiquement dans **Kit bibliothèque** : aucune modification GDScript n'est nécessaire.

## Génération

Le format runtime ne change pas :

- portrait : 192×192 ;
- atlas : 1152×768 ;
- 6 colonnes : Idle, Move, Attack, Cast, Hit, KO ;
- 4 lignes : Front, Right, Back, Left.

Le `SporeUnitVisualDefinition` existant reste compatible.


## V1.28 — Guided Kit Library

The guided mode now exposes an actual kit library with a thumbnail and metadata. Bundled kits are Scout forestier, Gardien nature, and Mage nature. Each kit is validated for all four directions. The editor reports how many combat states have dedicated drawings; missing states explicitly reuse Idle so the renderer never invents a distorted modular composite.

Add a new kit by creating `assets/hero_kits/<id>/front.png`, `right.png`, `back.png`, `left.png`, optionally `thumbnail.png` and `kit.json`. State-specific art follows `<direction>_<state>.png`.
