# R48.A — Project Collaboration & Versioning: contrats Core

**Statut : code en PR, non certifié.** Ce premier incrément R48 met en place
une collaboration locale *headless* sur les documents canoniques
**Content/GameProject**. Il ne livre ni l'interface Qt R48.B, ni une
certification deux-auteurs R48.C, ni une garantie d'authenticité cryptographique.

## Contrats

- `ProjectRevision` : snapshot validé et immuable (charge JSON en octets
  canoniques), SHA-256 stable, `schema=1`, auteur descriptif et un ou deux
  parents SHA-256 déclarés. `make_revision` refuse les parents invalides,
  documents non validables. Une branche inchangée peut conserver le digest
  de son parent; le champ auteur n'est pas signé.
- `CollaborationController.compare(base, local, incoming)` : exige que
  les deux branches déclarent **exactement** le digest du parent `base`,
  vérifie que le local correspond au snapshot actif d'`AuthoringSession`
  et fournit des conflits sans écrire sur disque. La parenté est **déclarative**,
  elle ne remplace pas la vérification de l'ancêtre Git de R30.D.
- `CollaborationController.apply(review, decisions)` : décisions obligatoires
  `local` ou `incoming` pour chaque conflit, revalidation des snapshots,
  protection contre changements de révision et cycles edit/undo ABA,
  validation du couple puis un seul `preview_pair/apply` du Studio.
  Aucun `save()` implicite, aucune mutation Git ni du runtime.
- `semantic_review(..., typed_sequences=True)` : réutilise l'algorithme R30
  pour les missions et étend les séquences d'objets à identifiant stable :
  `project.story.scenes`, `project.campaigns`, `project.cinematics`.
  Les champs indépendants d'un même objet peuvent fusionner; les ajouts
  *append-only* de deux auteurs sont combinés de manière déterministe,
  local puis distant. Suppression, insertion en milieu et réordonnancement
  concurrents restent des conflits de liste entière à trancher explicitement.
  Les séquences d'actions, unités, choix, triggers et listes non reconnues
  conservent le traitement atomique prudent de R30.
- Le mode `typed_sequences=False` reste **le comportement par défaut** des
  APIs R30 pour préserver les scénarios existants.

## Utilisation headless

```python
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import CollaborationController, make_revision

# content0/project0 : paire canonique commune de départ
base = make_revision(content0, project0, author="base")
local_session = AuthoringSession.new(content0, project0)
# ... modifications d'Alice dans local_session via preview/apply ...
snap = local_session.snapshot().to_dict()
local = make_revision(snap["content"], snap["project"],
                      author="alice", parents=(base.digest,))
# ... Bob a modifié indépendamment les mêmes documents de départ ...
incoming = make_revision(content_bob, project_bob,
                         author="bob", parents=(base.digest,))

controller = CollaborationController(local_session)
review = controller.compare(base, local, incoming)
# Une UI propose une décision pour *chaque* review.conflicts :
choices = {conflict.path: "incoming" for conflict in review.conflicts}
transition = controller.apply(review, choices)
# Le Studio conserve l'Undo/Redo ; save reste un geste explicite.
```

## Tests et limites de certification

```bash
python -m unittest tests_standalone.test_drawtemp_r48a_collaboration -v
python -m unittest tests_standalone.test_drawtemp_r30_creator -v
python -m unittest tests_standalone.test_drawtemp_r30c_review -v
python -m unittest tests_standalone.test_drawtemp_r30d_git -v
```

Les tests R48.A couvrent merges indépendants, scènes, ajouts concurrents,
résolutions manuelles, parents divergents, intégrité SHA-256, validation
canonique, ancien mode R30, ABA et transaction Undo. La CI doit confirmer
leurs résultats sur le SHA de la PR. Pas de claim GPU/Qt onscreen/tri-OS.

## Incrément R48.A2 : refactor transactionnel et audit local

Le code de ce lot complète R48.A1 sans créer de nouvelle source de vérité.

- `drawtemp.sdk.project_refactor.preview_rename(session, resource, new_id)`
  réutilise les planificateurs **R2.7** existants :
  `scene:id`, `campaign:id`, `map_actor:mission/id` et
  `map_object:mission/id`. Le rapport détaché expose les chemins d'impact
  et les digests avant/après. Pas de substitution de texte non typée :
  références opaques, IDs invalides ou collisions sont refusés.
- `apply_rename(session, review)` vérifie la révision du Studio, les digests
  des deux versions et le plan d'auteur lié à la session. L'opération est
  **un unique Undo** ; un edit suivi d'Undo (ABA) invalide la prévisualisation.
- Le changement d'ID d'une campagne ne peut être prévisualisé que depuis
  un Studio associé à une destination sauvegardée et non modifiée de façon
  externe ; présence de slots de sauvegarde dans l'ancien namespace = refus
  explicite. **Aucune migration de sauvegardes existantes**.
- `drawtemp.sdk.project_audit.LocalAuditLog` est un fichier JSONL local
  **facultatif**, append-only, numéroté, chaîné par SHA-256 et limité à
  8 Mio. Le verrou O_EXCL et le HEAD attendu refusent les écritures
  concurrentes par cette API; un journal tronqué, corrompu ou modifié
  bloque toute nouvelle entrée. Les entrées ne contiennent que la
  provenance, les noms d'opérations et les digests.
- **Limite transactionnelle :** le Studio et le journal sont deux supports.
  Une application validée peut précéder une panne d'append ; **on ne peut pas
  prétendre à une atomicité inter-supports ni à un audit exhaustif**.
  Le journal n'est ni un format de sauvegarde, ni une signature, ni un
  autorisateur de rollback. Aucun historique Git n'est modifié.

```python
from drawtemp.sdk.project_refactor import preview_rename, apply_rename
from drawtemp.sdk.project_audit import LocalAuditLog

review = preview_rename(session, "scene:arrival", "arrival_new")
# Afficher review.affected_paths dans la UI avant confirmation.
transition = apply_rename(session, review)
audit = LocalAuditLog("collaboration.audit.jsonl")
status = audit.inspect()
audit.append(expected_head=status["head"], actor="alice",
             operation="rename", resource=review.resource,
             before=review.before_digest, after=review.after_digest)
# Le save() Content/GameProject et la publication audit restent explicites.
```

Régressions R48.A2 :

```bash
python -m unittest tests_standalone.test_drawtemp_r48a2_refactor_audit -v
```

**Le rebase automatique, l'UX de revue complète avec annotations et le
gate R48.C restent ouverts.** La CI du SHA de la branche doit être
validée avant tout statut « prêt à fusionner ».

## R48.A3 : DAG local, historique multi-générations et rapprochement d'audit

Le nouveau `drawtemp/sdk/project_history.py` définit un `RevisionGraph`
**borné à 2 048 nœuds**. Chaque nœud contient une `ProjectRevision`
canonique validée et un identifiant de **nœud** distinct du SHA-256 du
**contenu** ; deux branches avec les mêmes documents ne sont donc pas
confondues. Les parents doivent être présents, déclarés et validés avant
l'ajout ; cet index est **local et en mémoire**, pas un dépôt Git, une
signature d'auteur, ni une base de données de sauvegarde.

`HistoryReviewController.compare_history(local_id, incoming_id,
base_id=None)` cherche les ancêtres réellement enregistrés dans le DAG.
Un seul ancêtre commun maximal est sélectionné automatiquement ; aucun
ancêtre donne `unrelated_history`. Plusieurs bases maximales (historique
entrecroisé) donnent `ambiguous_base`, sauf si l'auteur choisit
explicitement **une base maximale**. L'ancien contrôleur R48.A1 conserve sa
règle de parent immédiat; le contrôleur historique utilise le même moteur
R30 de merge typé et la même transaction R1/Undo. Le DAG ne prouve pas
l'ascendance **Git** : utiliser l'adaptateur R30.D pour cela.

Exemple headless :

```python
from drawtemp.sdk.collaboration import make_revision
from drawtemp.sdk.project_history import RevisionGraph, HistoryReviewController

graph = RevisionGraph()
base = make_revision(content0, project0, author="system")
base_node = graph.add(base, label="root")
alice = make_revision(content_alice, project_alice, author="alice",
                      parents=(base.digest,))
alice_node = graph.add(alice, parents=(base_node.node_id,), label="A1")
bob = make_revision(content_bob, project_bob, author="bob",
                    parents=(base.digest,))
bob_node = graph.add(bob, parents=(base_node.node_id,), label="B1")
controller = HistoryReviewController(local_session, graph)
review = controller.compare_history(alice_node.node_id, bob_node.node_id)
# Après revue interactive de chaque conflit :
transition = controller.apply(review, decisions)
```

Le module `drawtemp/sdk/audit_reconciliation.py` rapproche les lignes
d'audit avec les digests du Studio et une liste **explicite** de
`ProjectRevision` historiques. Il expose `empty`, `aligned`,
`partial_evidence` et `drift`, ainsi que les numéros d'entrées dont les
preuves manquent ou dont les liens ne sont pas continus. Le paramètre
`expected_head` est facultatif et peut déceler un journal supprimé ou
remplacé depuis une inspection antérieure. Il ne modifie jamais le contenu,
ne récupère pas automatiquement les sauvegardes et **ne transforme pas un
audit en preuve d'exhaustivité**. Une chaîne valide intégralement tronquée
reste indétectable sans HEAD conservé ailleurs.

```python
from drawtemp.sdk.audit_reconciliation import reconcile_audit

head = audit.inspect()["head"]  # conserver cette empreinte pour la revue
status = reconcile_audit(audit, local_session, known_revisions=(base, alice),
                         expected_head=head)
# status.state est un diagnostic, jamais une autorisation d'écrasement.
```

### Limites du lot

Les `parents` des révisions sont déclaratifs, sans vérification d'identité
ou signature. Deux commits dont les documents sont identiques peuvent avoir
des IDs de nœuds différents ; l'ancienne API `make_revision` refuse encore
deux parents ayant exactement le même digest de **contenu**, même si les
nœuds du graphe diffèrent. Un rebase qui réécrit les documents et la
publication durable/synchronisée des nœuds ne sont pas implémentés : R48.A3
offre pour l'instant un **merge multi-générations révisable**, et non un
rebase automatique.

Tests :

```bash
python -m unittest tests_standalone.test_drawtemp_r48a3_history_audit -v
```

**R48.B** : l'interface Qt exploite désormais l'historique et les
commentaires ; les gates onscreen/lecteurs d'écran restent ouverts.
**R48.C** : test réel 2 auteurs/2 branches, journaux crash/recovery,
références, sauvegardes/replay et Player/export sur plusieurs OS.

## R48.B1 : Project History & Review dans le Studio Qt

Le menu **Outils → Collaboration / VCS → Historique et revue collaborative
R48…** ouvre `drawtemp/studio/r48_history_qt.py::ProjectHistoryDialog`.

L'interface conserve la même `AuthoringSession` que la fenêtre Studio,
avec une façade **Qt-independent** dans
`drawtemp/studio/r48_history_review.py` :

1. Le snapshot initial de la session est capturé comme **racine** en mémoire.
   Capturer le Studio actuel produit un nœud enfant d'un parent choisi.
2. Importer un Content JSON exige son **GameProject adjacent**, via le lecteur
   validé et épinglé par SHA de R30.C. Les sources ne sont pas modifiées.
   L'utilisateur déclare un auteur, un libellé et un parent. Cette relation
   n'est pas une preuve d'ascendance Git ni une signature.
3. Les sélecteurs « Locale », « Entrante » et « Ancêtre commun » recensent
   les révisions connues et les bases maximales. Les bases ambiguës doivent
   être choisies ; les historiques sans ancêtre commun sont refusés.
4. Les différences typées Content/GameProject, l'avant/après et les conflits
   apparaissent dans un tableau dédié. Chaque conflit exige **local** ou
   **entrant** explicitement ; changer de sélection invalide la revue.
5. La confirmation applique le candidat uniquement au Studio actif, une
   seule transaction, avec **Undo**, staleness/ABA et validation canonique
   R1. **Aucun autosave, checkout Git, push, conflit auto-résolu**.
6. Optionnel : choisir un journal d'audit local JSONL pour lire son
   statut sans écriture. Son HEAD est épinglé à l'ouverture du fichier ;
   une modification ultérieure est signalée. Cette vérification ne certifie
   ni auteur ni exhaustivité.

```bash
python -m unittest tests_standalone.test_drawtemp_r48b_history_qt -v
# Qt offscreen sur les trois OS, avec :
# QT_QPA_PLATFORM=offscreen
# QT_QUICK_BACKEND=software
# pip install ".[qt6]"
```

**Portée initiale de R48.B1 :** historique en mémoire, import manuel des
branches et revue des conflits. R48.A4 a depuis ajouté un archivage explicite
de l'index : fermer la fenêtre sans enregistrer les nouvelles révisions ne
persiste pas ces changements. Les fichiers Content/GameProject du Studio
restent inchangés tant que l'on n'a pas explicitement appliqué la revue.
Les commentaires/reviews persistants attachés aux IDs, les invitations,
la collaboration en temps réel et les tests GUI *onscreen* sont hors lot.
La suite R48.B2 doit traiter ces fonctions et les gates d'accessibilité.

## R48.B2 : fils de revue persistants et accessibilité clavier

Les annotations de revue sont **séparées** du jeu et des choix de fusion :
`drawtemp/sdk/review_notes.py::ReviewNoteStore` conserve les commentaires
dans un journal JSONL local facultatif, dont le chemin est choisi par l'auteur
dans la fenêtre R48. Chaque entrée a un numéro, un SHA-256 chaîné, le
`node_id` du snapshot, son SHA Content/GameProject, un **chemin d'ancrage
typé** et un auteur déclaré. L'ancrage pointe soit vers le projet, soit vers
une ressource existant dans le snapshot : mission, scène, campagne ou
cinématique identifiée par ID stable.

- Un clic sur une ligne de différence permet d'identifier la ressource dans
  la **version annotée choisie**. Les ressources supprimées et les IDs
  inconnus ne peuvent recevoir de nouveaux commentaires sur ce snapshot.
  Les anciennes notes historiques ne sont **jamais réattribuées** par
  substitution de texte après un renommage.
- Publier une note, répondre à un fil, résoudre et rouvrir un fil sont des
  **événements explicites** dans le journal. Les commentaires et réponses
  restent lisibles séparément ; ils n'autorisent jamais une fusion.
- Une écriture requiert le **HEAD attendu**, un verrou local exclusif et
  un contrôle intégral du fichier déjà enregistré ; données corrompues,
  modification externe ou dernier événement tronqué bloquent l'écriture.
  Il n'y a **ni correction ni effacement automatique**, même après crash.
- La limite par fichier est 4 Mio et 2 048 événements. Les messages sont
  limités à 2 000 caractères et ne contiennent ni script ni HTML exécutable
  dans le Qt Studio (`QPlainTextEdit`/`QTableWidgetItem`).
- Le fichier est **optionnel et advisory**. Une chaîne SHA valide n'authentifie
  pas ses auteurs ; le HEAD doit être conservé dans un support externe
  pour détecter une troncature totale. L'ajout de notes n'est pas atomique
  avec une sauvegarde Content/GameProject.
- Le panneau Qt propose un aperçu accessible de chaque réponse, avec
  navigation clavier dans la table, **Alt+C** pour comparer,
  **Alt+P** ou **Ctrl+Entrée** pour publier et un formulaire défilant
  sur les petits écrans. L'ensemble reste à vérifier avec NVDA/VoiceOver
  et lors d'une vraie session onscreen.

Contrats et tests :

```python
from drawtemp.sdk.review_notes import ReviewNoteStore, anchor_from_path

anchor = anchor_from_path("/project/story/scenes/arrival/title")
store = ReviewNoteStore("project.review.jsonl")
observed = store.inspect()["head"]
entry = store.append(graph.node(revision_id), expected_head=observed,
                     anchor=anchor, author="alice",
                     text="Clarifier le titre de cette scène")
# Réponse : thread=entry["sequence"] (le fil initial).
# État d'un fil : kind="resolve" / kind="reopen", thread=ID.
```

```bash
python -m unittest tests_standalone.test_drawtemp_r48b2_review_notes -v
```

**Limites du seul lot B2 :** les commentaires sont enregistrés dans
un journal séparé ; depuis R48.A4, le DAG peut être explicitement sauvegardé
et rechargé en préservant les mêmes identifiants de nœuds. Les commentaires
restent séparés de cette archive et les deux supports ne sont pas atomiques. La revue collaborative distante, l'authentification des
auteurs, les commentaires sur ressources non reconnues et les gates
QTest/onscreen certifiés restent hors R48.B2.

## R48.A4 — archive persistante, rebase documentaire revu et récupération

L'index de versions R48 n'est plus limité à la durée d'ouverture du Studio :
`drawtemp/sdk/project_history_store.py::LocalHistoryStore` sérialise les
snapshots validés du DAG dans un **fichier JSON facultatif** distinct de
Content/GameProject. Le format est versionné, canonique, borné à **64 Mio
et 2 048 nœuds**, avec SHA-256 de l'ensemble du payload, digest indépendant
de chaque document, vérification des `node_id` (auteur, libellé,
parenté) et reconstruction complète par le validateur canonique.

L'écriture est **explicite** et optimiste : `save(graph,
expected_digest=None)` crée un fichier inexistant seulement.
Pour remplacer une archive déjà ouverte, il faut fournir le SHA-256 exact
précédemment constaté par `inspect()` / `load()`. Une sauvegarde refusée
ne doit jamais effacer la version précédente. Le protocole emploie le verrou
exclusif déjà utilisé par le Studio, un fichier temporaire dans le même
répertoire, `fsync`, puis `os.replace` et synchronisation du répertoire
sur POSIX quand celle-ci est disponible. L'interface Qt présente désormais
**« Enregistrer l'historique… »** et **« Ouvrir un historique… »** :
aucune écriture sans action explicite, aucun overwrite d'un fichier externe
modifié depuis l'ouverture. Le chargement doit contenir au moins un snapshot
correspondant au contenu actuel de la session Studio ; sinon il est
refusé sans remplacer l'index précédent.

Les historiques dont les **nœuds** ont des identifiants différents mais dont
le **contenu** a le même SHA peuvent conserver deux parents distincts.
Cette prise en charge corrige la limitation du contrat `make_revision`
précédent, sans confondre les parentés ; le DAG contrôle toujours l'unicité
des identifiants de nœuds.

`drawtemp/sdk/project_rebase.py::SquashRebaseController` permet un rebase
documentaire **condensé** : ouvrir en Studio la version amont (onto),
prévisualiser `preview(topic_id=..., onto_id=...)` avec le plus récent
ancêtre commun maximal, puis prendre explicitement toutes les décisions
local/entrant. `apply(review, decisions)` utilise le merge R30 typé,
la validation Content/GameProject et un seul Undo dans la session R1.
`register(author=..., label=...)` crée ensuite **une nouvelle révision
enfant de la version amont**, uniquement si la session n'a pas bougé.
La publication du fichier JSON est **une troisième action explicite**.
Le rebase ne modifie pas l'historique d'origine, ne réécrit aucun commit Git
et ne rejoue pas chaque commit du topic : c'est un **squash rebase de
snapshots**, pas un `git rebase`.

```python
from drawtemp.sdk.project_rebase import SquashRebaseController
from drawtemp.sdk.project_history_store import LocalHistoryStore

rebase = SquashRebaseController(session_on_upstream, graph)
review = rebase.preview(topic_id=topic.node_id, onto_id=upstream.node_id)
transition = rebase.apply(review, decisions)  # Tous les conflits résolus explicitement
rebased_node = rebase.register(author="alice", label="topic on upstream")
store = LocalHistoryStore("project-history.r48.json")
current_head = store.inspect()  # None = créer un nouveau fichier seulement
store.save(graph, expected_digest=current_head)
```

### Reprise et sûreté

- Archive tronquée, checksum invalide, parents absents/non ordonnés,
  identifiants usurpés, JSON à clés dupliquées ou un projet différent
  provoquent un **refus de chargement**, sans modification du Studio.
- Lors d'une exception pendant le staging avant `os.replace`, l'ancienne
  archive valide reste intacte ; les tests simulent l'échec de publication.
  Après un arrêt brutal, un fichier `.stage-*` ou `.lock` peut subsister :
  **pas de suppression ni de reconstruction automatique**. L'utilisateur
  doit contrôler ces éléments avant reprise.
- L'archive ne certifie pas l'auteur, n'est pas un service de partage distant
  et ne garantit pas une écriture atomique entre sauvegarde du jeu, archive
  de versions, notes et audit. Une défaillance après l'application R1
  mais avant `register` reste résoluble manuellement (Undo ou capture
  contrôlée).
- Sur Windows, la garantie de durabilité du renommage dépend du système
  de fichiers ; aucun gate réel d'extinction/coupure matérielle n'est
  revendiqué. La CI tri-OS et les tests Qt offscreen restent à exécuter.

```bash
python -m unittest tests_standalone.test_drawtemp_r48a4_history_store -v
python -m unittest tests_standalone.test_drawtemp_r48a4_rebase -v
```

## R48.C1 — gate vertical deux auteurs, sauvegarde et replay Jeanne

Le scénario intégral est décrit dans
[`R48C_TWO_AUTHOR_RELEASE_GATE.md`](R48C_TWO_AUTHOR_RELEASE_GATE.md).

`python -m drawtemp.sdk.r48_vertical_gate` construit deux branches
indépendantes depuis `reference_project()` : **Alice** modifie la carte
(un tile cobble→grass), le nom de mission et un titre de scène ; **Bob**
modifie le texte narratif, le sous-titre du projet et revendique un titre
différent pour la même scène. Le gate refuse une fusion sans choix explicite,
puis applique la décision `incoming` en préservant les modifications
non conflictuelles, avec validation du couple canonique Content/GameProject.

Le gate enregistre et rouvre les documents du jeu, le DAG R48, une discussion
de revue et son état résolu, puis rapproche l'audit en lecture seule.
Enfin le **moteur réel** `GameSession` est lancé avec la seed 17 ; Jeanne
ouvre la porte avec le levier, la bataille doit finir victorieuse et les
enregistrements sauvegardés/rechargés/rejoués doivent être équivalents.

```bash
python -m unittest tests_standalone.test_drawtemp_r48c_vertical -v
python -m drawtemp.sdk.r48_vertical_gate
```

Les tests C1 supplémentaires injectent une interruption après publication
d'un seul des deux documents du jeu et imposent un choix explicite de
`complete` ou `rollback`, ainsi qu'une interruption de `os.replace`
avant la publication de l'archive. Les anciennes versions valides doivent
rester inspectables.

**C1 est seulement un gate logiciel simulé** : pas encore d'extinction
brutale, d'export Player validé, de concurrence entre vrais processus,
d'exécution CI attestée ni de revue visuelle ou screen reader certifiée.
Aucune fusion sur master tant que ces garanties n'ont pas été contrôlées.

## Tranches restantes

- **R48.A5** : rejeu contrôlé commit-par-commit si requis, recovery réel
  multi-processus et coupure matérielle, garanties transactionnelles renforcées.
- **R48.B3** : validations NVDA/VoiceOver, commentaires avec identité
  attestée et UX onscreen ; éventuelles vues d'ensemble multi-révisions.
- **R48.C2** : test deux processus/crash brutal, export Player reproductible,
  replay approfondi, et gate d'intégration final Windows/macOS/Linux.
