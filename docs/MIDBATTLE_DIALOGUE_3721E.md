# 3.7.21E — Dialogues à choix pendant une bataille

## Résultat attendu

Un déclencheur canonique de `Mission.triggers` peut interrompre une
bataille du Player pour ouvrir une scène du Story Studio, accepter un choix
réel et reprendre exactement le même combat.

**Aucun second moteur narratif ni modification du journal de replay Battle.**
Les choix continuent d'utiliser `StoryBook.choose`, et leurs conséquences
sont enregistrées dans la progression de campagne existante.

## Édition visuelle

1. Créer le déclencheur tactique dans le Graphe des événements :
   par exemple `garden/spore_pulse` ou un `interact` sur le levier.
2. Créer les scènes, dialogues, conditions, choix et conséquences dans
   **Story Studio**.
3. Dans la section Déclenchement, choisir **Mission / trigger** et
   **Dialogue pendant combat**. Cliquer **Lier dialogue tactique**.
4. Le lien est stocké sous
   `GameProject.story.during_tactical_event["garden/spore_pulse"]`.
   Une mission, un trigger ou une scène inexistants sont refusés lors
   de la validation et de l'enregistrement du projet.

## Comportement runtime

- `GameSession` examine seulement les IDs réellement ajoutés à
  `Battle.fired` par le moteur pendant la dernière commande.
- Plusieurs événements simultanés donnent une **file FIFO** de scènes.
  Les scènes `next_scene` de la scène actuelle se terminent avant que
  la file ne reprenne.
- Les commandes tactiques et l'IA sont suspendues jusqu'à résolution des choix.
- `StoryBook.matches`, `StoryBook.choices` et `StoryBook.choose`
  restent la source des conditions et effets : drapeaux, or, équipement,
  recrutement et déblocage de missions. Le combat reprend avec le même
  journal de commandes et les mêmes unités.
- Si la victoire et le dialogue surviennent ensemble, le règlement des
  récompenses est différé jusqu'au choix final. La cinématique tactique
  de 3.7.21D, si elle existe, conserve sa présentation antérieure au
  dialogue dans le Player.

## Sauvegarde / reprise / invalidité

La sauvegarde de session ajoute seulement si nécessaire les clés optionnelles
`tactical_story_pending` et `tactical_story_queue`. Les anciennes
sauvegardes sans ces champs restent acceptées.

Au chargement, la session vérifie le digest, la compatibilité contenu/projet,
le replay de Battle, la scène en attente, la file, l'origine tactique
effectivement déclenchée et l'absence d'un dialogue de campagne concurrent.

Les choix sont appliqués via `PlayerController._apply`, dont le checkpoint
transactionnel restaure la session entière sur erreur d'effet ou de
persistance.

## Limites délibérées

- Périmètre P0 : **batailles seules**, pas d'activation d'un dialogue
  tactique depuis un front de siège non focalisé.
- Les changements immédiats de porte, HP, dangers et renforts restent gérés
  par les **actions tactiques rejouables** du moteur. Les choix de scène
  modifient la campagne persistante ; injecter des effets tactiques
  directement depuis une scène exigerait un nouveau contrat de commandes
  rejouables et auditées, non ajouté ici.
- La narration après victoire reste sur son hook de campagne distinct.

## Commandes

```bash
python -m unittest tests_standalone.test_tactical_dialogue \
    tests_standalone.test_narrative tests_standalone.test_game_session
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
    tests_standalone.test_event_graph_gui tests_standalone.test_story_conditions_gui
```
