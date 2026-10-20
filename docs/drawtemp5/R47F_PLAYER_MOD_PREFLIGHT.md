# R47.F — Projet moddé : préflight de lancement (opt-in, sans runtime tiers)

## Objectif

Ne jamais confondre un GameProject valide et un jeu moddé dont les ressources ou
descripteurs sont encore disponibles et approuvés par l'hôte. Le Player DrawTemp
continue de lire les extensions inconnues **comme des données inertes** ; il
n'exécute pas d'extensions Python, QML ou de code injecté.

Le contrôle R47.F est **optionnel**, mais **strict** lorsqu'un hôte l'active :
une erreur de pin, de dépendance, de namespace ou de pack interdit la création
du contrôleur Player. Les formats `Content`, `GameProject` et les sauvegardes
`GameSession` ne changent pas.

## Flux de l'hôte (sans état implicite)

1. Charger manuellement des manifests via `read_mod_manifest` puis
   `ModRegistry.install` avec des ZIP R30 sélectionnés par l'hôte.
2. Obtenir `expected_pins` **d'un inventaire indépendant et fiable** (clé ID
   mod → digest SHA-256 du manifeste). Il ne faut pas considérer une liste
   provenant du GameProject, du mod ou de son ZIP comme autorité de confiance.
3. Passer `managed_namespaces` : les namespaces déclaratifs dont l'hôte est
   responsable, y compris ceux dont le mod est potentiellement absent.
   Les namespaces internes DrawTemp (par exemple l'extension Asterion) ne
   doivent pas être assimilés sans preuve à des mods R47.
4. Appeler `inspect_modded_project(content_path, registry,
   expected_pins=pins, managed_namespaces=scope)` pour une revue sans effet.
5. Si et seulement si `ready_for_player_preview` est vrai, un hôte Qt peut
   demander `drawtemp.player.qt_app.build_controller(..., mod_registry=registry,
   expected_mod_pins=pins, managed_mod_namespaces=scope)`.

## API exemple

~~~python
from drawtemp.sdk.mod_preflight import inspect_modded_project
from drawtemp.player.qt_app import build_controller

# registry / approved_pins / declared_mod_namespaces sont fournis par le host.
result = inspect_modded_project(
    "my-game/game.json", registry,
    expected_pins=approved_pins,
    managed_namespaces=declared_mod_namespaces,
)
if not result["ready_for_player_preview"]:
    raise RuntimeError("; ".join(result["errors"]))

controller = build_controller(
    content_path="my-game/game.json",
    save_dir="my-game/saves",
    mod_registry=registry,
    expected_mod_pins=approved_pins,
    managed_mod_namespaces=declared_mod_namespaces,
)
~~~

Le `build_controller` historique **n'exige aucun registre** pour un projet
standard ; un hôte qui fournit le registre sans les pins (ou inversement)
obtient un refus immédiat. Un chemin GameProject personnalisé hors du couple
canonique est refusé lorsque le préflight de mods est demandé, pour éviter
d'inspecter un fichier et d'en charger un autre.

## Contrôles techniques

- Validation du couple canonique via `validate_pair` et `preflight` R15,
  incluant les ressources et validations de scripts autorisés existantes.
- Relecture des archives R30 épinglées, SHA-256, dépendances transitives et
  enveloppes déclaratives. `audit_project` refuse un mod installé mais non
  épinglé quand sa contribution existe réellement dans le GameProject.
- `managed_namespaces` signale `orphan_namespace` si une donnée de module
  sous la responsabilité de l'hôte n'est reliée à aucun manifeste approuvé.
  Un descripteur read-only qui prétend posséder des données de projet est
  refusé (`unexpected_namespace`).
- Lecture JSON des deux documents avec détection de doublons de clés et
  plafond de 32 MiB par document pour ce préflight ; interdiction des
  symlinks directs. Comparaison des empreintes SHA-256 des documents avant
  et après le scan R15 pour signaler une sauvegarde concurrente ordinaire.
- Aucun asset, manifeste, document, mod ou sauvegarde n'est modifié par le
  préflight.

Ce contrôle **ne fournit pas un snapshot atomique du système de fichiers** :
un éditeur concurrent ou adversarial peut modifier les fichiers immédiatement
après l'audit. Les droits de redistribution, la provenance, les signatures,
les tests onscreen/GPU et l'export natif Player demandent toujours des preuves
indépendantes. Le rapport retourne toujours
`rights_verified: false`, `native_player_verified: false` et
`release_certified: false`.

## Tests et preuves

- `tests_standalone/test_drawtemp_r47f_project_preflight.py` : templates
  Tactical et Asterion ; pins, orphelins, modules non épinglés, mod
  read-only avec payload forgé, archive altérée, JSON malformé, sauvegarde
  concurrente et non-mutation des fichiers.
- `tests_standalone/test_drawtemp_r47f_player_optin.py` : construction du
  vrai contrôleur Player pour les deux jeux, refus de pack altéré et des
  configurations d'hôte incomplètes. Exécution Qt nécessaire, **pas un test
  de rendu à l'écran**.
- CI : R47.C Linux/Windows/macOS headless ; R47.B Linux/Windows/macOS Qt
  offscreen, toutes deux encore soumises au problème GitHub Actions sans
  jobs observé sur la PR #384.

**Gate R47 : NO-GO** jusqu'aux trois matrices de tests réellement exécutées,
au Player autonome natif sur machine propre, aux droits d'assets approuvés et
à la revue de sécurité.
