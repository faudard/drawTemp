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

## 2.1 — profondeur tactique

- [x] Combat 1.1 framework : engagement, zones de contrôle, Guard/Vigilance/Brace/Intercept, Disengage, portée LOS/falloff, threat forecast.
- [x] Combat 1.2 melee pressure : Charge rectiligne avec coût CT et push, Pursuit bornée, contre Brace/Disengage et preview de menace.
- [x] Team Tactics foundation : Pincer + Crossfire, coût CT partenaire, forecast pur et prise en compte IA.
- [x] Tactical Bonds foundation : stats par paire, kills ciblés, Intercepts, missions, séquences secrètes, tactiques connues/préparées et sauvegarde.
- [ ] Tactical Bonds 2 : trios, indices progressifs/codex, règles de séquence plus riches et UI de préparation.
- [ ] Team Tactics 2 : Launch/Relay, Pursuit, Charge, terrain combos et temporal combos.
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
