# R30.B — Import contrôlé de packs dans le projet canonique

**Statut : code proposé (branche empilée sur la PR #305). Non certifié 7.0.**
Dépendance : R30.A, format de pack inerte ZIP, hash SHA-256 et négociation SDK.

## Objectif

Importer une sélection explicite de sprites PNG, portraits PNG et sons
WAV/OGG dans GameProject.assets, via AssetRegistry et AuthoringSession,
sans second registre, sans scripts/plugins exécutables et sans modification
du projet d'origine.

Ce premier lot ne fait PAS d'import in-place : il publie une nouvelle copie
du projet uniquement après vérification complète. C'est volontaire afin de
ne pas promettre une transaction atomique entre fichiers d'assets et
documents Content/GameProject encore non journalisée dans le projet actif.

## Parcours et garanties

1. Lecture et validation R1 de Content et GameProject, preflight R15 des
   assets existants, empreintes des documents et des ressources.
2. Vérification intégrale ZIP R30.A : chemins, hash SHA-256, tailles,
   doublons, exigences SDK, provenance et licence déclarées.
3. Sélection explicite du créateur (path, kind, name) et construction
   d'identifiants namespacés de type art-pack.grass. Aucun contenu JSON de
   quêtes/puzzles/événements n'est automatiquement exécuté ou fusionné.
4. Refus des collisions d'identifiants/chemins, y compris différences
   majuscules/minuscules, et validation canonique du futur GameProject.assets.
5. La preview est sans effet. Après confirmation, on revalide empreintes,
   sélection, manifestes et source. Les ressources sont copiées dans une
   arborescence temporaire et les deux documents sont créés par
   AuthoringSession.preview_project + apply + save_as.
6. Preflight final R15 sur la COPIE physique et vérification de l'inventaire.
   Publication seulement dans un répertoire destination inexistant.
7. Toute exception avant publication abandonne le dossier temporaire ;
   le jeu source n'est pas modifié.

## API

    from drawtemp.export.pack_import import (
        preview_pack_import, import_pack_to_copy,
    )

    bindings = [{"path": "terrain/grass.png",
                 "kind": "sprite", "name": "grass"}]
    preview = preview_pack_import("jeu/game.json", "terrain.zip", bindings)
    print(preview.to_dict())
    copied = import_pack_to_copy(preview, "jeu-avec-terrain")

CLI, où choices.json contient un tableau de bindings :

    python -m drawtemp.export.pack_import_cli --content jeu/game.json --pack terrain.zip --bindings choices.json
    python -m drawtemp.export.pack_import_cli --content jeu/game.json --pack terrain.zip --bindings choices.json --output jeu-avec-terrain --confirm

Le paramètre --confirm est obligatoire pour une écriture. La destination
doit être un répertoire inexistant, hors de l'arborescence du jeu source.

## Sécurité, droits et limites

- Rejet de pack corrompu/modifié, source changée depuis la preview,
  ressource avec fausse signature, mauvais type ou collisions de chemins/IDs.
- Aucun fichier du projet source réécrit, même en cas de panne de copie ou
  de validation en cours.
- Les attestations de droits existantes peuvent être conservées, mais
  AUCUNE approbation automatique pour les nouveaux assets. Le rapport
  publié maintient rights_verified=false et release_certified=false.
- La copie n'est pas une preuve de redistribution autorisée : revue
  humaine des droits et gate strict R15 / INT-03 requis.
- Les assets de type template, quête, ennemi, puzzle, HUD et autres formats
  devront disposer de contrats de conversion séparés, validés et transactionnels.
- Pas de Git multi-utilisateur, import in-place, marketplace ni code
  d'extension sandboxé, qui relèvent des prochaines tranches R30.

## Tests

    python -m unittest tests_standalone.test_drawtemp_r30_creator tests_standalone.test_drawtemp_r30b_pack_import tests_standalone.test_drawtemp5_r1_authoring -v

Workflow dédié : Python 3.12 Linux/Windows/macOS + replay de référence
Jeanne. Ne pas annoncer les gates CI comme verts avant contrôle du SHA final.

**Suite :** R30.C UI Qt de preview/conflits et intégration transactionnelle
in-place avec journal multi-assets ; R30.D galerie et certification d'un
second jeu seulement après fermeture réelle des dépendances R25–R29.
