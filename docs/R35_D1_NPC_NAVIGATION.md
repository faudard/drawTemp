# R35.D1 — Navigation déterministe PNJ dans les scènes hors focus

**Statut : implémentation sur la branche de PR #339 ; non fusionnée et non certifiée.** Prolongement R35.3/R35.10, à valider sur SHA final (CI et scènes Qt onscreen).

## Contrat spatial facultatif

Le document canonique reste `GameProject.extensions["org.drawtemp.livingworld"]["data"]`, sans nouveau registre de personnages ni modification au format de replay CT. Pour un PNJ dont tous les horaires ont une position, ajouter `pos: [x, y]` à chaque arrêt existant :

```json
{
  "id": "merchant",
  "schedule": [
    {"minute": 0, "scene": "arrival", "activity": "sleep", "pos": [1, 1]},
    {"minute": 480, "scene": "arrival", "activity": "trade",
     "when": {"flag": "market_open", "eq": true}, "pos": [3, 1]},
    {"minute": 1020, "scene": "arrival", "activity": "home", "pos": [1, 1]}
  ]
}
```

Les positions utilisent la grille **déjà validée** de `GameProject.exploration` (3–32 cellules de largeur/hauteur). Elles sont refusées sur une scène tactique sans géométrie d'exploration. Des arrêts partiellement positionnés, hors limites ou sur un obstacle sont interdits. Les arrêts d'un même lieu ne peuvent nécessiter plus de cellules à parcourir que de minutes disponibles. Les PNJ historiques sans aucune position gardent **la même forme de projection JSON** qu'avant R35.D1.

## Projection temporelle

- Trajet cardinal le plus court calculé par recherche bornée (au plus 1024 cellules explorées par recherche). Priorité de départage des chemins égaux : haut, gauche, droite, bas. Les cellules bloquées ne sont jamais franchies et les diagonales sont interdites.
- **Une case par minute du monde**, départ tardif : pour atteindre un arrêt à 08:00 nécessitant quatre cases, l'acteur reste à son poste jusqu'à 07:56, puis traverse quatre cases à 07:57, 07:58, 07:59 et 08:00. L'activité devient `travel` pendant le déplacement.
- Position consultée via `GameSession.living_world_state(scene=...)` : `pos` et `moving` sont ajoutés uniquement aux PNJ spatialisés. `LivingWorld.npc_pose` utilise directement le projet, les flags existants et l'heure, sans mutation par frame. L'ouverture d'une boutique dépend du marchand réellement au poste et ferme lorsqu'il part.
- Le temps ne progresse que par les appels `living_world_advance` (hors rencontre) et le tick d'exploration libre déjà autorisé. Un saut de N ticks et N appels d'un tick produisent la même position à état/flags identiques. Le monde hors focus est projeté à la demande, sans boucle de simulation cachée.
- Le checkpoint conserve les mêmes champs `living_world` qu'avant R35.D1 : seul le compteur de ticks est requis pour reconstruire la position ; les contenus et chemins sont vérifiés par le `project_digest` existant. Les sauvegardes sans données spatiales ne changent pas.

**Limites explicites :** une transition entre deux scènes distinctes reste un **handoff à l'heure du prochain arrêt**, signalé par `handoff_pending`, et non un chemin géométrique continu. Pour les PNJ **spatialisés**, les conditions `when` activent ou désactivent uniquement l'activité (par exemple, commerce fermé), **jamais la trajectoire** : modifier un flag à 07:59 ne téléporte pas un marchand. Pour les PNJ historiques non spatialisés, les arrêts conditionnels restent filtrés comme avant. Un chemin introuvable est refusé, pas corrigé silencieusement. Aucun mouvement sous-pixel, collision entre PNJ, réservation de cases, navmesh global, météo, rendu interpolé certifié ou budget p95 matériel n'est revendiqué.

## Auteur Qt et vérifications

Depuis **Studio → Outils → Monde vivant**, sélectionner un PNJ puis un horaire et cocher « Coordonnées PNJ (exploration) » ; régler la cellule (X/Y) et prévisualiser. Les modifications passent par le même `AuthoringSession`, avec validation du projet, apply, Undo/Redo. Pour activer la navigation, **tous les arrêts du PNJ** doivent avoir des coordonnées valides.

Tests ajoutés :
```bash
python -m unittest tests_standalone.test_r35_navigation -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r35_navigation_qt -v
```

Le workflow `.github/workflows/r35-living-world.yml` exécute ces cas et les régressions R35.A/B/C. Le gate R35.3 complet nécessite en plus le traitement des passages inter-scènes sans téléportation visible, un banc de 256 PNJ, une vérification Player Qt onscreen (framerate, changements de focus, chargements), et l'absence de dérive sous des combinaisons de flags de quête.
