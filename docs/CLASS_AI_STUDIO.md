# 2.5.3.3 — Class Progression & AI Studio

Le **Character & Rules Studio** propose maintenant deux nouvelles vues :

- **Graphe des classes** : prérequis entre classes, niveaux requis, arbres de
  talents, coûts JP, bonus, compétences et spécialisations exclusives.
- **IA & patrouilles** : édition des étiquettes de rôle et des points de
  patrouille directement sur la grille de la mission.

Ces deux vues réutilisent les règles existantes de `Content v1`,
`builds3.validate_talent_trees` et `rules.tactical_behavior`.
Elles ne modifient ni les règles de combat, ni les slots de sauvegarde, ni
le contrat des replays.

## Graphe des classes

La vue de gauche montre les classes par niveau de dépendance, avec un lien
`A → B` lorsque **B requiert A**. La vue de droite affiche les talents
de la classe sélectionnée.

1. Cliquer une classe dans le graphe ou la choisir par son ID.
2. Sélectionner **Classe requise** et le **Niveau requis**, puis valider.
3. Cliquer un talent existant, ou saisir un nouvel ID dans
   **Talent / nouvel ID**.
4. Spécifier **Coût JP** (1 à 20), IDs des talents requis séparés par
   virgules, groupe de spécialisation exclusif, bonus de caractéristiques
   (par exemple `attack=2,max_hp=10`), et compétences débloquées.
5. Créer, modifier ou supprimer le talent.

Les graphes sont des vues déterministes des données, sans identifiants
temporaires enregistrés dans les projets. Les cycles de classes et de talents
sont interdits ; il est impossible de supprimer un talent référencé par un
autre. Les bonus et compétences sont validés par le moteur. Les chemins de
spécialisation exclusifs restent soumis aux règles d'achat en partie,
y compris le budget JP et les talents déjà débloqués.

Les opérations utilisent `Document.replace` et la pile
Undo/Redo existante du Studio. **Ouvrir la classe** renvoie au formulaire
classique, qui conserve la gestion du nom et des compétences par niveau.

## IA et patrouilles

Choisir une unité de la mission active : son profil et sa route sont chargés
depuis la véritable définition de l'unité.

Les routes peuvent être saisies sous la forme :

```text
2,1; 4,1; 5,3
```

Ou être dessinées en cliquant les cases de la miniature. Il faut au moins
**deux cases distinctes** ; les obstacles et les positions hors carte sont
rejetés. **Effacer route** rétablit l'IA tactique sans parcours imposé.

Les étiquettes de rôles se saisissent avec des virgules, par exemple
`medic,protector`. Elles sont stockées dans les tags natifs de l'acteur.

### Attention au ruleset coordonné

Le moteur standard connaît `tactical` et, lorsqu'une route est renseignée,
la politique tactique déléguée `patrol_behavior`. Le modèle ne crée **pas**
une nouvelle IA à partir des rôles indiqués : ils constituent des métadonnées
pour les comportements opt-in. En particulier, `coordinated` nécessite un
ruleset avancé explicite ; l'éditeur refuse de l'enregistrer silencieusement
dans un contenu classique.

L'aperçu est donc une **projection des données authored** : mode tactique ou
patrouille, rôles et points, et **non une simulation inventée de décisions IA**.
Un futur éditeur de doctrines et de priorités de choix devra définir la
version du ruleset et ses garanties de sauvegarde/replay.

## Contrats techniques

- `sporebound/class_ai_authoring.py` — API pure, DAGs de classes/talents,
  opérations atomiques et validation des routes.
- `sporebound/studio_class_ai.py` — éditeur Tk, graphes Canvas cliquables,
  formulaire de talents et miniature de carte à points de patrouille.
- `sporebound/studio_character_rules.py` — branchement dans le Studio,
  sans nouveau format de projet.
- `tests_standalone/test_class_ai_authoring.py` — vérification de cycles,
  références, validation du contenu, isolation de mission et Undo/Redo.
- `tests_standalone/test_class_ai_gui.py` — scénario réel sous Xvfb,
  création de talent, lien de classe, route, sauvegarde/rechargement.
- `.github/workflows/standalone.yml` — gate GUI dédié.

## Tests

```sh
python -m unittest discover -s tests_standalone -p test_class_ai_authoring.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_class_ai_gui.py -v
```

### Suite envisagée

Une étape dédiée pourra étendre les profils IA de façon versionnée avec un
véritable éditeur de priorités et de doctrines de groupe, un inspecteur de
décisions alimenté par le moteur et la gestion explicite du ruleset 2.7.
