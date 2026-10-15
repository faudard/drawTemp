# DrawTemp 5.0 — Roadmap de refondation Qt 6

> **Statut :** roadmap cible (proposition structurée, aucun lot 5.0 déclaré livré par ce document).  
> **Date de référence :** 14 octobre 2026.  
> **Dépôt :** [faudard/drawTemp](https://github.com/faudard/drawTemp) — branche principale `master`.  
> **Décision produit :** **Qt 6 / PySide6 pour le Studio et le Player**, **un renderer GPU 2.5D isométrique commun**, **Tactical Core Python headless**.  
> **Références UX :** RPG Maker MZ (ergonomie d'édition), RPG Maker U2U (construction P2D), gameplay tactique propre à DrawTemp.

Ce document définit la **cible DrawTemp 5.0**, et non l'état d'avancement des lots 2.x/3.x. Il complète [ROADMAP.md](../ROADMAP.md) et les docs héritées au lieu de les réécrire. Une fonctionnalité documentée dans le dépôt legacy n'est pas automatiquement marquée « livrée en Qt ». Les priorités sont des **priorités de réalisation**, pas des statuts.

## État d'intégration au 15 octobre 2026 — PR #237 (non fusionnée)

**Suivi de l'implémentation, distinct de la roadmap cible.** La [PR #237](https://github.com/faudard/drawTemp/pull/237) propose une consolidation des PR #224–#236 couvrant R3 à R14 et des correctifs de baseline. Son état **draft** indique que les gates fonctionnels, visuels, CI et de packaging ne sont **pas** réputés franchis. Le fait qu'une branche soit à jour ou mergeable ne constitue pas une certification.

| Périmètre | État d'intégration | Validation nécessaire |
| --- | --- | --- |
| R0–R2 | Fondations déjà présentes sur `master`, certification des parcours toujours à distinguer de la présence de code | Compatibilité, Studio Qt et isolation headless |
| R3–R4 | Code et tests proposés par #237, non certifiés | GPU matériel, scènes identiques et ressources/provenance |
| R5 + R12 | Branchement partagé R3 proposé dans #237 (même `IsoViewport.qml`, `scene_from_mission`, caméra et picking) | CI Qt réelle sur les trois OS et validation visuelle encore exigées |
| R6–R11 + R13 | Implémentations proposées par #237, non déclarées terminées | Flux UI de bout en bout, fichiers partagés, Undo/Redo, replay |
| R14 | Contrôles et matrice multi-OS proposés par #237 | Rapport final et preuve complète; pas de réussite inférée de tests offscreen |
| R15–R16 | Hors périmètre de #237 | Export autonome et retrait du legacy après certification |

### Écarts d'intégration à lever avant fusion

1. **INT-01 — Rendu R3/R5/R12 (code raccordé; certification ouverte).** `IsoViewport.qml` est désormais l'unique composant scène-graph rendu dans R3, R5 et R12. Le Studio utilise `make_controller(scene_from_mission(...))` et reçoit les gestes de peinture via les signaux QML ; le Player utilise `scene_for_player`, alimenté par les snapshots R1, avec un `TacticalBoard.qml` réduit à une façade de compatibilité. `MapDraft.qml` (ancien Canvas) a été supprimé. Même géométrie/picking, profondeur, atlas et caméra R3. Les tests `test_drawtemp5_shared_viewport.py` vérifient le contrat headless et l'instanciation Qt offscreen. **Le gate visuel/GPU réel et les performances restent non certifiés** jusqu'aux preuves multi-OS, textures/animations et scènes à étages.
2. **INT-02 — Propriété des documents.** Les modules Map, Database, Events et Campaign savent partager un `AuthoringSession`. Le `CinematicDocument` de R11 travaille sur une copie du `GameProject`; l'intégration à l'historique transactionnel commun doit être assurée dans le Studio avant de revendiquer des Undo/Redo et des sauvegardes multi-ateliers sûres. Aucun schéma secondaire ne doit être ajouté.
3. **INT-03 — Assets de production (certification fail-closed ajoutée; livraison non validée).** Une PR dédiée ajoute la vérification des 99 vrais PNG (88 originaux + 11 dérivés), leurs SHA-256 et références de sprites/animations, le test de résolution runtime, l'import de pack 99 images ainsi qu'une matrice CI Linux/macOS/Windows. Le producteur GitHub Actions peut publier les 11 PNG sur la branche, mais **la génération n'est pas une preuve de publication**. Le fichier `assets/watercolor/rights.json` reste `pending` tant qu'une licence et les permissions de transformation/redistribution ne sont pas documentées; le gate de release demeure rouge jusque-là. Voir [INT-03](drawtemp5/INT03_ASSET_PUBLICATION.md).
4. **INT-04 — Certification R14.** Les smokes Qt offscreen/software prouvent seulement le chargement du parcours testé, pas les performances GPU, l'identité visuelle ni une release autonome. Conserver les gates fail-closed et joindre les rapports de la matrice du dernier SHA.
5. **INT-05 — Export.** R15 et R16 restent à réaliser : ne pas assimiler la présence d'un lanceur Python à une distribution Player autonome ni supprimer le legacy avant le remplacement vérifié.

### Test de non-régression conjoint ajouté dans #237

`tests_standalone/test_drawtemp5_joint_integrity.py`, invoqué par le workflow R14 sur Linux, Windows et macOS, teste la **même session d'authoring** à travers R5 (carte/bâtiment), R8 (règles), R9 (événement), R10 (campagne), puis l'insertion transactionnelle de R11, une sauvegarde Content/GameProject, la réouverture, et l'utilisation de ces mêmes documents par R12 (Player et reprise de sauvegarde) et R3 (projection de scène). Il vérifie également le rejet d'une prévisualisation obsolète entre deux éditeurs.

**Portée exacte :** cette preuve headless valide le contrat documentaire lorsqu'elle réussit; elle **ne remplace pas** les tests GUI/GPU, ne démontre pas encore le branchement réel du renderer commun et ne certifie pas R15/R16. Toute régression du test bloque désormais le job R14; son succès isolé ne débloque pas INT-01 à INT-05.

## Vision et critères de réussite

Permettre à une personne de **créer puis exporter un RPG tactique narratif complet sans écrire de JSON** : cartes, personnages, classes, objets, événements, dialogues, campagnes, sièges, cinématiques, équilibrage et présentation. L'expérience d'édition doit être proche de RPG Maker en accessibilité, plus ambitieuse sur l'isométrie et le gameplay tactique, avec des outils de production d'assets cohérents.

La qualité est appréciée **de bout en bout** : Studio → jeu compilé/exporté → Player autonome → sauvegarde → reprise. La carte et les assets prévisualisés par le Studio doivent être rendus par **le même moteur** dans le Player.

### Architecture décidée

```text
DrawTemp Studio (Qt Widgets, PySide6)       DrawTemp Player (Qt Quick, PySide6)
         |                                              |
         +-------------- Shared Game SDK ---------------+
         |                    |                         |
         |            Scene/View Models                 |
         +------- Shared Qt Quick GPU Renderer ----------+
                              |
                     Tactical Core Python
             (CT, IA, combats, événements, campagnes)
                              |
            Content / GameProject / Asset Registry
                  (versions & migrations)
```

- **Studio :** `QMainWindow`, docks natifs, vues modèles, inspecteurs, commandes et édition visuelle. Le viewport peut être intégré via Qt Quick, suivant un benchmark de composition.
- **Player :** Qt Quick/QML et PySide6; seules les informations de présentation transitent dans QML.
- **Renderer :** une implémentation de scène isométrique (Qt Quick Scene Graph), texture atlases, batching/chunks/culling, profondeur, animations, picking et overlays. Ne pas présupposer qu'un `QQuickPaintedItem` à grande surface offre le meilleur chemin GPU.
- **Core :** Python sans import PySide6/Tk; déterminisme, replays, règles, validations et migrations testables en headless.
- **Performance :** C++/QRhi envisagé pour le rendu critique seulement après benchmark représentatif, sans créer un second renderer.
- **Compatibilité :** le dépôt actuel annonce Python >=3.10; **Python 3.12 est une cible initiale pour 5.0**, pas une modification immédiate de cette contrainte. Verrouiller les versions Qt/PySide6 testées avant migration.
- **Données :** `Content` et `GameProject` restent les points de départ; évolutions possibles via versions/migrations explicites, sans fichier parallèle de vérité métier.
- **Environnement :** Windows, Linux et macOS. Le Player exporté ne requiert ni Studio ni une installation manuelle de Python.

### Référence du dépôt au lancement

- `master` examiné à `3ad7426c712c5f6a2519a02eee347a9724d79ac3` (14-10-2026).
- [PR #218 — Consolidation Jeanne/Player/Studio/Terrain](https://github.com/faudard/drawTemp/pull/218) **ouverte et non fusionnée lors de la rédaction**, rassemble les dix PR antérieures; sa CI/validation et sa fusion doivent être réévaluées avant de définir le baseline de migration.
- L'éditeur actuel utilise Tk dans `sporebound/editor.py`, `studio_*` et les vues Player historiques; le noyau s'appuie notamment sur `model.py`, `engine.py`, `game_session.py`, `editor_architecture.py`, `persistence.py` et les fichiers `*.game.json`.
- `drawtemp` est déjà le point d'entrée utilisateur; `sporebound` subsiste en namespace technique de compatibilité.
- Le projet de référence doit être **Jeanne d'Arc — Les Cendres du Royaume**, avec prologue, maison, porte/levier, loup, acteur animé, combat, sauvegarde et conséquence narrative.

### Priorités et gouvernance

| Priorité | Interprétation |
| --- | --- |
| P0 | Bloquant pour un jalon, un MVP ou une garantie transverse. |
| P1 | Indispensable pour le produit 5.0 complet, mais peut suivre le premier vertical slice. |
| P2 | Enrichissement différable après stabilisation du socle. |

**Definition of Done commune :** code réel + tests automatisés du niveau concerné + documentation + parcours GUI vérifié pour les interfaces + non-régression Core/Player + mesures de performance lorsqu'il s'agit du rendu + audit migration s'il y a changement de schéma. Aucun simple écran maquette ne valide un lot.

**Règle de migration :** conserver l'ancienne application disponible durant la transition; supprimer les composants Tk uniquement après remplacement testé du parcours équivalent. Ne pas faire dépendre une PR de documentation d'une PR logicielle non fusionnée.

## Index des jalons

| Jalon | Domaine | Priorité | Dépendance principale |
| --- | --- | --- | --- |
| [R0](#r0) | Architecture & Migration Foundation | P0 | Aucune |
| [R1](#r1) | Tactical Core & Game SDK 5.0 | P0 | R0 |
| [R2](#r2) | Qt Application Foundation & Design System | P0 | R0 et interfaces initiales R1 |
| [R3](#r3) | Shared GPU Isometric Renderer | P0 | R1 snapshots, R2 bootstrap |
| [R4](#r4) | Asset Pipeline & Art Direction 5.0 | P0 | R0, contrat R3 |
| [R5](#r5) | Map & World Editor 5.0 | P0 | R2, R3, R4 initial |
| [R6](#r6) | Building & P2D Construction Studio | P1 | R5 et profondeur R3 |
| [R7](#r7) | Character Creator & Animation Studio | P1 | R4, R3 et R8 initial |
| [R8](#r8) | RPG Database & Rules Studio | P0 | R1, R2 |
| [R9](#r9) | Event & Narrative Studio 5.0 | P0 | R1, R2, R5 |
| [R10](#r10) | Campaign, World & Siege Studio 5.0 | P1 | R8, R9, R12 initial |
| [R11](#r11) | Cinematic, Audio & Effects Studio | P1 | R3, R4, R9 et R12 initial |
| [R12](#r12) | Player 5.0 & Tactical UX | P0 | R1 et première tranche R3 (démarrage parallèle à R5) |
| [R13](#r13) | AI, Combat Design & Balance Lab | P1 | R1 et R12 |
| [R14](#r14) | Quality, Performance & Reliability | P0 transversal | Début dès R0; enrichissement sur tous les jalons |
| [R15](#r15) | Export, Packaging & Creator Experience | P1 | R12 jouable et R14 gates |
| [R16](#r16) | Migration finale & Legacy Cleanup | P1 | Tous remplaçants certifiés et R15 packaging |

### Ordre d'exécution (et non ordre d'achèvement de tous les lots)

1. **R0 + R1 + R2** : baseline, SDK indépendant et Studio Qt minimum.
2. **R3 + R4 initiaux** : renderer commun, atlas, géométrie et interactions.
3. **R5 + R12 en parallèle** : carte réellement éditable et immédiatement jouable dans le Player.
4. **R8 + R9 minimum** : personnage/classes, événements et liens du gameplay.
5. **R6, R7, R10, R11** : bâtiments, personnages animés, campagnes et présentation.
6. **R13 et R14 continus** : IA/équilibrage et certification de qualité dès les premières PR.
7. **R15 puis R16** : export fiable, outils de création finalisés et décommissionnement du legacy.

La première valeur produit mesurable est : **ouvrir le Studio Qt → créer/peindre une carte → placer Jeanne → lancer le Player Qt → jouer une action tactique → sauvegarder/recharger**. Ne pas attendre la fin de tous les ateliers pour ce parcours.

## Jalons détaillés

### <a id="r0"></a>R0 — Architecture & Migration Foundation

**Priorité :** P0. **Dépendances :** Aucune.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R0.1 | Repository Baseline | Figer commit, inventaire des PR et résultats CI des systèmes actuels; suivre #218 avant intégration. | P0 |
| R0.2 | Dependency Audit | Cartographier imports Tk, liens runtime/UI, ressources, points d'entrée, API et schémas historiques. | P0 |
| R0.3 | Architecture Decisions | ADR sur Qt Widgets/Quick, renderer, isolation Python, threading, sérialisation et packaging. | P0 |
| R0.4 | Package Boundaries | Définir core, sdk, render, studio, player, assets et platform sans rupture des imports legacy. | P0 |
| R0.5 | Compatibility Contract | Spécifier garanties Content/GameProject, replays, slots et migrations non destructives. | P0 |
| R0.6 | Migration Harness | Exécuter des scénarios équivalents ancien/nouveau et comparer état, RNG, sorties et snapshots. | P0 |
| R0.7 | Reference Project | Sélectionner village, forêt, maison/porte/levier, Jeanne, dialogue, combat et sauvegarde comme fixtures. | P0 |

**Gate R0 :** Baseline déterministe, périmètre de migration connu et scénarios Jeanne de référence prêts.


### <a id="r1"></a>R1 — Tactical Core & Game SDK 5.0

**Priorité :** P0. **Dépendances :** R0.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R1.1 | Core Extraction | Isoler CT, Battle, IA, navigation, campagne, objectifs et règles des dépendances UI. | P0 |
| R1.2 | Simulation API | API publiques load/new_game/start_mission/execute/inspect/save/load et gestion d'erreurs. | P0 |
| R1.3 | State Snapshots | États de présentation immuables, identifiants stables et diff d'événements consommables par l'UI. | P0 |
| R1.4 | Game Events | Événements typés d'action, position, dommage, statut, intention, dialogue et résultat. | P0 |
| R1.5 | Authoring Commands | Preview/validate/commit, transaction atomique, historique Undo/Redo et rejet des versions obsolètes. | P0 |
| R1.6 | Versioned Content | Versions et migrations explicites des schémas; adaptation Content et GameProject existants. | P0 |
| R1.7 | Deterministic Replay | Même seed, ordre CT et consommation RNG; empreintes d'état et tests de relecture. | P0 |
| R1.8 | Persistence SDK | Snapshots, backups, reprises, corruption, écriture atomique et import des versions antérieures. | P0 |
| R1.9 | Threading Boundary | Simulation/validation lourde hors boucle UI, progression, annulation et snapshots non obsolètes. | P1 |
| R1.10 | Developer API | API documentée, exemples, contrat de versionnement et erreurs structurées. | P1 |

**Gate R1 :** Mission jouable en headless, sauvegardée, rechargée et rejouée avec état et RNG identiques; aucun import Qt du core.


### <a id="r2"></a>R2 — Qt Application Foundation & Design System

**Priorité :** P0. **Dépendances :** R0 et interfaces initiales R1.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R2.1 | Qt Bootstrap | Application PySide6, logs, lanceur CLI et fermeture protégée des documents modifiés. | P0 |
| R2.2 | Main Window | QMainWindow, QDockWidget, zones centrale, barres d'outils et menus natifs. | P0 |
| R2.3 | Workspace Navigation | Projet, Carte, Personnages, Base RPG, Événements, Campagne, Cinématiques, Analyse. | P0 |
| R2.4 | Design System | Light/Dark, couleurs, typographie, icônes, espacement, états vides et contrôles partagés. | P0 |
| R2.5 | Resource Explorer | QAbstractItemModel, arbre projets/cartes/ressources, recherche, filtres, favoris et références. | P0 |
| R2.6 | Universal Inspector | Modèles typés, multi-sélection, valeurs mixtes, erreurs et édition transactionnelle. | P0 |
| R2.7 | Docking & Layout | Panneaux réarrangeables, presets de disposition et restauration de la géométrie. | P0 |
| R2.8 | Command Registry | Commandes partagées, actions, raccourcis configurables, menus contextuels et command palette. | P1 |
| R2.9 | Accessibility | Navigation clavier, ordre de focus, contrastes, tailles UI et technologies d'assistance. | P1 |
| R2.10 | Localization | Traductions FR/EN, chaînes externalisées, formats locaux et textes longs. | P1 |

**Gate R2 :** Studio Qt lance Jeanne, navigue entre ressources et restaure ses docks sans Tk.


### <a id="r3"></a>R3 — Shared GPU Isometric Renderer

**Priorité :** P0. **Dépendances :** R1 snapshots, R2 bootstrap.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R3.1 | Scene Graph Foundation | Viewport Qt Quick et interface de rendu partagée, sans gameplay dans QML. | P0 |
| R3.2 | Iso Geometry | Projections monde/écran, cases, altitudes, niveaux, ancrages et transformation inverse. | P0 |
| R3.3 | Camera 5.0 | Pan, zoom, centrage, suivi de cible, bornes et invariance du picking. | P0 |
| R3.4 | Tile Rendering | Batching, atlas, chunks, culling et invalidation régionale des cases modifiées. | P0 |
| R3.5 | Render Layers | Terrain, relief, bâtiments, toitures, unités, objets, effets et overlays. | P0 |
| R3.6 | Depth & Occlusion | Tri spatial, masquage/coupe toiture, visibilité étages et traversées de portes. | P0 |
| R3.7 | Sprite Animation | États, transitions, déplacement, attaques, impacts et timing indépendant du CT. | P0 |
| R3.8 | Visual FX | Eau, feu, météo, particules, ombres et lumières dans le budget GPU mesuré. | P1 |
| R3.9 | Viewport Overlays | Sélections, chemin, LOS, couvert, portée, intentions ennemies et objectifs. | P0 |
| R3.10 | Picking & Hit Testing | Sélection précise cases/acteurs/parties de structures malgré occlusion et échelle. | P0 |
| R3.11 | GPU Resources | Cycle de vie textures, caches, téléchargement, nettoyage et rechargement à chaud. | P0 |
| R3.12 | Renderer Certification | Goldens, tests GPU réels, profilage et équivalence Studio/Player. | P0 |

**Gate R3 :** Même scène Jeanne, mêmes positions, profondeurs et textures dans Studio et Player; caméra fluide; benchmarks enregistrés.


### <a id="r4"></a>R4 — Asset Pipeline & Art Direction 5.0

**Priorité :** P0. **Dépendances :** R0, contrat R3.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R4.1 | Unified Asset Registry | IDs stables, catalogues, types, familles, liens et références versionnées. | P0 |
| R4.2 | Visual Asset Browser | Vignettes, collections, favoris, récents, recherche, aperçu animé, drag-drop. | P0 |
| R4.3 | Atlas Pipeline | Import PNG, atlas, découpe, métadonnées, validation taille/format et cache. | P0 |
| R4.4 | Directional Assets | Schéma poses, directions, pivots, empreintes, tailles et transparence. | P0 |
| R4.5 | Terrain Materials | Herbe, terre, pierre, sable, eau, pavés, route, palettes et raccords. | P0 |
| R4.6 | AutoBlend System | Variantes et raccords automatiques cohérents entre voisins. | P0 |
| R4.7 | Procedural Assets | Génération contrôlée et reproductible des variantes et compositions par seed. | P1 |
| R4.8 | Animated Environment | Herbes animées, drapeaux, feu, fumée, eau et végétation. | P1 |
| R4.9 | Art Consistency QA | Pivots, échelles, palettes, continuité animation et cohérence de rendu. | P0 |
| R4.10 | Asset Migration | Importer catalogues et ressources existants en conservant les identifiants. | P0 |
| R4.11 | Asset Licensing | Provenance, licences, mentions et validation pré-export. | P1 |

**Gate R4 :** Importer terrain et personnage animés, les voir dans les deux applications, sauvegarder et retrouver les mêmes atlas/IDs.


### <a id="r5"></a>R5 — Map & World Editor 5.0

**Priorité :** P0. **Dépendances :** R2, R3, R4 initial.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R5.1 | Map Project Explorer | Arbre de cartes, dossiers, création, duplication, renommage, navigation. | P0 |
| R5.2 | Map Canvas | Viewport GPU, grille, zoom, pan, sélection et niveau actif. | P0 |
| R5.3 | Painting Tools | Pinceau, rectangle, gomme, remplissage, pipette, ligne, sélection. | P0 |
| R5.4 | Smart Brushes | Peinture intelligente, auto-tiling et prévisualisation des voisins. | P0 |
| R5.5 | Visual Tileset Palette | Palette illustrée, filtre matériaux/décors, curseur fantôme et drag-drop. | P0 |
| R5.6 | Layers Workspace | Visibilité, verrouillage, niveaux, opacité et calques métier distincts de profondeur. | P0 |
| R5.7 | Selection & Transform | Multi-sélection, copier/coller, déplacer, dupliquer, rotation, miroir. | P0 |
| R5.8 | Prefabs & Groups | Groupes persistants, sous-éléments, duplications et préfabriqués. | P1 |
| R5.9 | Map Properties | Dimensions, ambiance, météo, musique, interactions et objectif de mission. | P0 |
| R5.10 | Procedural Generation | Biomes, rivières, chemins, ponts, relief et protection de données existantes. | P1 |
| R5.11 | World Integration | Liens de campagne, entrée/sortie, navigation et carte stratégique. | P1 |
| R5.12 | Tactical Overlays | Collision, couvert, LOS, hauteurs, zones dangereuses et déploiement. | P0 |
| R5.13 | Map Diagnostics | Références invalides, obstruction, erreurs de niveau et navigation. | P0 |
| R5.14 | Undo & Live Playtest | Une transaction par geste, preview révisionnée et test immédiat sur carte. | P0 |

**Gate R5 :** Créer et tester un village iso avec rivière, pont, maison, personnages et objectifs, sans JSON.


### <a id="r6"></a>R6 — Building & P2D Construction Studio

**Priorité :** P1. **Dépendances :** R5 et profondeur R3.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R6.1 | Construction Workspace | Mode contextualisé sur même viewport et mêmes commandes de carte. | P0 |
| R6.2 | Direct Geometry Picking | Clic sur toiture, mur, façade, fenêtre, porte et emprise réelle. | P0 |
| R6.3 | Building Footprints | Placement, agrandissement, découpe, édition multicase et contraintes géométriques. | P1 |
| R6.4 | Modular Walls & Roofs | Segments, angles, ouvertures, raccords et styles de toits. | P1 |
| R6.5 | Material Painting | Pierre, bois, torchis, tuiles et palettes de textures par surface. | P1 |
| R6.6 | Terrain Volume Editor | Falaises, rampes, surfaces hautes et continuité des reliefs. | P1 |
| R6.7 | Interior Authoring | Étages, pièces, escaliers, coupes de toiture, sols et mobilier. | P1 |
| R6.8 | Fortifications | Remparts, tours, herses, pont-levis et structures de siège. | P1 |
| R6.9 | Structure Prefabs | Bibliothèque maisons, fermes, tours et compositions personnalisées. | P1 |
| R6.10 | Gameplay Integration | Collision, LOS, entrées et sorties, franchissement des niveaux et états de porte. | P0 |
| R6.11 | Building Visual QA | Sélection, superposition, cutaway, reprise et parité Player. | P0 |

**Gate R6 :** Créer maison deux niveaux, modifier toiture/fenêtres/porte, aménager intérieur, naviguer entre étages, recharger identiquement.


### <a id="r7"></a>R7 — Character Creator & Animation Studio

**Priorité :** P1. **Dépendances :** R4, R3 et R8 initial.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R7.1 | Character Workspace | Liste, variantes, templates, aperçu et édition d'apparence. | P0 |
| R7.2 | Modular Appearance | Corps, visage, cheveux, yeux, accessoires, cape et vêtements. | P1 |
| R7.3 | Color Customization | Palettes de teintes par pièce, transparence, contraintes artistiques. | P1 |
| R7.4 | Directional Compositor | Assembler N/S/E/O, gérer pivots, volumes et offsets cohérents. | P0 |
| R7.5 | Outfit Variants | Jeanne paysanne, apprentie, armure, blessée; identité de personnage unique. | P1 |
| R7.6 | Animation Editor | Timeline, images-clés, onion skin, durée, offsets et playback. | P1 |
| R7.7 | Combat Animation Set | Idle, marche, course, attaque, magie, dégâts, blocage, mort, victoire. | P0 |
| R7.8 | Sprite Sheet Export | Atlas, frames, timings et métadonnées compatibles avec le renderer. | P0 |
| R7.9 | Portrait & Expressions | Portraits, expressions et états de dialogue/cinématique. | P1 |
| R7.10 | Equipment Visualization | Variantes d'armes et tenues liées aux ressources gameplay. | P1 |
| R7.11 | Animation Consistency QA | Silhouette, pivot, durée, continuité des poses et transitions. | P0 |
| R7.12 | Character Library | Villageois, chevaliers, archers, lanciers, loups, monstres et modèles. | P1 |

**Gate R7 :** Créer Jeanne avec tenues paysanne/armure, quatre directions et animations marche/attaque cohérentes, testées dans Player.


### <a id="r8"></a>R8 — RPG Database & Rules Studio

**Priorité :** P0. **Dépendances :** R1, R2.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R8.1 | Database Shell | Arbre/listes et formulaire/aperçu stable, sans modélisation parallèle. | P0 |
| R8.2 | Actors & Archetypes | Personnages, ennemis, monstres, statistiques, instances vs modèles. | P0 |
| R8.3 | Classes & Jobs | Classes, spécialisations, arbres de talents, XP/JP, prérequis. | P0 |
| R8.4 | Skills & Effects | Coûts, portées, zones, statuts, effets multiples et preview. | P0 |
| R8.5 | Equipment & Items | Armes, armures, consommables, valeurs et restrictions. | P0 |
| R8.6 | States & Reactions | Buffs, immunités, réactions, déclencheurs et durée. | P1 |
| R8.7 | Enemy & AI Profiles | Rôles d'IA, stratégies, doctrines et formations. | P1 |
| R8.8 | Troops & Encounters | Équipes ennemies, placements, objectifs et récompenses. | P1 |
| R8.9 | Global Variables | Variables, drapeaux, conditions et recherche par références. | P0 |
| R8.10 | Referential Integrity | Renommage et suppression contrôlés, diagnostics, Undo/Redo. | P0 |
| R8.11 | Resource Preview | Portrait, sprite, effets, caractéristiques calculées. | P1 |
| R8.12 | Bulk Operations | Édition multiple, duplication et recherche/remplacement transactionnels. | P1 |

**Gate R8 :** Créer un Lancier, sa classe, son équipement et sa compétence de protection; valider les références et tester en combat.


### <a id="r9"></a>R9 — Event & Narrative Studio 5.0

**Priorité :** P0. **Dépendances :** R1, R2, R5.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R9.1 | Event Workspace | Créer/ouvrir événement depuis carte, ressources ou graphe. | P0 |
| R9.2 | Event Properties | Déclencheur, position, conditions, répétition, priorité et état. | P0 |
| R9.3 | Visual Command List | Dialogue, choix, variable, objet, mouvement, audio, combat, cinématique. | P0 |
| R9.4 | Condition Builder | Formulaire ET/OU/NON, valeurs typées et feedback sur validité. | P0 |
| R9.5 | Event Pages & States | Variantes, activation, expiration, événements persistants. | P1 |
| R9.6 | Visual Branch Graph | Créer et relier scènes, choix, conditions et actions. | P1 |
| R9.7 | Event Timeline | Programmation, annulation, délais, répétitions et synchronisation. | P1 |
| R9.8 | Map Event Preview | Surimpression des triggers, zones et conséquences sur la carte. | P0 |
| R9.9 | Event Debugger | Pas à pas, valeurs, provenance, trace et replay d'événements. | P0 |
| R9.10 | Cross-Mission Events | Conséquences durables, variables, fronts et campagnes. | P1 |
| R9.11 | Graph QA | Chemins inaccessibles, cycles, références cassées et fins bloquées. | P0 |
| R9.12 | Event Replay Gate | Rejeu déterministe et historique transversal Studio/Player. | P0 |

**Gate R9 :** Porte + levier + condition + dialogue + cinématique: création visuelle, simulation, annulation, sauvegarde et reprise.


### <a id="r10"></a>R10 — Campaign, World & Siege Studio 5.0

**Priorité :** P1. **Dépendances :** R8, R9, R12 initial.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R10.1 | Campaign Explorer | Actes, chapitres, missions, événements et fins. | P0 |
| R10.2 | Mission Graph | Ouvertures conditionnelles, embranchements, dépendances et état. | P0 |
| R10.3 | World Map Editor | Lieux, chemins, connexions, rencontres et points d'intérêt. | P1 |
| R10.4 | Persistent Campaign State | Réputation, ressources, compagnons, blessures et conséquences. | P0 |
| R10.5 | Mission Transitions | Entrée/sortie de cartes, spawn, scènes, récompenses et reprise. | P0 |
| R10.6 | Siege Studio | Fronts, remparts, réserves, renforts, ravitaillement et doctrines. | P1 |
| R10.7 | Multi-Front Timeline | Progression globale, changement de secteur et résolution hors focus. | P1 |
| R10.8 | Campaign Simulation | Parcours, conditions, ressources et conséquences simulées. | P1 |
| R10.9 | Path Certification | Atteignabilité, récurrence, récompenses et fins vérifiées. | P0 |
| R10.10 | Campaign Export | Paquet campagne autonome avec dépendances valides. | P1 |

**Gate R10 :** Trois missions liées, deux décisions, combat et conséquences persistantes; deux fins vérifiées sans JSON.


### <a id="r11"></a>R11 — Cinematic, Audio & Effects Studio

**Priorité :** P1. **Dépendances :** R3, R4, R9 et R12 initial.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R11.1 | Cinematic Editor | Timeline multipiste, plans, acteurs, caméra et transitions. | P0 |
| R11.2 | Camera Tracks | Travelling, zoom, suivi, panoramique et interpolation. | P1 |
| R11.3 | Actor Animation Tracks | Déplacements, poses, expressions et synchronisation des actions. | P0 |
| R11.4 | Dialogue Presentation | Portraits, texte progressif, émotions, choix et transitions. | P0 |
| R11.5 | Audio Studio | Musiques, ambiances, SFX, volumes et fondus. | P1 |
| R11.6 | FX Studio | Particules, lumières, fumée, feu, météo et effets de caméra. | P1 |
| R11.7 | Event Binding | Événement → scène → cinématique → conséquence de jeu. | P0 |
| R11.8 | Timeline Preview | Lecture, pause, seek, vitesse et rendu Player identique. | P0 |
| R11.9 | Audio/Cinematic QA | Synchronisation, interruptions, reprise et intégrité de l'export. | P0 |

**Gate R11 :** Créer introduction Jeanne dans le Studio et la jouer dans Player: caméra, personnages, dialogue, son et transition.


### <a id="r12"></a>R12 — Player 5.0 & Tactical UX

**Priorité :** P0. **Dépendances :** R1 et première tranche R3 (démarrage parallèle à R5).

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R12.1 | Player Foundation | Application Qt Quick autonome consommant GameSession et renderer partagé. | P0 |
| R12.2 | Title & Main Menu | Nouvelle partie, continuer, charger, options, quitter et menu animé. | P0 |
| R12.3 | Campaign Flow | Intro, exploration, dialogue, déploiement, combat, résultats, progression. | P0 |
| R12.4 | Exploration UX | Sélection, déplacements, caméra, interaction et transitions. | P0 |
| R12.5 | Combat HUD | CT, portraits, PV/PM, compétences, objets, réactions et objectifs. | P0 |
| R12.6 | Tactical Feedback | Prévisions, portée, LOS, danger, réactions et intentions ennemies. | P0 |
| R12.7 | Animation Controller | Commandes/états vers animations, interruptions et timing. | P0 |
| R12.8 | Input & Keybinding | Clavier/souris, AZERTY/QWERTY, remapping et modes contextuels. | P0 |
| R12.9 | Menus & Options | Graphismes, audio, interface, commandes et accessibilité. | P0 |
| R12.10 | Save Manager | Slots, autosave, backup, corruption, reprise et conflits. | P0 |
| R12.11 | Cinematic Runtime | Dialogues, transitions, audio et scènes synchronisées. | P1 |
| R12.12 | Accessibility | Taille HUD, contrastes, focus, navigation et préférences. | P1 |
| R12.13 | Combat Presentation | Impacts, déplacements, effets, lisibilité et télégraphies. | P1 |
| R12.14 | Player Polish | Gestion chargements/overlays, interruptions, progression et états sans blocages. | P0 |
| R12.15 | Controller Support | Support manette et profils dédiés. | P2 |

**Gate R12 :** Titre → Jeanne prologue → exploration → combat → résultat → sauvegarde → reprise fonctionne sans Studio.


### <a id="r13"></a>R13 — AI, Combat Design & Balance Lab

**Priorité :** P1. **Dépendances :** R1 et R12.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R13.1 | Tactical Intent System | Attaques, charges, invocations, zones et risque d'interception lisibles. | P0 |
| R13.2 | Coordinated AI | Escouades, soutien, protection de soigneur, repli et objectifs. | P1 |
| R13.3 | Formation Intelligence | Phalange, boucliers, escorte, encerclement et synergies. | P1 |
| R13.4 | Terrain & Floor AI | Hauteurs, couverts, goulots, escaliers, portes et multiétages. | P1 |
| R13.5 | Boss & Elite AI | Télégraphies, phases, multicases et renforts. | P1 |
| R13.6 | Encounter Designer | Placement et objectifs visuels, profils et équipements. | P0 |
| R13.7 | Battle Simulation | Multi-seeds, métriques CT, durées simulées et replays. | P0 |
| R13.8 | Visual Battle Lab | Graphiques, timeline, déplacements, erreurs IA et décisions. | P1 |
| R13.9 | Balance Regression | Comparaison avant/après, seed identique, alertes. | P0 |
| R13.10 | Human Playtest Analytics | Durée humaine, échecs, abandons, incompréhensions; collecte opt-in. | P1 |
| R13.11 | Campaign Balance | XP/JP, économie, équipement et courbe de difficulté. | P1 |

**Gate R13 :** Simulations comparables, écarts explicables, pas de régression majeure de difficulté/déterminisme; playtests humains pour durée réelle.


### <a id="r14"></a>R14 — Quality, Performance & Reliability

**Priorité :** P0 transversal. **Dépendances :** Début dès R0; enrichissement sur tous les jalons.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R14.1 | Cross-Platform CI | Build/test Windows, Linux, macOS et versions Python/Qt fixées. | P0 |
| R14.2 | Core Unit Tests | Règles, IA, événements, sérialisation, déterminisme et migrations. | P0 |
| R14.3 | Qt Integration Tests | Signaux, modèles, focus, raccourcis, UI et transactions. | P0 |
| R14.4 | GUI End-to-End | Parcours réels souris/clavier via driver GUI Qt; tests sur écran et offscreen si pertinent. | P0 |
| R14.5 | Visual Goldens | Références multi-DPI/zoom, tolérances explicites et inspection des écarts. | P0 |
| R14.6 | GPU Profiling | Frame time p50/p95/p99, CPU/GPU, VRAM, fuites et chargements. | P0 |
| R14.7 | Large Map Scale | 32²/64²/128², 24/54/96 px et 80 acteurs visuels. | P0 |
| R14.8 | Long Session Reliability | Sessions longues, journal, autosave et endurance. | P0 |
| R14.9 | Crash Recovery | Interruptions, fichiers partiels, backups et récupération explicite. | P0 |
| R14.10 | Security & Validation | Chemins d'assets, entrées externes, manifests, imports non fiables. | P0 |
| R14.11 | Accessibility QA | Clavier, contrastes, taille UI, focus et lecteurs d'écran. | P1 |
| R14.12 | Release Certification | Rapport, mesures, versions, écarts connus et critères d'acceptation. | P0 |

**Gate R14 :** CI multi-OS, tests déterministes et GUI, goldens, profilage sur GPU réel et rapport de release reproductible.


### <a id="r15"></a>R15 — Export, Packaging & Creator Experience

**Priorité :** P1. **Dépendances :** R12 jouable et R14 gates.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R15.1 | Studio Distribution | Paquets/installations Windows, macOS et Linux. | P0 |
| R15.2 | Player Export | Livrable autonome sans Studio ni environnement développeur. | P0 |
| R15.3 | Asset Packaging | Inclure assets requis, licences, dépendances et hashes. | P0 |
| R15.4 | Project Templates | Projet vierge, RPG tactique, récit et template Jeanne. | P1 |
| R15.5 | Content Validation | Rapport pré-export des ressources, liens, missions et options. | P0 |
| R15.6 | Project Migration UI | Assistant, aperçu, réversibilité, sauvegarde des originaux. | P0 |
| R15.7 | Creator Documentation | Tutoriels, exemples, API et guides Studio. | P1 |
| R15.8 | Plugin & Extension API | Extensions versionnées et contrôlées des éditeurs. | P2 |
| R15.9 | Release Pipeline | Versions, publications, intégrité/signatures selon plateformes. | P1 |

**Gate R15 :** Exporter Jeanne et lancer Player sur machine cible sans Studio ni installation manuelle de Python.


### <a id="r16"></a>R16 — Migration finale & Legacy Cleanup

**Priorité :** P1. **Dépendances :** Tous remplaçants certifiés et R15 packaging.

| Lot | Fonctionnalité | Travail et livrable | Priorité |
| --- | --- | --- | --- |
| R16.1 | Legacy Inventory | Lister les usages résiduels Tk et API de transition. | P0 |
| R16.2 | Project Migration | Conversion versionnée des contenus et sauvegarde originale. | P0 |
| R16.3 | Save Compatibility | Import explicite des slots/replays supportés; avertir des incompatibilités. | P0 |
| R16.4 | Renderer Retirement | Retirer anciens Canvas et chemins de rendu après équivalence. | P0 |
| R16.5 | Studio Retirement | Supprimer les anciens panneaux Tk remplacés et tests obsolètes. | P1 |
| R16.6 | Python Namespace Cleanup | Déprécier l'alias sporebound avec compatibilité transitoire. | P1 |
| R16.7 | Documentation Cleanup | Marquer le legacy, index 5.0 et guides actuels. | P1 |
| R16.8 | Final Regression | Campagnes, goldens, replays, profils, migration et release certifiés. | P0 |

**Gate R16 :** Aucune dépendance Tk dans Studio/Player 5.0 distribué; projets anciens migrés sans perte et avec rollback.

## Jalons de livraison certifiables (M0–M5)

| Release gate | Livrable | Preuve attendue |
| --- | --- | --- |
| M0 — Qt Technical Preview | Studio Qt, une carte Jeanne rendue au GPU, caméra, picking, acteur visible et simulation headless. | Smoke Windows/Linux/macOS, snapshots et captures, benchmark initial. |
| M1 — Studio MVP | Carte créée/peinte, maison/acteur placés, événement simple configuré, playtest lancé. | Parcours utilisateur sans JSON + sauvegarde/reprise/Undo-Redo. |
| M2 — Jeanne Prologue | Jeanne paysanne, village, dialogues, exploration, premier combat et retour campagne. | Démo autonome Qt, aucune dépendance Studio, séquence rejouable. |
| M3 — Jeanne Acte I Demo | Missions reliées, équipements et évolutions, animations, branches et progression persistante. | Playtests humains, qualité artistique, export et rapport CI/visuel. |
| M4 — Castle Vertical Slice | Déploiement, assaut, fronts, renforts, intérieurs, boss, fins alternatives. | Rejeu multi-fronts, saves et QA chemins/fins. |
| M5 — DrawTemp 5.0 | Création complète de jeu, packaging, migration, documentation, performances certifiées. | Garde-fous R14/R15/R16 satisfaits, release notes et bilan. |

M0/M1 sont des jalons techniques et d'authoring, **pas** des démos de production. Un jalon n'est « terminé » que lorsque son gate fonctionne depuis une installation propre.

## Tranches initiales recommandées (petites PR)

| Ordre | PR proposée | Gate |
| --- | --- | --- |
| 1 | `refactor/qt-foundation-r0` | Baseline reproductible, ADR et fixtures Jeanne. |
| 2 | `refactor/core-sdk-r1` | Jeu headless pilotable et rejouable via SDK. |
| 3 | `feat/qt-studio-shell-r2` | Shell Qt, explorateur, docks et chargement projet. |
| 4 | `feat/shared-iso-renderer-r3a` | Iso viewport Qt, pan/zoom/picking. |
| 5 | `feat/shared-iso-renderer-r3b` | Atlas, relief, profondeur, acteurs et goldens. |
| 6 | `feat/asset-pipeline-r4` | Import/affichage atlas existants, mêmes IDs. |
| 7 | `feat/qt-player-foundation-r12` | Même scène affichée par un Player Qt séparé. |
| 8 | `feat/qt-map-editor-r5` | Palette graphique, peinture, Undo/Redo et sauvegarde. |

Créer les PR en dépendances explicites et préférer des lots isolés, vérifiables, qui ne rendent pas `master` inutilisable. Une branche de programme 5.0 peut aider à tester les intégrations, mais **elle ne doit pas remplacer** des PR étroites et révisables. Documenter les bases de PR; ne jamais fusionner une branche empirique contenant des travaux non validés.

## Scénarios utilisateurs d'acceptation

| Scénario | Parcours exigé | Risque fonctionnel vérifié |
| --- | --- | --- |
| Carte village | Créer carte → herbe/eau/chemin → maison/arbres → acteur → playtest. | WYSIWYG, projections, sauvegarde, sélection, Undo/Redo. |
| Générateur Jeanne | Modifier cheveux/yeux → tenue paysanne/armure → quatre directions → animations → export. | Cohérence artistique, atlas, pivots, identité persistante. |
| Porte et levier | Sélectionner porte → associer levier → condition → action → dialogue → test. | Graphes, références, transaction globale, rejeu. |
| Maison à étages | Toiture, fenêtres, porte, intérieur, escalier, acteurs, couches. | Occlusion, géométrie tactique, navigation inter-niveaux. |
| Campagne | Trois missions, bifurcation, blessure persistante, deux fins. | Sauvegarde, transfert, progression, path certification. |
| Siège | Préparation, fronts, vagues, porte, remparts, boss, épilogue. | Multi-front persistence, scripts et IA. |
| Jouer/exporter | Studio → Player → save/load → export → installation propre. | Indépendance du Studio, chemins/assets, migrations. |

## Matrice de performances — hypothèses à calibrer

| Scène de référence | Mesures obligatoires | Cible initiale / politique |
| --- | --- | --- |
| Cartes 32², 64², 128², zooms 24/54/96 px | Frame time p50/p95/p99, CPU/GPU, VRAM, chargement, items visibles. | Viser 60 FPS standard (p95 <= 16,7 ms sur profil cible défini), **à confirmer** sur baseline GPU. |
| 80 acteurs visuels animés | FPS, animation, cache, profondeur/occlusion. | Aucune désynchronisation simulation/rendu; fixer seuils après mesure. |
| Édition normale (brush, Undo, inspector) | Latence geste→retour p50/p95/p99 et mémoire. | Viser p95 <= 100 ms pour commande ordinaire, hors opérations explicitement asynchrones. |
| Prévisualisation procédurale | Durée, annulation, obsolescence, mémoire et mutation. | Un aperçu obsolète ne peut jamais écraser une édition plus récente. |
| Sessions et sauvegardes longues | Latence, taille, reprise, duplication, empreinte replay. | Reprise identique, récupération explicite, pas de récompense dupliquée. |

Les machines, GPU, pilotes, résolution, backend Qt et contenu exact doivent être inscrits dans chaque rapport. L'offscreen logiciel peut tester la fonction; la performance GPU nécessite des tests **sur GPU réel**. Les budgets deviennent bloquants seulement après mesures de référence et décision documentée.

## Risques et atténuations

| Risque | Mesure de maîtrise |
| --- | --- |
| Qt Widgets ↔ Qt Quick coûteux ou fragile | Benchmark d'intégration viewport très tôt (R0/R3), mesurer focus, hi-DPI, resize, composition et GPU. |
| Renderer de Studio différent du Player | Un seul package rendu, snapshots partagés, goldens et scénario de parité systématique. |
| Glissement des modèles `Content` / `GameProject` | Évolutions par migrations, validations croisées et ancien fichier conservé. |
| Réécriture inutile des règles CT/IA | Adapter l'existant au SDK; ne réécrire que sur preuve de défaut ou dette bloquante. |
| Regressions de déterminisme | Même seed/actions, comparer RNG, état et hash; gates CLI indépendants. |
| Animations incohérentes | Pivots/frames/version des atlas contrôlés, goldens et revue artistique. |
| Explosion de l'effort (185 lots) | Vertical slices M0/M1/M2 et priorités P0/P1/P2, aucun gros-bang merge. |
| PR #218/legacy non stabilisé | Vérifier statut, CI et chemin de fusion avant de choisir le commit de migration; ne pas inventer de statut livré. |
| Packaging Qt/Python complexe | Prototype d'export dès M1/M2; tests machine propre sur les trois plateformes. |
| Performances GPU variables | Capturer profil matériel et métriques par backend; éviter de fixer les seuils sans baseline. |

## Références techniques de l'existant

- [Architecture actuelle](../ARCHITECTURE.md), [roadmap legacy](../ROADMAP.md) et [Editor Architecture 2.0](EDITOR_ARCHITECTURE_2.md).
- [Game Studio 4.0](GAME_STUDIO_4.md), [Building Editor 1.0](BUILDING_EDITOR_1_0.md), [Asset Browser](ASSET_BROWSER_COLLECTIONS.md).
- [Character & Rules Studio](CHARACTER_RULES_STUDIO.md), [Campaign Flow](CAMPAIGN_FLOW_R5B.md), [Cinematics](CINEMATICS.md).
- [Combat Design](design/COMBAT_DESIGN.md), [Asset Pipeline](ASSET_PIPELINE.md) et [Player UX](PLAYER_UX_R7.md).
- [PR de consolidation #218](https://github.com/faudard/drawTemp/pull/218) : référence de travaux ouverts, à réexaminer avant démarrage.

## Politique de statut

Pour chaque lot R*, suivre séparément : `non démarré`, `en cours`, `en revue`, `validé` ou `bloqué`; conserver PR, commit, preuves CI, captures et rapport de gate. **Ce document est une roadmap, pas une certification de livraison.** Les gates sont les seuls critères de clôture; la présence d'une classe ou d'une PR ne suffit pas.
