# R44.A — WorldGraph 2.0 / Contrat headless

**Statut : implémentation du seul sous-lot R44.A, pas certification R44 / 8.4.**

## Autorité des données

- Définition optionnelle : `GameProject.extensions["drawtemp.worldgraph"] = {"schema_version": 1, "data": {...}}`. Les projets existants n'ont aucune migration implicite.
- `GameProject.scene_routes` (R25) reste **la seule topologie de transitions exécutable** : un portail R44 référence un identifiant de route existant. `SceneRouter.destination` valide les conditions ; `GameSession.route_transition` déplace effectivement le joueur. Les coûts R44 servent aux diagnostics de trajet ; ils ne débitent pas d'horloge sans API métier ultérieure validée.
- L'atlas de R44 découpe les scènes exploratoires/tactiques connues en régions nommées, avec un biome et une projection (`top_down` ou `isometric`). Les coordonnées `origin` sont propres à chaque scène; transformation/picking est entière et réversible sur les cellules, sans renderer supplémentaire.
- `objects` déclare des objets de type `chest`, `door`, `npc`, `switch` avec un flag `world44_...`. La valeur est lue depuis `Campaign.story_flags`, déjà persistée et signée dans les sauvegardes `GameSession`. Aucun second registre d'état, aucune écriture cachée ni deuxième moteur de quêtes.
- Les références `palette` renvoient exclusivement à des sprites du `AssetRegistry` canonique. Le validateur d'assets de publication conserve la responsabilité des fichiers et licences réels ; R44.A ne prétend pas les certifier.

## Contrat minimal v1

```json
{
  "version": 1,
  "regions": [
    {
      "id": "village", "title": "Vallée", "biome": "forest",
      "projection": "top_down", "palette": [],
      "scenes": [{"id": "arrival", "origin": [0, 0]}]
    }
  ],
  "portals": [],
  "objects": [
    {"id": "chest_a", "scene": "arrival",
     "kind": "chest", "flag": "world44_chest_a_open"}
  ]
}
```

Les scènes et routes doivent exister dans les manifestes canoniques. Toutes les scènes déclarées doivent être structurellement accessibles depuis `scene_routes.start` par les portails R44. Les cycles avec retour sont autorisés ; les îlots inaccessibles, liens manquants, IDs redondants, portails dans des cases bloquées, versions futures et valeurs booléennes présentées comme des entiers sont rejetés. L'accessibilité **dynamique** dépend des conditions R25; `WorldGraph.shortest_path` renvoie `None` si le chemin est fermé et respecte le coût total et un ordre stable des liens.

**Bornes :** 64 régions, 256 scènes, 512 portails, 512 objets, et 64 Kio au maximum par extension R24. Aucun streaming, aucune transition implicite et aucun effet métier de coût.

## Contrôles

```bash
python -m unittest tests_standalone.test_r44_world_graph
python -m unittest tests_standalone.test_r25_scene_router
```

Les tests vérifient schema/roundtrip, changement de version rejeté, liens/biomes/palettes, conditions, chemin le moins coûteux, conversion des coordonnées, idempotence en lecture, sauvegarde/recharge des flags par `GameSession` et non-régression manifeste v1 sans extension.

## Restant avant Gate R44

**R44.B :** Atlas graphique Qt, visualisation/édition via `AuthoringSession`, transactions Undo/Redo et QTests. **R44.C :** 5 régions complètes avec interactions réelles, portes conditionnelles, routes/PNJ, audit asset/licence, export Player, CI tri-OS et validation sur GPU réel. La reachability clés/portes (contre-exemples) et la mesure du temps de chargement ne sont pas encore certifiées.
