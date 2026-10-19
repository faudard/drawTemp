# R17.A — Merge Ledger / INT-CROSS-01

Baseline de référence : `master` à `6648cc3a284d4f4ac966bc0e102001078a5cc438`, 15 octobre 2026.
Vérification des *merge commits* GitHub : 17 octobre 2026.
Le badge `merged` est insuffisant pour déclarer la fonction intégrée.

| PR | Lot | Merge SHA | Ancêtre de master ? | Preuve/risque |
|---|---|---|---|---|
| [#248](https://github.com/faudard/drawTemp/pull/248) | R7.B | `6648cc3` | oui (HEAD) | Adaptateur CharacterPack et R3 présents ; certification visuelle à faire |
| [#264](https://github.com/faudard/drawTemp/pull/264) | R7.C | `9fa8851` | oui | Jeanne art, projection équipement présents |
| [#263](https://github.com/faudard/drawTemp/pull/263) | R9.C | `475700c` | **non** (diverged) | event_overlay, event_graph_qt, event_command_catalog et test R9.C absents |
| [#273](https://github.com/faudard/drawTemp/pull/273) | R9.D | `ac90249` | **non** (diverged) | event_pages et test R9.D absents |
| [#253](https://github.com/faudard/drawTemp/pull/253) | R16 | `7829988` | oui | Migration présente ; retrait Tk non autorisé sans gate |
| [#255](https://github.com/faudard/drawTemp/pull/255) | R15 | `d8f7e84` | oui | Export présent ; clean-machine non certifié |
| [#275](https://github.com/faudard/drawTemp/pull/275) | R14.5 | `8dd6b32` | oui | Visual goldens présents ; validation humaine distincte |
| [#254](https://github.com/faudard/drawTemp/pull/254) | R14 | `9dc808e` | oui | Infrastructure GUI présente ; SHA final de CI à confirmer |

Vérification par comparaison GitHub des merge commits vers master. Un statut
`ahead` sans commits `behind` prouve l'ascendance. Pour R9.C et R9.D,
la comparaison était `diverged` ; des fichiers majeurs de leurs PR sont absents
du tree de master. Des fonctions équivalentes éventuelles ailleurs doivent être
auditées par tests : ce registre ne prétend pas prouver leur absence métier complète.

## Reproduire

Depuis **un clone complet** (pas un checkout shallow) :

```bash
python scripts/audit_r17_merge_ledger.py --ref master
python scripts/audit_r17_merge_ledger.py --ref master --format json > r17-ledger.json
python -m unittest discover -s tests_standalone -p 'test_r17_merge_ledger.py'
```

Option `--strict` : retourne 1 tant qu'un merge n'est pas prouvé comme ancêtre
ET que ses fichiers/symboles de contrôle ne sont pas trouvés. À ce jour, elle
doit donc échouer tant que R9.C/R9.D ne sont pas restaurées ; **ne pas en faire
un gate bloquant par défaut sans plan de récupération**.

## Suite prioritaire, à ne pas masquer par un cherry-pick global

1. Reprendre R9.C/R9.D par lots ciblés sur master, en particulier
   `sporebound/event_pages.py`, `drawtemp/studio/event_graph_qt.py`,
   `drawtemp/studio/event_command_catalog.py`, leurs tests et intégrations
   `events.py` / `game_session.py`.
2. Comparer les fichiers modifiés avec le code master actuel, protéger
   Content/GameProject et AuthoringSession et résoudre les conflits par symbole.
3. Ajouter un test porte/levier/page/priorité/replay/roundtrip depuis Studio,
   puis démontrer Qt Player onscreen avant de fermer R17.3.
4. R7.B/R7.C : tester durée/action/tenue/décès sur **le même** Player et
   son renderer R3, sur les trois OS ; ne pas confondre tests Qt et preuve GPU.

Statut : R17.1 *audit produit*, R17.3 **bloqué**, R17 global **non certifié**.
