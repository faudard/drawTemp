# Éditeur drawTemp — audit et roadmap 3.7.16–3.7.22

## 3.7.20 — suivi d'implémentation (13 octobre 2026)

- **3.7.20A en PR** : mode d'intérieurs consultables (coupe des toits,
  sols/murs/entrées, mobilier existant et inspecteur contextuel) ; mêmes
  tuiles tactiques, même rendu Studio/Player et anciens fichiers préservés.
- **3.7.20B en PR empilée** : plateaux intérieurs visuels de niveaux 1–3,
  sols/mobilier/trous et édition isométrique dans le Studio. Voir
  [INTERIOR_FLOORS_3720B.md](INTERIOR_FLOORS_3720B.md).
- **3.7.20C non livré** : vrais étages simultanément jouables. RFC et gates
  multi-niveaux dans [INTERIORS_MULTILEVEL_3720.md](INTERIORS_MULTILEVEL_3720.md).
  La vue 2.5D actuelle ne constitue pas un modèle tactique à plusieurs plans.
- Preuves : tests headless 3.7.20A ajoutés ; CI/captures GUI et inspection
  visuelle multi-OS restent nécessaires avant fermeture du gate artistique.


## 3.7.17B — proposition : identité visuelle durable

Les nouvelles structures enregistrent une identité visuelle optionnelle,
indépendante des tuiles tactiques, et ne disparaissent plus lors d'une
retouche locale. Les cartes antérieures restent sans nouveau champ et
conservent la détection des tampons intacte. Voir
[PERSISTENT_STRUCTURES_3717B.md](PERSISTENT_STRUCTURES_3717B.md).

Le gate attend la CI Python/Tk, un round-trip, un replay validé et un contrôle
visuel Studio/Player. La fusion du code ne ferme pas le gate artistique.


## Suivi de livraison — 12 octobre 2026, après audit historique

Les statuts du tableau initial plus bas datent de la base `1af3b41` ;
ils sont conservés pour expliquer les décisions, et non comme état GitHub
instantané. Vérification GitHub effectuée sur `master` 8d5867b :

| Séquence / jalon | Statut GitHub ou gate | Priorité | Complexité / suite |
| --- | --- | --- | --- |
| #73–#77 — constructeurs + atlas 3.7.11–15 | Fusionnées ; validation artistique incomplète | P0 | Base existante |
| #78 — 3.7.16A palette 26 assets | Fusionnée ; import de projet et variantes absents | P0 | M |
| #79–#81 — 3.7.18A–C Player, profondeur, cache de mouvement | Fusionnées ; occlusion/échelle à valider | P0 | L |
| [#82](https://github.com/faudard/drawTemp/pull/82) — cache acteur | Ouverte Draft ; indépendante | P0 | S, tests puis CI |
| [#83](https://github.com/faudard/drawTemp/pull/83) — 3.7.16B survol PNG | Ouverte Draft ; CI testée verte sur 42bf34e | P0 | S, revue visuelle |
| **3.7.17A — scène village Valcroix** | **Implémentée sur branche, gate à vérifier en CI** | **P0** | M ; [guide et captures](REFERENCE_FORTIFIED_VILLAGE_3717A.md) |
| 3.7.17B — bâtiments éditables persistants | À faire, risque compatibilité Content | P0 | L après 17A |
| 3.7.18D — budget graphique et profondeur | Cache Studio et profiling livrés ; budgets à consolider ([mesures](STUDIO_RENDER_PROFILING_3718D.md)) | P0 | M |
| 3.7.19 — entités et objets interactifs, édition guidée | Partiel | P1 | M |
| 3.7.21 — ergonomie/favoris/inspecteur | Partiel | P1 | L |
| 3.7.20 — intérieurs et niveaux superposés | Partiel/absent ; RFC gameplay préalable | P1 | XL |
| 3.7.22 — sauvegarde, export, Player et validation 3 OS | Gate final non fermé | P0 final | L |

Le village de référence assemble **les outils existants**, y compris
`Document`, `place_structure`, `add_object` et `add_event`.
Il ne réécrit pas le moteur et ne dépend pas du ghost-preview de #83 :
les deux PR peuvent être évaluées puis fusionnées séparément.
La preuve graphique sera conservée en artefact du job Linux/Tk/Xvfb ;
une capture générée mais non inspectée **ne ferme pas** le gate esthétique.
Ne pas fusionner automatiquement.


Audit du 12 octobre 2026, base `master` **1af3b41**. Les statuts ci-dessous
portent sur les gates utilisateur, pas sur le nombre de modules présents.
Aucune gate graphique multiplateforme n'est déclarée terminée.

## Actualisation après les fusions du 12 octobre 2026

La base a évolué depuis l'audit initial `1af3b41`. Le tableau d'audit
initial ci-dessous est conservé comme référence **historique** et ne doit
plus être lu comme un état instantané. État GitHub vérifié :

| Livrable | Statut constaté | Référence |
| --- | --- | --- |
| 3.7.11–3.7.15 outils, architecture et quatre atlas | Fusionné, gate esthétique final non fermé | PR #73–#77 |
| 3.7.16A palette de 26 entrées / miniatures / défaut PNG | Fusionné ; gate 3.7.16 encore partiel | PR #78 |
| 3.7.18A scène isométrique Studio + Player | Fusionné, Players château spécialisés non couverts | PR #79 |
| 3.7.18B mouvement animé, ordre de profondeur, coupe | Fusionné ; occlusion volumétrique complète non prouvée | PR #80 |
| 3.7.18C réutilisation Canvas pendant mouvements | Fusionné ; benchmark représentatif 128² à consolider | PR #81 |
| 3.7.18C correction invalidation des attributs d'acteurs | **Ouvert** ; ne pas le dupliquer | PR #82 |
| 3.7.16B prévisualisation WYSIWYG sous le pointeur | **En revue** dans `feat/3.7.16b-wysiwyg-scene-preview` | [note technique](ISOMETRIC_PLACEMENT_PREVIEW_3716B.md) |

### Priorités et PR suivantes (ordre ajusté)

1. **P0, S — 3.7.16B** : même PNG/ancrage entre catalogue,
   pointeur et pose réelle ; test souris Tk, fallback absent, rotations.
   Indépendant de #82. Gate : survol/pose/undo/save/reopen sans dérive
   d'alignement et sans JSON manuel.
2. **P0, M — 3.7.17A** : village test construit *avec les outils de
   l'éditeur*, comprenant une rivière, un pont, deux maisons, une tour,
   un rempart, un accès et de la végétation. Dépend du preview.
   Gate : capture 24/54/96, inspection de raccords, rechargement,
   projet + Player identiques.
3. **P0, L — 3.7.17B** : remplacer la reconnaissance fragile de
   bâtiments basée uniquement sur des tampons strictement intacts
   par une identité de structure compatible avec les anciennes cartes
   (contrat/migration à valider avant modification). Dépend de 17A.
4. **P0, M — 3.7.18D** : rafraîchissement terrain / overlays et
   profil mémoire, avec comparaison des p95 32²/64²/128².
   Dépend de la clôture de #82. Ne pas déclarer un budget
   atteint sans mesure sur le SHA livré.
5. **P1, L — 3.7.19 / 3.7.21** : personnages et objets interactifs
   par palette, inspecteur de propriétés contextualisé, historique
   continu sans recours au JSON. Sous-PR ciblées indépendantes si possible.
6. **P1, XL — 3.7.20** : intérieurs visibles en premier, puis RFC
   des véritables étages superposés avant toute règle tactique nouvelle.
7. **P0 final, L — 3.7.22** : petite mission de siège avec export
   et reprise Player sans JSON ; ne se ferme qu'après preuves Linux,
   Windows et macOS et livrable Python installé hors dépôt.

Criticité : qualité visuelle et continuité **édition → Player** avant
quantité d'assets. Les PNG pixel-art actuellement livrés sont des
prototypes graphiques, pas des illustrations finales manga/chibi.
Les entrées `assets/watercolor` ne prouvent pas la présence des 88 PNG.
Risques : effets d'édition qui rompent la détection des structures,
survol opaque dans les bâtiments, changement de caméra et zoom,
redraws complets après nouveau snapshot, ergonomie du `editor.py`
monolithique. Aucune PR de présentation ne doit altérer le moteur.

## État factuel et problèmes par impact

| Impact | Constat vérifiable | Source / conséquence |
| --- | --- | --- |
| P0 | La vue isométrique est réservée à l'édition (`iso_var and not battle`). Le playtest repasse en vue orthogonale. | `editor.py:refresh`, `player_app.py`, `tk_renderer.py` ; rupture de fidélité édition → jeu. |
| P0 | Sols/décors/structures disponibles mais sélectionnés par listes textuelles ; pas de catalogue visuel commun. | `editor.py:launch`, `iso_structures.py` ; premier lot 3.7.16 ci-dessous. |
| P0 | Réduction Tk isométrique par zoom/subsample combinés : miniatures tronquées ou vides, confirmé par capture et pixels. | Les quatre loaders iso ; réutiliser la correction entière de `CanvasRenderer._cell_photo` (3.7.10). |
| P0 | PNG absents/invalides provoquent un secours silencieux. | Les quatre classes `Iso*Atlas` renvoient `None` ; il faut afficher le diagnostic sans empêcher de placer. |
| P0 | Un bâtiment est reconnu par son tampon de terrain intact. Modifier une case peut faire disparaître son sprite. | `iso_architecture.py:architecture_instances` ; documenter avant de décider d'un modèle persistant compatible. |
| P0 | Les sprites de bâtiments sont superposés après le terrain ; les acteurs passent au premier plan. | `iso_map.py:render_isometric`, `iso_architecture.py:draw_architecture` ; visibilité tactique conservée mais pas d'occlusion spatiale générale. |
| P1 | Plusieurs rangées horizontales de contrôles et de nombreux onglets ; inspecteur surtout textuel. | `editor.py:launch`, `studio_panels.py:StudioPanels` ; mesurer sur 1280×850, clavier et petite fenêtre. |
| P1 | Reconstruction entière du canvas et recherche des structures à chaque rafraîchissement isométrique. | `iso_map.py:render_isometric` (`delete('all')`) ; caches PNG déjà présents, cache géométrique à profiler. |
| P1 | Les orientations de structures 0/180 et 90/270 réutilisent les mêmes frames. | `iso_building_atlas.py`, `iso_fortification_atlas.py` (`turns % 2`) ; quatre rotations de terrain ne signifient pas quatre dessins. |
| P1 | Game Studio, événements, bestiaire, sièges, dialogues, audio et export existent. | `studio_panels.py`, `studio_workspace.py`, `studio_siege.py`, `studio_cinematics.py`, `game_export4.py` ; améliorer les raccords plutôt que recréer des panneaux. |

Le moteur headless (`engine.py`, `model.py`, `rules/`) reste indépendant de Tk.
`Document.replace` valide puis historise ; `place_structure` protège unités,
objets et objectifs ; `TerrainClipboard` porte déjà rotation, miroir et modèles.
`GameProject` porte le registre d'assets et `game_export4` exporte les sources,
le contenu, les assets référencés et les assets embarqués. Ce ZIP n'est pas un
exécutable autonome. Les apparences isométriques de l'éditeur ne constituent pas
encore une preuve de rendu identique dans le Player.

### PR de référence

- [#72](https://github.com/faudard/drawTemp/pull/72) : historique du chantier éditeur, à lire avec ses dépendances historiques.
- [#76](https://github.com/faudard/drawTemp/pull/76) : atlas de bâtiments, fusionné dans la base auditée.
- [#77](https://github.com/faudard/drawTemp/pull/77) : atlas de fortifications, fusionné dans la base auditée.
- La recherche GitHub des PR ouvertes lors de l'audit n'en retourne aucune.
  La nouvelle branche part directement de master ; aucune branche empilée requise.

## Inventaire artistique réellement présent

| PNG embarqué | Dimensions / découpes | Transparence / ancrage |
| --- | --- | --- |
| `content/art/iso/terrain.png` | 1536×48 ; 16 frames 96×48 ; 8 sols × 2 variantes | RGBA, alpha 0–214 ; losange de terrain, largeur affichée = 2×cell_size |
| `content/art/iso/props.png` | 1152×128 ; 12 frames 96×128 | RGBA, alpha 0–255 ; pied au centre de case, échelle source 54 |
| `content/art/iso/buildings.png` | 2100×220 ; 6 frames 350×220 | Palette transparente ; sommet nord (175,22), échelle source 36 |
| `content/art/iso/fortifications.png` | 2700×250 ; 6 frames 450×250 | Palette transparente ; sommet nord (210,24), échelle source 36 |
| `content/art/jeanne/jeanne_atlas.png` | 256×512 ; 32 frames 64×64 | RGBA ; 4 directions × 8 poses, découpe dans `jeanne.game.json` |
| Jeanne : portrait et 4 expressions | 256×256 et 192×192 | Opaques intentionnellement ; ne pas les présenter comme sprites détourés |

Les 659 PNG présents ont passé un décodage/vérification Pillow.
Dimensions et alpha relevés sur les fichiers de master ; loaders et
tests PNG vérifient les découpes. Les PNG isométriques forment une première passe
pixel-art. Leur harmonie avec Jeanne manga et la lisibilité aux différents zooms
restent à valider artistiquement ; ne pas qualifier la direction de finale.
`assets/watercolor` ne contient que README/index/registry : **aucun des 88 PNG**.
Les nombreux éléments historiques sous `assets/hero_parts`, portraits et poses
ne constituent pas un catalogue médiéval prêt à placer. Le paquet Python embarque
actuellement les PNG Jeanne et iso, pas toute cette bibliothèque historique.

## Ordre de livraison et dépendances

Complexité relative : S (local), M (plusieurs composants), L (parcours transversal),
XL (contrat architectural et compatibilité). P2 = confort après gates P0/P1.

| Ordre / jalon | Priorité | État du gate à l'audit | Complexité | Découpage de PR / dépendances / preuve exigée |
| --- | --- | --- | --- | --- |
| 1 — 3.7.16 Asset Library & Palette 2.0 | P0 | Partiel | M | **A** catalogue des sols/décors/structures existants, miniatures, recherche, catégories, diagnostic, sélection → placement → undo → sauvegarde. **B** assets du projet et variantes, aperçu ancré à l'échelle de carte, validation des métadonnées. A sans dépendance ; B après A et contrat du registre existant. Gate : petite scène sans JSON, y compris un atlas absent. |
| 2 — 3.7.18 Visual Rendering & Occlusion | P0 | Partiel | L | **A** adaptateur de scène partagé éditeur/Player sans modifier Battle ; même scène et mêmes assets. **B** ordre de profondeur et coupe des bâtiments, hit-test après zoom/scroll/hauteur. **C** profils 32²/64²/128², médiane/p95 et invalidation de caches. Dépend de 3.7.16A, précède l'élargissement artistique. Gate : acteur derrière/dans bâtiment visible et sélectionnable dans les deux vues. |
| 3 — 3.7.17 World & Architecture Builder | P0 | Partiel | L | **A** village de référence reproductible avec sols/rivière/pont/maison/remparts existants. **B** variantes de façades/toits et rotations cohérentes ; traiter la perte de détection après édition. Raccords eau/ponts, relief, copie/miroir/groupes existent déjà. Dépend de rendu 3.7.18A. Gate : village construit graphiquement, revu à trois zooms, sans raccord cassé. |
| 4 — 3.7.19 Character & Object Placement | P1 | Partiel | M | **A** connecter palette aux archétypes/objets existants et aperçus d'animation. **B** interactions/déploiements/événements guidés, références valides. Dépend de 3.7.16B. Gate : 3 familles ennemies, coffre/porte/levier et événement jouables sans JSON. |
| 5 — 3.7.21 Editor UX & Productivity | P1 | Partiel | L | **A** réorganiser outils et inspecteur, états Édition/Playtest explicites ; **B** récupération, favoris et modèles guidés (favoris P2). Undo/redo, sélection/groupes existent : les unifier. Dépend des parcours ci-dessus ; peut avancer par corrections ciblées. Gate : scénario de création chronométré, clavier et annulation de chaque opération. |
| 6 — 3.7.20 Interior & Multi-Level | P1 | Partiel graphique / absent pour étages superposés | XL | **A** coupe/visibilité et mobilier à règles inchangées ; **B** RFC sur vraies connexions multi-niveaux avant tout changement tactique. Terrain actuel : une hauteur par (x,y), pas plusieurs étages superposés. Dépend de 3.7.18/19. Gate : entrée, visibilité, interaction et reprise avec règles documentées. |
| Transversal, fermeture en dernier — 3.7.22 End-to-End Production | P0 avant livraison | Partiel, fermeture bloquée par fidélité Player | L | **A dès maintenant** conserver un scénario témoin et les tests de round-trip. **B final** création siège → Player → save/load → export → lancement hors checkout. Dépend de 16/17/18 et du sous-ensemble 19/21 nécessaire. Les étages superposés ne bloquent pas un siège mono-niveau. Gate : zéro édition JSON manuelle, données identiques après reprise, artefacts et preuves OS conservés. |

## CI, risques et règle de clôture

CI existante : moteur Linux/Windows/macOS × Python 3.10/3.12/3.14 ; distribution
sur les trois OS en 3.12 ; GUI Tk/Xvfb **Linux uniquement**. Ajouter une vérification
graphique Windows/macOS (ou rapport manuel reproductible) avant la clôture finale.
Les tests skipped ne sont pas des validations graphiques. La matrice CI doit être
rapportée avec le SHA réellement testé ; aucun statut vert ne sera supposé.

Ne modifier ni CT, ni IA, ni pathfinding dans les PR de présentation. Préserver
les formats et les empreintes de contenu des anciennes sauvegardes. Les structures
existantes écrivent volontairement des tuiles bloquées/hauteurs : une palette doit
annoncer cet effet, contrairement à un simple PNG de présentation.

Dette prioritaire : éditeur monolithique, deux chaînes de rendu, détection de
structures coûteuse/fragile, style artistique mixte, gates anciennes parfois
restées ouvertes alors que des composants ont été fusionnés. Ce document est la
référence des gates éditeur ; ROADMAP.md conserve l'historique du jeu global.

## Premier lot exécuté

[3.7.16A — palette et correction de réduction Tk](ASSET_PALETTE_3716.md) :
parcours concret, architecture, capture, tests et limites. Les statuts du tableau
restent ceux des gates complètes ; la livraison de ce lot ne ferme pas 3.7.16.
