# Asset Browser — Collections, familles, favoris et récents

La bibliothèque existante `Bibliothèque d’assets — Carte` conserve ses outils
et ses IDs : aucune seconde bibliothèque, aucun nouveau système de placement,
aucun changement des sauvegardes ni des bindings Player.

## Navigation

- **Tous les assets** : arborescence Terrains, Décors, Personnages, Structures,
  Effets visuels et Interactions. Terrains est ouvert au premier affichage.
- **Terrains** : sols et matériaux de la carte.
- **Décors** : végétation, props et illustrations de décor.
- **Personnages** : acteurs plaçables et familles aquarelle (Jeanne, Loup,
  Lancier, soldats, etc.).
- **Structures** : ponts, maisons et fortifications.
- **Effets visuels** : animations du groupe aquarelle `vfx`.
- **Interactions** : objets tactiques plaçables existants.
- **☆ Favoris** : le bouton du panneau d'aperçu ajoute/retire un élément.
  Pour l'aquarelle, le favori vise la **famille** plutôt que chaque frame.
- **◷ Récents** : dernièrement **choisis pour la carte** (et non simplement
  survolés), ordre le plus récent d'abord, maximum 20.

Le champ Rechercher et l'ancien filtre de catégories restent disponibles.
La navigation latérale remet ce filtre à **Tous** afin d'éviter une collection
faussement vide. Les animations sont toujours regroupées et l'aperçu reste
centré. Les catégories ouvertes/restées fermées sont conservées lors de la
mise à jour de la liste. Un double-clic ou Entrée sur un outil plaçable
conserve le workflow existant.

Les illustrations aquarelle **ne sont pas plaçables** : le bouton de pose
reste désactivé, y compris depuis les Favoris.

## Persistance et sécurité

Les préférences sont stockées dans un fichier d'interface
`<fichier-content>.asset-browser.json` dans le même dossier que le contenu
ouvert, par exemple `jeanne.asset-browser.json`.

- `version: 1`, `favorites: []`, `recents: []`
- Écriture atomique via fichier temporaire et remplacement ;
- Références invalides ignorées si elles n'existent plus dans le catalogue ;
- Les préférences corrompues sont traitées comme vides ;
- Aucun changement de `Content`, `GameProject`, des `registry.json`,
  du moteur tactique ou du Player.

## Validation

```sh
python -m unittest tests_standalone.test_asset_browser_state -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
    tests_standalone.test_asset_palette_gui \
    tests_standalone.test_watercolor_catalog_gui -v
```

Gate UX : filtrer les Terrains, ajouter Herbe aux Favoris, choisir Herbe pour la
carte, retrouver Herbe dans Récents, fermer/réouvrir le Studio, retrouver les
Favoris, puis naviguer jusqu'à Jeanne sans perdre ses animations.
