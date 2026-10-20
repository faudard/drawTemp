# R75.A — Assisted Narrative & Quest Authoring (premier incrément)

**Statut : implémentation en PR, non certifiée.** Le premier assistant Qt
R75.B est raccordé au Studio. Il reste à certifier l'UX et la revue
par auteur tiers R75.C, ainsi que la couverture de sauvegardes préexistantes.

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

## Assistant Qt opt-in (première tranche R75.B)

Depuis le shell principal : **Outils → R75 • Quêtes et dialogues assistés…**
(également dans la palette de commandes). Le dialogue
`R75NarrativeAssistDialog` partage la `AuthoringSession` du Studio.
Il choisit une mission et un préfixe, propose un arbre déterministe local,
puis présente **un diff lisible** : scènes, textes, choix, prédicats,
effets, provenance, droits déclarés, chemins témoins et SHA-256.

Un changement de paramètres annule la revue. L'action Approuver est
désactivée tant que l'aperçu n'a pas abouti et exige une confirmation
explicite dans une boîte de dialogue (refus par défaut). La session
est alors modifiée en un seul pas Undo, **sans sauvegarde implicite**.
Qt reste une dépendance optionnelle; le Core n'importe jamais PySide6.

L'interface n'est pas un service génératif ni un éditeur de texte
libre multi-quêtes et n'est pas certifiée sur matériel réel.
Le test Qt offscreen vérifie l'affichage du diff, le refus,
l'invalidation des paramètres, la révision obsolète et Undo.

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
Pour l'intégration Qt facultative :

```sh
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r75_narrative_qt -v
```

`PySide6` est requis pour la suite Qt, lancée dans un job Ubuntu dédié.
Les gates complémentaires restent nécessaires : Qt onscreen, vrai gameplay
Studio/Player, validation auteur tiers, compatibilité longue durée des
sauvegardes et certification de release sur SHA final.
