# 3.3.2 — Événements stratégiques vers scènes narratives

## Chaîne causale authentifiée

La PR #51 établit la preuve tactique et applique les effets (par exemple
`interact portcullis_lever` sur le front `walls` → `open_door main_gate` sur
`gate`). Ce jalon raccorde l'**activation effective** du nœud à une scène
de `StoryBook`, et non un prédicat client ou une prévision.

Dans **Scénario & dialogues**, choisir l'identifiant
`siege_id/node_id` sous « Siège / événement », choisir la scène à déclencher
puis **Lier événement stratégique**. Cette relation est stockée dans
`GameProject.story.after_strategic_event`, facultatif et validé contre
les véritables nœuds du siège. Les liens figurent dans les références
du Workspace. Aucun JSON manuel.

### Lecture dans le Player

1. `MultiFrontSession.execute()` valide la commande tactique, applique
   les conséquences inter-fronts et journalise `strategic_event_fired`.
2. `SiegeStory.sync()` observe ce journal et le set `fired_graph`, puis
   inscrit **une seule fois** une entrée narrative `strategic`.
3. Le Player affiche la scène et bloque les nouvelles commandes tant
   qu'un choix narratif est attendu. Les effets du choix sont conservés
   par `StoryBook`.
4. Plusieurs scènes déclenchées dans la même opération sont mises en file,
   dans l'ordre chronologique du journal stratégique.

Le journal narratif opt-in passe en **version 2** avec empreinte des
nœuds déclenchés et de la file de scènes. Les projets sans cette fonctionnalité
conservent exactement le format **version 1**. Une sauvegarde provenant d'un
manifeste modifié est déclarée incompatible ; aucune nouvelle règle n'est
appliquée silencieusement.

À la reprise, chaque entrée `strategic` est vérifiée sur le **préfixe exact**
du replay tactique, à la commande authentique où le nœud a réellement été
déclenché. Les déclenchements forgés, anticipés, répétés ou omis sont rejetés.

## Exemple reproductible

```sh
python -m unittest discover -s tests_standalone \
  -p 'test_strategic_narrative_bridge.py' -v
python -m unittest discover -s tests_standalone -v
```

Le test modifie uniquement la position du levier des remparts dans son contenu
de test pour rendre son interaction réelle accessible rapidement. Il vérifie
le front `gate` encore non chargé, le déclenchement de la scène, le blocage
des commandes, le choix, les fichiers de sauvegarde/reprise et les rejets
de journaux falsifiés.

**Limite du présent jalon :** le déclenchement des timelines caméra/audio
sur cette scène nécessite le jalon 3.3.4. Le moteur tactique n'est pas modifié.
