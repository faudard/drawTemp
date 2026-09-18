# V1.31 — FFT Abilities & Statuses

- Reaction/Support/Movement ability slots.
- Blade Grasp, Auto-Potion, MP Switch.
- Attack/Magic Attack/Defense/Magic Defense Up, Concentrate, Short Charge.
- Move+1/+2, Ignore Height, Teleport, Move-MP Up.
- Protect/Shell/Regen/Silence/Sleep/Stop/Don't Move/Don't Act.
- FFT Faith/MA status success hook.
- Sleep/Stop CT freeze and FFT forced CT costs for Don't Move/Don't Act.

# V1.30 — FFT Core Combat
- Brave/Faith/Zodiac/WP
- Brave-based repeatable reactions
- FFT-style weapon and Faith magic formulas
- Haste/Slow CT-rate and clocktick status durations
- Poison 1/8 MaxHP/AT

# V1.29.0 — FFT Magic / Charging / Evasion

- MP semantics replace the visible Focus economy without breaking serialized content.
- Removed automatic +1 MP/Focus round regeneration.
- Casters continue accumulating unit CT during slow-action charge.
- Move/WAIT keep Charging; choosing another Action cancels it.
- Slow actions pay/check MP at resolution, matching FFT.
- Ordinary damage no longer interrupts Charging; only a new Action or explicit interruption does.
- Charging sets evade to zero and takes x3/2 physical damage.
- Added layered FFT-style front/side/rear physical evasion.
- Basic ATTACK accuracy base changed to 100 before evasion.
- Added `tests/test_fft_magic_charge_v129.gd`.

# V1.27 — Library Art Runtime

- Nouveau `render_mode` dans `SporeUnitVisualDefinition` : `auto`, `procedural`, `sprite_sheet`, `portrait_billboard`.
- `SporeUnitActor3D` peut afficher directement les portraits transparents de la bibliothèque comme billboards 3D de combat.
- Les 10 unités actuelles sont associées à des personnages Sporebound de la bibliothèque.
- 39 skins `lib_*` ajoutés au catalogue Visuals pour rendre toute la bibliothèque sélectionnable depuis Sporebound Studio.
- 12 poses d’attaque runtime 512×512 extraites des action strips ; changement automatique de texture pendant Attack/Cast en mode billboard.
- Visual Editor : choix du mode de rendu et prévisualisation réelle des portraits bibliothèque.
- Catalogue enrichi avec tags de rôle et associations unité -> asset.
- Les 8 icônes de statut restent indexées pour le futur HUD d’états altérés.
- Nouveau smoke test `tests/test_library_assets_v127.gd`.

# V1.22.0 — Weapon & Defense Mechanics

- Profils d’armes mécaniques : mêlée, lance, distance et focus.
- Portée minimale/maximale des attaques de base ; les armes de tir peuvent avoir un angle mort au contact.
- Zone de menace séparée de la portée d’attaque ; les lances peuvent contrôler jusqu’à deux cases.
- Les attaques d’opportunité respectent désormais le profil d’arme et peuvent être désactivées pour les armes de tir.
- Séparation des statistiques `PUI.P`, `PUI.M`, `DEF.P` et `DEF.M`, avec compatibilité de l’ancien champ `attack`.
- Jobs, équipements, progression et statuts peuvent modifier les nouvelles statistiques.
- Les attaques et compétences choisissent la puissance et la défense correspondant à leur type de dégâts.
- Blocage de bouclier data-driven (`chance` + `réduction`) appliqué après les autres mitigations.
- Forecast et IA tiennent compte des nouvelles défenses/portées ; parité 2D/3D conservée.
- Nouveau smoke test `tests/test_weapon_defense_v122.gd`.

# V1.19 — Hero Creator

- Nouvel onglet **Hero Creator** dans Sporebound Studio.
- Personnalisation modulaire du héros : corps, chapeau, visage, haut, bas, accessoire et arme.
- Palettes indépendantes et aperçu 4 directions.
- Génération automatique d’un atlas compatible avec le pipeline directionnel V1.18 et d’un portrait.
- Bibliothèque de pièces extensible par simple ajout de PNG.
- Momo utilise un preset généré prêt à tester.

# V1.18.0 — Directional Sprites & Character Animation

- Runtime `SporeUnitActor3D` connecté aux `UnitVisualDefinition` : spritesheets réellement affichés sur les billboards 3D.
- États d’animation runtime : `idle`, `move`, `attack`, `cast`, `hit`, `ko`.
- Nouveau clip `Cast` dans `UnitVisualDefinition` et dans Sporebound Studio.
- Support `single`, `4_way` et `8_way` selon l’orientation du personnage relativement à la caméra.
- Deux layouts de spritesheet : `rows` (une ligne par direction) et `blocks` (bloc de frames par direction).
- Ordre des directions configurable, stride de bloc configurable, flip horizontal optionnel.
- Changement de frame automatique lorsque la caméra tourne autour du plateau.
- `sprite_scale`, `sprite_offset` et `tint_sprite_with_primary` sont maintenant appliqués au runtime 3D.
- Le fallback procédural distingue face / dos / profil, donc le système directionnel est testable sans asset externe.
- Prévisualisation Visuals enrichie avec sélection de la direction et état `Cast`.
- Les 10 visuels de départ sont configurés en authoring 4 directions, tout en gardant leur fallback procédural actuel.
- Nouveau test `tests/test_directional_animation_v118.gd`.

# V1.17.0 — Advanced Combat VFX

- Nouveau type de VFX data-driven `beam`, disponible dans Sporebound Studio.
- `Lance prismatique` utilise maintenant un vrai faisceau continu 3D au lieu d'un projectile.
- Les projectiles peuvent verrouiller un `Node3D` cible et recalculer leur destination pendant le vol.
- Les compétences AOE déclenchent des impacts successifs sur chaque cellule réellement affectée.
- Les lignes parcourent visuellement les cellules dans l'ordre depuis le lanceur.
- VFX persistants attachés aux unités pour les statuts : Poison, Brûlure, Garde et fallback générique pour les autres statuts.
- Les VFX persistants utilisent `StatusDefinition.vfx_id` et les couleurs des `VfxDefinition`.
- Les ticks périodiques déclenchent aussi le VFX du statut au moment des dégâts/soins.
- Nouveaux réglages `aoe_cell_impacts_enabled`, `aoe_cell_impact_stagger` et `status_tick_vfx_enabled`.
- Nouveau smoke test `tests/test_advanced_vfx_v117.gd`.

# V1.16.0 — Action VFX & Projectile Camera

- Nouveau runtime `SporeActionVfx3D` consommant directement les `VfxDefinition` existantes.
- Rendu 3D procédural des types `projectile`, `burst`, `slash`, `ring`, `cross` et `aura`.
- Projectiles avec trajectoire en arc, noyau lumineux, traînée dissipative et gerbe d'impact.
- Les dégâts sont maintenant synchronisés avec le moment visuel d'impact du VFX.
- Les attaques de base utilisent `UnitVisualDefinition.basic_attack_vfx_id`.
- Les compétences utilisent directement `SkillDefinition.vfx_id`.
- Caméra optionnelle suivant les projectiles à distance avec zoom dédié.
- Réactions (contre/opportunité) déclenchent aussi leur VFX sans bloquer le pipeline de réaction.
- Nouveaux réglages Inspector : `action_vfx_enabled`, `projectile_camera_follow`, `projectile_camera_zoom_in`, `vfx_impact_pause`.
- Nouveau smoke test `tests/test_action_vfx_3d_v116.gd`.

# V1.15.0 — Action Wheel, Cinematic Camera & Impact Feel

- Nouveau menu contextuel **ActionWheel** projeté au-dessus de l’unité active : Move, Attack, Skill I/II, Face et Fin.
- Le menu suit l’unité pendant les rotations/zooms caméra et se masque pendant prévisions, animations et tours ennemis.
- Curseur tactique animé : pulsation, léger flottement et couleur liée au mode déplacement/attaque/skill.
- Caméra d’action automatique : cadrage entre attaquant et cible, zoom temporaire puis retour fluide au suivi normal.
- Punch caméra à l’impact avec micro-zoom et shake configurable.
- Présentation des unités enrichie : respiration idle, pulsation de sélection/tour actif, squash/lunge d’attaque, cast avec élévation.
- Attaques et skills joueur/IA partagent le même pipeline de caméra d’action.
- Paramètres `action_camera_enabled`, `action_camera_duration`, `action_camera_zoom_in`, `impact_shake_strength` et `show_action_wheel` éditables dans l’Inspector.
- Nouveau smoke test `tests/test_action_wheel_camera_v115.gd`.

# V1.14.0 — Tactical Presentation & Camera Polish

- Barres HP et Focus billboard visibles au-dessus de toutes les unités 3D.
- Couleur de HP dynamique : vert, orange puis rouge selon l'état de santé.
- Timeline d'initiative compacte affichant l'unité active et les prochaines activations.
- Fiche d'unité contextuelle au survol : portrait, HP/Focus, ATK/MOV/RNG/INIT, orientation, réaction, skills et statuts.
- Caméra isométrique interpolée : rotation et zoom ne sautent plus instantanément.
- Suivi fluide configurable de l'unité active pendant déplacements et sauts.
- Raccourci `C` pour recentrer immédiatement la caméra sur l'unité active.
- Cache de timeline et de portrait pour éviter les reconstructions UI inutiles au survol.
- Nouveau smoke test `tests/test_presentation_v114.gd`.

# V1.13.0 — Combat Forecast & Confirmation

- Ajout d’un vrai panneau de prévision avant attaque ou compétence dans le prototype 3D.
- Premier clic : prépare l’action sans consommer déplacement/action/Focus ; Entrée ou bouton CONFIRMER exécute.
- Échap / ANNULER ferme la prévision sans coût et conserve le mode de ciblage.
- Attaque normale : dégâts, HP avant/après, K.O., face/flanc/dos, hauteur, couvert, interception et contre potentielle.
- Compétences : coût Focus, cooldown, point ciblé, taille de zone et prévision par unité touchée (dégâts, soins, statuts, garde, réaction, Focus, push/pull).
- Les zones persistantes sont décrites avec type de tick, phase et durée.
- La case confirmée est surlignée en or et la prévisualisation AOE reste figée jusqu’à confirmation/annulation.
- Nouveau test structurel `tests/test_combat_forecast_v113.gd`.

# V1.12.0 — Reactions, Skill AI & Persistent Zones

- Réactions configurables dans `UnitDefinition` : `none`, `counter`, `opportunity`, `intercept`.
- Portée et bonus de dégâts de réaction éditables dans Sporebound Studio.
- Une réaction normale par round ; l'effet Skill `reaction` arme une réaction supplémentaire.
- Contre-attaque après une attaque/compétence dommageable lorsque l'assaillant est à portée.
- Attaque d'opportunité déclenchée lorsqu'une unité quitte réellement une zone de menace pendant son chemin.
- Interception d'une attaque mono-cible par un allié adjacent configuré pour protéger, avec réduction de dégâts dédiée.
- Le trajet s'interrompt proprement si une réaction met le déplacement K.O.
- IA 3D : comparaison chiffrée entre attaque normale et compétences (dégâts/K.O., soin utile, statuts, garde, réaction, Focus et AOE).
- Les ennemis de la mission 1 utilisent désormais leurs compétences et leurs réactions.
- Nouveau bloc SkillEffect `zone` avec tick `damage/heal/status`, phase début/fin d'activation et durée en rounds.
- Zones persistantes visibles sur le plateau, avec compteur de rounds et ticks appliqués aux unités présentes.
- Nouveau skill de démonstration `Flaque corrosive` attribué à Baveux.
- Studio Skills enrichi pour éditer les paramètres de zone persistante.
- Smoke test `tests/test_reactions_zones_ai_v112.gd`.

# V1.11.0 — 3D Skills, AOE & Status Runtime

- Compétences I / II jouables directement sur le plateau 3D avec raccourcis `1` / `2`.
- Focus, régénération, coûts et cooldowns par unité.
- Ciblage 3D data-driven depuis `SkillDefinition` : self, ally, enemy, unit et ground.
- Formes de zone `single`, `cross`, `diamond`, `line` et `circle`, également ajoutées à Sporebound Studio.
- Prévisualisation : violet = ancre ciblable, cyan = zone, rouge/vert = unité ennemie/alliée affectée.
- Tolérance de hauteur séparée pour l’ancre et la zone d’effet.
- Exécution des blocs `damage`, `heal`, `status`, `guard`, `focus`, `reaction`, `push` et `pull`.
- Statuts actifs dans le prototype 3D : durées, modificateurs, ticks début/fin d’activation, expiration et consommation sur impact/attaque.
- Les dégâts de skill respectent hauteur, statuts et couvert directionnel ; tag `ignore_cover` pris en charge.
- Nouveau skill `Lance prismatique` (ligne) attribué à Luma en secondaire.
- Nouveau skill `Orbite sporale` (cercle) attribué à Ziggy en secondaire.
- Compatibilité du BattleController 2D étendue aux formes `line` et `circle`.
- Smoke test `tests/test_skills_3d_v111.gd`.

# V1.10.0 — Facing, Jump & Directional Cover

- Orientation cardinale persistante pour chaque unité, matérialisée par un indicateur au sol.
- Le déplacement oriente automatiquement l’unité vers sa dernière case ; l’attaque l’oriente vers sa cible.
- **F** pivote le héros de 90° et **Shift+F** dans le sens inverse avant de terminer son activation.
- Attaques de face / flanc / dos avec bonus configurables (`side_attack_bonus`, `back_attack_bonus`).
- Prévision de dégâts au survol incluant hauteur, flanc/dos et réduction de couvert.
- Sauts entre niveaux : limites distinctes montée/descente (`max_jump_up`, `max_jump_down`) et animation en arc.
- Les transitions de hauteur sont affichées en bleu dans le chemin prévisualisé.
- Les cases `cover` exposent désormais `cover_facing` (north/east/south/west) dans l’Inspector.
- Le muret 3D se place du côté protégé et la réduction à distance ne s’applique que si le tir arrive de ce côté.
- `SporeMap3D.to_environment()` exporte maintenant `cover_directions`.
- L’IA préfère à portée équivalente une position de dos/flanc, puis la hauteur.
- Nouveau smoke test `tests/test_facing_jump_cover_v110.gd`.

# V1.9.9 — Tactical Paths, LOS & Cover

- Prévisualisation du chemin en jaune au survol d'une case atteignable.
- Déplacements héros et ennemis animés case par case à partir du même pathfinding tactique.
- Ligne de vue sur grille : les obstacles intermédiaires et reliefs suffisamment hauts bloquent désormais les attaques.
- Portée d'attaque calculée uniquement sur les cellules réellement visibles.
- Les cases `cover` réduisent de 1 les dégâts à distance (valeur exportée et réglable).
- Les cases de couvert apparaissent en orange dans la portée d'attaque.
- UI enrichie : hauteur, couvert et indication `vue bloquée` au survol.
- Nouveau smoke test `tests/test_tactical_combat_3d_v199.gd` pour le tracé de ligne/path/LOS.

# V1.9.8 — Tactical Combat 3D

- Le prototype 3D devient un mini-combat tactique jouable : initiative, activations, déplacement et attaque.
- Une activation autorise 1 déplacement + 1 attaque dans l’ordre choisi, proche du rythme Final Fantasy Tactics.
- Portée de déplacement en vert et portée d’attaque en rouge directement sur les cases 3D.
- Gestion des PV, dégâts, K.O., victoire/défaite et journal de combat.
- Bonus de +1 dégât lorsqu’un attaquant frappe depuis une case plus haute.
- IA ennemie simple : cible le héros le plus proche, avance avec les contraintes de relief puis attaque si elle est à portée.
- Les statistiques runtime viennent des `UnitDefinition` et des overrides de mission existants.
- Picking souris amélioré par projection écran des centres de cases, y compris sur les reliefs.
- Feedback visuel : lunge d’attaque, flash d’impact, dégâts flottants, animation K.O.
- Inspector de `SporeMap3D` : nouveau bouton **▶ Combat 3D** pour sauvegarder puis lancer directement le prototype.
- Nouveau smoke test `tests/test_battle_board_3d.gd` couvrant map, acteurs, caméra, timeline et première activation.

# V1.9.7 — 3D Battle Board Prototype

- Ajout d'une scène jouable `scenes/mission_1_battle_3d.tscn` pour prévisualiser une vraie bataille sur la nouvelle map 3D.
- Ajout de `SporeBattleBoard3D` : caméra isométrique, survol de case, sélection des héros, déplacement par clic et rotation/zoom caméra.
- Ajout de `SporeUnitActor3D` : personnages 2D billboard procéduraux posés sur le plateau 3D, avec ombre, anneau de sélection et info-bulle.
- Les cases atteignables sont maintenant visibles directement sur le plateau 3D.
- La battle 3D relit les données réelles de mission 1 (`SporeMap3D`, spawns, unités catalogue) au lieu d'une scène jetable.
- Nouveau smoke test `tests/test_battle_board_3d.gd`.

# V1.9.6 — First Tactical 2.5D Map

- Mission 1 migrée vers une scène `SporeMap3D` réellement éditable dans le workspace 3D.
- 80 `SporeTacticalTile3D` explicites : coordonnée, hauteur et type de terrain éditables dans l'Inspector.
- Relief visuel, obstacles, couvertures, spores, extraction, bonus et couronne visibles en 3D.
- Spawns héros/ennemis et interactables 3D alignés automatiquement sur le sommet des cases.
- Contrat runtime identique à `SporeMap2D`, donc compatibilité avec le BattleController existant.
- Inspector Sporebound étendu aux maps/tiles/spawns/objets 3D.
- Caméra orthographique + lumière pour prévisualisation F6.
- Ancienne mission 1 2D conservée dans `mission_1_map_2d_legacy.tscn`.
- Smoke tests natifs mis à jour pour accepter les maps 2D et 3D.

# V1.9.5 — Native Level Design Production

- Ajout de `SporeMapZone2D` : zones polygonales visibles/éditables dans la viewport Godot.
- Zones exportées vers le runtime sous forme de cellules couvertes.
- Nouveaux triggers `player_enters_zone` / `enemy_enters_zone`.
- Exemple `center_stage` dans la mission 2.
- Menu `+ Objet` dans la toolbar native pour créer rapidement spawns, interactables et zones.
- `▶ Ici` / `▶ Tester direct` : sauvegarde de scène + lancement automatique de la mission courante.
- Le playtest éditeur ne persiste pas les changements de campagne.
- Templates de nouvelles missions : vide, escarmouche 8×8, objectif 10×8, grande 12×10.
- Validation/Inspector enrichis avec les zones.
- Ajout de `tests/test_native_level_design_v195.gd`.

# V1.9.4 — Native Level Design UX

- Inspector Godot enrichi pour maps, spawns et interactables.
- Aperçu tactique directement dans la viewport 2D : mouvement + enveloppe d’attaque.
- Overlay de validation rouge/jaune avec erreurs localisées sur les cases.
- Validation renforcée des spawns, Unit Id, ordres héros, Object Id, liaisons et couches TileMap.
- Liaison interrupteur → porte visible dans la viewport.
- Actions contextuelles : cadrer, snap, ouvrir la fiche unité, suivre une liaison.
- Nouveau smoke test `test_native_level_design.gd`.

# V1.9.3 — Native TileMap Editor

- Terrain migré vers de vrais `TileMapLayer` Godot : Ground / Height / Terrain / Objectives.
- TileSet visuel fourni dans `assets/editor/`.
- Ouverture de map : bascule automatique en 2D, cadrage automatique et sélection de Ground.
- Les spawns/objets sont maintenant des `Polygon2D` visuels et sélectionnables.
- Le runtime lit directement les couches TileMap ; les tableaux V1.9.2 ne servent plus que de migration/fallback.
- La barre Spore Map fournit des raccourcis vers chaque couche native ; la palette TileMap Godot est le workflow principal.

# V1.9.2.4 — Progression strict typing hotfix

- `SporeJobDefinition.progression_node_by_id()` retourne maintenant `SporeProgressionNodeDefinition` au lieu de `Resource`.
- `SporeJobCatalog.definition()` retourne `SporeJobDefinition`.
- Typage explicite de `node`, `required`, `other`, budgets et collections de nœuds.
- Typage propagé au canvas d’arbre, à l’éditeur Studio et au BattleController.
- Remplacement des `max/clamp` génériques par `maxi/maxf/clampi` dans la progression.
- Inclut les hotfixes précédents V1.9.2.1/V1.9.2.2 (plugin path, JSON Variant, Bresenham strict).

# V1.9.2.2 — Strict typing hotfix

- Fixed Bresenham/line-of-sight integer inference under `warnings as errors`.
- Replaced generic `abs()` inference with typed `absi()` in the line-cell helpers.
- Explicitly typed `x0/y0/x1/y1/dx/sx/dy/sy/error/twice_error` as `int`.
- Applied the same safe fix to historical gameplay scripts containing the same helper.

# V1.9.2.1 — Strict GDScript hotfix

- Corrige `SporeSaveManager.load_campaign()` : `JSON.parse_string()` est maintenant stocké dans un `Variant` explicite au lieu d'utiliser `:=`.
- Corrige la même occurrence dans le script historique V0.9.
- Vérification ciblée des API retournant `Variant` dans les scripts actifs et le plugin Studio.
- Conserve l’édition native des maps Godot introduite en V1.9.2.

# V1.9.2 — Native Godot Map Editing

- Maps migrées vers de vraies scènes `.tscn` éditables dans le workspace 2D de Godot.
- `SporeMap2D` `@tool` dessine la grille et les couches tactiques directement dans l'éditeur.
- Spawns héros/ennemis et interactables deviennent des `Node2D` sélectionnables dans le Scene Tree et éditables dans l'Inspector.
- Toolbar **Spore Map 2D** native : mode peinture, terrain, hauteurs, spawns, porte/interrupteur/coffre, gomme, snap et validation.
- Toutes les opérations du pinceau utilisent `EditorUndoRedoManager`.
- `MissionDefinition.map_scene_path` relie la mission à sa scène de map.
- `MissionCatalog` lit en priorité la scène native, avec fallback sur les données legacy.
- Création/duplication de mission crée/duplique aussi sa scène de map.
- **Ouvrir dans Godot** bascule vers le workspace 2D/3D en fonction du type de scène.
- **Tester** sauvegarde les scènes ouvertes avant le lancement.
- Trois scènes natives fournies pour les trois missions historiques.
- Ajout de `tests/test_native_maps.gd`.

# V1.9.1 — Godot strict-warning hotfix

- Fixed Sporebound Studio plugin path in `plugin.cfg` (`script="plugin.gd"`).
- Fixed Variant type-inference warnings treated as errors in `battle_controller.gd`.
- Replaced ambiguous generic `max/min/clamp` inference with typed helpers where needed.
- Added explicit local types for Dictionary/Resource-derived values used by battle/UI/FX code.
- Applied the same strict-typing cleanup to Studio previews/catalog helpers.

# Changelog

## V1.9 — Visual Progression Trees

- Ajout de `ProgressionNodeDefinition`.
- Ajout d'un canvas d'arbre visuel partagé entre Studio et l'UI runtime.
- Nouveau sous-onglet **Progression > Skill Tree**.
- Création/duplication/suppression et déplacement visuel des nœuds.
- Types Skill / Stat / Passive.
- Coûts en points, niveau requis, prérequis et groupes exclusifs.
- Validation des IDs, références et cycles.
- 48 nœuds fournis sur les 8 jobs de départ.
- Bouton ARBRE dans la Serre tactique et achat persistant des nœuds.
- Respec gratuit du job courant.
- Effets runtime : stats, résistance, skill power, guard-after-skill et Focus regen.
- `skill_power_bonuses` et `guard_after_skill_ids` permettent plusieurs passifs simultanés.
- Sauvegarde V5 avec `hero_job_nodes`, migration transparente depuis V1.8.
- `skill_unlocks` conservé comme fallback pour les jobs sans arbre.
- Nouveau `tests/test_progression_tree.gd`.

## V1.8 — Jobs, Progression & Equipment

- Ajout de `JobDefinition`, `JobSkillUnlock`, `ResistanceEntry` et `EquipmentDefinition`.
- 8 jobs de départ avec spécialisations et déblocages niveau 3.
- XP de maîtrise par héros/job et déblocage de compétences par niveau.
- Nouvel onglet Studio `Progression` avec éditeurs Jobs/Equipment.
- Unit Editor : job par défaut, niveau initial, jobs disponibles.
- 3 slots runtime : weapon / armor / accessory.
- Migration des 9 reliques historiques vers des Equipment Resources.
- Types de dégâts sur SkillEffect et ticks de statuts.
- Résistances appliquées aux attaques, skills, Poison, Brûlure et spores terrain.
- Save schema V4 avec migration V1.7.
- Ajout de `tests/test_progression.gd`.

## V1.7 — Asset & Visual Editor

- Nouveau `UnitVisualDefinition.tres` séparant l'apparence des statistiques d'unité.
- Nouveau `VisualCatalog` et liaison `UnitDefinition.visual_id`.
- Nouvel onglet **Visuals** dans Sporebound Studio.
- Portrait, spritesheet, taille de frame, échelle, offset et palette éditables.
- Clips data-driven `Idle`, `Move`, `Attack`, `Hit`, `KO` avec preview live.
- Fallback procédural par unité/skin pour permettre une migration graphique progressive.
- Nouveau `VfxDefinition.tres`, `VfxCatalog` et onglet **VFX**.
- Types de VFX : burst, projectile, aura, ring, cross et slash.
- Texture/spritesheet de VFX optionnelle avec animation de frames.
- `SkillDefinition.vfx_id`, `StatusDefinition.vfx_id` et VFX d'attaque de base par skin.
- VFX branchés sur attaques, compétences composées et application de statuts.
- Aura visuelle persistante pour les statuts de type aura/ring.
- Courte animation `KO` avant disparition d'une unité.
- Portrait automatique des dialogues depuis l'apparence d'une unité quand aucun portrait explicite n'est imposé.
- Dossiers `assets/portraits`, `assets/sprites` et `assets/vfx` ajoutés.
- 10 apparences de départ et bibliothèque VFX initiale sans dépendance graphique externe.
- Nouveau smoke test `tests/test_visual_assets.gd`.

## V1.6 — Dialogue & Cinematic Timeline

- Nouveau `CinematicDefinition.tres` réutilisable et `CinematicCatalog`.
- Nouvel onglet **Cinematics** dans Sporebound Studio.
- Timelines Intro / Victoire / Défaite par mission.
- Action `play_cinematic` disponible dans Mission Logic.
- Dialogues bloquants avec locuteur, portrait gauche/droite, avance manuelle ou automatique.
- Caméra : focus case/unité, zoom, reset et shake.
- Fondus écran data-driven.
- Lecteurs musique et SFX pilotables par timeline.
- Exécuteur commun async `_run_action_sequence()` pour événements et cinématiques.
- Mapping souris compatible avec le panoramique/zoom du plateau.
- Huit timelines de démonstration, dont les phases II/III de l'Archiviste appelées en combat.
- Nouveau `tests/test_cinematics.gd` et extension des smoke tests existants.

## V1.5 — Combat Event Sequencer

### Studio

- Trigger `condition -> actions[]` au lieu d'une action unique.
- Ajout/suppression/duplication/réordonnancement des actions.
- Délai configurable avant chaque action et action `wait`.
- Éditeur de règles dynamiques victoire/défaite.
- Éditeur d'objets Door / Switch / Chest.
- Pinceaux Porte / Interrupteur / Coffre dans l'éditeur Maps.
- Affichage des objets directement sur le canvas de map.
- Validation des liens trigger -> unité/statut/objet.

### Runtime

- File d'événements ordonnée avec délais.
- Texte d'objectif et phase modifiables en combat.
- Conditions de victoire/défaite remplaçables en combat sans muter les Resources.
- Portes bloquant déplacement + ligne de vue.
- Interrupteurs liés aux portes.
- Coffres donnant soin ou Focus.
- Compatibilité des triggers V1.4 conservée.

### Contenu de démonstration

- Mission 1 : porte, interrupteur et coffre à spores.
- Mission 1 : événement de manche 2 en trois étapes.
- Mission 2 : renfort Baveux converti en séquence message -> délai -> spawn.
- Mission 3 : phases II/III de l'Archiviste exprimées en séquences V1.5.
