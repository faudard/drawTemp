# R38.2 — Prefab variants et mises à jour contrôlées

**Statut : code en PR #377 ; R38 non certifié.** Tranche limitée aux prefabs de groupes R6 v1, sans entité prefab runtime supplémentaire ni moteur parallèle.

## Parcours Studio

Dans **Outils → R38 • Prefabs et variantes héritées…**, charger un prefab de groupes v1 JSON, puis créer une variante avec identifiant stable et propriété héritée du premier groupe. La source est identifiée par SHA-256. Choisir une mission, une position et un identifiant d'instance pour le placement.

Le placement délègue à place_group_prefab : collisions, identité des unités/objets/groupes, structures et coordonnées restent gérés par le Content canonique. Content et provenance GameProject sont enregistrés par la même transaction AuthoringSession, avec Undo/Redo.

Pour changer une variante, utiliser **Prévisualiser la mise à jour**, examiner les anciennes/nouvelles valeurs et les instances concernées, puis **Appliquer la mise à jour**. Une révision périmée ou un champ modifié manuellement bloque la totalité de l'opération.

## API

~~~python
from sporebound.prefab_variants import (
    KIND, prefab_digest, preview_register_variant,
    preview_place_variant, preview_update_variant, preview_override_instance,
)
variant = {
    "kind": KIND, "version": 1, "id": "stone_gate",
    "base_sha256": prefab_digest(source_group_prefab),
    "overrides": [
        {"section": "groups", "id": "group_1",
         "field": "name", "value": "Fortified Gate"},
    ],
}
session.apply(preview_register_variant(session, source_group_prefab, variant))
session.apply(preview_place_variant(
    session, source_group_prefab, "stone_gate", "village", (12, 10), "gate_village"))
~~~

La bibliothèque et ses instances vivent dans GameProject.extensions (namespace org.drawtemp.prefabvariants). Les instances référencent les ID *réels* placés dans Content. Une instance peut recevoir des overrides explicites qui prévalent sur les champs hérités. Les champs en conflit ne sont jamais écrasés.

## Champs et limites

Les modifications typées autorisées, si le champ existe dans la source, sont : groups.name ; units.name/hp/attack/defense ; objects.name/hp/locked/amount. Pas de modification des IDs, coordonnées, liens, hiérarchies ou structures : les mises à jour géométriques restent hors périmètre et nécessiteront un aperçu spatial spécifique.

Taille bornée par l'enveloppe R24 (64 KiB), avec au plus 32 variantes, 128 instances, 32 overrides. À la lecture du projet, vérifier membres réels, références mission et unicité. Aucun chemin de fichier externe n'est ouvert automatiquement : un changement de la source est rejeté jusqu'à migration explicite.

## Tests

~~~sh
python -m unittest tests_standalone.test_drawtemp_r38_prefabs.PrefabVariantTests -v
python -m unittest tests_standalone.test_drawtemp_r38_prefabs.PrefabVariantQtTests -v
python -m unittest tests_standalone.test_editor_group_prefabs_3725 -v
~~~

Gates : preview sans mutation, placement et Undo/Redo, héritage de deux instances, overrides propres, conflits de modifications manuelles, schémas invalides, source modifiée, isolation Qt/headless, et validation CI multi-OS. Les suites doivent être réellement exécutées avant intégration.

Suite : R38.2B inspecteur des autres propriétés et prévisualisation géométrique ; R38.3 refactoring typé transactionnel ; R38.4–6 validation de projet et conflits inter-auteurs.
