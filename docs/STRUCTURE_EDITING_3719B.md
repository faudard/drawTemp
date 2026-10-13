# 3.7.19B — Édition de structures complètes

Base : `master` `ef88ca5` (13 octobre 2026). Cette PR prolonge l'identité persistante de 3.7.17B, sans modèle de bâtiment concurrent ni modification du runtime.

## Parcours opérateur dans le Map Editor

1. Choisir **Sélectionner structure**, puis cliquer une case de la maison, tour, ruine, pont, escalier ou rempart.
2. L'inspecteur indique le modèle, l'identifiant, l'ancre, l'emprise, la rotation et l'entrée. Les réglages du bandeau reprennent les valeurs de la structure sélectionnée.
3. Pour changer le type, la rotation ou l'entrée : modifier les contrôles puis **Appliquer propriétés**.
4. Pour déplacer : **Déplacer sélection**, déplacer le curseur vers la nouvelle ancre (ou pivot choisi) et cliquer.
5. Pour copier : **Dupliquer sélection**, puis cliquer la destination. La copie reçoit une identité distincte.
6. Annuler/Rétablir via l'historique du Document ; enregistrer et rouvrir le contenu normalement.

Le contour bleu indique la structure sélectionnée. L'empreinte verte ou rouge et le sprite de prévisualisation utilisent les mêmes calculs que la pose standard. La prévisualisation de survol est réutilisée lorsque le pointeur demeure sur la même cellule : pas de revalidation à chaque pixel.

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
- CI du dépôt : Linux / macOS / Windows, en attente d'exécution sur la tête exacte de la PR.

Gate **fonctionnel** : sélection → modification/duplication → Undo/Redo → sauvegarde/réouverture → même identifiant et rendu. Le gate **visuel** reste à examiner manuellement avec la scène Valcroix, à plusieurs zooms et sur Windows/macOS. Les tests Tk/Xvfb vérifient le nombre d'instances de sprites, mais ne certifient pas leur qualité artistique.

## Hors périmètre

- Préservation des retouches tactiques locales lors d'une transformation.
- Bâtiments multi-étages jouables superposés.
- Historique inter-éditeurs, commandes de groupe et refonte de l'agencement des panneaux (3.7.21).
