# 3.7.33A — Inspecteur universel éditable

Le Workspace 3.7.31 reste le point de navigation. Cette évolution rend
**les propriétés usuelles directement modifiables dans le panneau Inspecteur**,
sans créer de nouveau modèle de ressources, de JSON métier ou de moteur
d'événements. Les éditions approfondies restent dans les éditeurs spécialisés.

## Parcours auteur

1. Ouvrir **Espace projet**, sélectionner un acteur placé, objet interactif
   ou groupe hiérarchique. Ses propriétés éditables s'affichent sous le résumé.
2. Modifier uniquement les champs autorisés pour le type choisi :
   - acteurs : nom, équipe, orientation ;
   - objets : réglages de leur type actuel (porte : PV/verrouillage,
     levier/engin : porte cible, etc.) ;
   - groupes : nom du groupe. Parentage et déplacements restent dans
     « Groupes et appartenances » pour préserver le contrat d'édition.
3. Cliquer **Appliquer les propriétés** : une transaction, validation du
   Content, mise à jour du Workspace, Historique/Undo/Redo habituels.
4. Pour le terrain, sélectionner une case sur la carte et cliquer
   **Inspecter la case sélectionnée** dans le Workspace : surface, décor
   et hauteur sont éditables via les pinceaux normaux.
5. Double-cliquer une référence de l'inspecteur pour rejoindre l'éditeur
   existant. Les propriétés non couvertes ne sont pas éditées ici.

## Contrat d'architecture

- `workspace_editing.editable_form(data, key)` retourne une projection
  headless, une liste blanche de champs et une empreinte de la ressource.
- `WorkspacePropertyCommand` refuse les changements hors liste blanche,
  les valeurs invalides, les clés périmées et une ressource modifiée
  depuis l'ouverture du formulaire.
- `EditingContext.execute` applique exactement une modification validée,
  avec `Document.replace` et la sauvegarde/historique actuels.
- `EntityCommand`/les fonctions `entity_editing.edit_entity` demeurent
  la source des règles des entités. Les groupes passent par
  `editor_groups.rename_editor_group` et les cases par `Document.paint_many`.
- Aucun fichier de données supplémentaire ; `Content` et `GameProject`
  conservent leurs contrats et les références existantes.

## Gate de vérification

- Depuis l'arbre Workspace, renommer Ziggy, constater le changement
  immédiatement, Annuler puis Rétablir.
- Modifier un levier pour cibler une porte sans référence ; l'alerte du
  panneau Problèmes doit disparaître sans commande « Rafraîchir ».
- Renommer un groupe persistant sans perdre ses membres/descendants.
- Éditer surface + décor + hauteur d'une case en une action Undo.
- Tentatives invalides : supprimer le lien requis, changer une propriété
  non autorisée, référence périmée, valeur hors domaine. Aucune mutation
  ni entrée d'historique dans ces cas.

Tests :

```bash
python -m unittest tests_standalone.test_workspace_editing_3733a -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_workspace_editing_3733a_gui -v
```

Le chantier **3.7.33B**, distinct, portera sur la synchronisation
bidirectionnelle de la navigation carte/arbre/inspecteur et l'historique
précédent/suivant. Il n'est pas implicite dans ce lot.
