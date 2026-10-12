# 3.7.17A — Le Pont de Valcroix : village fortifié de référence

## Objectif et périmètre

Cette PR matérialise le premier **terrain de validation graphique reproductible**
de l'éditeur isométrique. Elle n'ajoute ni nouvel outil de construction,
ni sprite inventé : elle **utilise exclusivement les API d'édition existantes**
et les vrais atlas déjà empaquetés. Aucune carte JSON n'a été écrite à la main.
Un utilisateur peut ensuite ouvrir, modifier, sauvegarder et jouer cette
mission dans le Studio.

Le niveau fait **26 × 20 cases** et comprend :

- rivière incurvée, deux rives sableuses, pont 3 × 2 franchissable ;
- route de traversée, placette de village pavée et cour intérieure ;
- trois maisons, une tour, une ruine et quatre segments de remparts,
  dont un accès ouvert au niveau de la route ;
- arbres, buissons, rochers, roseaux, lanternes et mobilier ;
- un attaquant à l'ouest et un défenseur à l'est, dans des zones accessibles ;
- une porte et un coffre interactifs, plus un événement au franchissement.

Les objets et unités sont créés ou déplacés au moyen des opérations
`Document` et `authoring`. Les variantes de sols restent celles
du renderer déterministe. Les images d'architecture continuent à provenir
de la détection des **tampons de terrain intacts** (dette 3.7.17B).

## Construction et jeu — zéro modification manuelle de JSON

Depuis la racine du dépôt :

```sh
python -m examples.fortified_village_3717a --output village.json
python -m sporebound validate --content village.json
python -m sporebound editor --content village.json
```

Dans le Studio, choisir la mission **Le Pont de Valcroix**,
activer la vue isométrique et tester le placement d'un nouvel arbre ou
d'une maison depuis **Bibliothèque d’assets** (la PR #83 est une amélioration
indépendante du survol des PNG). **Enregistrer sous**, rouvrir le contenu,
puis choisir **Playtest**. Pour lancer le Player autonome :

```sh
python -m sporebound player --content village.json
```

Le scénario est généré depuis le contenu d'exemple standard : il conserve
les autres missions de base pour ne modifier aucune référence globale.
L'export autonome complet avec reprise et campagne reste le gate 3.7.22.

## Architecture

- `examples/fortified_village_3717a.py` :
  seul orchestrateur de composition. Il réutilise
  `add_blank_mission`, `Document.paint_many/paint_rectangle/place_unit`,
  `place_structure`, `add_object` et `add_event`.
  Aucune dépendance supplémentaire ; la fonction
  `build_village_document(Content)` est utilisable par les tests.
- `tests_standalone/test_reference_village_3717a.py` :
  village constructible, détectabilité des dix tampons, connexion terrestre
  entre les deux acteurs à travers l'eau, objets/événement, sauvegarde,
  rechargement, replay et undo/redo.
- `tests_standalone/test_reference_village_3717a_gui.py` :
  rendu du vrai terrain et des PNG dans Tk, picking du pont, éléments de
  scène réellement créés à 24, 54 et 96 px/case. Le job CI Linux/Xvfb
  archive les trois captures PNG et le niveau généré.

La grille tactique et les données sont les mêmes que celles du moteur headless.
**Aucun changement** de combat, CT, IA, pathfinding, formats de cartes,
sauvegardes et replays. Les quatre loaders utilisés restent facultatifs :
une indisponibilité PNG n'empêche pas l'ouverture ni le jeu.

## Contrôles et preuve

```sh
python -m unittest discover -s tests_standalone \
  -p test_reference_village_3717a.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover \
  -s tests_standalone -p test_reference_village_3717a_gui.py -v
python -m unittest discover -s tests_standalone -v
```

Le job `editor` de `.github/workflows/standalone.yml` produit l'artefact
**village-reference-3717a** (JSON + vues 24/54/96). Les captures sont des
preuves du rendu sur Linux/Xvfb, non une certification artistique.
Il faut inspecter les images et répéter la vue native sur Windows et macOS
avant de fermer le gate visuel final.

### Critères 3.7.17A

- [ ] La suite headless et les contrôles Tk/Xvfb passent sur le SHA de la PR.
- [ ] Un créateur ouvre le niveau généré, modifie via l'éditeur, sauvegarde
      et recharge sans intervention dans le JSON.
- [ ] Les dix structures et les personnages restent visibles et sélectionnables
      à trois zooms.
- [ ] Les rives, le pont, les raccords, l'échelle et l'éclairage sont revus
      à partir des captures réelles (pas seulement des assertions).
- [ ] Comparaison Studio → Player, avec sauvegarde et reprise de combat.
- [ ] Matrice Python et vérification des distributions sur 3 OS terminées.

## Dettes et suite

**3.7.17B (P0, L)** : un pinceau sur la case d'un bâtiment peut encore
faire disparaître son sprite entier, car sa reconnaissance exige le motif
original intact. Spécifier un contrat d'identité persistante rétrocompatible,
sans altérer silencieusement le déplacement ni les replays.

**3.7.16C (P1, M)** : registres PNG de projet et acteurs/animations intégrés
à la palette, avec diagnostics et variantes explicites.

**3.7.18D (P0, M)** : p95 de rendu/occlusion du village et caches
sur 32²/64²/128², après clôture de #82.

**Direction artistique** : les atlas disponibles sont encore des ébauches
pixel-art. Un passage de validation graphique humaine devra unifier
proportions, échelle, palette, relief, éclairage et silhouettes des acteurs.
Produire davantage de PNG avant cela ajouterait surtout de la dette.

## Revue de trois captures CI — 12 octobre 2026

Première inspection humaine des vues générées sur
[la CI de la PR #84](https://github.com/faudard/drawTemp/actions/runs/38264348042)
(artefact `village-reference-3717a`) :

- Le village est lisible en plan isométrique : route et franchissement,
  espaces bâtis et accès à la forteresse se distinguent. Le plateau tient
  dans la vue générale à 24 px/case.
- **Défaut P0 :** aux zooms 54/96, une zone d'eau décorative déborde
  visuellement sous le pont et ne suit pas le chenal du terrain. Examiner
  le PNG pont de `fortifications.png`, ses pixels alpha, son ancrage et
  l'ordre de dessin avant de décider du correctif. L'origine exacte
  n'est pas encore prouvée.
- **Défaut P0 :** dans la vue générale une ombre apparaît détachée
  sous le plateau ; inspecter le cadrage et les ombres incorporées aux
  sprites. Ne pas considérer ce rendu comme final.
- **Dette artistique P1 :** les combattants restent des marqueurs ronds
  avec noms hérités du contenu standard, non des personnages chibi
  illustrés. Le décor pixel-art et les acteurs ne partagent pas encore
  la direction artistique demandée.
- La scène générée et trois PNG peuvent être téléchargés ensemble dans
  l'artefact du job `editor`. Ils ne valent pas preuve Windows/macOS.

**Gate visuel 3.7.17A : non validé.** Ne pas marquer ce jalon « terminé »
à la seule lecture des tests automatiques. Donner priorité au traitement
des défauts visibles avant d'élargir les packs d'assets.

