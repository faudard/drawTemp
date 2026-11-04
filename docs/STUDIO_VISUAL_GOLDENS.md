# DrawTemp Studio — captures de référence et contrôle visuel des PR

## Fonctionnement

Le workflow [Studio PR visual review](../../.github/workflows/studio-pr-visual.yml)
démarre le **véritable Studio Tk** avec une carte Valcroix créée par les
commandes métier existantes (et non une imitation de l’interface).

La CI exécute quatre scénarios à taille de fenêtre fixe 1280 × 850 :
`01-studio-2d-textures-autotiles`, `02-studio-2d-grid`,
`03-studio-iso` et `04-studio-playtest`. Les captures sont générées sous
Ubuntu 24.04 / Xvfb et Pillow épinglé, avec une fenêtre de 1600 × 1000.

Chaque exécution produit un artefact GitHub Actions (PNG, manifest JSON,
`index.html`), conservé 30 jours. L’onglet *Actions* de la PR contient un
lien de téléchargement. Un commentaire automatique ajoute le lien aux
captures. Les contrôles techniques vérifient la présence d’une scène réelle,
les dimensions, le nombre d’objets Canvas, le contraste des captures,
l’état du bouton Playtest et l’empreinte SHA-256 des images.

## Avant / après / différence

`scripts/studio_visual_goldens.py compare` charge **uniquement** une
référence qui a été explicitement approuvée dans le dépôt, avec un manifeste
`reviewed: true`, l’identité du relecteur et le SHA-256 de chaque PNG.

Pour chacun des quatre scénarios, le rapport génère :

- `approved/<scenario>.png` : **avant**, référence approuvée ;
- `<scenario>.png` : **après**, capture actuelle ;
- `diff/<scenario>.png` : écarts visibles, surlignés en rouge ;
- `comparisons/<scenario>.png` : comparaison côte à côte, sur trois colonnes.

Un pixel est considéré comme changé si un canal dépasse **12/255**.
Le seuil automatique est **0,5 % de pixels modifiés**. Un changement de taille,
un fichier absent, un hash invalide ou un écart au-dessus du seuil invalide la
comparaison. Ce seuil est un détecteur de régression, **pas** une évaluation
esthétique ou une validation fonctionnelle.

## Première approbation : décision humaine obligatoire

Au départ il n’y a **aucune référence approuvée**. Le rapport dit
`review_required` plutôt que `pass`, et publie uniquement les
**captures candidates**. Le workflow n’approuve jamais ses propres images.

Pour constituer la première référence :

1. Télécharger le ZIP `studio-ui-visuals-<PR>` d’une exécution CI saine
   et inspecter manuellement tous les PNG sur GitHub ou localement.
2. Extraire le ZIP, vérifier le rendu souhaité, puis lancer **hors CI**
   depuis la racine du dépôt :

   ```bash
   python -m scripts.studio_visual_goldens approve \
      --capture ./studio-visual-review \
      --reviewer "Nom du relecteur"
   ```

3. Vérifier les nouveaux fichiers sous
   `tests_standalone/goldens/studio-tk/tk-linux-xvfb-1280x850/`,
   puis les ajouter dans **une PR de référence séparée**, à revoir et fusionner
   manuellement. Ne jamais promouvoir la référence depuis le workflow.

Les approbations ultérieures exigent également une PR distincte :
le script refuse d’écraser une référence existante. Aucun token GitHub de CI
ne possède le droit d’écrire un golden dans le dépôt.

## Commandes

```bash
python -m unittest tests_standalone.test_studio_visual_goldens -v

SPOREBOUND_GUI_SMOKE=1 xvfb-run -a -s "-screen 0 1600x1000x24" \
  python -m scripts.capture_studio_pr --output ./studio-visual-review

python -m scripts.studio_visual_goldens compare \
  --capture ./studio-visual-review

# Mode strict : échoue également si aucune référence approuvée n'existe.
python -m scripts.studio_visual_goldens compare \
  --capture ./studio-visual-review --require-approved
```

La pipeline n’utilise **pas** `--require-approved` tant que le premier jeu
d’images n’a pas été examiné et fusionné : cela garde les captures candidates
disponibles sans annoncer artificiellement un succès de comparaison. Dès la
première approbation, une régression fait échouer le job de capture.

## Portée et limites

- Les références sont propres à ce profil **Linux/Xvfb**. Comparer les pixels
  Windows, macOS, un autre DPI ou une version différente des polices/Tk
  nécessite un profil et des captures approuvées distincts.
- Les sorties `index.html` fonctionnent **hors ligne**, dans le dossier
  extrait de l’artefact, avec les images relatives à ce fichier.
- Les changements intentionnels de design peuvent faire échouer le test :
  examiner d’abord la régression, puis soumettre un changement de golden
  séparé après validation humaine.
- Le PNG ne prouve pas l’absence de problème de focus, de clavier ou de
  performances : conserver les tests fonctionnels et l’inspection Windows.
