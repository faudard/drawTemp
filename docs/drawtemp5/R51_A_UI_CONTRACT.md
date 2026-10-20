# R51.A — UI & HUD Designer: contrat déclaratif (incrément P0)

**État : implémentation proposée en PR, pas de certification R51 ou 10.0.**
Dépendance générale : R18/R28/R38/R41–R50 ; le gate R50 demeure **NO-GO**
tant que les preuves physiques/tri-OS/UX/Player ne sont pas disponibles.

## Frontières

- **Source unique** : \`GameProject.extensions["org.drawtemp.ui"]\` (enveloppe R24
  \`schema_version: 1\` et données \`version: 1\`). Aucun sidecar de HUD,
  aucun champ ajouté à \`GameSession\`, \`Campaign\` ou \`Content\`.
- **Affichage uniquement** : \`sporebound.ui_layout_r51.project_layout()\`
  accepte une \`GameSession\` canonique et, si requis, un \`BattleFrame\`
  canonique. Aucune lecture par introspection et aucune action de combat.
- **Édition transactionnelle** : \`LayoutAuthoring\` passe par
  \`AuthoringSession.preview_project/apply\`, donc vérification des références,
  révisions obsolètes, Undo/Redo et modifications atomiques.
- **Inertie stricte** : boutons = intentions de commande en liste blanche,
  jamais du Python/QML/JS, et ne sont pas exécutés par R51.A. Le routage
  d'input utilisateur réel fait partie de R51.B.
- **Compatibilité** : un projet sans extension n'est pas modifié, y compris
  pendant lecture/round-trip; ses enregistrements tactiques restent tels quels.
  Le manifest opt-in entre dans l'empreinte de projet existante afin de ne pas
  charger silencieusement une sauvegarde avec un HUD modifié.

## Structure de données v1

\`\`\`json
{
  "schema_version": 1,
  "data": {
    "version": 1,
    "layouts": {
      "combat": {
        "kind": "HUD_CT",
        "root": {
          "id": "panel", "type": "column",
          "children": [
            {"id": "focus", "type": "text",
             "binding": {"path": "combat.focus", "type": "str"}},
            {"id": "end_turn", "type": "button",
             "text": "Fin du tour", "action": "combat.end_turn"}
          ]
        },
        "breakpoints": [
          {"min_width": 0, "columns": 1},
          {"min_width": 900, "columns": 2}
        ],
        "focus_order": ["end_turn"]
      }
    }
  }
}
\`\`\`

L'objet ci-dessus est la valeur du namespace
\`GameProject.extensions["org.drawtemp.ui"]\`, **pas un projet complet**.

Widgets acceptés : \`row\`, \`column\` (conteneurs), \`text\`,
\`gauge\` (deux bindings numériques), \`button\` (libellé + intention).
Chaque écran possède au maximum 64 widgets, profondeur 8, 8 breakpoints,
12 écrans par projet ; largeur entière valide de 1 à 16 384 unités logiques.
Les breakpoints sont ordonnés et commencent à zéro. \`focus_order\` doit
couvrir exactement les boutons, une fois chacun; un écran \`MENU\` ne peut
pas être vide d'actions.

Bindings en lecture seule et typés : \`session.campaign_id\`,
\`session.scene_id\`, \`session.seed\`, \`combat.title\`,
\`combat.objective\`, \`combat.phase\`, \`combat.focus\`,
\`combat.selection\`, \`combat.active_hp\`, \`combat.active_max_hp\`.
Les champs \`combat.*\` absents du contexte ne deviennent **pas** des zéros
inventés : la projection est refusée. Aucun chemin personnalisé ne traverse
des attributs d'objet. Les données gameplay restent celles de GameSession et
BattleFrame.

## Migration, sécurité, limitations

- Aucun historique antérieur de schéma HUD R51 n'est défini : la version 1
  est la première, et toute version future/inconnue est refusée. Une future
  migration devra fournir une transaction explicite et une preuve sans perte.
- Le chargeur canonique valide l'extension présente ; payload malformé,
  type faux, identifiant dupliqué, lien inexistant, focus incomplet, composant
  ou action inconnu => refus. Les limites de taille des extensions R24
  s'appliquent également.
- Aucun moteur de rendu Qt, WYSIWYG, manette ou action exécutable n'est livré
  ici. Les éléments \`columns\`/focus sont des **données de présentation**,
  pas des preuves d'accessibilité ou de rendu responsive réel.
- Les textes sont des chaînes de données ; R51.B devra les échapper dans
  le renderer et ne jamais les interpréter comme QML/HTML/JS.
- La présence de la PR ne certifie ni R50 ni le gate R51.

## Validation ciblée

\`\`\`sh
python -m unittest -v tests_standalone.test_r51a_ui_layout
python -m unittest -v tests_standalone.test_r25_foundation tests_standalone.test_player_hud_layout_r710
\`\`\`

Couvert : round-trip \`GameProject\`, compatibilité des projets v1 historiques,
enregistrement/replay \`GameSession\`, bindings et breakpoints, erreurs
fail-closed, absence de mutation du combat, transactions, suppression,
Undo/Redo, preview périmée.

## Suite — sous-lots restants

**R51.B (P0)** : adaptateur de projection partagé Studio/Player Qt, éditeur
WYSIWYG des arbres et des contraintes, rendu réel en HUD CT/action/menus,
textes accessibles, navigation clavier/manette, preview/apply/Undo/Redo.

**R51.C (P0)** : goldens Studio↔Player et DPI, thèmes HC, focus/lecteurs
d'écran, refus d'export de ressources non autorisées, Player indépendant
sur les trois OS, preuves humaines et matérielles de gate.
