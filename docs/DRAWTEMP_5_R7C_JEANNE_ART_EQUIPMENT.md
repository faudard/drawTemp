# DrawTemp 5.0 — R7.C : costumes de Jeanne et liaison R8

## Objectif de la tranche

Après R7.A (atelier d'animation) et R7.B (sprites dans le viewport commun
R3/R5/R12), produire un **premier ensemble éditable de tenues réellement
distinctes** et refléter les équipements/blessures déjà sauvegardés par la
campagne. Aucun second registre ou nouveau format de sauvegarde.

## Créer et tester les ressources

~~~sh
python -m pip install ".[qt6,art]"

# Crée un projet auteur portable (sources + calques + recette + atlas Player).
python -m drawtemp.assets.jeanne_art --repository . --output .r7-jeanne-authoring

# Ouvre la recette et permet de retoucher chaque tenue et animation.
python -m drawtemp.studio.character_studio \
    --open .r7-jeanne-authoring/jeanne.character.json

# Ouvre la même scène R3 depuis le Studio et le Player.
python -m drawtemp.studio.map_editor \
    --character-pack .r7-jeanne-authoring/runtime
python -m drawtemp.player.qt_app \
    --character-pack .r7-jeanne-authoring/runtime

# Générer une planche de revue graphique.
python scripts/render_jeanne_art_contact_sheet.py \
    .r7-jeanne-authoring --output jeanne_r7c_review.png
~~~

Un bouton **Créer les 4 tenues de Jeanne…** dans Character Studio lance
cette génération et ouvre le résultat. Le dossier auteur reste externe au
dépôt et indépendant du Player : copier le sous-dossier runtime et ses PNG
suffit à tester le rendu autonome.

La génération produit les quatre variantes : peasant (corsage et tablier),
apprentice (cuir et équipement d'entraînement), armor (plastron et épaulières
métalliques), wounded (tunique déchirée et bandages). Chaque tenue possède
**quatre calques directionnels d'habillement propres**, peints en RGBA avec
silhouettes, ombrages et détails propres. Le visage, les cheveux, les huit
lignes de l'atlas historique Jeanne et les portraits existants sont
préservés. Ce sont des calques graphiques originaux et modifiables,
**pas quatre copies renommées de l'atlas**.

Les 5 clips de l'atlas approuvé sont diffusés aux quatre directions :
idle, walk, attack, hit, death. Les autres actions prévues en R7
(run, magic, block et victory) restent à illustrer en vrais dessins ;
ne pas prétendre que des frames dupliquées sont des animations nouvelles.

## Sélection fonctionnelle de la tenue

L'unique source de vérité reste Campaign.progress.heroes[actor].equipment :
les IDs d'objets correspondent aux équipements R8 de Content.equipment.
Le Player dérive la variante visuelle, en lecture seule :

| État de la campagne | Tenue affichée |
| --- | --- |
| Jeanne au début, sans équipement | peasant |
| Une arme équipée et valide | apprentice |
| Une armure équipée et valide | armor |
| Blessure persistante | wounded, prioritaire |

Une référence invalidée, un objet supprimé ou un équipement dans le
mauvais slot **ne déclenchent jamais** la tenue correspondante.
Le chargement et la restauration de sauvegarde rafraîchissent cette
projection et effacent les prévisualisations temporaires. Les états CT, IA,
combat, RNG, inventaire et fichier de sauvegarde ne sont pas modifiés.
L'interface de choix de tenue reste une **prévisualisation cosmétique**,
pas une commande d'équipement gratuite ; la sélection est recalculée depuis
la campagne à chaque retour de l'état canonique.

## Tests et gates

- Tests de création des 16 calques directionnels, unicité des couleurs et
  silhouettes, poses de marche réellement distinctes, offsets/pivots.
- Export strict R7, import du pack par AssetRegistry v1/AssetResolver R4,
  lecture dans QML Qt R3 et le Player R12.
- Un build répété doit produire exactement les mêmes PNG ; les fichiers
  déjà retouchés par l'artiste ne doivent jamais être écrasés.
- Tests des configurations équipement/arme/armure/blessure, y compris
  références inexistantes.
- CI Linux/Windows/macOS, Python 3.10/3.12 pour la génération et smoke
  Qt 6 sur Python 3.12 ; planche d'art et atlas exporté publiés comme
  artefacts pour revue humaine.

## Limites avant certification finale R7

Ce lot constitue un **premier passage de production artistique composite**.
Les tenues s'appuient sur les poses homologuées du même atlas de Jeanne :
le changement de silhouette n'est pas encore une refonte intégrale des poses,
des cheveux, des objets tenus ou des mouvements complexes. Le visuel doit
être jugé sur les captures du Player à 24/54/96 px, et la direction artistique
finale doit valider les nuances, le placement des épaules, le contact au sol
et la lisibilité en action.

R8 conserve la propriété des règles d'équipement. Le Player ne dispose
pas encore d'un écran d'inventaire complet permettant de déclencher
equip/unequip via des actions du SDK. C'est un travail ultérieur distinct
de la **projection correcte des objets déjà équipés/sauvegardés**.

Les scènes à déplacement continu et les effets avancés de run/magic/block/
victory restent des lots ouverts. Le gate R7 n'est pas certifié par la seule
présence des PNG et des tests CI offscreen.
