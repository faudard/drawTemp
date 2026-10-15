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

## R5.7 — Selection & Transform (tranche Qt)

### Parcours sans JSON

1. Choisir **Sélection** pour tracer un rectangle ou **Lasso** pour
   sélectionner une région polygonale. L'option **Ajouter à la sélection**
   permet plusieurs zones disjointes, sans perdre les cases déjà retenues.
2. **Copier** (`Ctrl+C`) capture un presse-papiers indépendant et immuable
   des cases terrain/décors et des objectifs de mission. **Coller**
   (`Ctrl+V`) engage un placement en aperçu. Les identifiants d'unités,
   d'objets et de bâtiments ne sont *jamais* dupliqués implicitement.
3. **Déplacer sélection** (`Ctrl+M`) transfère le relief, les surfaces,
   les caractéristiques tactiques, les décors et les objectifs sélectionnés.
   Les personnages/objets placés dans la sélection sont déplacés avec leurs
   identifiants stables, sauf incompatibilité de leur emprise.
4. **Dupliquer sélection** (`Ctrl+D`) laisse la zone initiale intacte
   puis prévisualise une nouvelle zone. La duplication de personnages et
   d'objets avec liens est explicitement refusée : utiliser leurs
   éditeurs pour créer des identifiants distincts.
5. **Rotation ↻/↺** (`Ctrl+R` / `Ctrl+Shift+R`) et **Miroir
   horizontal/vertical** (`Ctrl+H` / `Ctrl+J`) prévisualisent
   une modification *en place*. Les opérations utilisent le contrat
   `sporebound.map_transform.transform_terrain`.
6. Dans l'outil **Placement sélection**, déplacer la souris pour voir
   une empreinte colorée ; le **rouge** signifie que la prévalidation
   refuse le placement. Cliquer **Appliquer aperçu** ou appuyer sur
   `Entrée` pour créer **une seule transaction Undo/Redo**, ou
   **Annuler aperçu** / `Échap` pour quitter sans toucher au document.

### Intégrité et limites

- Un seul `AuthoringPlan` R1 par opération, construit sans mutation puis
  validé à nouveau à l'application. Révision obsolète, changement de
  mission, tentative hors limites, destination déjà éditée, unité
  étrangère ou calque verrouillé : **refus avant changement de Content**.
- Les formes sont des ensembles explicites de cases (avec trous possibles).
  Le lasso est échantillonné sur la grille isométrique via le picking R3.
- Toute emprise touchant une structure persistante/son étage, un escalier
  relié, une zone de déploiement, une relique ou un déclencheur narratif
  doté de coordonnées est refusée. L'édition de ces identités et de leurs
  liens relève des ateliers Construction R6 / Événements R9.
- Les calques non modifiés ne changent pas ; le verrouillage par domaine R5.6
  s'applique aux transformations autant qu'aux pinceaux.
- La sélection, les plans et les overlays de fantôme sont **éphémères** :
  ni `GameProject`, ni `Content`, ni une sauvegarde Player ne stockent
  de métadonnées d'outil. Les créations finales restent rechargeables
  dans le même format canonique.

### Gates

```bash
python -m unittest tests_standalone.test_drawtemp5_r5_selection -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_drawtemp5_r5_selection_qt -v
```

Le smoke Qt certifie le parcours fonctionnel **hors GPU matériel**.
Le gate R5 global (village jouable, rendu artistique certifié, packaging)
reste ouvert indépendamment de la fusion du lot R5.7.
