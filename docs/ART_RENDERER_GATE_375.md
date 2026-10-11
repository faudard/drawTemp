# 3.7.5 — Jeanne Art & Renderer Gate

## Statut et décision technique

**Jalon 3.7.5 : comparaison mesurée et choix du renderer de référence documentés.**

La branche a été réconciliée avec la campagne Acte I de la PR #62 : les 13 scènes,
les choix de recrutement, les missions de Vaucouleurs et les conséquences restent
présents. Les animations et le portrait Jeanne sont ajoutés au manifeste actuel,
sans retour à l'ancien prologue.
Le renderer de production reste **Tk Canvas** pour le vertical slice Jeanne :
c'est le seul backend déjà connecté à `BattleFrame`, au Studio et aux contrôles
de campagne, sans dépendance optionnelle. Le code tactique Python reste headless.

Ce choix reste **local au vertical slice actuel** : la comparaison des blits
mesure pygame-ce et PySide6 plus rapides que Tk sur Ubuntu/Xvfb, mais aucun des
deux n'est actuellement intégré à toutes les interactions du Player.
Ne pas migrer le Player avant validation clavier, DPI, packaging, autosave
et mesure des scènes complètes. Le jalon 3.7.5 fixe l'architecture présente ;
une migration éventuelle relève d'un jalon ultérieur.

## Première héroïne jouable : Jeanne

![Atlas de Jeanne](../sporebound/content/art/jeanne/jeanne_atlas.png)

- Direction artistique originale, sans reproduction d'une licence : cheveux
  **blonds**, yeux **bleus**, armure de campagne argentée, tunique bleu acier,
  détails or et lin. 2D pixel-art lisible dans une case tactique.
- Atlas PNG RGBA : **256 × 512**, frames **64 × 64** ;
  colonnes `south, north, east, west` ; lignes
  `idle_0, idle_1, move_0, move_1, attack_0, attack_1, hit_0, defeat_0`.
  Le portrait principal (256 × 256) et quatre expressions (192 × 192) proviennent de la **direction artistique validée**.
- Identifiants stables `jeanne_<direction>_<action>_<frame>` et bindings
  `jeanne_<action>_<direction>` dans
  `sporebound/content/jeanne.game.json`. Portrait associé à l'intervenante
  de dialogue `Jeanne`. Pas de JSON manuel pour jouer la démo.
- Découpe des régions d'atlas en mémoire via `PhotoImage copy` ; la source
  est décodée **une fois** par renderer et les frames sont cachées.
  Les sprites et portraits classiques à fichier unique restent compatibles.
- Les animations sont cosmétiques : elles ne progressent pas le CT, les ticks,
  la RNG, les replays ou les sauvegardes.
- Les autres personnages restent en fallback vectoriel.

**Direction artistique validée :** le design de Jeanne — tresse et ruban bleu,
cheveux blonds, yeux bleus, armure argentée, bleu royal, lin et détails dorés —
est approuvé pour la campagne. Les images intégrées sont dérivées de la planche
de validation visuelle produite pour `drawTemp`; aucun personnage de franchise
tierce n'a été recopié dans les assets.

Portrait principal :

![Portrait validé de Jeanne](../sporebound/content/art/jeanne/jeanne_portrait.png)

Variantes : `Jeanne_neutral`, `Jeanne_smile`, `Jeanne_determined`,
`Jeanne_battle_shout` sont disponibles dans le registre `portrait`,
sans ajouter de nouvelles propriétés à `GameProject`. Le slot existant
`Jeanne` pointe désormais sur le portrait principal; les quatre variantes
sont prêtes pour la prochaine passe de scènes cinématiques.

**Limites restantes** : l'atlas tactique 64 × 64 reprend les silhouettes et
la palette du concept validé, mais des séquences (notamment de dos) utilisent
encore des poses dérivées. Les animations directionnelles plus riches,
expressions additionnelles et VFX cohérents devront passer une validation
graphique distincte. Aucune validation de performance renderer n'est
présumée par cette approbation artistique.

Les sources sont des visuels générés pour ce projet. Les décors, FX et autres
personnages ne sont pas modifiés ici.

## Comparaison concrète, même workload

```sh
python -m unittest tests_standalone.test_jeanne_art_375 -v
python -m sporebound validate --content sporebound/content/jeanne.json --project sporebound/content/jeanne.game.json

# Dans une session graphique (X11/Wayland/Windows/macOS) :
python scripts/benchmark_renderers_375.py --backend tk --actors 80 --scale 1
python -m pip install pygame-ce PySide6  # uniquement dans un venv de test
python scripts/benchmark_renderers_375.py --backend pygame --actors 80 --scale 1
python scripts/benchmark_renderers_375.py --backend qt --actors 80 --scale 1
```

Pour automatiser la matrice complète et conserver les mesures par exécution,
lancer le collecteur (processus isolé par point de mesure) :

```sh
python scripts/collect_renderers_375.py --dry-run --output matrix.json
python scripts/collect_renderers_375.py \\
  --backends tk pygame qt --actors 20 80 200 --scales 1 2 \\
  --repeats 3 --frames 120 --output renderers-local.json

# CI Linux : smoke de performance réel sous Xvfb et artifact de preuves
xvfb-run -a python3 scripts/collect_renderers_375.py \\
  --backends tk --actors 20 80 --scales 1 2 \\
  --repeats 2 --frames 120 --output tk-evidence.json
```

Le rapport contient les 54 essais individuels attendus pour une matrice complète
(Tk/pygame-ce/PySide6 × 20/80/200 × 1x/2x × trois répétitions), le p50/p95 de
chaque essai, la médiane des p50/p95 et le p95 maximal par scénario.
Une bibliothèque optionnelle ou un display absent provoque un **échec explicite**,
jamais une mesure fictive ni un faux backend ignoré. Le critère p95 inférieur
à 33,3 ms est un indicateur non décisionnel du benchmark de blit :
il ne valide pas à lui seul les performances réelles du Player.

Chaque invocation doit utiliser un **processus indépendant**. Exécuter pour
`--actors 20, 80, 200`, `--scale 1, 2` sur Windows, Ubuntu et macOS, au
moins 120 frames et trois répétitions après warmup. Conserver les JSON obtenus
comme preuves de l'arbitrage. Les trois backends présentent la **même** région
de l'atlas RGBA, sur un viewport 800 × 600 avec les mêmes positions
déterministes et une image complète à chaque frame.

Le script mesure p50/p95 du temps mur du rendu + présentation UI, et un pic
**Python** via tracemalloc. Ce dernier n'inclut **pas** les allocations
natives Qt/SDL/Tk ou GPU : mesurer la mémoire résidente du processus avec un
outil OS dans le relevé final. La parité des outils GUI ne signifie pas
encore parité complète avec le Player (tuiles, overlays, sélection) : ce
prototype isole le coût du blit, avant un éventuel spike de Player alternatif.

### Mesures reproductibles : Ubuntu/Xvfb — 11 octobre 2026

Le [workflow comparatif #38131081008](https://github.com/faudard/drawTemp/actions/runs/38131081008)
a exécuté avec succès **54 échantillons réels** sur **un même runner**
(Python 3.12.15, viewport 800×600, 120 frames + warmup,
3 backends × 3 populations × 2 échelles × 3 répétitions).
La synthèse ci-dessous donne la **médiane des p95** de trois répétitions,
en millisecondes, selon le collecteur de la PR.

| Population et échelle | Tk Canvas | pygame-ce | PySide6 |
| --- | ---: | ---: | ---: |
| 20 acteurs / 1× | 1,299 | 1,295 | 0,209 |
| 20 acteurs / 2× | 2,088 | 1,410 | 0,227 |
| 80 acteurs / 1× | 4,415 | 1,626 | 0,420 |
| 80 acteurs / 2× | 7,321 | 1,948 | 0,490 |
| 200 acteurs / 1× | 10,428 | 2,369 | 0,874 |
| 200 acteurs / 2× | 17,572 | 2,926 | 1,042 |

**Portée exacte :** le benchmark mesure le coût du dessin de la même image,
de l'effacement et du traitement des événements ; il ne compare pas encore
le moteur de rendu *complet* de drawTemp, les tuiles, surcouches, télégraphes,
animations complexes, réactivité des menus ou consommation mémoire native.
L'API `QWidget.repaint()` n'offre pas exactement la même garantie de
présentation écran que `pygame.display.flip()` : comparer les valeurs en
tant qu'indicateurs de coût CPU sur ce workload, **pas** comme des FPS
équivalents ou une preuve de supériorité visuelle. Xvfb n'est pas un
GPU de joueur. Les p95 ne sont pas des délais garantis.

**Arbitrage 3.7.5 :** conserver **Tk Canvas** comme backend de référence
du vertical slice Jeanne, car il existe déjà, a des contrôles de campagne,
un registre d'assets, les tests clavier et des builds Windows/Linux/macOS.
Le scénario synthétique 200 acteurs × 2× reste sous **33,3 ms p95**
sur ce runner. Pour des batailles plus riches et/ou un objectif 60 FPS
à 200 acteurs, prioriser un **spike pygame-ce** centré sur `BattleFrame` ;
tester PySide6 si l'accessibilité native, le DPI et les outils GUI compensent
sa distribution Qt. La migration ne doit jamais altérer le moteur headless.

### Gate 3.7.5 et limites avant migration

| Critère | Cible | Situation |
| --- | --- | --- |
| 4 directions × 5 états + portraits | Runtime, PNG validés, GUI Tk | Réussi (PR #64) |
| Sécurité des régions d'atlas | Rejet des dimensions/coords invalides | Réussi (tests) |
| Gameplay et replay headless inchangés | CI Python 3.10/3.12/3.14 sur 3 OS | Réussi sur le head de référence |
| Comparaison Tk/pygame-ce/PySide6 | 54 mesures réelles × p50/p95, un même runner | Réussi (Linux/Xvfb) |
| Performance Player réel | 20 à 200 acteurs + overlay/zoom/caméra, p95 cible | À mesurer avant migration |
| A11y et contrôles clavier | Aucun recul sur Player complet | Régressions de base couvertes ; audit manuel restant |
| Packaging multi-OS | Wheel avec atlas, portrait et expressions | Réussi (distribution CI) |
| GPU/hardware et macOS/Windows | Comparatif visuel sur machines de jeu | À programmer en validation approfondie |

**Décision de livraison 3.7.5 :** Tk est conservé ; les gates de migration sont distincts.
En cas de p95 trop élevé sur le Player réel, privilégier un spike
`pygame-ce` pour le combat, tout en gardant le Studio en Tk, et mesurer le
coût de deux runtimes. Considérer PySide6 si l'accessibilité et la gestion DPI
font gagner davantage que le coût de distribution Qt. Pas de réécriture du
moteur tactique, des formats d'assets ni des sauvegardes pour un renderer.

## Compatibilité de sauvegardes

L'ajout d'un registre non vide modifie le digest du projet Jeanne, comme prévu
par `docs/ASSET_PIPELINE.md`. Les checkpoints Jeanne antérieurs doivent donc
être **déclarés incompatibles**, sauf migration explicite après audit ; ne
jamais rejouer une sauvegarde sous un nouveau digest sans avertissement. Les
projets sans assets ne changent pas. Ce changement ne concerne ni les tables
tactiques ni les replays headless autonomes.
