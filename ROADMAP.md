# Roadmap — priorité gameplay, sans dépendance à Godot

## Research gate — Combat Fundamentals 1.0

La profondeur tactique n'est plus développée comme une liste ouverte de features. Les décisions de gameplay doivent d'abord être confrontées au cadre de recherche et au journal de décisions :

- [Combat Design 1.0](docs/design/COMBAT_DESIGN.md)
- [Comparative Analysis](docs/research/COMPARATIVE_ANALYSIS.md)
- [Research Bibliography](docs/research/BIBLIOGRAPHY.md)
- [Decision Log](docs/research/DECISION_LOG.md)

Ordre de recherche : combat fundamentals → jobs/builds/progression → encounter design → tactical AI → campagne/meta → authoring UX → balance/telemetry → renderer/player UX.

## 2.0 alpha — socle implémenté

- [x] Moteur headless, contenu JSON validé, commandes atomiques et événements.
- [x] CT, déplacement/relief/LOS, dégâts, orientations, compétences, statuts, casts, réactions.
- [x] IA jouant avec les mêmes règles, prévisions, tests, simulations multi-seeds.
- [x] Objectifs, couronne, objets interactifs et triggers simples.
- [x] Progression, jobs, boutique/équipement, campagne et replays.
- [x] Notre éditeur de carte avec playtest, JSON, undo/redo et journal.

## 2.0b — Game Studio (PR #14)

- [x] Opérations d'authoring data-driven et validées : unités, objets interactifs,
  triggers simples, taille de carte, propriétés et chaînage des missions.
- [x] Assistant carte vierge + duplication de mission, avec playtest et undo/redo.
- [x] Onglets Tk dédiés aux personnages, événements et configuration globale.
- [x] Manifeste distinct `GameProject` : titre, sous-titre, campagnes,
  langue, options audio, plein écran, nombre de slots.
- [x] Aperçu de la page de garde : nouvelle partie, continuer, charger et options.
- [x] Sauvegardes de progression par campagne/slot via `Campaign.save` ;
  progression de mission acquise avec `Campaign.finish`.
- [x] Exemple de projet embarqué, tests headless et smoke Tk/Xvfb.
- [ ] **Studio 2.1** : éditeur de tilesets / brosses / pinceaux rectangles,
  groupes, rotation, copier-coller, sélection multiple et palettes d'acteurs.
- [x] **Studio 2.2 foundation** : bibliothèque réutilisable d'acteurs,
  formulaires d'archétypes, conditions et actions d'événements ordonnées.
- [ ] **Studio 2.2 closure** : éditeurs de compétences/inventaire,
  vagues de renforts, dialogue et cinématiques.
- [x] **Studio 2.3 foundation** : graphe visuel des `next_missions`,
  ajout/retrait de liens, détection de cycles et missions isolées.
- [x] **Studio 2.3 narrative tree** : arbre de choix dépliable, scènes
  partagées visibles sur plusieurs branches, création/liaison atomique,
  conditions et conséquences inspectables, limites d'affichage.
- [x] **Studio 2.3 conditional foundation** : dialogues conditionnels,
  choix exclusifs de missions, drapeaux persistants, écran de narration,
  sauvegardes compatibles avec Campaign.
- [ ] **Studio 2.3 closure** : checkpoints, transitions, édition avancée des
  conditions imbriquées, visualisation des impasses et diagnostic des flags.
- [x] **Player Shell 0.1** : menu joueur autonome, choix campagne/slot,
  missions débloquées et combats Tk utilisant `Battle`, avec sauvegardes.
- [ ] **Player Shell 1.0 closure** : carte de campagne illustrée,
  déploiement ergonomique, menus d'équipement et rendu/audio dédiés.
- [ ] **Persistence 2.0** : identité projet/version de contenu dans les slots,
  détection de slots incompatibles, migration et autosave.

Les options de présentation restent de la configuration, pas un renderer/audio.
Les sauvegardes multi-fronts ne sont pas encore intégrées au manifeste général.
Voir [docs/STUDIO.md](docs/STUDIO.md).

## 2.1 — profondeur tactique

- [x] Combat 1.1 framework : engagement, zones de contrôle, Guard/Vigilance/Brace/Intercept, Disengage, portée LOS/falloff, threat forecast.
- [x] Combat 1.2 melee pressure : Charge rectiligne avec coût CT et push, Pursuit bornée, contre Brace/Disengage et preview de menace.
- [x] Team Tactics foundation : Pincer + Crossfire, coût CT partenaire, forecast pur et prise en compte IA.
- [x] Tactical Bonds foundation : stats par paire, kills ciblés, Intercepts, missions, séquences secrètes, tactiques connues/préparées et sauvegarde.
- [ ] Tactical Bonds 2 : trios + stats/sauvegarde, séquences répétables et codex progressif implémentés ; reste l’UI de préparation dédiée.
- [ ] Team Tactics 2 : Encirclement trio + Pursuit + Charge + Relay implémentés ; restent Launch/throw, terrain combos et temporal combos.
- [ ] Formations : Shield Wall, Phalanx, Escort Diamond, contrôle de couloirs et preview dédiée.
- [ ] Déploiement avant combat, limites d’équipe et formations sauvegardées.
- [ ] Menaces et réserves de réaction visibles ; Intercept et protection d’alliés.
- [ ] Compatibilités zodiacales, immunités de statut, dissipation et règles de stacking dédiées.
- [ ] Arbres de classes complets : JP à dépenser, apprentissage, supports/mouvements équipables.
- [ ] Armes à portée/trajectoire/élément, équipements à conditions, butins de mission.
- [ ] IA coordonnée : protection du soigneur/porteur, priorités d’objectifs, ouverture des portes,
      profils agressif/support/défensif, explication des décisions et budgets de calcul.
- [ ] Renforts, escortes, capture multi-zones, objectifs secondaires, difficultés et règles de défaite.
- [ ] Tests d’équilibrage et longues campagnes reproductibles avant de figer les valeurs.

## 2.1b — Assaut multi-fronts et boss (PR #14)

- [x] Horloge stratégique partagée, changement de zone et résolution automatique des fronts non focalisés.
- [x] Application déterministe des pertes stratégiques aux unités, y compris lors de la première ouverture d'un front.
- [x] Journal de commandes multi-fronts, replay vérifié, sauvegarde/restauration par reconstruction.
- [x] Salle du trône : deux postes défensifs sabotables et renforts déclenchés à 50 % des PV du châtelain.
- [x] Liens événementiels déclaratifs entre fronts : herse → porte/cour, sabotage → défense neutralisée, réserves coupées → vagues bloquées.
- [x] Validation des références, effets différés sur fronts non ouverts, application atomique et replay multi-fronts v2 (compatibilité v1).
- [x] Logistique v1 : routes orientées, réserves finies, capacité de transport, ordres à délai en tours stratégiques.
- [x] Transfert de véritables unités entre fronts avec PV/MP/statuts conservés, garnissons minimales, arrivées et retraites.
- [x] Défaite du front de la porte → attrition alliée de la cour ; replay stratégique v3 + lecture des formats v1/v2.
- [x] Tests d'ordres invalides, de duplication, de perte de convoy et de replay déterministe (validation CI en attente).
- [x] Économie optionnelle de provisions, interception de convois, pertes, escorte limitée et secours en cas d'embuscade.
- [x] Tableau de commandement terminal des fronts, chronologie globale, ressources, convois, ETA et opérations.
- [x] Sauvegarde JSON atomique + restauration vérifiée depuis le commandement ; replay inter-fronts v4 rétrocompatible.
- [x] Première fenêtre Tk de commandement : tableau des fronts, état des convois, commandes, sauvegardes et journal global (test Xvfb).
- [ ] Commandement visuel avancé : carte des fronts, timeline cliquable, drag/drop, placement graphique, prévision d'ordres et finition UX.
- [x] Mission tactique de secours du convoi : chariot protégé, élimination des pillards, victoire/défaite réelle, abandon explicite.
- [x] Secours à embranchements optionnel : sauver l'équipage sans cargaison, négocier pendant le combat, récupérer un butin partiel après une élimination.
- [x] Poursuite jouable des pillards, récupération de ressources limitée et réduction bornée de l'opposition du front cible.
- [x] Contrats et tests de replay v4 (anciens scénarios inchangés) pour les choix, inventaires et combats annexes.
- [x] Campagne multi-fronts v5 optionnelle : verrou du trône, conditions de victoire acceptées et confirmation par véritable combat final.
- [x] Négociation du passage, retraite avec pertes inter-fronts, victoire partielle liée à une interaction tactique réelle ; validations et replay.
- [x] Commandement Tk / terminal : état d'avancement campagne, décisions et interdiction du passage au trône jusqu'au déverrouillage.
- [x] Routes alternatives optionnelles : brèche classique, souterrains tactiques, assaut direct coûteux (déduction immédiate de provisions et de forces).
- [x] Contre-attaque jouable pour reconquérir la porte après retrait/défaite, avec coûts, état `reclaimed`, journal et reprise.
- [x] Trêve conditionnelle : preuve d'interaction dans une mission de ravitaillement avant négociation.
- [x] Démonstration de trois fins de siège, tests d'ownership des décisions et replays v5 stables.
- [x] Représailles ennemies temporisées : un secteur sécurisé peut être rouvert, avec pression stratégique, puis doit être repris par une vraie bataille tactique et rejouable.
- [x] Patrouilles d'infiltration déterministes par waypoints : les gardes reprennent l'IA tactique à vue et les routes sont validées sur la carte.
- [ ] Routes adaptatives complexes et diplomatie à plusieurs étapes.
- [x] Journaux/replays des combats de sauvetage en cours et de leurs conclusions, sans duplications des voyageurs ; tests de compatibilité.
- [ ] Défense prolongée des lignes de ravitaillement, choix négociation/fuite, plusieurs variantes de carte et chargements.

- [ ] Sélecteur visuel des zones d'arrivée et de l'ordre de mission pour chaque convoy.
- [x] Conséquences stratégiques des objectifs tactiques (porte, remparts, ravitaillement et défaite locale).
- [ ] Tests longue campagne, simulations d'équilibrage et UX de la timeline globale.

Voir [contrats multi-fronts](docs/MULTI_FRONT.md).

## 2.2 — contenu et migration vérifiée

- [ ] Inventaire exhaustif des anciens effets, passifs, missions et ressources réellement utilisés.
- [ ] Convertisseur explicite `.tres/.tscn` vers JSON avec rapport des champs non portés.
- [ ] Reprise fidèle des trois missions historiques, dialogues et branches de campagne.
- [ ] Scénarios comparatifs avec les tests Godot existants ; expliquer chaque divergence voulue.
- [ ] Sauvegardes à checkpoints, migrations de versions et tests de campagnes longues.

## 2.3 — notre éditeur complet

- [ ] Formulaires de stats/classes/équipement et composition visuelle des effets.
- [ ] Zones peintes, inspecteurs d’objectifs et graphe de triggers avec validation des références.
- [ ] Palette d’unités, création/suppression, multi-sélection et copie/collage.
- [ ] Timeline CT prévisionnelle, outils de menace/LOS et arrêt sur événement.
- [ ] Gestion de campagne/roster dans l’interface, lancement de batteries d’équilibrage.
- [ ] Sauvegarde automatique, projets multi-fichiers, distribution Windows/Linux/macOS.

## Plus tard — présentation

- [ ] Choisir un renderer après stabilisation des règles et des contrats d’événements.
- [ ] Sprites/animations, sons, caméra, cinématiques et interface joueur travaillée.
- [ ] Ne jamais déplacer les règles métier dans le renderer ou l’éditeur.

Les éléments cochés sont implémentés ; ils ne constituent pas une certification de
parité Godot, de gameplay final ou de finition produit.

## Architecture modulaire — continuation PR #14

Livré : douze registres composables, incluant statuts, déplacements, réactions
passives/préparées, synergies et conditions/actions de triggers. Validation, IA et
prévisions partagent ces définitions. Les archétypes personnages/monstres/invocations,
le rollback des extensions et les replays v3 avec lecture v1/v2 sont intégrés.
La campagne accepte les synergies enregistrées via `ruleset`.
Exemples et contrats : [moteur modulaire](docs/MODULAR_ENGINE.md).

Prochaines étapes :
- Ajouter spawn/despawn transactionnels, renforts et durée de vie des invocations.
- Éditeur d'archétypes avec distinction explicite défauts/surcharges et resynchronisation.
- Profils IA spécialisés (soigneur, meute, boss) avec tests de décisions déterministes.
