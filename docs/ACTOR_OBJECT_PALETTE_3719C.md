# 3.7.19C — Palette d'acteurs, poses et objets interactifs

## Portée

Cette livraison prolonge la bibliothèque d'assets **existante** : aucune seconde
palette, aucun nouveau renderer et aucun schéma JSON/replay. Les entrées
supplémentaires sont construites à partir des archétypes du `Content`, des
unités de la mission courante et des sept types d'objets tactiques déjà compris
par le moteur : porte, levier, coffre, bélier, catapulte, passage et défense.

Le jalon 3.7.19B (édition des structures) est indépendant. Branche 3.7.19C
créée directement depuis `master` `ef88ca5`.

## Parcours utilisateur

1. Ouvrir le Map Editor, choisir **Bibliothèque d'assets**.
2. Choisir **Acteurs** ou **Interactions** (recherche textuelle disponible).
3. Pour un acteur, renseigner éventuellement l'identifiant (vide = généré),
   le nom, l'équipe, l'orientation initiale. **Pose (aperçu)** permet de voir
   les frames `idle` et `move` de l'atlas existant ; elle n'introduit pas un
   état d'animation persistant artificiel. L'orientation est bien enregistrée
   comme `Unit.facing`.
4. Pour un levier, un bélier ou une catapulte, indiquer l'ID d'une porte
   existante. Pour un passage, indiquer sa sortie `x,y`.
5. Cliquer sur **Utiliser sur la carte** puis sur la case cible. Le
   survol affiche une empreinte verte/rouge et, si disponible, le sprite
   existant de l'acteur ou le repère vectoriel de l'objet.
6. Annuler/Rétablir, Enregistrer sous, réouvrir puis Playtest utilisent les
   chemins de validation et d'exécution déjà présents.

Chaque pose d'un même élément avec ID laissé vide obtient un nouvel identifiant
unique. Les copies de personnages présents dans la mission sont des *snapshots*
des données de jeu (PV/MP initiaux, CT et états de tour réinitialisés) ; les
archétypes demeurent liés à leur définition existante. Les unités et objets
ne sont jamais écrits lors d'un survol de souris.

## Garanties et limites

- `place_palette_entity` appelle `authoring._edit` ou `add_object` et
  valide toute la mission via `Content.from_dict` et le ruleset authored.
  Un déplacement illégal, chevauchement, lien de porte manquant, sortie hors
  carte, identifiant dupliqué, etc. laisse `Document` intact.
- Le test rapide du survol sert uniquement d'indication UX ; seul le validateur
  complet tranche lors du clic. Il n'est **pas** un moteur de règles parallèle.
- Le PNG chibi 3.7.19A est réutilisé à toutes les échelles (24–96) avec
  fallback sans PNG. Les objets n'ont pas encore de sprites dédiés : ce sont
  les mêmes marqueurs vectoriels que ceux du renderer partagé.
- Aucune nouvelle `pose` n'est persistée dans `Content` ; le mouvement en
  combat reste piloté par `MotionDirector`. Le côté esthétique n'est pas
  considéré comme validé tant que captures Windows/macOS et Player n'ont
  pas été examinées.
- La palette ne configure pas encore tous les champs avancés de combat
  ou les liens événementiels complexes : cela reste au Character/Bestiary
  Studio et au futur éditeur d'événements contextualisé 3.7.21C.

## Vérification

```sh
python -m unittest tests_standalone.test_entity_palette_3719c -v
SPOREBOUND_GUI_SMOKE=1 python -m unittest tests_standalone.test_entity_palette_3719c_gui -v
```

À vérifier aussi manuellement sur la scène de Valcroix : zoom 24/54/96,
orientation d'un acteur, levier relié à une porte, emplacement invalide,
Undo/Redo, sauvegarde/rechargement, interaction dans le Player et disposition
de la palette sur écrans compacts. Ne pas confondre tests ajoutés avec CI verte.

## Approfondissement : inspection et édition des instances

La palette ne se limite plus à créer de nouvelles entités. Le bouton
**Inspecter acteur / objet** ou l'outil **Inspecter entité** ouvre un panneau
contextuel sur une case de la scène. L'inspecteur propose un sélecteur lorsque
plusieurs entités partagent la même case ; les acteurs multicases sont
sélectionnés sur toute leur emprise, pas seulement sur leur origine.

- **Acteur :** nom, équipe et orientation initiale modifiables, avec aperçu
  de l'atlas existant dans les deux poses disponibles (immobile / marche).
  L'orientation est persistée et utilisée par le renderer Studio/Player.
- **Objets :** porte (PV, verrouillage), coffre (contenu), levier (porte
  liée), engins de siège (porte cible, puissance, équipe, munitions),
  passage (destination, coût, disponibilité, sens), défense (équipe,
  puissance, charges, état).
- **Manipulation :** « Déplacer au clic » et « Dupliquer au clic »
  réutilisent les modèles existants. L'identité d'une entité déplacée
  demeure stable ; une copie reçoit une nouvelle identité. Les cellules
  de défense et patrouilles suivent leur entité à déplacement/duplication.
  La destination d'un passage reste absolue par conception.
- **Suppression :** les références doivent rester valides. Supprimer une
  porte utilisée par un levier, ou la dernière unité d'une équipe requise,
  est refusé par `Content` ; rien n'entre dans l'historique.
- **Palette de placement :** les objets nécessitant une porte proposent
  maintenant une liste des portes existantes. Un passage exige une
  destination `x,y` lisible avant d'entrer en mode placement.

L'interface affiche une cible **bleue informative** lors d'un déplacement
ou d'une duplication, car la validité tactique finale dépend de l'ensemble
des règles. Aucune réussite n'est promise par le simple survol.

### Tests de cette extension

```sh
python -m unittest tests_standalone.test_entity_editing_3719c -v
SPOREBOUND_GUI_SMOKE=1 python -m unittest tests_standalone.test_entity_editing_3719c_gui -v
```

Ces commandes sont des gates à exécuter sur les SHA publiés, pas des
résultats de tests déclarés. Également vérifier des acteurs ayant une
patrouille, le refus de retirer une porte référencée et la manipulation
à 24/54/96 sous Windows, macOS et Tk/Xvfb Linux. La branche est en brouillon
et ne prétend pas fournir des sprites d'attaque, de dégâts ou de mort :
l'atlas isométrique n'offre actuellement que deux frames disponibles
par direction. L'animation de combat doit rester synchronisée avec
`MotionDirector` dans un lot artistique distinct.
