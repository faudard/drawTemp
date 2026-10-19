# R19.B3 — Bestiaire quatre directions, audit et renderer multi-acteurs

**État : socle d’intégration prêt à recevoir de vraies illustrations. Les huit fiches ne sont pas des packs artistiques finis.**

## Les huit rôles du bestiaire

| Rôle | Actions directionnelles requises | Source aquarelle actuelle |
| --- | --- | --- |
| Loup | idle, walk, attack, hit, death | Plusieurs poses en vue unique, non certifiées 4 vues |
| Bandit | idle, walk, attack, block, hit, death | Illustration isolée ; vue unique insuffisante |
| Archer | idle, walk, attack, hit, death | Illustration isolée ; vue unique insuffisante |
| Lancier | idle, walk, attack, block, hit, death | Plusieurs poses en vue unique, non certifiées 4 vues |
| Chevalier | idle, walk, attack, block, hit, death | Illustration isolée ; vue unique insuffisante |
| Soigneur | idle, walk, attack, magic, hit, death | Illustration isolée ; vue unique insuffisante |
| Officier | idle, walk, attack, magic, hit, death | Illustration isolée ; vue unique insuffisante |
| Boss | idle, walk, attack, magic, block, hit, death | Illustration isolée ; vue unique insuffisante |

La liste des actions concerne uniquement le contrat visuel. Elle n’ajoute aucune capacité, stat, classe, compétence, HP, IA, règle CT ou changement de sauvegarde au jeu.

## Préparer les images auteur

Le format requis est **un PNG RGBA éditable par frame**, de 64×64 pixels pour les rôles usuels et 128×128 pour le boss. Pour chaque rôle, action et direction :

~~~text
assets_production/
  wolf/
    south/
      idle_0.png
      idle_1.png
      walk_0.png
      walk_1.png
      attack_0.png
      attack_1.png
      hit_0.png
      hit_1.png
      death_0.png
      death_1.png
    north/ ... mêmes actions, vrais angles
    east/  ... mêmes actions, vrais angles
    west/  ... mêmes actions, vrais angles
  bandit/ ...
  archer/ ...
  spearman/ ...
  knight/ ...
  healer/ ...
  officer/ ...
  boss/ ...
~~~

Les vues nord/sud/est/ouest doivent être *réellement dessinées séparément*. Le code ne retourne, ne reflète et n’étire aucune vue isolée pour combler un manque.

## Contrôler puis exporter une candidate

~~~sh
python -m pip install ".[art]"
python -m drawtemp.assets.bestiary_r19 --source ../assets_production --report ../r19-bestiary-report.json
python -m drawtemp.assets.bestiary_r19 --source ../assets_production --role wolf --output ../pack-wolf-r7
python -m unittest tests_standalone.test_drawtemp5_r19b3_bestiary -v
~~~

Le rapport contient pour chaque rôle le nombre exact de PNG requis, les fichiers absents, les frames statiques, les directions aux pixels identiques ou exactement miroités, et les actions recyclées. **Candidate ready** signifie uniquement une conformité structurelle/pixel ; cette mention n’approuve ni esthétique ni droits de distribution.

L’export utilise la recette `drawtemp.assets.characters.validate`, puis `export_pack` et le registre `AssetRegistry v1` inchangés : `atlas.png`, `registry.json`, `character.json`. Un `bestiary-provenance.json` contient les empreintes SHA-256 de toutes les images d’origine et les champs `redistribution_approved: false`, `human_art_approval: pending`. Les répertoires sources restent inchangés et l’export refuse un dossier de sortie existant.

## Preview multi-acteurs dans Studio / Player

`make_controller` et `create_view` acceptent maintenant `character_packs={"wolf": Path(".../pack-wolf-r7"), ...}` en complément de l’option R7 historique `character_pack` pour Jeanne. La même scène R3 peut afficher plusieurs acteurs aux atlas/pivots/poses indépendants. Les événements R12 (attack, impact…) utilisent alors le bon pack via `visualClipFrame`, avec le facing de l’acteur ou de son action.

Le Player Qt en développement accepte :

~~~sh
python -m drawtemp.player.qt_app --character-pack ../jeanne-motion-r19/runtime --actor-pack wolf=../pack-wolf-r7
~~~

Le chargement de packs non vérifiés est volontairement refusé dans les versions natives gelées. Le pipeline de release R15/INT-03 doit approuver chaque ressource et intégrer des packs à un bundle signé avant distribution.

## Critères non atteints et suite R19

- **Art original** : les PNG requis ne sont pas fournis pour les huit personnages. Les illustrations actuelles mono-vue ne sont pas recyclées automatiquement.
- **Droits** : provenance enregistrée, mais licences et redistribution non approuvées.
- **Vérification artiste** : orientation anatomique, lisibilité 24/54/96 px, contours aquarelle, ombres et silhouettes doivent être inspectés humainement.
- **Couverture gameplay** : le runtime reconnaît les poses disponibles mais n’ajoute ni ennemis aux campagnes, ni nouveaux spells ou combats.
- **GPU et diffusion** : profiling, goldens Studio/Player, DPI et 60 FPS restent hors de cette tranche.

**Prochaine étape R19.B4** : intégrer les vraies planches validées, calibrer leurs pivots/ombres et établir des scènes de référence village/forêt/siège sous le même renderer.
