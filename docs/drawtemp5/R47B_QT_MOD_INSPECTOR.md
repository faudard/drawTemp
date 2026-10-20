# R47.B — Gestionnaire Qt des mods déclaratifs (prototype fonctionnel)

**Statut : proposition de code dans la PR #384 ; ni test onscreen humain, ni certification R47/8.7.**

## Intégration réelle

Le Studio historique (`drawtemp.studio.qt_shell.StudioWindow`) expose **Outils → Modules / SDK R47 → Inspecter les mods déclaratifs…**. Ce menu instancie un dialogue Qt natif (`drawtemp.studio.r47_mods_qt.ModManagerDialog`) et partage `StudioWindow.session` et le `ModRegistry` R47.A. Le contrôleur ne crée aucun deuxième Content/GameProject, aucun registre de vérité concurrent et ne charge aucun code fourni par le manifeste.

Le gestionnaire permet :
- **Importer** un manifeste JSON R47 (lecture et validation fail-closed). Les packs ZIP requis sont sélectionnés individuellement par l'utilisateur, contrôlés par l'inspecteur R30 et épinglés avec la version et le SHA-256. L'import installe un manifeste **désactivé**.
- **Inspecter** ID, version, namespace, SHA-256 du manifeste, dépendances, packs, permissions demandées/accordées, provenance déclarée et statut des droits. Les droits réels restent **NON validés** malgré la présence de champs de licence.
- **Activer** : afficher le delta des permissions dans un dialogue en texte brut avec **Non** sélectionné par défaut ; aucune permission avant confirmation explicite. Le `ModRegistry.enable` n'accorde que les permissions exactes déclarées.
- **Désactiver** : révoquer immédiatement tous les grants sans modifier les données du projet.
- **Prévisualiser/appliquer** : générer un vrai `AuthoringSession.preview_project` avant de demander confirmation. La validation se fait sur la paire canonique ; `apply_extension` vérifie la révision au moment de l'application. Après commit, Undo/Redo du Studio restent disponibles.
- **Retirer** : demander confirmation, refuser la suppression si un autre mod en dépend ou si le namespace contient des données de projet. Aucun fichier, pack ou document n'est supprimé. La suppression d'un manifeste est une opération en mémoire.

Chaque ouverture du Studio nécessite un nouveau consentement. **Changer de projet** réinitialise complètement le `ModRegistry`, et donc les permissions consenties ; les données du GameProject précédent restent intactes.

## Mesures de sécurité

- Contenu de manifeste et origine : rendu en texte brut, sans HTML ni QML externe ; widgets Qt possédés exclusivement par le Studio.
- Les manifestes sont déclaratifs et non exécutables. Pas de `eval`/`exec`, d'import Python tiers, de subprocess ou de sandbox OS revendiquée.
- Aucune inscription automatique au démarrage, restauration des grants, écriture sur disque pendant l'import, ou persistance silencieuse d'une permission.
- Les packs sélectionnés font l'objet d'une vérification R30 **à l'installation** ; l'intégrité et les licences **à l'export** restent à démontrer en R47.C/R50.
- Un mod invalide, un namespace déjà existant ou des données référencées déclenchent un diagnostic sans écrasement silencieux.
- Une boîte de consentement R47.B ne certifie pas une extension publiée. Un contrôle indépendant des licences, signatures et droits reste obligatoire.

## Tests automatisables

Headless :

~~~bash
python -m unittest tests_standalone.test_drawtemp_r47a_modding -v
~~~

Qt hors écran, seulement si PySide6 est installé :

~~~bash
QT_QPA_PLATFORM=offscreen python -m unittest tests_standalone.test_drawtemp_r47b_qt -v
~~~

Le workflow `.github/workflows/drawtemp-r47b-qt.yml` prévoit Python 3.12 sur Linux, Windows et macOS et relance aussi les tests R47.A. Les tests R47.B couvrent l'inspection, les refus de permissions, la révocation, la preview annulée, l'Undo, le retrait non destructif, les dépendances, l'absence d'exécution et la réinitialisation au changement de projet.

**Gates encore ouverts** : exécution effective des tests sur runners GitHub, essai Qt *onscreen* manuel, accessibilité et DPI, démontstration Studio→Player sur 2 jeux, export sur machine propre Windows/Linux/macOS, signatures/provenance et licences approuvées, perf/CPU si un jour du code tiers est autorisé. **R47.C et gate R47 : NO-GO.**
