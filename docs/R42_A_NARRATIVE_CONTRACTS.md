# R42.A — Narrative Studio 2.0: contrats et migration (incrément)

Statut : **code en PR**, pas certification R42/DrawTemp 8.2. Roadmap source :
[`DRAWTEMP_8_1_TO_9_0_DETAILED_ROADMAP_R41_R50.md`](DRAWTEMP_8_1_TO_9_0_DETAILED_ROADMAP_R41_R50.md).
PR #289 définit les jalons multi-genres R25–R30, pas les contrats R42.

## Autorités canoniques et limites

- `GameProject.story` est **la seule** source des scènes, locuteurs, choix et conséquences. `Content.missions[].triggers` reste la source R9 des événements tactiques.
- `sporebound.narrative.validate_story`, `matches` et `StoryBook.choose` restent la **seule** validation/interprétation des prédicats et effets; pas de `eval`/`exec`, pas de second bus d'événements ni de gestionnaire de quêtes.
- `GameSession.progress` (Campaign) reste l'autorité des flags, de l'or, de l'inventaire, des récompenses et du checkpoint; aucune nouvelle persistance runtime.
- Le nouveau `schema_version: 2` est **opt-in** dans `GameProject.story`. Un projet non versionné garde exactement son sérialisateur, ses digests et ses choix.
- Chaque scène v2 porte ses `lines` (`id`, `speaker`, `text`) avec des références stables `scene_id/line_id`. La première ligne doit égaler les champs historiques `speaker` et `text`, projetés pour l'ancien Player. Les autres lignes ne sont **pas encore jouées** par ce Player (travail R42.B).
- `subgraphs` est une liste de **références nommées** `id/entry_scene` vers les scènes canoniques existantes. Les chemins partagés utilisent les `choices[].next_scene` R9; aucun appel récursif de script ou moteur d'exécution parallèle. Les vraies piles d'appels/retours attendront un contrat Player transactionnel séparé.
- Budgets v2: 512 scènes, 32 lignes par scène, 4096 lignes au total, 64 points d'entrée réutilisables, 32 arêtes sur le plus long chemin. Les cycles, références manquantes, champs inconnus, lignes en doublon et effets inconnus sont rejetés **à l'ouverture**.

## Migration explicite

```python
from sporebound.narrative_r42 import (
    migrate_story_v1, set_dialogue_lines, declare_subgraph,
)
upgraded = migrate_story_v1(project, content)
upgraded = set_dialogue_lines(upgraded, content, "arrival", [
    {"id": "intro", "speaker": "Jeanne", "text": "Nous partons."},
    {"id": "captain", "speaker": "Capitaine", "text": "En avant !"},
])
upgraded = declare_subgraph(upgraded, content, "first_meeting", "arrival")
# Faire preview/apply via la même AuthoringSession, puis sauvegarder le projet.
```

Les trois opérations sont **copy-on-write** : elles renvoient un `GameProject`
entièrement revalidé, sans muter l'entrée, et peuvent entrer dans une transaction
Preview/Apply + Undo/Redo de l'AuthoringSession R1. Aucun fichier externe.

**Sauvegardes :** le digest du graphe est intentionnellement différent après
migration. Ne jamais charger automatiquement une ancienne sauvegarde avec le
nouveau manifeste; conserver l'ancien projet et ses sauvegardes, ou démarrer une
nouvelle partie. Un migrateur de sauvegardes certifié est hors périmètre.

## R42.A2 — Variables typées, relations et portées déclaratives

- `GameProject.story.state` est facultatif, v2 uniquement, et contient au plus 128
  déclarations `id / kind / scope / owner / initial`.
- Types : `bool`, `int`, `text`, `relation` (valeur entière -100..100).
  Portées : `campaign` (owner = campagne), `scene` (owner = scène) et
  `mission` (owner = mission, pour les branches de quête adossées à R10).
- **Portée = espace de noms durable**, pas durée de vie automatique : aucun
  reset silencieux en sortie de scène. La durée de vie contextuelle, les
  conversions et la réputation de faction R35 seront traitées explicitement.
- Les clés stables `r42_<scope>_<owner>_<id>` vivent **dans le même
  `Campaign.story_flags`**, sans nouveau magasin ou schéma de checkpoint.
  R9 `matches`, `set_flag` et `add_flag` restent la seule exécution.
- `StoryBook.initialize` installe une fois les valeurs initiales après
  vérification de collision. À la reprise, `verify_state` rejette tout
  champ absent, mauvais type ou relation hors bornes, même si le checksum
  a été recalculé. `StoryBook.choose` vérifie également les bornes après
  un choix, avant tout commit : pas de mutation partielle.
- Les constructeurs `state_condition`, `state_effect` génèrent des
  prédicats/effets R9 ordinaires, validés au chargement du projet et
  inspectables via `GameSession.narrative_state()` (projection détachée).
- La réputation **économique/de faction** de R35 reste exclusivement dans
  `LivingWorld` ; aucun miroir R42 de cette réputation n'est créé.
  Le raccordement des déclencheurs de quêtes idempotents R10 viendra dans
  un incrément distinct.

Exemple d'authoring (à soumettre ensuite à l'AuthoringSession) :

```python
from sporebound.narrative_state_r42 import (
    declare_state, state_condition, state_effect,
)
new = declare_state(upgraded, content, identifier="captain", kind="relation",
                    scope="campaign", owner="main", initial=0)
predicate = state_condition(new.story, identifier="captain",
                            scope="campaign", owner="main",
                            operator="gte", value=30)
effect = state_effect(new.story, identifier="captain",
                      scope="campaign", owner="main", action="add", value=10)
# Utiliser les helpers de story_authoring pour attacher les effets/conditions.
```

## Vérifications

```bash
python -m unittest tests_standalone.test_r42_narrative_contracts tests_standalone.test_r42_narrative_state -v
python -m unittest tests_standalone.test_narrative tests_standalone.test_story_graph tests_standalone.test_game_session -v
```

La CI R42.A couvre trois OS en headless. **Elle ne certifie pas** le Player Qt,
les interactions UI onscreen, les GPU, l'export natif ou la release. La reprise
au milieu d'un dialogue multi-lignes, les variables par portée, la réputation,
l'idempotence de quêtes, le debugger interactif, le QA de reachability complet,
la localisation et le vertical slice *La loyauté du capitaine* restent à livrer
sur R42.B/C ou incréments Core supplémentaires. Les preuves d'acceptation
ne doivent pas être cochées avant validation sur le SHA final de master.
