# R25.B — SceneRouter : transitions multi-mode et état persistant

**Statut :** développement proposé en PR empilée sur R25.A. Non certifié R25/6.1.

## Contrats réellement couverts

- `GameProject.scene_routes` est facultatif, versionné (schema 1), et reste dans le manifeste **canonique** ; ni deuxième graphe de campagne ni nouveau registre métier.
- Le routeur headless `sporebound.scene_router.SceneRouter` valide des arcs `source → destination` entre les scènes `GameProject.exploration` et les missions `Content`. Les références sont explicites et contrôlées, IDs uniques, champs stricts et bornes de taille.
- Les conditions `when` sont celles du moteur narratif préexistant (`sporebound.narrative.matches`) : flags, missions complétées, or, conjonctions/négations. Aucun langage parallèle.
- L'arrivée exploration est un vrai point de spawn libre/atteignable dans la carte de la scène ; elle est persistée dans `Campaign.story_flags` avec la clé d'exploration historique.
- L'arrivée en arène CT doit désigner une **position déjà occupée par un héros du contenu tactique**. R25.B ne reprogramme pas le placement/deployment du combat : ce serait une modification des règles/replays existants.
- `GameSession.route_transition(id)` réalise le départ en jeu en passant par le vrai `start_mission()`, avec les règles de disponibilité de campagne. La progression, les flags, l'inventaire, les héros et l'équipement restent dans `GameSession.progress`, sans copie indépendante.
- `GameSession.route_move(dx,dy)` réemploie le `Exploration` cardinal actuel. C'est une **passerelle fonctionnelle**, pas un moteur de déplacement temps réel à vitesse/FPS indépendante. Le temps réel est R26.
- Pendant le combat, toute transition est interdite. Le joueur doit terminer et appeler `return_to_campaign()`, ou abandonner explicitement avec `abandon_encounter()`. Les récompenses du vrai CT restent accordées une seule fois.
- Les projets ayant des liens de scène ne peuvent pas démarrer une mission tactique via le point d'entrée direct `start_mission()` ; les projets historiques sans liens conservent l'ancien comportement.

## Exemple de manifeste du projet

```json
{
  "game_modes": {
    "version": 1,
    "default": {"preset": "srpg"},
    "scenes": {"arrival": {"preset": "action"}}
  },
  "scene_routes": {
    "version": 1,
    "start": "arrival",
    "links": [
      {
        "id": "to_arena",
        "source": "arrival",
        "destination": "r0_village_forest",
        "spawn": [1, 1],
        "when": {"flag": "portal_open", "eq": true}
      },
      {
        "id": "return",
        "source": "r0_village_forest",
        "destination": "arrival",
        "spawn": [0, 1],
        "when": {"completed_mission": "r0_village_forest"}
      }
    ]
  }
}
```

**Important :** les IDs et positions ci-dessus ne sont qu'illustratifs ; `arrival` doit être une vraie scène avec carte `exploration` valide, et `spawn` en arène doit être la position d'un héros réellement déployé dans cette mission.

## Sauvegarde et reprise

- Les sessions historiques de version 1 et projets sans `scene_routes` restent **inchangés** : pas de champ ajouté aux JSON ni de changement au digest historique.
- Une session opt-in ajoute uniquement `scene_route: {version:1, current:"...", history:["..."]}` au **même GameSession.recording()**. Le digest enveloppant couvre l'état de campagne et l'itinéraire.
- `GameSession.from_recording()` vérifie le digest du projet, le journal tactique/replay, l'ordre des transitions et que le curseur correspond à la bataille en cours. Les sauvegardes corrompues ou incohérentes échouent explicitement.
- Une transition refusée (précondition, source, mission verrouillée, spawn erroné) n'altère ni la progression, ni la bataille, ni l'historique de route. Une exception pendant la transition revient à l'état pré-commande en mémoire.
- **Limite de sécurité :** le SHA-256 détecte les corruptions et incohérences, mais ce n'est pas une signature d'authenticité contre quelqu'un qui réécrit le fichier et recalcule son hash. La suite R25.E doit ajouter la vérification forte inter-modes/transactions d'IO, reprise après crash, identités et journaux événementiels.

## Tests ciblés

```sh
python -m unittest tests_standalone.test_r25_scene_router -v
python -m unittest tests_standalone.test_r25_foundation -v
python -m unittest tests_standalone.test_game_session -v
```

Workflow dédié : `.github/workflows/r25-scene-router.yml` (Linux, Windows, macOS, Python 3.12). La CI doit être évaluée sur le dernier SHA et les vrais logs, pas inférée de la création du workflow.

## Hors périmètre

Le Player Qt / QML n'expose pas encore le passage de portail, le HUD ni la caméra top-down ; pas de simulation libre à tick fixe branchée à ce stade ; pas de Studio sans JSON. Les transitions multi-fronts sont explicitement bloquées lorsque `scene_routes` est actif. Les gates UX/GPU physiques, packaged Player, R25.6–R25.10 et certifications inter-genres restent ouverts.
