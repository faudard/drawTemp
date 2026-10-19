# R24.E — Hooks de scénario contrôlés (scripting v1, sans exécution tierce)

**Statut : tranche de code en PR empilée après R24.D (#341), R24.C (#328), R24.B (#316), R24.A (#296).** R24.5 est P2 et cette tranche n'implémente pas un interpréteur Python/Lua, des hooks arbitraires ou la certification 6.0.

## Décision d'architecture

Le système R24.E est un **compilateur déclaratif borné** pour hooks narratifs préexistants, pas une VM. Le créateur déclare des conditions de déclenchement `story.choice` (scène et option) et une série d'effets narratifs **déjà pris en charge par `sporebound.narrative.StoryBook.choose`**. L'import traduit ces effets en modifications d'une **paire Content/GameProject canonique** via la même `AuthoringSession.preview_project` / `apply` que le Studio. Il n'y a aucun `eval`, `exec`, import de module tierce partie, appel réseau, fichier tiers chargé dans le Player ni nouveauté dans les commandes de Battle.

Les choix compilés continuent à être validés par `GameProject.validate` / `validate_story` (limite native de 20 effets par choix) et à être exécutés par GameSession/StoryBook avec le déterminisme, les sauvegardes, les hachages et les replays existants. La seule extension stockée est un reçu de compilation *inerte* dans le namespace choisi (`GameProject.extensions.<namespace>`), qui inclut source SHA-256, permissions, ID du hook et hash des actions injectées. Le reçu entre dans le digest du projet, donc une sauvegarde issue d'un jeu compilé ne se recharge pas silencieusement dans une version différente.

## Format strict

Un JSON comprend les champs exacts `schema_version: 1`, `id`, `namespace` reverse-domain, `sdk_api: [1,0]`, `permissions` et `hooks` (1..16). Chaque hook a `id`, `trigger: story.choice`, `scene`, `choice`, `effects` (1..8). L'exemple physique `examples/scripts/asterion-scan.json` cible le briefing du second jeu Asterion.

Seuls les effets natifs suivants sont autorisés :

| Effet natif | Permission nécessaire | Exécution |
|---|---|---|
| `set_flag` / `add_flag` | `story.flags.write` | StoryBook modifie les story_flags de Campaign |
| `unlock_mission` | `campaign.missions.unlock` | StoryBook ajoute une mission validée aux débloquées |
| `gold` | `campaign.gold.write` | StoryBook modifie l'or avec bornes natives |

Chaque permission déclarée doit correspondre **exactement** à un effet effectivement présent. Les permissions non nécessaires ou absentes, `python`, `script`, `lua`, `network`, `filesystem`, des effets inconnus, des champs supplémentaires, un hook différent de `story.choice`, des IDs/chemins dangereux, des références inexistantes et une API plus récente sont refusés.

Limites : 16 hooks, 8 effets/hook, manifeste 64 KiB, profondeur JSON et types dérivés des effets autorisés, 20 effets par choix après compilation. Chaque hook vise un couple scène/choix unique dans le manifeste ; un autre script R24.E n'a pas le droit de posséder le même couple. Le namespace ne peut pas remplacer des données existantes.

## Utilisation SDK (headless)

```python
import json
from pathlib import Path
from drawtemp.sdk import AuthoringSession, install_script, read_script_manifest

session = AuthoringSession.open('game.json')
manifest = read_script_manifest('examples/scripts/asterion-scan.json')
# La liste ne doit être transmise qu'après consentement explicite du créateur.
install_script(session, manifest, granted_permissions=manifest['permissions'],
               expected_revision=session.revision)
session.save()  # écriture explicite des documents canoniques
```

`preview_script` retourne le plan transactionnel sans modification ni accès aux fichiers du projet. `install_script` applique ce plan (1 entrée Undo/Redo). En cas de refus d'autorisation, de scène/choix manquant, d'effet invalide, de namespace occupé ou de prévisualisation obsolète, la session reste intacte.

## Utilisation dans Studio Qt

**Outils → Hooks contrôlés → Importer des hooks JSON…** : le Studio lit le manifeste local, affiche les permissions demandées et présente le refus par défaut. Un « Oui » compile le hook dans la session en cours. La modification est éditable, annulable/rétablissable et ensuite persistée par Enregistrer. Le panneau Diagnostics indique les imports. Aucun script n'est auto-chargé au démarrage. Les permissions donnent droit à une **compilation ponctuelle** : elles ne sont pas persistées et ne servent pas d'autorisations d'exécution au Player. Pour annuler après sauvegarde, éditer le projet avec des migrations explicites ; R24.E ne fournit pas encore de désinstallation de hook compilé.

## Gate déterministe

L'exemple Asterion ajoute à son premier choix deux effets : `signal_scan = true` et `gold += 15`. Les tests vérifient la présence des effets pendant une vraie transition StoryBook/GameSession, la sauvegarde/relecture `Simulation`, `verify_recording`, `verify_sequence`, `certify_trace` avec trois seeds et contrôle des hachages RNG/CT du premier combat. Une sauvegarde faite avec le hook compilé est rejetée si chargée avec le GameProject original.

Tests recommandés :

```bash
python -m unittest tests_standalone.test_drawtemp5_r24e tests_standalone.test_drawtemp5_r24d tests_standalone.test_drawtemp5_r24a
```

Les workflows R24.E font une matrice Python 3.10/3.12 Linux et Python 3.12 Windows/macOS ainsi que Qt offscreen. Aucun résultat ne constitue une preuve d'exécution GPU, d'une vraie release autonome ou d'un audit de code plugin exécuté : il **n'y a pas** de code plugin exécuté.

## Non inclus et suite

R24.5 ne couvre ici que les hooks narratifs **précompilés**. Un futur ajout de hooks de combat, tick ou post-battle devrait passer par de nouvelles commandes natives explicitement journalisées/rejouables avec budgets CPU et politique de capacités, ou être refusé. La conception R24.F pourra traiter R24.6/7 (scale et simulations), puis R24.G R24.8 (diff sémantique) et R24.10 sécurité de distribution. Les travaux de certification R24.12 restent ouverts jusqu'aux preuves hardware/légales/clean-machine et aux gates des PR empilées sur master.
