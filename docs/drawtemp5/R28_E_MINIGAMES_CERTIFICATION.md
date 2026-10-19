# R28.E — Trois mini-jeux de référence, création Qt et matrice de certification

**Statut : première tranche exécutable R28.10/R28.11, release DrawTemp 6.4 = NO-GO.**

Branche empilée : **#298 R25.A → #306 R28.B → #321 R28.C → #332 R28.D → R28.E**.
L'assistant R28.A #292 reste une branche séparée à rebaser/intégrer ;
le runtime action R26.A #300 n'est pas intégré au Player canonique.

## Démarrage (FR)

1. Lancer le Studio Qt 6 sous **Python 3.12** :
   `python -m drawtemp.studio.qt_shell --workspace minigames`.
2. Dans l'atelier **Mini-jeux R28**, choisir un dossier parent existant,
   puis un mini-jeu et cliquer sur **Aperçu sans écriture**.
3. Utiliser **Créer le mini-jeu sélectionné** ou **Créer les 3 mini-jeux**.
   La création du portfolio publie les trois dossiers ensemble après
   validation complète, sans remplacer un dossier déjà existant.
4. Après création, utiliser **Vérifier le mini-jeu** pour le préflight
   et le roundtrip `GameSession`, ou **Matrice de certification**.
   L'action **Ouvrir dans le Studio** recharge les fichiers canoniques et
   respecte la confirmation des modifications non enregistrées.
5. Éditer ensuite dans les ateliers existants (cartes, compétences, IA,
   narratif, animations), sauvegarder Content/GameProject et répéter l'audit.

## Getting started (EN)

1. Launch `python -m drawtemp.studio.qt_shell --workspace minigames`
   with Python 3.12 and the Qt6 extra installed.
2. Choose an existing parent directory and click **Preview** (French UI:
   `Aperçu sans écriture`). Preview never writes a file.
3. Click **Create selected** or **Create all three**; existing destinations
   are never overwritten.
4. Run the **Audit** or **Certification matrix** and open the created
   `game.json` in the same Studio. The real R1 authoring owner is replaced
   only after the normal unsaved-change confirmation.

## Trois projets réellement créés

| Mini-jeu | Modèle R15 | Genre effectif | Vérification réelle |
|---|---|---|---|
| `duel_tactique` — Duel de l'écuyer | `tactical` | SRPG CT | Démarrage de mission dans `GameSession/Battle`, checkpoint restauré |
| `garde_remparts` — Garde des remparts | `blank` | SRPG CT, carte distincte 12×12 | Démarrage de mission CT et replay de session vérifié |
| `choix_village` — Le choix du village | `narrative` | Narratif avec mission CT conservée | Deux choix `enter`/`observe`, drapeaux persistants, checkpoint restauré |

Les mini-jeux ne sont pas des variantes de dossiers par simple renommage :
chacun reçoit une paire JSON distincte issue de `create_template` R15,
éditée avec `AuthoringSession.preview_pair/apply/save`, et vérifiée par
`preflight`, `GameSession.new`, puis `GameSession.from_recording`.
Les deux prototypes tactiques et le prototype narratif utilisent leurs
véritables règles existantes ; la création ne modifie jamais le projet
courant. La galerie ne fait aucun accès réseau.

## Gates et vérité des preuves

`certification_matrix(folder)` retourne un document machine-readable
`r28e-certification-matrix` (schema 1) avec, pour chaque dossier,
la réussite du préflight et du roundtrip, et un **NO-GO explicite** :

- trois projets de référence valides : **atteignable** et vérifiable ;
- trois genres indépendants dont Action : **non atteint** (SRPG ×2, narratif ×1) ;
- Player graphique et transitions Action/CT : **non atteint** tant que
  R25 SceneRouter, R26 ActionRuntime et R28.9 Classic RPG ne sont pas intégrés ;
- export Player natif signé sur Windows/Linux/macOS : **non atteint** ;
- tests d'usage novice FR/EN, performance GPU, input/manette, retours de
  playtest réel et trois bundles sur machines propres : **non atteints**.

**La matrice doit rester `release_6_4_go: false`**, y compris quand
les trois préflights passent. Un fichier corrompu ou un dossier manquant
renvoie une ligne `passed: false`, et la matrice ne certifie rien.

## Tests & CI

```bash
python -m unittest tests_standalone.test_r28e_minigames_certification -v
python -m unittest tests_standalone.test_drawtemp5_r15_creator -v
python -m unittest tests_standalone.test_r28d_animation_events_roundtrip -v
```

Le workflow `.github/workflows/drawtemp-r28e-minigames.yml` exécute
les tests headless Python 3.10/3.12/3.14, les tests Qt offscreen tri-OS
et un smoke Studio avec l'atelier `minigames`.
Ce sont des gates **à exécuter** ; une PR créée n'est pas une preuve CI verte.

## Suite nécessaire après R28.E

1. Intégrer proprement #292 (nouveau projet) et ce catalogue, en unifier
   les boutons et documents utilisateur sans doubles modèles.
2. R25 SceneRouter + R26 action : enregistrer un **véritable mini-jeu
   action-aventure** dans un GameProject v1 depuis Qt, le lancer et
   vérifier les commandes et checkpoints sur le Player.
3. R28.9 : combat RPG par menus, puis troisième genre fonctionnel si
   le projet choisit RPG plutôt que narratif.
4. Vérifier les trois genres sur un Player graphique, les packages
   multiplateformes, l'UX sans JSON, ainsi que les retours en Studio.
5. Inscrire les preuves de test et d'export (SHA précis, OS, GPU, CPU,
   versions Python/Qt) avant de considérer le jalon 6.4 livré.
