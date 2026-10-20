# R54.B — World Streaming Inspector (Studio)

**Portée :** inspection et authoring visuel sans JSON du contrat R54.A.
La navigation streaming réelle Player, les sprites/atlas/LOD GPU,
la parité export et la certification p95/p99 restent à R54.C.

## Ouvrir l'inspecteur

Dans le Studio Qt6 : **Outils → World Streaming Inspector R54…**.
La commande figure aussi dans la palette de commandes du Studio.

Si un manifeste `org.drawtemp.streaming` existe, l'inspecteur affiche les
cellules, leurs régions, les scènes canoniques et les arêtes. Les données
proviennent du `GameProject` actuel et sont validées par R54.A.

Si aucun manifeste n'existe, préparer d'abord dans le projet des
`scene_routes` R25 entre scènes d'exploration, avec un lien retour pour
chaque traversée. Cliquer sur **Construire depuis les portails R25**.
Le générateur :

1. part de la scène R25 `start` ;
2. conserve uniquement les arêtes réciproques entre scènes d'exploration ;
3. calcule le composant accessible, trié et reproductible ;
4. utilise les IDs des scènes comme IDs stables de cellules ;
5. produit des régions `world`, personnalisables par sélection de cellule.

Le générateur n'ajoute pas de portails, d'assets ou d'inventaire fictifs.
Les scènes non retenues sont signalées. Une route unidirectionnelle n'est
pas implicitement rendue bidirectionnelle.

## Edition transactionnelle

Sélectionner une cellule pour modifier son `region`, puis **Modifier
région (brouillon)**. Le budget est réglable de 1 à 32 MiB. Les changements
restent locaux à la boîte de dialogue jusqu'à **Prévisualiser** puis
**Appliquer (1 Undo)**. Le chemin utilise exclusivement
`AuthoringSession.preview_project` puis `AuthoringSession.apply`.

Si la révision du Studio change entre l'ouverture et l'application,
la transaction périmée est refusée. **Actualiser le projet** relit les
données actuelles et abandonne le brouillon local. Undo et Redo restent
ceux du Studio R1 : aucun fichier JSON n'est écrit directement.

## LOD, liens et préchargement

Le graphe montre le nombre de régions, les arêtes bidirectionnelles, la
distance topologique au focus et trois niveaux *conceptuels* :

- `detail` : focus en zoom ≥100 %, voisins en zoom ≥200 % ;
- `overview` : focus et voisins en zoom ≥50 % ;
- `outline` : cellules distantes ou zoom réduit.

Le mode `detail` affiche en miniature les 8×4 premières cases de la
scène d'exploration (cases bloquées marquées) ; `overview` affiche région et
dimensions ; `outline` réduit la cellule à un repère. Le graphe est un
viewport de diagnostic, **pas** un renderer de jeu certifié. Ce ne sont
**pas** des niveaux de rendu 2D/2.5D réellement installés dans le renderer.
L'estimation des octets de grille est une heuristique
`width × height × 16 + blocked × 16`, pas une mesure GPU.

**Précharger autour** dépose au plus 8 tickets sur le cache R54.A (focus,
puis voisins BFS stables). Un chargeur fourni par le Studio importe
uniquement les métadonnées détachées des scènes (`id, scene, size, blocked`).
Le widget met à jour les octets résidents **effectifs** de
`WorldCellCache.stats()`. Les tickets sont annulés en changeant de
manifeste ou en fermant la fenêtre; une complétion tardive est ignorée.

## Vérification

```sh
python -m unittest tests_standalone.test_r54_world_streaming \
  tests_standalone.test_r54_streaming_inspector -v

# Avec PySide6 installé, sous environnement Qt offscreen :
QT_QPA_PLATFORM=offscreen python -m unittest \
  tests_standalone.test_r54_streaming_inspector_qt -v
```

Tests : génération depuis des portails réciproques, exclusion des routes
incomplètes, graphe/LOD reproductible, prefetch borné, corruption de
télémétrie rejetée, prévisualisation sans mutation, transaction et Undo/Redo,
révision périmée, cache fermé à la fermeture de la fenêtre.

**Gate R54 : non atteinte.** R54.C doit ajouter les branchements du Player
et sa traversée en continu, avec des preuves sur machines réelles.
