# Playtest V1.9.5 — Native Level Design Production

## 1. Ouverture

1. Active `Sporebound Studio`.
2. Maps → mission **Tenir la Scène** → `ÉDITER LA MAP EN 2D`.
3. Vérifie que TileMap, spawns et `CenterStageZone` sont visibles.

## 2. Zone polygonale

1. Sélectionne `CenterStageZone`.
2. Vérifie l’Inspector Sporebound et le surlignage des cases couvertes.
3. Modifie un point du `Polygon2D` avec l’outil natif Godot.
4. Sauvegarde puis vérifie que le surlignage suit la nouvelle forme.

## 3. Création rapide

1. Survole une case libre.
2. Toolbar → `+ Objet` → Spawn ennemi.
3. Vérifie que le spawn apparaît sur cette case, est sélectionné et supporte Undo/Redo.
4. Répète avec Porte et Zone.

## 4. Triggers de zone

1. Mission Logic → Tenir la Scène.
2. Vérifie le trigger `enter_center_stage` avec `Zone ID condition = center_stage`.
3. Lance la mission et déplace un héros dans la zone centrale.
4. Le message associé doit se déclencher une seule fois.

## 5. Play From Here

1. Depuis la map ouverte, clique `▶ Ici`.
2. La mission doit démarrer automatiquement sans écran de sélection manuel.
3. Quitte après quelques actions.
4. Relance normalement le jeu et vérifie que la sauvegarde campagne n’a pas été modifiée par le playtest.

## 6. Templates

Crée successivement une mission à partir de chaque template. Vérifie dimensions, spawns/terrain initiaux, création du `.tres` et du `.tscn`, puis ouverture immédiate dans la viewport.

## 7. Régression

- TileMap natifs toujours éditables.
- Aperçu tactique/Erreurs fonctionnels.
- Spawns et interactables restent sélectionnables dans la Scene Tree.
- `plugin.cfg` doit garder `script="plugin.gd"`.
