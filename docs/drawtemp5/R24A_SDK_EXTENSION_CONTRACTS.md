# ADR R24.A — SDK semver & namespaces GameProject v1

**Statut : implémentation en PR, non certifiée en release.** La roadmap 6.0 pose les contrats de plateforme ; R25 introduira plus tard les profils de jeu et le runtime multi-genres. Cette décision couvre R24.1 et la première tranche de R24.3, pas l'ensemble de R24.

## Décision

- Le SDK de simulation reste en version API **1.0 provisoire**, distincte de Content v1, GameProject v1 et GameSession v1. **Aucune migration de sauvegarde** n'est déclenchée ici.
- Une capacité est identifiée par un nom versionné (`sdk-negotiation.v1`, `project-extensions.v1`, etc.). Un client appelle `negotiate_sdk([major, minor], required_features=[...])`. Une version majeure différente, mineure future ou capacité inconnue est refusée par une erreur avec code stable.
- Les extensions sont des **données déclaratives au sein de GameProject v1** ; aucune base annexe, script Python importé, nouvelle source de vérité ou exécution lors de la lecture. Le modèle canonique est validé avant enregistrement/export par les flux existants.
- Un projet historique sans extension garde son dictionnaire sérialisé inchangé ; `extensions` est omis quand il est vide. Une extension non vide entre dans le digest du projet de sauvegarde, pour refuser une restauration avec contenu incompatible plutôt que de faire un fallback silencieux.
- Un consommateur ignore l'interprétation métier des namespaces inconnus, **mais conserve leurs données à l'identique**. Les enveloppes de version future sont refusées ; seules les données structurellement valides peuvent être ouvertes.

## Contrat de données

Un namespace est une clé en minuscules de forme reverse-domain, par exemple `org.example.quest`. Chaque enveloppe contient exactement `schema_version: 1`, `data: { ... }` et éventuellement `references: [{kind, id}]`.

```json
{
  "extensions": {
    "org.example.quest": {
      "schema_version": 1,
      "data": {"chapter": 3, "tags": ["forest", "castle"]},
      "references": [{"kind": "campaign", "id": "main"}]
    }
  }
}
```

Validation obligatoire : maximum 32 namespaces, 64 KiB par extension, 256 KiB au total, profondeur JSON bornée, nombres finis, chaînes/valeurs JSON pures, champs de l'enveloppe fermés, références explicites existantes (`mission` / `campaign`) sans doublon. Une référence non déclarée dans `references` n'est **pas** vérifiée automatiquement : les auteurs doivent déclarer les liens métier concernés.

Les autres familles d'objets (assets, compétences, événements, etc.) nécessitent un contrat de référence spécifique avant de pouvoir être déclarées comme telles. Aucun chemin de fichier ou hook executable n'est accepté par le schéma des références.

## Exemple d'usage SDK

```python
from drawtemp.sdk import capabilities, negotiate_sdk, AuthoringSession

negotiate_sdk([1, 0], required_features=["project-extensions.v1"])
# Procéder avec le Content et le GameProject canoniques déjà chargés
session = AuthoringSession.new(content, project)

def add_quest(manifest):
    manifest.setdefault("extensions", {})["org.example.quest"] = {
        "schema_version": 1, "data": {"chapter": 1},
        "references": [{"kind": "campaign", "id": "main"}],
    }
    return manifest

plan = session.preview_project(add_quest, kind="r24-extension")
session.apply(plan)   # même historique transactionnel, Undo/Redo et sauvegarde
```

**Migration :** modifier une extension v1 passe par `AuthoringSession.preview_project` + `apply` après validation. Une évolution v1→v2 des données d'extension nécessite une migration explicite, réversible et testée dans un lot ultérieur. Charger directement v2 échoue `unsupported_schema`; aucune transformation implicite ou perte de champs.

## Sécurité et compatibilité

- Le validateur canonique est dans `sporebound.project_extensions`, appelé par `GameProject.validate`. Le SDK `drawtemp.sdk` réexporte le contrat en import paresseux ; les tests interdisent les imports Qt/Tk.
- Les références vérifient des IDs du Content/GameProject actuellement ouverts ; changer les IDs sans mettre à jour les références bloque la validation. La session transactionnelle rejette les edits invalides sans modifier le document.
- L'ancien manifeste de plugin R15 (`drawtemp.export.extensions`) continue de décrire des capacités **sans exécuter le code**. La gestion de permissions, les points d'extension UI et l'isolation runtime relèvent de R24.2 et ne sont pas attestés par cette PR.
- Ce lot ne fournit **ni** jeu témoin R24.9, **ni** certification R24.12, **ni** runtime action/R25, **ni** preuve GPU, publication finale ou test sur machine propre.

## Validation

Commande : `python -m unittest tests_standalone.test_drawtemp5_r24a tests_standalone.test_drawtemp5_r1d tests_standalone.test_drawtemp5_r15_creator`.

Critères : négociation positive/négative, roundtrip JSON et fichier, digest historique invariant en absence d'extension, réf valide/invalide, payload hors limites, `preview/apply/undo/redo`, et imports headless. L'exécution en CI ne constitue pas une certification visuelle ou release.

**Suivants :** R24.B plugins Studio déclaratifs contrôlés, R24.C packs/ressources et migrations versionnées, R24.D deuxième projet et gate plateforme ; préalables R17–R23 à revalider sur `master`.
