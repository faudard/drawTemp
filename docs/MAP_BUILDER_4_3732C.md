# 3.7.32C — Map Builder 4.0 : calques visuels, verrous et niveau actif

## Problème

Le Map Editor possède déjà ses calques Tk (Terrain, Relief, Décors, Bâtiments,
Toitures, Déploiement, Objectifs, Objets, Unités), sa sélection, les coupes de
toiture et les niveaux tactiques. Il manquait une distinction exploitable entre
**masquer une couche** et **protéger ses données**, ainsi qu'une restauration
du contexte de travail entre deux sessions.

## Parcours dans le Map Editor

1. Dans **Terrain & couches**, les cases **Toitures** et le menu
   **Autres couches** contrôlent uniquement le rendu. La couche **Étages**
   est ajoutée pour les plateaux superposés.
2. Le nouveau menu **Verrouiller couches** protège les modifications de
   chaque domaine. Un pinceau terrain peut toujours peindre une case dont
   seul le décor est verrouillé, et inversement. Un déplacement d'acteur
   reste possible même si le terrain sous ses pieds est verrouillé.
3. Choisir **Niveau actif 0–3**. Le niveau 0 correspond au terrain habituel,
   les niveaux 1–3 aux plateaux intérieurs réellement créés. Une sélection
   d'étage inexistant est refusée, sans générer de données de jeu.
4. Le clic **Intérieurs / coupe des toits** et le raccourci Ctrl+I continuent
   d'utiliser la coupe existante. Les caméras, le moteur et les acteurs du
   Player ne sont pas modifiés.
5. Changer de mission puis revenir restaure ses préférences. Fermer/réouvrir
   le même fichier les restaure également.

## Architecture

Nouveau module headless : `sporebound/map_layer_workspace.py`.

Les préférences par mission sont enregistrées dans un fichier séparé,
par exemple `content.json.mapbuilder-view.json`. C'est une **préférence
locale de l'éditeur**, pas un contenu exporté dans le Player. Le format JSON
versionné inclut des cartes explicites `visible` et `locked`, un entier
`active_level` dans 0–3 et le booléen `interiors`. Les données sont
strictement validées et publiées par `storage.write_json` (remplacement
atomique). Aucun champ n'est ajouté à Content, GameProject ni Battle.

La politique d'édition `Document.edit_policy` est consultée **après**
la validation métier et **avant** la modification des piles Undo/Redo.
Elle évalue les domaines de données réellement modifiés plutôt que le nom
de l'outil : terrain (surface/collision/coût/danger), relief, décors,
structures, toiture, intérieurs/liaisons entre niveaux, entités,
déploiement et objectifs. Les modifications interdites ne laissent aucune
trace dans Document ni son historique.

Les modifications multi-cases reconstruites après un glissement passent
également par la même vérification. Undo/Redo reste disponible sous
verrouillage pour récupérer les états antérieurs validés.

## Contrats

- **Masquer ≠ verrouiller**. La visibilité ne change aucune règle de gameplay
  et ne rend pas une case praticable ou infranchissable.
- Le **niveau actif** choisit une présentation et un plan d'édition ;
  ce n'est ni `tile.height` ni la position tactique d'une unité.
- Les préférences sont indépendantes pour chaque mission. Les cartes anciennes
  sans fichier annexe se chargent avec tous les calques visibles, aucun verrou
  et le niveau actif 0.
- Un fichier annexe corrompu ne bloque jamais l'ouverture du contenu de jeu ;
  il est signalé puis les valeurs par défaut sont restaurées en mémoire.
- La copie `Enregistrer sous` emporte les préférences au nouveau nom, sans
  modifier la sauvegarde Content.
- La gestion des structures/escaliers/meubles conserve ses API existantes.
  Les lots 3.7.32A/B restent des PR séparées et peuvent être rebasés ensuite.

## Tests et gates

```bash
python -m unittest discover -s tests_standalone -p 'test_map_layer_workspace_3732c.py' -v
python -m unittest discover -s tests_standalone -p 'test_map_fill_3711.py' -v
python -m unittest discover -s tests_standalone -p 'test_interior_levels_3720b.py' -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p 'test_map_layer_workspace_3732c_gui.py' -v
```

Acceptation : masquer la toiture, verrouiller Terrain, vérifier qu'un tracé
est refusé sans historique, le déverrouiller, peindre une case, sélectionner
un plateau N1, enregistrer, fermer puis rouvrir. Vérifier les données
inchangées du Player en dehors du tracé déverrouillé. Exécuter aussi les
tests de parité du rendu Editor/Player et de navigation des étages.

## Suites

- 3.7.32D : réutilisation de groupes de bâtiments/quartiers.
- 3.7.32E : génération assistée avec aperçu de diff et retour arrière.
- Gate final : place fortifiée interactive, deux étages, rivière/pont,
  bâtiments/objets, utilisable dans le Player.
