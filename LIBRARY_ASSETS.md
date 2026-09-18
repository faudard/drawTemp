# Sporebound Tactics — Library Asset Pack V1

Ce pack trie les assets Sporebound retrouvés dans la bibliothèque et les prépare pour le projet Godot 4.7.1.

## Ce qui est directement utilisable

- `assets/portraits/library/` : portraits transparents normalisés en **512×512** pour UI, fiches d’unité et sélection de héros.
- `assets/status_icons/library/` : 8 icônes **128×128** : `sick`, `electrified`, `burning`, `cursed`, `controlled`, `poisoned`, `frozen`, `sleep`.
- `data/library_assets/catalog.json` : catalogue machine-readable avec chemins `res://`, catégories et niveau de préparation.
- `scripts/catalogs/library_asset_catalog.gd` : petit loader Godot pour retrouver un portrait ou une icône par identifiant.


## Intégration runtime V1.27

Les assets de bibliothèque ne sont plus seulement classés : ils sont maintenant branchés au runtime 3D via le nouveau mode `portrait_billboard` de `SporeUnitVisualDefinition`. Ce mode affiche l’illustration transparente haute qualité sur le billboard tactique, tout en conservant les animations de déplacement/attaque/cast du `SporeUnitActor3D` (bob, lunge, hit flash, KO). Il sert de rendu de production intermédiaire tant que le vrai atlas 4 directions n’existe pas.

Les 10 unités existantes ont une association active :

| Unité | Asset bibliothèque | Rôle visuel |
|---|---|---|
| Momo | `shield_guard` | garde / frontline |
| Pipo | `flower_healer` | soin / soutien |
| Luma | `rifle_ranger` | distance / éclaireuse |
| Ziggy | `spore_gunslinger` | gunner mobile |
| Grincheux | `spike_fighter` | mêlée agressive |
| Baveux | `toxic_mage` | toxique / debuff |
| Le Comptable | `spore_alchemist` | soutien distance |
| DJ Morille | `coral_monk` | tempo / soutien |
| Choriste Moisi | `spore_shepherd` | soutien / invocation |
| L’Archiviste | `shadow_duelist` | boss / contrôle |

Les **39 portraits** ont aussi chacun un skin `lib_<asset_id>` dans `data/visuals/units/`. Ils apparaissent donc directement dans **Sporebound Studio > Visuals** et peuvent être affectés à une unité sans recopier de chemin à la main. Le Visual Editor sait maintenant prévisualiser le mode `portrait_billboard`.

Pour **12 personnages** disposant déjà d’une planche d’action compatible, une pose d’impact transparente 512×512 a été extraite dans `assets/action_poses/library/`. Le runtime bascule automatiquement sur cette pose pendant `Attack`; les mages compatibles peuvent l’utiliser aussi pendant `Cast`. Cela donne déjà des attaques visuellement cohérentes avec la bibliothèque avant la production des atlas 4 directions définitifs.

Pour revenir temporairement au rendu procédural ou à un atlas existant, change simplement `render_mode` dans le visuel : `procedural`, `sprite_sheet`, `portrait_billboard` ou `auto`.

## Sources conservées, mais pas branchées directement au runtime

`assets/source_art/library/` contient les originaux haute résolution, planches d’actions, planches directionnelles, états altérés et concepts. Un `.gdignore` est placé dans ce dossier afin que Godot ne réimporte pas inutilement ces gros fichiers.

Les **action strips** ne doivent pas être affectés directement à `SporeUnitVisualDefinition.sprite_sheet_path` : le runtime actuel attend des cellules fixes et, pour le mode `4_way`, 4 directions (`front,right,back,left`). Les planches servent de source pour fabriquer le véritable atlas de chaque personnage.

## Contrat visuel actuel du projet

Le projet V19 utilise déjà le bon format de production pour le Hero Creator : **192×192**, quatre directions et six états (`Idle`, `Move`, `Attack`, `Cast`, `Hit`, `KO`). Les 572 PNG de `assets/hero_parts/` restent donc la base modulaire à conserver.

Pour convertir un personnage de la bibliothèque en unité de combat complète, cible recommandée :

```text
row 0: front  [Idle][Move][Attack][Cast][Hit][KO]
row 1: right  [Idle][Move][Attack][Cast][Hit][KO]
row 2: back   [Idle][Move][Attack][Cast][Hit][KO]
row 3: left   [Idle][Move][Attack][Cast][Hit][KO]
frame: 192x192
```

Le catalogue indique les paires portrait/action-strip déjà identifiées. Les identifiants ajoutés ici sont des **working IDs** de classement, pas des noms de lore définitifs.
