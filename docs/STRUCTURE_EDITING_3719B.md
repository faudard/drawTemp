# 3.7.19B — Édition de structures complètes

Base : `master` `ef88ca5` (13 octobre 2026). Cette PR prolonge l'identité persistante de 3.7.17B, sans modèle de bâtiment concurrent ni modification du runtime.

## Parcours opérateur dans le Map Editor

1. Choisir **Sélectionner structure**, puis cliquer une case de la maison, tour, ruine, pont, escalier ou rempart.
2. Pour déplacer directement : **glisser-déposer** depuis la case cliquée vers la destination. Le décalage entre curseur et ancre est conservé, évitant tout saut du bâtiment.
3. Pour copier directement : **Maj + glisser-déposer**. La copie reçoit une identité distincte et l'original reste en place.
4. L'inspecteur indique modèle, identifiant, ancre, emprise, rotation et entrée. Les réglages du bandeau reprennent ceux de la structure sélectionnée. Les **flèches du clavier** déplacent la sélection d'une case.
5. Pour changer le type, la rotation ou l'entrée : modifier les contrôles puis **Appliquer propriétés**.
6. Les commandes **Déplacer sélection** et **Dupliquer sélection** restent disponibles pour cliquer un nouvel emplacement avec pivot Coin/Centre/Porte.
7. **Échap** annule un glissement en cours sans modifier le document. Annuler/Rétablir via l'historique du Document ; enregistrer et rouvrir le contenu normalement.

Le contour bleu indique la structure sélectionnée. Pendant un glissement, l'empreinte et le sprite sont prévisualisés avant commit : vert = destination validée, rouge = placement refusé. Le bouton de souris relâché réalise une transaction unique, y compris si les empreintes initiale et finale se recouvrent. La prévisualisation de survol est réutilisée lorsque le pointeur demeure sur la même cellule : pas de revalidation à chaque pixel. La sélection des structures persistantes suit leur identifiant à travers les déplacements et Undo/Redo, évitant de sélectionner accidentellement un bâtiment voisin.

## Contrat des opérations headless

`iso_structures.py` expose `structure_at`, `validate_structure_edit`, `edit_structure`, `move_structure` et `duplicate_structure`.

- Validation **avant** modification du Document : carte, unités multicases, objets, objectifs, reliques, déploiements, autres structures persistantes et détection des anciennes structures sans identifiant.
- Le déplacement retire l'ancienne empreinte dans une copie temporaire **avant** de vérifier le nouvel emplacement : décalages de 1 case possibles même lorsque les deux empreintes se recouvrent.
- L'identifiant d'une structure persistante est préservé lors de sa transformation. Une duplication obtient un identifiant distinct.
- Une structure sans métadonnées d'identité (ancienne carte) est reconnue par le système historique, puis reçoit une identité persistante à la première transformation.
- Une erreur ne modifie pas le document ni son historique.
- Une transformation est une seule opération `Document.replace` : Undo/Redo existant, sérialisation `Content` version 1 inchangée.

**Sémantique du terrain :** les nouvelles structures conservent le sol d'origine dans une métadonnée `underlay`. Une suppression ou un déplacement restaure exactement les cases enregistrées sous le bâtiment, y compris les tuiles absentes du document initial. Une transformation réapplique ensuite le nouveau tampon sur sa destination, après capture de son terrain d'accueil. Les retouches tactiques peintes sur le bâtiment **ne remplacent pas** cette sauvegarde du sol d'origine.

## Vérifications

- `python -m unittest tests_standalone.test_structure_editing_3719b -v`
- `SPOREBOUND_GUI_SMOKE=1 python -m unittest tests_standalone.test_iso_persistent_structures_3717b_gui -v` (nécessite Tk et écran/Xvfb)
- `SPOREBOUND_GUI_SMOKE=1 python -m unittest tests_standalone.test_structure_editing_3719b_gui -v` (nécessite Tk et écran/Xvfb, **ajouté au job éditeur CI**)
- CI du dépôt : Linux / macOS / Windows, en attente d'exécution sur la tête exacte de la PR.

Gate **fonctionnel** : sélection → modification/duplication → Undo/Redo → sauvegarde/réouverture → même identifiant et rendu. Le gate **visuel** reste à examiner manuellement avec la scène Valcroix, à plusieurs zooms et sur Windows/macOS. Les tests Tk/Xvfb vérifient le nombre d'instances de sprites, mais ne certifient pas leur qualité artistique.

## Hors périmètre

- Préservation des retouches tactiques locales lors d'une transformation.
- Bâtiments multi-étages jouables superposés.
- Historique inter-éditeurs et refonte de l'agencement général des panneaux (3.7.21).

### Critères supplémentaires après la passe de manipulation directe

- Un clic simple sélectionne sans produire de commande Undo.
- Maj+glisser crée une nouvelle identité visuelle et n'altère pas la structure source.
- Un glisser non valide ne modifie ni le document ni l'historique ; Échap annule le geste.
- Après un Undo d'un déplacement, l'inspecteur et le déplacement clavier retrouvent la structure via son identifiant, pas via l'ancienne case.
- Les anciennes cartes restent reconnues par leur tampon initial et sont migrées à la première transformation.


## 3.7.19B — structures groupées (passe complémentaire)

L'outil de **Sélection** existant (rectangle) sert aussi à sélectionner
plusieurs bâtiments. Chaque bâtiment est inclus uniquement si *toutes*
ses cases tactiques figurent dans la sélection : une maison partiellement
survolée n'est pas embarquée par erreur.

1. Utiliser l'outil **Sélection**, puis tracer un rectangle contenant toutes
   les cases des bâtiments à manipuler.
2. Régler les décalages **ΔX/ΔY** dans le bandeau *Structures groupées*.
3. Choisir **Aperçu groupe**. Les cases prévues sont vertes si valides,
   rouges si refusées ; la vue isométrique affiche aussi les sprites
   déplacés aux ancrages prévus.
4. Choisir **Déplacer groupe** ou **Dupliquer groupe**. Le groupe se
   transforme en une transaction `Document.replace`, donc un seul Undo.
5. La sélection suit les empreintes d'arrivée, afin d'enchaîner un autre
   déplacement/une duplication. Une copie reçoit de nouveaux IDs, tandis
   qu'un déplacement conserve les IDs persistants existants.

### Sécurité et compatibilité

- La validation se fait sur une copie : restauration des terrains sous toutes
  les anciennes emprises (pour le déplacement), puis contrôle des nouvelles
  emprises avant d'ajouter un bâtiment. Les recouvrements avec l'ancienne
  position d'un autre bâtiment du groupe conservent ainsi son vrai sol.
- Les sources adjacentes peuvent se recouvrir avec leurs propres anciennes
  cases après translation. Deux nouvelles emprises ne peuvent jamais se
  chevaucher.
- La destination ne peut recouvrir des unités, objets interactifs, objectifs,
  reliques, déploiements incompatibles ou autres structures (persistantes ou
  inférées depuis une ancienne carte).
- Les structures issues d'une ancienne carte sans ID reçoivent une identité
  persistante lors de la première transformation.
- Limite temporaire de 128 bâtiments par opération, afin de contenir le coût
  des validations et l'historique.
- Un décalage `(0,0)` n'engendre pas de nouvelle opération Undo ;
  une duplication `(0,0)` est refusée.
- Les nouvelles structures conservent le fond de terrain en `underlay`.
  Les anciennes structures sans cette métadonnée gardent l'effacement
  historique à la suppression (aucune reconstitution du sol ne peut être
  inventée). Les retouches de surface effectuées sur une structure restent
  distinctes du fond enregistré.

### Gates ajoutés

- `python -m unittest tests_standalone.test_structure_groups_3719b -v`
  : identités, translation adjacente, duplication, Undo/Redo, format sauvegardé,
  sélection incomplète, collisions et legacy.
- `SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_structure_groups_3719b_gui.py -v`
  : rectangle, aperçu, déplacement, duplication et Undo/Rétablir depuis la
  vraie interface, câblé au job `editor` du workflow Standalone.


## 3.7.19B — Terrain sauvegardé sous les bâtiments

Chaque nouvelle structure persistante ajoute un champ **optionnel**
`underlay` à son enregistrement `Mission.structures[]`. Ce champ contient
une entrée par case de l'emprise sous forme
`{"pos": [x, y], "tile": null | {surface, feature, height, cost, blocked, cover, hazard}}`.
Une valeur `null` signifie que la case ne possédait **aucune tuile explicite**
dans la carte sparse, ce qui permet de restaurer exactement l'état initial.

- Pose : capturer le terrain **avant** d'écrire le tampon de la structure ;
  la simulation continue à utiliser les tuiles tactiques ordinaires.
- Suppression : supprimer le tampon, restaurer les tuiles sauvegardées et
  rendre les anciennes cellules absentes au format sparse si nécessaire.
- Déplacement : restaurer l'ancienne emprise, capturer le terrain à destination,
  appliquer la nouvelle structure et conserver son identité.
- Duplication : l'original conserve son `underlay` ; la copie capture le terrain
  situé sous son propre emplacement.
- Groupe : restaurer **tous** les terrains d'origine avant la validation et
  avant d'appliquer les destinations, y compris lorsque des bâtiments adjacents
  échangent partiellement leurs anciennes cases.
- Éditeur : l'inspecteur précise si une structure dispose d'un terrain
  sauvegardé ou si elle provient d'une ancienne carte.

Le parseur `Content` conserve la version **1** et accepte les deux formats :
enregistrement historique à cinq champs et enregistrement récent avec
`underlay`. Il vérifie le nombre exact de cases, leur appartenance à
l'emprise, l'absence de doublons et les types/valeurs de terrain. Aucune
migration destructive de documents anciens n'est effectuée.

**Limite importante :** les structures créées avant cette modification ne
possèdent pas leur sol d'origine. Lors de leur premier déplacement, les anciennes
cases restent effacées (comportement historique), tandis que la nouvelle
position bénéficie immédiatement d'une sauvegarde du sol.

**Gate :** `python -m unittest tests_standalone.test_structure_underlay_3719b -v`.
Il couvre rivière, surface pavée, décor, relief, champs tactiques, cases sparse,
rotation/changement de structure, déplacement superposé, duplication,
opérations groupées, Undo/Redo, relecture JSON, anciennes cartes et snapshots
invalides. La réussite de la CI doit encore être vérifiée sur le dernier SHA.


## Gate Valcroix après la fusion du 3.7.19B

Le banc de validation utilise exclusivement la carte existante
`examples/fortified_village_3717a.py`, réalisée via les commandes
d'édition officielles (26 × 20 cases, dix structures). Aucun terrain
de test dessiné manuellement ne remplace cette scène.

- **Pont (12,9) → (12,7)** : le déplacement conserve son identifiant,
  laisse réapparaître les six cases d'eau sous le pont initial et
  capture l'eau sous le nouvel emplacement.
- **Suppression du pont déplacé** : comparer toutes les tuiles et
  identités de la scène à une suppression du pont à sa position initiale.
  Les autres bâtiments, objets et décors restent inchangés.
- **Deux maisons (3,3) et (6,13)** : une translation de groupe d'une
  case en X conserve les IDs et restaure exactement les terrains
  sous-jacents après retrait des maisons.
- **Undo/Redo et sauvegarde JSON** : mêmes données et identités
  après relecture, sans migration supplémentaire.
- **Rendu Tk réel** aux zooms **24 / 54 / 96** : avant déplacement,
  après déplacement et après suppression du pont, avec les atlas
  existants. Les captures `village-underlay-<état>-<zoom>.png` sont
  jointes à l'artefact de captures Valcroix du workflow Linux/Xvfb.

Commandes de validation :

```bash
python -m unittest discover -s tests_standalone -p test_reference_village_underlay_3719b.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_reference_village_3717a_gui.py -v
```

Ces vérifications sécurisent la fidélité technique et créent des preuves
inspectables. Elles ne remplacent **pas** la revue graphique humaine
(occlusion, composition et lisibilité), notamment sous Windows/macOS.

Le test historique d'underlay a également été corrigé dans `master`
pour lire `structures` comme un champ optionnel lorsque la dernière
structure est supprimée ; le format Content v1 omet volontairement
la liste vide.


## Gate de résistance — éditions successives (passe 3.7.19B)

Une validation déterministe supplémentaire vérifie que les fonds enregistrés
ne se dégradent pas pendant de longues chaînes de modifications :

- **32 modifications successives** d'une maison alternant ancrages,
  rotations (0/90/180/270°) et portes (A/B), avec vérification d'un ID
  invariant ; Undo/Redo et sauvegarde/relecture à intervalles réguliers.
- **12 translations groupées aller-retour** de trois maisons accolées,
  puis une duplication du groupe, retrait des six bâtiments et comparaison
  *exacte* avec le document sparse de départ.
- **Échec atomique au milieu de la séquence** : déplacement hors de la
  carte interdit, aucune mutation du document ni de l'historique, et
  possibilité de poursuivre les éditions.
- **Compatibilité persistante historique** : un enregistrement sans
  `underlay` ne peut pas restituer son sol initial, mais capture le sol
  des nouveaux emplacements dès la première transformation.

Test ajouté : `python -m unittest discover -s tests_standalone -p test_structure_underlay_stress_3719b.py -v`.

La réussite de ce gate complète mais ne remplace pas la revue du
rendu isométrique réel Valcroix à 24/54/96.
