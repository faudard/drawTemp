# DrawTemp — Roadmap détaillée 8.1 → 9.0 (R41–R50)

> **Planification, 19 octobre 2026 — PROPOSITION DOCUMENTAIRE, NON CERTIFIÉE.** Les lots R41–R50 ne sont ni développés ni livrés du simple fait de ce document. Les versions 8.1–9.0 sont des cibles de séquencement, pas des dates de disponibilité. Une PR de documentation et une PR fusionnée ne certifient pas un gate.
>
> **Amont :** [DrawTemp Creator Engine 7.1–8.0 (R31–R40)](DRAWTEMP_7_1_TO_8_0_DETAILED_ROADMAP.md). **Aval :** [PR #368 — proposition 10.0–12.0 R51–R80](https://github.com/faudard/drawTemp/pull/368) ; son document `docs/DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md` est, lors de la rédaction, dans une **PR ouverte**, pas sur `master`.
>
> **Contexte produit :** préserver Jeanne d'Arc, les capacités SRPG, l'action top-down, le metroidvania, le roguelite, les modes hybrides et la capacité de production Studio→Player→export au-delà des seuls tests headless.

## 0. Vision du passage de 8.0 vers 9.0

DrawTemp 9.0 doit devenir un **Studio de création 2D/2.5D multi-genres complet et exploitable** : RPG classique, narration multi-branches, capacités/combat composables, monde en régions, simulation vivante, cinématiques, API d'extensions, collaboration, UX auteur tiers, publication stable. Le critère produit n'est **pas** de posséder les ateliers en catalogue : c'est de produire et maintenir des jeux jouables sans édition de Python/JSON.

Les familles de références (FFT, Zelda, JRPG classiques, etc.) ne sont que des inspirations de mécaniques; les assets, cartes, noms et histoires de ces licences ne doivent pas être copiés. Les six réalisations historiques comprennent quatre genres certifiés conditionnellement à R40, et la certification R50 ajoute un cinquième genre majeur : **RPG classique**, avec un chemin narratif/hybride.

### 0.1 Objectifs hors périmètre

- Pas de moteur 3D universel, multijoueur/MMO, support console, boutique SaaS obligatoire ou streaming continu de grandes cartes (déplacé explicitement à **R54**).
- Pas de refonte de renderer pour chaque genre, de duplication de l'inventaire ou de nouveau système de quêtes concurrent de R9/R31.
- Pas de gestion d'économie complexe ni éditeur système universel à ce stade (fondations R45 ; extensibilité ultérieure **R55**).
- Pas de gestion avancée et centralisée des HUD/UI au-delà des menus de jeu requis pour R41–R49 (le **UI & HUD Designer** complet est **R51**).
- Pas de génération automatique d'assets, d'agent IA créatif obligatoire ou de publication de contenus sans droit de redistribution.

### 0.2 Priorité, statut et preuves

| Code | Sens | Condition de passage |
|---|---|---|
| P0 | Bloquant pour le gate du lot | Tests software nécessaires + UX/Player/GPU/hardware selon le livrable, intégrés sur SHA final de master |
| P1 | Valeur produit à livrer en séquence | Ne remplace aucun gate P0; limites explicitement publiées |
| P2 | Exploration optionnelle | Ne doit pas créer de dette régressive du Core |
| Statut | PROPOSÉ → CODE EN PR → INTÉGRÉ MASTER → CI SHA VERT → UX/GPU VALIDÉ → RELEASE CERTIFIÉE | Ne jamais déduire un statut d'une simple fusion dans une branche intermédiaire |

**DoD commun** : contrat versionné, implementation utilisateur/Player, tests nominaux + adversariaux, migrations explicites, preview/apply avec Undo/Redo, save/load/replay si runtime, annulation, Qt onscreen si UI, GPU matériel si rendu, documentation, export sur machine propre pour gate stable, preuve du SHA master.

## 1. Architecture et invariants non négociables

| Domaine | Préserver | Interdiction / garde-fou |
|---|---|---|
| Modèle canonique | **Content + GameProject**, références, versions/migrations explicites | Aucun sidecar de vérité ni base inventaire/quête bis |
| Édition | **AuthoringSession**, validations, preview/apply, Undo/Redo atomique | Aucune écriture invisible dans l'état runtime |
| Gameplay | **Core headless** CT/RNG/replay + adaptateurs de capacités pour RPG_TURN et action tick fixe | Pas de changement silencieux des règles CT Jeanne |
| Orchestration | **GameSession** détenteur inventaire, quêtes, scènes, groupe, états et persistance | Ni doubles récompenses ni corruption masquée |
| Présentation | **Studio PySide6/Qt Widgets**, Player **Qt Quick**, renderer partagé | Ni renderer distinct par genre ni interaction uniquement mockée |
| Narration | Un moteur R9 Event Graph et R31 Game Logic, conditions/déclencheurs typés | Aucun eval/exec arbitraire ou boucle non bornée |
| Assets/packs | Asset Registry, licences, provenance, checksums, chemins confinés | Export fail-closed si droits manquants |
| Versions/collaboration | Diffs sémantiques, conflits explicites, historique et rollback | Pas de merge silencieux écrasant les données |
| Release | CI headless + GUI + vrais GPU, clean-machine PC, rapports de preuve | Offscreen/software ≠ certification physique |

**Contrat de passage vers R51–R80** : exposer en R50 au moins les points d'extension de l'interface (R51), du groupe (R53), des systèmes (R55), de la QA (R56), des packages (R58) et des mises à jour (R59) par ADR et schémas ; ne pas anticiper une implémentation dans le jalon 9.0.

## 2. Matrice des lots, versions et dépendances

| Lot | Cible proposée | Fonction | Dépendances | Démonstrateur |
|---|---|---|---|---|
| **R41** | 8.1 | Classic RPG & Party Foundations | R8/R10/R25/R28/R31/R37/R40 | VS-41 |
| **R42** | 8.2 | Narrative Studio 2.0 | R9/R10/R11/R20/R31/R35/R38/R41 | VS-42 |
| **R43** | 8.3 | Combat & Ability Designer 2.0 | R8/R13/R21/R26/R28/R31/R36/R37/R41 | VS-43 |
| **R44** | 8.4 | World Builder 2.0 | R5/R6/R27/R34/R35/R38/R40 | VS-44 |
| **R45** | 8.5 | Living Simulation & Economy | R8/R9/R10/R31/R35/R38/R44 | VS-45 |
| **R46** | 8.6 | Cinematic Studio Pro | R11/R19/R36/R42/R43/R57 futur | VS-46 |
| **R47** | 8.7 | SDK & Modding 2.0 | R24/R30/R31/R38/R39/R43 | VS-47 |
| **R48** | 8.8 | Project Collaboration & Versioning | R1/R24/R30/R38/R47 | VS-48 |
| **R49** | 8.9 | Creator Experience & Scale | R18/R22/R28/R38/R41–R48 | VS-49 |
| **R50** | 9.0 | Creator Studio 9.0 Certification | R40 certifié et R41–R49 gates P0 | Release gate 9.0 |

**Chemin critique :** R40 certifié → R41.A/R42.A contrats → R41 RPG classique et R42 narration → R43 combat → R44 monde + R45 simulation → R46 cinéma → R47 SDK + R48 collaboration (en partie parallèles) → R49 UX consolidée → **R50 release 9.0**. Le calendrier est à établir après estimation réelle et mesure des gates; ne pas transformer 8.1–9.0 en dates.

## 3. Détail R41 à R50

## 5. R41 — Classic RPG & Party Foundations (cible 8.1)

**But :** Créer un RPG classique complet sans réécrire le moteur CT/action ni introduire un nouvel inventaire.

**Dépendances principales :** R8/R10/R25/R28/R31/R37/R40. La présence d'un numéro de lot ne certifie pas sa réalisation.

| ID | Priorité | Livrable contrôlable | Dépendances et preuve |
|---|---|---|---|
| R41.1 | P0 | ADR des profils RPG_TURN/Exploration et compatibilité avec GRID_CT/FREE_REALTIME | R25/R40; migrations/flags inconnus rejetés |
| R41.2 | P0 | Roster, groupe actif/réserve, recrutement, remplacement et état commun dans GameSession | R8/R10; crash/restore sans duplication |
| R41.3 | P0 | Ordonnancement RPG_TURN avec ordre d'action explicite et séparation du CT historique | R1/R21; golden Jeanne inchangés |
| R41.4 | P0 | Actions d'équipe: attaque, garde, capacité, objet, fuite, ciblage, KO et victoire/défaite | R8/R43 futur; replay borné/état persisté |
| R41.5 | P0 | Réutilisation classes, statistiques, équipement, inventaire et progression R8 sans registre bis | R8; XP/drop au plus une fois |
| R41.6 | P0 | Transitions exploration→combat→exploration avec conservation des états et flags | R25/R10; corruption/reprise au milieu du combat |
| R41.7 | P0 | Party/Encounter Studio Qt, formulaires typés et tests de références | R28/R38; preview/apply/Undo/Redo |
| R41.8 | P1 | HUD et menus de combat configurables par profils existants, pas de moteur UI nouveau | R18/R39; focus et input |
| R41.9 | P1 | Lab de rencontres/équilibrage, traces des actions et matrices de stats | R13/R29; même seed/simulation |
| R41.10 | P0 | Template RPG classique éditable sans JSON, installable en Player PC | R39/R40; tri-OS, licences et UX |

**Incréments PR proposés :**
- **R41.A — Contrats/Core (P0)** : Contrats PARTY_RPG / RPG_TURN opt-in, règles et données versionnées, migration des anciens profils tactiques inchangés. Tests headless, versionnement, migrations et failure cases obligatoires.
- **R41.B — Studio/Player (P0)** : Ateliers Party/Class/Encounter Qt et écran de combat tour par tour Player, navigation à la manette/clavier. Test Qt offscreen pour non-régression et **onscreen + vrai Player** pour validation utilisateur.
- **R41.C — Intégration/Gate (P0)** : Campagne courte village→donjon→combat→récompense→ville; sauvegarde, replay, export et tests humains. Replays/sauvegardes, matrice tri-OS, assets et captures GPU réels lorsqu'applicables.

**Gate R41 :** Auteur novice produit un RPG classique original : recrutement 3 héros, équipements, 2 rencontres et une quête; parties CT Jeanne inchangées; replay et save/load déterministes, Player PC autonome.

**Vertical slice :** VS-41 — Le relais du village : village, 3 compagnons, combat au tour par tour, butin et retour.

## 6. R42 — Narrative Studio 2.0 (cible 8.2)

**But :** Rendre la narration à branches complexes maintenable, jouable et débogable sans dupliquer Event Graph R9 ni Game Logic R31.

**Dépendances principales :** R9/R10/R11/R20/R31/R35/R38/R41. La présence d'un numéro de lot ne certifie pas sa réalisation.

| ID | Priorité | Livrable contrôlable | Dépendances et preuve |
|---|---|---|---|
| R42.1 | P0 | ADR unique Narration ↔ R9/R31; sources des flags, variables et événements | R9/R31; pas de second évaluateur |
| R42.2 | P0 | Dialogues typés multi-locuteurs, ports branches, conditions et effets inspectables | R9/R10; références/version |
| R42.3 | P0 | Relations/réputation/flags et variables par portée, seule autorité GameSession | R35; sauvegarde/replay et collisions de noms |
| R42.4 | P0 | Déclencheurs de quêtes et état de progression idempotent sans double récompense | R10; assertions après rechargement |
| R42.5 | P0 | Graphes réutilisables et appels de sous-graphes, profondeur bornée et détection de cycles | R31; fuzz conditions/cycles |
| R42.6 | P0 | Narrative Graph Qt avec inspecteur typé, aperçu branches et navigation source→usage | R18/R38; interactions onscreen |
| R42.7 | P0 | Debug narration: step événement, trace, points d'arrêt avant effets, seed et flags | R31; rejouabilité d'une trace |
| R42.8 | P1 | Dialogue à effets de mise en scène avec ancrages cinématiques/audio R11 | R11; seek/skip idem |
| R42.9 | P1 | Première localisation de dialogues avec ID de ligne stable (R57 l'étendra) | R18; accents et longueur |
| R42.10 | P0 | Validation reachability et contre-exemple de route impossible; export vers Player | R29; 3 fins jouables/save/load |

**Incréments PR proposés :**
- **R42.A — Contrats/Core (P0)** : Schémas narratifs canonique condition/choix/conséquence, chemins réutilisables, identifiants stables et migrations. Tests headless, versionnement, migrations et failure cases obligatoires.
- **R42.B — Studio/Player (P0)** : Narrative Graph Qt, inspector contextualisé, outils de dialogues et renvois, debugger des branches/reprises. Test Qt offscreen pour non-régression et **onscreen + vrai Player** pour validation utilisateur.
- **R42.C — Intégration/Gate (P0)** : Quête multi-actes trois fins, conséquences sur alliances/PNJ, checks reachability et playtests externes. Replays/sauvegardes, matrice tri-OS, assets et captures GPU réels lorsqu'applicables.

**Gate R42 :** Construire une intrigue de 3 fins avec 2 branches réutilisées, choix persistants, quête conditionnelle et reprise au milieu d'un dialogue; aucun chemin mort non signalé.

**Vertical slice :** VS-42 — La loyauté du capitaine : trois fins et réputation différenciée.

## 7. R43 — Combat & Ability Designer 2.0 (cible 8.3)

**But :** Concevoir des actions, formules, états et combos multi-genres depuis le Studio, en préservant la déterminisation tactique.

**Dépendances principales :** R8/R13/R21/R26/R28/R31/R36/R37/R41. La présence d'un numéro de lot ne certifie pas sa réalisation.

| ID | Priorité | Livrable contrôlable | Dépendances et preuve |
|---|---|---|---|
| R43.1 | P0 | ADR typage Ability/Effect et adaptateurs CT/Action/RPG_TURN; capacités refusées si indisponibles | R8/R26/R41; compat rétroactive |
| R43.2 | P0 | Formules bornées de dégâts/coût/ressources, arrondis et ordre d'effets versionnés | R1; tests adversariaux et hash |
| R43.3 | P0 | États de durée et interactions élémentaires, stack/dispels/suppression bien définis | R8; pas de double application |
| R43.4 | P0 | Ciblages cases/zones/cones/entités et coordonnées partagées avec viewport R3 | R3/R21; parité picking |
| R43.5 | P0 | Temps d'activation, cooldowns, fenêtres d'interruption et choix de mode sans contamination CT | R25/R32; replays |
| R43.6 | P0 | Graphe compositionnel d'Ability relié R31, sandbox, effets autorisés, budget exécution | R31; cycles et coûts |
| R43.7 | P0 | Ability Designer Qt: palette, édition, prévisualisation, erreurs et Undo/Redo | R28/R38; QTest onscreen |
| R43.8 | P1 | Animation/FX et signaux hitbox synchronisés au tick; baisse flashes opt-in | R36; goldens/GPU |
| R43.9 | P1 | Balance Lab multi-seeds et analyse des contres/combos, limites affichées | R13/R29; métriques sourcées |
| R43.10 | P0 | Affrontement cross-mode et sortie Player PC, traces persistantes et régression Jeanne | R39; E2E scene/save/replay |

**Incréments PR proposés :**
- **R43.A — Contrats/Core (P0)** : Modèle d'abilities versionné et contrats d'effets: coût, portée, timing tick/CT, formules bornées, RNG. Tests headless, versionnement, migrations et failure cases obligatoires.
- **R43.B — Studio/Player (P0)** : Ability/Effect Studio Qt, preview de ciblage, timeline d'impact, tests de formules, outils de balance. Test Qt offscreen pour non-régression et **onscreen + vrai Player** pour validation utilisateur.
- **R43.C — Intégration/Gate (P0)** : Même compétence composée jouée en CT et action via adaptateurs explicites, avec combat replayable et feedback. Replays/sauvegardes, matrice tri-OS, assets et captures GPU réels lorsqu'applicables.

**Gate R43 :** Un auteur crée sans code 4 compétences, dont une à effet de zone et une synergie; chaque profil exécute ses règles sans changement involontaire du CT, temps réel stable 30/60/120 FPS.

**Vertical slice :** VS-43 — L'épreuve des quatre arts : capacités tactiques/action et effet d'équipe.

## 8. R44 — World Builder 2.0 (cible 8.4)

**But :** Permettre de créer de grandes aventures cohérentes avec des régions reliées et événements persistants, sans promettre encore le streaming complet R54.

**Dépendances principales :** R5/R6/R27/R34/R35/R38/R40. La présence d'un numéro de lot ne certifie pas sa réalisation.

| ID | Priorité | Livrable contrôlable | Dépendances et preuve |
|---|---|---|---|
| R44.1 | P0 | WorldGraph régional versionné (scènes, entrées/sorties, connexions, régions) | R27; validate références |
| R44.2 | P0 | Politique de coordonnées/top-down/iso et conversion monde/picking, sans nouveau renderer | R3/R25; scènes anciennes intactes |
| R44.3 | P0 | Persistance état des coffres/portes/PNJ/flags par scène à travers les transitions | R10/R35; crash/reload |
| R44.4 | P0 | Portails conditionnels et trajets à coûts explicites, cycles et sorties invalides rejetés | R9/R25; non-duplication |
| R44.5 | P0 | Biomes et palettes de terrain, références vers assets licites | R4/R34; import/export |
| R44.6 | P0 | World Atlas Qt: cartes connectées, navigation et inspection destination/conditions | R27/R38; Undo/Redo |
| R44.7 | P0 | Validation reachability de clés, quêtes et portes sur graphes inter-scènes | R27/R29; contre-exemples |
| R44.8 | P1 | Génération assistée déterministe de lieux/route soumise à validation auteur | R34; seeds/contraintes |
| R44.9 | P1 | Profiling taille/carte/temps de chargement, budgets avant toute promesse streaming | R14; données machines |
| R44.10 | P0 | Slice 5 régions et export Player; transition fiable et sauvegarde complète | R39; 3 OS clean-machine |

**Incréments PR proposés :**
- **R44.A — Contrats/Core (P0)** : Schéma régions, portails, topologies, coordonnées, biomes et persistance; métriques de capacité. Tests headless, versionnement, migrations et failure cases obligatoires.
- **R44.B — Studio/Player (P0)** : World Atlas Qt: liens, minimap, conditions, édition multi-scènes, validation de références. Test Qt offscreen pour non-régression et **onscreen + vrai Player** pour validation utilisateur.
- **R44.C — Intégration/Gate (P0)** : Aventure en 5 zones distinctes avec retours, portes conditionnelles, navigation PNJ et save/load. Replays/sauvegardes, matrice tri-OS, assets et captures GPU réels lorsqu'applicables.

**Gate R44 :** Créer/éditer cinq régions, voyager via passages explicites, revenir sur zones modifiées et retrouver tous les états sans édition JSON; contenu exporté et rejouable.

**Vertical slice :** VS-44 — La route des cinq vallées : carte mondiale et événements persistants.

## 9. R45 — Living Simulation & Economy (cible 8.5)

**But :** Donner des systèmes de vie/commerce simples et vérifiables, bases des futurs System Designer R55 et Farming R62.

**Dépendances principales :** R8/R9/R10/R31/R35/R38/R44. La présence d'un numéro de lot ne certifie pas sa réalisation.

| ID | Priorité | Livrable contrôlable | Dépendances et preuve |
|---|---|---|---|
| R45.1 | P0 | ADR sur frontières R35 world time, R8 inventaire, R9 flags et économie canonical | R35/R8; modèle de vérité unique |
| R45.2 | P0 | Marchands: prix entiers bornés, monnaie et stocks avec transaction atomique | R8; anti-duplication/reload |
| R45.3 | P0 | Recettes simples consommations/productions déterministes, contraintes de ressources | R8; tests conservation |
| R45.4 | P0 | Routines PNJ conditionnelles et politique simulation hors focus documentée | R35; projections convergentes |
| R45.5 | P0 | Quêtes quotidiennes et dates/événements périodiques idempotents | R31/R42; rollover minuit |
| R45.6 | P0 | Conditions faction/réputation appliquées aux commerces/activités et conséquences | R35/R42; branchement test |
| R45.7 | P0 | Living Economy Qt: inspecteur stocks, agendas et source des changements | R18/R38; preview/apply/Undo |
| R45.8 | P1 | Paramètres météo/saison comme variables de jeu seulement; visuel piloté par R36 | R35/R36; opt-in |
| R45.9 | P1 | Balance Lab économique limité: 7–30 jours, métriques, limites de densité | R29/R35; benchmark |
| R45.10 | P0 | Village complet, joueur achetant/fabriquant/vendant, états et droits export | R39; Player, save, QA |

**Incréments PR proposés :**
- **R45.A — Contrats/Core (P0)** : Extensions canonique stock/inventaire, recettes, commerce, besoins simples et horloge, avec invariants de conservation. Tests headless, versionnement, migrations et failure cases obligatoires.
- **R45.B — Studio/Player (P0)** : Economy/Living Studio Qt, calendriers, aperçu des transactions et des effets sur les PNJ. Test Qt offscreen pour non-régression et **onscreen + vrai Player** pour validation utilisateur.
- **R45.C — Intégration/Gate (P0)** : Village marchand avec production, échange, réputation et calendrier sur plusieurs jours, sans dupe. Replays/sauvegardes, matrice tri-OS, assets et captures GPU réels lorsqu'applicables.

**Gate R45 :** Sur une simulation de 7 jours, stocks, achats, quêtes et PNJ restent cohérents avec/sans focus et après minuit, crash et reprise; un auteur contrôle ces règles dans Studio.

**Vertical slice :** VS-45 — Le marché de sept jours : PNJ, stocks, artisanat et réputation.

## 10. R46 — Cinematic Studio Pro (cible 8.6)

**But :** Unifier narration, animation, son et cinématiques non linéaires sans deuxième timeline ni synchronisation de gameplay fondée sur le rendu.

**Dépendances principales :** R11/R19/R36/R42/R43/R57 futur. La présence d'un numéro de lot ne certifie pas sa réalisation.

| ID | Priorité | Livrable contrôlable | Dépendances et preuve |
|---|---|---|---|
| R46.1 | P0 | ADR R11 timeline unique, autorité GameSession et synchronisation tick→animation | R11/R31; pas de deuxième runtime |
| R46.2 | P0 | Tracks typeés pour acteurs, caméra, animation, dialogue, son, FX et variables | R36/R42; migrations |
| R46.3 | P0 | Sémantique événements à effets de bord, skip/seek/pause et checkpoints atomiques | R9/R11; pas de dupe |
| R46.4 | P0 | Découpage plans, interpolation contrôlée, cadrage et occlusion multi-projections | R3/R36; goldens |
| R46.5 | P0 | Références voix/sous-titres/locales/provenance sans média non autorisé | R4/R42; licences |
| R46.6 | P0 | Editeur Timeline Qt multi-pistes: trim/preview/zoom/scrub, Undo/Redo | R18/R38; QTest |
| R46.7 | P1 | Événements interactifs avec choix de branche reliés Narrative Studio | R42; chemins sûrs |
| R46.8 | P1 | Transitions cinématiques↔action↔CT et règles d'input/pause | R25/R43; logs/replay |
| R46.9 | P0 | Parité Player/Studio: vidéos logiques, audio et sous-titres conformes | R36/R39; onscreen et GPU |
| R46.10 | P0 | Mini-épisode avec 2 parcours et reprise à la minute précédente | R39; clean machine/QA |

**Incréments PR proposés :**
- **R46.A — Contrats/Core (P0)** : Chronologie unique versionnée, plans, tracks, caméra, événements idempotents, pause/skip/seek contractuels. Tests headless, versionnement, migrations et failure cases obligatoires.
- **R46.B — Studio/Player (P0)** : Timeline Qt avancée avec aperçu, dialogues, doublage autorisé, sous-titres et actions de caméra. Test Qt offscreen pour non-régression et **onscreen + vrai Player** pour validation utilisateur.
- **R46.C — Intégration/Gate (P0)** : Cinématique branchée à la quête avec 2 parcours, sauts sûrs, sauvegarde et parité Studio/Player. Replays/sauvegardes, matrice tri-OS, assets et captures GPU réels lorsqu'applicables.

**Gate R46 :** Une cinématique ramifiée de 90 s cible est montée sans code; lancement, skip, seek, reload et interruptions conservent les mêmes effets logiques sans les jouer deux fois.

**Vertical slice :** VS-46 — Conseil de guerre : scène dialoguée, combat déclenché, deux sorties.

## 11. R47 — SDK & Modding 2.0 (cible 8.7)

**But :** Stabiliser un SDK de création extensible et des capacités de plugins sûres, documentées et compatibles.

**Dépendances principales :** R24/R30/R31/R38/R39/R43. La présence d'un numéro de lot ne certifie pas sa réalisation.

| ID | Priorité | Livrable contrôlable | Dépendances et preuve |
|---|---|---|---|
| R47.1 | P0 | Public API Stability ADR: contrats publics, compat semver, dépréciations | R24/R30; fixtures |
| R47.2 | P0 | Capabilities granulaire: lecture/proposition/action autorisée, refus par défaut | R24/R31; sécurité permissions |
| R47.3 | P0 | Manifestes versions/dépendances/compatibilité, hachage et signatures si disponibles | R4/R30; absence de droits=NO-GO |
| R47.4 | P0 | Isolation du code externe ou limitation aux extensions déclaratives en fonction du sandbox prouvé | R31; aucun eval/exec libre |
| R47.5 | P0 | Exécution bornée et contrôles input/timeout/mémoire selon capacités autorisées | R31; tests malveillants |
| R47.6 | P0 | Schémas/IDs de ressources exposées; migration et gestion plugin manquant | R1/R24; roundtrip |
| R47.7 | P1 | Plugin Manager/Inspector Qt: diff permissions, enable/disable, provenance, rollback | R38; opérations réversibles |
| R47.8 | P1 | Docs SDK et 2 exemples reproductibles cross-platform sans API privée | R39; tutorial auteur |
| R47.9 | P0 | Matrix API de compatibilité multi-version et licences dépendances | R14/R23; tests CI |
| R47.10 | P0 | Deux packs/plug-ins approuvés dans deux jeux, import/export vérifié | R39; E2E PC |

**Incréments PR proposés :**
- **R47.A — Contrats/Core (P0)** : ABI/API Python exposée sous capacités strictes, semver, manifests, migrations, ressources autorisées. Tests headless, versionnement, migrations et failure cases obligatoires.
- **R47.B — Studio/Player (P0)** : Plugin/SDK Inspector Qt, exemples documentés, validation des permissions et désinstallation non destructive. Test Qt offscreen pour non-régression et **onscreen + vrai Player** pour validation utilisateur.
- **R47.C — Intégration/Gate (P0)** : Deux extensions indépendantes (combat et UI outil) installées, versionnées et retirées sans casser le jeu. Replays/sauvegardes, matrice tri-OS, assets et captures GPU réels lorsqu'applicables.

**Gate R47 :** Deux plugins déclaratifs/contrôlés testés Windows/Linux/macOS, install/downgrade/remove propres, droits d'assets vérifiés; suppression = diagnostic des dépendances, jamais perte cachée.

**Vertical slice :** VS-47 — Deux extensions installables sans fork du Core.

## 12. R48 — Project Collaboration & Versioning (cible 8.8)

**But :** Élever les diff sémantiques et la gestion de versions déjà amorcés vers un workflow multi-auteur fiable, sans cloud obligatoire.

**Dépendances principales :** R1/R24/R30/R38/R47. La présence d'un numéro de lot ne certifie pas sa réalisation.

| ID | Priorité | Livrable contrôlable | Dépendances et preuve |
|---|---|---|---|
| R48.1 | P0 | Réutiliser R38.6 diff/merge canonique Content/GameProject et sorties de preuves | R38; identifiants stables |
| R48.2 | P0 | Contrats rebase/upstream, révisions immuables, digest sémantique et résolution stale | R1/R30; collisions/rollback |
| R48.3 | P0 | Merge typé de listes/graphes/scènes sans écrasement implicite | R31/R38; cas adversariaux |
| R48.4 | P0 | Renommage global/reference graph cross-document avec preview/apply | R38; undo complet |
| R48.5 | P0 | Journal audit append-only local et provenance commits/versions, pas de sidecar de vérité | R24; reconstruction contrôlée |
| R48.6 | P0 | UX de résolution des conflits Qt: comparaison valeurs et provenance, choisir/apply | R38; QTest/onscreen |
| R48.7 | P1 | Annotations/revues liées aux IDs d'entités et diff PR/export, sans données privées imposées | R38; persistance locale |
| R48.8 | P1 | Intégration Git optionnelle et mode offline prioritaire | R30; aucun écrasement |
| R48.9 | P0 | Tests 2 auteurs, perturbations crash, références cassées et annulation atomique | R14; stress |
| R48.10 | P0 | Démonstrateur multi-scènes merge sans perte, export identique après résolution | R39; E2E |

**Incréments PR proposés :**
- **R48.A — Contrats/Core (P0)** : Protocole projets, branches/versions, refactor typé, merges sémantiques et validation staleness. Tests headless, versionnement, migrations et failure cases obligatoires.
- **R48.B — Studio/Player (P0)** : Project History & Review Qt pour comparer, annoter et résoudre conflits manuellement. Test Qt offscreen pour non-régression et **onscreen + vrai Player** pour validation utilisateur.
- **R48.C — Intégration/Gate (P0)** : Deux auteurs modifient simultanément carte et dialogue, merge documenté sans perte et tests de conflits. Replays/sauvegardes, matrice tri-OS, assets et captures GPU réels lorsqu'applicables.

**Gate R48 :** Deux branches divergentes d'un même projet sont réunies dans le Studio par résolution typée; Undo/Redo, référents et Player restent intacts; aucune mutation silencieuse.

**Vertical slice :** VS-48 — Deux auteurs, carte et quête modifiées, conflit résolu.

## 13. R49 — Creator Experience & Scale (cible 8.9)

**But :** Rendre le Studio apprenable par un auteur tiers, avec une vraie productivité, sans cacher les diagnostics ni multiplier les outils.

**Dépendances principales :** R18/R22/R28/R38/R41–R48. La présence d'un numéro de lot ne certifie pas sa réalisation.

| ID | Priorité | Livrable contrôlable | Dépendances et preuve |
|---|---|---|---|
| R49.1 | P0 | Auditer parcours Studio de 8.0 et ateliers R41–R48, supprimer commandes sans action | R40; capture E2E |
| R49.2 | P0 | Workspaces profilés et navigation globale cohérente, focus persistant, raccourcis sans conflit | R18/R38; QTest |
| R49.3 | P0 | Template Wizard SRPG/action/RPG/narration, ressources conformes et schémas validés | R28/R41; scénario no-JSON |
| R49.4 | P0 | Inspector commun et erreurs inline pour ressources, graphes, classes, états, licences | R38/R47; source→usage |
| R49.5 | P0 | Undo/Redo multi-ateliers et recovery après crash, travaux longs annulables | R1/R38; fault injection |
| R49.6 | P0 | Mode playtest aller/retour précis: contexte Studio→Player→Studio, diagnostics conservés | R22/R29; E2E |
| R49.7 | P1 | Tutoriels contextualisés avec jeux exemples et versions d'API | R41–R48; tests auteur |
| R49.8 | P1 | Accessibilité Studio: tab/focus, contraste, narration des contrôles et DPI | R18/R40; tests hardware |
| R49.9 | P0 | Benchmark ouverture gros projet et outils recherche/undo, p95/p99 mesurés | R14/R38; baseline hardware |
| R49.10 | P0 | Test auteur tiers complet sans JSON: menu, scène, quête, combat, export | R39; rapport et vidéo/captures |

**Incréments PR proposés :**
- **R49.A — Contrats/Core (P0)** : Parcours de production documentés, navigation unifiée, métriques de flux et contrats de commande. Tests headless, versionnement, migrations et failure cases obligatoires.
- **R49.B — Studio/Player (P0)** : Onboarding/templates, recherche, inspecteurs, commandes et outils contextuels cohérents. Test Qt offscreen pour non-régression et **onscreen + vrai Player** pour validation utilisateur.
- **R49.C — Intégration/Gate (P0)** : Études de créateurs tiers sur scénarios guidés et libres, focus/accessibilité/profiler, corrections P0. Replays/sauvegardes, matrice tri-OS, assets et captures GPU réels lorsqu'applicables.

**Gate R49 :** Un auteur tiers crée mini-jeu depuis template, modifie cartes/règles/dialogues, lance playtest et exporte sans JSON; erreurs P0 d'UX et commandes inactives supprimées.

**Vertical slice :** VS-49 — Premier jeu en Studio : nouveau projet → scène → action → export.

## 14. R50 — Creator Studio 9.0 Certification (cible 9.0)

**But :** Produire une preuve de plateforme utilisable par des auteurs externes et définir des contrats fiables pour R51–R80.

**Dépendances principales :** R40 certifié et R41–R49 gates P0. La présence d'un numéro de lot ne certifie pas sa réalisation.

| ID | Priorité | Livrable contrôlable | Dépendances et preuve |
|---|---|---|---|
| R50.1 | P0 | Release Ledger R41–R49: PR, SHA master, preuves CI/UX/GPU/export, risques et limitations | R14/R39; états non confondus |
| R50.2 | P0 | Compatibilité schémas/migrations 5.x→9.x + rollback, fixtures content/gameproject/saves | R16/R40; corruption injection |
| R50.3 | P0 | Régression CT Jeanne/siège, action temps réel, platformer/roguelite et narrations à seed fixe | R40/R41–R46; golden replay |
| R50.4 | P0 | Catalogue de cinq templates originaux sans assets protégés et imports documentés | R40/R41; licences/attribution |
| R50.5 | P0 | Création, modification, playtest, sauvegarde et publication sans JSON depuis Studio | R49; auteur tiers |
| R50.6 | P0 | Tests UI onscreen, manette/clavier, a11y, langues, résolutions et QML Player partagé | R18/R36/R49; test hardware |
| R50.7 | P0 | Exécution de bundles sur PC propres Windows/Linux/macOS, dépendances et SBOM | R23/R39; SHA final |
| R50.8 | P0 | Performance CPU/GPU p95/p99, mémoire/endurance avec corpus/matériel et seuils calibrés | R14/R29; rapports reproductibles |
| R50.9 | P0 | Audit sandbox/plugin, licences et transparence du preflight fail-closed | R47; cas adversariaux |
| R50.10 | P0 | Rapport GO/NO-GO et contrat public minimal R51 UI, R53 Party, R55 Systems, R56 QA | R41–R49; aucune promesse non prouvée |

**Incréments PR proposés :**
- **R50.A — Contrats/Core (P0)** : Gel des APIs/schémas et migrations, corpus de jeux/replay/asset/licences, audit de dépendances et migration. Tests headless, versionnement, migrations et failure cases obligatoires.
- **R50.B — Studio/Player (P0)** : Quatre templates historiques R40 + RPG classique + narrative/hybride supplémentaires éditables sans JSON, tutoriels. Test Qt offscreen pour non-régression et **onscreen + vrai Player** pour validation utilisateur.
- **R50.C — Intégration/Gate (P0)** : Certification de Player PC tri-OS, tests matériels et utilisateurs, performance p95/p99, décision GO/NO-GO publique. Replays/sauvegardes, matrice tri-OS, assets et captures GPU réels lorsqu'applicables.

**Gate R50 :** Cinq familles de jeux minimum (SRPG, action-aventure, RPG classique, metroidvania, roguelite) sont réellement jouables/éditables/exportables sur PC propre; jeu narratif/hybride documenté en démonstrateur. Aucun P0 non prouvé ni état de sauvegarde dégradé.

**Vertical slice :** VS-50 — DrawTemp 9.0 : catalogue auteur de 5 jeux + slice narrative/hybride.


## 4. Vertical slices et preuve croisée

| Slice | Produit démontrable | Conditions de réussite |
|---|---|---|
| VS-41 | Le relais du village : village, 3 compagnons, combat au tour par tour, butin et retour. | Studio éditable sans code; Player fonctionnel; save/load/replay et reprise |
| VS-42 | La loyauté du capitaine : trois fins et réputation différenciée. | Studio éditable sans code; Player fonctionnel; save/load/replay et reprise |
| VS-43 | L'épreuve des quatre arts : capacités tactiques/action et effet d'équipe. | Studio éditable sans code; Player fonctionnel; save/load/replay et reprise |
| VS-44 | La route des cinq vallées : carte mondiale et événements persistants. | Studio éditable sans code; Player fonctionnel; save/load/replay et reprise |
| VS-45 | Le marché de sept jours : PNJ, stocks, artisanat et réputation. | Studio éditable sans code; Player fonctionnel; save/load/replay et reprise |
| VS-46 | Conseil de guerre : scène dialoguée, combat déclenché, deux sorties. | Studio éditable sans code; Player fonctionnel; save/load/replay et reprise |
| VS-47 | Deux extensions installables sans fork du Core. | Studio éditable sans code; Player fonctionnel; save/load/replay et reprise |
| VS-48 | Deux auteurs, carte et quête modifiées, conflit résolu. | Studio éditable sans code; Player fonctionnel; save/load/replay et reprise |
| VS-49 | Premier jeu en Studio : nouveau projet → scène → action → export. | Studio éditable sans code; Player fonctionnel; save/load/replay et reprise |
| VS-50 | DrawTemp 9.0 : catalogue auteur de 5 jeux + slice narrative/hybride. | Install tri-OS, licences et tests humains |

**Corpus de non-régression transversal** :
1. **Jeanne CT/siege** : initiative, positions, RNG, formations, replay, XP, états, sauvegardes et portails inchangés sans opt-in.
2. **Action top-down** : inputs horodatés, collisions et interactions indépendants des FPS affichés; save/load/replay après changements de scènes.
3. **Metroidvania R33 et roguelite R34** : reachability, portes/compétences, seeds, progression meta sans duplication.
4. **Narration et monde vivant** : embranchements quêtes, horloges, PNJ hors-focus et minuit sans divergence à la reprise.
5. **Studio/Player** : mêmes données, camera/picking et visuels partagés; Qt offscreen pour non-régression et onscreen/hardware pour acceptation.
6. **Licence/export** : les ressources et extensions importées ne franchissent jamais le preflight si la provenance, les droits ou manifests sont invalides.

### 4.1 Matrice d'acceptation R50 (proposée)

| Famille | Projet témoin | Auteur Studio | Moteur & Player | Certification attendue |
|---|---|---|---|---|
| SRPG | Jeanne/siege | Mission avec classe et tactiques CT | Replay seed et save d'une mission complète | Migrations historiques et export PC |
| Action-aventure | Village/donjon/boss original | Carte, personnage, capacités, coffre | Exploration réelle et combat action | Input 30/60/120 FPS, QA matériel |
| RPG classique | VS-41 | Groupe, rencontres RPG_TURN, inventaire | Tour par tour distinct du CT | Aucun effet collatéral sur Jeanne |
| Metroidvania | Projet R33 | Capacité unlock, saut, portes | Reachability et plateforme tick fixe | Export + tests UX |
| Roguelite | Projet R34 | Recettes génération, objets, seed | Run/meta, save/replay | 100 seeds et reward exactly-once |
| Narration/hybride | VS-42/43/46 | Dialogues, choix, effets, cinématique | Conséquences persistantes entre action/CT | Trois fins, pas de softlock |

**Budget de performance :** définir CPU, mémoire, p50/p95/p99, taille de scènes et GPU de référence *après benchmark réel*. Un objectif 60 FPS sur corpus choisi implique p95 frame-time approximativement ≤16,7 ms, mais aucun chiffre n'est ici une mesure existante. P95 UI souhaité ≤100 ms hors tâches longues; opérations longues annulables et signalées.

## 5. Séquencement des 30 PR de code **futures**

> Ce document crée **zéro PR de code** ; les lignes suivantes sont des lots d'implémentation proposés, à ouvrir un par un après les prérequis. Une PR documentaire ne donne aucun statut de certification.

**V01 — Profils RPG + sémantique des variables et capacités partagées, pas de fork Core.** Dépendances : R40 master gate, ADR schemas et replay baseline.

**V02 — Clore RPG classique et narration, valider jeu témoin complet.** Dépendances : R41.A, R42.A, R31/R9 effectifs.

**V03 — Actions multi-genre et fondations de monde/économie.** Dépendances : R41/R42 interfaces, R43.A, R27/R35.

**V04 — Atlas visuel et village sur calendrier fiable.** Dépendances : R44.A, R45.A, R35 + documents graphiques.

**V05 — Cinématique et contrat SDK commun.** Dépendances : R42/R43 et R11/R36, R24.

**V06 — Extensions robustes et workflow multi-auteur.** Dépendances : R47.A, R38/R30 et sérialisation stable.

**V07 — Finition UX et onboarding sur les fonctions disponibles.** Dépendances : R41–R48 P0 et outils R38.

**V08 — Release 9.0 certifiée, préparation API R51–R80.** Dépendances : Gates R41–R49 et tests de certification finaux.

| Ordre | Vague | Sous-lot / PR suggérée | Domaine de changement | Base minimale |
|---:|---|---|---|---|
| 01 | V01 | **R41.A** | Contrats, versionnement et tests headless | R40 master gate, ADR schemas et replay baseline |
| 02 | V01 | **R42.A** | Contrats, versionnement et tests headless | R40 master gate, ADR schemas et replay baseline |
| 03 | V01 | **R43.A** | Contrats, versionnement et tests headless | R40 master gate, ADR schemas et replay baseline |
| 04 | V02 | **R41.B** | Studio/Player + E2E UI | R41.A, R42.A, R31/R9 effectifs |
| 05 | V02 | **R41.C** | Gate, vertical slice et preuves de release | R41.A, R42.A, R31/R9 effectifs |
| 06 | V02 | **R42.B** | Studio/Player + E2E UI | R41.A, R42.A, R31/R9 effectifs |
| 07 | V02 | **R42.C** | Gate, vertical slice et preuves de release | R41.A, R42.A, R31/R9 effectifs |
| 08 | V03 | **R43.B** | Studio/Player + E2E UI | R41/R42 interfaces, R43.A, R27/R35 |
| 09 | V03 | **R43.C** | Gate, vertical slice et preuves de release | R41/R42 interfaces, R43.A, R27/R35 |
| 10 | V03 | **R44.A** | Contrats, versionnement et tests headless | R41/R42 interfaces, R43.A, R27/R35 |
| 11 | V03 | **R45.A** | Contrats, versionnement et tests headless | R41/R42 interfaces, R43.A, R27/R35 |
| 12 | V04 | **R44.B** | Studio/Player + E2E UI | R44.A, R45.A, R35 + documents graphiques |
| 13 | V04 | **R44.C** | Gate, vertical slice et preuves de release | R44.A, R45.A, R35 + documents graphiques |
| 14 | V04 | **R45.B** | Studio/Player + E2E UI | R44.A, R45.A, R35 + documents graphiques |
| 15 | V04 | **R45.C** | Gate, vertical slice et preuves de release | R44.A, R45.A, R35 + documents graphiques |
| 16 | V05 | **R46.A** | Contrats, versionnement et tests headless | R42/R43 et R11/R36, R24 |
| 17 | V05 | **R46.B** | Studio/Player + E2E UI | R42/R43 et R11/R36, R24 |
| 18 | V05 | **R46.C** | Gate, vertical slice et preuves de release | R42/R43 et R11/R36, R24 |
| 19 | V05 | **R47.A** | Contrats, versionnement et tests headless | R42/R43 et R11/R36, R24 |
| 20 | V06 | **R47.B** | Studio/Player + E2E UI | R47.A, R38/R30 et sérialisation stable |
| 21 | V06 | **R47.C** | Gate, vertical slice et preuves de release | R47.A, R38/R30 et sérialisation stable |
| 22 | V06 | **R48.A** | Contrats, versionnement et tests headless | R47.A, R38/R30 et sérialisation stable |
| 23 | V06 | **R48.B** | Studio/Player + E2E UI | R47.A, R38/R30 et sérialisation stable |
| 24 | V06 | **R48.C** | Gate, vertical slice et preuves de release | R47.A, R38/R30 et sérialisation stable |
| 25 | V07 | **R49.A** | Contrats, versionnement et tests headless | R41–R48 P0 et outils R38 |
| 26 | V07 | **R49.B** | Studio/Player + E2E UI | R41–R48 P0 et outils R38 |
| 27 | V07 | **R49.C** | Gate, vertical slice et preuves de release | R41–R48 P0 et outils R38 |
| 28 | V08 | **R50.A** | Contrats, versionnement et tests headless | Gates R41–R49 et tests de certification finaux |
| 29 | V08 | **R50.B** | Studio/Player + E2E UI | Gates R41–R49 et tests de certification finaux |
| 30 | V08 | **R50.C** | Gate, vertical slice et preuves de release | Gates R41–R49 et tests de certification finaux |

### 5.1 Branches et règles de fusion

- La première PR de chaque thème est **A** : ADR, schémas, tests headless; elle cible `master` après certification réelle des prérequis.
- La PR **B** ajoute édition / Player, et est basée sur A seulement en pile explicite ; repointer sur master dès qu'A est vraiment intégrée. Une PR B fusionnée dans une branche A non merged n'est **pas** dans master.
- La PR **C** livre la vertical slice et le gate : tests E2E, licences, captures, replay, migrations, faisabilité clean-machine; elle clôt le lot seulement si les preuves sont accessibles.
- Préférer **3 petites PR par R** au lieu d'une méga-PR 9.0; ne créer les PR que lorsque les contrats stabilisés et les conflits sur les fichiers de schéma sont connus.
- Documenter pour chaque PR : base/head et SHA, fichiers, liens aux gates, métadonnées de versions, CI, statut Qt onscreen/GPU, données test et qualité, limites et rollback.
- Les modules R41/R43 (combat/règles) et R42/R45 (variables/économie) se coordonnent via ADR A partagé pour prévenir les conflits sur GameSession/Content/GameProject.

## 6. Release Gate R50 : procédure GO / NO-GO

**Entrées bloquantes :** R40 réellement stable sur le SHA master; gates R41–R49 P0 fermés; ressources/licences approuvées; Studio Qt et Player sur même renderer; compatibilité des anciennes sauvegardes et jeux.

**Dossier de preuve :** statut PAR LOT, numéro de PR, SHA présent sur master, tests headless/Qt offscreen/onscreen/GPU, exports trois OS, auteur tiers, contrôle des assets et droits, rapport d'échecs, budget perf instrumenté, décision GO/NO-GO datée. Ne pas confondre un succès de test unitaire avec une certification d'usage.

**Condition GO** : un utilisateur tiers crée/modifie et exporte cinq genres PC (SRPG, action-aventure, RPG classique, metroidvania, roguelite), avec une intrigue hybride jouable, replays/save corrects, licences conformes et aucune anomalie P0 de workflow/undo/sauvegarde; le produit s'installe sur PC propre (Win/Linux/macOS).

**Conditions NO-GO** : CT Jeanne cassé ; perte silencieuse; double récompense; script/plugin non sandboxé; ressources interdites exportées; UI factice; données différentes Studio/Player; tests offscreen présentés comme GPU; gate CI P0 rouge; machine propre échoue; pas de test créateur réel.

## 7. Registre risques / arbitrages et limites

| Risque | Importance | Réponse attendue |
|---|---|---|
| Développement R41–R50 sans R40 validé | P0 | Garder prototypes séparés; interdire « release certifiée » avant preuves |
| Inventaires ou moteurs combat dupliqués | P0 | Contrats R41/R43 ↔ R8/GameSession; adaptateurs de genre sans fork |
| R42 et R31 possèdent deux systèmes de logique | P0 | Réutiliser R9/R31; traces, typage et idempotence |
| Monde R44 présenté comme streaming complet | P0 | R44 = graphe et persistance; **R54** = streaming grande échelle |
| Simulation R45 présentée comme System Designer complet | P0 | R45 = fondations économiques bornées; **R55** = composition générale |
| UI de R41 présentée comme UI Designer complet | P0 | R41 = menus consommés via widgets existants; **R51** = édition complète |
| Extension R47 dangereuse | P0 | Sandbox, capabilities, signatures/provenance/licence et fail-closed |
| Conflits R48 écrasent un document | P0 | Diff sémantique et validation des révisions, rollback et tests adversariaux |
| CI prête sur PR mais rouge sur master | P0 | Vérifier SHA master après fusion avec artefacts/GPU/hardware |
| Trop de scope et création impossible pour utilisateurs | P0 | Une slice jouable par lot; R49 tests utilisateurs avant certification R50 |

## 8. Suites et liens vers R51–R80

- R50 constitue la **baseline contractuelle** pour R51 (UI/HUD Designer), R53 (Party & Combat), R55 (System Designer), R56 (Gameplay QA), R58 (Packages) et R59 (mises à jour).
- La roadmap prospective R51–R80 est proposée dans [PR #368](https://github.com/faudard/drawTemp/pull/368). **Ne pas déclarer son document en master avant merge effectif** ; après fusion, ajouter un lien canonique relatif et garder la matrice de compatibilité.
- Les R41–R50 et R51–R80 restent des propositions. Les futurs tickets, implémentations et certifications doivent expliciter la branche cible et ne pas impliquer une sortie commerciale immédiate.

**Prochain incrément de développement admissible après gate R40 : R41.A — contrats RPG classique, portée de GameSession et compatibilité CT ; puis R42.A pour la narration typée.**
