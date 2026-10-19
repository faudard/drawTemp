# R30.A — Creator Ecosystem : contrats de fondation

**Statut : code proposé, non certifié 7.0.** Référence :
[DRAWTEMP_MULTI_GENRE_CREATOR_ROADMAP.md](../DRAWTEMP_MULTI_GENRE_CREATOR_ROADMAP.md).
R30 est dépendant de R24–R29 et ne peut être déclaré complet par ce lot.

## Ce qui est effectivement implémenté

| Lot | Implémenté dans cette PR | Restant |
| --- | --- | --- |
| R30.1 | Négociation de version/capacités du SDK provisoire | Politique officielle de dépréciation et semver stable |
| R30.2 | Format pack ZIP inert, construction et inspection SHA-256 | Import atelier, signature/autorisation des licences, export final |
| R30.4 | Diff par identifiant de mission, preview trois voies, session Undo | Interface de résolution visuelle |
| R30.3/.5/.6/.7/.8/.9 | Non | Plugins sandboxés, collaboration Git, perfs, génération, galerie et docs complètes |
| R30.10 | Bloqué | Second jeu complet autonome, tests humains, GPU, licences et release |

Aucun second moteur, format Content/GameProject, état tactique, renderer ni
mécanisme d'exécution de plugin n'est ajouté.

## R30.1 — Contrat SDK

Le module drawtemp.sdk.capability_contracts expose les fonctions parse_semver,
negotiate_sdk et require_sdk. Elles comparent une version minimale incluse et
maximale exclue (ex. 1.0.0 à 2.0.0) à la version déjà annoncée par le SDK R1,
et vérifient les capacités réellement publiées dans SDK_FEATURES.

Tout mode R25–R29 non implémenté reste indisponible. Erreurs explicites
CapabilityError.code, aucun chargement de code tiers. Le statut API demeure
provisional et aucun engagement d'ABI 7.0 n'est prétendu.

## R30.2 — Packs sûrs et vérifiables

Un pack est un ZIP constitué d'un manifest.json et des ressources nommées
exactement dans ce document. Format JSON d'exemple :

    {
      "schema": 1,
      "id": "original-terrain",
      "version": "1.0.0",
      "kind": "terrain",
      "requires": {
        "min_api": "1.0.0",
        "max_api": "2.0.0",
        "features": ["authoring.v1"]
      },
      "files": [{
        "path": "terrain/grass.png",
        "size": 1024,
        "sha256": "<empreinte réelle de 64 caractères hexadécimaux>",
        "license": "CC0-1.0",
        "origin": "Auteur original / source de production"
      }]
    }

Remplacer l'exemple de taille et d'empreinte par des valeurs physiques avant
de construire. Appels :

    python -m drawtemp.export.creator_pack_cli build --source mes-ressources --manifest pack.json --output terrain.zip
    python -m drawtemp.export.creator_pack_cli inspect terrain.zip

Le constructeur ne remplace jamais un fichier ZIP existant. L'inspection est
strictement passive : aucune extraction, aucun import, aucune exécution.
Contrôles : path confinement, symlink/chiffrement ZIP refusés, doublons et
collisions insensibles à la casse, hash SHA-256 et taille par fichier,
provenance et licence déclarées pour chaque ressource, format inert seulement.
Limites initiales : 256 ressources, 16 MiB par fichier et 64 MiB décompressés.

IMPORTANT : licences et origines dans le manifeste sont des déclarations,
non une preuve juridique. Le rapport de vérification garde
rights_verified = false. Le gate INT-03/R15 sur droits de modification et
redistribution reste ouvert. Un format de pack accepté ne vaut jamais
autorisation de publication.

## R30.4 — Diff et fusion transactionnelle

    from drawtemp.sdk.semantic_review import preview_merge, stage_merge

    review = preview_merge(
        base_content, base_project,
        local_content, local_project,
        incoming_content, incoming_project,
    )
    for conflict in review.conflicts:
        print(conflict.to_dict())

    if review.can_apply:
        plan = stage_merge(authoring_session, review,
                           expected_revision=authoring_session.revision)
        # Seulement après confirmation explicite du créateur :
        authoring_session.apply(plan)

Le diff est ordonné par chemin et référence les missions par leur identifiant.
Les listes d'actions, d'événements, d'unités et de choix restent atomiques :
les altérations concurrentes provoquent un conflit. Une permutation simultanée
de missions n'est pas fusionnée automatiquement. Aucun changement implicite
dans les données n'a lieu lors du preview ou du stage.

stage_merge vérifie la révision et le fingerprint local, puis réutilise
AuthoringSession.preview_pair. apply produit exactement une transaction
Undo/Redo après validation canonique Content + GameProject. Une UI de
résolution de conflits et la collaboration Git restent à développer.

## Tests et release gate

    python -m unittest tests_standalone.test_drawtemp_r30_creator -v

Workflow dédié Linux/Windows/macOS Python 3.12, avec tests historiques
authoring/SDK. Contrôler les résultats au SHA final. Aucun gate GPU,
certification de licence ou validation humaine n'est affirmé par cette PR.

Rollback : les nouvelles fonctions sont opt-in, n'écrivent aucune migration
dans les projets existants et n'altèrent pas les saves/replays Jeanne. Retirer
ces modules et le workflow n'affecte ni le Core ni les fichiers utilisateurs.

## Suite à livrer

R30.B : import contrôlé des packs dans Asset Registry et AuthoringSession,
plus provenance opposable. R30.C : interface de diff/merge et erreurs visibles.
R30.D : galerie de projets complets et certification du deuxième jeu multi-
genre (seulement après les gates R25–R29).
