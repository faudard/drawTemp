# R31.G — Variables tactiques vers campagne

**État : PR #385 (R31.E–G), brouillon, sans certification CI du SHA final.**

## Usage

Dans Game Logic Studio, après avoir appliqué un graphe possédant au moins une action de variable R31.F, utiliser **Exporter campagne**. L'auteur sélectionne :
- la variable tactique source r31_* ;
- le drapeau de campagne cible r31_* ;
- un résultat autorisé : victory, defeat ou both.

L'export est inscrit dans l'extension du projet **org.drawtemp.logic.campaign**. Chaque mapping est explicite et limité au périmètre d'une mission. L'éditeur valide les destinations uniques, les noms typés, la présence réelle d'une action source et l'existence de la mission. Le maximum est de 64 mappings.

## Contrat de runtime

La sortie d'un combat dans GameSession._commit() est le seul point de transfert. Un Battle encore en cours ne peut rien exporter. Les variables sources sont reconstruites depuis Battle.events par variables_from_journal ; le transfert n'invente ni état ni ordonnanceur.

Le résultat victory/defeat conditionne l'export. Une variable non affectée n'est pas exportée et n'est pas remplacée par False ou 0. Les drapeaux existants d'un autre type ne peuvent pas être écrasés. Le transfert s'applique à une **copie détachée** de la progression, après le règlement classique de campagne ; les garde-fous GameSession empêchent la double finalisation.

Campaign.story_flags est le stockage persistant canonique. Les checkpoints gardent le Battle et son journal de commandes et sont vérifiés par le digest. Le mapping fait partie du digest de GameProject : le changement de configuration rend les checkpoints précédents incompatibles.

La synchronisation de l'inventaire, des récompenses, des quêtes et des variables d'autres scopes est volontairement hors périmètre ; Campaign Flow et StoryBook conservent leur autorité.

## Tests et certification

- tests_standalone/test_drawtemp_r31_logic_campaign.py : victoire native (mentor retiré par action R9), variable tactique, export au règlement, checkpoint restauré, aucun second export.
- Défaite sans export non demandé et export de défaite autorisé.
- Erreurs de mapping, références absentes, doublons, Undo/Redo R1, rollback et incompatibilité de checkpoint après changement du projet.
- tests_standalone/test_drawtemp_r31_logic_qt.py : création d'un export depuis Qt sans toucher au combat.

Workflow : .github/workflows/r31-visual-graph.yml, Ubuntu/Windows/macOS. Les jobs doivent réellement s'exécuter et passer ; un workflow marqué failure avec zéro job ne prouve aucune régression des tests.

**Gate global R31 : NO-GO.** Reste à réaliser et à valider un vertical slice authentique sans JSON manuel :
PNJ → dialogue → porte verrouillée → combat → coffre → quête terminée → sauvegarde/reprise du Player.
