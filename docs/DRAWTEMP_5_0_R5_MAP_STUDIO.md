# DrawTemp 5.0 — R5 Map & World Editor (première tranche)

Cette PR livre une **tranche exécutable** de R5 sans attendre R2/R3/R4. Elle ne
déclare **pas** les 14 lots R5 validés. Le prototype Qt Quick affiche des
surfaces/propriétés canoniques; il sera remplacé par le renderer GPU **partagé**
de R3, et non maintenu en parallèle dans la livraison 5.0.

## Utilisation

Sous Python 3.12 :

```sh
python -m pip install ".[qt6]"
python -m drawtemp.studio.map_editor
# Charger un couple Content + GameProject existant :
python -m drawtemp.studio.map_editor --content chemin/jeanne.json
```

L'éditeur ouvre par défaut la fixture de migration Jeanne, sans modifier les
fichiers embarqués. « Nouvelle carte » crée une mission sur les modèles
canoniques, avec unités jouables. Un geste de pinceau, rectangle, ligne,
remplissage, structure ou collage = **une transaction Undo**.

- **R5.1 (partiel)** : liste des missions, création, duplication, renommage,
  changement de carte ; dossiers et navigation avancée restent à faire.
- **R5.2 (branché à R3)** : `IsoViewport.qml` en Qt Quick Scene Graph, caméra et picking partagés, peinture par gestes, grille, acteurs,
  objectifs. Ce n'est pas encore le renderer GPU R3.
- **R5.3** : pinceau, rectangle, ligne, gomme, remplissage, pipette, objectif,
  couvert, collision, danger, hauteur.
- **R5.4 (SDK)** : empreinte de pinceau intelligent via `smart_brush_cells`
  existant, validée transactionnellement. Commande GUI à compléter.
- **R5.5 (partiel)** : palette de surfaces ; vignettes atlas, drag-drop et
  curseur fantôme enrichi encore à raccorder à R4.
- **R5.7 (partiel)** : sélection rectangulaire + copie/collage de terrain ;
  transformations, multi-objets et groupes restent à faire.
- **R5.9 (partiel)** : renommage et objectif, sans modification de schéma.
- **R5.12** : affichage collision, hauteur, unités et objectifs.
- **R5.13 (partiel)** : avertissements de cases objectif inaccessibles ; les
  validations structurelles sont déléguées au modèle canonique.
- **R5.14 (partiel)** : prévisualisation révisionnée, sauvegarde atomique
  Content + GameProject, Undo/Redo, playtest **headless isolé**. Le lancement
  d'un Player Qt interactif attend R12.

Non livrés : R5.6 Layers Workspace, R5.8 Prefabs & Groups (GUI), R5.10
génération procédurale (GUI), R5.11 intégration carte du monde (GUI).
Les API legacy correspondantes peuvent déjà exister mais leur intégration 5.0
ne doit pas être considérée comme certifiée.

## Architecture

`drawtemp.studio.map_authoring.MapStudio` est une façade **sans dépendance Qt
ou Tk**. Elle modifie uniquement `Content` via les fonctions métier existantes
et `AuthoringSession.preview_pair/apply`. `GameProject` demeure la seule
source de vérité pour les données de présentation/campagne. Aucun nouveau
format `map.json`, aucune seconde pile Undo et aucun modèle tactique parallèle.

Les prévisualisations portent `revision` et `mission_id`; une modification,
un Undo, ou le changement de mission rendent l'aperçu obsolète. Les erreurs
de validation ne mutent pas les documents. L'enregistrement exige les deux
fichiers et leur protocole R1 de récupération explicite.

## Vérification

```sh
python -m unittest tests_standalone.test_drawtemp5_r5_map -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.studio.map_editor --smoke
```

CI dédiée Python 3.10 / 3.12 (headless) et Python 3.12 Qt Quick (offscreen).
Elle ne mesure ni FPS GPU ni qualité visuelle.

## Gate R5 non clôturé

Objectif du gate : village iso avec rivière, pont, maison, personnages et
objectifs, créé et **joué dans le Player** sans JSON. Cette PR fournit les
commandes de création visuelle, la sauvegarde et la simulation tactique
isolée, mais le gate final dépend de R3 (renderer commun), R4 (atlas) et R12
(Player). Les captures, goldens et vérifications sur GPU réel restent à
produire avant de marquer R5 « validé ».

### Intégration R3 (PR #237)

Le `MapWindow` n'utilise plus de renderer QML `Canvas` : la projection des missions validées `Content` est fournie à `RendererController` et affichée par `IsoViewport.qml`. Les gestes `strokeStarted/Moved/Finished` repassent par `MapStudio` (transaction et Undo/Redo inchangés). La vérification du rendu sur GPU matériel et des étages reste distincte du smoke Qt offscreen.


## Suite R5.6 — Layers Workspace (PR dédiée)

Le dock **Calques** du Studio Qt utilise directement les dix domaines
\`sporebound.map_layer_workspace.LAYERS\` : Terrain, Relief, Décors,
Bâtiments, Toitures, Déploiement, Objectifs, Objets, Unités, Étages.

- **Visibilité** par carte dans le viewport R3 partagé. La structure
  géométrique reste disponible pour le picking, sans mutation de Content.
  Les calques actuellement projetés en R3 (terrain, décors, murs, objets,
  acteurs, objectifs) répondent aux contrôles. Les superpositions
  spécifiques toitures/déploiement/étages attendent R6 et R5.12.
- **Verrouillage réel** des modifications via \`changed_layers\` /
  \`ensure_unlocked\`, contrôlé avant \`AuthoringSession.apply\` : peinture,
  bâtiments, objectifs et autres commandes ne peuvent pas contourner le
  verrouillage. Les opérations sur un autre domaine restent autorisées.
- **Niveau actif** 0–3, enregistré en tant que réglage d'éditeur et
  distinct de la hauteur tactique de chaque case.
- **Opacité** réglable par calque côté Studio uniquement, conservée pendant
  la session ; sa persistance attend une migration versionnée du sidecar
  (pas de nouvelle clé silencieuse en version 1).
- **Persistance** : le sidecar existant \`*.mapbuilder-view.json\` conserve
  les réglages d'éditeur lors de \`save\`/\`save_as\` et les restitue
  à l'ouverture. Il ne modifie ni Content, ni GameProject, ni les sauvegardes.
- **Fiabilité** : Undo d'une mission nouvellement créée répare la sélection
  active plutôt que laisser le dock sur une mission supprimée.

Gates supplémentaires :
\`\`\`bash
python -m unittest tests_standalone.test_drawtemp5_r5_layers -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_drawtemp5_r5_layers_qt -v
\`\`\`

Cette tranche ne certifie pas le gate de R5 complet. Le support visuel des
étages/toitures, l'opacity persistante, les captures GPU et le parcours de
création du village jusqu'au Player restent à intégrer/tester.

## Suite R5.4 + R5.5 — Smart Brushes et palette illustrée (PR empilée sur R5.6)

### Ce qui est livré

- **Pinceau intelligent** : rayon de 0 à 3, empreinte losange ou carrée,
  interpolation déterministe des gestes rapides. Un glisser de souris =
  une commande du SDK R1 et un seul Undo/Redo.
- **Aperçu révisionné** : l'empreinte du pinceau et ses voisins immédiats
  sont projetés dans `IsoViewport.qml` sans mutation de Content. L'application
  utilise exactement le plan validé; changement de révision, annulation ou
  changement de mission rejettent toute tentative de commit périmée.
- **Préservation** : le pinceau intelligent épargne les empreintes d'acteurs,
  objectifs, objets et structures, ainsi que les décors significatifs déjà
  placés. L'outil Pinceau classique reste disponible pour les retouches
  explicitement voulues.
- **AutoBlend partagé R3/R12** : les raccords entre surfaces terrestres
  utilisent `sporebound.terrain_autoblend.blend_edges` et
  `blend_polygon`. La scène Qt Quick reçoit des polygones GPU; aucun
  nouveau champ n'est écrit dans Content ni GameProject. Les limites de
  relief bloquent le raccord. La logique du Player est identique.
- **Palette R5.5** : tuiles du véritable atlas de terrain, échantillons
  illustrés de végétation, vignettes de décors, recherche accent-insensible,
  filtres Terrain/Décors et sélection persistante pendant l'édition.
  Identifiants de peinture canoniques `surface:*` et `feature:*`.
- **Drag/drop** : MIME `application/x-drawtemp-map-brush`, strictement validé
  contre le catalogue connu, déposé sur le viewport R3 après picking
  isométrique commun. Aucun chargement de fichiers glissés non fiables.

### Démonstration

```bash
python -m pip install ".[qt6]"
python -m drawtemp.studio.map_editor
```

Sélectionner un carreau dans le dock **Palette illustrée** ; choisir
**Pinceau intelligent**, le rayon et la forme ; survoler la carte pour
prévisualiser les cellules touchées et les voisins affectés. Un glisser
applique la transaction. Une vignette peut également être déposée sur la
carte pour appliquer le pinceau choisi.

### Vérification

```bash
python -m unittest tests_standalone.test_drawtemp5_r5_smart_palette -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_drawtemp5_r5_smart_palette_qt -v
```

Les snapshots du Studio et du Player utilisent `scene_from_mission` et
`render_items` communs : une transition calculée est identique dans les
deux processus. Le rendu logiciel Qt offscreen ne certifie toujours pas
l'apparence sur GPU réel, la qualité artistique de tous les décors ni les
performances grands formats. Les raccords aquatiques restent liés au
système existant de berges/ponts, à intégrer visuellement en R3.B.
