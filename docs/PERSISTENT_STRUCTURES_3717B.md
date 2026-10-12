# 3.7.17B — Identités persistantes des structures

## Problème et résolution

Avant ce lot, une maison, un pont ou une tour était détecté uniquement si les
cases de son tampon de terrain correspondaient encore exactement au preset.
Modifier une case suffisait donc à faire disparaître tout le sprite.

`place_structure` écrit désormais les mêmes tuiles tactiques et enregistre,
en plus, une identité visuelle **optionnelle** dans `Mission.structures` :
`id`, `name`, `anchor`, `turns` et `door_slot`. La présentation utilise
l'identité pour calculer le sprite et son ancrage ; les collisions,
hauteurs, dégâts, mouvement, CT et IA lisent exclusivement les tuiles.

Les nouvelles maisons, tours, ruines, ponts, remparts et escaliers gardent
leur représentation après retouche locale du sol ou d'un mur. Le Studio
propose **Supprimer structure**, qui efface explicitement la métadonnée
et le tampon complet, dans une seule transaction annulable. Modifier une
seule tuile ne supprime jamais implicitement la structure.

## Compatibilité

- Les anciennes cartes **sans** `structures` sont chargées et réémises
  sans ce champ. Leur reconnaissance des bâtiments reste inchangée.
- Les cartes mixtes dessinent en priorité les structures explicites,
  puis déduisent les autres uniquement sur leurs tuiles intactes ;
  aucune zone ne reçoit deux instances.
- Un enregistrement hors carte, mal formé, de variante invalide,
  d'identifiant dupliqué ou chevauchant un autre est refusé.
- Les replays et sauvegardes anciens ne sont pas migrés silencieusement.
  Ajouter de nouvelles structures à un projet change normalement son
  empreinte de contenu et peut rendre une ancienne sauvegarde
  incompatible, conformément au contrat de `GameSession`.
- Le copier-coller **de terrain seul** n'embarque pas les identités :
  ce comportement est volontaire et suit celui des objets/acteurs.

## Reproduction et test

```sh
python -m unittest discover -s tests_standalone -p test_iso_persistent_structures_3717b.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_iso_persistent_structures_3717b_gui.py -v
python -m unittest discover -s tests_standalone -v
```

Parcours visuel : placer une maison avec entrée B et rotation, modifier un
mur, sauvegarder, rouvrir puis jouer la mission. L'image doit rester ;
supprimer le bâtiment puis undo doit la restaurer. Même renderer
isométrique entre Studio et Player standard.

## Limites

Les métadonnées décrivent des structures **mono-niveau** et n'introduisent
aucun étage tactique. Le déplacement de groupes de structures, leurs
variantes artistiques définitives et la continuité avec le Player château
appartiennent aux prochains jalons. Un ancien binaire qui ne connaît pas
le nouveau champ n'est pas garanti capable de lire une carte nouvelle.
