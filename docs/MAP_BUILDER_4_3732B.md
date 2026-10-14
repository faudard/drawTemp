# 3.7.32B — Architecture visuelle : façades, toitures, ouvertures

## Objectif et portée

Étendre les bâtiments **persistants** déjà éditables dans le Map Editor 3.0,
sans second système de structures, de navigation, ni de rendu.

La PR ajoute des détails visuels facultatifs aux records `structures`
existants (Maison et Tour) :

- Façades : `pierre`, `torchis`, `brique`.
- Toitures : `tuiles`, `ardoise`, `plat` (différence visible dans le rendu
  vectoriel partagé Player/Editor, sans nouveau spritesheet requis).
- Fenêtres : cases **locales** de murs extérieurs, décoratives uniquement.

La sélection d'une structure affiche ses matériaux actuels dans l'onglet
**Architecture**. Modifier les listes et cliquer **Appliquer façade/toiture**.
Choisir **Poser fenêtre** ou **Effacer fenêtre**, puis cliquer un mur
extérieur ; un contour de survol indique si la case est autorisée. L'outil
historique **Position de porte** reste l'unique outil pour déplacer une porte.
Son application continue d'utiliser `StructureCommand` / `edit_structure`.

Les escaliers et le mobilier **ne sont pas réimplémentés** : les contrôles
`Étage intérieur`, `Mobilier` et `Escalier N-1 ↔ N` utilisent déjà
`interior_levels.py` et `level_navigation.py`. Ils sont testés avec les
nouvelles apparences. Aucune fenêtre ne transforme un mur bloqué en passage
tactique ; les ouvertures jouables restent à placer explicitement via les
outils existants.

## Format facultatif, compatible avec les cartes anciennes

Une maison ou tour persistante peut inclure la clé facultative suivante :

```json
"appearance": {
  "facade": "brique",
  "roof": "ardoise",
  "windows": [[0, 1], [3, 1]]
}
```

Les positions de fenêtres sont locales à l'empreinte **après rotation**,
sur des cellules de mur extérieur valides, pas sur des portes ou des sols.
Les anciennes cartes sans `appearance` continuent d'utiliser les sprites
et les couleurs traditionnels. Les valeurs inconnues ou des ouvertures
hors périmètre sont rejetées par `Content.from_dict`.

- Sauvegarde/chargement : via le sérialiseur actuel, `version=1` inchangée.
- Annulation : un seul `Document.replace` par changement de style ou de fenêtre.
- Translation et duplication : conservent l'apparence et les fenêtres ;
  rotation : adapte les coordonnées locales au nouveau plan.
- Références et ID : inchangés pour les modifications, uniques pour les copies.
- Le nouveau rendu dessine une variante vectorielle uniquement si une
  apparence personnalisée a été enregistrée ; autrement, l'atlas existant
  reste prioritaire.

## Gates

```bash
python -m unittest discover -s tests_standalone -p 'test_map_builder4_3732b.py' -v
python -m unittest discover -s tests_standalone -p 'test_interior_levels_3720b.py' -v
python -m unittest discover -s tests_standalone -p 'test_structure_editing_3719b.py' -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p 'test_map_builder4_3732b_gui.py' -v
```

Critères : une maison personnalisée conserve ses fenêtres après
déplacement/rotation, sa toiture n'occulte pas l'édition de ses niveaux, un
escalier N0↔N1 demeure valide, un meuble reste au bon étage, le rendu
Editor/Player partage les mêmes structures, et le tout survit au
save/reload/undo/redo. Un effet tactique (porte à ouvrir, passage, événement)
doit être **créé via le système événementiel existant** ; il n'est pas implicite
dans les métadonnées visuelles.

## Suite

3.7.32C : calques et niveaux actifs ; 3.7.32D : préfabriqués composés de
structures authorées ; 3.7.32E : génération assistée et prévisualisation
diffable. Le gate global de place fortifiée reste en attente de ces lots.
