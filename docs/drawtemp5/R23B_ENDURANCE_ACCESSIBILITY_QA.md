# DrawTemp 5.5 — R23.B : endurance, accessibilité et QA utilisateurs

> **Statut : intégration d'un banc de vérification, pas validation finale 5.5.**
> Suite empilée de [R23.A](R23A_RELEASE_HARDENING.md) et de la roadmap
> [R17–R24](../DRAWTEMP_5_0_TO_6_0_DETAILED_ROADMAP.md).

## Reprise des contrats existants

- **R8.13** : `examples.persistence_soak.run_soak` rejoue de vraies actions
  persistées via `LongSessionStore`, compacte le journal, rouvre les
  sauvegardes et recalcule les campagnes terminées. R23.B contrôle le
  nombre de cas, les seeds, les digests, le nombre de commandes,
  la cohérence des percentiles et les observations mémoire.
- **R7.7** : les réglages d'accessibilité Player restent séparés des
  sauvegardes tactiques. R23.B teste **l'écriture réelle, la relecture,
  le refus d'une valeur incorrecte sans perte de données**, le remapping
  d'`execute` sur F1, le contraste élevé et la taille 150 %.
- **R3.8.4** : télémétrie de playtest strictement volontaire, locale,
  sans identifiants personnels. Seuls les JSON exportés par les testeurs
  peuvent servir d'entrées; les données IA/CT et les tests simulés ne
  remplacent pas de vrais parcours humains.
- **R14** : le parcours Qt QML existant vérifie de vrais clics, F5
  clavier, sauvegarde et rechargement. Le test Tk vérifie la persistance
  des réglages au travers de vrais widgets. La CI emploie une surface
  **offscreen / Xvfb** : ne pas présenter cela comme une certification
  clavier-only ou assistive technology en affichage réel.

Aucune mutation des formats `GameSession`, `GameProject`,
`SessionStore`, `LongSessionStore` ou du moteur tactique.

## Exécution

```bash
python -m unittest tests_standalone.test_drawtemp5_r23b -v

# Sur un OS donné, avec exactement le code de la révision Git fournie :
python scripts/r23b_evidence.py run \
  --revision "$(git rev-parse HEAD)" \
  --platform Linux --iterations 1 --commands 8 \
  --output r23b-ci.json

# Après collecte des rapports Linux, Windows et macOS, dans trois dossiers :
python scripts/r23b_evidence.py aggregate \
  --directory r23b-artifacts \
  --revision "$(git rev-parse HEAD)" \
  --output r23b-assessment.json

# Optionnel : importer uniquement des vrais rapports opt-in explicites
python scripts/r23b_evidence.py aggregate \
  --directory r23b-artifacts \
  --revision "$(git rev-parse HEAD)" \
  --human-report /chemin/rapport-playtest.json \
  --output r23b-review.json
```

Le mode par défaut est `headless-ci-smoke` : **1 itération / 8
commandes par OS**, incluant une campagne de contrôle et reprise.
Le rapport contient des observations `p50/p95/p99/max`,
`python_peak_tracemalloc_bytes`, les digests et la provenance SHA.
Les timings sont mesurés par machine et ne sont **pas des budgets certifiés**.
Ils ne mesurent ni la VRAM/GPU, ni une session multi-heures, ni
le temps d'attente de l'interface.

## Matrice des preuves restantes

| Exigence | Ce que produit R23.B | Pour débloquer R23 |
|---|---|---|
| R23.6 Endurance P0 | Soak persistance/replay sur 3 OS, SHA unique; anomalies bloquantes | 2–4 h de créations/lectures répétées, crash injection, surveillance mémoire/CPU, environnements représentatifs |
| R23.7 Accessibilité P1 | Remapping/prefs persistant, Qt F5 et actions QML, Tk Apply→reopen | Parcours intégral **clavier seul**, focus/Tab/Échap, lecteurs d'écran, contrastes mesurés et retests sur écrans réels |
| R23.8 Playtests P0 | Ingestion des rapports volontaires et sessions observées distinctes des tests IA | Testeurs externes créateurs/joueurs, tâches et temps, incidents bloquants, priorisation/correctifs et retests vérifiables |
| R23.12 Go/No-go | `r23b-assessment.json` avec les trois états partiels/bloqués, **NO-GO** | Réunion/revue Go-No-go des 12 gates R23, références des preuves, anomalies acceptées explicitement |

## Protocole de playtest externe suggéré

Chaque testeur doit utiliser un build identifié par SHA et OS, idéalement sur
machine propre. Scénarios séparés :

1. **Créateur** : partir d'un template, éditer une carte, placer un
   personnage/événement, créer deux états de campagne, sauvegarder,
   fermer/rouvrir, exporter.
2. **Joueur** : démarrer le Player exporté, jouer un combat et un choix,
   sauvegarder, fermer/reprendre, terminer une route et tester les options.
3. **Accessibilité** : répéter le parcours sans souris avec focus visible;
   tester 150 %, contraste élevé, remapping et restauration des raccourcis.
4. **Endurance** : répéter chargement de carte, combat, sauvegarde/restauration;
   retenir logs/crash dumps et mesurer le p95/p99 et la mémoire.

Pour chaque incident, conserver un ID non personnel, OS, SHA, procédure de
reproduction, sévérité, capture/log, correctif, statut et résultat de retest.
**Ne pas enregistrer de données personnelles dans la CI ou le dépôt.**
L'inclusion d'un rapport opt-in dans l'agrégateur ne vaut **pas** revue
humaine, correction ni validation UX.

## Go/No-go

L'agrégation échoue si un OS manque, si les SHAs divergent, si une
mesure est incohérente, ou si un rapport tente d'affirmer GPU/human/a11y
non vérifiés. Même une matrice correcte produit `decision=NO-GO`.

Les contrôles R23.6 et R23.7 restent `partial`, R23.8 `blocked`
sans playtests (au plus `partial` si des fichiers humains opt-in
existent). Le passage à `pass` nécessite une procédure de certification
séparée appuyée sur les preuves, et non un changement manuel du JSON.
