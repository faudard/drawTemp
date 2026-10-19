# R30.F — Profilage CPU, montée en charge et budgets d'assets

**État : première tranche R30.6 proposée en PR draft, empilée sur R30.E
(#350), R30.D (#343), R30.C (#340), R30.B (#329), R30.A (#305).**

Objectif : instrumenter réellement le coût de cinq chemins canoniques du
Creator et de deux charges synthétiques, enregistrer des mesures traçables,
comparer seulement des environnements/scénarios compatibles et consulter des
graphiques dans le Studio, sans compromettre les Content/GameProject.

## Charges mesurées

| Opération | Source | Contrat |
|---|---|---|
| authoring_open | Content/GameProject canonique | Construction d'une nouvelle session validée (mémoire) |
| snapshot | session canonique | Snapshot immuable et conversion document |
| resource_projection | session canonique | Projection des cartes, acteurs, événements, scènes pour le Studio |
| gallery_load | galerie R30.E réelle | Chargement/validation du catalogue distribué |
| asset_inventory | GameProject.assets canonique | Validation des chemins et somme des tailles physiques, sans décodage |
| synthetic_resource_projection | dictionnaire synthétique | 10 à 10 000 scènes purement projetées, non validées en gameplay |
| synthetic_asset_registry | registre synthétique | 10 à 10 000 chemins d'assets, sans fichiers physiques ni licence validée |

Le rapport identifie chaque opération avec workload_kind = canonical ou
synthetic. Les métriques sont des durées réelles perf_counter_ns, en ms :
p50, p95, p99, maximum, plus pic de mémoire Python tracemalloc. Les mesures
ne prédisent ni FPS ni qualité GPU. Les pics tracemalloc ne couvrent pas
toute la mémoire native du processus ou les allocations GPU.

Chaque opération est mesurée séparément, après ses préchauffages. La collecte
d'un profil sur projet disque revérifie les SHA-256 des deux fichiers canoniques
après le test. Les assets ne sont ni extraits ni décodés : les paths de la
registry sont contrôlés par les garde-fous R14 et les tailles viennent de
stat sur les fichiers, sans attribuer de droit de redistribution.

## Utilisation de la CLI (Python 3.12 qualifié)

Profil référence Jeanne, préchauffage et 30 échantillons :

    python -m drawtemp.quality.r30_scale --samples 30 --warmups 3 --synthetic-resources 1000 --output cpu-reference.json

Profil d'un vrai projet enregistré :

    python -m drawtemp.quality.r30_scale --content chemin/jeu.json --samples 120 --warmups 5 --synthetic-resources 10000 --output cpu-projet.json

Les fichiers output n'écrasent jamais un fichier existant. La sortie
standard contient également le JSON de rapport. L'absence de --output
ne crée aucun fichier. Si la commande échoue, elle retourne un code
non nul ; aucun status green n'est synthétisé. Les sorties de CI sont
des artefacts, et non des baselines validées ou des seuils automatiques.

### Comparaison et budget régression p95

Un budget est **opt-in** : choisir une référence réellement comparable,
produite sur le même hôte, même Python/architecture/OS, même jeu, mêmes
tailles de charge, même nombre d'échantillons/préchauffages :

    python -m drawtemp.quality.r30_scale --content chemin/jeu.json --samples 120 --warmups 5 --synthetic-resources 10000 --baseline cpu-projet.json --max-p95-growth-pct 25 --min-delta-ms 1 --output cpu-projet-candidat.json

Le test bloque uniquement si la dégradation p95 dépasse **à la fois**
25 % ET 1 ms pour une opération. Code 2 = dépassement du seuil ;
code 1 = entrée/scénario invalide. Le bypass allow-host-mismatch existe
pour exploration uniquement, **pas pour certification** ; le rapport
indique comparable_hosts = false.

**La CI n'active aucun seuil absolu de latence sur des runners partagés.**
Une p99 calculée sur moins de 100 mesures est explicitement étiquetée
tail_exploratory = true. Les percentiles de CPU sont de la mesure
intra-processus, pas un budget frame-time de gameplay.

## Tableau de bord Qt

Ouvrir Studio, puis :

**Outils → Performance CPU et budgets**

Le dialogue R30ScaleDashboard lit un rapport JSON de schema
drawtemp-r30f-scale-v1, refuse les percentiles invalides, les opérations
manquantes et tout rapport revendiquant faussement une certification GPU
ou Player. Il affiche :
- graphique de barres p95/p99 CPU pour les sept opérations ;
- tableau p50/p95/p99/max et pic de mémoire Python ;
- inventaire des assets, tailles physiques et statut de vérification ;
- comparaison optionnelle avec une baseline existante.

Le graphique est dessiné en Qt Widgets (QPainter), sans bibliothèque Qt
Charts facultative. Mesurer un projet lourd s'effectue dans la CLI
pour éviter de bloquer l'event loop du Studio. Le tableau de bord est
strictement **en lecture seule** ; la session Editor n'est pas modifiée.

## Tests et critères

Headless :

    python -m unittest tests_standalone.test_drawtemp_r30f_scale -v

Qt offscreen :

    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_drawtemp_r30f_qt -v

Workflow R30.F : Windows, Linux, macOS ; Python 3.12 ; rapports CPU
artefacts ; R1/R14, R30.E et baseline Jeanne ; offscreen GUI.

Éléments bloquants restant hors tranche :

- p95/p99 GPU à partir de 120 frames et vraie carte graphique R14 ;
- UI responsive sous charges 10k avec interaction utilisateur et traces
  callback-to-idle (le profil actuel mesure seulement la projection) ;
- consommation native RSS, mémoire graphique, cache textures/audio et budgets
  de frames Player ; les mesures tracemalloc sont seulement Python ;
- création et validation de véritables grandes cartes/scènes/campagnes,
  résultats moteur inter-genres, profils de jeu long sur machines cibles ;
- validation R29 puis second jeu complet de genre différent (R30.10).

Le statut R30.6 reste donc **partiel** et R30.10 **bloqué**, même si la
CI headless/offscreen est verte ultérieurement.
