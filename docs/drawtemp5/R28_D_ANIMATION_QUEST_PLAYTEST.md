# R28.D — Animation, hitboxes, Event/Quest Graph et playtest roundtrip

**État : incrément exécutable R28.5 / R28.6 / R28.8, PARTIEL.**
**Branche empilée : #298 R25.A → #306 R28.B → #321 R28.C → PR R28.D.**

Les données persistantes restent exclusivement dans :
- `GameProject.assets` (registre portable v1 des sprites/animations),
- `Content.missions[*].units` (footprints du moteur tactique),
- `Content.missions[*].triggers` et `GameProject.story` (graphe R9),
- `GameSession` / `Battle` (playtest isolé et replay vérifié).

## Parcours Studio Qt

Dans `drawtemp.studio.qt_shell`, choisir **Événements / Animation**.

### 1. Animation & Hitbox Studio

**Animations** : déclarer l'identifiant et le chemin portable d'un sprite PNG
déjà existant dans le projet, puis un identifiant d'animation, un slot de
présentation (`hero_move`, `hero_move_east`…), une durée par sprite en ms
et le bouclage. Le registre `AssetRegistry` valide les chemins, IDs, références
et durées. Les modifications sont inspectées par `AuthoringSession.preview_project`
puis appliquées en **une transaction Undo/Redo**.

**Sélection d'image** : `animation_sprite_id` issu de
`sporebound.visual_motion` renvoie le bon ID de sprite à un instant logique.
Ce n'est **pas** une lecture PNG ni une animation jouée à l'écran.

**Hitboxes** : vue 2D des cases réellement occupées par les unités
tactiques, obtenues de `pos` et `footprint` dans le contenu.
Aucune modification de collision n'est autorisée par cette vue :
le `RADIUS` fixe du runtime action R26.A, les hitboxes d'attaque,
hurtboxes et le montage d'animations sur le joueur action restent à concevoir
après le SceneRouter R25 / raccordement R26.

### 2. Event/Quest Graph

Projection interactive de `Mission.triggers` par le
`EventGraphView` R9 déjà validé. Les liens entre deux événements
créent les vraies dépendances `after` / `after_any` avec
`EventStudio.link`, rejet des cycles et rollback par R1. La liste des
scènes narratives (ID, titre, capacité effective) est lue du
`GameProject.story` existant et des profils R25 ; aucun nouveau nœud
narratif sérialisé ni condition de quête factice.

**Limite multi-mode** : les liens éditables restent des triggers CT. Les
transitions Action / Classic RPG / récit en temps réel ne sont pas encore
implémentées ni simulées par ce graphe.

### 3. Studio → GameSession → Studio (playtest isolé)

Choisir une campagne, un éventuel ID de choix narratif, éventuellement
une mission réellement accessible, puis la graine. Le Studio construit une
`GameSession.new` à partir de **copies validées** du snapshot R1,
traverse les vrais gates `choose_story_option`/`start_mission` si
demandés, puis vérifie le checkpoint :
`GameSession.from_recording(game.recording(), content, project)`.
Le rapport inclut le digest, la révision d'auteur, la scène narrative
et l'état vérifié. **Aucune sauvegarde Player, aucun déblocage artificiel,
aucune édition Content/GameProject**.

C'est un **roundtrip headless d'une session réelle**, pas encore un
`Studio → Player GUI → Studio` complet avec contrôles/renderer action et
retour de télémétrie. Ce dernier nécessite R25/R26 et reste un gate R28.8.

## Gates automatisés (à vérifier dans GitHub Actions)

```bash
python -m unittest tests_standalone.test_r28d_animation_events_roundtrip -v
python -m unittest tests_standalone.test_r28c_gameplay_designers -v
python -m unittest tests_standalone.test_r28_profile_inspector -v
python -m unittest tests_standalone.test_drawtemp5_r2 -v
```

Workflow : `.github/workflows/drawtemp-r28d-roundtrip.yml`,
Python headless 3.10/3.12/3.14 et PySide6 offscreen sous Ubuntu,
Windows et macOS. CI verte **non présumée** au moment du commit.

## Critères de suite R28.D2 / R28.E

1. Hitbox/hurtbox et zones d'attaque temps réel éditables avec contrat de
   collision signé par le runtime R26, lecture des frames dans un Player
   action concret, goldens visuels + budget performance.
2. SceneRouter R25 : scènes et quêtes multi-mode persistantes, retours
   Player→Studio, pause/resume et erreurs explicites.
3. Trois projets SRPG / action-aventure / narratif réellement créés sans
   JSON manuel, jouables, sauvegardables et exportés sur 3 OS.
4. Rebase de #292 après les dépendances empilées, sans perdre les commandes
   de l'assistant de création R28.A.
