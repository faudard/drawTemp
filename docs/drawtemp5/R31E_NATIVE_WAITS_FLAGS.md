# R31.E — Attentes natives et drapeaux de journal (Game Logic Studio)

**Statut :** incrément en développement sur une PR dédiée issue de \`master\`. Le regroupement #339 est déjà **fusionné**, sa branche d'intégration a disparu : cette PR est son successeur, non un amendement à #339. Le gate complet R31 et les tests multi-OS restent à obtenir.

## Contrat R31.E

### 1. Séquences et attente par ticks

Un graphe **schema v3** est linéaire et borné : un déclencheur \`event\`, une liste d'actions, puis zéro ou plusieurs paires **\`wait(ticks)\` / liste d'actions** ou **\`flag(event_id)\` / liste d'actions**. Au moins une paire est nécessaire. Aucun cycle, join, fork ni nœud de contrôle sans action en aval n'est autorisé. Le nombre de nœuds est limité à 64, de phases **R9 natives** à 16 et d'attente à **1…10000 ticks**.

Chaque groupe d'actions produit un événement standard \`Mission.triggers\` : IDs stables \`r31_<graph>_s0\`, \`_s1\`… L'événement initial prend le déclencheur réel \`tick\` ou \`interact\`. Les suivants ont condition \`tick=0\` + \`after: [id_phase_précédente]\` et, sur le nœud \`wait\`, \`delay_ticks: n\`.

L'horloge de l'attente utilise **\`sporebound.temporal_events.temporal_status\`**, calculée uniquement depuis le **journal des événements R9 et le tick logique du Battle**. Aucune file d'attente auxiliaire, objet QTimer, thread ni gestion du temps par frame graphique.

### 2. Variable booléenne bornée : drapeau d'événement déclenché

Le nœud \`flag\` représente une **variable booléenne en lecture seule** : « le déclencheur R9 \`event_id\` a-t-il déjà été déclenché ? ». Il s'abaisse vers une dépendance native supplémentaire \`after\` sur la phase suivante.

- Les références d'événements natifs sont vérifiées lors de \`Content.from_dict\`; la validation du projet refuse les références inexistantes et les cycles de dépendances.
- Les références à des phases futures du **même** graphe sont rejetées avant le commit. Le drapeau ne peut pas être modifié arbitrairement par un script d'auteur : sa valeur est dérivée du journal.
- Les variables mutables numériques, d'inventaire, de portée scène/campagne et leurs écritures transactionnelles sont **hors périmètre** : elles nécessitent un contrat de persistance GameSession et de replay distinct, jamais un simple dictionnaire éditorial.
- Le nœud \`flag\` est une dépendance conjonctive persistante (« déjà déclenché »), **pas** une branche conditionnelle instantanée. Une référence à un événement qui n'arrive jamais bloque sa phase au lieu de choisir un autre chemin.

### 3. Éditeur et migration

Dans **Outils → Game Logic Studio R31…**, sélectionner un nœud d'action de graphe v1/v3 et cliquer **+ Attendre** ou **+ Drapeau**. Le Studio insère automatiquement le nœud de contrôle après l'action. Si l'action était terminale, un message d'après-contrôle est ajouté pour préserver un graphe valide. Modifier la durée ou l'ID via **Propriétés…**. Cliquer **Vérifier** avant **Appliquer**.

Le graphe est persisté dans le même \`GameProject.extensions["org.drawtemp.logic"]\`. Le passage de v1→v3 remplace les triggers du même graphe **atomiquement**, avec \`AuthoringSession.preview_pair/apply\`, Undo/Redo et protection contre les changements R9 externes. Les graphes v1 et v2 restent lisibles et compilés par leurs chemins historiques.

Le débogueur R31.D projette désormais les nœuds \`wait/flag\` sur la phase R9 suivante, en affichant \`waiting\`, \`scheduled\`, \`ready\` ou \`fired\` selon \`temporal_status\`. Son contrôle **Pas événement** exécute un événement actuellement prêt ; il **ne fait pas avancer les ticks** du Battle jetable. Le contrôle temporel précis (avance par ticks avec input journalisé) relève d'un lot ultérieur.

### 4. Persistance/replay

Les preuves unitaires R31.E vérifient la séquence native, le statut différé, le déclenchement après des **commandes Battle authentiques** et l'égalité des empreintes SHA au moyen de \`Battle.recording()\` / \`Battle.replay()\`, ainsi que le save/reopen des deux documents auteurs. Ce sont des tests automatisés, **pas** une certification de reprise GameSession multisystème tant que l'ensemble des jobs CI et les scénarios de Player installés ne sont pas verts.

Exécuter :

    python -m unittest tests_standalone.test_drawtemp_r31_logic_sequence -v
    QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r31_logic_qt.VisualLogicQtTests -v

Le workflow \`.github/workflows/r31-visual-graph.yml\` inclut les gates R1/R9/R31.A–E sur Ubuntu, Windows et macOS.

## Fichiers

- \`drawtemp/sdk/logic_sequence.py\` : validation stricte, compilation R9 multi-étapes et budget.
- \`drawtemp/sdk/logic_graph.py\` : dispatcher compilateur et schema v3 explicite.
- \`drawtemp/studio/logic_graph_draft.py\` : commandes de création/édition atomiques en brouillon.
- \`drawtemp/studio/logic_graph_qt.py\` : boutons typés et diagnostic des phases.
- \`drawtemp/studio/logic_debugger.py\` : correspondance nœud↔état natif.
- \`tests_standalone/test_drawtemp_r31_logic_sequence.py\` : couverture headless, preview, rollback, replay et fail-closed.
- \`tests_standalone/test_drawtemp_r31_logic_qt.py\` : couverture Qt offscreen.

## Reste à faire avant le gate R31

R31.10 variables mutables de portées local/scène/campagne et sérialisation réelle ; conditions sur l'inventaire et les quêtes ; support d'attentes conditionnelles et annulation ; exécution par tick en debug ; E2E sans JSON « PNJ → porte → combat → coffre → quête » ; tests de reprise GameSession et Player et certification de release. **R31 reste NO-GO.**
