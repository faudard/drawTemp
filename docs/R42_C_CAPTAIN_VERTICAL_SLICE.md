# R42.C1 — VS-42 « La loyauté du capitaine »

**Statut : implémenté dans la PR #372, non certifié tant que la CI et les
tests Player installés/onscreen ne sont pas validés.** Ce vertical slice
est un projet *éditable et jouable dans le Player existant*, pas une nouvelle
machine à quêtes, ni un export binaire vérifié.

## Source de vérité

- `drawtemp.sdk.r42_captain_slice.make_captain_slice()` fabrique un
  `Content` et un `GameProject` valides avec les contrats existants.
  Le contenu est basé sur la petite fixture de migration Jeanne R0,
  copiée sans modifier ses sources.
- Les scènes, choix, conditions, effets, sous-graphes et dialogues v2
  habitent **uniquement** `GameProject.story`. Exécution par
  `GameSession → StoryBook (R9)`.
- Les variables `captain_trust` (relation -100..100), `evidence`,
  `quest_ready` et `ending` sont déclarées dans `story.state` et
  persistées dans **Campaign.story_flags**. Les effets `add_flag` et
  `set_flag` réutilisent les opérations R9 existantes.
- L'accès à `r42_captain_quest` est accordé par
  `unlock_mission` (R9) et filtré par `campaign_flow.gates` (R5).
  Les fins sont déclarées dans `campaign_flow.endings` (R5).
  Aucun second registre de missions, factions ou réputation R35.
- Les scènes `council` et `camp` sont des **convergences réutilisées**,
  référencées par des entrées de sous-graphes stables.
  Les chemins d'arrivée dynamiquement explorés proviennent de plusieurs
  scènes sources distinctes.

## Parcours témoins

Les choix ci-dessous utilisent les identifiants auteur des scènes/choix.
La navigation complète exige la lecture de chaque ligne avant un choix.

| Issue | Séquence depuis la scène `oath` | Confiance | Quête ouverte |
|---|---|---:|---|
| **Alliance** | `defend → rescue → trust → accept → alliance → finish` | 50 | Oui |
| **Accord** | `defend → ledger → avoid → accord → finish` | 25 | Non |
| **Exil** | `accuse → silence → avoid → exile → finish` | -30 | Non |

La route par preuve documentaire existe également :
`accuse → reveal → proof → accept → accord → finish`.
Elle ouvre la quête mais ne satisfait pas le seuil d'alliance.
Les conséquences sont appliquées **une seule fois** par choix. Les
conditions de départ, les flags, les relations et les récompenses restent
vérifiables après une sauvegarde au milieu de la première conversation.

## Création dans le Studio (sans JSON manuel)

1. Ouvrir **Outils → Narrative Studio R42…**.
2. Cliquer sur **Modèle VS-42** et confirmer la prévisualisation du
   remplacement *en mémoire* de Content + GameProject.
3. Vérifier l'aperçu puis cliquer **Appliquer**. Un Undo annule les deux
   documents ensemble ; aucune sauvegarde disque n'a eu lieu.
4. Sélectionner `oath`, consulter le graphe, les références et les variables.
   Cliquer **Auditer les chemins**, choisir `main` pour afficher
   les 3 routes témoins et les branches inaccessibles.
5. Enregistrer un **nouveau** projet via le mécanisme Studio normal,
   puis le lancer dans le Player pour tester les choix et sauvegardes.

## Génération reproductible et QA (CLI)

Depuis le dépôt, avec les dépendances installées :

```bash
# Audit borné ; strict, échoue si une fin, une scène, un choix ou
# une des deux scènes partagées est inaccessible.
python -m drawtemp.sdk.r42_reachability

# Génère deux *nouveaux* fichiers : captain.json + captain.game.json ;
# destination existante = refus, aucun overwrite silencieux.
python -m drawtemp.sdk.r42_captain_slice \
  --content-path /chemin/existant/dossier/captain.json

# Tests unitaires et sauvegardes / PlayerController
python -m unittest tests_standalone.test_r42_captain_slice -v
```

L'auditeur `drawtemp.sdk.r42_reachability.audit_narrative` parcourt
de façon déterministe des **copies de GameSession**, exécute les
`advance_narrative_line` et `choose_story_option` canoniques, et rend :

- fins trouvées et **route témoin complète** pour chacune ;
- scènes jamais visitées et choix impossibles, avec condition, exemple
  de chemin d'accès et valeurs observées (contre-exemple) ;
- au moins **deux scènes réutilisées** (arcs réellement parcourus et
  au moins deux scènes sources distinctes) ;
- budgets bornés : 2048 états par défaut, profondeur 32 choix ;
- distinction obligatoire `scope=campaign_entry_narrative_only`,
  `tactical_replay_verified=False`,
  `player_export_verified=False`.

L'audit ne simule pas de victoire tactique, d'événement de carte ni de
trigger hors entrée de campagne. Il ne prétend pas tester tous les
scénarios R10/R31 ou certifier la compatibilité GPU.

## Régressions et gates restant ouverts

Les tests `test_r42_captain_slice` couvrent trois fins, relations et
mission conditionnelle, un aller/retour `GameSession.recording` à mi-dialogue,
une reprise manuelle `PlayerController`, l'absence de double choix,
l'entrée dans la **vraie mission CT déverrouillée** et son checkpoint de combat,
les scènes orphelines, les conditions impossibles et les budgets trop courts.
Le test vérifie l'initialisation/reprise de la mission, **pas une victoire
tactique effective**.

À certifier avant de considérer **R42.C comme terminé** :

- CI du SHA final (Linux/Windows/macOS) et rapport de tests effectif ;
- vrais parcours installés dans les Players PC et captures UI/keyboard/focus ;
- preuves de sauvegarde/reprise et d'export sur machines propres ;
- quêtes multi-actes déclenchées *après* des missions tactiques réelles,
  plutôt que seulement débloquées depuis la narration ;
- localisation, portraits et mise en scène R11, tests d'accessibilité et
  couverture des scènes hors entrée de campagne.

**Ne pas fusionner cette PR en l'absence de résultats de CI fiables.**


## R42.C2 — Événement tactique et épilogue de victoire (incrément)

La mission `r42_captain_quest` n'est plus une simple mission
débloquée : elle porte maintenant un objectif CT canonique
`survive` (`target_ticks=50`) et un **trigger R9 one-shot**
`captain_orders` (`condition=tick, value=0`). Le trigger est
associé à `story.during_tactical_event` pour ouvrir la scène
multiligne `orders` pendant le combat.

Le joueur doit lire les deux répliques et choisir `acknowledge`
avant de pouvoir reprendre les commandes CT. La décision passe par
`GameSession.choose_tactical_story_option`, qui écrit une action
`story_effects` dans le journal Battle vérifiable. Le flag typé
`battle_orders` est écrit par l'effet R9, pas par le rendu Qt.

Après une **victoire produite par de vraies commandes CT**, le moteur
effectue son `_settle()` habituel :

- `Campaign.finish` crédite normalement la récompense de mission et la
  progression des héros ;
- `campaign_flow.outcomes[mission].victory` ajoute **une seule fois**
  le bonus d'or (+13) et le flag typé `quest_won=True` au travers du
  registre R5 `flow_ledger` ;
- `story.after_mission[mission]` ouvre la scène `quest_return` pour
  le rapport du capitaine ; la réponse `report` inscrit le flag
  `captain_report=True` dans le même `Campaign.story_flags`.

Les tests `tests_standalone/test_r42_captain_battle.py` enregistrent
une vraie session pendant le dialogue tactique, reprennent le Battle,
exécutent des commandes `end` jusqu'à la victoire (sans assigner
`battle.result`), enregistrent l'après-bataille, rechargent ce
checkpoint, vérifient l'unicité des effets et terminent le rapport.
Ils vérifient également que la mission ne peut être lancée avant son
déverrouillage narratif.

```bash
python -m unittest tests_standalone.test_r42_captain_battle -v
```

L'audit R42.C1 s'arrête volontairement aux scènes déclenchées depuis
l'entrée de campagne. Les racines `orders` (trigger tactique) et
`quest_return` (victoire mission) sont désormais énumérées
explicitement dans `external_trigger_scenes_unverified`, **sans les
classifier faussement comme orphelines**, et sans prétendre qu'un simple
parcours des dialogues suffit à prouver un déclenchement Battle.
Le test C2 fournit un témoin séparé, fondé sur le vrai moteur tactique.

La certification **sur vrai PC**, les scénarios de défaite, les
déclenchements tactiques composés et la validation packaging du Player
restent des critères ouverts.
