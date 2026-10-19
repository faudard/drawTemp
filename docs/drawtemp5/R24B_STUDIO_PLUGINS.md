# R24.B — Plugins Studio déclaratifs et contrôlés

**État : implémentation en PR empilée sur R24.A (#296), sans certification de release.**

## Objectif

Étendre le Studio Qt avec des contributions de tiers strictement **non exécutables** : panneaux natifs de lecture seule et modèles de données propres à un namespace GameProject. Le Core, le SDK, les sauvegardes et l'historique AuthoringSession demeurent canoniques.

## Contrat v2

Le manifeste R24.B est un JSON dont la version `api_version` vaut 2 ; il n'altère pas le validateur R15 de manifests v1. Un ancien manifeste n'acquiert donc jamais de droits d'écriture implicitement. Exemple utilisable : [quest-helper.json](../../examples/plugins/quest-helper.json).

Les champs obligatoires sont : `api_version`, `id`, `name`, `namespace`, `sdk_api`, `required_sdk_features`, `capabilities`, `permissions`, `contributions`. `namespace` est une chaîne reverse-domain unique dans l'instance Studio, compatible avec GameProject.extensions (R24.A). La négociation SDK refuse une version majeure/mineure inconnue.

Les capacités prises en charge sont `property-panel` et `project-template`. Un panneau contient `id`, `title`, `description` et la liste blanche `fields` (title/subtitle/count campagnes/missions). Un modèle contient `id`, `label`, `data` JSON et `references` vers des missions/campagnes validées lors de l'application.

Les permissions sont exactement `project.read` (panneaux) et `project.extensions.write` (modèles). Elles doivent correspondre aux contributions réelles : ni accès filesystem, ni réseau, ni commandes Python, ni injection de widgets. Les IDs de plugin et namespaces sont uniques ; un maximum de 12 panneaux et 12 modèles par plugin est accepté, avec manifeste de 64 Kio au plus.

## Utilisation

Dans DrawTemp Studio Qt → Outils → Plugins Studio → Charger un manifeste…, sélectionner `examples/plugins/quest-helper.json`. Un dialogue demande explicitement l'autorisation des permissions déclarées, avec refus par défaut. Après acceptation, le Studio affiche un dock Qt natif avec des données de projet en lecture seule et un bouton **Initialiser les quêtes**.

Ce bouton déclenche une prévisualisation R1 via AuthoringSession puis un apply atomique : les données sont stockées sous `GameProject.extensions.org.example.quest`. L'opération peut être annulée/rétablie. Elle ne remplace jamais un namespace déjà présent, et une référence invalide rejette l'opération avant mutation.

Dans le même menu, Désactiver un plugin… révoque ses permissions et enlève son dock. Ni le manifeste ni son consentement ne sont rechargés automatiquement à l'ouverture suivante. Une exception inattendue lors du rendu du panneau désactive le seul plugin concerné, qui est mis en quarantaine ; le Studio continue avec les autres plugins.

## Sécurité, validation et limites

Le registre `drawtemp.studio.plugins` ne fait aucun import de code depuis le manifeste. Il expose des données et autorise des actions natives fixes du Studio seulement. Il ne fournit PAS de sandbox d'exécution OS pour des plugins Python non fiables, et n'autorise pas leur exécution.

Le chargement est manuel depuis un fichier JSON régulier (symlinks et JSON avec propriétés répétées refusés). Le modèle de confiance pour des fichiers locaux modifiés concurremment, les signatures de packs, l'analyse des assets, l'export sous licence, les scripts tiers et l'isolation par processus restent hors de R24.B.

Les propriétés de panneau sont résolues à partir de l'instantané détaché de la session. Les références du modèle passent par le validateur GameProject v1 et la prévisualisation atomique. Aucun nouveau schéma de sauvegarde et aucun second éditeur de données n'est créé.

Tests : `python -m unittest tests_standalone.test_drawtemp5_r24b tests_standalone.test_drawtemp5_r24a tests_standalone.test_drawtemp5_r15_creator`.

Qt optionnel : `python -m unittest tests_standalone.test_drawtemp5_r24b.QtPluginDockTests` avec PySide6 6.8.3 et QT_QPA_PLATFORM=offscreen. Les tests Qt offscreen ne sont ni une preuve UX onscreen ni une certification GPU.

**Suite :** R24.C packs de ressources vérifiés et migrations ; R24.D second jeu + gate 6.0 ; R25 modes de jeu ; les gates R17–R23 restent indépendants.
