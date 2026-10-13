# 3.7.20C2 — Tir entre étages, ouvertures et IA de liaison

Cette livraison reprend 3.7.20C1 sur la branche courante des intérieurs
3.7.20A+B, puis ajoute un **premier combat inter-étages contrôlé**.

## Ce qui fonctionne

- Un acteur peut tirer depuis N0 vers N1, ou N1 vers N0, uniquement avec
  une attaque de base et une arme `ranged` ou `focus`.
- La cible doit être à **un seul étage d'écart** et dans la portée de
  l'arme, en comptant une unité de distance verticale.
- Une dalle **manquante dans le plancher supérieur** constitue une
  ouverture. Elle doit être à une case maximum du tireur inférieur
  **et** de la cible supérieure. Un toit coupé VISUELLEMENT ne suffit
  pas : la collision du plateau de l'étage fait foi.
- Depuis N0, la ligne basse vers l'ouverture doit être dégagée.
  Les plafonds pleins bloquent toujours le tir, même si le personnage
  est visible grâce à la coupe du toit.
- `level_attack` est une **commande explicite** : coordonnées XY et
  numéro d'étage de la cible. Les anciennes commandes `act`/replays
  2D ne changent pas.
- Le calcul prévisionnel `Battle.vertical_forecast(level, cell)` est
  pur : il ne consomme ni aléatoire, ni action ni points de magie.
- La commande atomique consomme l'action, applique une pénalité de
  précision de 15 % et journalise le tir (y compris les étages).
  Une cible impossible ne consomme rien.
- Le Player et le Map Editor exposent `level_attack` avec sélection
  de l'étage cible et picking des losanges surélevés.
- Les déplacements `level_move` sont désormais exécutés pas par pas :
  tirs de préparation des personnages présents sur le même étage,
  puis dangers/ramassage/déclencheurs uniquement lors des passages N0.
- L'IA se rapproche d'un ennemi situé à un autre étage à l'aide des
  liaisons explicites ; aucun escalier fictif n'est créé.

## Scénario de test

Le fichier `examples/layered_house_3720c.py` permet de générer
la maison avec N1. Pour tester le tir vertical, ajouter une ouverture
dans N1 près de la cible (avec **Trou** dans le Map Editor) en conservant
une case séparée pour l'escalier.

Commandes de référence :

```python
battle.vertical_forecast(1, (4, 4))
battle.execute({'kind': 'level_attack', 'level': 1, 'cell': [4, 4]})
```

Le test `tests_standalone/test_vertical_combat_3720c2.py`
construit une scène avec un ennemi à N1, une fenêtre de tir dans le
plancher et un escalier situé sur une dalle conservée. Il vérifie
tir permis/interdit, erreurs atomiques, succès/échec déterministes,
même XY sur deux niveaux, IA et replay.

## Périmètre encore non couvert

- La règle de fenêtre de tir est volontairement locale : pas de
  ray-tracing balistique 3D à travers plusieurs étages, ni de murs et
  fenêtres dédiés aux niveaux supérieurs.
- Les dégâts verticaux passent sans contre/riposte/interception,
  dont la sémantique inter-étages reste à spécifier.
- Pas de sorts, AoE, explosions verticales, coups de mêlée au travers
  d'une trémie, chutes de personnages ou projectiles arqués.
- Les systèmes de prise à revers, protections et formations restent
  de plein droit sur un plan tactique ; leur interaction entre plans
  demande des tests dédiés.
- Les mises à jour de structures qui déplacent une cage d'escalier
  doivent rebaser leurs liens ou refuser l'édition atomiquement.
- Les cas d'IA exigeant plusieurs tours pour atteindre un escalier
  lointain restent une prochaine amélioration.

## Livraison / contrôle

- [ ] CI Python multi-OS passée après report sur la branche de #93
- [ ] Tests GUI des niveaux 24/54/96 et rendu Player
- [ ] Non-régression cache de rendu et fixtures d'acteurs historiques
- [ ] Vérification manuelle maison et tour, tirs autorisés seulement
      au travers d'un plancher réellement ajouré
- [ ] Rebase propre quand #93 sera fusionnée dans `master`
