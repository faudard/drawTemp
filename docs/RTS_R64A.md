# R64.A — Real-Time Strategy: prototype headless vérifiable

Statut : **prototype isolé** sur branche / PR ; **ni RTS Player certifié,
ni Studio, ni gate R64 atteint**. Le document canonique reste
[DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md).

## Contrats livrés dans R64.A

- `sporebound.rts64.RTSWorld` : grille entière bornée, cellules bloquées,
  128 unités maximum et 32 unités par ordre ; groupes de **même équipe**
  uniquement, positions et points de formation distincts.
- Ordres explicites `move_group` (`line`, `column`, `wedge`),
  `stop_group`, `set_engagement`. La sélection est fournie par l'appelant :
  aucun outil graphique de sélection n'est prétendu implémenté.
- Affectation des emplacements de formation sans occupation adverse,
  recherche BFS 4 directions (N/E/S/O), réservations à chaque tick, réévaluation
  du chemin à chaque pas. Les unités bloquées attendent ; à partir de 8 ticks,
  `stalled_units` rend le problème visible pour le débogage.
- Cadence **indépendante du FPS d'affichage** : `FixedTickJournal` R25,
  ordre canonique des entrées `(tick, source, sequence)`, snapshots
  JSON, contrôles d'intégrité par tick et rejeu intégral.
- Règles d'engagement expérimentales : `hold_fire`, `return_fire`,
  `fire_at_will`. Tir adjacent, 1 PV par attaque, toutes les 10 unités
  de tick ; dégâts simultanés. Aucun système de production économique ou de
  tir à distance n'est intégré à ce prototype.
- Validation stricte (pas de bool comme coordonnées/HP, ni doublons, ni
  groupes multi-équipes, ni terrain hors limites). Ordre rejeté = tick
  **non validé** ; journal conservé. Digest de scénario dans chaque snapshot.
- Module opt-in : aucune modification des `Battle`, `GameSession`,
  `GameProject`, sauvegardes ou valeurs CT de la campagne Jeanne.

### Exemple minimal

```python
from sporebound.rts64 import RTSWorld

units = [
    {"id": "archer1", "team": "blue", "pos": [0, 0]},
    {"id": "archer2", "team": "blue", "pos": [0, 1]},
]
world = RTSWorld(8, 6, units, walls=[[3, 2], [3, 3]], seed=64)
world.submit(1, "player", {
    "kind": "move_group", "units": ["archer2", "archer1"],
    "target": [6, 4], "formation": "line",
    "rules": "hold_fire",
})
for _ in range(20):
    frame = world.step()  # Une étape logique, jamais un delta wall-clock.
recording = world.recording()
verified = RTSWorld.replay(
    8, 6, units, recording, walls=[[3, 2], [3, 3]])
assert verified.snapshot() == world.snapshot()
```

### Vérification automatisée

```sh
python -m unittest tests_standalone.test_r64_rts -v
python -m unittest tests_standalone.test_r25_foundation -v
```

Tests ciblés : contournement de murs, arrivée de deux unités en formation,
absence de superposition, ordre de soumission multi-sources, tir simultané /
contre-tir, rejet atomique, blocage signalé, modification de replay ou de
scénario refusée, non-régression de l'enregistrement CT Jeanne.

### Limites et suites (non livrées)

1. **R64.A — durcissement** : recherche de trajectoires partagées/flow fields,
   résolution de face-à-face en couloirs étroits, mesure p95/p99 et limite
   d'unités par matériel réel ; un blocage détecté n'est **pas** aujourd'hui
   résolu automatiquement. Pas de vitesse individuelle ni d'obstacle mobile.
2. **R64.B — P0** : relier l'éditeur au schéma versionné, sélection multi-unités
   souris/clavier, groupes de contrôle, minimap, marqueurs d'ordres, undo/redo,
   contrôles focus/a11y et Player Qt/Tk testés bout en bout.
3. **R64.C — P1** : scénario « Défense du village » : vagues, renforts,
   ressources, doctrines IA et données d'équilibrage, replays et profils CPU/GPU.
4. **Gate R64 final** : coordination simultanée de plusieurs escouades sur
   une scène complète, avec budgets mesurés + baseline CT Jeanne inchangée.

La PR ne démontre pas de façon générale l'absence de deadlocks sur toutes les
topologies ; seuls les cas testés sont vérifiés. Le prototype est hors du format
canonique d'authoring, sans sauvegarde de session produit ni networking.
