# 3.7.18A — Scene isométrique commune, Editor / Playtest / Player

## Constat initial

Le 3.7.16A apporte une bibliothèque graphique dans le Studio, mais la vue
isométrique disparaissait au lancement du Playtest. Le Player autonome
utilisait exclusivement `CanvasRenderer` en carrés orthogonaux. L'utilisateur
ne testait donc pas le niveau avec sa vraie présentation artistique.

## Portée de cette PR

- **Studio** : cocher « Vue isométrique 2.5D » conserve les mêmes terrains,
  rivières, ponts, bâtiments, toitures et décors pendant le Playtest. Les
  clics utilisent toujours le picking spatial `IsoGeometry.hit_test`.
- **Player autonome** : bascule « Vue isométrique 2.5D » dans la barre de
  combat. Elle conserve l'éditeur, les modèles tactiques et le mode 2D
  historique. Les clics, le zoom centré sur la case et le pan sont adaptés
  à la projection isométrique ; un clic hors carte ne change pas la cible.
- **Module partagé** : `iso_battle_view.py` utilise le moteur de rendu
  `iso_map.render_isometric` de l'éditeur et les quatre atlas PNG embarqués
  (`terrain`, `props`, `buildings`, `fortifications`). L'état des
  acteurs et les cases atteignables viennent du `Battle` courant ;
  `presentation.battle_frame` fournit les menaces sans inventer de règles.
- **Lisibilité** : zones de déplacement en vert, incantations en violet,
  charges possibles en orange et dangers du terrain en rouge ; priorité des
  menaces identique au renderer orthogonal. L'acteur actif est entouré et
  les PV sont affichés. Les bâtiments masquent leur toit lorsque leur
  emprise est sélectionnée ou occupée par un personnage.
- **Conservation** : les moteurs de tactique, IA, commandes, CT, gestion des
  tours, campagnes, sauvegardes et replays sont inchangés.

## Validation

```bash
python -m unittest discover -s tests_standalone -p test_iso_battle_view_3718.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_iso_battle_view_3718_gui.py -v
python -m unittest discover -s tests_standalone -v
```

Le test pur couvre projection/hit-test pour trois zooms, zoom ancré,
menaces prioritaires, couche de déploiement et absence de modification
de `Battle.digest()`. Le test Tk/Xvfb effectue le vrai parcours
Éditeur → Playtest → clic → Éditer, puis Player → mission →
isométrique → cible → zoom → retour orthogonal.

CI : `Standalone gameplay` (Linux, Windows, macOS × Python 3.10,
3.12, 3.14) + `Distribution smoke`; le job `editor` lance
explicitement le nouveau smoke sous Xvfb.

## Limites et prochains travaux

Il s'agit du **raccord de présentation 3.7.18A**, pas de la fermeture
totale du jalon « Visual Rendering & Occlusion » :

- Le mode 2D du Player conserve ses animations interpolées et son
  `CanvasRenderer` optimisé. Le mode isométrique affiche des snapshots
  des positions réelles ; l'interpolation des déplacements/attaques
  isométriques doit être intégrée après validation de la projection
  (3.7.18B).
- Le canvas isométrique reconstruit actuellement la scène à chaque
  rafraîchissement. Le cache géométrique et les mesures sur cartes
  32²/64²/128² sont une tâche 3.7.18C ; éviter de promettre les mêmes
  budgets que le renderer orthogonal.
- La coupe de toiture est conditionnée par l'empreinte sélectionnée ou
  occupée, et non une occlusion 3D parfaite pour tous les volumes.
- Les interfaces spécialisées `castle_player_app` et
  `studio_siege_player_app` ne sont pas encore migrées ; le Player
  de campagne principal et le Playtest Studio le sont.
- Les essais de vrais PNG sur Windows/macOS natifs restent souhaitables
  en plus du smoke Tk Linux/Xvfb.

## Gate de complétion

Une carte créée graphiquement doit présenter les mêmes sols, décors
et structures dans le Playtest Studio et dans une mission du Player.
Le clic/zoom/pan doit garder les mêmes cases tactiques, et une sauvegarde
de combat et son replay doivent rester compatibles avec la version
préexistante. Ne pas fusionner avec CI KO ou sans revue visuelle.
