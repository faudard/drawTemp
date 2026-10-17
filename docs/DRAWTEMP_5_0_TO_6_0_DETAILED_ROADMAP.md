# DrawTemp — Roadmap détaillée de la consolidation 5.0 à la plateforme 6.0

> **Document de planification — 15 octobre 2026.** Complément de la [roadmap 5.0 canonique](DRAWTEMP_5_0_ROADMAP.md), qui conserve intégralement les lots R0 à R16. Les lots R17 à R24 sont **proposés**, non implémentés ou certifiés par le simple ajout de ce fichier.
>
> **Règle de lecture :** une PR fusionnée n'implique ni la présence de toutes les branches empilées dans master, ni la validation d'un gate, ni une livraison publique. Les états GitHub ci-dessous correspondent à une vérification ponctuelle, non à un tableau de bord vivant.

## 0. Vision, frontières et Definition of Done

**Vision produit :** permettre de créer un Tactical RPG 2.5D isométrique narratif — carte, bâtiments, personnages, animations, base RPG, événements, campagne, siège, cinématiques, audio, IA, équilibrage — depuis un Studio graphique, de le tester immédiatement et d'exporter un Player autonome sans saisie manuelle de JSON.

**Architecture non négociable :**
- Studio : PySide6/Qt Widgets, docks et modèles Qt, viewport Qt Quick.
- Player : PySide6/Qt Quick et même renderer isométrique R3 ; séparation simulation/présentation.
- Core/SDK : Python headless, CT, RNG, IA, formations, campagne, événements, replay déterministe.
- Données métier : une paire canonique Content/GameProject, migrations explicites, AuthoringSession, preview/apply, transactions Undo/Redo. Ne pas créer un second registre RPG, un second moteur tactique ou un sidecar de vérité.
- Art : Asset Registry, manifests versionnés, provenance et autorisation de redistribution ; pas de placeholder considéré comme asset de release.
- Transition : conserver les dépendances de compatibilité sporebound/Tk tant que le remplacement complet R16 n'est pas démontré.

**Statuts distincts par ligne :** (1) proposition, (2) code proposé en PR, (3) code vérifié sur master, (4) gate automatisé vert sur le SHA final, (5) UX/visuel certifiés humainement, (6) release certifiée. Une ligne passe à « validée » uniquement avec une preuve consultable.

**Priorités :** P0 = bloque le gate annoncé ; P1 = indispensable à la version complète mais séquençable ; P2 = extension différable. Un chiffre de performance est une **cible à étalonner**, pas un résultat constaté.

**Definition of Done par lot :** comportement réel + tests au bon niveau (headless/Qt onscreen/GPU selon besoin) + intégrité Content/GameProject + tests des erreurs et annulations + preuve Windows/Linux/macOS si portable + documentation + captures comparées pour tout changement UI + inventaire des limites. Une simulation QML software/offscreen n'est pas une certification GPU matériel.

## 1. Baseline vérifiée et risques de fusion

État ponctuel GitHub au 15/10/2026 :
- [#248 R7.B](https://github.com/faudard/drawTemp/pull/248) est la PR encore ouverte lors de la vérification. Son état de mergeabilité peut changer : contrôler sa base et sa CI avant fusion.
- [#264 R7.C](https://github.com/faudard/drawTemp/pull/264), costumes Jeanne/équipement, a été fusionnée **vers la branche de #248**, et non directement vers master ; prouver sa présence après intégration finale.
- [#263 R9.C](https://github.com/faudard/drawTemp/pull/263) et [#273 R9.D](https://github.com/faudard/drawTemp/pull/273) sont fusionnées dans une branche d'événements intermédiaire ; auditer leur présence dans master, plutôt qu'inférer leur intégration du badge « merged ».
- [#255 R15](https://github.com/faudard/drawTemp/pull/255), [#253 R16](https://github.com/faudard/drawTemp/pull/253), [#254 R14](https://github.com/faudard/drawTemp/pull/254) et [#275 R14.5](https://github.com/faudard/drawTemp/pull/275) ont été fusionnées : **leur existence n'est pas un certificat de packaging/GPU/UX**.
- INT-03 exige une preuve des 99 PNG physiques et, pour toute distribution, des droits de modification/redistribution réellement approuvés. Le document [INT-03](drawtemp5/INT03_ASSET_PUBLICATION.md) indique que les droits restent à valider ; ne pas forcer le gate.
- Le [suivi R16](drawtemp5/R16_LEGACY_MIGRATION.md) indique que R16.4/R16.5 restent conditionnés à la certification réelle des remplaçants. Le nettoyage de sporebound/Tk n'est pas une action indépendante.

**Audit de branche obligatoire (INT-CROSS-01) :** relever pour chaque PR base/head/SHA, comparer tree et commits à master, inventorier les fichiers survivants et comparer les symboles/features attendus. Une PR empilée fusionnée dans une branche qui n'a pas atteint master reste **non intégrée au produit**.

### 1.1 Matrice de reprise des jalons existants R0–R16

| Jalon conservé | Validation de fermeture à effectuer | Gate principal |
|---|---|---|
| R0 Architecture | Baseline, ADR, scénarios de migration et fixtures Jeanne rejouables | Origine/provenance des tests et rollback |
| R1 Tactical Core SDK | CT/RNG/events/replay/save identiques après import, crash et reprise, sans import Qt dans Core | Rapport de déterminisme au SHA final |
| R2 Foundation Studio | Docks, explorateur, inspecteur typé, saisie et focus cohérents, zéro double propriétaire | Scénario Qt réel avec Undo/Redo |
| R3 Renderer commun | Identité Studio/Player pour profondeur, caméra, couches, personnages, picking | Goldens approuvés + profilage GPU |
| R4 Assets | Import, atlas, IDs, droits et chemins identiques après export | Gate fail-closed provenance/licences |
| R5 Map Editor | Carte avec AutoBlend, calques, sélection, bâtiments, événement et live test sans JSON | E2E souris/clavier + persistance |
| R6 Construction | Portes, murs, intérieurs, étages, LOS et escaliers réellement tactiques | Mouvement IA/Player multiétage |
| R7 Character Studio | Quatre directions, poses distinctes, variantes persistantes et export runtime | Preuve #248 + #264 et revue artistique |
| R8 RPG Database | Classes, objets, compétences, états, IA et référence contrôlées | Lancier créé puis vérifié en combat |
| R9 Event Studio | Pages, conditions, commandes, graphes, priorités et conséquences | Porte/levier/dialogue/replay |
| R10 Campaign & Siege | Campagne liée, progression, embranchements, multi-fronts et fins | Trois missions/deux fins sauvegardables |
| R11 Cinématique/Audio | Timeline et documents partagés, playback/seek/sons/interruptions | Même séquence en Studio et Player |
| R12 Player | Menu, exploration, combat, animations, autosaves et options utilisables | Jeu autonome + recovery |
| R13 AI/Balance Lab | Simulation répétable, analyse justifiable, limites de diagnostics explicites | Replays réels + playtests humains |
| R14 QA | CI trois OS, GUI onscreen, goldens, métriques hardware et endurance | Agrégation sans faux vert |
| R15 Export | Player/Studio assemblés et installés sur machines propres | Run complet sans Python/Studio |
| R16 Legacy | Migrations réversibles, imports Tk éliminés uniquement après équivalence prouvée | Rapport migration + aucun parcours cassé |

## 2. Versions et ordre de développement

| Release cible proposée | Chantiers | Dépendance de gate | Produit vérifiable |
|---|---|---|---|
| 5.0 RC → stable | R17 | R0–R16 vérifiés au niveau P0 | Tranche Jeanne éditable → jouable → exportable |
| 5.1 | R18 | R17 stable, contrôles Studio/Player réels | UX de création claire et HUD utilisable |
| 5.2 | R19 | R3/R4/R7/R12 certifiés et bibliothèques licites | Vertical slice artistiquement cohérent |
| 5.3 | R20 | R9/R10/R11/R12 + R18/R19 initiaux | Acte I Jeanne terminable |
| 5.4 | R21 | R6/R8/R10/R13 + contenu R20 | Siège jouable sous plusieurs stratégies |
| 5.5 beta | R22 | R5–R11 fiables, R15 fonctionnel | Jeu créé dans le Studio sans JSON |
| 5.5 stable | R23 | R17–R22 et tests de release | Distribution et projet de démo certifiés |
| 6.0 | R24 | 5.5 stable et SDK stabilisé | Second jeu indépendant, plugins maîtrisés |

**Chemin critique :** INT-CROSS-01 → R17 → R18/R19 (parallélisables) → R20 → R21/R22 (partiellement parallèles) → R23 → R24. Ne pas attendre R20 pour lancer les tests de performance, la documentation ou le prototype d'export.

## 3. R17 — Post-merge Integration & Release Readiness

> **Avancement du 17 octobre 2026, code en PR non fusionné :** [#280 R17.C1](https://github.com/faudard/drawTemp/pull/280) restitue le moteur R9.D (pages, priorité, activation, répétition, replay et édition transactionnelle) et son workflow dédiée ; [#281 R17.C2](https://github.com/faudard/drawTemp/pull/281), empilée sur #280, restitue le graphe Qt, les commandes typées, la présentation narrative et les marqueurs ISO. La CI R17.C1 a réussi sur le dernier SHA examiné ; la matrice complète, la certification GUI/GPU et l'E2E porte/levier/Player/export restent **ouverts**. Ces deux PR ne constituent pas encore un jalon R17.3 validé dans master.

**But :** terminer les contrats 5.0, fermer les écarts d'intégration, sans ajouter une nouvelle architecture.

| ID | Priorité | Livrable vérifiable et comportement attendu | Dépendances et preuves |
|---|---|---|---|
| R17.1 Merge Ledger | P0 | Registre de PR, parents, SHAs, fichiers, statut réel dans master, code orphelin et conflits documentés | #248/#264/#263/#273 ; diff et tests |
| R17.2 R7 Bridge | P0 | Atlases exportés visibles dans Studio/Player ; quatre facings, cycle attaque/marche, tenue pilotée par équipement | R3/R4/R7/R8/R12 ; démonstration Qt |
| R17.3 R9 Graph Integration | P0 | Pages, priorités, conditions et événements rémanents accessibles depuis carte/graphes, mêmes références sauvegardées | R1/R9 ; test portes/leviers, replay |
| R17.4 One Authoring Session | P0 | R5–R11 éditent le même contenu transactionnel ; rejet d'une preview obsolète entre deux ateliers | R1/R2 ; test de concurrence |
| R17.5 Renderer Equivalence | P0 | Même géométrie, ordre de profondeur, atlas, couches, caméra, picking et étages Studio/Player | R3/R5/R6/R12 ; captures et pixels |
| R17.6 Asset Integrity | P0 | Assets réels présents, manifestes cohérents, SHA, licences de redistribution/transformation documentées ; refus explicite sinon | R4/INT-03 ; rapport fail-closed |
| R17.7 Persistence & Replay | P0 | CT/RNG/events, checkpoint manuel/auto, backup et récupération sans mutation silencieuse ni perte de récompenses | R1/R12 ; crash/fault injection |
| R17.8 Clean-machine Export | P0 | Export Windows/Linux/macOS autonome, fichiers nécessaires embarqués, Player démarre sans le Studio | R15/R14 ; test installation propre |
| R17.9 GPU Certification | P0 | Goldens validés, frame-times p50/p95/p99 et VRAM matériel réel, tests zoom/DPI, aucune mesure software appelée GPU | R3/R14 ; rapport par GPU/backend |
| R17.10 Legacy Transition | P0 | Inventaire et suppression progressive Tk/Canvas après remplacement prouvé ; rollback des projets anciens | R16 ; compatibilité et import |
| R17.11 Error Recovery UX | P0 | Messages et actions claires lors de corruption, fichier externe modifié, pack invalide, échec d'écriture ou retour arrière | R2/R12/R15 ; tests GUI |
| R17.12 Cross-workshop E2E | P0 | Carte→bâtiment→personnage→classe→événement→campagne→cinématique→Player→save→export | R1–R16 ; scénario avec assets réels |
| R17.13 Release Evidence | P0 | Manifeste SHA, logs, captures, listes des risques, critères satisfaits et notes de version | Tous gates P0 ; revue externe |

**Gate R17 :** un testeur crée/édite une mission Jeanne depuis le Studio Qt, joue dans un Player Qt exporté, sauvegarde/reprend et vérifie la parité graphique sans accès à Python développeur. Toute licence « pending », import cassé, perte de données ou E2E rouge bloque la certification 5.0.

## 4. R18 — Studio & Player UX 2.0 (5.1)

**But :** transformer l'accumulation d'ateliers en un outil compréhensible et fluide.

| ID | Priorité | Livrable vérifiable et comportement attendu | Dépendances et preuves |
|---|---|---|---|
| R18.1 Navigation globale | P0 | Projet, Carte, Construction, Personnages, Base RPG, Événements, Campagne, Cinématiques, Analyse, Publication sans doublons | R2/R5–R15 ; navigation clavier |
| R18.2 Menu principal Studio | P0 | Nouveau/Ouvrir/Récents/Enregistrer sous/Playtest/Exporter/Préférences, actions réelles et raccourcis | R2/R15 ; GUI E2E |
| R18.3 Workspace Layout | P0 | Viewport central dominant, explorateur à gauche, inspecteur à droite, timeline/diagnostic en bas, presets persistants | R2 ; multi-écrans et DPI |
| R18.4 Inspector 2.0 | P0 | Propriétés typées, édition multiple, valeurs mixtes, validations inline, navigation des références, Undo atomique | R1/R2 ; transactions |
| R18.5 Outils contextuels | P0 | Outils fenêtre/porte/intérieur uniquement en mode construction, pinceaux uniquement en mode carte | R5/R6 ; commande impossible hors contexte |
| R18.6 Explorer & Search | P0 | Recherche, filtres, favoris, références entrantes/sortantes, navigation des objets manquants | R2/R8/R9 ; index persistants |
| R18.7 Command Palette | P1 | Raccourcis visibles/remappables, menus contextuels, recherche de commandes et collisions détectées | R2/R12 ; tests clavier |
| R18.8 Player Title & Flow | P0 | Menu Nouvelle partie/Continuer/Charger/Options/Quitter, transitions propres et retour au titre | R12 ; E2E utilisateur |
| R18.9 Tactical HUD | P0 | CT, portrait, PV/PM, actions, compétences, coût, LOS, couvert, intentions, historique d'actions | R12/R13 ; cohérence calcul |
| R18.10 Game Input | P0 | Souris, clavier AZERTY/QWERTY, sélection et confirmation séparées, aucun clic ambigu sur étages | R3/R12 ; tests réels |
| R18.11 Notifications et erreurs | P0 | Sauvegarde, crash recovery, conflits externes, import illégal et validation présentés avec solution | R1/R15 ; erreurs injectées |
| R18.12 Accessibilité + FR/EN | P1 | Focus, contraste, scaling, lecteurs d'écran Qt lorsque pris en charge, textes externalisés | R2/R12 ; audit manuel |
| R18.13 Onboarding & UX Tests | P0 | Parcours guidé de premier projet, états vides utiles, tests novices avec erreurs recensées | R17 ; protocole et résultats |

**Gate R18 :** un utilisateur sans expertise du dépôt peut créer une carte, placer Jeanne, associer un événement et jouer sans ouvrir JSON ni CLI ; un joueur termine une première rencontre et retrouve sa partie sans écran de développement.

## 5. R19 — Art Direction, Assets & Renderer 2.0 (5.2)

**But :** élever la qualité de rendu tout en gardant la lisibilité tactique et un renderer unique.

| ID | Priorité | Livrable vérifiable et comportement attendu | Dépendances et preuves |
|---|---|---|---|
| R19.1 Bible graphique | P0 | Palette aquarelle, échelles, lignes, lumière, silhouettes, densité et règles Studio/Player documentées | R4 ; échantillons approuvés |
| R19.2 Assets de production | P0 | Pack terrain/personnages avec provenance et droits vérifiés, sans placeholders annoncés comme finis | R4/INT-03 ; manifeste |
| R19.3 Jeanne Animation Set | P0 | N/S/E/O et animations distinctes idle, marche, course, attaque, magie, blocage, hit, mort, victoire | R7/R12 ; revue image par image |
| R19.4 Outfits synchronisés | P0 | Paysanne, apprentie, armure, blessée ; apparence liée aux équipements/événements persistants | R7/R8 ; save/load |
| R19.5 Bestiaire cohérent | P1 | Loup, bandit, archer, lancier, chevalier, soigneur, officier, boss ; silhouettes et pivots cohérents | R7/R8 ; comparatifs 4 directions |
| R19.6 Terrains et AutoBlend | P0 | Herbe/terre/route/eau/pierre/falaise/biomes sans coutures et avec variantes contrôlées | R3/R4/R5 ; goldens |
| R19.7 Paysages animés | P1 | Eau, végétation, feu, fumée, météo, ombres ; effets ne masquant pas les intentions tactiques | R3/R4 ; FPS + lisibilité |
| R19.8 Architecture 2.5D | P0 | Façades, toitures, pièces, escaliers, portes, fenêtres, étages et cutaway stable | R6/R3 ; picking/LOS |
| R19.9 Animations runtime | P0 | Interpolation visuelle de déplacement, ordonnancement attaque/impact, interruption/reprise, timing indépendant CT | R3/R12 ; replay inchangé |
| R19.10 Caméra cinématique | P1 | Suivi, traveling, zoom contextuel, limites, shake réglable ; respect du picking et du confort | R3/R11 ; tests zoom |
| R19.11 Optimisation terrain | P0 | Chunks 8×8 ou taille benchée, cache borné, invalidation dirty tiles, culling, mémoire et VRAM mesurées | R3.D/R14 ; comparatif before/after |
| R19.12 Scene Profiles | P0 | Scènes village/forêt/château, cartes 32²/64²/128², 80 acteurs, 1x/2x DPR et zooms | R14 ; mesures matérielles |
| R19.13 Revue artistique | P0 | Planche avant/après, captures goldens approuvées humainement et rejets documentés | R14.5 ; décision explicite |
| R19.14 Dégradation maîtrisée | P1 | Paramètres qualité GPU avec mêmes règles, picking et assets essentiels, pas de faux GPU benchmark | R12 ; smoke multi-profil |

**Gate R19 :** village, forêt, bâtiments, Jeanne et ennemis composent une scène cohérente, sans pose artificiellement recyclée ni apparition double ; rendu identique Studio/Player à états égaux. **Cible initiale**, à réviser après profilage : 60 FPS, p95 frame-time ≤16,7 ms sur configuration matérielle cible documentée ; jamais certifiée par l'offscreen.

## 6. R20 — Jeanne d'Arc : Les Cendres du Royaume, Acte I (5.3)

**But :** produire une campagne narrative uchronique à laquelle les outils de création sont confrontés réellement.

| ID | Priorité | Livrable vérifiable et comportement attendu | Dépendances et preuves |
|---|---|---|---|
| R20.1 Bible narrative | P0 | Chronologie, fiches personnages, motivations, factions, liens, contraintes de ton et arbres des choix | R9/R10 ; revue cohérence |
| R20.2 Prologue village | P0 | Jeanne paysanne, dialogue, interaction, tutorial exploration, loup/premier combat et départ | R5/R7/R12 ; scène jouable |
| R20.3 Village en crise | P0 | Transition dramatique, personnages concernés, choix local avec conséquence durable | R9/R11 ; state persisté |
| R20.4 Chapitre Fuite | P0 | Forêt, rencontre, embuscade, nouveaux alliés, introduction terrain/formation | R8/R13 ; combat jouable |
| R20.5 Chapitre Refuge | P0 | Ville/refuge, relations, dialogue politique, quêtes, progression et deuxième mission liée | R9/R10 ; embranchements |
| R20.6 Héroïne et antagonistes | P1 | Relations évolutives, personnages récurrents, conflit puis rapprochement éventuel selon choix et cohérence | R9/R10 ; QA narrative |
| R20.7 Progression des classes | P0 | XP/JP ou schéma retenu, compétences, équipements, tenues visibles et états persistants | R8/R7/R12 ; roundtrip |
| R20.8 Quêtes/variables | P0 | Conditions, flags, dialogues alternatifs, événements uniques/répétitifs correctement contrôlés | R9 ; replay/QA graphe |
| R20.9 Campaign Flow | P0 | Missions, scènes et conséquences reliées ; au moins deux chemins significatifs et fins d'acte | R10 ; path certification |
| R20.10 Cinématiques | P1 | Intro, transition, événements dramatiques, caméra et animation synchronisées, skip sûr | R11 ; export Player |
| R20.11 Audio narratif | P1 | Ambiances, musiques, SFX combats/scènes, mixage et licences vérifiées | R11/R4 ; écoute et manifeste |
| R20.12 Encounters tactiques | P0 | Rencontres différenciées par espace/rôles/objectifs, pas seulement hausse de PV | R13 ; playtest |
| R20.13 QA Acte I | P0 | Parcours des branches, dialogues, sauvegarde/reprise, récompenses non dupliquées, zéro softlock connu | R14 ; tests E2E |
| R20.14 Démo distribuable | P0 | Début/fin de l'acte I via Player autonome, menus, options, sauvegardes et feedback de testeurs | R15/R23 précoce ; rapport |

**Gate R20 :** trois missions narratives liées au minimum, une bifurcation réellement persistante, une fin d'acte identifiable, et un joueur externe peut tout terminer sans Studio ni compréhension des formats. La qualité narrative est revue humainement, pas « prouvée » par des tests de graphe seuls.

## 7. R21 — Tactical RPG & Castle Siege 2.0 (5.4)

**But :** faire dépendre les résultats du placement, de la préparation et des synergies autant que des dégâts.

| ID | Priorité | Livrable vérifiable et comportement attendu | Dépendances et preuves |
|---|---|---|---|
| R21.1 CT et intentions | P0 | CT conservé, prochaine activation lisible, zones de charge/incantation/risque exactes | R1/R12/R13 ; replay |
| R21.2 Vigilance/réactions | P0 | Attaques d'opportunité, blocage, garde, contres, réactions déclenchées sans ambiguïté | R8/R13 ; séquences testées |
| R21.3 Positionnement avancé | P0 | Flanc, encerclement, arcs de menace, couvert, lignes de vue, hauteur et étranglements | R6/R13 ; dégâts comparés |
| R21.4 Formations | P0 | Phalange, mur de boucliers, lance longue, escorte et protection mutuelle, avec rupture lisible | R8/R13 ; simulation |
| R21.5 Coordination ennemie | P0 | Lancier protège archer/soigneur, officier orchestre, repli et renforts, IA explicable | R13 ; traces décisions |
| R21.6 Classes et synergies | P1 | Spécialisations, équipements et compétences combinées, progression et contre-jeu | R8/R20 ; équilibre |
| R21.7 Terrain et intérieurs | P0 | Collision, escalier, porte, herse, mezzanine, étages, navigation IA réaliste | R6/R13 ; scénarios multiétages |
| R21.8 Siege Preparation | P0 | Choix d'équipe, équipement, déploiement, objectifs, chemins d'assaut | R10/R12 ; sauvegarde |
| R21.9 Siège extérieur | P0 | Bélier poussé puis frappant la porte, pont-levis/herse, tours de siège, grappin ou catapulte selon contenu | R6/R10 ; état simulé |
| R21.10 Fronts synchronisés | P0 | Remparts, cour, ravitaillement, renforts ; progression globale et résolution hors focus sans perte d'état | R1/R10 ; replay save/load |
| R21.11 Infiltration/diplomatie | P1 | Stratégies alternatives, conditions narratives et conséquences contrôlées | R9/R10/R20 ; deux branches |
| R21.12 Salle du trône | P0 | Boss à phases télégraphiées, états environnementaux et renforts sous règles traçables | R13 ; tests multi-seeds |
| R21.13 Fins de siège | P0 | Victoire, accord, défaite cohérents et persistés ; aucune fin inaccessible par défaut de script | R10 ; path validation |
| R21.14 Balance Lab | P0 | Analyse seeds, distribution pertes/durée, heatmaps et statistiques couplées au replay exact | R13 ; QA humaine et CI |

**Gate R21 :** le siège se termine par au moins deux approches tactiques cohérentes, avec plusieurs fronts, portes/escaliers, boss et conséquences durables. L'IA ne téléporte pas les unités hors simulation et le replay reste déterministe.

## 8. R22 — Creator Studio 2.0 (5.5 beta)

**But :** industrialiser la création sans écrire du JSON ni ouvrir des écrans techniques isolés.

| ID | Priorité | Livrable vérifiable et comportement attendu | Dépendances et preuves |
|---|---|---|---|
| R22.1 Project Wizard | P0 | Projet vierge/Jeanne/template tactique, dossiers, identité du jeu, paramètres et validation initiale | R2/R15 ; création réelle |
| R22.2 Carte avancée | P0 | Peinture, lasso, prefabs, calques, terrains et génération déterministe avec prévisualisation/annulation | R5 ; transactions |
| R22.3 Monde & biomes | P1 | Connexion des cartes, routes, lieux, variantes biomes et restrictions de génération non destructrice | R5/R10 ; navigation |
| R22.4 Construction 2.5D | P0 | Bibliothèque maisons, murs, toitures, fenêtres, intérieurs, étages, éditeur séparé de l'outil terrain | R6 ; Player parité |
| R22.5 Character Workshop | P0 | Silhouette, couleurs, tenues, animations, portraits et export contrôlé de sprite | R7/R4 ; atlas runtime |
| R22.6 Bestiaire | P1 | Création modèles d'ennemis, variantes, rôles, drops et présentation cohérente | R7/R8 ; combat |
| R22.7 RPG Rules | P0 | Classes, compétences, états, AI profiles, progression et équipement avec diagnostics de références | R8 ; simulation |
| R22.8 Events Graph 3.0 | P0 | Pages, branches, dialogues, variables, actions tactiques, debugger et prévisualisation sur viewport | R9 ; replay |
| R22.9 Campaign Studio | P0 | Actes, missions, passages, fins, état global, front de siège et simulation de chemins | R10 ; certification |
| R22.10 Cinematic & Audio | P1 | Timeline multipiste, animations, audio/FX, scrubbing, preview exact Player et raccord événement | R11 ; A/V QA |
| R22.11 Live Playtest | P0 | Tester une scène depuis le contexte édité, revenir sans altérer le document, copier logs utiles | R1/R12 ; roundtrip |
| R22.12 Resource Workspace | P0 | Import batch, catalogues, vignettes, références, licences et ressources cassées visibles | R4/R2 ; preflight |
| R22.13 Production Dashboard | P1 | État projet, validation, risques/ressources, builds/export, historique rapports sans faux feux verts | R14/R15 ; provenance |
| R22.14 First-game Acceptance | P0 | Un tiers crée trois cartes, deux personnages, un combat, un choix et exporte sans aide du code | Tous ateliers ; session observée |

**Gate R22 :** une mini-campagne nouvelle est créée entièrement dans les ateliers Qt avec sauvegarde, annulation, preview, export et reprise. Pas d'éditeur métier qui « marche » seulement avec un fichier préparé manuellement.

## 9. R23 — Public Release & Certification 5.5

**But :** publier un produit de création utilisable et maintenable, pas une succession de builds.

| ID | Priorité | Livrable vérifiable et comportement attendu | Dépendances et preuves |
|---|---|---|---|
| R23.1 Installateurs | P0 | Studio Windows/macOS/Linux installable et désinstallable proprement, version et manifestes stables | R15 ; VM propre |
| R23.2 Export de jeux | P0 | Player portable/installer autonome, ressources, licences, dépendances correctes et démarrage offline | R15/R22 ; E2E |
| R23.3 Save/Migration | P0 | Compatibilité garantie des formats supportés, backup/recovery, rollback, refus explicite des formats inconnus | R1/R16 ; injections |
| R23.4 Sécurité des imports | P0 | Chemins, zips, manifests, ressources externes, scripts/plugins, tailles bornées et validation stricte | R14/R24 design ; corpus malveillant |
| R23.5 Performance matérielle | P0 | Scènes cibles, FPS p50/p95/p99, consommation CPU/GPU/VRAM, buffers et temps de chargement | R3/R14 ; rapport |
| R23.6 Endurance | P0 | Longues sessions création+jeu, changements carte/partie, autosave et restauration en cas de crash | R12/R14 ; soak tests |
| R23.7 Accessibilité | P1 | Contrastes, navigation clavier, textes, réglages Player, remapping et problèmes critiques résolus | R18 ; audit |
| R23.8 UX Playtests | P0 | Testeurs créateurs/joueurs, blocages, retours classés, corrections et preuve de retest | R18–R22 ; rapports |
| R23.9 Documentation | P0 | Guide premier projet, référence formats/API, tutos carte/événement/campagne/export, limites connues | R22 ; test tutoriel |
| R23.10 Licensing & Attribution | P0 | Droits sources/dérivés vérifiés, notices embarquées, paquets d'assets non conformes bloqués | R4/INT-03 ; revue |
| R23.11 Release Automation | P0 | Artefacts OS, checksums, métadonnées, changelog, reproductibilité et contrôle SHA commun | R14/R15 ; provenance |
| R23.12 Go/No-go | P0 | Décision formelle à partir de tous les gates, anomalies et dérogations documentées | Tous P0 ; signature |

**Gate R23 :** un testeur installe Studio, crée un mini-jeu, l'exporte et distribue le Player à une machine propre ; sauvegarde et reprise fiables, ressources légalement redistribuables, parcours principaux et performances validés selon la matrice de release.

## 10. R24 — DrawTemp 6.0 Creator Platform

**But :** rendre les outils réutilisables sur plusieurs jeux sans remettre en cause les contrats de 5.5.

| ID | Priorité | Livrable vérifiable et comportement attendu | Dépendances et preuves |
|---|---|---|---|
| R24.1 SDK semver | P1 | API versionnée de simulation, authoring, renderer-read models et export ; dépréciations annoncées | R1 ; compatibilité |
| R24.2 Plugins Studio | P2 | Extensions contrôlées des panels/outils/inspecteurs, manifeste capacités, isolation des erreurs | R2/R22 ; projet exemple |
| R24.3 Data Extension Contracts | P1 | Schémas versionnés ou namespaces d'extensions explicites, validation/migration/références sûres | R1/R8 ; roundtrip |
| R24.4 Packs ressources | P1 | Publication/import de bibliothèques avec hash/licence/version/dépendances, aucune collision IDs silencieuse | R4/R23 ; intégrité |
| R24.5 Scripting contrôlé | P2 | Hooks documentés et permissions limitées, déterminisme des actions gameplay ou refus explicite | R1/R9 ; replay |
| R24.6 Renderer scale | P2 | Bench cartes et mondes plus vastes, streaming/chunks, caches bornés, GPU profiling comparatif | R3/R19 ; profils |
| R24.7 Simulation massive | P2 | Battle Lab avec campagnes de seeds, analyse des performances et contrôles d'annulation | R13 ; rapports |
| R24.8 Collaboration et VCS | P2 | Diff sémantique pour Content/GameProject, comparaison/résolution contrôlée, aucun merge sauvage | R1 ; tests conflits |
| R24.9 Templates & Examples | P1 | Deuxième univers jouable distinct de Jeanne, modèles de classe/ennemi/carte/campagne réutilisables | R22 ; certification |
| R24.10 Modding & Distribution | P2 | Packages tiers signés ou inspectables, compatibilité et risques documentés, permissions explicites | R23 ; sécurité |
| R24.11 Tooling QA | P1 | Suite compatibilité API/plugins, fixtures de versions, contrôles de performance et migration | R14/R23 ; CI |
| R24.12 Platform 6.0 Gate | P1 | Créer/exporter un deuxième jeu sans fork du Core ni changement de renderer | Tous les R24 P1 ; jeu témoin |

**Gate R24 :** un créateur peut produire un second Tactical RPG de genre/univers différent en ne changeant que contenu, assets et extensions autorisées ; compatibilité du projet 5.5 préservée ou migration explicite.

## 11. Vertical slices de référence

| Scène d'acceptation | Création Studio | Player, combat, narration | Preuves requises |
|---|---|---|---|
| VS-01 Village | Route, prairie, rivière, maison, Jeanne, loup, dialogues | Exploration puis rencontre, résultat | Parité Studio/Player, autosave, replay |
| VS-02 Levier & porte | Porte, levier, condition, page événement, son, cinématique | Interaction, ouverture, progression, retour | Undo/Redo, choix, persistance, déterminisme |
| VS-03 Maison à étages | Toiture, étage, escalier, décor, portes | Traversée et combat avec LOS/occlusion | Picking, navigation IA, sauvegarde |
| VS-04 Trois missions | Branches de campagne, équipement, personnages | Deux routes, conséquences et deux fins | Path certification, restauration |
| VS-05 Siège | Remparts, cour, bélier, vagues, fronts, salle du trône | Assaut ou infiltration, boss, fins | Timeline multifronts, save/replay |
| VS-06 Export externe | Build jeu après preflight | Installation sur PC sans outils Studio | Manifeste/licences, ouverture/sauvegarde |

## 12. Preuves, budgets et politique de release

### 12.1 Matrice de certification minimale

| Axe | Preuve attendue | Bloque quelle version |
|---|---|---|
| Données | Content/GameProject même hashes avant/après roundtrip, migrations sûres, sauvegarde atomique | 5.0 |
| Déterminisme | CT, RNG, events, résultats après replay, multi-seeds et crash injection | 5.0 |
| GUI | QTest + parcours souris/clavier réels Studio/Player, écran et offscreen documentés | 5.0 |
| Parité rendu | Scènes identiques, deux applications, zoom/DPI/niveaux, images goldens acceptées | 5.0 |
| Assets & droits | Fichiers physiques/hashes/licences/transformation/redistribution et exports | 5.0 |
| GPU | CPU, GPU, VRAM, p50/p95/p99, pilotes, Qt RHI, capture de scène sur machine physique | 5.0 |
| Créateur novice | Réaliser une carte puis jeu sans modifier les données manuellement | 5.1 et 5.5 |
| Campagne Jeanne | Enchaîner missions/choix/sauvegardes jusqu'au générique d'acte | 5.3 |
| Siège | Multi-fronts, environnement, alternatives, boss, deux chemins valides | 5.4 |
| Publication | Installer depuis bundle OS, jeu exporté indépendant, UX et documentation revues | 5.5 |
| Extensibilité | Nouvel univers et plugin test dans contrats semver | 6.0 |

### 12.2 Budgets proposés, à calibrer sur baseline

- **Rendu :** objectif 60 FPS sur profil PC défini après mesure (p95 ≤ 16,7 ms) ; p99 et spikes enregistrés. Comparer scènes 32×32, 64×64, 128×128, à 24/54/96 px et jusqu'à 80 acteurs. Ne pas déduire la vitesse GPU de frameSwapped ou d'un rendu logiciel.
- **Studio :** cible p95 < 100 ms geste→retour pour opérations ordinaires ; toute génération lourde passe par worker annulable et révision contrôlée.
- **Chargement :** mesurer p50/p95 de lancement Studio/Player, chargement projet, changement de mission et export ; définir budgets après baseline.
- **Sécurité :** interruption au milieu de la sauvegarde/export, corruption fichiers/backup, conflit de révision et import malformé doivent échouer sans modifier silencieusement l'état sain.
- **QA :** rapports nomment SHA Git, versions Python/Qt/PySide6, OS, backend, carte, résolution, GPU et pilote ; green sur un autre SHA ≠ preuve de release.

### 12.3 Go/No-go

Une release est refusée si l'un des points suivants demeure : perte silencieuse de données, incompatibilité non détectée des sauvegardes, assets interdits ou à droits inconnus redistribués, crash sans récupération, export incapable de tourner sans environnement de développement, incohérence de gameplay entre Studio/Player, triche de certification (fallback ou tests non exécutés), défaut majeur de navigation bloquant un scénario de référence.

Les défauts P1/P2 peuvent être différés uniquement si le périmètre de la version est ajusté explicitement, sans déclarer le jalon intégralement terminé.

## 13. Plan de PR incrémentales (bases explicites)

| Séquence | PR proposée | Base et dépendance | Critère d'intégration |
|---|---|---|---|
| 1 | R17.A — Git history, stacked PR audit | master | Diff #248/#264 et #263/#273 audité |
| 2 | R17.B — Character runtime bridge recovery | master après audit | Animation et tenue persistante prouvées |
| 3 | R17.C — Event Pages/Graph true master integration | master après audit | Porte/levier/page/replay Qt fonctionnels |
| 4 | R17.D — Studio–Player E2E cross-workshop | master après B/C | Même contenu de bout en bout |
| 5 | R17.E — Assets/license + native export gate | master après D | Publication refuse droits incomplets |
| 6 | R17.F — Real GPU & release evidence | master après E | Matrice matérielle, goldens revus |
| 7 | R18.A — Studio shell/navigation/layout | master sur gate R17 | Parcours auteur sans navigation perdue |
| 8 | R18.B — Inspector & contextual command UX | après R18.A | Undo/Redo et multi-edit réels |
| 9 | R18.C — Player title/HUD/input | master, dépend R12 | Combat lisible et menu complet |
| 10 | R18.D — Onboarding/a11y + UX certification | après R18.A–C | Test utilisateur |
| 11 | R19.A — Art Bible & production assets | master, dépend R4 | Packs approuvés |
| 12 | R19.B — Jeanne/bestiary animation runtime | après R19.A | Actions N/S/E/O distinctes |
| 13 | R19.C — Terrain/buildings/FX & cutaway | après R19.A | Parité GPU |
| 14 | R19.D — Real GPU performance & visual goldens | après R19.B/C | Profiling tracé |
| 15 | R20.A — Narrative bible & project pack | master, dépend R9/R10 | Graphes de parcours définis |
| 16 | R20.B — Jeanne village/forest/refuge Acte I | après R20.A + R19 art | Première campagne jouable |
| 17 | R20.C — Cutscenes/branches & persistence | après R20.B | Deux chemins valides |
| 18 | R20.D — Playtests + standalone Act I | après R20.C | Joueur termine l'acte |
| 19 | R21.A — CT/formations/reactions/IA coordinated | master, dépend R13 | Replay et lisibilité |
| 20 | R21.B — Castle environment/multifronts | après R21.A et R6 | Fronts et états persistants |
| 21 | R21.C — Boss/branch endings & balance lab | après R21.B | Routes stratégiques testées |
| 22 | R22.A — Project creation + unified authoring | master, dépend R18 | Mini-jeu sans JSON |
| 23 | R22.B — Advanced map/building/character tooling | après R22.A | Assets et cartes exportables |
| 24 | R22.C — Rules/events/campaign/cinematic authoring | après R22.A | Scénario créé et joué |
| 25 | R22.D — Creator acceptance + export | après R22.B/C | Tiers livre mini-jeu |
| 26 | R23.A — Distribution + integrity/hardening | master, dépend R22 | Trois OS propres |
| 27 | R23.B — Endurance, accessibility, user QA | après R23.A | Go/no-go final |
| 28 | R24.A–D — API, resources, plugins, second-game certification | master après stable 5.5 | Pas de fork du moteur |

**Règle de fusion :** PR étroites et autonomes, rebase explicite sur master, aucune mise à jour silencieuse du même chemin depuis plusieurs branches ; l'agrégation de grosses PR ne remplace pas les gates de composants.

## 14. Registre des risques et décisions encore ouvertes

| Risque | Niveau | Action requise |
|---|---|---|
| Fusion intermédiaire non présente dans master | P0 | Inventaire tree/commits + restauration ciblée, pas de badge trompeur |
| Document parallèle R5/R9/R11 | P0 | Revenir à Content/GameProject + AuthoringSession |
| Droits de sprites/aquarelles inconnus | P0 | Preuves juridiques ; bloquer l'export final |
| Tests offscreen assimilés aux GPU réels | P0 | Baseline physique OS/GPU/RHI |
| Exports fonctionnent seulement sur machine de développement | P0 | Tests clean-machine VM/PC séparés |
| UI belle mais commandes inactives | P0 | Chaque contrôle porte une action E2E |
| Direction artistique incohérente | P1 | Bible, sprites réellement indépendants, revue humaine |
| Combat trop complexe/peu lisible | P1 | Intentions, feedback, playtests avant nouvelles règles |
| Croissance des fonctionnalités sans vertical slice | P0 | Chaque lot doit rendre Jeanne ou un mini-jeu plus jouable |
| Migration legacy destructive | P0 | Rollback, anciennes sauvegardes conservées et tests multi-formats |
| Évolution du schéma sans version | P0 | Migrations explicites et tests d'import/export |
| API plugin non fiable | P2 | Retarder à 6.0, capabilities et sécurité explicites |

## 15. Journal d'avancement recommandé

Pour chaque lot : ID, version cible, priorité, dépendances, PR (numéro + branche + base), commit SHA présent sur master, statut code, statut tests headless, Qt onscreen, GPU réel, artistique, build clean-machine, captures/rapports et bloqueurs. Ne jamais confondre « terminé en code », « merged » et « certifié ».

**Critère final DrawTemp 5.5 :** installer le Studio, créer sans JSON un univers comprenant bâtiments intérieurs, classes, personnages animés, événements, campagnes et cinématiques ; lancer en playtest, produire un Player autonome, terminer une campagne, sauvegarder et reprendre sur un PC propre.

**Critère final DrawTemp 6.0 :** refaire cet exercice pour un second jeu entièrement différent, avec templates et extensions compatibles, sans forker le moteur.
