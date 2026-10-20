# R31.F — Variables tactiques typées et reproductibles

**Statut :** incrément proposé dans la PR de consolidation R31.E/F issue de \`master\` après la fusion de #339. Les tests GitHub Actions ne sont **pas certifiés** tant que les jobs et leurs logs ne sont pas disponibles.

## Ce qui est livré

### Variables de portée Battle

Une variable tactique possède un identifiant \`r31_…\` (ASCII borné) et une valeur **booléenne** ou **entière signée** dans l'intervalle [-1 000 000, 1 000 000]. Elle peut être manipulée via trois opérations **typées** :

- **Affecter** (\`logic_set\`) : assignation booléenne ou entière.
- **Ajouter** (\`logic_add\`) : incrément entier borné à [-10 000, 10 000], non nul. Le type booléen ne peut pas être incrémenté.
- **Tester** (\`logic_compare\`) : égalité/inégalité pour booléens et entiers, \`gte/lte\` exclusivement pour entiers. Une variable absente ne satisfait **aucun** test.

Les écritures ont lieu uniquement pendant les **actions R9 natives**, au moyen de \`battle.emit("logic_variable", name=…, value=…)\`. La fonction \`variables_from_journal(battle)\` reconstruit la valeur courante à partir de \`Battle.events\`; il n'existe **aucun état mutable indépendant** des commandes rejouables. Les journaux sont bornés à 4 096 écritures de variable et 32 noms distincts.

L'exécution de l'action, les conditions et les erreurs utilisent des règles explicitement enregistrées dans \`RuleSet.trigger_actions\` / \`RuleSet.trigger_conditions\`. Les nouveaux descripteurs sont **opt-in** : \`authored_rules_for_document\` active le module uniquement si une mission utilise au moins une de ces règles. Cela préserve les manifests legacy (replay version 1/2/3) lorsqu'aucune variable R31.F n'est utilisée.

### Auteur / Studio Qt

Les graphes linéaires acceptent maintenant un **schéma v4** :

- \`+ Variable\` : insère une action d'affectation ou d'addition après l'action sélectionnée.
- \`+ Tester var\` : insère un contrôle typé après l'action sélectionnée, avec une action de continuation. Le prochain événement R9 reçoit \`when: {"condition":"logic_compare",…}\` et \`after: ["r31_…_sN"]\`.
- \`Propriétés…\` modifie les valeurs sans interprétation de script et sans édition de JSON.
- Les contrôles R31.E **Attendre** et **Drapeau** restent utilisables sur les graphes v4.
- Les mutations sont validées en brouillon et les paires Content + GameProject sont appliquées **atomiquement** par \`AuthoringSession.preview_pair/apply\`.

Le débogueur R31.D expose une copie des \`battle_variables\` et leur \`variable_scope="battle"\`; ses inspections portent sur le même dispatcher R9. Le graphe sauvegardé ne peut pas être débogué si les événements natifs ont changé en dehors de Logic Studio.

### Persistance réelle

Les écritures de variable se retrouvent dans le journal de \`Battle.recording()\` et sont reconstruites pendant \`Battle.replay()\`, avec vérification du digest. \`GameSession.recording()\` embarque le Battle et le manifeste des règles opt-in. \`GameSession.from_recording()\` reconstitue les journaux du même combat : il ne crée pas de deuxième magasin de variables ni de nouveau format de sauvegarde.

Les tests R31.F couvrent les valeurs booléennes/entières, l'ordre set→add→compare, les conditions fausses, les types invalides, les bornes, les manifests legacy, l'inspection du débogueur et le rechargement de GameSession.

## Contraintes explicites

Les variables R31.F sont **locales à un Battle**. Elles ne modifient **jamais implicitement** \`Campaign.story_flags\`, les sauvegardes de progression, les quêtes ou l'inventaire. Les données de campagne sont déjà gérées par StoryBook / Campaign Flow et réclament un **pont de transition explicitement autorisé et rejoué** pour éviter une duplication ou une fuite d'état d'un combat vers le monde.

Une comparaison bloque une phase jusqu'à devenir vraie ; elle ne constitue pas une nouvelle branche \`Si/Sinon\`. La combinaison du schéma v2 (IF/ELSE) avec les opérations v4 dans **le même graphe** reste à développer. Il n'y a pas de boucle, de timer QML ou d'exécution de code Python auteur.

## Tests et gates

\`\`\`bash
python -m unittest tests_standalone.test_drawtemp_r31_logic_variables -v
python -m unittest tests_standalone.test_drawtemp_r31_logic_sequence -v
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r31_logic_qt.VisualLogicQtTests -v
\`\`\`

CI : \`.github/workflows/r31-visual-graph.yml\` cible Ubuntu/Windows/macOS, Python 3.12 et PySide6 offscreen.

**Gate R31 complet : NO-GO** avant tous les jobs verts, la revue des valeurs à la frontière campagne/mission et le vertical slice sans JSON « PNJ → porte → combat → coffre → quête ».
