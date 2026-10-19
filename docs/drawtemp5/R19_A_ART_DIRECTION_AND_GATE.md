# R19.A — Bible graphique et certification des candidats artistiques (5.2)

**Statut : en cours, R19 n'est pas certifié.**  
Référence : [roadmap R19](../DRAWTEMP_5_0_TO_6_0_DETAILED_ROADMAP.md) ; compatibilité : [multi-genres R25–R30](../DRAWTEMP_MULTI_GENRE_CREATOR_ROADMAP.md).

## Direction artistique proposée — R19.1

L'univers Jeanne s'appuie sur une aquarelle médiévale **originale** : personnages
aux silhouettes lisibles, matières lin/bois/pierre/métal, lavis désaturés,
lumière chaude et contours affirmés dans les zones d'interaction. Il ne s'agit
pas d'une reproduction d'un jeu de référence.

| Rôle | Couleur proposée | Application |
| --- | --- | --- |
| Parchemin | #EFE0BD | UI, dialogues, panneaux |
| Encre | #344357 | Contours, textes, haute lisibilité |
| Pierre / métal | #9CABBC | Remparts, équipement |
| Cuir / bois | #744B37 | Objets, terrain bâti |
| Végétation | #718968 | Forêt, prairie, couvert |
| Or mat | #B8915E | Silhouette et équipement de Jeanne |
| Danger | #A04B43 | Feu et télégraphes de danger uniquement |
| Sélection | #E9C479 | Anneaux, focus et repères fonctionnels |

Ces couleurs sont des **valeurs de départ soumises à approbation humaine**, pas
des échantillons de production validés.

### Échelles, composition et cohérence

- Sprite Jeanne actuel : canvas 64×64 pixels et pivot au contact du sol,
  conservé par les annotations R4. Ce n'est pas une taille universelle pour
  les futurs jeux top-down. Comparer à 24, 54 et 96 px affichés.
- DPR 1× et 2×, zoom petit/standard/fort. Ne pas effacer le contour d'arme,
  l'orientation ou le socle d'unité à petit zoom.
- Lumière principale cohérente en haut à gauche ; ombres douces et courtes.
  La décoration ne masque jamais les intentions, zones de couverture, cases,
  portes, escaliers, acteurs ou objectifs.
- Terrain : herbe, terre, route, eau, pierre et falaise en transitions sans
  coutures ; variantes contrôlées par seed et référencées dans R4/R5.
- Architecture : toitures, façades, intérieurs et étages dans le même repère
  d'occlusion/picking/LOS que le moteur R3/R6. Pas de second algorithme de
  collisions dessiné dans le client graphique.
- Studio et Player consomment les mêmes sprites, atlas, pivots et calques
  depuis le registre canonique AssetRegistry v1. Ne pas ajouter un registre
  parallèle propre à Jeanne, au mode top-down ou aux profils R25–R30.

### Trois scènes témoin pour la revue

| Scène | Éléments clés | Défauts à exclure |
| --- | --- | --- |
| Village | Jeanne paysanne, PNJ, routes, maisons, sorties | Personnage fondu dans l'herbe, portes illisibles |
| Forêt | Loup, bandit, arches végétales, couvert | FX masquant intentions/cases, acteur derrière un arbre non signalé |
| Château | Armure, archer, lancier, murs, fenêtres, étages | Toit bloquant le picking, cutaway instable |

L'étalon doit être un **couple de captures réelles Studio/Player** sur la même
scène et au même état de gameplay, complété par vidéo ou spritesheets d'animation.
Aucune comparaison offscreen n'atteste à elle seule le rendu GPU final.

## R19.3 — Contrat de vraies animations

Pour chaque tenue de Jeanne, puis pour les autres personnages en revue :
quatre directions (north, south, east, west) et neuf actions
(idle, walk, run, attack, magic, block, hit, death, victory).
Chaque combinaison contient au moins **deux images visuellement distinctes**.
Les poses ne doivent pas être recyclées sous une nouvelle étiquette ; chaque
action doit posséder au moins un visuel propre et les directions ne doivent pas
avoir la même séquence pixel par pixel.

Idle/walk/run bouclent ; les autres séquences sont non bouclées. Le timing
visuel ne modifie jamais CT, règles, sauvegardes ou replays.

Le nouvel audit R19.A décode les fichiers PNG R7, applique les régions d'atlas,
calcule les signatures des pixels RGBA et détecte :
- action ou orientation manquante ;
- séquence figée / images dupliquées ;
- poses intégralement recyclées depuis une autre action ;
- séquence identique entre directions ;
- chemin absent, symbolique, hors projet, région hors image ;
- boucle incompatible.

Exécution :

~~~sh
python -m pip install ".[art]"
python -m drawtemp.assets.art_gate \
  --recipe .r7-jeanne-authoring/jeanne.character.json \
  --project-root . \
  --report r19-art-report.json

python -m unittest tests_standalone.test_drawtemp5_r19a -v
~~~

La racine du projet doit contenir les PNG référencés par la recette R7 ; le
contrôle n'ajoute ni ne modifie aucun fichier d'asset. Le statut
passed_structural_pixel ne signifie **pas** validation visuelle finale,
licence, parité GPU ou examen manuel. Ces champs restent not_assessed.
Pour les ressources aquarelles officielles, le gate de droits déjà existant
INT-03 est réutilisé, sans nouvelle source de vérité :

~~~sh
python -m drawtemp.assets.art_gate \
  --recipe .r7-jeanne-authoring/jeanne.character.json \
  --project-root . --watercolor-root assets/watercolor \
  --require-rights --report r19-production-audit.json
~~~

Les assets au statut pending/unverified peuvent servir de brouillon selon
le pipeline de prévisualisation, mais **jamais être annoncés comme
redistribuables**. Le pack R19.2 n'est livrable qu'avec provenance SHA-256,
droits de modification, redistribution et pièce justificative vérifiés par
INT-03/R15. Plusieurs animations partageant un atlas ne créent qu'un seul
fichier physique et une seule preuve.

Le kit R7.C existant ne possède pas encore toutes les actions run/magic/block/
victory dessinées indépendamment. Il **doit échouer** au gate R19 tant que ces
animations ne sont pas réellement produites ; les tests CI de l'auditeur
utilisent des images synthétiques, sans les présenter comme de l'art final.

## R19 : séquence de PR recommandée

| Lot | État | Suite et preuve |
| --- | --- | --- |
| R19.A / R19.1 | Bible et auditeur proposés | Revue humaine de palette, valeurs et standards |
| R19.2 | Bloqué pour release | Production source, licences, provenance, manifestes |
| R19.B / R19.3–5/9 | Ouvert | Jeanne, loup, bandit, classes, 9 actions / 4 directions, runtime |
| R19.C / R19.6–8/10 | Ouvert | Terrains, bâtis 2.5D, FX, caméra, picking |
| R19.D / R19.11–14 | Ouvert | Caches/culling, trois scènes, goldens et GPU réel |

La sortie globale R19 suppose les scènes village/forêt/château, sans pose
recyclée ni doublon visuel, et la parité Studio/Player. Les performances sont
à relever sur GPU documenté, scènes 32×32 / 64×64 / 128×128, jusqu'à 80
acteurs, DPR 1×/2×. Cible indicative 60 FPS et p95 inférieur ou égal à
16,7 ms, **jamais certifiée par le seul rendu offscreen**. Une personne doit
approuver/rejeter les captures goldens, leurs différences et la lisibilité.
