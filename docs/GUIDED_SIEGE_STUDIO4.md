# Game Studio 4.0 — 3.3.3 : Assistant de campagne et de siège

## Objectif

Réutiliser les trois outils canoniques **Carte et combat**, **Campagne & siège**
et **Scénario & dialogues** pour composer un petit siège sans éditer de JSON.
L'assistant ne crée **aucun moteur de combat ni nouveau format de sauvegarde**.

## Parcours utilisateur

1. Ouvrir **Espace projet → Assistant siège (3 missions)** ou
   **Campagne & siège → Assistant siège**.
2. Choisir un identifiant de siège inédit, une campagne existante et trois
   missions tactiques **distinctes** : *remparts*, *porte*, *salle du trône*.
   Ce sont des **missions existantes**, pas des copies implicites.
3. Utiliser **Vérifier préparation**. Les missions sans héros déclenchent une
   erreur ; les déploiements non définis ou adversaires absents sont signalés.
4. **Préparer déploiements** (action explicite) : déclare une zone
   `studio_start` sur les cartes qui n'en ont pas, à partir des positions
   de départ des personnages joueurs. Les zones existantes restent intactes.
   Cette modification du `Content` est soumise à Undo/Redo du document.
5. Renseigner réservistes, provisions, escortes et capacité des convois.
   Trois routes de réserve de **deux tours** sont proposées et restent
   modifiables dans l'onglet **Logistique & convois**.
6. Facultatif : choisir un véritable **levier** sur les remparts et une
   **porte** sur la mission d'entrée. Cela crée le nœud stratégique
   `walls_open_gate` avec preuve `battle_event(interact)` et conséquence
   `open_door`. Les conditions et effets restent modifiables via le
   Graphe stratégique de la PR #51.
7. Si souhaité, cocher explicitement **Définir les remparts comme départ de
   campagne**. Sinon, la mission de départ de la campagne ne change pas.
8. Cliquer sur **Créer siège guidé**. Le candidat est construit puis
   entièrement validé avant mutation du projet en mémoire. Il n'écrase
   aucun siège existant ; enregistrer ensuite le `*.game.json`.
9. Continuer dans **Fronts et finale**, **Scénario & dialogues** et
   **Chronologie / jouer**, puis démarrer le vrai Player 2D et sauvegarder.

## Sémantique et limites

- Fronts `walls` et `gate` : jouables indépendamment, dans l'ordre choisi.
- Front `throne` : verrouillé jusqu'à **deux victoires réelles** sur
  `walls` et `gate`. Aucune simulation d'issue tactique.
- Les ressources sont limitées ; un convoi ne téléporte pas d'unité :
  l'arrivée dépend des vraies commandes et tours du moteur existant.
- L'assistant ne dessine pas automatiquement les cartes, ne crée pas
  de dialogues ou de cinématiques et ne remplace pas le graphe narratif.
- Les sauvegardes et replays précédents ne sont pas réécrits. Une nouvelle
  campagne de siège dispose de ses propres slots vérifiés.
- **Le gate Game Studio 4.0 complet reste ouvert** : scènes, cinématiques,
  deux fins alternatives et parcours de trois missions devront être
  vérifiés ensemble dans les jalons 3.3.4–3.3.6.

## Tests

```sh
python -m unittest discover -s tests_standalone -p test_studio_siege_flow.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover \
  -s tests_standalone -p test_studio_siege_flow_gui.py -v
python -m unittest discover -s tests_standalone -v
```

Les tests couvrent : construction atomique, déploiement explicite et idempotent,
doublons/ref invalides, finale verrouillée, quantités de ressources, routes,
événement de levier opt-in, rejeu de siège et enregistrement depuis Tk.
