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

**Sémantique du terrain :** comme une suppression suivie d'une nouvelle pose, modifier la structure entière efface son ancien tampon tactique, puis applique le preset sur le nouvel emplacement. Les retouches case par case de l'ancienne emprise **ne suivent pas** le bâtiment. Les retouches simples ne font toujours pas disparaître l'image de la structure persistante.

## Vérifications

- `python -m unittest tests_standalone.test_structure_editing_3719b -v`
- `SPOREBOUND_GUI_SMOKE=1 python -m unittest tests_standalone.test_iso_persistent_structures_3717b_gui -v` (nécessite Tk et écran/Xvfb)
- `SPOREBOUND_GUI_SMOKE=1 python -m unittest tests_standalone.test_structure_editing_3719b_gui -v` (nécessite Tk et écran/Xvfb, **ajouté au job éditeur CI**)
- CI du dépôt : Linux / macOS / Windows, en attente d'exécution sur la tête exacte de la PR.

Gate **fonctionnel** : sélection → modification/duplication → Undo/Redo → sauvegarde/réouverture → même identifiant et rendu. Le gate **visuel** reste à examiner manuellement avec la scène Valcroix, à plusieurs zooms et sur Windows/macOS. Les tests Tk/Xvfb vérifient le nombre d'instances de sprites, mais ne certifient pas leur qualité artistique.

## Hors périmètre

- Préservation des retouches tactiques locales lors d'une transformation.
- Bâtiments multi-étages jouables superposés.
- Historique inter-éditeurs, commandes de groupe et refonte de l'agencement des panneaux (3.7.21).

### Critères supplémentaires après la passe de manipulation directe

- Un clic simple sélectionne sans produire de commande Undo.
- Maj+glisser crée une nouvelle identité visuelle et n'altère pas la structure source.
- Un glisser non valide ne modifie ni le document ni l'historique ; Échap annule le geste.
- Après un Undo d'un déplacement, l'inspecteur et le déplacement clavier retrouvent la structure via son identifiant, pas via l'ancienne case.
- Les anciennes cartes restent reconnues par leur tampon initial et sont migrées à la première transformation.
