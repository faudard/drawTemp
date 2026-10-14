# Intégration des 10 PR — 14 octobre 2026

La branche d'intégration réunit les PR #207, #208, #210, #211, #212, #213, #214, #215, #216 et #217 en une seule PR cible `master`.

## Périmètre
- Studio et Building Editor : fiabilité, composants visuels de bâtiment, génération de carte naturelle.
- Player et campagne de Jeanne : chapitre I, exploration plein écran en 2.5D, camera zoom/pan, dialogue accessible, menu pause, sauvegardes et options sur une page.
- Rendu : identité visuelle de Jeanne et menu titre avec éléments Tk réels.
- Tests et CI : conservation des étapes existantes de `master` et ajout des tests de chaque lot.

## Arbitrages de conflits
- `sporebound/player_app.py` conserve la navigation fullscreen/écran titre des PR #213/#215/#217. Les deux modifications de l'ancien panneau de démarrage (#208) sont supplantées par le menu titre cinématique interactif.
- Le viewport de dialogue complet de #211 remplace l'ancienne présentation, tandis que les actions de campagne et la navigation récente sont préservées.
- La page d'options de #212 conserve le paramètre `return_to_game` introduit par #213 pour revenir correctement à la pause.
- La caméra de #210 a été adaptée au nouveau rendu plein écran et à l'atlas artistique de #215 plutôt que de rétablir son ancien panneau latéral.
- `sporebound/editor.py` et `.github/workflows/standalone.yml` ont été reconstruits sur `master` avec les changements des branches concernées, pour conserver les ajouts intermédiaires.

## Gates de fusion
1. Toutes les validations CI et vérifications Python doivent réussir.
2. Player : démarrage Jeanne, chapitre I, déplacement isométrique, zoom ancré et pan, dialogues et choix visibles aux petites résolutions, combat, sauvegarde/chargement, options et commandes.
3. Studio : outil bâtiment, prévisualisation des terrains naturels, Undo/Redo et persistances sans corruption.
4. Smoke visuel sur fenêtres 800×580 et 1160×820, avec DPI/échelle 100/125/150 %.
5. Les dix PR originales restent disponibles pour comparaison jusqu'à la validation de cette PR unique.

Aucune des PR originales n'a été intégrée directement dans `master`.
