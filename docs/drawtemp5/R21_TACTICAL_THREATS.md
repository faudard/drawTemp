# R21.A — Menaces tactiques superposées (tranche R21.1)

## Périmètre livré

La roadmap 5.4 définit R21.1–R21.14. Cette première tranche **corrige
l'observabilité de R21.1** en réutilisant exclusivement les moteurs
`sporebound.engine.Battle`, `tactical_intents`, `battle_frame` et
`combat_hud`. Elle ne certifie pas R21 complet, ni les autres jalons du
siège. La certification UX et GPU exige toujours une revue humaine.

### Comportement vérifiable

- Une case menacée par deux ennemis conserve **les deux identifiants de
  source** pour un sort déjà programmé (`scheduled`), une réaction
  effectivement armée (`armed`) ou une charge légalement envisageable
  (`possible`). Les anciennes projections fusionnaient les sources
  par `(kind, cell)` ; elles utilisent maintenant `(kind, cell, source)`.
- Les trajectoires alternatives du **même** ennemi ne créent pas de
  doublons artificiels pour une même famille de menace et une même case.
- Le HUD de sélection affiche `×2`, `×3`, etc. quand plusieurs unités
  distinctes portent une même famille de menace sur la case. La
  projection détaillée `BattleFrame.danger` garde toutes les lignes,
  avec `unit` et `certainty` conservés.
- L'ordre des lignes est stable (famille, case, identifiant). Aucun appel
  de projection ne consomme le RNG, n'avance le CT ni ne modifie une
  action, formation, sauvegarde, replay ou schéma du contenu.
- Le `truncated` existant reste limité aux cellules parcourues pour
  les réactions préparées : il **n'est pas** un plafond global pour les
  zones de charge ou de sorts. Ne pas présenter ce compteur comme tel.

### Exemple côté Player

Pour une case `(2, 2)` visée simultanément par deux sorts :

```text
danger:
  - {kind: cast, cell: [2, 2], unit: alpha, certainty: scheduled}
  - {kind: cast, cell: [2, 2], unit: zulu, certainty: scheduled}
warnings: ["sort programmé ×2"]
```

Les mentions `scheduled`, `armed` et `possible` sont essentielles :
un sort programmé peut être interrompu, une réaction ne frappe que si
les règles de déclenchement sont satisfaites, et une charge possible
n'est **pas** une décision IA déjà prise.

## Validation

```bash
python -m unittest -v tests_standalone.test_r21_overlapping_threats
python -m unittest -v tests_standalone.test_combat31
python -m unittest -v tests_standalone.test_drawtemp5_r12_tactical
```

Le nouveau jeu de tests couvre les deux sorts, les deux overwatch,
deux trajectoires de charge convergentes, pureté de projection, HUD
et replay exact après une commande canonique. Les suites doivent être
exécutées sur le SHA de la PR et les logs de CI contrôlés avant
validation de ce sous-lot.

## À faire pour R21

- **R21.1 complet** : UX des intentions, portée verticale et plans
  multiétages, contrôle des limites de grands combats, validation réelle
  Qt onscreen et captures de référence.
- **R21.2–R21.7** : certifier les réactions, le positionnement, les
  formations, la coordination IA et les intérieurs dans des séquences
  tactiques combinées (pas uniquement des tests unitaires isolés).
- **R21.8–R21.14** : préparation du siège, bélier/herse, fronts
  synchronisés, diplomatie/infiltration, salle du trône, fins alternatives
  et Balance Lab multi-seeds avec sauvegarde et replay.
- **Gate 5.4** : deux approches terminables, multi-fronts persistants,
  trajectoires IA sans téléportation, stratégie ayant des conséquences
  réelles, preuves UI/Player et QA humaine.

Références : [roadmap détaillée R17–R24](../DRAWTEMP_5_0_TO_6_0_DETAILED_ROADMAP.md)
et [roadmap multi-genres R25–R30](../DRAWTEMP_MULTI_GENRE_CREATOR_ROADMAP.md).
