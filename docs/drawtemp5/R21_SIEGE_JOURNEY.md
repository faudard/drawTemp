# R21.D — Parcours de siège, déploiement, logistique et checkpoint

**Tranche incrémentale R21.8–R21.11 — non certifiante.**

Le moteur possède déjà `Battle.execute`, `MultiFrontSession.execute`,
`MultiFrontSession.switch`, `send_reserves`, `advance`,
`MultiFrontSession.recording/replay`, la validation `deployment.check_position`
et les sauvegardes atomiques du centre de commandement. Il faut les
**assembler sans créer un second moteur ni un deuxième journal**.

## Contrat de la tranche

### 1. Préparation lisible avant le combat

`siege_journey_snapshot(session)` fournit :

- une phase de front (`deployment`, `tactical` ou `resolved`) ;
- pour chaque joueur vivant les cases de placement **réellement autorisées**
  par les zones, les occupations, le footprint et la géométrie canonique ;
- jusqu'à huit cases proposées par défaut, avec `valid_count` et
  `truncated` pour éviter les affichages géants. La limite de préview
  ne modifie pas la légalité de `deploy` dans Battle ;
- la possibilité de **changer de front** à l'instant courant : elle est
  évaluée par `switch()` sur une copie isolée de la session et tient
  donc compte des tours CT inachevés, du verrouillage des campagnes et
  des missions annexes ;
- des interactions tactiques réellement disponibles via les préviews
  R21.C, et les décisions de ravitaillement/convoyage connues.

Aucun choix n'est exécuté automatiquement par la preview. Elle ne
garantit pas que l'action sera encore disponible après une commande
ou une avancée temporelle. Chaque requête est bornée par les objets,
les fronts et les zones éditées (maximum configurable 1..32 cases
affichées par unité).

### 2. Chronologie authentique du château

```bash
python -m examples.siege_r21d_journey
```

Le scénario **joue effectivement** les commandes suivantes :

1. Sur le secteur de ravitaillement : validation du déploiement initial,
   `start_battle`, sabotage de `supply_cache` et ordre `end`.
   Un lien causal interdit les futurs renforts du front du trône.
2. Le joueur envoie une réserve finie vers la porte avec `send_reserves`
   et dépense des vivres réels ; `advance` synchronise tous les fronts
   et transporte le convoi jusqu'à la porte. Aucun combat automatique
   n'est simulé dans le front focalisé.
3. `switch("gate")` matérialise ce front avec ses pertes déjà subies.
   L'ordre `deploy` installe le capitaine à proximité du bélier,
   `start_battle` ouvre le combat, puis `interact("ram")` fait avancer
   physiquement le bélier d'une case.
4. Chaque étape est enregistrée par `MultiFrontSession`. Le replay
   reconstruit exactement les mêmes états et le même digest.

Ce parcours n'autoproclame pas la porte détruite ni le château gagné :
il couvre **une progression effective et reproductible**, pas encore
toute la bataille de la salle du trône.

### 3. Sauvegarde, chargement et continuation

Le centre de commandement ajoute :

```text
journey
```

qui rend le plan courant en JSON. Les commandes existantes restent :

```text
save siege-r21d.json
load siege-r21d.json
```

La sauvegarde est atomique et vérifie le replay avant écriture ;
la reprise recalcule le checksum depuis la chronologie, pas depuis
un état mutable arbitraire. Le test R21.D prend un checkpoint après
les premières opérations du bélier, recharge la session, effectue
ensuite une transition vers les remparts et une synchronisation
stratégique sur les deux sessions indépendantes, puis compare leurs
digests et leurs replays. Un checksum corrompu est rejeté sans
modifier la session en cours.

## Tests

```bash
python -m unittest -v tests_standalone.test_r21d_siege_journey
python -m unittest -v tests_standalone.test_r21c_siege_readiness
python -m unittest -v tests_standalone.test_fronts
python -m unittest -v tests_standalone.test_siege
```

Les tests R21.D couvrent placement légal/occupé, choix de focus refusé
durant un tour déjà engagé, sérialisation stable sans mutation du
combat, action réelle sur le bélier, sabotage multi-front, coût d'une
réserve, checkpoint/rechargement, reprise divergente en mémoire
indépendante et rejet de corruption.

**Aucun résultat de CI n'est présumé** avant exécution des workflows.
Les branches sont empilées : R21.A #291 → R21.B #308 → R21.C #317
→ R21.D, puis retarget et vérification du SHA de chaque étage avant
fusion. Vérifier en particulier la fusionabilité de #291 sur le
`master` courant, qui évolue simultanément.

## Ce qui reste dans R21

- Un guide de déploiement et de passage entre fronts **graphique dans
  le Player Qt**, avec reprise d'une partie depuis le navigateur des
  sauvegardes, choix d'équipe et affichage des effectifs.
- Des parties réellement complètes par bélier, infiltration,
  négociation, cour et salle du trône, sans raccourcis de scripts ;
  objectifs, transitions, coût logistique et cinématiques certifiés.
- Variantes de siège (multi-seeds), IA défense active, réglage du
  rythme, journal de causes et statistiques de Balance Lab.
- Tests visuels et de performance Windows/Linux/macOS, non inférés
  d'une simple suite `unittest`.

Voir la [roadmap 5.0→6.0](../DRAWTEMP_5_0_TO_6_0_DETAILED_ROADMAP.md).
