# R30.C — Revue Qt des packs et des fusions sémantiques

**Statut : code proposé en PR draft, empilée sur R30.B (#329), puis R30.A
(#305).** Ce lot n'est ni une release DrawTemp 7.0 ni une certification GPU,
de droits d'assets ou de jouabilité inter-genres.

## Studio Qt, session unique et commandes réelles

L'action **Outils → Packs et revue des conflits** ouvre une fenêtre modale
Qt Widgets depuis le Studio R2. Elle reçoit la même AuthoringSession que les
autres ateliers ; il n'y a aucun deuxième propriétaire Content/GameProject.
Les contrôleurs de validation et de transaction sont headless, indépendants
de Qt, et ne chargent jamais le code d'un plugin.

### Onglet Packs

1. Ouvrir un ZIP ; vérifier son contenu via le format strict R30.A/B :
   hash SHA-256, tailles, chemins, compatibilité SDK, provenance et licence
   déclarées.
2. Les ressources sont désélectionnées par défaut. Les PNG proposent les
   types sprite/portrait ; WAV/OGG proposent sound. Les autres entrées restent
   non sélectionnables.
3. Définir un nom local et **Prévisualiser**. Le candidate GameProject.assets
   est validé par les modèles canoniques ; aucune écriture n'a encore lieu.
4. Modifier la sélection invalide immédiatement la preview.
5. Confirmer la création d'une **nouvelle copie** : R30.B revérifie les
   octets et publie un répertoire inexistant après staging/preflight.
   Aucun remplacement des fichiers originaux.

Les licences des nouveaux assets ne sont jamais approuvées
automatiquement : rights_verified reste false. Attention : la copie provient
des documents enregistrés sur disque ; il faut enregistrer les changements
locaux avant de lancer l'import si on souhaite les retrouver dans la copie.

### Onglet Diff / Conflits

1. Ouvrir deux paires Content/GameProject : base commune et entrant.
   Le local est la session Studio active (même si elle est dirty).
2. Comparer les changements et afficher les conflits par chemin.
3. Résoudre chaque conflit par **Garder local** ou **Prendre entrant**.
   Aucun choix implicite. Les listes ordonnées d'événements/actions,
   unités et campagnes restent atomiques.
4. Le bouton Appliquer est désactivé tant que tous les conflits ne sont
   pas résolus. Une confirmation utilisateur est requise.
5. Avant application, revérifier les hash des deux paires de fichiers et
   la révision du document local ; calculer la résolution et transmettre
   au flux unique AuthoringSession.preview_pair/apply.
6. L'historique Undo/Redo est conservé. Enregistrer sur disque reste une
   opération Studio distincte.

## Utilisation

Depuis le Studio enregistré :

    python -m drawtemp.studio.qt_shell --content chemin/jeu.json

Ou dialogue Qt autonome :

    python -m drawtemp.studio.r30_creator_qt --content chemin/jeu.json

Sans --content, l'import de pack est désactivé ; la comparaison peut
fonctionner sur la session de référence.

## Tests

    python -m unittest tests_standalone.test_drawtemp_r30c_review -v
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m unittest tests_standalone.test_drawtemp_r30c_qt -v
    QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m drawtemp.studio.r30_creator_qt --smoke

Workflow R30.C : headless et Qt offscreen sur Linux, macOS et Windows
(Python 3.12). Inclut les tests de régression R30.A/B et la référence Jeanne.
Les résultats CI doivent être lus sur le SHA final, et aucune simulation
logicielle ne vaut preuve de GPU physique.

## Exclusions et suites

Ne sont PAS livrés : import in-place atomique de ressources + documents,
journal crash-safe multi-asset, marketplace, signature d'auteur, revue
juridique, plugin Python sandboxé, collaboration Git distante, merge par
commandes de gameplay, opérations lourdes en worker annulable, certification
UX et GPU, ou deuxième jeu complet. R30.D devra traiter VCS/collaboration ;
R30.8–.10 restent conditionnés à la fermeture des gates R25–R29.
