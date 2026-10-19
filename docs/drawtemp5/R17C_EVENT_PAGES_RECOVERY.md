# R17.C1 — Réintégration du moteur R9.D (pages d'événements)

## Contexte

Les PR [#263](https://github.com/faudard/drawTemp/pull/263) et
[#273](https://github.com/faudard/drawTemp/pull/273) ont été fusionnées vers
une branche d'événements intermédiaire, **pas** dans master. Le code R9.D
était donc absent malgré les badges « merged ». Cette tranche repart
exclusivement de master et récupère le **contrat headless** avec ses tests,
sans fusionner aveuglément l'ancien historique.

## Contrat restauré

- `sporebound/event_pages.py` : pages et priorités, activation/désactivation
  via `event_state`, cooldown/répétition et inspection à partir du journal
  tactique, sans sidecar mutable.
- `sporebound/rules/triggers.py` : sélection de la page éligible dans le
  dispatcher existant, sans scheduler parallèle.
- `sporebound/model.py` : validation des pages et références croisées avec
  le même registre de règles.
- `sporebound/engine.py` et `game_session.py` : replay, restauration,
  dialogue tactique répétable et choix du manifeste opt-in.
- `sporebound/event_composer.py` et `event_graph.py` : les éditions
  existantes ne perdent pas les règles des pages lorsqu'on réordonne,
  duplique ou retire un événement.
- `drawtemp/studio/events.py` : API headless de pages sur
  **AuthoringSession**, avec preview/apply, révision et Undo/Redo canonique.
  Aucun nouveau format de sauvegarde ou moteur n'est ajouté.

### Validation

```sh
python -m unittest tests_standalone.test_drawtemp5_r9d \
  tests_standalone.test_r17c_event_integration \
  tests_standalone.test_drawtemp5_r9 \
  tests_standalone.test_drawtemp5_r9b \
  tests_standalone.test_drawtemp5_r1_authoring -v
```

La workflow dédiée exécute cette matrice sur Python 3.10/3.12. Les
régressions de compatibilité vérifient que les anciens projets gardent
le manifeste de règles par défaut et que les pages restent dans le
Content validé, pas dans le Player UI ni dans un état indépendant.

### Limites — gate R17.3 encore ouvert

L'ancien Studio Qt R9.C n'est pas dans master. Son
`_command_dialog()`, son graphe Qt, ses marqueurs isométriques et
l'éditeur Qt de pages dépendant de ces widgets seront repris dans **une
PR séparée R17.C2**, après stabilisation headless. Ne pas déclarer le
parcours porte/levier/page/Player certifié tant qu'il manque l'E2E
onscreen et la parité d'export.

Des échecs CI d'autres lots (R6, qualité/certification) sont
également connus et suivis séparément ; un test R9.D vert ne constitue
pas une validation globale de DrawTemp 5.0.
