# R37.C — Behavior Trees : moteur, éditeur Qt et débogage pas-à-pas

**Statut : implémentation en PR #371, validation de CI à confirmer ; le gate R37 final reste ouvert.**

## Fonctionnalités réellement implémentées

- **R37.2** : schéma d'arbre v1, nœuds typés `sequence`, `selector`, `condition`, `action` et `decorator` (`invert`). Enfants ordonnés selon l'auteur ; validation de tous les liens, racine unique, un parent par nœud, absence de cycles, références strictement déclaratives.
- **R37.8** : au plus 64 nœuds, 16 enfants/composite, profondeur 16 ; toutes les décisions sont évaluées sur les `facts` et `blackboard` d'un unique contexte canonique. Aucun accès fichier, Python arbitraire, appel réseau, moteur alternatif ou boucle non bornée.
- **R37.9 (fondation)** : journal d'évaluation post-ordre (`node_id`, type, statut, cause), digest d'entrée et de rapport, curseur de trace, breakpoints et continuation lecture seule. Le debug **ne relance pas** le jeu.
- **Éditeur Qt** : Outils → Advanced AI Studio R37. Vue arborescente, création de conditions/actions/composites, inversion, suppression, réordonnancement, modification des feuilles, diagnostic et lecture pas à pas. Appliquer réalise **une transaction `AuthoringSession`** ; Annuler/Rétablir utilisent l'historique R1.
- **Intégration** : chaque agent dans `GameProject.extensions['org.drawtemp.advancedai']` contient **soit `policies` R37.A/B, soit `tree` R37.C**. La sélection est explicite ; R37.B reste rétrocompatible. `GameSession.ai_decision_preview` choisit l'évaluateur correspondant sans exécuter l'action.

## Sémantique des nœuds

| Nœud | Comportement déterministe |
|---|---|
| `condition` | Compare le fait courant à `equals` avec égalité de type stricte ; renvoie `success` ou `failure` |
| `action` | Propose une action et renvoie `running` ; ne prétend pas l'avoir exécutée |
| `sequence` | Évalue les enfants dans l'ordre, s'arrête au premier `failure` ou `running` |
| `selector` | Évalue les enfants dans l'ordre, s'arrête au premier `success` ou `running` |
| `decorator:invert` | Inverse `success`/`failure`, laisse `running` inchangé |

Une action qui n'a jamais été atteinte donne le `fallback=wait`. Le résultat reste une **proposition** : le Player doit toujours passer par les règles canoniques avant exécution. Les scripts arbitraires et la mutation des ressources pendant l'évaluation restent interdits.

## Exemple déclaratif

```json
{
  "schema_version": 1, "root": "root",
  "nodes": [
    {"id": "root", "kind": "selector", "children": ["hunt", "patrol"]},
    {"id": "hunt", "kind": "sequence", "children": ["see_enemy", "chase"]},
    {"id": "see_enemy", "kind": "condition",
     "fact": "enemy_visible", "equals": true},
    {"id": "chase", "kind": "action", "action": "chase"},
    {"id": "patrol", "kind": "action", "action": "patrol"}
  ]
}
```

Ces faits sont un **exemple de test** ; `enemy_visible` n'est pas affirmé comme une perception LOS réelle. En mode CT, R37.B expose `has_opponents`, pas un champ de vision. La perception LOS/bruit et la navigation arrivent en R37.D.

## Édition et diagnostic

L'éditeur accepte une session R1 et propose un brouillon privé. Il lit l'extension R37 et remplace seulement la définition de l'agent choisi. Les autres agents, missions, événements et assets restent inchangés. Toute configuration invalide est refusée avant `Apply`. La révision R1 protège contre les brouillons obsolètes.

Lorsque `game_session` est fournie, le diagnostic utilise les faits réels et le blackboard canonique. Sinon, l'éditeur offre un **contexte JSON explicitement de démonstration** ; cela n'est ni une preuve de gameplay, ni un état de perception inventé.

## Gates de vérification

```sh
python -m unittest tests_standalone.test_r37_behavior_tree -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_r37_behavior_tree_qt -v
python -m unittest tests_standalone.test_r37_ai_decision tests_standalone.test_r37_ai_session -v
```

La workflow `r37-ai-decision.yml` ajoute la matrice Linux/Windows/macOS headless et un smoke Qt offscreen. Le moteur ne change ni `Battle.execute`, ni `sporebound.ai`, ni les sauvegardes des projets sans opt-in. La CI, l'UX Qt réellement observée, les tests GPU, les performances à l'échelle et le vertical slice boss doivent encore être qualifiés.

## Suites

- **R37.D** : perceptions réelles (cônes/LOS/bruit/mémoire) et adaptateurs de navigation existants ; coordination et phases de boss sans doubles règles.
- **R37.E** : traces liées aux replays effectivement exécutés, campagnes de régression Jeanne/top-down/platformer, AI Debugger multi-acteurs et boss créé/joué depuis le Studio.
