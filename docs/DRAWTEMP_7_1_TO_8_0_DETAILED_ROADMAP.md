# DrawTemp 7.1 → 8.0 — Roadmap détaillée Creator Engine (R31–R40)

> **Statut : PROPOSITION DE ROADMAP, 19 octobre 2026.** Aucun lot R31–R40 n'est implémenté, fusionné, validé ou livré du seul fait de cette documentation. Les versions 7.1 à 8.0 sont des *cibles de séquencement*, pas des dates ni des engagements commerciaux.
>
> **Dépendance directe :** [Creator Studio multi-genres, R25–R30](DRAWTEMP_MULTI_GENRE_CREATOR_ROADMAP.md) (PR [#289](https://github.com/faudard/drawTemp/pull/289), fusionnée le 19 octobre 2026). Les contrats [R0–R16](DRAWTEMP_5_0_ROADMAP.md) et [R17–R24](DRAWTEMP_5_0_TO_6_0_DETAILED_ROADMAP.md) restent applicables et non supplantés par les nouvelles propositions.
>
> **Vision :** au-delà d'un éditeur de SRPG, fournir un **environnement de création de jeux 2D/2.5D multi-genres** : tactical RPG, action-aventure top-down, RPG classique, metroidvania/plateformer, roguelite et simulation narrative, y compris les hybrides. Références de mécaniques (et non d'assets à recopier) : Final Fantasy Tactics, Zelda, Hollow Knight, Hades, Stardew Valley.

## 0. Décision produit : spécialisé et extensible, pas moteur universel à tout prix

**Ce que DrawTemp doit être :** Studio visuel convivial, auteur unique des documents canoniques, Player portable, simulation headless reproductible, moteur de rendu partagé, outils d'IA/équilibrage/diagnostic et pipeline de publication. Les nouveaux genres se construisent par **capacités réutilisables et composition de scènes/règles** ; le projet ne se divise pas en cinq moteurs concurrents.

**Ce que DrawTemp n'est pas dans R31–R40 :** moteur 3D AAA complet, moteur réseau massivement multijoueur, éditeur universel de shaders arbitraires, service cloud obligatoire, clone de jeux existants, promesse de compilation console. Une étude de faisabilité peut suivre R40 ; aucune release ne dépend de ces ambitions.

**Conserver les atouts acquis :**
- tactical Core headless, initiative CT/seed/replay, combats de siège et campagne Jeanne ;
- jeu libre top-down, action temps réel, RPG classique et transitions multi-modes R25–R30, sous réserve que les gates soient réellement démontrés ;
- Qt 6/PySide6 Studio/Player, Qt Quick renderer partagé, Content/GameProject/Asset Registry, AuthoringSession, preview/apply, transactions Undo/Redo, GameSession, sauvegardes atomiques, licences et export ;
- compatibilité des anciens jeux/missions/sauvegardes ou migration explicite et réversible. Aucun changement de profil ne doit transformer silencieusement une partie CT en physique temps réel.

### 0.1 Définition des priorités et statuts

| Code | Sens |
|---|---|
| P0 | Indispensable au *gate du lot*, bloque sa certification |
| P1 | Nécessaire au produit complet, peut être livré dans un lot ultérieur explicitement |
| P2 | Extension optionnelle, non requise pour le gate cible |
| Statuts | PROPOSÉ → CODE EN PR → INTÉGRÉ SUR MASTER → TESTS VERTS SUR SHA FINAL → VALIDATION UX/GPU/ART → RELEASE CERTIFIÉE |

**Definition of Done par sous-lot :** comportement observé + documentation et migration + cas nominaux/erreurs/annulations + tests headless/Qt onscreen/visuels/GPU réel selon le sujet + conservation des documents + rapport sur le SHA de master + limites connues. Les chiffres sont des **budgets proposés à étalonner**, jamais des résultats mesurés par ce document.

## 1. Architecture cible et contrats transversaux

### 1.1 Modules et frontières

| Couche | Responsabilité | Invariant |
|---|---|---|
| Project/Profile | Capacités de genre, scène, inputs et HUD versionnés | Un profil inconnu donne une erreur explicite |
| Content/GameProject | Entités, scènes, composants, ressources, graphes, règles et versions | Une seule vérité métier, migrations transactionnelles |
| AuthoringSession | Création/édition visuelle, preview/apply et Undo/Redo inter-ateliers | Pas d'écriture cachée du runtime |
| Core headless | Tick logique, événements, RNG, CT, action, physique 2D, world sim, IA | Aucun import Qt / frame-rate indépendant |
| Runtime orchestration | GameSession, scènes/modes, quêtes, inventories, persistence/replays | Transitions atomiques, récompenses au plus une fois |
| Shared renderer | Qt Quick 2D/top-down/2.5D iso, caméras, lumières, FX et picking | Studio/Player obtiennent la même projection |
| Creator tooling | Script Graph, Map/World/Platform, animation, IA, ProcGen, labs | Chaque action possède test et diagnostic |
| Distribution | Bundles PC, manifests, licences, formats, versions | Player fonctionne sans Studio/Python dev |

### 1.2 Visual scripting : contrat d'exécution

- Nœuds typés de données (booléen, entier borné, réel contrôlé, vecteur, entité, référence de scène, événement, ressource), ports explicites et validation statique.
- Deux flux distincts : **événements/actions** et **expressions pures** ; chaque effet, timing, RNG, mouvement, spawn et sauvegarde passe par une capacité autorisée et journalisable.
- Compilation/normalisation d'un graphe versionné vers une représentation exécutable *bornée* et inspectable ; **pas de eval/exec arbitraire**, d'accès fichiers/réseau OS ou d'import Python libre dans un jeu non fiable.
- Budget par tick (nœuds/événements, profondeurs, allocations et retries), détection de cycles infinis, annulation, sandbox des extensions ; erreur de graphe visible plutôt que freeze.
- Déterminisme : identifiants stables, ordre de dispatch, horodatage tick logique, seeds, snapshot de version et diff de replay. Les capacités temporelles non déterministes sont rejetées ou explicitement non rejouables et hors gameplay certifié.
- Graphes intégrés **au modèle d'événement R9 et à GameSession**, pas un second moteur de quêtes. Convertir l'existant par migration auditable et retour arrière.
- API ABI/semver des nœuds : ID stable, schéma versionné, palette de catégories, contrat des ports, migration, tests golden de graphes, erreur lorsque le plugin manque.

### 1.3 Physique, gameplay et replays

- Monde libre : pas d'intégration de physique avec delta temps d'affichage ; cadence fixe et ordre collision/trigger/effet versionnés.
- Grille CT : inchangée. Les composants physiques n'affectent pas le temps tactique ni les formules de combat existantes sans activation explicite.
- Un moteur 2D existant sous licence compatible peut être évalué **par benchmark et ADR** ; l'adaptateur doit respecter le Core headless, la persistance et les plateformes. Ne pas ajouter par défaut une dépendance externe native opaque.
- Les collisions/picking et hitboxes du gameplay utilisent des formes et coordonnées stables ; l'interpolation du renderer n'altère jamais le contact physique.
- Save/load/replay des entités, moteurs d'IA, règles de monde et RNG en états finis : hash validé et refus explicite pour données incompatibles.

### 1.4 Sécurité, droits et extensibilité

- Extensions, packs d'assets, graphes, shaders, import ZIP et templates restent déclaratifs, à ressources bornées et chemins confinés ; permissions explicites à toute capacité à risque.
- Chaque asset a provenance, empreinte, licence et droits de redistribution/modification. Tout export public échoue si les droits requis restent inconnus.
- Collaboration = Git ou diffs sémantiques de documents canoniques, **pas** fichier d'état parallèle ou fusion silencieuse de deux éditions concurrentes.
- Opt-in pour toute génération assistée (R38) ; aucune modification de contenu appliquée sans aperçu, Undo et attribution/licences conformes.

## 2. Releases, dépendances et chemins critiques

| Release cible | Lot | Produit livré et gate de sortie | Ordre |
|---|---|---|---|
| 7.1 | R31 — Game Logic Studio | Logique d'événement visuelle sûre, testable et réutilisable | Dépend R9/R24/R28/R30 |
| 7.2 | R32 — Physics & Movement | Plateforme physique 2D stable sans altérer CT | Dépend R25/R26/R31 |
| 7.3 | R33 — Platformer & Metroidvania | Jeu de plateformes exploratoire complet sans JSON | Dépend R32/R27/R31 |
| 7.4 | R34 — Procedural & Roguelite | Génération seedée validée, progression run/meta | Dépend R31/R27/R33 selon modèle |
| 7.5 | R35 — Living World Simulator | Routines PNJ, factions, monde réactif | Dépend R27/R31 ; indépendant de R34 |
| 7.6 | R36 — Animation & VFX Studio | Pipeline visuel unifié et renderer optimisé | Dépend R19/R28/R32 ; peut avancer en parallèle |
| 7.7 | R37 — Advanced AI Studio | IA visuelle, débogable, compatible temps réel et CT | Dépend R13/R26/R31/R35 |
| 7.8 | R38 — Creator Tools Pro | Productivité, tests, collaboration et gros projets | Dépend R22/R29/R31/R37 ; tranches parallèles |
| 7.9 | R39 — Publishing Everywhere | PC/handheld qualifiés + évaluations Web/mobile | Dépend R29/R36/R38 ; licences et clean-machine |
| 8.0 | R40 — Creator Engine Certification | Plusieurs jeux de genres distincts livrables | Tous gates P0, UX/hardware/licensing |

**Dépendance bloquante :** *ne pas démarrer la certification R31+* avant présence réelle sur master des capacités R25–R30 nécessaires, avec suites de non-régression. Les prototypes indépendants peuvent être explorés plus tôt, mais ne sont pas des features livrées. R35 et R36 peuvent se développer en parallèle de R34 après les contrats communs ; R39 exige les artefacts construits depuis un même SHA.

## 3. R31 — Game Logic Studio (7.1)

**But :** programmation visuelle expressive sans exposer le projet à des scripts arbitraires ni dupliquer l'Event Graph existant.

| ID | P | Livrable vérifiable | Dépendances et tests |
|---|---|---|---|
| R31.1 | P0 | ADR Visual Graph ↔ R9 Event Graph, capacités, types, modèle d'état | R9/R24 ; revue et fixtures |
| R31.2 | P0 | Schéma de graphe et nœuds versionnés, migrations, IDs stables, références typées | R1/R16 ; roundtrip |
| R31.3 | P0 | Éditeur de nœuds (créer, relier, copier, grouper, rechercher) avec Undo/Redo atomique | R18/R22 ; QTest souris/clavier |
| R31.4 | P0 | Typage de ports, expression pure, erreurs de connexion, diagnostics de références | R31.2 ; corpus invalide |
| R31.5 | P0 | Runtime borné et déterministe (budget/tick, dispatch ordonné, boucle interdite) | R25 ; seeds/replays/fuzz |
| R31.6 | P0 | Nœuds gameplay : entrée, interaction, conditions, variables, portes, inventaire, combat, quêtes | R8/R9/R26/R27 ; E2E |
| R31.7 | P0 | Nœuds flux : branches, séquences, attentes de ticks, déclenchements/annulations | R31.5 ; tests timing |
| R31.8 | P0 | Debugger : breakpoint, pas-à-pas, pins/état, trace causalité, erreur utile | R13/R31.5 ; replay ciblé |
| R31.9 | P1 | Fonctions et sous-graphes réutilisables, signatures, versions, dépendances | R24 ; migration refs |
| R31.10 | P1 | Variables de portée local/scène/campagne, observabilité et invalidation sûre | R10/R25 ; save/load |
| R31.11 | P0 | Galerie de graphes de référence + sandbox des actions dangereuses | R23/R29 ; test sécurité |
| R31.12 | P0 | E2E Studio→Player : PNJ → porte verrouillée → combat → coffre → quête terminée | Tous P0 ; zéro JSON |

**Gate R31 :** un auteur branche et teste le scénario sans code ; interruption et reprise produisent les mêmes événements, aucune boucle malformée ne fige le Studio ou le Player, les événements tactiques existants restent compatibles.

## 4. R32 — Physics & Movement (7.2)

**But :** ajouter des règles de mouvement et de collisions adaptées aux platformers sans remplacer le système SRPG.

| ID | P | Livrable vérifiable | Dépendances et tests |
|---|---|---|---|
| R32.1 | P0 | ADR sur adapter physique 2D et budgets, comparaison build/licences/API | R25/R26 ; benchmark |
| R32.2 | P0 | Colliders : AABB, segments, polygones simples, layers/masks, triggers | R32.1 ; tests unitaires |
| R32.3 | P0 | Corps cinématiques et dynamiques, gravité, accélération, friction, vitesse max | R32.2 ; trajectoires déterministes |
| R32.4 | P0 | Contrôleur plateforme : marche, course, saut, chute, réception, coyote time optionnel | R32.3 ; tests frames |
| R32.5 | P0 | Collision continue ou subdivision bornée empêchant tunneling dans cas validés | R32.3 ; fast mover |
| R32.6 | P0 | Plateformes mobiles, sens unique, pentes/escalades choisies par profil | R32.4 ; tests collisions |
| R32.7 | P0 | Capteurs sol/mur/eau et interaction avec déclencheurs R31 | R31 ; gameplay |
| R32.8 | P0 | Outils de collision Studio : formes, snapping, layers, debug overlay, édition undo | R5/R18 ; Qt E2E |
| R32.9 | P1 | Objets poussables, rebonds, zones de vitesse/vent, contraintes simples | R32.3 ; stress |
| R32.10 | P0 | Synchronisation hitboxes/hurtboxes, impacts, collisions et animations sans double vérité | R26/R28 ; frame-step |
| R32.11 | P0 | Reprise/replay : état physique sérialisé, même résultat à FPS différents | R25/R17.7 ; hashes |
| R32.12 | P0 | Benchmark cartes/platformers, charges de contacts, courbes p95/p99 | R14/R29 ; CI+hardware |

**Gate R32 :** un personnage traverse une salle, saute sur une plateforme mobile, actionne un interrupteur et revient après save/load à la même position/état ; rendu 30/60/120 FPS ne change pas le résultat simulé.

## 5. R33 — Platformer & Metroidvania (7.3)

**But :** première preuve que DrawTemp crée des jeux hors RPG tout en conservant l'ergonomie visuelle et les outils existants.

| ID | P | Livrable vérifiable | Dépendances et tests |
|---|---|---|---|
| R33.1 | P0 | Profil de genre Platformer/Metroidvania, defaults input/physique/caméra/HUD | R25/R32 ; migration |
| R33.2 | P0 | Side-view Tile/Room Editor et calques de collisions, niveaux superposés | R5/R27 ; peinture/undo |
| R33.3 | P0 | Room Graph / monde connecté, points de spawn, portes, bornes de caméra | R27 ; validation références |
| R33.4 | P0 | Compétences de mobilité : double-saut, dash, wall-jump (capacité/config) | R31/R32 ; tests combinaisons |
| R33.5 | P0 | Progression en capacités/déblocages et portes de capacité déclaratives | R8/R10/R31 ; chemins |
| R33.6 | P0 | Checkpoints, mort/respawn, réapparition ennemis avec politique explicite | R25/R32 ; save/load |
| R33.7 | P0 | Combat plateforme : hitboxes, projectiles, patterns, invincibilité, attaques lisibles | R26/R32 ; replay |
| R33.8 | P0 | Exploration : carte révélée, zones visitées, secrets, téléporteurs | R27/R31 ; state |
| R33.9 | P1 | Caméra avancée (zone/anticipation/transition), shake limité, réduction des effets | R36 précoce/R32 ; UX |
| R33.10 | P1 | Inventaire, objets de soin et collectibles liés aux quêtes | R8/R9 ; récompenses uniques |
| R33.11 | P0 | Solveur/checker de reachability tenant compte des capacités acquises | R27/R31 ; aucun verrou involontaire |
| R33.12 | P0 | Template et tutoriel « 3 salles, 2 capacités, 1 boss » utilisables sans code | R18/R28 ; novice |

**Gate R33 :** un testeur crée depuis un projet vierge un monde de 3 salles ; récupère le double-saut ; ouvre une route auparavant inaccessible ; bat un boss ; sauvegarde, reprend et exporte. Le contrôle des softlocks doit explorer les états de capacités et de portes.

## 6. R34 — Procedural Generation & Roguelite (7.4)

**But :** permettre la génération reproductible de runs tout en conservant un éditeur utile aux concepteurs.

| ID | P | Livrable vérifiable | Dépendances et tests |
|---|---|---|---|
| R34.1 | P0 | Schéma de recette générative (seed, règles, contraintes, versions, assets, sortie) | R24/R31 ; validation |
| R34.2 | P0 | Générateur graphes de salles avec entrée, objectif, sortie et branches | R27 ; connectedness |
| R34.3 | P0 | Bibliothèque de salles/prefabs tagués, compatibilité des portes et biomes | R24/R27 ; références |
| R34.4 | P0 | Placement borné ennemis/loot/rencontres selon budget et courbe difficulté | R13/R26 ; distributions |
| R34.5 | P0 | Algorithme et diagnostics pour éviter runs impossibles (clés, portes, capacités, accès boss) | R27/R33 ; recherche |
| R34.6 | P0 | Preview seed dans Studio, explication des refus, batch seeds et export de repro | R13/R31 ; GUI |
| R34.7 | P0 | Run state : seeds, étage, inventaire run, mort/restart, checkpoints/version | R25 ; replay/save |
| R34.8 | P0 | Progression persistante meta séparée des ressources temporaires du run | R10/R25 ; cohérence |
| R34.9 | P1 | Tables de loot pondérées et équilibrage visualisé, RNG contrôlé | R8/R13 ; statistiques |
| R34.10 | P1 | Templates : dungeon crawler top-down, roguelite tactique ou action | R28 ; auteur |
| R34.11 | P0 | Rejet explicite de recettes incohérentes, limites CPU/mémoire/temps, annulation | R14/R31 ; fuzz |
| R34.12 | P0 | Acceptance : centaines de seeds répétées et rejouées, contre-exemples archivés | R13/R29 ; corpus |

**Gate R34 :** un éditeur génère 100 runs de référence avec mêmes seeds → mêmes cartes/récompenses ; au moins une route complète vérifiée par run selon les contraintes déclarées ; mort et reprise respectent les règles meta, sans récompenses dupliquées. Le nombre de seeds de certification complète doit être étalonné.

## 7. R35 — Living World Simulator (7.5)

**But :** créer des mondes RPG réactifs sans simuler inutilement une ville entière hors champ.

| ID | P | Livrable vérifiable | Dépendances et tests |
|---|---|---|---|
| R35.1 | P0 | WorldClock calendrier/heure/ticks et stratégie de pause explicités | R25/R31 ; replay |
| R35.2 | P0 | Schedules PNJ (lieux, activité, exceptions, conditions de quête) éditables | R31/R27 ; GUI |
| R35.3 | P0 | Déplacement PNJ et navigation hors focus par approximation contractuelle documentée | R26/R27 ; convergence |
| R35.4 | P0 | Relations/factions/réputation avec conséquences persistantes | R9/R10 ; transitions |
| R35.5 | P0 | Quêtes quotidiennes et événements calendaires sans loops ni doubles récompenses | R31/R35.1 ; edge cases |
| R35.6 | P1 | Cycle jour/nuit, lumière/météo gameplay opt-in, effets visuels cohérents | R36/R19 ; QA |
| R35.7 | P1 | Marchands, stocks simples, achats/ventes, économie locale contrôlée | R8/R10 ; anti-duplication |
| R35.8 | P1 | Artisanat et ressources consommables, recettes vérifiées, historique d'inventaire | R8 ; intégrité |
| R35.9 | P0 | Debugger timeline monde, traces de changement d'état, retour arrière en playtest | R13/R31 ; replay |
| R35.10 | P0 | Budget de simulation à distance, granularité variable sans divergence observable | R14 ; profiling |
| R35.11 | P0 | Événements concurrents/sauvegarde à minuit, disparition PNJ, conflits de routage traités | R17/R31 ; stress |
| R35.12 | P0 | Vertical slice village : 4 PNJ, boutique, deux horaires, quête sensible à la réputation | Tous P0 ; auteur |

**Gate R35 :** un PNJ ouvre une boutique à l'heure prévue, quitte son poste, réagit à une action du joueur et conserve son état après changement de zone/reprise. La politique de simulation hors focus est testable et expliquée.

## 8. R36 — Animation, Lighting & VFX Studio (7.6)

**But :** passer des sprites et séquences séparées à un pipeline d'animation/effets productif, performant et cohérent.

| ID | P | Livrable vérifiable | Dépendances et tests |
|---|---|---|---|
| R36.1 | P0 | Animation Controller versionné : états, transitions, conditions, clips, priorités | R7/R28/R31 ; save/replay |
| R36.2 | P0 | Timeline sprites/squelettes 2D si retenus, événements d'impact et surfaces hitbox | R28/R32 ; preview |
| R36.3 | P0 | Éditeur courbes/frames/events, scrubbing et undo transactionnel | R11/R18 ; Qt |
| R36.4 | P0 | Pivots, directions, variations d'équipement, atlas et sprites de production | R4/R7/R19 ; goldens |
| R36.5 | P0 | Particules CPU/GPU avec budget et fallback visuel fidèle (non tactique) | R3/R14 ; GPU réel |
| R36.6 | P1 | Lighting 2D et occlusion choisie par profil, faible coût et paramétrage | R3 ; comparatifs |
| R36.7 | P1 | FX météo/eau/fumée et postprocess contrôlé, compatibilité top-down/iso/side | R19/R35 ; bench |
| R36.8 | P0 | Synchronisation logique/visuel : impact et hitbox même événement tick, rendu interpolé | R25/R32 ; replay |
| R36.9 | P0 | Performance : atlas batching, cache borné, culling, dirty regions, profils GPU | R3/R29 ; p95/p99 |
| R36.10 | P1 | Préférences a11y : réduction flashes/shake, contraste et HUD prioritaire | R18 ; audit |
| R36.11 | P0 | Asset Registry/manifest licences pour VFX/animations/shaders, export fail-closed | R4/R23 ; droits |
| R36.12 | P0 | Parité visuelle Studio/Player et goldens approuvés multi-DPI/backends | R14/R29 ; captures |

**Gate R36 :** créer une animation attaque / esquive / impact / mort dans le Studio et la voir identique dans Player action et dans les usages tactiques compatibles, avec hitboxes exactes et profilage matériel sans faux vert offscreen.

## 9. R37 — Advanced AI Studio (7.7)

**But :** rendre les décisions ennemies conçues, expliquées et testables, sans boîte noire.

| ID | P | Livrable vérifiable | Dépendances et tests |
|---|---|---|---|
| R37.1 | P0 | Contrat AI Decision Context et blackboard versionné, état sérialisable | R13/R31 ; tests |
| R37.2 | P0 | Behavior Trees visuels : séquences/sélecteurs/décorateurs bornés, debugging | R31 ; QTest |
| R37.3 | P0 | Utility AI scorings avec pondérations/exclusions explicables | R13/R26 ; traces |
| R37.4 | P0 | Perception : vision/cônes/bruit/LOS/alertes/temps de mémoire contrôlés | R26/R32 ; replay |
| R37.5 | P0 | Pathfinding par monde : grille tactique, nav 2D et traversée de plateforme via adaptateurs | R6/R27/R33 ; benchmark |
| R37.6 | P0 | Coordination : rôles, protection, encerclement, fuite, appels de renfort | R21/R26 ; simulations |
| R37.7 | P0 | Boss Composer : phases, patterns, télégraphies, fenêtres de vulnérabilité | R26/R33/R36 ; combat |
| R37.8 | P0 | IA sûre : pas de boucles non bornées, budget tick/action et fallback justifié | R31/R35 ; fuzz |
| R37.9 | P0 | AI Debugger : décisions, score, perception, prochaine action, contexte spatial | R13/R31 ; rapport |
| R37.10 | P1 | Batch balance et heatmaps multi-genres liées au replay exact | R29/R34 ; analyse |
| R37.11 | P0 | Dataset et tests de régression tactique Jeanne et aventure/plateformer | R21/R26/R33 ; CI |
| R37.12 | P0 | Boss multi-phase créé dans le Studio, IA inspectée lors d'un playtest | Tous P0 ; auteur |

**Gate R37 :** le créateur peut expliquer avec les diagnostics pourquoi un garde patrouille, poursuit, se replie ou attaque, et reproduire cette décision avec seed + inputs ; les tactiques CT ne changent pas sans modification explicite de profil.

## 10. R38 — Creator Tools Pro (7.8)

**But :** productivité, maintenabilité, validation et partage de gros jeux réalisés dans le Studio.

| ID | P | Livrable vérifiable | Dépendances et tests |
|---|---|---|---|
| R38.1 | P0 | Explorateur/recherche globale entités, ressources, graphes, quêtes, usages | R18/R22 ; index |
| R38.2 | P0 | Prefabs/variants, références, mises à jour contrôlées et overrides affichés | R24/R28 ; roundtrip |
| R38.3 | P0 | Édition de masse et refactor de références typées, preview/apply/undo | R1/R31 ; rollback |
| R38.4 | P0 | Validation temps réel : références cassées, graphes bloqués, portes impossibles, assets illégaux | R27/R31/R34 ; preflight |
| R38.5 | P0 | CI de projets : build/replay/tests automatiques et rapports lisibles non trompeurs | R14/R29 ; SHA |
| R38.6 | P0 | Diff sémantique Content/GameProject, détection de conflits, résolution contrôlée | R24/R30 ; concurrent |
| R38.7 | P1 | Intégration Git optionnelle, review d'assets/docs et versionnement de projet | R38.6 ; cas vrais |
| R38.8 | P0 | Jobs longs annulables, cache invalidation, génération et import non destructifs | R22/R34 ; stress |
| R38.9 | P1 | Profiler Studio/Player : coût graphes, AI, physique, rendu, streaming ressources | R29/R32/R37 ; budget |
| R38.10 | P1 | Batch import/export et templates packagés avec droits attestés | R4/R24 ; roundtrip |
| R38.11 | P2 | Génération assistée opt-in avec propositions diffables, attribution et licences | R38.3 ; sécurité |
| R38.12 | P0 | Test auteur tiers : intégrer des changements conflictuels sans écraser de scène | Tous P0 ; UX observée |

**Gate R38 :** un créateur ouvre un projet à plusieurs cartes/graphes, cherche une référence, réutilise un prefab, renomme un objet sur plusieurs scènes, revient en arrière et résout un conflit externe sans perte de contenu. Aucun « merge automatique réussi » n'est accepté sans comparaison des valeurs.

## 11. R39 — Publishing Everywhere (7.9)

**But :** fiabiliser la diffusion et rendre les plateformes supplémentaires *mesurables*, sans annonces irréalistes.

| ID | P | Livrable vérifiable | Dépendances et tests |
|---|---|---|---|
| R39.1 | P0 | Build Player Windows/Linux/macOS depuis SHA canonique, dépendances/version/licences | R23/R29 ; clean-machine |
| R39.2 | P0 | Projet PC portable (manette, focus, scaling, sauvegarde, plein écran, suspend/reprise) | R25/R33 ; hardware |
| R39.3 | P0 | Export Studio→Player de SRPG/action/metroidvania/roguelite, options explicites | R28/R33/R34 ; 4 E2E |
| R39.4 | P0 | Assets/packs : références, droits, checksums et bibliothèques versionnées | R4/R30 ; gate fail-closed |
| R39.5 | P0 | Mise à niveau de sauvegardes, récupération, rollback, tests corruption et migrations | R17/R25 ; fault injection |
| R39.6 | P0 | QA entrée manette/AZERTY/QWERTY, remapping, UX, a11y, multirésolution | R18/R29 ; vrai matériel |
| R39.7 | P1 | Matrice performances à GPU et plateformes fixés, budgets p95/p99/FPS/mémoire | R14/R36 ; mesures réelles |
| R39.8 | P1 | Étude Web : Qt runtime, taille, sandbox, stockage, APIs et licence ; spike isolé | R3/R23 ; go/no-go |
| R39.9 | P1 | Étude Android/iOS : entrée tactile, lifecycle, APIs, packaging/signatures, limites Qt | R12/R23 ; go/no-go |
| R39.10 | P2 | Canaux de publication (archives/stores compatibles) et métadonnées, conformité, retrait | R23 ; legal/ops |
| R39.11 | P0 | SBOM, provenance builds, checksums, signatures si disponibles et notes de release | R23/R29 ; audit |
| R39.12 | P0 | Install/launch/save/restore depuis machines propres et utilisateurs tiers | Tous P0 ; release report |

**Gate R39 :** quatre familles de jeu fonctionnent en Player autonome PC depuis bundles certifiés ; jeux de contrôles et sauvegardes testés. **Web, mobile et consoles restent conditionnés à des ADR/POC validés** ; pas de support revendiqué sur la seule base d'un spike ni d'un outil de cross-compilation.

## 12. R40 — DrawTemp Creator Engine 8.0 (8.0)

**But :** certifier une plateforme pratique pour produire des jeux distincts, plutôt qu'un catalogue de fonctions sans expérience complète.

| ID | P | Livrable vérifiable | Dépendances et tests |
|---|---|---|---|
| R40.1 | P0 | Stabilisation des APIs/schémas, policy semver, parcours migration 6.x/7.x | R24/R31–R39 ; fixtures |
| R40.2 | P0 | Exemple SRPG Jeanne / siège : contenu éditable et sauvegardes historiques | R17–R30 ; replay |
| R40.3 | P0 | Exemple Zelda-like **original** : village/donjon/puzzles/boss, aucun asset copié | R26/R27/R31/R37 ; export |
| R40.4 | P0 | Exemple metroidvania : plateformes, compétences débloquées, carte/reachability | R32/R33 ; export |
| R40.5 | P0 | Exemple roguelite : runs seedés, progression meta, galerie et debug | R34 ; export |
| R40.6 | P1 | Exemple life RPG/simulation : PNJ, horaires, boutique, quêtes | R35 ; démo |
| R40.7 | P0 | Studio : parcours premier projet par template, guides et données éditables sans JSON | R18/R28/R38 ; novice |
| R40.8 | P0 | Bench et endurance : Core, GUI, GPU, Player, mémoire/fuites, corpus de machines | R14/R29/R39 ; SHA |
| R40.9 | P0 | Export et sauvegarde : multi-OS, clean machine, crash recovery, droits d'assets | R17/R39 ; attestations |
| R40.10 | P0 | Revue accessibilité, ergonomie, artistique et localisation, défauts P0 fermés | R18/R36 ; humain |
| R40.11 | P0 | Dépendances, licences, documentation SDK/plugin, tutoriels et exemples source | R23/R30/R38 ; reviewer |
| R40.12 | P0 | Go/No-go signé : preuves CI, UX, validation réelle et dérogations explicites | Tous R40 ; rapport |

**Gate R40 :** quatre projets originaux de genres distincts (SRPG, action-aventure, metroidvania, roguelite) créés/édités dans le Studio, playtestés, sauvegardables/rejouables lorsque déterminisme requis, exportés et installés sur machines propres. Aucun plugin privé ou modification du Core pour chacun. Le jeu de simulation vivante est un cinquième exemple P1, explicitement optionnel pour le gate 8.0.

## 13. Vertical slices et matrice d'acceptation transversale

| ID | Objet | Studio/authoring | Runtime/QA |
|---|---|---|---|
| VS-31 | Porte intelligente / quête | Créer un graphe « approche → condition → porte → récompense » | Déboguer, rejouer, reprise identique |
| VS-32 | Pièce de plateformes | Collider, plateforme mobile, interrupteur, animation | Simulations indépendantes FPS, save/load |
| VS-33 | 3 salles interconnectées | Double-saut, clé, boss, portes conditionnelles | Vérifier accessibilité avant/après capacités |
| VS-34 | 100 seeds d'un donjon | Génération batch, preview, constraints/rejets | Sortie atteignable, replays stables, pas de dupe |
| VS-35 | Village vivant | PNJ, boutique, horaires, quête de réputation | États conservés hors focus et après reprise |
| VS-36 | Personnage animé | Idle/marche/saut/attaque/hit/death, atlas FX | Hitbox au tick, effets non bloquants |
| VS-37 | Gardes et boss | Behavior Tree, Utility AI, débogage perceptions | Traces de décisions, phases, simulations |
| VS-38 | Édition multi-auteur | Prefab, renommage global, conflit à résoudre | Zero overwrite/undo/references intactes |
| VS-39 | Export sur machine propre | Preflight, licences, manifeste/version | Installation, input, save/restore offline |
| VS-40 | Catalogue démonstrateur | 4 templates et projets complets modifiables | 4 Player indépendants et testeurs externes |

### 13.1 Gates de non-régression historiques

Pour chaque jalon, conserver :
1. Mission tactique Jeanne : CT, RNG, récompenses, replay sauvegarde, restauration, campagne et scènes de siège.
2. Aventure top-down R25–R30 : mêmes entrées logiques et traces sur reprises et FPS différents, collisions/timing.
3. Versionnage Content/GameProject/AssetRegistry et import legacy : pas de données perdues ni de schéma non reconnu silencieusement.
4. Même renderer Qt Quick en Studio et Player, captures goldens revues ; écran offscreen/software != certification GPU.
5. Exports avec ressources disponibles et autorisées ; le Studio ne doit pas masquer un paquet illégal ou incomplet.
6. GUI testée onscreen et parcours créateur réel ; CLI/headless seul ne certifie pas la création visuelle.

### 13.2 Budgets cibles à mesurer, pas assertions

- 60 FPS sur *scènes et GPU étalon choisis*, frame-time p95 ≤ 16,7 ms ; rapporter aussi p99 et spikes plutôt que seule moyenne.
- Geste créateur → réponse visible p95 < 100 ms hors traitement batch ; les traitements longs sont annulables.
- Replays Core identiques entre exécutions, pause/reprise, export et variation 30/60/120 FPS d'affichage.
- Graph scripts/AI/ProcGen : budgets/tick/latence définis par ADR après mesure ; pas de récursion ou monde simulé sans borne.
- Scalabilité : profils comparatifs petite/moyenne/grande cartes, grands graphes, centaines d'ennemis ou de PNJ selon mode et configuration de test ; pas de chiffre de capacité annoncé sans mesure.
- Tests sous Windows/Linux/macOS, Python/Qt/PySide6 et backend versionnés ; mesures GPU physique distinctes de CI software.
- Tests créateurs « nouveau projet → premier jeu jouable » et « modification → retest → export » chronométrés avec obstacles recensés, testeurs externes et procédure reproductible.

## 14. Ordre des PR futures (propositions, non créées)

Ne pas ouvrir une PR de code géante : construire des incréments de petite taille, dépendances explicites et gate à la fin de chaque tranche. Une branche n'est jamais « intégrée au produit » simplement parce qu'une PR a été fusionnée dans une autre branche non présente sur master.

| Séq. | Future PR | Livrable, base et gate |
|---|---|---|
| 1 | R31.A — ADR scripting/capacités | master après R30 : schémas et contrat d'exécution |
| 2 | R31.B — Graph model + typed validation | après A : roundtrip, erreurs de ports |
| 3 | R31.C — Script Graph Editor | après B : Qt UX + Undo/Redo |
| 4 | R31.D — Deterministic executor | après B : budgets/replay/sandbox |
| 5 | R31.E — Gameplay actions + debugger + E2E | après C/D : VS-31 |
| 6 | R32.A — Physics ADR + colliders | master après R31 core : baselines |
| 7 | R32.B — Fixed-step motion + platforms | après A : tests indépendants FPS |
| 8 | R32.C — Collider/Hitbox Studio + recovery | après B : VS-32 |
| 9 | R33.A — Side-view room editor + scene graph | après R32 : outils sans JSON |
| 10 | R33.B — Abilities, gates, saves, reachability | après A : progression sans softlock |
| 11 | R33.C — Template et boss Playtest | après B : VS-33 + export |
| 12 | R34.A — ProcGen recipes + seeded graph | master R31/R27 : seed identique |
| 13 | R34.B — Prefabs + constrained generation | après A : checker reachability |
| 14 | R34.C — Run/meta persistence + lab | après B : VS-34 |
| 15 | R35.A — Clock + NPC schedules | master R31/R27 : snapshots |
| 16 | R35.B — Factions + quests + off-focus | après A : replay |
| 17 | R35.C — World Debugger + village slice | après B : VS-35 |
| 18 | R36.A — Animation Controller / editor | master R28/R31 : state graph |
| 19 | R36.B — VFX/lighting + sync gameplay | après A : replays et QA FX |
| 20 | R36.C — Renderer performance + art certification | après B : GPU réel/goldens |
| 21 | R37.A — AI schema + Behavior Trees | master R31/R35 : décisions lisibles |
| 22 | R37.B — Utility/perception/navigation | après A : replay |
| 23 | R37.C — Boss Composer + AI Debugger | après B : VS-37 |
| 24 | R38.A — Search + prefabs + typed refactor | master R31 : UX |
| 25 | R38.B — Semantic diff + safe conflict resolution | après A : aucune perte |
| 26 | R38.C — CI/validators/profiler + long jobs | après A/B : VS-38 |
| 27 | R39.A — Portable PC export profiles | master R29/R38 : PC propre |
| 28 | R39.B — Input/a11y/save/release QA | après A : matrice hardware |
| 29 | R39.C — Web/mobile feasibility ADRs | indépendante de B, scope séparé : no promise |
| 30 | R40.A — Reference projects + templates | après R33–R38 : 4 jeux source |
| 31 | R40.B — Author tests + QA/licensing/performance | après A/R39 : release evidence |
| 32 | R40.C — Stable 8.0 documentation / Go-No-go | après B : décision explicite |

**Politique de branche :** base master après fusion réelle des prérequis ; PR feature narrow ; rebase/retarget et CI sur SHA final ; migrations et QA dans la même PR que le comportement ; PR documentation initiale distincte de toute promesse d'implémentation. Tous les chantiers parallèles doivent annoncer les chemins de schémas/interfaces qu'ils modifient.

## 15. Registre des risques et décisions à instruire

| Risque / décision | Criticité | Mesure / propriétaire conceptuel |
|---|---|---|
| Visual scripting redondant avec Event Graph | P0 | ADR R31.1 + schéma unique |
| Scripts libres / plugins dangereux | P0 | DSL borné, permissions, aucune exécution Python arbitraire |
| Physique dépendante FPS / divergence entre OS | P0 | Tick fixe, ordre stable, normalisation, replay |
| Ajout platformer dégradant CT Jeanne | P0 | Modes isolés et golden corpus historique |
| Génération de runs impossibles | P0 | Constraints/solveur, rejets et contre-exemples |
| NPC hors focus divergent de reprise | P0 | Politique d'agrégation déterministe |
| VFX détériorant lisibilité/epilepsie/FPS | P1 | Contrôles flash/shake, budgets GPU et a11y |
| IA non explicable, boucle ou coût explosif | P0 | Utility/Tree traces, budgets et fallback explicite |
| Conflits VCS supprimant du contenu | P0 | Semantic diff et validation avant apply |
| Assets packs sans droits | P0 | Export fail-closed licences/hashes |
| Web/mobile/consoles présentés prématurément comme supportés | P0 | ADR de faisabilité uniquement, promesse conditionnée aux preuves |
| Épuisement projet par multiplication des genres | P0 | Slices petites et certification réelle, réduire le scope si besoin |

## 16. Politique de release et horizon R41+

**Conditions NO-GO 8.0 :**
- perte silencieuse de données/compatibilité/sauvegardes ou récompenses dupliquées ;
- jeu dont la logique varie selon le framerate ou la machine sans diagnostic/version explicite ;
- script ou asset importé contournant le sandbox ou les droits de publication ;
- scène visible seulement dans Studio mais non dans Player exporté ;
- jeu démo non créable depuis l'éditeur sans modifier du code ou du JSON ;
- tests headless/software déclarés à tort comme certification physique du rendu/Player ;
- manque d'un des quatre jeux de référence R40.2–R40.5, ou un gate P0 non prouvé.

**Objectif de release :** un auteur installe le Studio 8.0, crée un projet depuis un template, construit un jeu jouable, analyse ses règles et sa performance, l'exporte en Player autonome puis peut le rouvrir et le faire évoluer. La même plateforme permet au minimum : SRPG, action-aventure, metroidvania et roguelite.

**Après 8.0 (R41+) :** sujets d'étude possibles — plateformes supplémentaires (si faisables), nouveaux templates simulation/gestion, outils de collaboration mieux intégrés, tests et assistance à la création, marketplace de packs conformes, scénarios de grands projets. Ils ne sont ni jalons approuvés ni dépendances de 8.0 ; les prioriser à partir d'usage réel et de retours de créateurs plutôt que de spéculer sur une 3D universelle.

**Prochaine étape d'ingénierie :** finir R25–R30 et les gates réels ; ouvrir **R31.A — ADR du visual scripting et capacités du Core** uniquement lorsque les dépendances nécessaires sont sur master. Ce document ne change pas le code de gameplay.
