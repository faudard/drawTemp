# Entity & Event Studio 2.0 — parcours contextuel de siège

## Périmètre livré

Depuis **Carte et combat**, sélectionner une **porte** ou son **levier** puis
**Créer événement lié à la porte** (ou, dans **Inspecter acteur / objet**,
**Événement lié**). Cela sélectionne la porte dans l'onglet existant
**Personnages et événements → Objets interactifs**. Aucun nouvel inspecteur
indépendant, aucun nouveau modèle sérialisé ni registre d'événements parallèle.

1. Choisir une porte et son **levier**. Le levier lié existant est réutilisé ;
   un nouvel identifiant crée un objet `switch` ordinaire.
2. Sur la carte, choisir la case du levier puis cliquer
   **Depuis la carte** à côté de **Case levier**. Répéter pour **Case danger**.
   Les deux positions restent éditables au format `x,y`.
3. Saisir l'ID d'événement, l'intensité du danger et un court dialogue.
4. **Créer et simuler** prépare et valide un Content et un GameProject
   **ensemble** : objet lié, trigger `interact`, actions `message` et
   `hazard`, cinématique `tactical_event` incluant un vrai clip `dialogue`.
5. Le **Graphe des événements** existant s'ouvre avec **Condition vraie**,
   le rapport moteur avant/après, la porte traversable, la case de danger
   modifiée et l'ID de la cinématique attendue. Le bouton
   **Aperçu isométrique** du graphe reste disponible, ainsi que l'éditeur de
   cinématiques pour enrichir le plan narratif.

L'aperçu utilise un `Battle` jetable et les prédicats/actions existants.
Le moteur exécute désormais les triggers d'interaction **au moment de la
commande** : le Player peut donc détecter immédiatement la cinématique et
la présenter via `triggered_tactical_cinematics`, sans attendre une fin
de tour supplémentaire. Les sauvegardes et replays utilisent les données
`Mission.triggers` et `GameProject.cinematics` historiques.

## Gate de validation

- Une interaction valide sur le levier ouvre **effectivement** la porte
  (case précédemment bloquée, puis traversable).
- Le trigger du levier applique une conséquence tactique mesurable
  (danger sur une case), et émet le message prévu.
- Le Player retrouve la cinématique sous la cible
  `mission/event` et ne doit pas la rejouer après acquittement.
- Une référence inexistante, un ID déjà utilisé ou une case invalide
  empêchent **toute modification** ; Undo/Redo global du Studio conserve
  contenu et projet dans une seule transaction.
- Aucune fenêtre d'édition supplémentaire, aucune migration du schéma v1,
  aucune action tactique ou cinématique factice réservée à l'éditeur.

### Commandes de validation

```bash
python -m unittest tests_standalone.test_entity_event_studio_2 -v
python -m unittest tests_standalone.test_event_context tests_standalone.test_event_graph tests_standalone.test_cinematics tests_standalone.test_game_session -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_entity_editing_3719c_gui -v
```

Le scénario automatisé vérifie également l'exécution au travers de
`GameSession.execute` (commandes publiques), et non une simple peinture
de la carte. Les tests GUI/captures et la matrice CI doivent être contrôlés
sur la révision de la PR.

## Limites explicites

La tranche guidée crée **une cinématique tactique**, pas une nouvelle scène
du Story Studio. Pour un dialogue à choix en plein combat, utiliser le pont
narratif dédié déjà présent dans le projet : ce flux ne forge pas de
`during_tactical_event` sans validation du schéma existant. Les conditions
plus complexes, renforts et autres actions restent configurables dans le
Graphe des événements standard. Une cinématique peut être enrichie dans
l'éditeur existant, sans réimplémenter un Player ni un renderer.
