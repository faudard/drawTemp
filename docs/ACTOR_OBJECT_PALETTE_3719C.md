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
