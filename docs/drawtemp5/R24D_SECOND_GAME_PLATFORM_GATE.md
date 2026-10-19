# R24.D — deuxième jeu Asterion, modèle Creator et gate logiciel 6.0

**Statut : prototype en PR empilée après R24.C (#328), R24.B (#316) et R24.A (#296).** L'existence de ce jeu ne clôt pas R24.12 : R23, tous les R24 P1, l'export Player natif et le gate visuel/release sont des dépendances ouvertes.

## Univers exemple : Asterion — Les Veilleurs du Signal

Jeu **original** tactique de science-fiction dans une station orbitale, distinct de Jeanne d'Arc. Il comprend deux cartes/missions (`signal_depot`, `reactor_vault`), deux personnages joueurs (Lyra et Iro), quatre archétypes réutilisables (`scout`, `engineer`, `security_drone`, `guardian`), trois compétences de combat/soutien, des couvertures/obstacles, un événement de mission, deux scènes de dialogue et une campagne persistante avec suite déverrouillable.

Les données sont écrites de façon indépendante dans `drawtemp/creator_examples/asterion.json` (Content v1) et `asterion.game.json` (GameProject v1). Elles ne sont **pas** construites en renommant ou copiant des missions Jeanne à l'exécution ; aucun fork de GameSession/Battle/Studio/renderer n'est créé.

Les archétypes utilisent le `ActorFactory` canonique et les mêmes actions de combat, CT/RNG, événements et sauvegardes que le moteur de référence. Le namespace `org.drawtemp.example.asterion` est une extension déclarative R24.A, sans exécution de plugin.

## Création d'un projet utilisateur

Dans le Creator R15, `asterion` est maintenant un type reconnu. Par exemple :

```python
from drawtemp.export.templates import create_template
create_template('asterion', 'mon-asterion')
```

Le modèle est livré avec les fichiers de package `drawtemp/creator_examples/*.json` pour fonctionner depuis une installation normale de `drawtemp-tactics` (sans chemin de repo fixe). La fonction écrit les deux JSON canoniques dans une nouvelle destination, les valide et lance le preflight R15. Une destination existante est refusée.

Pour l'ouvrir dans le Studio :

```bash
drawtemp-studio5 --content mon-asterion/game.json
```

Ce modèle ne fournit pas de sprites propriétaires ou de nouveaux atlases à licence fictive : le rendu technique du moteur repose sur les contrats de présentation préexistants. **Asterion n'est pas encore une démo avec art et animation certifiés.**

## Gate logiciel

```bash
python -m scripts.certify_r24_second_game --report r24d-software-report.json
python -m unittest tests_standalone.test_drawtemp5_r24d
```

Le script utilise les vraies API du SDK : négociation version/capacités, chargement et validation des deux documents, lancement de la scène de briefing et de la première bataille, `AuthoringSession.preview/apply/undo/redo/save_as/open`, vérification d'export R15, puis **replay + sauvegarde/restauration sur disque après chaque commande** pour trois seeds. Aucun mock de Battle n'entre dans cette preuve.

Le rapport JSON inclut les hash canoniques Content/GameProject, les commandes jouées, les hashes de RNG/CT et un bilan des gates. **`software_passed` n'est pas `release_certified`** : le rapport exige séparément installation native/clean-machine, GPU/onscreen, provenance et droits des assets, tests UX, parcours de jeu complet avec les deux missions et sha master final.

Pour ne pas confondre preuve logicielle et release :

```bash
python -m scripts.certify_r24_second_game --require-release
# code retour 2 tant que les preuves externes ne sont pas validées
```

Les tests R15 peuvent utiliser un exécutable synthétique pour contrôler la forme et les hashes d'un bundle ; **cela n'atteste pas** qu'un Player natif démarre sur une machine propre. Le script R24.D ne prétend ni exécuter du QML sur GPU matériel ni certifier les droits d'assets.

## QA et critères non satisfaits

Tests Linux Python 3.10/3.12, Windows et macOS Python 3.12 ; smoke Qt offscreen 3.12 avec les mêmes widgets Studio que Jeanne. Le second projet passe par les formats Content v1/GameProject v1 et le même renderer, sans démontrer une parité visuelle dans cette tranche. La création d'un second jeu complet *sans édition manuelle du JSON dans le Studio*, sa progression intégrale sur deux missions, et un Player autonome réellement installé restent à certifier : la seule présence d'un modèle Creator ne vaut pas fermeture du gate R24.12.

Ordre de fusion : #296 → #316 → #328 → R24.D, rebase/retest à chaque montée vers master. Prochains lots R24.5–R24.8/R24.10 et R24.12 release P1, puis transition R25 multi-genres.
