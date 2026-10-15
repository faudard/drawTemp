# DrawTemp 5.0 — R9 Event & Narrative Studio (R9.A + R9.B + R9.C + R9.D)

> **Périmètre :** R9.A et R9.B, par PR dédiées. Ceci décrit les fonctionnalités effectives, non la certification globale R9. L'intégration Studio R2 / carte GPU R5 reste à réaliser.

## Ouvrir l'atelier

```bash
python -m pip install ".[qt6]"
python -m drawtemp.studio.event_studio
# Projet existant : Content et GameProject dans les deux fichiers canoniques
python -m drawtemp.studio.event_studio --content /chemin/jeanne.json
# Validation de démarrage Qt sans interaction
QT_QPA_PLATFORM=offscreen python -m drawtemp.studio.event_studio --smoke
```

L'atelier autonome démarre sur le projet de référence Jeanne (mémoire, sans remplacer les fichiers existants). Pour modifier un vrai projet, passer `--content` avec son fichier Content ; son fichier `.game.json` est obligatoire. `Enregistrer` utilise la transaction atomique existante de R1 ; sur un projet de référence, la première sauvegarde propose un emplacement. Le système refuse de remplacer silencieusement une destination existante. Si une transaction interrompue doit être récupérée, passer par `AuthoringSession.recover` avec un choix explicite avant de rouvrir le document.

## Contrats et fonctionnalités disponibles

| Roadmap | Statut de cette tranche | Parcours effectif |
| --- | --- | --- |
| R9.1 Workspace | **Initial** | Choisir une mission, créer/dupliquer/ouvrir/supprimer un trigger, inspecter ses commandes |
| R9.2 Properties | **Partiel** | Déclencheur `tick`, `interact`, `enter`, `defeated`, `hp_below`, `wave_capacity` ; délais/expiration |
| R9.3 Visual Commands | **Partiel** | Message, danger, statut, disparition ; ajout, réordonnancement, retrait ; d'autres actions sont exposées par l'API de service |
| R9.4 Condition Builder | **Initial** | Ajout de feuilles typées en ET/OU/NON et manipulation d'arbre via API headless |
| R9.5 Pages/States | **À compléter** | Délais/expiration et références persistantes existantes ; pas de nouveau système de pages |
| R9.6 Visual Graph | **Partiel** | Graphe DAG issu des triggers canoniques, liaisons ET/OU et assistant visuel de création de deux branches narratives et réunion ; déplacement direct des nœuds à venir |
| R9.7 Timeline | **Partiel** | Délais et expiration en ticks ; activations, annulations et édition avancée exposées par le service |
| R9.8 Map Preview | **Partiel** | Repères 2D pour interaction/entrée/danger, pas encore la surimpression dans le viewport GPU R5 |
| R9.9 Debugger | **Partiel** | Simulation isolée et trace du moteur réel ; démarrage, pas à pas, continuation, points d'arrêt et trace de provenance depuis Qt ; pas un replay attesté |
| R9.10 Cross-Mission | **Partiel** | Scènes narratives et liaisons événement → scène/cinématique dans GameProject ; pas encore l'inspection du graphe de campagne intermissions |
| R9.11 Graph QA | **Partiel** | Validation des références par Content/GameProject, contrôle borné de graphe ; certification exhaustive des fins inaccessibles à venir |
| R9.12 Replay Gate | **Non certifié** | Preview et débogage synthétiques explicitement **non assimilés** à un replay Player attesté |

### Démonstration porte / levier / narration

Le service `drawtemp.studio.events.EventStudio` expose `gate_wizard(...)`, réutilisant `sporebound.entity_event_studio.author_gate_sequence`. Cette commande produit dans **une seule transaction** un événement d'interaction associé au levier, un dialogue et une cinématique déclenchée en jeu ; elle n'invente pas de schéma alternatif. L'atelier Qt dispose du formulaire de création des événements et des scènes. L'assistant visuel complet porte+levier reste à brancher dans le workspace Qt unifié R2/R5.

Pour un flux assisté headless :

```python
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.events import EventStudio

content, project = reference_project()
studio = EventStudio(AuthoringSession.new(content, project))
studio.gate_wizard(
    MISSION, door_id="gate", lever_id="lever", lever_cell=[2, 4],
    event_id="gate_r9", danger_cell=[1, 3], danger=4,
    dialogue="La porte est ouverte !", cinematic_id="cin_gate_r9")
trace = studio.preview(MISSION, "gate_r9", scenario="satisfied")
assert trace["report"]["isolated"]
studio.undo()
```

## Garantie de non-régression

- **Source de vérité :** les événements restent dans `Content.missions[].triggers` ; scènes et cinématiques dans `GameProject`. Aucun fichier `*.event.json`, nouvel interpréteur ou simulation personnalisée.
- **Atomicité :** `AuthoringSession.preview_pair → apply`, Undo/Redo et rejet de la prévisualisation obsolète. Les liens invalides et cycles sont refusés par la validation canonique.
- **Simulation :** la prévisualisation délègue à `sporebound.event_context.preview_event`, qui appelle le dispatcher tactique réel dans un Battle jetable. Le débogueur `EventDebugger` émet des traces isolées ; `replay_verified = None` ne vaut pas certification.
- **Qt optionnel :** import du service sans Qt ; seules les vues importent `PySide6`. Les outils Tk restent disponibles pendant la migration.
- **Tests :** `python -m unittest tests_standalone.test_drawtemp5_r9 -v`, plus smoke Qt 6 et non-régression événementielle du legacy.

## Gates encore ouverts avant de déclarer R9 terminé

Intégration au `QMainWindow` R2 et au viewport GPU R5, palette exhaustive des commandes R9.3 avec audio/combat/cinématiques liées au runtime, pages/états et programmation complète, graphe narratif interactif, debugger à points d'arrêt depuis Qt, QA d'atteignabilité de bout en bout, rejouabilité déterministe du parcours Studio → Player → sauvegarde/reprise et inspection réelle du rendu. Aucune simple démo de fenêtre ne clôt ces exigences.

## R9.B — Embranchements, debugger interactif et QA

La deuxième tranche est implémentée dans `drawtemp.studio.events.EventStudio`, `drawtemp.studio.event_debug_controller.EventDebugController` et l'interface Qt existante, sans créer de nouveau format d'événement.

- **Embranchement sans JSON :** onglet Graphe → « Créer un embranchement narratif (2 choix)… ». Renseigner l'événement source, la case d'entrée, la scène, deux décisions et leurs actions (message ou danger), avec réunion optionnelle. Le constructeur métier reste `sporebound.event_branch_builder.author_choice_fork`. Tous les triggers, scènes et gardes `after_choice` sont validés puis committés en **un seul Undo/Redo**.
- **Gardes de choix :** l'onglet Narration relie un événement à un choix existant et permet de supprimer cette garde (sans supprimer la scène).
- **Timeline :** édition des délais/expirations en ticks et activations, plus annulation après d'autres événements. Les effets temporels sont exécutés par les règles canoniques.
- **Débogage :** onglet Simulation → Démarrer → choisir un événement de la chaîne → activer son point d'arrêt → Pas/Continuer. Les inspections restent isolées d'une partie réelle. Toute édition/Undo/Redo rend immédiatement obsolète la session de diagnostic : il faut la redémarrer.
- **Branch QA :** contrôle structurel des scènes, des entrées, des choix contradictoires et des gardes tactiques, plus des sondes bornées facultatives appelant la production StoryBook et les prévisualisations Battle. **La QA structurelle ne prouve pas qu'une fin soit atteignable en jeu.**
- **Tests :** `python -m unittest tests_standalone.test_drawtemp5_r9b -v`. La CI R9 lance aussi les tests legacy de débogage, d'embranchement et de couverture du graphe, sur Python 3.10/3.12 et Qt 6 multi-OS.

### Exemple transactionnel

```python
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.events import EventStudio
from sporebound.event_branch_builder import branch_recipe

content, project = reference_project()
studio = EventStudio(AuthoringSession.new(content, project))
studio.create_choice_fork(
    MISSION, origin_event_id="decision_origin", origin_cell=[2, 3],
    scene_id="decision_jeanne", title="Quelle voie ?",
    text="Jeanne doit choisir.", speaker="Jeanne",
    branches=branch_recipe(
        first_id="combat", first_label="Se battre",
        first_event="decision_combat", first_action="hazard",
        first_text="Combattre", first_amount=5,
        second_id="parler", second_label="Négocier",
        second_event="decision_parler", second_action="message",
        second_text="Tentons de discuter", second_amount=0),
    reunion_event_id="decision_suite", reunion_message="Les chemins convergent")
diagnostic = studio.branch_qa(MISSION)
debug = studio.start_debug(MISSION, "decision_origin")
debug.breakpoint("decision_suite")
report = debug.resume()
assert report["report"]["isolated"]
assert report["report"]["replay_verified"] is None
```

### Limites restantes

Le graphe Qt ne gère pas encore le câblage par glisser-déposer, la palette de commandes reste partielle, les pages/états ne sont pas livrés, et les marqueurs de carte utilisent encore une projection schématique distincte du viewport GPU partagé. La chaîne de replay certifiée **Studio → Player → sauvegarde → chargement → replay** reste un gate ouvert. Aucune confusion entre aperçu de bataille synthétique et certification de partie réelle n'est autorisée.

## R9.C — Actions natives, graphe éditable et viewport ISO

La troisième tranche dépend explicitement de R9.B : la branche R9.C est dérivée de `feat/drawtemp5-r9b-branches-debugger`, non de `master`, puisque la PR R9.B peut encore être en revue.

### Commandes réellement exécutables (R9.3)

- **Actions du moteur tactique :** `message`, `hazard`, `status`, `despawn`, `spawn`, `wave` et `queue_wave`. Onglet **Commandes** → sélectionner un type → Ajouter / Modifier. Les formulaires sont typés (identifiant d'acteur, archétype, position, équipe, durée). Le résultat passe par `event_composer.action` et `Content` ; aucune action inconnue ni code utilisateur brut n'est injecté.
- **Cinématiques déclenchées par événement :** onglet **Commandes** → Pistes de présentation → Ajouter une piste. Crée ou enrichit une `GameProject.cinematics` existante, dont le trigger est `tactical_event: mission/event`. Les pistes compatibles avec le Player sont `dialogue`, `sound`, `actor`, `camera`, `background`, `fade`, `fx`. Leurs paramètres passent par `cinematics.event_template` et le validateur de `GameProject`.
- **Variables/objets/économie :** onglet **Narration** → Ajouter effet de choix. Les opérations natives `set_flag`, `add_flag`, `grant_item`, `equip_hero`, `gold`, `recruit_hero`, `unlock_mission` ne s'exécutent **qu'après un choix StoryBook valide**, pas comme action tactique autonome. Leur source de vérité est `GameProject.story.scenes[].choices[].effects` ; `story_authoring.add_effect` vérifie chaque référence.

Ce catalogue couvre les opérations déjà définies dans les registres du moteur et dans StoryBook. **Une commande de mouvement arbitraire en pleine bataille, un branchement conditionnel de scripts utilisateur ou un inventaire modifié directement par un trigger tactique ne sont pas des capacités du moteur actuel : elles ne sont pas inventées dans cette PR.**

### Graphe éditable (R9.6)

L'onglet Graphe affiche un nœud par trigger, avec condition, nombre et types d'actions. Les nœuds peuvent être déplacés pour composer la vue (positions locales non sérialisées). En cochant « Relier deux événements par clic », sélectionner d'abord le **prédécesseur**, puis le **successeur** ; le choix ET/OU détermine `after` ou `after_any`. Les cycles, références cassées et doublons sont refusés transactionnellement par le validateur de Content.

### Viewport R3 commun (R9.8)

La carte schématique `QGraphicsView` est remplacée par un `QQuickWidget` affichant **le vrai `IsoViewport.qml`** de R3/R5/R12. La scène est construite par `scene_from_mission`, sans renderer parallèle. La propriété opt-in `renderer.eventMarkers` ajoute des symboles déclencheur/effet via la même projection isométrique et les hauteurs des tiles ; les mouvements caméra et zoom réutilisent l'état du même contrôleur. Cliquer une case de trigger sélectionne son événement. Quand le Player utilise le composant sans l'option `showEventMarkers`, ces symboles ne sont pas affichés.

### Validation

```bash
python -m pip install ".[qt6]"
python -m unittest tests_standalone.test_drawtemp5_r9c -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.studio.event_studio --smoke
```

Les tests R9.C couvrent le catalogue natif, la validation et l'atomicité, les pistes liées, les effets StoryBook, la projection avec hauteur et le démarrage Qt. La CI globale doit aussi confirmer l'absence de régression du Player.

**Reste ouvert :** commandes tactiques non prises en charge par le moteur (mouvement arbitraire, effets d'inventaire directement sur un trigger), édition cinématique avancée déléguée à R11, position du graphe persistante et édition de ses arêtes par glisser-déposer, certification GPU réelle et replay complet du gate R9.12. R9.C est une tranche de livraison, pas le statut « R9 terminé ».

## R9.D — Event Pages & States : moteur et Studio Qt 6

### Contrat canonique, rétrocompatibilité et sauvegarde

Les missions 5.0 continuent d'utiliser `Content.missions[].triggers`. Une page est une variante **du même identifiant d'événement**, pas un deuxième trigger. Les anciens triggers, sans `pages`, `enabled` ni `repeat`, gardent le comportement « une fois » et **leur ruleset / manifeste de replay d'origine**.

- **Page `base`** : condition/actions existantes du trigger, priorité fixe `0`, activée et non répétable par défaut.
- **Pages supplémentaires** : `pages: [{id, priority, condition, actions, enabled?, repeat?, cooldown_ticks?, when?}]`, 8 maximum, priorité entière de -100 à +100. Chaque page utilise les prédicats et actions de règles déjà déclarés dans `Content`.
- **Choix de la page active** : parmi les pages activées dont la condition est vraie, priorité décroissante, puis ordre défini dans la mission. Le plus haut rang prime, même si cette page a déjà été déclenchée (pas de cascade vers une page inférieure consommée).
- **Désactivation/activation** : l'action opt-in `event_state` sur un trigger pointe vers l'ID d'événement cible, et éventuellement l'ID de page. Elle enregistre `{kind:"event_state", event, page, enabled}` dans le journal tactique. Le dernier changement applicable détermine l'état courant, y compris après sauvegarde/rejeu. La création de cette action est accessible dans la palette visuelle.
- **Répétition bornée** : `repeat=true` et `cooldown_ticks=1..10000`. Une page répétable ne s'exécute jamais deux fois au même tick. Les répétitions sont tracées via les occurrences `trigger` du journal, sans compteur mutable séparé. `battle.fired` conserve l'identité historique du premier déclenchement pour les dépendances des autres triggers.
- **Priorité de compatibilité** : `authored_rules_for_document` n'enregistre `event_state` que dans les rulesets opt-in. Le manifeste des anciens jeux demeure identique ; un replay utilisant une autre version de règles échoue explicitement au gate de compatibilité.

Les états « persistants » de R9.D concernent **la bataille en cours et sa sauvegarde/reprise Player/GameSession**. La propagation vers une autre mission/campagne est le travail distinct de R9.E.

### Utilisation sans JSON

L'atelier Qt dispose désormais de l'onglet **Pages & états** : sélection d'une page, priorité, activation, répétition, cooldown, condition, liste d'actions, création/suppression et sauvegarde. Ajouter la commande `event_state` à un trigger pour changer la page d'un autre événement (ou toutes les pages de cet événement si `page` est vide).

Exemple du service headless :

```python
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project, MISSION
from drawtemp.studio.events import EventStudio
from sporebound.event_composer import action, condition

content, project = reference_project()
studio = EventStudio(AuthoringSession.new(content, project))
studio.create(MISSION, "gate_scene", condition("interact", object_id="lever"),
              [action("message", text="Jeanne touche le levier.")])
studio.add_page(
    MISSION, "gate_scene", page_id="gate_open", priority=50, enabled=False,
    condition=condition("tick", tick=0),
    actions=[action("message", text="Le passage est ouvert.")])
studio.add_tactical_command(
    MISSION, "gate_scene", "event_state",
    {"event": "gate_scene", "page": "gate_open", "enabled": True})
studio.undo()  # tous les fichiers et variantes reviennent à la révision précédente
```

Note : l'activation dans le code d'exemple est attachée au **même trigger** et sera visible au prochain passage du dispatcher. Le Player ne fabrique pas de nouvelles variables de script.

### Vérification R9.D

```bash
python -m unittest tests_standalone.test_drawtemp5_r9d -v
python -m unittest tests_standalone.test_drawtemp5_r9 tests_standalone.test_drawtemp5_r9b tests_standalone.test_drawtemp5_r9c -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.studio.event_studio --smoke
```

Critères de validation : priorité et égalité d'ordre ; page désactivée ignorée ; action d'état prise en compte par le vrai dispatcher ; pas de répétition dans un même tick ; reconstruction des occurrences et des valeurs après `Battle.replay` et `GameSession.from_recording` ; Undo/Redo et rejet d'une référence/condition invalide. Une page non rejouée après une victoire doit rester inactive ; aucun accès direct aux structures internes du Player n'est permis depuis le Studio.

### Gates encore ouverts

R9.E (état/campagne intermissions), R9.F/R9.12 (parcours certifié complet avec sauvegarde/reprise sur toutes les plateformes), UI de comparaison et prévisualisation conditionnelle avancées, captures GPU réelles et certification artistique du parcours Jeanne. Cette tranche ne doit pas être marquée « terminé » sur la seule présence des API.
