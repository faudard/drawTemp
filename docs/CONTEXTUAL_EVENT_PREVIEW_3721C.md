# 3.7.21C — Événements et prévisualisation contextuelle

## Livraison (incrément compatible avec master)

Dans **Graphe des événements**, la sélection d'une condition ou d'une action
ouvre un panneau **Contexte et prévisualisation** sans quitter le graphe.

- Le panneau lit le déclencheur réel de `Mission.triggers`, en conservant
  l'ordre et la priorité des actions tels qu'utilisés par le Player.
- Les boutons **Scène liée** et **Cinématique liée** ouvrent les éditeurs
  canoniques lorsqu'une ressource de la **mission** est présente.
- Le lien narratif concerne `story.after_mission[mission_id]`, donc **après la
  victoire**. Les cinématiques visibles ont `before_mission` ou
  `after_mission` pour déclencheur. Elles ne sont **pas** activées par le
  déclencheur tactique sélectionné.
- Le bouton **Tester avec le moteur** instancie une bataille jetable à partir
  d'une copie du contenu, désactive les autres déclencheurs, puis réinjecte le
  déclencheur choisi dans `rules.triggers.dispatch`. Le prédicat et les
  actions sont donc exécutés par le **moteur existant**, jamais réinterprétés
  par l'interface.
- Le résultat indique si la condition a été satisfaite, les événements
  émis par le moteur, les unités ajoutées/retirées et les erreurs d'exécution.
  L'ensemble est sans écriture ni modification du projet, de la mission ou
  de l'historique undo/redo.

## Parcours de validation

1. Ouvrir le Map Editor → onglet **Graphe des événements**.
2. Créer un déclencheur `tick >= 5` avec action `message`.
3. Sélectionner son nœud, tester au tick `4` : aucune activation.
4. Tester au tick `5` : événement `trigger` puis `message`.
5. Revenir aux blocs, déplacer une action, revenir au graphe : l'ordre est
   identique. Enregistrer et rouvrir : aucune donnée d'aperçu n'est sérialisée.
6. Configurer une scène après victoire et une cinématique de mission dans les
   éditeurs existants ; vérifier l'ouverture des deux ressources depuis le
   graphe. L'absence de lien désactive le bouton correspondant.

Commandes de régression :

```bash
python -m unittest tests_standalone.test_event_context tests_standalone.test_event_graph
# Linux avec Xvfb, même protocole que la CI :
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_event_graph_gui
```

## Limites connues (à ne pas confondre avec une cinématique jouée)

- Le tick fourni est une **sonde ponctuelle** du prédicat : les ticks
  intermédiaires ne sont pas simulés, aucune IA ni campagne n'est déroulée.
  Pour tester un enchaînement complet, utiliser le véritable playtest.
- Les objets de carte (leviers, portes), conséquences stratégiques et scènes
  cinématiques n'ont pas encore de lien direct `trigger → scène` dans le
  modèle de runtime. Le panneau ne crée pas de faux liens. Leur unification
  complète exige une évolution explicite et testée des contrats de jeu.
- L'aperçu est textuel et contextuel, pas un rendu visuel du Player. Une
  prévisualisation viewport synchrone reste un chantier distinct.
- Les opérations de sauvegarde globale, d'historique transversal et de
  récupération ne sont pas modifiées ici (3.7.21B).

Ce jalon ferme **l'incrément de navigation et de diagnostic tactique** de
3.7.21C, sans prétendre fermer l'intégration runtime narrative/cinématique
ou l'ensemble du Studio End-to-End.
