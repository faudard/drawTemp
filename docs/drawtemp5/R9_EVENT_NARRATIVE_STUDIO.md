# DrawTemp 5.0 — R9 Event & Narrative Studio (première tranche)

> **Périmètre :** branche `feat/drawtemp5-r9-event-narrative-studio`. Ce document décrit l'implémentation effective, pas une certification globale R9. Les dépendances R2/R5 doivent être intégrées avant clôture du jalon complet.

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
| R9.4 Condition Builder | **Initial** | Ajout de feuilles typées en ET/OU/NON, édition d'arbre possible via API headless |
| R9.5 Pages/States | **À compléter** | Délais/expiration et références persistantes existantes ; pas de nouveau système de pages |
| R9.6 Visual Graph | **Partiel** | Graphe DAG issu des triggers canoniques, création/suppression des dépendances ET/OU par formulaire, pas encore de manipulation directe des nœuds |
| R9.7 Timeline | **Partiel** | Délais et expiration en ticks ; activations, annulations et édition avancée exposées par le service |
| R9.8 Map Preview | **Partiel** | Repères 2D pour interaction/entrée/danger, pas encore la surimpression dans le viewport GPU R5 |
| R9.9 Debugger | **Partiel** | Simulation isolée et trace du moteur réel ; points d'arrêt déjà disponibles dans le moteur, pas encore exposés dans l'interface |
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
