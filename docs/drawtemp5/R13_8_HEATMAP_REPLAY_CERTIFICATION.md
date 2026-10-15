# DrawTemp 5.0 — R13.8 · Heatmaps des déplacements et replay animé

**Branche :** `feat/drawtemp5-r13-8-ai-damage-visuals`
**Roadmap :** `docs/DRAWTEMP_5_0_ROADMAP.md`, lot R13.8.
**Base technique :** `sporebound.battle_diagnostics.trace_seed()` +
`drawtemp/sdk/r13_combat_lab.py` + travail R13.8 des PR #243 / #267.

## Utiliser le Battle Lab

```bash
python -m pip install ".[qt6]"
python -m drawtemp.studio.r13_workbench --content sporebound/content/jeanne.json
```

Sélectionner une mission, puis **Simuler + vérifier les replays**.
La première seed simulée est retracée par le moteur canonique et validée par
`Battle.replay`. Le lecteur indique explicitement ses commandes
`0 / nombre total`, sans représenter des frames temporelles inventées.

### Heatmaps

L'onglet **Heatmaps des déplacements** affiche automatiquement les
déplacements enregistrés de toute la bataille, et permet de filtrer :
- **Équipe** : toutes, joueurs, ennemis ou autre équipe présente.
- **Unité** : toutes les unités ou un acteur précis, y compris les renforts.
- **Étage** : chaque niveau du replay est une vue indépendante.
- **Mesure** : déplacements observés, ou visites incluant positions initiales
  et apparitions d'acteurs.

Les cases chaudes reflètent un **nombre d'arrivées réellement observées**,
pas le temps d'occupation. Un acteur immobile ne remplit pas la même cellule
au fil des commandes des autres. Les sauts/téléportations intercases et les
changements d'étage ne fabriquent aucun chemin intermédiaire. L'empreinte
multicase n'est pas reconstituée : seule l'ancre de l'acteur est suivie.

Cocher/décocher **Toute la bataille** pour afficher le cumul global ou la
heatmap progressive synchronisée avec le lecteur. En mode progressif,
le clic sur une case visitée positionne le replay à la dernière arrivée
réellement observée dans cette case avant le curseur.

### Lecture animée

Sous les résultats du Battle Lab, la barre de lecture offre :
- **Lire / Pause**, **début**, **précédente / suivante**.
- **Curseur précis** de la commande zéro à la dernière commande exécutée.
- **Vitesse** : 0,5×, 1×, 2×, 4× (intervalle d'affichage, pas vitesse de l'IA).
- **Synchronisation** des positions du viewport diagnostique, de la timeline,
  des courbes de dégâts/soins et de la heatmap progressive.

La lecture déclenche uniquement le passage à une **commande déjà
enregistrée**. Elle ne simule pas de nouvelles décisions et n'interpole
aucun sprite. La commande `0` affiche la position initiale, les unités
mortes disparaissent du rendu après leur élimination et les renforts
apparaissent lorsqu'ils existent dans le replay.

La lecture est arrêtée lorsque le projet/la mission change, qu'une nouvelle
simulation démarre, lorsque la fenêtre est fermée ou lorsque la dernière
commande est atteinte. Une demande de simulation périmée ne peut pas
remplacer les vues courantes.

## Gate de certification R13.8

| Axe | Contrôle automatisé | Preuve |
| --- | --- | --- |
| Déterminisme | Même trace, mêmes cellules, même ordre, JSON stable | Tests headless |
| Intégrité | Replay vérifié exigé, coordonnées/bornes, niveaux, IDs, budgets | Tests headless |
| Précision tactique | Pas de faux déplacements immobiles ni d'interpolation | Fixture tests multiétages |
| Navigation | Lecture/pause/fin/seek/vitesse, état initial, contrôles réinitialisés | Tests Qt offscreen |
| Synchronisation | Timeline ↔ lecteur ↔ heatmap ↔ courbes PV | Smoke Qt intégré |
| Visuel | Cellule modifiée visible et retour arrière produisant même pixel | Tests Qt offscreen |
| Multi-OS | Python 3.10/3.12 SDK + Qt 6 offscreen Windows/Linux/macOS | GitHub Actions |
| Preuves visuelles | Captures PNG initiale/finale et rapport JSON de test | Artifacts CI |
| Ergonomie humaine | Inspection manuelle des captures, tests souris/clavier réels | **À valider** |
| Player isométrique GPU | Intégration définitive, golden DPR et budgets GPU | **Hors de cette tranche** |

**Important :** les tests/captures vérifient l'affichage et les interactions,
mais ne valent pas certification visuelle humaine tant que les artefacts CI
n'ont pas été revus. Les images automatiques comprennent un scénario
déterministe à deux niveaux explicitement identifié comme **fixture**
(`heatmap-initial.png`, `heatmap-final.png`) et un combat
**réellement simulé/rejoué** par le moteur canonique
(`heatmap-canonical-replay.png`, `r13_canonical_replay.json`).
Ce dernier est un scénario d'arène de test, pas une capture trompeuse
d'une mission complète de Jeanne.

### Exécution locale

```bash
python -m unittest tests_standalone.test_drawtemp5_r13_heatmap -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp5_r13_replay_qt -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp5_r13_qt -v
```

Captures optionnelles (le répertoire sera créé lors du test) :

```bash
QT_QPA_PLATFORM=offscreen R13_VISUAL_EVIDENCE_DIR=ci-evidence/r13 \
  python -m unittest tests_standalone.test_drawtemp5_r13_replay_qt -v
```

Sur CI, les artifacts **r13-visual-evidence-ubuntu-latest**,
**r13-visual-evidence-windows-latest** et
**r13-visual-evidence-macos-latest** contiennent les PNG et un fichier
`r13_visual_certification.json` indiquant explicitement que la revue
visuelle humaine n'est **pas encore signée**.

## Limites techniques

- Le viewport associé reste le **diagnostic Qt Widgets orthogonal** :
  ce n'est pas la restitution isométrique GPU R12.
- Les transitions reflètent l'ancre du personnage après chaque commande,
  pas chaque case traversée pendant une animation intracommande.
- Le SDK protège un maximum de **5 000 commandes**, **512 unités** par
  état et **100 000 arrivées**. Les heatmaps 128×128 à grande densité
  demandent encore un profilage de performance.
- Les graphiques d'IA et de dégâts/soins de #267 et l'export PNG de #262
  conservent des cycles de validation distincts.
