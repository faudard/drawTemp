# DrawTemp — Roadmap Creator Studio multi-genres (6.0 → 7.0)

> **Statut : proposition de produit et de développement, 19 octobre 2026.** Aucun lot R25–R30 n'est considéré comme implémenté par l'ajout de ce document. Les versions sont des jalons proposés et non des dates de livraison.
>
> **Périmètre :** créer sans programmation des jeux **2D / 2.5D** à partir d'un même Studio, d'un Player et de contrats de données versionnés : **SRPG tactique** (inspiration Final Fantasy Tactics / Tactics Ogre), **action-aventure avec exploration libre** (inspiration Zelda), **RPG classique**, **aventure narrative / énigmes**, et **jeux hybrides**. Ces œuvres sont des références de design, pas des contenus à copier.
>
> **Documents complémentaires :** [roadmap canonique 5.0 (R0–R16)](DRAWTEMP_5_0_ROADMAP.md) · [consolidation 5.0–6.0 (R17–R24)](DRAWTEMP_5_0_TO_6_0_DETAILED_ROADMAP.md) · [roadmap historique](../ROADMAP.md).
>
> **Règle :** ne pas transformer DrawTemp en clone de FFT ni en clone de Zelda, ne pas créer de second moteur concurrent. L'éditeur est **multi-genres par composition de capacités et de profils de jeu**. La continuité de Jeanne et du SRPG reste un contrat de compatibilité.

## 0. Décision de produit et périmètre réel

**Positionnement :** DrawTemp Creator Studio est une plateforme de conception, de test, d'équilibrage et d'export de jeux 2D/2.5D narratifs. Son différenciateur est le **même contenu édité, simulé, visualisé, débogué, sauvegardé et exporté**, avec une prise en main de type RPG Maker mais des règles et des systèmes davantage composables.

| Famille de jeu | Déplacement et caméra | Combat et interactions | Exemple d'acceptation |
|---|---|---|---|
| SRPG / tactical RPG | Cases, hauteur, caméra isométrique ou orthographique | CT/tours, actions, orientations, couverture, IA de groupe | Mission Jeanne avec combat tactique, save/replay |
| Action-aventure | Mouvement libre top-down 2D/2.5D, caméra de suivi | Temps réel, collisions, attaque/esquive, ennemis, objets, puzzles | Village → donjon → boss → récompense → retour |
| RPG classique | Exploration top-down, transitions de scènes | Combat au tour par tour ou commandes RPG, inventaire, quêtes | Ville → dialogue → rencontre → récompense |
| Aventure / exploration narrative | Déplacement libre ou point-and-click selon profil ultérieur | Dialogues, interrupteurs, clés, logique d'événements, cinématiques | Puzzle à états persistants et embranchement |
| Hybride | Exploration continue puis transition explicite | Exploration ARPG + rencontre tactique au choix du jeu | Exploration → escarmouche CT → exploration sans perte d'état |

**Hors périmètre initial :** moteur 3D généraliste, MMORPG / multijoueur réseau, jeu de plateforme à physique complexe, monde ouvert géant en streaming continu, moteur de scripts arbitraires non sécurisé. Ces domaines requièrent étude de coût et validation explicite avant toute promesse.

**À ne pas confondre :** un simple changement de caméra ne suffit pas à produire un action-RPG ; le temps réel exige ses propres commandes, cadence, collisions, comportements et UX. Réciproquement, ces systèmes doivent réutiliser la présentation, les ressources, les événements, l'inventaire, la persistance et la publication existants.

## 1. Situation de départ, compatibilité et dépendances

- **R0–R16** : contrats Qt/PySide6, Core headless, rendu partagé, données Content/GameProject, Asset Registry, AuthoringSession, système d'événements, campagne, sauvegarde et QA tels que documentés.
- **R17–R24** : rester le chemin critique déjà spécifié ; R17 fusion/certification, R18 UX, R19 direction artistique, R20 Jeanne, R21 sièges, R22 création sans JSON, R23 distribution, R24 SDK et second jeu. Ces lots restent à vérifier par preuve, pas par titres de PR.
- **Au 19/10/2026** : [#285](https://github.com/faudard/drawTemp/pull/285) (consolidation R17), [#286](https://github.com/faudard/drawTemp/pull/286) (assets/licences) et [#287](https://github.com/faudard/drawTemp/pull/287) (sauvegardes/reprise) étaient ouverts au contrôle ; #286 et #287 sont empilés sur #285. Revalider base, HEAD, CI et présence dans master avant de les fermer.
- **Gate avant changement transversal** : aucun prototype action-RPG ne doit compromettre la déterminisation CT, les replays Jeanne, les migrations, l'export sans Python développeur ou les tests de rendu Studio/Player.
- **Positionnement de R24.9 / R24.12** : le « deuxième univers » devient le premier **témoin inter-genres**. L'objectif de non-fork du Core/renderer demeure ; un prototype Zelda-like peut servir de preuve, mais n'est pas réputé complet avant les gates R25–R28.

## 2. Principes d'architecture non négociables

1. **Une plateforme et un SDK headless** : conserver la logique de domaine hors de Qt ; GameSession reste l'orchestrateur des scènes, campagnes, transitions et sauvegardes. Les différents systèmes de règles sont des modules/capacités enregistrés, pas des applications séparées.
2. **Profil de jeu déclaratif, par projet et par scène** : combinaison explicite de MovementMode (GRID_CT, FREE_REALTIME, éventuellement GRID_TURN), CombatMode (TACTICAL_CT, ACTION_REALTIME, RPG_TURN, NONE), CameraProfile (ISOMETRIC, TOP_DOWN), InteractionProfile et UIProfile. Énumérations *proposées*, non API publique actuelle.
3. **Compatibilité bidirectionnelle contrôlée** : une mission Jeanne sans profil continue à charger avec le comportement tactique historique via défaut de migration versionné ; une scène inconnue échoue explicitement, sans fallback silencieux.
4. **Simulation et présentation séparées** : le Core produit des snapshots d'état et commandes validées ; Studio et Player utilisent le même renderer R3 enrichi de projections/caméras, et le même mapping de picking propre à chaque projection. Ne pas dupliquer les scènes QML par genre.
5. **Temps réel déterministe** : introduire un tick logique fixe et des commandes horodatées en ticks entiers (pas en delta-temps flottant dépendant des FPS), ordre d'événements stable et RNG explicite. Le rendu interpole sans modifier les résultats. Les entrées du joueur, transitions, pauses et changements de scène sont enregistrés pour replay/reprise.
6. **CT conservé et isolé** : dans TACTICAL_CT, règles de CT/ordre/intentions inchangées sauf migration testée. Ne pas forcer le temps réel dans le moteur tactique ; choisir un adaptateur/système de simulation par mode avec contrats partagés.
7. **Données uniques** : étendre Content/GameProject, schémas versionnés, Asset Registry, AuthoringSession, preview/apply et Undo/Redo atomique. Jamais de deuxième base d'objets RPG, de fichier de vérité caché ou de migration destructive.
8. **Événements transversaux** : conditions et actions typées pour portes, interrupteurs, puzzles, dialogues, quêtes, combats, transitions, cinématiques, audio ; une seule sémantique de variables persistantes et de références validées.
9. **Entrées et HUD par profil** : clavier AZERTY/QWERTY, souris, manette (si activée), remapping et accessibilité ; top-down et tactique ne partagent pas forcément les mêmes commandes, mais leurs conflits sont détectés.
10. **Publication sûre** : export Player embarquant exclusivement les systèmes requis par le projet ; licences et hachages d'assets prouvés ; sauvegardes, crash recovery et import strict préservés.

### 2.1 Schéma conceptuel (non implémenté)

Projet → Profils de jeu → Scènes et ressources → Capacités (mouvement, combat, inventaire, événements, caméra) → GameSession / Core headless → Snapshots → Renderer commun → Studio/Player.

Les profils ne sont **pas** des branches irréconciliables du moteur. Un même jeu peut avoir un village en FREE_REALTIME, un donjon action et une bataille TACTICAL_CT. Les conversions de scènes sont explicites et testées ; aucune conversion automatique d'une grille CT vers un monde libre n'est présumée.

### 2.2 Contrats de transition et sauvegarde

- Transition identifiée par source, destination, position d'arrivée/spawn, préconditions et actions post-transition ; validation de toutes les références.
- Contrat de conservation : joueur, groupe, inventaire, équipement, XP, flags, quêtes, portes et coffres, état des adversaires selon politique de respawn, ressources consommées et checkpoints.
- Séparer horloge d'exploration, tick temps réel et compteur CT ; enregistrer la politique de pause lors des menus, dialogues, combats et cinématiques.
- Sauvegarde atomique à frontières définies ; crash entre deux modes → reprise unique cohérente, récompenses non dupliquées, état de mission intact. Replays avec version des règles/seed/commandes et refus explicite si incompatibles.
- Faire coexister anciennes campagnes et nouveaux profils par migrations testées ; ne pas renommer / supprimer les formats historiques avant un gate de compatibilité.

## 3. UX cible : un seul Studio de création

**Shell commun** : Espace projet → Monde/Cartes → Construction/Donjons → Personnages/Bestiaire → Base RPG/Compétences → Gameplay/Règles → Événements/Quêtes → Campagne → Cinématiques/Audio → Labs → Playtest → Export.

| Atelier | Capacités visuelles attendues | Résultat instantanément vérifiable |
|---|---|---|
| Project Wizard | Modèles SRPG, Action Adventure, Classic RPG, Narrative, Hybrid ; dépendances et assets | Projet vierge valide, jouable et exportable |
| Map & World Builder | Peinture 2D, isométrie, relief, calques, biomes, chemins, collisions, régions, caméra, portails | Traverser plusieurs cartes dans le Player |
| Dungeon & Puzzle Designer | Salles, portes, clés, dalles, leviers, coffres, interrupteurs, blocs poussables, séquences d'énigme | Résoudre et persister un puzzle |
| Character & Bestiary Workshop | Portraits, sprites/atlas, animations N/S/E/O, hitbox/hurtbox, comportements, drops, variantes | Ennemi animé, collision et mort correctes |
| RPG & Ability Database | Classes, stats, équipement, capacités, formules, états, progression ; capacité action ou tactique | Tester compétence/arme dans le bon mode |
| Gameplay Profile & Input | Déplacement, caméra, combat, input mapping, HUD, règles de transition | Changer de mode sans casser le projet |
| Event / Quest / Campaign Graph | Pages, variables, branches, priorités, conditions, quêtes, dialogues, cutscenes | Exécuter/déboguer les chemins et conséquences |
| Battle & Gameplay Lab | CT/replay, simulation temps réel, heatmaps, durée réelle de jeu, couverture de scénarios | Reproduire un bug à la seed et aux inputs |
| Publishing Studio | Dépendances, licences, checksums, tests, bundles par OS, release report | Player lancé sur PC propre sans Studio |

**Exigences transversales** : viewport dominant, outils contextuels, inspecteur typé, recherche et références croisées, Undo/Redo inter-ateliers, validations en ligne, états vides utiles, raccourcis, QTest/onscreen, capture goldens et prévisualisation identique au Player.

## 4. Ordre des releases proposées

| Cible | Lots | Produit tangible et gate |
|---|---|---|
| 5.0–5.5 | R17–R23 (déjà définis) | Jeanne SRPG et éditeur visuel, export fiable, certification |
| 6.0 | R24 ajusté par le présent document | SDK/contrats extensibles et preuve d'un **second projet non SRPG** sans fork ; profondeur ARPG encore limitée |
| **6.1** | **R25 — Game Modes Foundation** | Scène d'exploration libre avec profil, transitions, save/replay ; Jeanne inchangée |
| **6.2** | **R26 — Action Adventure Runtime** | Mouvement temps réel, combat simple, ennemis, HUD et manette/clavier |
| **6.3** | **R27 — World & Dungeon Designer** | Village/donjon/puzzles créés et joués sans JSON |
| **6.4** | **R28 — Multi-genre Authoring** | Wizards et ateliers permettant 3 types de mini-jeux |
| **6.5** | **R29 — Gameplay Lab & Publishing** | Certification inter-genres, équilibrage, packaging et onboarding |
| **7.0** | **R30 — Creator Ecosystem & Scale** | Packs, extensions, collaboration et seconde boucle de production répétable |

**Priorité d'ordonnancement :** R17 stable → UX R18/R22 minimum → contrats R24 → R25 → R26 → R27/R28 en parallèle maîtrisé → R29 → R30. Les tests d'export, licences, QA et migration sont continus. On peut prototyper R25 avant la fin de toutes les options P2 de R24, mais jamais contourner les gates P0 de sauvegarde et de données.

## 5. R25 — Game Modes Foundation (6.1)

**But :** rendre l'architecture réellement multi-genres, sans régression tactique.

| ID | P | Livrable et comportement vérifiable | Dépendances / preuve |
|---|---|---|---|
| R25.1 | P0 | ADR de capacités, profils SRPG/Action/Classic/Narrative/Hybrid et frontières d'API | R1/R24 ; revue contrats |
| R25.2 | P0 | Schéma versionné de profils projet/scène, migrations par défaut tactique et rollback | R1/R8/R16 ; fixtures anciennes |
| R25.3 | P0 | SceneRouter + GameSession transitions avec état persistant et spawn validé | R9/R10/R12 ; E2E entre scènes |
| R25.4 | P0 | Horloge de simulation fixe, entrée horodatée, ordonnanceur événement stable | R1 ; replay mêmes hash/états |
| R25.5 | P0 | Contrats de mouvement GRID_CT et FREE_REALTIME, aucun double propriétaire du monde | R1/R6 ; tests mixtes |
| R25.6 | P0 | Projection TOP_DOWN ajoutée au renderer partagé ; ISOMETRIC inchangée | R3/R14 ; picking et goldens |
| R25.7 | P0 | Caméra de suivi/limites/zoom par scène et conversion écran↔monde | R3/R12 ; tests DPI |
| R25.8 | P0 | Profils input/HUD et mapping de commandes, menus et pause | R12/R18 ; QTest/onscreen |
| R25.9 | P0 | Save, crash recovery, checkpoints et replays traversant les modes | R17.7/R23 ; fault injection |
| R25.10 | P0 | Studio édite et lance un projet à 2 scènes de modes différents sans JSON | R22/R24 ; acceptance |
| R25.11 | P1 | Rapport migration / compatibilité CI avec tous les scénarios SRPG de référence | R14 ; matrice SHA |

**Gate R25 :** créer un village à exploration libre et une arène tactique ; y faire passer le même héros avec inventaire/flags préservés, rejouer et restaurer après crash ; les tests de référence Jeanne restent identiques.

## 6. R26 — Action Adventure Runtime (6.2)

**But :** un véritable mode action-aventure au lieu d'une scène tactique jouée plus vite.

| ID | P | Livrable et comportement vérifiable | Dépendances / preuve |
|---|---|---|---|
| R26.1 | P0 | Mouvement continu 4/8 directions, accélération facultative, fréquence indépendante du FPS | R25 ; trajectoires déterministes |
| R26.2 | P0 | Collision statique/dynamique, hitbox/hurtbox, obstacles, triggers et recul | R25/R6 ; tests de contacts |
| R26.3 | P0 | Attaque corps-à-corps, cadence, invulnérabilité temporaire, interruption et feedback | R8/R12 ; scénario combat |
| R26.4 | P0 | Défense/esquive, stamina optionnelle et télégraphie lisible | R26.3 ; traces rejouables |
| R26.5 | P0 | IA d'ennemis temps réel (patrouille, vision, poursuite, attaque, retour, mort) | R13 ; seed + replay |
| R26.6 | P0 | Objets utilisables, loot, équipement et inventaire commun aux jeux tactiques | R8/R10 ; transition modes |
| R26.7 | P0 | Interaction contextuelle : PNJ, coffre, panneau, porte, levier | R9 ; persistence |
| R26.8 | P0 | HUD action : PV, objets/compétences rapides, prompts, pause, menus | R18/R25 ; test utilisateur |
| R26.9 | P1 | Projectiles, portée, collisions, états élémentaires et contre-mesures | R26.2 ; tests |
| R26.10 | P1 | Boss à phases simples et patterns télégraphiés, caméra/action safe | R26.3/R26.5 ; playtest |
| R26.11 | P1 | Audio, animation indépendante idle/walk/attack/hit/dodge et VFX non bloquants | R19/R11 ; revue artistique |
| R26.12 | P0 | Replays d'inputs et autosave action avec corruption/recovery testés | R25/R17.7 ; stress |
| R26.13 | P1 | Support manette avec remapping complet, clavier/souris équivalents | R25.8 ; devices réels |
| R26.14 | P0 | Mini-combat ARPG autonome avec mort/respawn et récompense persistante | R26.1–R26.12 ; bundle |

**Gate R26 :** une scène top-down où le héros se déplace librement, affronte un ennemi, interagit avec une porte/coffre et recharge son état ; le gameplay ne dépend pas du nombre de FPS.

## 7. R27 — World, Dungeon & Puzzle Studio (6.3)

**But :** donner au créateur les outils d'un jeu d'aventure et de donjons complet.

| ID | P | Livrable et comportement vérifiable | Dépendances / preuve |
|---|---|---|---|
| R27.1 | P0 | World Graph : cartes, connexions, entrées/sorties, conditions et minimap | R25/R10 ; références |
| R27.2 | P0 | Éditeur top-down et iso partagé : brushes, calques, autotile, collisions, régions | R5/R3 ; Undo/goldens |
| R27.3 | P0 | Room Builder : salles, portes, intérieur/extérieur, obstacles et propriétés | R6 ; expérience auteur |
| R27.4 | P0 | Puzzle Builder : clés, dalles, pression, blocs, leviers, séquences, resets configurés | R9 ; éditeur visuel |
| R27.5 | P0 | Débogueur d'états d'énigmes, détection d'impasses et playtest depuis sélection | R9/R13 ; contre-exemples |
| R27.6 | P0 | Transitions/cartes et chargement sûr des ressources, téléporteurs/portails | R25 ; save/load |
| R27.7 | P1 | Variantes terrain/biomes, cycles jour/nuit et états persistants de zones | R4/R5 ; cohérence |
| R27.8 | P1 | Navigation ennemis 2D avec obstacles mobiles et zones interdites | R26 ; tests IA |
| R27.9 | P0 | Événements de donjon + quêtes : prérequis, récompenses, dialogues et branches | R9/R10 ; graphe |
| R27.10 | P1 | Template de donjon et prefabs versionnés, références et licences | R4/R24 ; import/export |
| R27.11 | P0 | Création du village + donjon entièrement sans JSON | R22/R26 ; test novice |
| R27.12 | P0 | Certifier softlocks, checkpoints et états de puzzle à travers les scènes | R14/R25 ; parcours automatisés |

**Gate R27 :** créer deux salles et un boss, résoudre une énigme clé/levier/porte, récupérer un objet, revenir au village et constater la persistance des événements.

## 8. R28 — Multi-genre Creator Workflow (6.4)

**But :** faire de ces systèmes des fonctionnalités de Studio, pas seulement des APIs.

| ID | P | Livrable et comportement vérifiable | Dépendances / preuve |
|---|---|---|---|
| R28.1 | P0 | Project Wizard SRPG, Action Adventure, Classic RPG, Narrative, Hybrid | R22/R25 ; projets créés |
| R28.2 | P0 | Inspecteur de profil : mouvement, projection, caméra, combat, HUD et inputs | R18/R25 ; previews |
| R28.3 | P0 | Ability Designer modes tactique/action/RPG avec formule et cible explicites | R8/R26 ; tests |
| R28.4 | P0 | Enemy Designer : capteurs, états, comportements et diagnostics IA | R7/R13/R26 ; traces |
| R28.5 | P0 | Character Animation & Hitbox Studio, preview même runtime | R7/R19/R26 ; overlays |
| R28.6 | P0 | Event/Quest Graph multi-mode, logique accessible dans les deux Player | R9/R27 ; save/replay |
| R28.7 | P1 | UX locale Battle Lab + Action Gameplay Lab : dégâts, décision, difficulté, durées | R13/R26 ; comparaison |
| R28.8 | P0 | Transfert contextuel Studio → Player → Studio sans altérer le document | R22/R25 ; Undo/Redo |
| R28.9 | P1 | RPG classique : combat menu/tour, rencontres et retour exploration, sans simuler CT en accéléré | R8/R25 ; mini-jeu |
| R28.10 | P0 | Trois jeux témoins indépendants créés via Studio, pas via édition de données | R28.1–R28.9 ; test tiers |
| R28.11 | P1 | Documentation/assistant de création par genre, FR/EN, a11y et raccourcis | R18/R23 ; onboarding |

**Gate R28 :** trois auteurs novices réalisent chacun un mini-jeu (tactique, action-aventure, RPG classique) sans programmation et peuvent le modifier puis le relancer. Un échec bloque la certification de l'atelier concerné.

## 9. R29 — Quality, Gameplay Lab & Publishing (6.5)

| ID | P | Livrable et comportement vérifiable | Dépendances / preuve |
|---|---|---|---|
| R29.1 | P0 | Matrice headless déterministe CT + action fixe + RPG tour par tour | R14/R25/R28 ; replays |
| R29.2 | P0 | Comparaison Studio/Player, top-down/iso, multi-DPI, goldens approuvés | R3/R19 ; captures |
| R29.3 | P0 | Import/export/save/recovery avec injections d'erreurs et versions historiques | R17/R23 ; zéro perte |
| R29.4 | P0 | Exports Windows/Linux/macOS sans Studio ni Python développeur | R15/R23 ; VM propre |
| R29.5 | P0 | Licences et provenance de tous assets, refus fail-closed de distribution | R4/INT-03 ; manifeste |
| R29.6 | P1 | Profilage CPU/GPU, frame-time p50/p95/p99, mémoire, stutter par mode | R14/R19 ; matériel réel |
| R29.7 | P0 | Tests utilisateurs comparables par genre, parcours création→jeu→export | R18/R28 ; retest |
| R29.8 | P1 | Replay explorer, débogueur IA, graphe de causes et heatmaps compatibles action | R13/R26 ; diagnostic |
| R29.9 | P0 | Vérification anti-softlock quêtes/puzzles/états critiques (couverture documentée) | R9/R27 ; corpus |
| R29.10 | P0 | Release report par SHA et go/no-go documenté sans faux statut vert | R23 ; audit |

**Gate R29 :** trois mini-jeux installables, sauvegardables et rejouables sur machines propres, licences conformes et test créateur réussi. Les trois modes ne doivent pas nécessairement avoir une richesse équivalente, mais leurs limites publiées doivent être explicites.

## 10. R30 — Creator Ecosystem & Scale (7.0)

| ID | P | Livrable et comportement vérifiable | Dépendances / preuve |
|---|---|---|---|
| R30.1 | P1 | API de capacités + semver + dépréciations contrôlées | R24/R25 ; compatibilité |
| R30.2 | P1 | Packs templates, quêtes, ennemis, terrains, puzzles, HUD, licences versionnées | R24/R28 ; import/export |
| R30.3 | P2 | Extensions Studio sandboxées/capability-based, erreurs isolées | R24 ; sécurité |
| R30.4 | P1 | Diff sémantique pour Content/GameProject et revue des changements | R24 ; roundtrip |
| R30.5 | P2 | Intégration Git / collaboration, conflits résolus sans écraser des scènes | R30.4 ; scénarios concurrents |
| R30.6 | P1 | Graphiques de performance, budget d'assets, scène complexe/long jeu et stress | R29 ; profils |
| R30.7 | P2 | Génération assistée optionnelle de terrains/puzzles avec aperçu et Undo | R27 ; aucun effet caché |
| R30.8 | P1 | Gallery d'exemples : tactique, action-aventure, RPG classique, hybride | R28/R29 ; projets source |
| R30.9 | P1 | Référence SDK, tutos, guides de migration, changelog et examples CI | R24 ; revue |
| R30.10 | P0 | Certification d'un second jeu complet de genre différent sans fork Core/renderer | R24–R29 ; Player distribué |

**Gate R30 :** deux équipes ou créateurs peuvent partir des templates, construire chacun un jeu différent, exploiter des extensions déclarées et maintenir leurs projets au fil des versions sans perdre leurs données.

## 11. Vertical slices inter-genres obligatoires

| ID | Scène de référence | Studio | Player et preuves |
|---|---|---|---|
| VS-SRPG | Jeanne : village → bataille CT → campagne | Carte/terrain, classe, compétence, événement, progression | CT/seed/replay historiques inchangés, export et sauvegarde |
| VS-ADV-01 | Action-aventure : village → forêt → ruines | Monde 3 cartes, PNJ, animations, héros libre, interactions | Caméra top-down, collisions, ennemi et transition |
| VS-ADV-02 | Donjon : clef → levier → porte → boss | Puzzle graph, objets, compétence, boss phases | Pas de softlock connu, état persistant et checkpoint |
| VS-RPG | RPG classique : ville → auberge → rencontre → retour | Base RPG, quêtes, conversation, combat menu | Combat par tour et retour exploration sans duplication |
| VS-HYB | Scène libre → bataille tactique → scène libre | Un projet avec 2 profils et un contrat de transition | Groupe/inventaire/flags et replay sauvés |
| VS-EXPORT | Projet neuf sans éditeur de données | Wizard, playtest, export, manifest | Installation sur machine propre et sauvegarde |
| VS-FAIL | Interruption au milieu du changement de scène/sauvegarde | Diagnostics clairs, reprise ou rollback | Zéro corruption silencieuse et zéro récompense double |

**Définition de la vertical slice Action Adventure** : création de trois cartes reliées, PNJ donnant une quête, combat temps réel, énigme levier/clef/porte, récompense, boss, retour au village, sauvegarde/chargement et export. Tout doit être éditable et reproductible depuis Studio. Direction artistique propre ; aucune reprise d'assets Zelda sans droits.

## 12. Critères chiffrés à instrumenter, non certifiés

- **Créateur débutant :** premier projet + carte + personnage + événement + playtest ≤ 30 min cible ; une mission SRPG simple ≤ 15 min après formation ; mesurer avec tests humains et consigner les blocages.
- **Édition :** geste courant → feedback p95 cible < 100 ms après baseline ; opérations lourdes en worker annulable et transactions réversibles.
- **Rendu :** cible initiale 60 FPS à matériel/profil fixé ; frame-time p95 ≤ 16,7 ms à confirmer sur GPU physique ; rapport p99, stutter, CPU, VRAM, backend et SHA. Offscreen/software ≠ benchmark GPU réel.
- **Simulation temps réel :** tick fixe documenté ; résultat identique sur 2 fréquences d'affichage, sur save/reload et replay. Le replay ne dépend jamais des instants d'affichage.
- **Régressions :** zéro perte silencieuse de données, zéro divergence de CT/seed sur corpus certifié, zéro export non conforme aux droits.
- **Multi-OS :** Windows/Linux/macOS, PySide6/Qt versionné, CI headless + GUI onscreen + test matériel distinct ; ne pas masquer les échecs historiques.
- **Sécurité :** importer packs/zip et données externes avec path confinement, taille bornée, signatures/hashes si exigées et refus explicite en cas d'erreur.

## 13. Plan de PR incrémentales (pas de mega-PR de code)

Les lots ci-dessous sont des PR **proposées**, à ouvrir uniquement après vérification des dépendances et de la base réelle. Base préférée : master actualisée, pas une branche empilée obsolète.

| Ordre | PR | Dépendance | Gate minimal |
|---|---|---|---|
| 0 | R17 closure et audit #285/#286/#287 | master + CI du dernier SHA | aucune régression, preuves lisibles |
| 1 | R24.X — ADR Multi-genre & capability contracts | R17/R24 design | architecture et migrations approuvées |
| 2 | R25.A — Versioned game profiles | R24.X/R1 | Jeanne legacy identique |
| 3 | R25.B — Fixed-tick and input replay | R25.A | hash de replay stable |
| 4 | R25.C — SceneRouter and mode transitions | R25.B/R10 | inventaire/flags sauvegardés |
| 5 | R25.D — Top-down projection + camera + HUD | R25.C/R3 | picking et goldens Qt |
| 6 | R25.E — Cross-mode integration & save | R25.D/R17.7 | VS-HYB + fault injection |
| 7 | R26.A — Free movement and collision | R25.E | trajectoire indépendante FPS |
| 8 | R26.B — Action combat, enemies, reactions | R26.A | VS-ADV combat + replay |
| 9 | R26.C — Interactions, inventory, HUD | R26.B/R9 | puzzle simple, checkpoint |
| 10 | R26.D — Action runtime certification | R26.C | Player standalone et QA |
| 11 | R27.A — World/room/dungeon editors | R26.D/R5/R6 | cartes créées sans JSON |
| 12 | R27.B — Puzzle graph and debugger | R27.A/R9 | énigme sans softlock |
| 13 | R28.A — Project wizard + profile inspector | R25.E/R22 | 3 templates créés |
| 14 | R28.B — Ability/Enemy/Quest workflows | R27.B/R28.A | E2E authoring |
| 15 | R28.C — Classic RPG and hybrid demos | R28.B | VS-RPG et VS-HYB |
| 16 | R29.A — Multi-genre QA, telemetry, goldens | R28.C | tests/replays/rapports |
| 17 | R29.B — Publishing, docs, user tests | R29.A | 3 jeux exportés |
| 18 | R30.A–D — API, packs, semantic diff, platform gate | R29 stable | 2e jeu sans fork |

### Règles de gestion des PR

- Chaque PR indique : ID lot, base/head/SHA, dépendances, liste de fichiers, changements de schémas, migrations, parcours E2E, tests, preuves, limites et plan de rollback.
- PR docs seules distinctes des PR de code ; aucune « feature terminée » sans implémentation + gate vérifié sur master.
- Éviter deux PR modifiant simultanément le même document ou schéma métier sans dépendance explicite et plan de rebase.
- Les tests assurent l'identité des modèles tactiques déjà certifiés. Toute régression du mode Jeanne bloque la fusion d'un lot multi-genres.
- Les licences des assets de référence doivent autoriser modification/redistribution avant un export public ; preview local ≠ release.

## 14. Risques, décisions et non-objectifs

| Risque ou choix | Niveau | Traitement |
|---|---|---|
| Deux moteurs de vérité (CT versus ARPG) | P0 | SDK + session + données communs, systèmes de règles séparés et versionnés |
| Temps réel non déterministe | P0 | fixed tick, quantification, input log, RNG contrôlé, replay |
| Renderer top-down parallèle | P0 | enrichir renderer R3, tests de parité et profiler |
| Portes/énigmes incohérentes entre scènes | P0 | Event Graph unique, variables et états persistants |
| Conversion automatique implicite de cartes | P0 | outil de migration explicite, aucune perte silencieuse |
| Périmètre 3D/MMO/plateformer | P2 | exclusion des gates jusqu'à étude de faisabilité |
| UI surchargée par toutes les options | P1 | profils/templates et outils contextuels, onboarding |
| Dette legacy et PR empilées ouvertes | P0 | fermer R17 et préserver migrations avant nouveaux chantiers |
| Dépendance à assets sous droits inconnus | P0 | fail-closed export avec provenance/licences |
| Prototype « Zelda-like » copié plutôt qu'original | P1 | direction artistique et contenu originaux, références mécaniques seulement |

## 15. Definition of Done et Go/No-go

Une release est **NO-GO** si : données perdues ou rétrocompatibilité brisée sans migration ; replay instable ; scène ARPG ne fonctionnant que sur machine de développement ; simulation variant avec le framerate ; export avec assets à droits inconnus ; Studio et Player avec règles/rendu incompatibles ; UI sans workflow réel ; tests verts uniquement en offscreen software pour une certification GPU.

Pour chaque lot, garder six statuts distincts : **proposé → PR → intégré sur master → tests/gates automatisés verts → UX/GPU/art validés lorsque pertinents → release certifiée**.

**Succès 7.0 :** depuis un Studio installé, une personne peut créer (1) un tactical RPG, (2) une action-aventure top-down originale avec exploration/combat/puzzles et (3) un RPG classique, les tester, sauvegarder/reprendre, distribuer un Player autonome, puis les maintenir sans forker le moteur.

**Prochaine action concrète :** fermer les bloqueurs R17, faire valider l'ADR R24.X, puis livrer R25.A–E comme premier incrément multi-genres. Ne pas commencer par multiplier les ateliers sans preuve d'un parcours de jeu complet.
