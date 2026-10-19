# R24.G — Collaboration & VCS sémantique Content/GameProject

**Périmètre livré :** comparaison de documents versionnés, prévisualisation et application transactionnelle d'une fusion à trois versions *dans l'éditeur canonique*, et commande CLI read-only utilisable avec des worktrees Git. Cette tranche ne promet pas de CRDT, de serveur collaboratif ni d'intégration automatique au serveur GitHub.

## 1. Documents canoniques, pas de fork du moteur

Content v1 et GameProject v1 restent les seules sources persistées. Le service headless `drawtemp.sdk.r24g_semantic_vcs` appelle toujours `sporebound.studio_transaction.validate_pair` pour **chaque** entrée et pour le résultat fusionné. L'application passe exclusivement par `AuthoringSession.preview_pair` puis `AuthoringSession.apply`, avec une seule entrée dans l'historique Undo/Redo. `AuthoringSession.save()` continue de vérifier les empreintes des deux fichiers et son journal de récupération existant.

Les documents entrants sont des snapshots **base** (véritable ancêtre commun fourni par l'utilisateur), **ours** (état de l'éditeur local), **theirs** (branche externe). R24.G ne récupère pas automatiquement les ancêtres Git ni ne garantit que le chemin nommé « base » est authentiquement l'ancêtre commun : celui-ci doit être fourni correctement. Ce contrat est utile hors Git (copie de projets, collaboration hors ligne) et fonctionne sans client réseau.

## 2. Diff sémantique

`semantic_diff(before, after)` produit un rapport stable à chemins d'identité, avec `op` et deux empreintes SHA-256 (sans inclure le JSON brut des valeurs). Le diff est appliqué après normalisation des deux documents par les validateurs réels.

| Contenu | Chemin sémantique |
|---|---|
| Mission | `/content/missions[id=mission_1]/name` |
| Personnage de mission | `/content/missions[id=mission_1]/units[id=hero]/hp` |
| Case de carte | `/content/missions[id=mission_1]/board/tiles[pos=2,4]/surface` |
| Dialogue | `/project/story/scenes[id=arrival]/choices[id=enter]/label` |
| Extension | `/project/extensions/org.example.quest/data/...` |

Collections identifiées : compétences, missions, unités, objets, triggers, campagnes, sièges, cinématiques, scènes, choix (`id`) et tuiles de terrain (`pos`). Les autres listes (ex. effets de compétence, chronologies, conditions composites) sont **atomiques** : deux edits simultanés de ces listes sont considérés comme un conflit si leurs valeurs diffèrent. Les changements d'ordre concurrents sur les listes identifiées ne sont pas inventés ou ignorés silencieusement.

## 3. Trois versions et conflits

`preview_three_way(base, ours, theirs)` compare les changements issus du même ancêtre puis fusionne les changements indépendants. Les conflits **refusés** incluent : modification du même champ, suppression vs modification, deux créations divergentes avec la même identité, réordonnancement incompatible, échec de validation croisée Content/GameProject. Un projet fusionné qui référence une mission supprimée dans l'autre branche échoue lors de la validation canonique.

Pour les tableaux à identités, la fusion préserve l'ordre des entités existantes et ajoute les nouvelles identités dans un ordre stable, mais ne résout pas automatiquement des changements d'ordre concurrents. Les dictionnaires optionnels comme `extensions` peuvent recevoir des *namespaces* indépendants créés sur les deux branches ; le même namespace divergent reste un conflit.

Les rapports indiquent les chemins, causes et digests du base/ours/theirs. Ils ne masquent ni ne règlent un conflit par une priorité implicite « ours » ou « theirs ». Une fusion conflictuelle ne retourne jamais un état committable.

## 4. SDK : prévisualisation et validation explicites

```python
from drawtemp.sdk import AuthoringSession, read_pair, preview_merge, apply_merge

editor = AuthoringSession.open('game.json')
ancestor = read_pair('snapshots/base.json')
theirs = read_pair('snapshots/theirs.json')
review = preview_merge(editor, ancestor, theirs)
if review.can_apply:
    transition = apply_merge(editor, review)   # une transaction Undo/Redo
    editor.save()                               # sauvegarde séparée et explicite
else:
    print(review.report['conflicts'])
```

`preview_merge()` n'altère pas l'éditeur et attache le plan à la révision et à la session actuelle. `apply_merge` utilise la protection contre les changements intervenus entre-temps (même après Undo/Redo) et contre l'application d'un plan provenant d'une autre session. Le rapport est séparé du plan immutable de l'éditeur. Si le projet courant comprend déjà le résultat fusionné, `already_current=True` et aucun commit inutile n'est proposé.

## 5. Studio Qt : confirmation refusée par défaut

**Outils → Collaboration / VCS → Comparer et fusionner 3 versions…**. Deux fichiers `Content JSON` sont sélectionnés, le premier pour l'ancêtre commun et le second pour la branche externe. Le Studio utilise son `AuthoringSession` en cours comme *ours*. Pour chaque entrée, le `GameProject` est lu depuis le fichier jumeau `nom.game.json`, avec validation et protections contre symlinks, JSON à clés dupliquées, fichiers trop grands et changements externes pendant la lecture.

Une synthèse indique les changements locaux/distants et les conflits. S'il y a conflit, aucune application n'est possible, et jusqu'à 20 chemins/codes de conflit sont affichés. Si le merge est valide et non redondant, un dialogue demande le consentement explicite, **No par défaut**. L'application rafraîchit le Studio et peut être annulée/rétablie. L'écriture sur disque exige un Enregistrer ultérieur.

## 6. CLI pour worktrees / CI

```bash
# Organiser base/, ours/, theirs/ avec Content JSON + fichier jumeau *.game.json
python -m drawtemp.sdk.r24g_cli --mode diff --base base/game.json --ours ours/game.json --report diff.json
python -m drawtemp.sdk.r24g_cli --mode merge --base base/game.json --ours ours/game.json --theirs theirs/game.json --report review.json
```

Retour 0 : diff terminé ou fusion possible. Retour 2 : conflits attendus. Retour 1 : fichiers invalides, erreur d'accès ou sortie préexistante. Un rapport JSON existant n'est jamais écrasé ; un chemin source ou `.game.json` ne peut pas devenir la sortie. La CLI reste **read-only** pour les Content/GameProject : elle n'exécute pas Git, ne force pas de fusion et n'écrit jamais les documents fusionnés. Le JSON de revue contient seulement les digests et les chemins sémantiques, pas le contenu complet des fichiers.

## 7. Portes qualité et limites

```bash
python -m unittest tests_standalone.test_drawtemp5_r24g tests_standalone.test_drawtemp5_r24a
```

La CI R24.G exécute les tests unitaires sous Linux Python 3.10/3.12, Windows et macOS 3.12, puis un smoke Qt offscreen sur Ubuntu. Scénarios couverts : edits indépendants sur la même mission, namespaces concurrents distincts ou identiques, édition vs suppression d'une tuile, reorder concurrent, champs incompatibles, révisions obsolètes, plan d'un autre éditeur, sauvegarde/rechargement, source non modifiée, lectures sécurisées et codes retour CLI.

**Non inclus :** résolution interactive ligne par ligne des conflits, auto-réparation des références croisées, Git fetch/push/rebase, diff binaire des assets, verrouillage multi-auteurs temps réel, serveur cloud ou approbations asynchrones. Les workflows de validation des artefacts et la certification native/GPU R24.12 restent des gates séparés.
