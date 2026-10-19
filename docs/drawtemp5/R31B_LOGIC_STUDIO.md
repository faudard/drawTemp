# R31.B — Qt Game Logic Studio : graphes visuels R9

**Statut (19 octobre 2026) :** incrément proposé en code dans la branche d'intégration PR #339 ; pas de certification 7.1. À relire et tester sur le SHA final de la PR, puis sur master après intégration.

## Accès et usage dans DrawTemp Studio

Depuis le Studio Qt : **Outils → Game Logic Studio R31…**, ou via la palette globale de commandes (Ctrl+Shift+P).

1. Choisir une mission existante puis **Nouveau**. Saisir un ID de graphe unique, ASCII minuscule. Le graphe provisoire contient un déclencheur de tick et un message R9 déjà liés.
2. Cliquer un nœud pour afficher son inspection et utiliser **Propriétés…** pour modifier le tick, ID d'objet, texte, acteur ou danger. Les champs sont typés, pas un formulaire JSON.
3. **+ Action** crée un nœud message/danger/despawn ; **Dupliquer** copie une action existante. Le nœud créé est d'abord *non connecté* et reste dans un brouillon local. Sélectionner un prédécesseur, cliquer **Relier**, puis la destination ; **Délier** coupe un lien. Les boucles, ports invalides, sources avec plusieurs sorties et destinations avec plusieurs entrées sont refusés.
4. **Vérifier** compile en **Mission.triggers R9 natif** sur une preview de transaction Content/GameProject : aucun changement persistant ni effet gameplay n'est exécuté par le simple contrôle. Les erreurs de forme, références, budget ou conflit sont affichées dans le volet de diagnostic.
5. **Appliquer** est l'unique chemin d'écriture : R1 AuthoringSession.preview_pair + apply, une seule transaction sur Content et GameProject. **Annuler/Rétablir** utilisent l'historique natif de la même session, pas un document parallèle. Le bouton **Enregistrer le projet** du Studio conserve le même format et mécanisme de récupération atomique qu'avant.
6. La recherche atténue visuellement les autres cartes ; la disposition n'est pas un nouveau champ du modèle métier. Les brouillons incomplets ne sont jamais exportés vers les événements R9. Changer de graphe ou faire Undo quand le brouillon contient des modifications non appliquées demande confirmation.

**Portée réelle :** éditeur de graphes linéaires et ses actions R9 listées, avec connexions par clic. Les groupes, relations de données typées, fonctions imbriquées, conditionnelles, attentes et pas-à-pas seront dans des incréments ultérieurs ; la bibliothèque graphique R31.3 complète reste ouverte. Une connexion « Relier » est de type contrôle next → flow, pas un fil de données arbitraire.

## Architecture / anti-régression

- **drawtemp/studio/logic_graph_draft.py** : tampon non persistant, construction/édition/copie/suppression/connexion/déconnexion ; refuse mutation illégale et protège les révisions. N'importe quel graph incomplet échoue à l'aperçu sans écrire le projet.
- **drawtemp/studio/logic_graph_qt.py** : QDialog et QGraphicsScene, cartes différenciant déclencheur/action, sélection à la souris, connexions représentées par des courbes, recherche, diagnostics, propriété typée, Undo/Redo et signal de rafraîchissement du Studio.
- **drawtemp/studio/qt_shell.py** : nouvelle action globalisée dans menu Outils/palette, partage strictement la session existante.
- **drawtemp/sdk/logic_graph.py (R31.A)** : seule autorité de compilation ; aucun changement du runtime tactique ni du schéma des sauvegardes. Les collisions avec événements R9 modifiés directement sont explicitement bloquées.

## Tests

Pour les contrats headless (sans Qt) :

    python -m unittest tests_standalone.test_drawtemp_r31_logic_graph tests_standalone.test_drawtemp_r31_logic_qt.LogicDraftTests -v

Pour Qt logiciel/offscreen (pas un test matériel) :

    QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r31_logic_qt.VisualLogicQtTests -v

GitHub Actions : **.github/workflows/r31-visual-graph.yml**, jobs headless et Qt sous Python 3.12 sur Ubuntu, Windows et macOS. Les jobs R9 / R1 sont également rejoués. Les états queued/failed d'autres branches ne sont pas une preuve de conformité ; attendre la CI du **SHA de tête final**.

## Prochain incrément

R31.C : branchements conditionnels / port de données typé, expressions pures et attente de ticks avec budget déterministe via les règles déjà existantes. R31.D : debugger à points d'arrêt avec instrumentation causale sur vrai Battle/GameSession ; ensuite scénarios complets PNJ → porte → combat → coffre → quête Studio→Player, y compris tests UI/inputs réels et replay.

**Non couvert / NO-GO :** R31.5 runtime visuel général, R31.7 branche/attente/annulation, R31.8 pas-à-pas, R31.9 sous-graphes, R31.11 galerie robuste, R31.12 scénario complet sans JSON. La certification 7.1 demeure refusée jusqu'aux gates de la roadmap.