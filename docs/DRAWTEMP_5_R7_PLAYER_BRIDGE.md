# DrawTemp 5 — R7.B : atlas d'animation dans le Player Qt 6

## Pourquoi ce lot

R7.A a ajouté l'éditeur, les recettes de personnages et l'export AssetRegistry
v1. Toutefois R3 et R12 n'affichaient encore que les mannequins rectangulaires.
R7.B raccorde le rendu **réel** des atlas créés par R7 à l'unique viewport
GPU Qt Quick partagé entre Studio et Player. L'ancienne vue Tk reste inchangée.

## Contrat d'intégration

1. Exporter une recette avec l'outil R7 (il utilise Pillow à la création).
2. Le pack contient atlas.png, registry.json et character.json, et, le cas
   échéant, les portraits. AssetRegistry v1 et AssetResolver R4 valident les
   PNG, régions, références et chemins avant le rendu.
3. Le renderer R3 accepte character_pack=... et character_variant=... dans
   make_controller() et create_view(). Le Player utilise le même contrôleur.
4. Le rendu Qt Quick sourceClipRect extrait la frame depuis l'atlas GPU au
   lieu d'afficher un placeholder. Le pivot de pied commun à toutes les
   directions corrige la position au sol sans perturber le picking.
5. Une horloge **visuelle**, indépendante du CT, sélectionne les frames suivant
   leur duration_ms. Idle boucle, attack affiche son cycle puis revient
   automatiquement à idle. Une direction non dessinée n'est pas inventée.
6. Les autres personnages sans pack gardent leur fallback vectoriel actuel.

Aucune modification Content, GameProject, combat, seed, sauvegarde ou RNG ;
les changements de tenue présentés ici sont des prévisualisations cosmétiques.
Le Player ne charge pas le Studio, Pillow ou Tk. Il lui suffit d'un pack PNG
exporté et de PySide6.

## Commandes de référence

~~~sh
python -m pip install ".[qt6,art]"
python -m drawtemp.assets.characters --template jeanne --root . --export .r7-pack
python -m drawtemp.render.qt_viewport --smoke --character-pack .r7-pack
python -m drawtemp.player.qt_app --reference --smoke --smoke-scene battle \
    --character-pack .r7-pack --character-variant historical

# Session interactive avec des sprites :
python -m drawtemp.player.qt_app --character-pack .r7-pack
~~~

L'atlas historique Jeanne ne contient que cinq familles : idle, walk,
attack, hit, death. Le pack confirme quatre orientations et une durée
par frame, mais **ne prouve pas** une animation artistique finale.
L'absence de run, block, magic et victory reste visible dans les diagnostics.

## Preuves attendues

- Tests headless de résolution R7 dans les quatre directions, durées exactes,
  fin de clip non bouclée, fallback, chemins invalides et immutabilité.
- Test Qt affichant le véritable sprite sourceClipRect depuis le même
  RendererController que le Player.
- Smoke QML R3 et Player R12 sur Ubuntu, Windows et macOS ; tests de
  compatibilité R3/R4 existants.
- Parité des états tactiques et sauvegardes (aucun champ visuel ajouté au Core).

## Restant pour la certification R7

- Véritables costumes Jeanne paysanne / apprentie / armure / blessée, animés,
  cohérents sur 4 directions et construits à partir de dessins distincts.
- Intégration du choix de costume avec les modèles équipement R8 et la
  persistance du projet via la transaction d'assets R4. Le flag
  character_pack est une **intégration opt-in vérifiable**, pas une
  nouvelle source métier.
- Animation de déplacement corrélée au chemin Player (au lieu de déclencher
  seulement un clip visuel après l'action), animation d'impact et
  synchronisation visuelle.
- Revue humaine des captures du renderer avec des personnages/zones de
  profondeur réels, vérification 24/54/96 px et budget GPU.

La fermeture du gate R7 reste explicitement **ouverte**.
