# DrawTemp 10.0 → 12.0 — Roadmap détaillée R51–R80

> **Statut : PROPOSITION DOCUMENTAIRE — 19 octobre 2026.** Cette feuille de route n'implémente aucun lot R51–R80, n'approuve aucune release 10/11/12 et n'atteste aucun test. Numéros de versions = horizons de planification, pas dates. **Aucune de ces 90 PR de code n'est créée par cette documentation.**
>
> **Point de départ vérifié :** le dépôt dispose de [R31–R40](DRAWTEMP_7_1_TO_8_0_DETAILED_ROADMAP.md), proposition visant la 8.0. **R41–R50 ont été discutés mais ne sont pas documentés/certifiés dans ce dépôt à la rédaction.** Leur clôture, en particulier R41 RPG classique, R42 narration, R43 combat, R44 monde, R45 simulation, R46 cinéma, R47 SDK, R48 collaboration, R49 UX, R50 9.0, constitue un **contrat d'entrée futur à formaliser** ; ne pas les traiter comme des APIs existantes.
>
> **Non négociable :** R0–R40 restent les sources canoniques du patrimoine SRPG Jeanne, action-aventure, metroidvania et roguelite ; aucune version de cette roadmap ne constitue à elle seule une validation de compatibilité.

## 0. Vision et critères de succès

**Produit :** un seul Studio professionnel Qt/PySide6 + Player Qt Quick partagé pour créer, diagnostiquer, localiser, équilibrer, maintenir et publier des jeux **2D / 2.5D** de plusieurs genres, depuis des projets versionnés sans éditer du JSON ou du Python. La force de DrawTemp est la composition de capacités et l'inspection des règles, et non la compétition avec un moteur 3D AAA généraliste.

- **10.0 — Production professionnelle (R51–R60)** : HUD, rendu 2.5D, groupes hybrides, streaming, systèmes de jeu, QA, localisation, packs, mises à jour et premier jeu vitrine terminé.
- **11.0 — Extension multi-genres (R61–R70)** : gestion, simulation de vie, survie, RTS ciblé, action avancée, laboratoire de simulation ; études réseau/mobile isolées ; trois jeux témoin.
- **12.0 — Création avancée (R71–R80)** : réseau strictement conditionnel, création assistée *opt-in*, optimisation vérifiée, exploration QA, collaboration d'équipe et six jeux certifiés.

**Hors scope / sans engagement :** 3D générale, MMO, consoles, Web/mobile garantis, IA générative obligatoire, exécution non contrôlée de code importé, marketplace hébergée promise, certification commerciale de stores, métriques de performance revendiquées sans benchmark matériel.

## 1. Invariants d'architecture et contrats

| Domaine | Contrat obligatoire | Refus / surveillance |
|---|---|---|
| Édition | **Content + GameProject** uniques, schémas semver/migrations, AuthoringSession, preview/apply transactionnel, Undo/Redo | Pas de sidecar vérité, pas de mutation silencieuse ni édition directe du runtime |
| Simulation | **Core headless** (CT/RNG/replay/IA/temps), tick fixe pour temps réel, ordonnanceur stable, budget CPU/mémoire et annulation | Pas de dépendance Qt dans Core; aucune dépendance au FPS rendu |
| Orchestration | **GameSession** porte état, groupes, scènes, progression, economy, saves et transitions; identifiants stables | Pas de récompense double, corruption masquée, fallback implicite entre modes |
| Présentation | Studio Qt Widgets + viewport Qt Quick, Player Qt Quick et **renderer R3 partagé**, picking, couches et caméras cohérents | Pas de renderer alternatif créé par genre ; offscreen ≠ certification GPU |
| Langages/logique | Event Graph R9 + Logic Graph R31, capacités typées, budgets/sandbox, traces inspectables | Pas de `eval`/`exec` arbitraires ou accès OS implicite via packs |
| Assets | Asset Registry, provenance, hash, licences, droits modification/redistribution, version de packs | Export fail-closed si droits absents, chemins non confinés ou manifests incorrects |
| Edition collaboratrice | Diffs sémantiques, conflits explicités, history and rollback, autonomie hors ligne | Pas d'overwrite automatique ni d'état cloud requis pour ouvrir un projet |
| QA/release | États distincts: PROPOSÉ → PR CODE → MASTER → CI SHA VERT → UX/ONSCR/GPU → BUNDLE CLEAN MACHINE → RELEASE | Une PR merged ne certifie aucun gate; statuts affichés sans exagération |

### 1.1 Définitions de priorité et des preuves

- **P0** : bloque **le gate concerné**, sauf si la roadmap marque le lot entier *étude facultative* avec décision NO-GO acceptable (R67/R68/R71–R73/R79). Une étude P0 est obligatoire pour publier une *affirmation de faisabilité*, pas pour sortir 11.0/12.0.
- **P1** : nécessaire à la portée complète, éventuellement après le gate minimal explicitement réduit ; dépendances jamais remplacées par un mock en certification.
- **P2** : option sans engagement, ne doit pas dégrader les fondamentaux.
- **DoD par PR de code** : interfaces versionnées/ADR, comportement utilisateur réel, tests positifs/adversariaux, save/load/replay, migrations, refus/reprise, couverture Qt si UI, annulation/Undo si édition, logs/bench, doc, CI et captures approuvées si visuel.
- **DoD par gate produit** : preuve sur le **SHA final de master**, code de sortie des tests, jeu réellement ouvrable et exportable sans environnement de dev, droits et assets vérifiés, rapport UX humain, GPU physique avec modèle matériel/driver, écarts connus et décision GO/NO-GO.

### 1.2 Entrée bloquante et lien avec R41–R50

Avant tout tag 10.0 :
1. Les gates de R40 8.0 sont clos et publiquement auditables ; ne pas confondre merge R17–R31.D et R40 certifié.
2. Écrire la roadmap R41–R50 en reliant **R41 RPG**, **R42 Narration**, **R43 Combat**, **R44 Worlds**, **R45 Simulation**, **R46 Cinematics**, **R47 SDK**, **R48 Collaboration**, **R49 UX**, **R50 Release 9.0** ; vérifier les contrats requis ou réduire explicitement les lots R51+.
3. Baseline déterministe du corpus Jeanne CT, action R26, platformer R33, roguelite R34, monde vivant R35 et exemples R40 ; migrations anciennes sauvegardes, Content/GameProject et licences.
4. Réparer les vérifications GitHub Actions de la branche finale et démontrer au moins un export sur une machine propre avant tout P0 de publication.
5. Geler schémas/points d'extension avant d'autoriser des branches parallèles touchant les mêmes fichiers ; plan de résolution de conflits d'abord, branches ensuite.

## 2. Matrice des releases / dépendances

| Lot | Cible | Chantier | Prérequis majeurs | Nature |
|---|---|---|---|---|
| R51 | 9.1→10.0 | UI & HUD Designer | R18/R28/R38/R41–R50 (UI contract) | Livrable conditionné aux gates |
| R52 | 9.2→10.0 | Advanced 2.5D Rendering | R3/R19/R36/R39/R51 | Livrable conditionné aux gates |
| R53 | 9.3→10.0 | Party & Combat Orchestration | R8/R21/R26/R37/R41/R43/R51 | Livrable conditionné aux gates |
| R54 | 9.4→10.0 | Large World Runtime | R25/R27/R35/R44/R52/R59 | Livrable conditionné aux gates |
| R55 | 9.5→10.0 | System Designer | R31/R35/R38/R45/R51 | Livrable conditionné aux gates |
| R56 | 9.6→10.0 | Automated Gameplay QA | R14/R29/R31/R37/R38/R40 | Livrable conditionné aux gates |
| R57 | 9.7→10.0 | Localization & Accessibility Pro | R18/R39/R42/R51 | Livrable conditionné aux gates |
| R58 | 9.8→10.0 | Creator Package Ecosystem | R24/R30/R38/R47/R59 | Livrable conditionné aux gates |
| R59 | 9.9→10.0 | Production & Live Maintenance | R23/R29/R38/R39/R40/R56/R58 | Livrable conditionné aux gates |
| R60 | 10.0 | Game Production Studio 10.0 | R40/R41–R50/R51–R59 P0 | Livrable conditionné aux gates |
| R61 | 10.1→11.0 | Strategy & Management | R35/R45/R55/R56/R60 | Livrable conditionné aux gates |
| R62 | 10.2→11.0 | Farming & Life Simulation | R35/R45/R55/R57/R61 | Livrable conditionné aux gates |
| R63 | 10.3→11.0 | Survival & Crafting | R26/R43/R55/R61/R62 | Livrable conditionné aux gates |
| R64 | 10.4→11.0 | Real-Time Strategy | R26/R37/R52/R54/R55/R61 | Livrable conditionné aux gates |
| R65 | 10.5→11.0 | Action Systems Pro | R26/R32/R36/R37/R43/R53 | Livrable conditionné aux gates |
| R66 | 10.6→11.0 | Simulation Designer Pro | R31/R35/R55/R56/R61/R62/R63 | Livrable conditionné aux gates |
| R67 | 10.7 étude | Multiplayer Feasibility Gate | R25/R29/R56/R59/R60 | Faisabilité |
| R68 | 10.8 étude | Alternative Platform Feasibility | R39/R57/R59/R60 | Faisabilité |
| R69 | 10.9→11.0 | Community Creator Hub | R24/R47/R48/R58/R59/R67 | Livrable conditionné aux gates |
| R70 | 11.0 | Genre Expansion Certification | R60/R61–R66 P0; R67–R69 conditionnels | Livrable conditionné aux gates |
| R71 | 11.1 conditionnel | Connected Games Architecture | R67=GO et R70; sinon reporté | Livrable conditionné aux gates |
| R72 | 11.2 conditionnel | Cooperative Gameplay Prototype | R71=GO/R53/R65/R70 | Livrable conditionné aux gates |
| R73 | 11.3 conditionnel | Network Session UX & Tools | R71/R72=GO/R57/R59 | Livrable conditionné aux gates |
| R74 | 11.4→12.0 | Assisted World & Dungeon Creation | R27/R34/R38/R56/R70 | Livrable conditionné aux gates |
| R75 | 11.5→12.0 | Assisted Narrative & Quest Authoring | R9/R31/R42/R46/R56 | Livrable conditionné aux gates |
| R76 | 11.6→12.0 | Asset & Build Optimization | R4/R36/R52/R54/R59/R70 | Livrable conditionné aux gates |
| R77 | 11.7→12.0 | Automated Exploratory QA | R29/R37/R56/R66/R74/R75 | Livrable conditionné aux gates |
| R78 | 11.8→12.0 | Professional Team Workflows | R38/R48/R58/R69/R70 | Livrable conditionné aux gates |
| R79 | 11.9 étude | Future Platforms & Rendering Research | R39/R52/R68/R76; résultats conditionnels | Faisabilité |
| R80 | 12.0 | Next Generation Creator 12.0 | R70/R74–R78/R59/R56; R71–R73/R79 optionnels selon GO | Livrable conditionné aux gates |

**Chemin critique :** R40 validé → R41–R50 contractualisés et R50 certifié → R51/R56/R57/R59 socle → R52/R53/R54/R55/R58 en tranches compatibles → **R60** → R61–R66 → **R70** → R74–R78 → **R80**. R67/R68 puis R71–R73/R79 ne sont **pas sur le chemin critique** sauf décision GO et engagement de release révisé.

## 3. Spécifications R51 à R80

## R51 — UI & HUD Designer (9.1→10.0)

**Objectif :** Créer les interfaces de jeu sans coder de QML ni modifier le Core.

**Dépendances :** R18/R28/R38/R41–R50 (UI contract). Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R51.A** | P0 | Schéma de layout responsive, widgets déclaratifs, états de focus et bindings typés à GameSession; migrations sans perte. | Headless: schémas invalides, liens rompus, roundtrip, diff de sauvegardes. |
| **R51.B** | P0 | Editeur Qt WYSIWYG menus, HUD CT/action, inventaire, dialogue, navigation souris/clavier/manette; preview/apply et Undo/Redo. | QTest onscreen, DPI, AZERTY/QWERTY, manettes réelles. |
| **R51.C** | P0 | Parité Studio/Player, thèmes contrastés, tests de menus et overlays, export fail-closed sur ressources non autorisées. | Goldens approuvés, a11y et bundles PC clean-machine. |

**Gate R51 (sortie vérifiable) :** Un auteur remplace entièrement les menus et le HUD d'un mini-jeu CT et d'un mini-jeu action, navigables au clavier/manette, exportés à l'identique.

**Vertical slice :** VS-51 — Deux HUD personnalisés et menus complets.

## R52 — Advanced 2.5D Rendering (9.2→10.0)

**Objectif :** Améliorer lisibilité et profondeur visuelle sans deuxième renderer ni casser le picking.

**Dépendances :** R3/R19/R36/R39/R51. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R52.A** | P0 | ADR pipeline Qt Quick partagé: couches, parallaxe, lightmaps optionnelles, ombres, conversion monde/écran, backends et budgets. | Fixtures profondeur/picking multi-caméras; fallback explicite. |
| **R52.B** | P1 | Inspecteur lumière, caméra, transition, presets top-down/iso/side; rendu interpolé sans incidence sur le tick. | Goldens par DPI, profils, scène et backend. |
| **R52.C** | P0 | Culling, atlas/cache borné, profiling p95/p99 CPU/GPU et validation hardware Studio/Player. | Matrice physique 3 OS; écarts visuels justifiés. |

**Gate R52 (sortie vérifiable) :** Même scène à trois profils de caméra avec overlays HUD corrects, picking stable et comparaison sur GPU physique; aucune régression CT.

**Vertical slice :** VS-52 — Ville 2.5D avec profondeur, occlusion et transition jour/nuit.

## R53 — Party & Combat Orchestration (9.3→10.0)

**Objectif :** Supporter une équipe cohérente entre exploration, CT, action et RPG classique.

**Dépendances :** R8/R21/R26/R37/R41/R43/R51. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R53.A** | P0 | Modèle unique de groupe, roster, formation, contrôle actif, compétences coopératives et règles de transition; politique de pause. | Replay CT/action, sérialisation et inventaire sans duplication. |
| **R53.B** | P0 | Party Composer, choix des rôles, liens d'équipe, UI de formation, feedback des combos, preview d'impact. | Studio↔Player, QTest navigation, Undo/Redo. |
| **R53.C** | P0 | Rencontre hybride: exploration, échange de leader, escarmouche tactique, retour avec PV/items et récompenses identiques. | E2E et crash entre deux modes; deux seeds. |

**Gate R53 (sortie vérifiable) :** Trois compagnons et deux modes de combat; switch, groupe et inventaire conservés après sauvegarde/reprise/transition.

**Vertical slice :** VS-53 — Exploration de groupe et bataille tactique intégrée.

## R54 — Large World Runtime (9.4→10.0)

**Objectif :** Parcourir des régions importantes sans figer le Player ni provoquer de divergences de monde.

**Dépendances :** R25/R27/R35/R44/R52/R59. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R54.A** | P0 | Contrat de cellules/regions, cache borné, chargement asynchrone annulable, IDs stables et persistance inter-zone. | Stress interruptions, corruption, données tardives. |
| **R54.B** | P0 | World Streaming Inspector: cellules, préchargement, LOD 2D, liens et mémoire; prévisualisation depuis le Studio. | Test navigation et authoring no-JSON; viewport Qt. |
| **R54.C** | P0 | Traversée multi-zones, save/reload en frontière, profilage des stalls p95/p99, parité Player/export. | Test endurance, mémoire et PC de référence. |

**Gate R54 (sortie vérifiable) :** Traverser plusieurs régions en continu, revenir en arrière, quitter pendant chargement et reprendre sans duplication ni perte.

**Vertical slice :** VS-54 — Route de plusieurs régions avec streaming et reprise.

## R55 — System Designer (9.5→10.0)

**Objectif :** Assembler des systèmes de jeu sans scripts Python arbitraires ni état parallèle.

**Dépendances :** R31/R35/R38/R45/R51. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R55.A** | P0 | Contrats typés de ressources, besoins, production, consommations, capacités et cycles; budget tick et ordre déterministe. | Analyse statique cycles, transactions, replay, fail-closed. |
| **R55.B** | P0 | Editeur visuel des graphes de ressources, inspecteur économique, preview de flux, alertes d'impasses. | QTest graphes, Undo/Redo, conflit de révision. |
| **R55.C** | P0 | Démonstrateur production/consommation + achat/vente + quête; aucune création de ressources depuis un reload. | Simulation longue, balance et vérification conservation. |

**Gate R55 (sortie vérifiable) :** Un atelier transforme des ressources, le marchand les échange et la progression persiste à travers une zone et une sauvegarde.

**Vertical slice :** VS-55 — Micro-économie simulée depuis le Studio.

## R56 — Automated Gameplay QA (9.6→10.0)

**Objectif :** Démocratiser les tests de jeux réels plutôt que multiplier les faux verts.

**Dépendances :** R14/R29/R31/R37/R38/R40. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R56.A** | P0 | Contrat des scénarios E2E rejouables (seed, inputs, versions, états), oracle d'invariants, instrumentation et limites. | Tests de déterminisme CT/realtime/quests et provenance des traces. |
| **R56.B** | P0 | QA Lab visuel: capture scénario, batch, inspection diff, liens nœud↔échec, reproduction au tick. | UX Studio, traces/export identiques. |
| **R56.C** | P0 | Détection automatisée de softlocks, doubles récompenses, collisions, transitions invalides et régressions. | Matrice tri-OS; rapport NO-GO sur SHA final. |

**Gate R56 (sortie vérifiable) :** Reproduire un échec depuis le Studio et obtenir un contre-exemple minimal lié au commit, sans prétendre remplacer les playtests humains.

**Vertical slice :** VS-56 — Régression injectée puis détectée et rejouée.

## R57 — Localization & Accessibility Pro (9.7→10.0)

**Objectif :** Rendre Studio et Player internationalisables et utilisables sans dépendre d'un seul périphérique.

**Dépendances :** R18/R39/R42/R51. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R57.A** | P0 | Clés stables de localisation, pluralisation, paramètres de langue, fallback explicite, audit de chaînes et migration. | Pseudo-localisation, accents/RTL, encodage. |
| **R57.B** | P0 | Translation Studio: contexte visuel, recherche textes, longueur, sous-titres, raccourcis, préférences contraste. | QTest navigation clavier, lecteur d'écran quand supporté. |
| **R57.C** | P0 | Audit focus, contraste, réduction flash/shake, taille sous-titres, manette, réglages sauvegardés. | Essais utilisateurs et matériel/a11y documentés. |

**Gate R57 (sortie vérifiable) :** Un jeu et son Studio utilisables en deux langues plus pseudo-localisation, navigation sans souris et sous-titres/contrastes vérifiés.

**Vertical slice :** VS-57 — Localiser un acte narratif et parcourir le jeu sans souris.

## R58 — Creator Package Ecosystem (9.8→10.0)

**Objectif :** Partager des contenus réutilisables sans étendre silencieusement les permissions des projets.

**Dépendances :** R24/R30/R38/R47/R59. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R58.A** | P0 | Packages signés si infrastructure disponible, manifestes semver, dépendances, SHA et droits; sandbox/permissions restrictives. | Imports adversariaux, traversal ZIP, conflits de versions. |
| **R58.B** | P1 | Package Manager Qt: installation, prévisualisation diff, migration/rollback, désinstallation et usages. | No-overwrite, Undo, gestion références. |
| **R58.C** | P0 | Pack de personnage, HUD et quête installé dans deux jeux indépendants; export seulement avec provenance valide. | Clean import/export, licences, compatibilité. |

**Gate R58 (sortie vérifiable) :** Installer, mettre à jour et retirer un pack sans perdre de contenu ni exporter de ressource aux droits inconnus.

**Vertical slice :** VS-58 — Pack réutilisable sur deux jeux.

## R59 — Production & Live Maintenance (9.9→10.0)

**Objectif :** Distribuer et mettre à jour des jeux avec traçabilité et reprise sûre.

**Dépendances :** R23/R29/R38/R39/R40/R56/R58. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R59.A** | P0 | Manifeste de build/versions, migrations saves N/N-1, rollback, provenance SBOM et dépendances. | Reproductibilité de builds, injections de panne. |
| **R59.B** | P0 | Release Center Qt avec preflight licences, matrice plateformes, notes de release, sauvegardes et avertissements. | Parcours éditeur→bundle et refus sûr. |
| **R59.C** | P0 | Mise à jour d'un Player installé puis restauration d'une sauvegarde antérieure, rollback sur paquet défectueux. | Clean-machine tri-OS, signatures quand disponibles. |

**Gate R59 (sortie vérifiable) :** Publier une mise à jour et revenir à la version précédente sans corrompre les sauvegardes ni masquer un préflight NO-GO.

**Vertical slice :** VS-59 — Mise à jour contrôlée et retour arrière.

## R60 — Game Production Studio 10.0 (10.0)

**Objectif :** Certifier un cycle de production commercialement plausible, sans revendiquer prématurément une conformité store.

**Dépendances :** R40/R41–R50/R51–R59 P0. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R60.A** | P0 | Gel de contrats, semver, corpus migrations 5.x→10.x, contrôle des références et des comportements legacy. | Fixtures historiques Jeanne/CT et jeux R40. |
| **R60.B** | P0 | Projet vitrine original hybride: ville, équipe, temps réel↔CT, boutique, quêtes, HUD personnalisable, 2 régions. | Création par Studio, documentation de chaque étape. |
| **R60.C** | P0 | Release 10.0: CI master finale, UX tiers, sauvegardes, audit licences, GPU matériel, PC propres et decision GO/NO-GO. | Rapports signés dans le dossier de release. |

**Gate R60 (sortie vérifiable) :** Un auteur tiers modifie le jeu vitrine sans JSON, teste, exporte et met à jour le Player sur 3 OS; aucun P0 non attesté.

**Vertical slice :** VS-60 — Jeu hybride complet, installable et maintenable.

## R61 — Strategy & Management (10.1→11.0)

**Objectif :** Activer la construction/gestion de villes sans réécrire la simulation de monde.

**Dépendances :** R35/R45/R55/R56/R60. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R61.A** | P0 | Zones constructibles, jobs/agents, stocks, capacités, production et temps simulé; règles déterministes bornées. | Tests emplois concurrent, saturation, conservation. |
| **R61.B** | P0 | City Planner visuel: zones, bâtiments, connexions, habitants et tableaux de capacité. | Qt cartes, Undo/Redo, alertes flux. |
| **R61.C** | P0 | Village de production sur plusieurs jours avec chaîne de ressources et reprise intacte. | Batch seeds, performance, équilibre. |

**Gate R61 (sortie vérifiable) :** Une colonie produit, consomme, manque de ressources puis récupère via interventions du joueur; état stable après reload.

**Vertical slice :** VS-61 — Bourg artisanal évolutif.

## R62 — Farming & Life Simulation (10.2→11.0)

**Objectif :** Composer une boucle de jeu vie quotidienne et agriculture pilotée par le calendrier du monde.

**Dépendances :** R35/R45/R55/R57/R61. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R62.A** | P0 | Sol/parcelles, saisons, météo opt-in, cultures, animaux et besoins; politiques de tick hors focus. | Reprise minuit, inventaire, récolte non dupliquée. |
| **R62.B** | P0 | Farm/Relationship Studio: planter, programmer routines et commandes sociales visuelles. | Validation conditions/rythmes, Undo/Redo. |
| **R62.C** | P0 | Cycle semer→cultiver→récolter→vendre et évolution d'une relation PNJ. | Simulation multi-jours et Player Qt. |

**Gate R62 (sortie vérifiable) :** Une saison et ses récompenses rejouées à l'identique à seed fixe, même en passant hors zone.

**Vertical slice :** VS-62 — Ferme et village social.

## R63 — Survival & Crafting (10.3→11.0)

**Objectif :** Permettre une aventure de survie équilibrable sans modifier le Core CT.

**Dépendances :** R26/R43/R55/R61/R62. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R63.A** | P0 | Besoin énergie/faim/temperature opt-in, récolte, usure, craft et refuges avec règles déterministes. | Invariants coûts, limites de ressources, save/replay. |
| **R63.B** | P0 | Survival Designer: recettes, outils, HUD besoins, feedback, dangers et placements sur cartes. | Studio→Player E2E, a11y, Undo/Redo. |
| **R63.C** | P0 | Parcours collecte→craft→camp→exploration→retour avec échec/récupération. | Replays, équilibrage et anti-duplication. |

**Gate R63 (sortie vérifiable) :** Une session survie comporte au moins deux recettes, un risque environnemental et une boucle de progression persistante.

**Vertical slice :** VS-63 — Refuge, exploration et artisanat.

## R64 — Real-Time Strategy (10.4→11.0)

**Objectif :** Expérimenter RTS multi-unités sous contraintes mesurées, en gardant le tactical CT indépendant.

**Dépendances :** R26/R37/R52/R54/R55/R61. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R64.A** | P0 | Ordres de groupe, sélection multiple, pathfinding en formation, ordonnanceur temps réel et règles d'engagement. | Replays entiers, collisions, anti-deadlocks. |
| **R64.B** | P0 | RTS Command Editor + Player: groupes, raccourcis, point de ralliement, zones et minimap. | Tests sélection/focus et performances. |
| **R64.C** | P1 | Bataille de défense avec vague, renforts, ressources et 2 doctrines IA. | Profil CPU/GPU, UX et budget unités. |

**Gate R64 (sortie vérifiable) :** Déplacer et coordonner plusieurs escouades en temps réel de façon reproductible, sans modifier les résultats CT Jeanne.

**Vertical slice :** VS-64 — Défense de village à escouades.

## R65 — Action Systems Pro (10.5→11.0)

**Objectif :** Offrir des combats d'action approfondis avec des outils visuels explicables.

**Dépendances :** R26/R32/R36/R37/R43/R53. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R65.A** | P0 | Projectiles, cadence, combos, fenêtres parade/esquive, statut et stagger en tick entier. | Tests collision, synchronisation hitbox, replay. |
| **R65.B** | P0 | Combat Composer: séquences, fenêtres, télégraphies, patterns boss, preview des hitboxes. | Editeur Qt et Player, a11y motion. |
| **R65.C** | P0 | Arène avec armes distance/mêlée, deux ennemis coordonnés et boss 2 phases. | Playtest humain, frame independence. |

**Gate R65 (sortie vérifiable) :** Combat action lisible et rejouable à 30/60/120 FPS affichés, sauvegarde et reprise sûres.

**Vertical slice :** VS-65 — Arène action et boss chorégraphié.

## R66 — Simulation Designer Pro (10.6→11.0)

**Objectif :** Contrôler et diagnostiquer les simulations à multiples agents et ressources.

**Dépendances :** R31/R35/R55/R56/R61/R62/R63. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R66.A** | P0 | Contrats de simulation compositionnels: temps, dépendances, ressources, budgets, snapshots et annulation. | Propriétés conservation/idempotence, concurrence d'événements. |
| **R66.B** | P0 | Simulation Lab: avance rapide, comparaison de paramètres, événements et causalité inspectables. | UI step/rewind en playtest non destructif. |
| **R66.C** | P0 | Batch multi-seeds d'économie et PNJ, détection d'effondrement, dérives et softlocks. | Rapport reproductible, p95/p99 mesurés. |

**Gate R66 (sortie vérifiable) :** Une simulation longue est analysable et corrigeable dans le Studio sans modifier arbitrairement les replays.

**Vertical slice :** VS-66 — Diagnostic d'économie sur 30 jours simulés.

## R67 — Multiplayer Feasibility Gate (10.7 étude)

**Objectif :** Décider objectivement si la coopération réseau est compatible avec l'architecture.

**Dépendances :** R25/R29/R56/R59/R60. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. **Lot de recherche ou conditionnel :** aucun support produit ne peut être revendiqué avant décision GO documentée.

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R67.A** | P0 | ADR autorité/synchronisation, commandes, dérive de tick, latence, transport, versionnage, anti-triche et menace. | Budget et choix d'architecture documentés; aucune promesse MMO. |
| **R67.B** | P1 | Spike isolé 2 joueurs sur scène simple, réseau local non fiable simulé; journal serveur authoritative prototype. | Mesures dérives, latence, perte paquets; sécurité. |
| **R67.C** | P0 | Gate explicite GO / REDUCE / NO-GO fondé sur coûts, maintenance, sécurité et tests. | En cas NO-GO, R71–R73 retirés du chemin critique. |

**Gate R67 (sortie vérifiable) :** Rapport de faisabilité auditable, pas une fonctionnalité réseau déclarée livrée.

**Vertical slice :** VS-67 (expérimental) — Deux clients isolés synchronisés sur un scénario borné.

## R68 — Alternative Platform Feasibility (10.8 étude)

**Objectif :** Étudier Web/mobile avec les véritables contraintes Qt, OS, entrée, licences et distribution.

**Dépendances :** R39/R57/R59/R60. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. **Lot de recherche ou conditionnel :** aucun support produit ne peut être revendiqué avant décision GO documentée.

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R68.A** | P0 | Matrice contraintes runtime Qt, bundle, stockage, cycle de vie, GPU, performance, a11y, licence et coûts. | ADR distincts Web et Android/iOS, scope séparé. |
| **R68.B** | P1 | Portage spike Player minimal par plateforme retenue; contrôles tactiles et suspend/reprise. | Mesures matériel réel et audit installabilité. |
| **R68.C** | P0 | Décision GO / REDUCE / NO-GO par plateforme; PC demeure cible garantie. | Aucune certification inférée d'un émulateur. |

**Gate R68 (sortie vérifiable) :** Documenter ce qui fonctionne, ne fonctionne pas, et l'effort de support avant d'annoncer un Player mobile/Web.

**Vertical slice :** VS-68 (expérimental) — Player minimal hors PC, seulement si faisable.

## R69 — Community Creator Hub (10.9→11.0)

**Objectif :** Améliorer la distribution de créations sans rendre le Studio dépendant d'un serveur.

**Dépendances :** R24/R47/R48/R58/R59/R67. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R69.A** | P0 | Contrats de métadonnées, licences, modération/retrait, versions et sécurité des packages. | Publication locale/hors ligne maintenue. |
| **R69.B** | P1 | Workflow opt-in de catalogue, recherche, import et mises à jour, éventuellement service externe clairement séparé. | Permissions explicites, confidentialité, UX. |
| **R69.C** | P0 | Publication/consommation de trois packs de démo autorisés et retrait reproductible. | Gestion versions, provenance, protections. |

**Gate R69 (sortie vérifiable) :** Un créateur partage un pack conforme et un autre le récupère sans perte ni exécution de code arbitraire.

**Vertical slice :** VS-69 — Échange contrôlé de trois packs.

## R70 — Genre Expansion Certification (11.0)

**Objectif :** Livrer de vrais jeux de nouveaux genres sans dégrader les classiques.

**Dépendances :** R60/R61–R66 P0; R67–R69 conditionnels. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R70.A** | P0 | Compatibilité/migrations des schémas de simulation, budgets monde/agents, corrections critiques. | Régressions CT/action/R40/R60, corpus multi-seeds. |
| **R70.B** | P0 | Trois projets originaux de démonstration: gestion, vie quotidienne, survie/action; RTS si gate atteint. | Parcours no-code sans JSON, docs source. |
| **R70.C** | P0 | Certification production tri-OS, GPU physique, release gates, QA tiers et licences. | GO/NO-GO sur SHA final, P0 clos. |

**Gate R70 (sortie vérifiable) :** Trois genres supplémentaires jouables, sauvegardables, éditables et exportés sans modules privés; études réseau/mobile non bloquantes.

**Vertical slice :** VS-70 — Gestion + life sim + survie exportées.

## R71 — Connected Games Architecture (11.1 conditionnel)

**Objectif :** Définir des sessions connectées privées et bornées, jamais une promesse MMO.

**Dépendances :** R67=GO et R70; sinon reporté. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. **Lot de recherche ou conditionnel :** aucun support produit ne peut être revendiqué avant décision GO documentée.

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R71.A** | P0 | Versionnage messages, autorité et ownership des entités, sécurité des commandes, contrôle reconnect. | Protocole sérialisé, fuzz, replay serveur. |
| **R71.B** | P1 | Service/session testable, outils de logs et diagnostics réseau, migration des clients. | Latence/perte simulées, test offline inchangé. |
| **R71.C** | P0 | Décision GO/NO-GO à partir d'une scène coop non publique reproductible. | Test surcharge, auth/transport et conditions d'échec. |

**Gate R71 (sortie vérifiable) :** Contrats autoritaires et tests robustes avant exposition à de vrais joueurs; sinon reporter le lot.

**Vertical slice :** VS-71 (conditionnel) — Session synchronisée de laboratoire.

## R72 — Cooperative Gameplay Prototype (11.2 conditionnel)

**Objectif :** Tester une boucle coop à deux joueurs sans compromettre la sauvegarde solo.

**Dépendances :** R71=GO/R53/R65/R70. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. **Lot de recherche ou conditionnel :** aucun support produit ne peut être revendiqué avant décision GO documentée.

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R72.A** | P0 | Règles lobby/connexion, contrôle partagé, spawn et reprise; décisions serveur et snapshots persistants. | Injection déconnexions, rollback, conflit de commandes. |
| **R72.B** | P1 | UX coop bornée, affichage des deux joueurs, invitations locales, retours déconnexion. | Tests 2 devices sur réseau isolé. |
| **R72.C** | P0 | Scène puzzle + boss à deux joueurs, instrumentation de divergence et rapport de faisabilité. | Replays autoritaires, QA latence. |

**Gate R72 (sortie vérifiable) :** La session coop reprend après perte réseau contrôlée et ne duplique ni butin ni récompense; sinon NO-GO.

**Vertical slice :** VS-72 (conditionnel) — Puzzle coop + boss.

## R73 — Network Session UX & Tools (11.3 conditionnel)

**Objectif :** Rendre configurables et débogables les sessions coop, sans généraliser le réseau à tous les genres.

**Dépendances :** R71/R72=GO/R57/R59. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. **Lot de recherche ou conditionnel :** aucun support produit ne peut être revendiqué avant décision GO documentée.

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R73.A** | P0 | Règles de permissions, hôtes, versions, timeout, sauvegardes et gestion d'erreurs. | Tests sécurité commandes, crash/rejoin. |
| **R73.B** | P1 | Session Designer Qt, diagnostic bande passante/désynchronisation et réglages confidentialité. | UX joueur et créateur, focus/accessibilité. |
| **R73.C** | P0 | Export d'un exemple coop autonome avec protocole/version explicitement supportés. | Clean-machine + deux appareils; go/no-go. |

**Gate R73 (sortie vérifiable) :** Un projet coop expressément opt-in est créable et testable; le Player solo reste totalement hors réseau.

**Vertical slice :** VS-73 (conditionnel) — Projet coop éditable avec diagnostic.

## R74 — Assisted World & Dungeon Creation (11.4→12.0)

**Objectif :** Accélérer le placement de cartes et la conception de donjons sans perdre la main de l'auteur.

**Dépendances :** R27/R34/R38/R56/R70. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R74.A** | P0 | Pipeline de propositions bornées, seeds et contraintes (accessibilité, biomes, ressources, droits). | Solveur atteignabilité, rejet d'impasses, provenance. |
| **R74.B** | P1 | Assistant opt-in de variantes topologiques, preview/diff, édition locale, Undo/Redo. | Refus explicite; aucune écriture cachée. |
| **R74.C** | P0 | Créer 3 donjons originaux ayant chacun une solution démontrée et un export intact. | Reproduction seed, E2E puzzle/quête. |

**Gate R74 (sortie vérifiable) :** L'auteur sélectionne, modifie ou rejette un donjon proposé et obtient un chemin prouvé jouable.

**Vertical slice :** VS-74 — Trois donjons suggérés, validés puis personnalisés.

## R75 — Assisted Narrative & Quest Authoring (11.5→12.0)

**Objectif :** Assister la rédaction et les graphes de quêtes sans publier des dialogues non revus.

**Dépendances :** R9/R31/R42/R46/R56. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R75.A** | P0 | Contrat propositions de quêtes/dialogues, contraintes d'états, droits/attribution et graphe typé. | Vérif branches inatteignables, cycles, références. |
| **R75.B** | P1 | Assistant opt-in dans Narrative Studio: diff, validation humaine, versionning et Undo. | Mode hors ligne possible sans service externe. |
| **R75.C** | P0 | Arbre à 3 fins avec variables persistantes et guide de couverture des chemins. | Simulation par branches + auteur tiers. |

**Gate R75 (sortie vérifiable) :** Les suggestions ne deviennent effectives qu'après validation; chaque fin est atteignable et vérifiable après save/load.

**Vertical slice :** VS-75 — Quête à trois fins assistée, relue et jouée.

## R76 — Asset & Build Optimization (11.6→12.0)

**Objectif :** Optimiser les projets avec une preuve visuelle et un rollback.

**Dépendances :** R4/R36/R52/R54/R59/R70. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R76.A** | P0 | Auditeur dépendances/atlas/shaders/audio et empreinte mémoire, politiques de compression versionnées. | Droits, hashes, mesure de taille et qualité. |
| **R76.B** | P1 | Optimizer Studio: propositions comparables, golden avant/après et annulation transactionnelle. | Inspecteur side-by-side, aucun asset original détruit. |
| **R76.C** | P0 | Bench de démarrage, taille de bundle, mémoire et GPU sur corpus matériel/versionné. | p95/p99 et variance; pas d'optimisation supposée. |

**Gate R76 (sortie vérifiable) :** Optimisation approuvée diminue un coût mesuré sur scène étalon sans régression visuelle/gameloop ni licence.

**Vertical slice :** VS-76 — Bundle optimisé, preuves avant/après.

## R77 — Automated Exploratory QA (11.7→12.0)

**Objectif :** Explorer automatiquement des parcours rares sans assimiler simulation à certification humaine.

**Dépendances :** R29/R37/R56/R66/R74/R75. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R77.A** | P0 | Agents testeurs déterministes et bornés, couverture zones/conditions/actions, détection softlocks et exceptions. | Trace exploitable, aucune mutation du contenu auteur. |
| **R77.B** | P1 | Exploration Lab: heatmaps, chemins critiques, étapes minimisées, liens cartes/graphes, validation de faux positifs. | QTest, navigation Studio, comparateur versions. |
| **R77.C** | P0 | Campagne de tests de 4 genres + fuzz sauvegardes/transitions et bilan couverture. | Seeds, commits, artefacts inspectables. |

**Gate R77 (sortie vérifiable) :** Un bug de progression artificiel est découvert, réduit, corrigé et prouvé absent sur le SHA final.

**Vertical slice :** VS-77 — Chasse au softlock avec preuve reproductible.

## R78 — Professional Team Workflows (11.8→12.0)

**Objectif :** Supporter les équipes sans collaborer par un état parallèle opaque.

**Dépendances :** R38/R48/R58/R69/R70. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R78.A** | P0 | Rôles/droits sur dépôts ou espaces explicitement connectés, historique immuable, baux et résolution de conflits. | Aucune écriture silencieuse ni écrasement de fichiers. |
| **R78.B** | P1 | Revues de changements, commentaires associés à entités, tâches et tableaux de release; mode local disponible. | Tests concurrence à deux auteurs, restore/rollback. |
| **R78.C** | P0 | Deux créateurs éditent carte/quête et résolvent un conflit typé sans perte. | Revue du diff, Undo, logs et export. |

**Gate R78 (sortie vérifiable) :** Projet commun revisité après modification concurrente; résolution déterministe et traçable, même sans cloud obligatoire.

**Vertical slice :** VS-78 — Deux auteurs, conflit réel et résolution sûre.

## R79 — Future Platforms & Rendering Research (11.9 étude)

**Objectif :** Décider de futurs supports et capacités de rendu sans détourner le cœur 2D/2.5D.

**Dépendances :** R39/R52/R68/R76; résultats conditionnels. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. **Lot de recherche ou conditionnel :** aucun support produit ne peut être revendiqué avant décision GO documentée.

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R79.A** | P0 | ADR coût/risque des variantes RHI, matériels alternatifs, tactile, packaging, licences et contrôles. | Bench capteur/appareil, matrice OS et compatibilité. |
| **R79.B** | P2 | Spike isolé d'un backend/support choisi, jamais branché en production sans preuve. | Aucune dépendance mandatory pour Player PC. |
| **R79.C** | P0 | GO/NO-GO et suivi du coût maintenance/performance; recommandations de scope après R80. | Rapport reproduisible, sources et limites. |

**Gate R79 (sortie vérifiable) :** Une décision de périmètre étayée; pas de promesse consoles ou 3D générale sur une preuve conceptuelle.

**Vertical slice :** VS-79 (optionnel) — Prototype d'une plateforme ou projection, si admissible.

## R80 — Next Generation Creator 12.0 (12.0)

**Objectif :** Certifier la plateforme de création mature avec démos et retour réel de créateurs.

**Dépendances :** R70/R74–R78/R59/R56; R71–R73/R79 optionnels selon GO. Ces noms désignent des contrats / gates à prouver sur `master`, et non une présence supposée. 

| Sous-lot / PR proposée | Priorité | Livraison | Critères d'évidence |
|---|---|---|---|
| **R80.A** | P0 | Stabilisation ABI/SDK, schémas et migrations, sécurité assets/plugins, audit compatibilité 5.x→12.x. | Replays historiques, saves multi-versions, contrôles fail-closed. |
| **R80.B** | P0 | Catalogue de 6 jeux indépendants: SRPG, action-aventure, RPG classique, metroidvania, roguelite, gestion/vie. | Chaque template ouvrable, jouable, modifiable et exportable. |
| **R80.C** | P0 | Release finale: CI, vrais GPU et appareils, épreuves UX externes, accessibilité, licences, SBOM, clean-machine et NO-GO. | Dossier final par OS/SHA avec limites attestées. |

**Gate R80 (sortie vérifiable) :** Six jeux originaux produits dans un Studio unique par auteurs tiers, sauvegardés, replays lorsque requis, installés sur PC propres; pas de P0 non certifié.

**Vertical slice :** VS-80 — Six genres dans un seul Studio, avec release reproductible.


## 4. Vertical slices de référence et gates transversaux

| Identifiant | Genre / démonstrateur | Étapes requises | Preuves de sortie |
|---|---|---|---|
| VS-51–52 | Interface + profondeur 2.5D | Menu personnalisable, lumière, caméra iso/top-down, export | UX et captures approuvées, picking et manette |
| VS-53–54 | RPG hybride multi-zones | Déplacement groupe → changement leader → combat CT → retour → streaming | Replay/seed, inventaire/reward, crash recovery |
| VS-55–56 | Économie et QA | Construire la boucle production→vente, injecter bug économie/quête | Diagnostics, contres-exemples et fix prouvé |
| VS-57–59 | Production | Localiser, installer un pack, exporter puis updater un Player | A11y, licences, tri-OS, sauvegarde/rollback |
| **VS-60** | **Jeu vitrine 10.0** | Un jeu complet multi-systèmes modifié par auteur tiers | Export PC indépendant, P0 fermés |
| VS-61–63 | Gestion/vie/survie | Bâtir une colonie, cultiver puis fabriquer/protéger | Monde persistant sans duplication ni impasse |
| VS-64–66 | RTS/action/simulation | Commander groupes, boss action, diagnostiquer une économie | CPU/GPU/replays, équilibrage et UX |
| **VS-70** | **3 jeux témoin 11.0** | Projets séparés gestion, life sim, survie; RTS P1 | Création sans JSON, export, supports PC |
| VS-71–73 | Réseau expérimental | ADR → coopération test → outil session (si GO) | Diagnostic latence/paquets, NO-GO autorisé |
| VS-74–75 | Création assistée | 3 donjons validés, quête 3 fins choisie et relue | Preview, provenance, Undo, solveur et replay |
| VS-76–78 | Optimisation/QA/collaboration | Optimiser un bundle, retrouver un softlock, merger un conflit | Bench avant/après, traces, zéro perte |
| **VS-80** | **Certification 12.0** | Six jeux originaux et projets éditables | Player installable, UX tiers, qualité/compatibilité prouvées |

### 4.1 Matrice minimale de validation à chaque jalon

| Axe | Test automatique minimal | Validation réelle indispensable à une release |
|---|---|---|
| Core CT historique | Golden replay Jeanne, seed, ordre CT, formations, récompenses | Playtest tactique et intégrité de sauvegardes |
| Temps réel/physique | Tick fixe, variations 30/60/120 FPS présentation, collisions, RNG | Manette et ressenti réels, performances hardware |
| Sauvegarde / migration | Crash injection, versions anciennes, mauvaises références, double récompense | Mise à niveau/retour arrière sur machines propres |
| Studio | Preview/apply, Undo/Redo, QTest offscreen pour régression de code | Tests Qt **onscreen** souris/clavier et a11y |
| Studio ↔ Player | Snapshot/digest/rendu de scènes comparables, interactions réellement déclenchées | GPU matériel, goldens visuels validés |
| Performance | Profils p50/p95/p99/mémoire, métadonnées machines/driver/SHA | Baselines physiques représentatives et budgets revus |
| Projets importés / packs | Sandbox, ZIP traversal, manifestes versions, provenance et licences | Rapport juridique/licence et export fail-closed |
| Collaboration / assistance | Transactions, conflits stales, refus implicite, logs, rollback | Résolution de conflits par deux auteurs |
| Réseau/plateformes étude | Fuzz protocole, latence/pannes, lifecycle, licences Qt | Matériel, sécurité et gate séparé **GO/NO-GO** |

**Budgets cibles à confirmer** : 60 FPS seulement sur corpus/GPU de référence choisi; frame p95 autour de 16,7 ms et p99 explicitement mesuré; interactions UI p95 ≤100 ms hors jobs longs; jobs annulables, progress mesurés; mémoire sans croissance non bornée; latence réseau et nombre d'agents fixés seulement après baselines. Il s'agit de **cibles d'ingénierie, non de résultats observés**.

### 4.2 Conditions NO-GO communes

- Régression de CT, RNG/replay Jeanne, save/migrations, état inter-modes, données canoniques ou duplication de récompenses.
- Exécution de capacité/plugin non autorisée, source de contenu aux droits inconnus exportée, chemin non confiné, corrélation build/source absente.
- Action visible uniquement en Studio mais pas dans Player exporté, UI sans action, perte sur Undo/Redo ou sauvegarde.
- Performance/visuel GPU revendiqués à partir d'offscreen seul; aucun rapport matériel; tests Windows/Linux/macOS manquants lorsqu'exigés.
- Publication prématurée de support Web/mobile/coop, succès de spike assimilé à une API sûre, ou service cloud imposé au jeu solo.
- Aucune démonstration créée/modifiée sans toucher Python/JSON ou playtests tiers omis pour la stable.

## 5. Ordre des PR proposées : 90 unités *non encore créées*

**Règles :** 1 PR étroite = 1 sous-lot A, B ou C; **A** est le contrat/domaine, **B** l'intégration visuelle, **C** le gate et la slice. Le tableau est un **ordre d'ouverture recommandé** et non une demande de création simultanée. Les numéros 01–90 sont des positions de planification, **pas** des numéros de PR GitHub. Les dépendances inter-lots restent obligatoires même lorsque deux familles appartiennent à la même vague.

### V0 — préalables

**Prérequis :** R40 stable vérifiée; formalisation et certification séparées des propositions R41–R50; CI et release P0 fonctionnelles.

Sans baseline fiable, aucune PR R51+ ne peut revendiquer un résultat de release.

### V1 — socle transversal

**Prérequis :** R40/R50 certifiés; R56.A peut être amorcé avant R51

Outillage de tests, UI, accessibilité et mise à jour précèdent l'élargissement du gameplay.

### V2 — systèmes de production

**Prérequis :** R51.A, R56.A et les contrats existants mentionnés dans chaque lot

Caméras, équipes, monde, systèmes et packages peuvent être parallélisés avec schémas gelés.

### V3 — certification 10.0

**Prérequis :** Gates P0 des R51–R59

Un jeu vitrine complet prouve l'intégration.

### V4 — nouveaux genres

**Prérequis :** R60; R66 peut avancer avec R61; R67/R68 sont des études non bloquantes

Étendre le même moteur, en maintenant CT et jeux R40.

### V5 — certification 11.0

**Prérequis :** R61–R66 P0, résultats R67–R69 consignés

Trois jeux additionnels réellement exportés.

### V6 — outils avancés

**Prérequis :** R70; R71→R72→R73 uniquement si faisabilité R67 GO

Assistance et collaboration ne dépendent pas du réseau; études réseau peuvent suivre en parallèle.

### V7 — recherche + certification 12.0

**Prérequis :** R74–R78 P0 + R70, R79 facultatif, réseau facultatif

Ne pas rendre le support PC captif de plateformes expérimentales.


| Ordre proposé | Vague | PR / sous-lot | Priorité | Base fonctionnelle à valider avant ouverture | Critère de fermeture |
|---:|---|---|---|---|---|
| 01 | V1 | **R51.A** | P0 | R18/R28/R38/R41–R50 (UI contract) | Headless: schémas invalides, liens rompus, roundtrip, diff de sauvegardes. |
| 02 | V1 | **R51.B** | P0 | R51.A | QTest onscreen, DPI, AZERTY/QWERTY, manettes réelles. |
| 03 | V1 | **R51.C** | P0 | R51.A+B | Gate R51 |
| 04 | V1 | **R56.A** | P0 | R14/R29/R31/R37/R38/R40 | Tests de déterminisme CT/realtime/quests et provenance des traces. |
| 05 | V1 | **R56.B** | P0 | R56.A | UX Studio, traces/export identiques. |
| 06 | V1 | **R56.C** | P0 | R56.A+B | Gate R56 |
| 07 | V1 | **R57.A** | P0 | R18/R39/R42/R51 | Pseudo-localisation, accents/RTL, encodage. |
| 08 | V1 | **R57.B** | P0 | R57.A | QTest navigation clavier, lecteur d'écran quand supporté. |
| 09 | V1 | **R57.C** | P0 | R57.A+B | Gate R57 |
| 10 | V1 | **R59.A** | P0 | R23/R29/R38/R39/R40/R56/R58 | Reproductibilité de builds, injections de panne. |
| 11 | V1 | **R59.B** | P0 | R59.A | Parcours éditeur→bundle et refus sûr. |
| 12 | V1 | **R59.C** | P0 | R59.A+B | Gate R59 |
| 13 | V2 | **R52.A** | P0 | R3/R19/R36/R39/R51 | Fixtures profondeur/picking multi-caméras; fallback explicite. |
| 14 | V2 | **R52.B** | P1 | R52.A | Goldens par DPI, profils, scène et backend. |
| 15 | V2 | **R52.C** | P0 | R52.A+B | Gate R52 |
| 16 | V2 | **R53.A** | P0 | R8/R21/R26/R37/R41/R43/R51 | Replay CT/action, sérialisation et inventaire sans duplication. |
| 17 | V2 | **R53.B** | P0 | R53.A | Studio↔Player, QTest navigation, Undo/Redo. |
| 18 | V2 | **R53.C** | P0 | R53.A+B | Gate R53 |
| 19 | V2 | **R54.A** | P0 | R25/R27/R35/R44/R52/R59 | Stress interruptions, corruption, données tardives. |
| 20 | V2 | **R54.B** | P0 | R54.A | Test navigation et authoring no-JSON; viewport Qt. |
| 21 | V2 | **R54.C** | P0 | R54.A+B | Gate R54 |
| 22 | V2 | **R55.A** | P0 | R31/R35/R38/R45/R51 | Analyse statique cycles, transactions, replay, fail-closed. |
| 23 | V2 | **R55.B** | P0 | R55.A | QTest graphes, Undo/Redo, conflit de révision. |
| 24 | V2 | **R55.C** | P0 | R55.A+B | Gate R55 |
| 25 | V2 | **R58.A** | P0 | R24/R30/R38/R47/R59 | Imports adversariaux, traversal ZIP, conflits de versions. |
| 26 | V2 | **R58.B** | P1 | R58.A | No-overwrite, Undo, gestion références. |
| 27 | V2 | **R58.C** | P0 | R58.A+B | Gate R58 |
| 28 | V3 | **R60.A** | P0 | R40/R41–R50/R51–R59 P0 | Fixtures historiques Jeanne/CT et jeux R40. |
| 29 | V3 | **R60.B** | P0 | R60.A | Création par Studio, documentation de chaque étape. |
| 30 | V3 | **R60.C** | P0 | R60.A+B | Gate R60 |
| 31 | V4 | **R61.A** | P0 | R35/R45/R55/R56/R60 | Tests emplois concurrent, saturation, conservation. |
| 32 | V4 | **R61.B** | P0 | R61.A | Qt cartes, Undo/Redo, alertes flux. |
| 33 | V4 | **R61.C** | P0 | R61.A+B | Gate R61 |
| 34 | V4 | **R62.A** | P0 | R35/R45/R55/R57/R61 | Reprise minuit, inventaire, récolte non dupliquée. |
| 35 | V4 | **R62.B** | P0 | R62.A | Validation conditions/rythmes, Undo/Redo. |
| 36 | V4 | **R62.C** | P0 | R62.A+B | Gate R62 |
| 37 | V4 | **R63.A** | P0 | R26/R43/R55/R61/R62 | Invariants coûts, limites de ressources, save/replay. |
| 38 | V4 | **R63.B** | P0 | R63.A | Studio→Player E2E, a11y, Undo/Redo. |
| 39 | V4 | **R63.C** | P0 | R63.A+B | Gate R63 |
| 40 | V4 | **R64.A** | P0 | R26/R37/R52/R54/R55/R61 | Replays entiers, collisions, anti-deadlocks. |
| 41 | V4 | **R64.B** | P0 | R64.A | Tests sélection/focus et performances. |
| 42 | V4 | **R64.C** | P1 | R64.A+B | Gate R64 |
| 43 | V4 | **R65.A** | P0 | R26/R32/R36/R37/R43/R53 | Tests collision, synchronisation hitbox, replay. |
| 44 | V4 | **R65.B** | P0 | R65.A | Editeur Qt et Player, a11y motion. |
| 45 | V4 | **R65.C** | P0 | R65.A+B | Gate R65 |
| 46 | V4 | **R66.A** | P0 | R31/R35/R55/R56/R61/R62/R63 | Propriétés conservation/idempotence, concurrence d'événements. |
| 47 | V4 | **R66.B** | P0 | R66.A | UI step/rewind en playtest non destructif. |
| 48 | V4 | **R66.C** | P0 | R66.A+B | Gate R66 |
| 49 | V4 | **R67.A** | P0 | R25/R29/R56/R59/R60 | Budget et choix d'architecture documentés; aucune promesse MMO. |
| 50 | V4 | **R67.B** | P1 | R67.A | Mesures dérives, latence, perte paquets; sécurité. |
| 51 | V4 | **R67.C** | P0 | R67.A+B | Gate R67 |
| 52 | V4 | **R68.A** | P0 | R39/R57/R59/R60 | ADR distincts Web et Android/iOS, scope séparé. |
| 53 | V4 | **R68.B** | P1 | R68.A | Mesures matériel réel et audit installabilité. |
| 54 | V4 | **R68.C** | P0 | R68.A+B | Gate R68 |
| 55 | V4 | **R69.A** | P0 | R24/R47/R48/R58/R59/R67 | Publication locale/hors ligne maintenue. |
| 56 | V4 | **R69.B** | P1 | R69.A | Permissions explicites, confidentialité, UX. |
| 57 | V4 | **R69.C** | P0 | R69.A+B | Gate R69 |
| 58 | V5 | **R70.A** | P0 | R60/R61–R66 P0; R67–R69 conditionnels | Régressions CT/action/R40/R60, corpus multi-seeds. |
| 59 | V5 | **R70.B** | P0 | R70.A | Parcours no-code sans JSON, docs source. |
| 60 | V5 | **R70.C** | P0 | R70.A+B | Gate R70 |
| 61 | V6 | **R74.A** | P0 | R27/R34/R38/R56/R70 | Solveur atteignabilité, rejet d'impasses, provenance. |
| 62 | V6 | **R74.B** | P1 | R74.A | Refus explicite; aucune écriture cachée. |
| 63 | V6 | **R74.C** | P0 | R74.A+B | Gate R74 |
| 64 | V6 | **R75.A** | P0 | R9/R31/R42/R46/R56 | Vérif branches inatteignables, cycles, références. |
| 65 | V6 | **R75.B** | P1 | R75.A | Mode hors ligne possible sans service externe. |
| 66 | V6 | **R75.C** | P0 | R75.A+B | Gate R75 |
| 67 | V6 | **R76.A** | P0 | R4/R36/R52/R54/R59/R70 | Droits, hashes, mesure de taille et qualité. |
| 68 | V6 | **R76.B** | P1 | R76.A | Inspecteur side-by-side, aucun asset original détruit. |
| 69 | V6 | **R76.C** | P0 | R76.A+B | Gate R76 |
| 70 | V6 | **R77.A** | P0 | R29/R37/R56/R66/R74/R75 | Trace exploitable, aucune mutation du contenu auteur. |
| 71 | V6 | **R77.B** | P1 | R77.A | QTest, navigation Studio, comparateur versions. |
| 72 | V6 | **R77.C** | P0 | R77.A+B | Gate R77 |
| 73 | V6 | **R78.A** | P0 | R38/R48/R58/R69/R70 | Aucune écriture silencieuse ni écrasement de fichiers. |
| 74 | V6 | **R78.B** | P1 | R78.A | Tests concurrence à deux auteurs, restore/rollback. |
| 75 | V6 | **R78.C** | P0 | R78.A+B | Gate R78 |
| 76 | V6 | **R71.A** | P0 | R67=GO et R70; sinon reporté | Protocole sérialisé, fuzz, replay serveur. |
| 77 | V6 | **R71.B** | P1 | R71.A | Latence/perte simulées, test offline inchangé. |
| 78 | V6 | **R71.C** | P0 | R71.A+B | Gate R71 |
| 79 | V6 | **R72.A** | P0 | R71=GO/R53/R65/R70 | Injection déconnexions, rollback, conflit de commandes. |
| 80 | V6 | **R72.B** | P1 | R72.A | Tests 2 devices sur réseau isolé. |
| 81 | V6 | **R72.C** | P0 | R72.A+B | Gate R72 |
| 82 | V6 | **R73.A** | P0 | R71/R72=GO/R57/R59 | Tests sécurité commandes, crash/rejoin. |
| 83 | V6 | **R73.B** | P1 | R73.A | UX joueur et créateur, focus/accessibilité. |
| 84 | V6 | **R73.C** | P0 | R73.A+B | Gate R73 |
| 85 | V7 | **R79.A** | P0 | R39/R52/R68/R76; résultats conditionnels | Bench capteur/appareil, matrice OS et compatibilité. |
| 86 | V7 | **R79.B** | P2 | R79.A | Aucune dépendance mandatory pour Player PC. |
| 87 | V7 | **R79.C** | P0 | R79.A+B | Gate R79 |
| 88 | V7 | **R80.A** | P0 | R70/R74–R78/R59/R56; R71–R73/R79 optionnels selon GO | Replays historiques, saves multi-versions, contrôles fail-closed. |
| 89 | V7 | **R80.B** | P0 | R80.A | Chaque template ouvrable, jouable, modifiable et exportable. |
| 90 | V7 | **R80.C** | P0 | R80.A+B | Gate R80 |

### 5.1 Politique Git, branches et consolidation

1. Brancher chaque PR sur `master` **après vérification des prérequis présents sur master**, ou empiler exceptionnellement avec base explicitée et repointer après fusion ; un badge « merged » sur branche intermédiaire n'est pas une preuve d'intégration.
2. Éviter les branches simultanées éditant la même famille de schémas sans ADR/propriétaire ; proposer d'abord un commit contractuel A commun.
3. Fournir pour chaque PR: base/head SHA, migration, statut CI sur SHA final, fixtures, art/UX, compat, liste de fichiers modifiés, risques, limites et issue/lot associé.
4. Ne pas créer une PR globale de 30 versions de code. Les **PR de documentation peuvent grouper la vision**, mais pas remplacer les validations des 90 sous-lots.
5. Tous les merges sont bloqués si tests P0 requis en échec et non expliqués; les hotfixes CI ont une PR séparée et un contrôle des sorties réelles.
6. Consolider au niveau de release seulement après passage des gates unitaires, avec comparaison `tree`, SHA et sources ; fermer les branches empilées seulement quand leurs changements sont sur master.

## 6. Dossier de release et tableau de bord de preuve

Pour R60, R70, R80, maintenir un tableau **ID, P0/P1, version, dépendances, PR, SHA, état master, headless, Qt offscreen, Qt onscreen, GPU matériel, save/replay, export clean-machine, droits, UX humain, régression, limite et décision**. Le tableau des statuts ne doit jamais inventer de preuves.

**R60 GO** : jeu hybride original, HUD personnalisable, groupe, régions, économie, détection de régression, localisation, mise à jour et rollback; au moins 1 auteur tiers et installable tri-OS après vérification.

**R70 GO** : au moins trois projets indépendants (gestion, life sim, survie) avec Gameplay Lab, authoring sans JSON, gameplay/migrations et export; études réseau/mobile explicitement qualifiées en GO/REDUCE/NO-GO mais non bloquantes.

**R80 GO** : six projets indépendants (SRPG Jeanne/original, action-aventure originale, RPG classique, metroidvania, roguelite, gestion/simulation), tous éditables depuis le Studio, Player PC installable, contenu/licences approuvés, tests E2E/qualité/UX tiers, migration et stabilité; réseau et nouvelles plateformes facultatifs selon leurs propres gates.

**Indicateurs produit recommandés :** premier jeu jouable depuis template sans code, temps médian première carte→premier playtest, bugs P0 de sauvegarde, incidents d'assets/licences, temps de correction d'une quête, réussite des exports sur clean-machine, consommation p95/p99 d'un corpus versionné, taux de projets migrés sans intervention manuelle, tâches auteur réalisées au clavier/manette. Fixer les seuils à partir de sessions de mesure, pas d'estimations.

## 7. Risques et arbitrages

| Risque | P | Réponse / condition de réduction |
|---|---|---|
| Trop de genres affaiblit la fiabilité du Studio | P0 | Une slice complète à chaque grand gate; reporter les P2/P1 si la CI, l'UX ou le Player n'est pas prêt |
| R41–R50 non spécifiés réellement | P0 | Écrire, valider et implémenter les contrats nécessaires avant les lots dépendants; jamais inventer leur état |
| UI personnalisée duplique le runtime | P0 | Bindings UI uniquement sur GameSession, mêmes composants Player/Studio et sérialisation unique |
| Simulation hors focus diverge | P0 | Tick entier, approximation documentée, trace et conservation des invariants |
| Grand monde/RTS souffre de l'échelle | P0 | Budgets benchmark matériels, caps explicites, cache borné, annulation |
| Écosystème exécute du code dangereux | P0 | Capabilities, manifestes, sandbox; import fail-closed, revue licences |
| Réseau change scope, coûts et maintenance | P0 | R67 GO/NO-GO; R71–R73 hors chemin critique et pas de promesse MMO |
| Mobile/Web non viable avec Qt stack ou droits | P0 | ADR R68, preuve matériel et budget; PC reste supporté |
| Assistance générative produit du contenu illicite/inutile | P0 | Opt-in, autorisation/licences/provenance, validation humaine, diff, rollback et modes offline |
| Collaboration écrase des changements | P0 | Transactions, analyse sémantique, leases et rejet stale, solution de conflit explicite |
| DoD déclarée verte sur PR ou offscreen | P0 | SHA master + CI + on-screen + GPU réel + install clean-machine + UX selon lot |

## 8. Décisions de lancement

- **Maintenant :** fermer les gates préexistants et les échecs de CI avant de multiplier les PR; cette proposition ne doit pas détourner du chemin R36–R40 ni du travail de documentation R41–R50.
- **À la validation R50 :** découper R51.A, R56.A et R59.A en contrats et tests de référence; planifier le premier jeu vitrine immédiatement.
- **Après R60 :** lancer nouveaux genres par extraction de capacités communes; reporter RTS si les budgets multi-agents ne tiennent pas.
- **Après R67 :** la décision NO-GO réseau est une issue valide; conserver R71–R73 à l'état étude/reporté et avancer R74–R78.
- **Après R80 :** roadmap définie d'après données de créateurs, pas d'engagement implicite de version 13.0, MMO, consoles ou 3D universelle.

---

Liens : [R17–R24](DRAWTEMP_5_0_TO_6_0_DETAILED_ROADMAP.md) · [R25–R30](DRAWTEMP_MULTI_GENRE_CREATOR_ROADMAP.md) · [R31–R40](DRAWTEMP_7_1_TO_8_0_DETAILED_ROADMAP.md). **R41–R50 : document futur à établir.**
