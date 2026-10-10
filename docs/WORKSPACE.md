# 2.5.5 — Project Workspace (foundation)

Le nouvel onglet **Espace projet** de `python -m sporebound editor` sert de
porte d'entrée au Studio. Cette PR n'invente **aucun nouveau format** :
`Content` conserve cartes, missions, compétences, classes et équipements ;
`GameProject` conserve écran titre, campagnes, scénarios et assets. L'index
est recalculé à partir des objets validés présents en mémoire.

## Utilisation

1. Ouvrir le Studio avec `--content chemin/vers/content.json`. Le projet
   associé se trouve par défaut à `content.game.json` ; les deux documents
   restent indépendants.
2. Dans **Espace projet**, déplier *Campagnes*, *Cartes et missions*,
   *Scénarios et dialogues*, *Personnages et monstres*, *Compétences*,
   *Classes*, *Équipements* ou *Assets et animations*.
3. Double-cliquer sur une mission pour sélectionner sa carte existante ; sur
   une campagne pour rejoindre le panneau de configuration ; sur un scénario
   pour ouvrir l'éditeur de dialogues ; sur un personnage pour rejoindre la
   bibliothèque d'archétypes.
4. **Nouvelle carte / mission** crée une mission vierge via
   `authoring.add_blank_mission` (dimensions 4–128), avec validation
   `Content` et `GameProject` avant insertion dans l'historique Undo/Redo.
5. **Dupliquer la mission** recopie son terrain, ses acteurs et objets mais
   efface ses arcs `next_missions` afin de ne pas créer accidentellement
   une nouvelle branche de campagne.
6. **Nouvelle campagne** ajoute une entrée de manifeste avec la mission
   active comme départ, après validation des références.
7. **Vérifier projet et assets** valide le projet et les fichiers référencés
   par le registre 2.4.3, y compris leurs chemins portables et signatures.

Les erreurs sont refusées sans mutation du document d'origine ; le navigateur
n'écrit jamais de fichier lors d'une simple sélection. Les noms/IDs des
missions et campagnes sont validés par les modèles existants.

## Enregistrement et contrats

- La carte et les règles restent dans **Enregistrer sous** (contenu tactique).
- La narration, les campagnes, les options et le registre d'assets restent
  dans **Enregistrer projet de jeu…** (manifeste `*.game.json`).
- Les sauvegardes joueur, checkpoints et replays ne sont pas transformés.
- Les contrôles du navigateur n'importent pas Tk dans `sporebound.workspace` :
  le moteur de combat et `GameSession` restent headless.
- Il n'existe pas encore de transaction disque atomique portant sur les deux
  fichiers. Si les deux changent, enregistrer **les deux** avant de quitter.

## État d'avancement et prochaines PR

Cette fondation fournit un index global, un chemin d'accès cohérent vers les
éditeurs et la création guidée de campagnes et missions. Elle ne prétend pas
compléter le gate 2.5. Restent : édition graphique complète des compétences,
classes, assets et menus (2.5.3), création de cartes multi-calques (2.5.1),
conditions logiques ET/OU (2.5.2), et campagnes/sieges multi-fronts (2.5.4).
Les ressources sans éditeur spécialisé restent inspectables dans l'index ;
leur modification guidée sera traitée dans les PR correspondantes.

## Tests

```sh
python -m unittest discover -s tests_standalone -p test_workspace.py -v
python -m unittest discover -s tests_standalone -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_workspace_gui.py -v
```

Ces tests vérifient l'inventaire stable, la non-mutation en cas d'échec, les
références de campagne et le passage Studio → carte → création d'une mission.
