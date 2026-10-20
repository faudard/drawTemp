# R75.A — Assisted Narrative & Quest Authoring (premier incrément)

**Statut : implémentation en PR, non certifiée.** R75.B (assistant visuel Qt)
et la validation par auteur tiers/UX de R75.C restent ouvertes.

## Contrat canonique

`drawtemp.studio.r75_narrative_assist` livre un contrat de proposition
`version=1` contenant `id`, `source`, `hook`, `entry_scene`,
`scenes` et `endings`. Le format est un brouillon de revue **en mémoire**,
pas un second schéma sauvegardé. Le contenu appliqué reste uniquement
`GameProject.story`, inspecté et exécuté par le véritable `StoryBook`.

- Les déclarations `source.kind`, `attribution`, `license`, `rights`
  et `redistribution_allowed` sont obligatoires. Il s'agit de
  **déclarations auteur**, pas d'une certification de droits ni d'une
  autorisation automatique d'export.
- Les `hook` libres `entry_scenes` (campagne) ou `after_mission`
  (mission) ajoutent des scènes sans écraser un dialogue existant.
- Tous les choix et prédicats passent par la validation canonique; seuls
  `set_flag` et `add_flag` sont autorisés pour les effets proposés par
  cette première tranche. Aucune exécution de scripts ni service externe.
- `NarrativeAssistController.preview(proposal)` retourne une revue comprenant
  empreinte SHA-256, provenance, scènes ajoutées et chemins témoins des fins.
  Aucun changement de projet ou fichier n'est effectué.
- `apply(review, approved=True)` exige une approbation explicite, l'identité
  exacte de la revue, et une révision `AuthoringSession` valide. Chaque
  validation acceptée est un unique pas Undo/Redo; `save()` demeure distinct.

## Analyse de couverture

Les chemins sont simulés au moyen des véritables
`StoryBook.choices()/choose()` et de `Campaign`. Rejets : références
inconnues, cycles, choix/branches/fins inatteignables depuis l'état initial,
et dépassement des budgets (64 scènes, 64 étapes, 1024 états).

**Limite importante :** l'analyse part d'une campagne neuve, flags vides,
0 or, aucune mission terminée. Elle ne démontre pas la couverture de toutes
les sauvegardes historiques ni des conditions externes.

## Démonstrateur VS-75

`three_endings_template(mission_id)` crée cinq scènes : proposition,
conséquences, secours, accord et départ. Le drapeau `r75_route` commande
les embranchements et `r75_outcome` enregistre l'issue finale, persistante
via la sauvegarde native `Campaign`. Le modèle s'accroche à un
`after_mission` libre et ne remplace pas l'introduction Jeanne.

### Vérification

```sh
python -m unittest tests_standalone.test_drawtemp_r75_narrative -v
```

Le workflow R75 lance ces tests sur Ubuntu, Windows et macOS.
Les gates complémentaires restent nécessaires : Qt onscreen, vrai gameplay
Studio/Player, validation auteur tiers, compatibilité longue durée des
sauvegardes et certification de release sur SHA final.
