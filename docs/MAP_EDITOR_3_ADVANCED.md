# Map Editor 3.0 — Outils avancés (2.5.1)

Ce complément étend [la fondation Map Editor](MAP_EDITOR_3.md) sans introduire
de nouveau schéma de combat ni modifier la simulation, les replays ou les
sauvegardes. Les opérations restent des transformations de données validées
par `Content.from_dict` avant chaque commit dans `Document`.

## Rotation, symétrie et modèles réutilisables

1. En mode **Sélection**, choisir une zone sur la carte et **Copier cases**.
2. Utiliser **↻ 90°**, **↺ 90°**, **⇄ Sym. H** ou **⇅ Sym. V**. L'outil
   passe en **Collage** pour présenter le résultat. La taille de la zone
   englobante s'adapte aux rotations à 90°.
3. Choisir une case de destination pour coller. Une transformation ne modifie
   jamais les unités/objets et conserve les cases creuses des sélections
   irrégulières ainsi que les cases d'objectifs.
4. Utiliser **Sauver modèle** pour créer un fichier `.stamp.json` indépendant
   des missions. **Charger modèle** recharge ce modèle et prépare le collage
   dans n'importe quelle mission compatible.

Format portable : `kind=sporebound_terrain_stamp`, `version=1`,
`name`, `size`, `cells` (position relative + propriétés de terrain)
et `goals`. Les fichiers inconnus, trop volumineux (2 Mio max),
malformés ou contenant des propriétés non prises en charge sont refusés.
La sauvegarde utilise un remplacement atomique. Les fichiers sont des
données JSON, jamais des scripts exécutables.

**Un modèle ne duplique pas de héros, monstres, événements ou objets de
siège** : leurs IDs et références doivent continuer à être authorés et
validés explicitement.

## Déplacer un groupe d'objets et personnages

En mode **Sélection**, choisir les cases des unités/objets à déplacer, puis
utiliser les flèches du groupe `← ↑ ↓ →`. Une unité occupe une ou plusieurs
cases : sélectionner n'importe laquelle de son empreinte prend l'unité
entière. Les groupes peuvent contenir plusieurs unités et plusieurs objets.

- Les IDs, liens vers les portes et identités de personnages sont conservés.
- Les défenses déplacent leur zone d'effet avec elles.
- Les destinations des passages et les itinéraires de patrouille restent
  des positions **absolues** : ils ne sont pas translatés implicitement.
- Les collisions, empreintes multi-cases, déploiements, limites de carte
  et autres règles sont validés sur **l'ensemble du déplacement**.
- Un refus ne modifie rien ; un mouvement accepté est annulable/rétablissable
  en une seule opération.

## Zoom et vue tactique

Les boutons `−`/`+` changent la dimension de case entre 24 et 96 pixels.
La nouvelle **Vue tactique** (mini-carte, dans le panneau de droite) montre
les terrains spéciaux, objectifs, positions d'unités/objets, déploiements
et cadre de vue. Cliquer dessus permet de recentrer la carte principale.
La visibilité obéit aux interrupteurs de couches de l'éditeur.

Cette vue est **une mini-carte fonctionnelle**, pas un renderer de sprites
2.5D : le rendu artistique complet appartient à 2.6 Player & Presentation.

## Tests et gate de compatibilité

```sh
python -m unittest discover -s tests_standalone -p 'test_map_transform.py' -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_map_editor_gui.py -v
```

Cette PR inclut aussi le correctif de récupération des fichiers de sessions
profondément imbriqués : Python 3.10 peut lever `RecursionError` dans
`json.loads` alors que Python 3.12+ lève `JSONDecodeError`. Ces deux
erreurs sont désormais normalisées en `RuleError` pour assurer le
fallback vers le backup vérifié.

## À faire pour clôturer 2.5.1

- Tilesets graphiques réels et attributs visuels associés (assurant une
  séparation moteur/rendu et un packaging portable des assets).
- Composition visuelle d'objets multi-cellules et d'éléments animés.
- Édition guidée des déclencheurs et des zones avec l'Event Graph 2.5.2.
- Undo/Redo transversal au projet avec transactions entre missions,
  pas uniquement les transformations dans la mission en cours.
