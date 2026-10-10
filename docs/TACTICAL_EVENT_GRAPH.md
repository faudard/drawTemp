# 2.5.2 — Graphe des événements tactiques

Le Studio possède désormais un onglet **Graphe des événements**, complémentaire
de l'éditeur **Événements par blocs**. Il permet de visualiser et d'éditer les
conditions et actions d'une mission sans modifier manuellement son JSON.

## Modèle réellement exécuté

Une mission contient une liste ordonnée de déclencheurs :

```text
Mission
  1. SI tick >= 10          -> Message -> Danger -> Apparition
  2. SI HP(boss) <= 50 %     -> Message -> Statut -> Vague de renforts
  3. SI joueurs sur la case -> Message -> Ouvrir le combat suivant (règles existantes)
```

**Attention :** chaque déclencheur est exécuté **une seule fois** pendant une
bataille et ses actions sont exécutées **séquentiellement**. La priorité des
événements est leur ordre dans `Mission.triggers`. L'éditeur représente
l'ordre réel du runtime ; les flèches graphiques ne constituent pas un moteur
de règles supplémentaire, et il n'introduit ni scripts exécutables ni types
de conditions composites que le runtime ne connaît pas.

## Parcours dans le Studio

1. Ouvrir une mission puis l'onglet **Graphe des événements**.
2. Créer un déclencheur : saisir un **Nouvel ID**, choisir le type de condition
   et sa valeur, puis **Créer événement**. Il commence avec un message.
3. Sélectionner le nouveau nœud vert dans le graphe pour modifier sa condition
   avec **Appliquer condition**.
4. Choisir l'onglet **Actions**, configurer un type et cliquer **Ajouter**.
   Les nœuds bleus correspondent aux actions dans leur ordre d'exécution.
5. Sélectionner un nœud ou une action dans la liste pour la **Remplacer**,
   **Supprimer**, ou utiliser les flèches pour modifier son ordre.
6. Les commandes **↑ Priorité / ↓ Priorité** changent l'ordre d'évaluation
   des événements entiers, pas celui de leurs actions.
7. **Éditeur par blocs** ouvre la représentation précédente du même
   événement. Les deux éditeurs partagent la même source `Content`.

Toutes les commandes passent par `Content.from_dict` et
`Document.replace`, ce qui garantit Undo/Redo et le rejet atomique des
conditions, positions et références invalides.

## Déclencheurs pris en charge

| Type | Signification |
|---|---|
| `tick` | Horloge tactique supérieure ou égale à la valeur |
| `enter` | Un personnage joueur atteint la case |
| `defeated` | L'unité surveillée est vaincue |
| `hp_below` | L'unité vivante atteint le seuil de PV spécifié |
| `wave_capacity` | Effectif vivant du camp inférieur ou égal à une limite |

## Actions prises en charge

| Action | Effet |
|---|---|
| `message` | Émettre un texte dans le journal |
| `hazard` | Appliquer un danger à une case |
| `status` | Appliquer un statut à une unité |
| `spawn` | Invoquer un acteur |
| `despawn` | Retirer un acteur |
| `queue_wave` | Mettre en attente une vague de renforts |
| `wave` | Déclencher une vague suivant la capacité du moteur |

Les renforts sont authorés depuis un identifiant et un archétype existant
dans le catalogue, puis validés à la création. La version actuelle du
formulaire permet un seul nouveau personnage par bloc de vague ; les
groupes multi-personnages peuvent encore être composés par l'éditeur
avancé et le JSON validé. Une duplication d'événement est refusée pour
les actions `spawn` et `wave` afin de ne pas dupliquer silencieusement
les identifiants d'acteurs.

## Architecture et tests

- `sporebound/event_graph.py` : projection DAG bornée et déterministe,
  modifications transactionnelles de conditions, actions et priorités.
- `sporebound/event_composer.py` : extension de l'auteur visuel aux
  règles `wave_capacity`, `wave`, `queue_wave` déjà présentes.
- `sporebound/studio_event_graph.py` : dessin Tk Canvas, inspection d'un
  nœud, contrôles et navigation avec l'éditeur par blocs existant.
- `tests_standalone/test_event_graph.py` et `test_event_graph_gui.py` :
  invariants, références, ordre d'exécution, rendu et sauvegarde.

Exécution :

```sh
python -m unittest discover -s tests_standalone -p test_event_graph.py -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_event_graph_gui.py -v
```

## Limites et suite

L'édition des conditions composées ET/OU/NON reste dans le **graphe
narratif**, car le runtime des triggers tactiques ne les prend pas encore
en charge. Les transitions vers d'autres missions sont gérées par le
graphe de campagne. La prochaine évolution du système tactique sera
une définition de règles composites côté runtime, avec validation,
compatibilité des sauvegardes et replay déterministe, avant leur
exposition graphique.
