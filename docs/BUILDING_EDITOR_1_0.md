# Studio UX — Building Editor 1.0

## Pourquoi

La barre `Carte & monde → Architecture` empilait en permanence des commandes
sans rapport avec la carte vide : portes, fenêtres, toiture, groupe de
structures et niveaux intérieurs. À faible hauteur, elle masquait la carte.

## Parcours livré

1. Dans la navigation supérieure, choisir **Bâtiments**.
2. La carte existante reste visible (2D ou iso 2.5D), avec une bande
   d'actions minimale : **Sélectionner bâtiment**, **Poser une structure**,
   **Ouvrir l’éditeur de bâtiments**.
3. Le panneau de droite s'ouvre sur **Bâtiments**, avec le nom/identifiant et
   l'ancre de la structure sélectionnée, ou un message explicite quand aucune
   structure n'est sélectionnée.
4. Trois onglets indépendants et défilants regroupent les commandes :
   - **Général** : structures, déplacement, duplication, rotation, entrée,
     propriétés, opérations groupées.
   - **Extérieur** : façade, toiture, pose/suppression de fenêtres.
   - **Intérieur** : coupe de toiture, étages, sols et mobilier.
5. Le bouton **Retour carte** restitue l'espace de travail Carte & monde.
   Un bouton de l'inspecteur standard permet aussi d'entrer dans Bâtiments.

Les palettes **Acteurs et objets** et **Bibliothèque d'assets** sont dans
**Sélection & modèles**, et non dans l'inspecteur de bâtiment. Les commandes
inapplicables sont désactivées tant qu'aucune structure compatible n'est
sélectionnée.

## Architecture et compatibilité

- **Un seul** Notebook principal, Canvas de carte, renderer, moteur de
  commandes et schéma de sauvegarde. Bâtiments est un mode de `Carte et combat`,
  pas un deuxième fichier ou une duplication de l'éditeur.
- La navigation `StudioNavigation` expose une entrée synthétique
  « Éditeur de bâtiments » sans nouvel onglet gameplay. Elle reste synchronisée
  lors des navigations directes depuis l'explorateur ou les autres éditeurs.
- Conservation des callbacks existants : `StructureCommand`,
  `edit_structure`, `edit_building_appearance`,
  `interior_levels.py`, `level_navigation.py`, validations de `Content`,
  sauvegarde et Undo/Redo.
- La coupe de toiture et les fenêtres décoratives restent distinctes des
  portes et passages jouables : aucun effet tactique implicite nouveau.
- Aucune conversion du projet, migration, ou nouvel objet sérialisé n'est
  introduit.

## Contrôles de non-régression

```bash
python -m unittest tests_standalone.test_studio_layout_2026 -v
python -m unittest tests_standalone.test_map_builder4_3732b -v
python -m unittest tests_standalone.test_interior_levels_3720b -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_studio_layout_2026 \
  tests_standalone.test_map_builder4_3732b_gui -v
```

### Validation manuelle

- Carte vierge : pas de commandes de fenêtre/étage dans la barre supérieure ;
  l'espace Bâtiments explique comment sélectionner ou poser une structure.
- Maison : sélectionner, appliquer façade/toiture, poser une fenêtre,
  déplacer/dupliquer, créer un étage, y peindre du mobilier ; sauvegarder,
  recharger puis Annuler/Rétablir.
- Tour et ruines : n'activer que les commandes compatibles avec le modèle.
- Tester le retour Carte, le passage vers Projet et Événements, puis revenir
  sur Bâtiments sans remplacer le Canvas ni perdre la sélection.
- Vérifier la lisibilité à 1280×720 et le scroll de l'inspecteur.

## Suite (non incluse)

Une édition isolée de l'emprise avec aperçu 2.5D centré, la bibliothèque
visuelle de bâtiments et les opérations fines mur/porte/escalier pourront
venir ensuite, mais nécessitent des gates UX/Player distinctes.
