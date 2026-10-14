# Visual Fidelity & Art 2.0 — VF-B watercolor gallery

## What is in the Studio

The existing **Bibliothèque d’assets — Carte** palette now contains an
**Aquarelle** category, backed directly by the 88 sprite and 15 animation
entries in `assets/watercolor/registry.json`.

- Search by sprite or animation ID, family and author-readable title.
- Select an animated entry, step through its frames or play them at their
  *actual authored durations* (with clean timer cancellation on close).
- Preview only PNGs that exist and match the tracked SHA-256 provenance.
- Distinguish **unpublished**, **changed/tampered** and **verified** art.
- Decode an image only when selected (the 103-entry list is text-only).
- Reuse `AssetRegistry.resolve` for portable path and symlink safety.

The gallery is intentionally **read-only**. Art IDs are not gameplay actor
IDs or placeable structures; treating them as map brushes would corrupt the
authoring model. The palette's **Utiliser sur la carte** action is disabled
for watercolor entries. Existing terrain, architecture, character-placement,
undo/redo and Player flows remain unchanged.

**Shared-data gate:** The Studio reads the same validated `AssetRegistry`
and frame timing that existing presentation helpers use. This does **not**
yet switch the Player actor renderer to the watercolor pack. Binding
specific actors/objects to authored art and checking directional fidelity is
the next tranche (VF-C), once the real PNGs are committed.

## Navigation compacte par familles (UX)

Dans **Bibliothèque d'assets — Carte**, les entrées aquarelle sont désormais
regroupées sous leurs familles (Jeanne, Lancier, Loup, etc.). Une famille fermée
occupe une ligne au lieu de dérouler ses poses et animations au niveau racine.

- Sélectionner **Jeanne** affiche la pose `idle` si elle existe.
- Le champ **Pose / animation** permet de choisir Marche, Attaque, Garde,
  Victoire et les autres variantes déclarées, sans développer toute la liste.
- Les animations conservent leurs durées natives et le contrôle frame / lecture.
- Les sprites déjà utilisés comme frames d'une animation ne sont pas dupliqués
  dans l'arbre par défaut ; une recherche par identifiant exact les expose.
- Les groupes peuvent être développés à la demande. Le filtre **Aquarelle**,
  la recherche et les diagnostics de PNG absents restent disponibles.
- Le preview du sprite est centré et reste défilable si la source est plus
  grande que le viewport ; ceci ne corrige **pas** un éventuel débordement de
  pixels présent dans les PNG sources.

Ce changement ne modifie ni `registry.json`, ni les mappings Player, ni
le format de projet ou de sauvegarde. Les assets aquarelle demeurent en lecture seule.

## Delivery blocker: assets are still not checked in

The original V3 ZIP has been recovered and locally verified. However, the
repository currently contains metadata and provenance, **not the 88 PNG
binaries**. A green PR CI with `--allow-missing` is not a production art
certificate. Version-tag builds still require the strict 88/88 validator.

From a local checkout of this branch, publish through the already merged,
audited scripts:

```powershell
.\scripts\publish_watercolor_art.ps1 -RepoPath . -BundlePath "C:\Downloads\drawTemp_assets_Jeanne_88_sprites_v3.zip"
```

The importer refuses a non-V3 ZIP or mismatched original art, verifies the
88 indexed PNGs before committing, and does not force-push or merge the PR.

## Tests

```sh
python -m unittest tests_standalone.test_watercolor_catalog -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_watercolor_catalog_gui -v
```

**Accept VF-B** when searching the complete catalog, selecting Jeanne walk
frame 2, previewing an installed SHA-matching PNG and seeing a missing-art
warning without the PNG all work. Palette placement/undo and the Player must
remain behaviorally unchanged. Full Studio/Player art parity is a separate
future gate.
