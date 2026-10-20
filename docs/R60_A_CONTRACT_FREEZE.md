# R60.A — Contrats figés et préflight des migrations historiques

**Statut :** implémentation partielle et contrôles headless. **Pas de release 10.0 certifiée.**
Référence : [roadmap détaillée R51–R80](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md#r60--game-production-studio-100-100).

## Contrats gelés pour ce lot

- SDK api_version = [1, 0], status = provisional, négociation explicite existante (R24/R30).
- Content.version = 1, GameProject.version = 1, GameSession/replay schema 1. La numérotation produit 5.x→10.x **ne crée pas** de version 10 pour ces formats.
- Le comportement Jeanne/CT/replay est comparé à l'intégralité du golden historique docs/drawtemp5/reference-baseline.json, et non uniquement à result=victory.
- Les documents v0-envelope connus bénéficient d'une **prévisualisation** vers v1 via preview_documents. Les schémas futurs, inconnus ou corrompus sont refusés.
- Aucun jeu, sauvegarde, original ou golden n'est modifié par l'audit. Le module ne déclenche pas la migration : elle reste une opération explicite, distincte et vérifiée.

Le nouveau module drawtemp.quality.r60_freeze génère un bilan machine en lecture seule. Une dérive de contrat, du replay, de hash ou une version inconnue bloque la vérification de compatibilité. Même un bilan technique vert reste **NO-GO** : seule une revue indépendante peut autoriser la release.

## Matrice de fixtures contrôlée

Une équipe peut fournir un manifeste supplémentaire de paires historiques (**aucune conversion automatique**), de cette forme :

~~~json
{
  "schema": 1,
  "pairs": [
    {
      "id": "projet-historique",
      "content": "fixtures/legacy.json",
      "project": "fixtures/legacy.game.json",
      "content_sha256": "<sha256 réel lowercase du fichier>",
      "project_sha256": "<sha256 réel lowercase du fichier>"
    }
  ]
}
~~~

Les deux SHA-256 doivent être figés après revue des octets originaux. Les chemins sont relatifs au checkout, sans traversée ni symlink, et chaque paire est validée par le Core canonique. Les entrées sont bornées en taille et en nombre. L'absence de corpus ou d'une migration réelle reste un **bloqueur documenté**, jamais un faux passage.

Exécution locale / CI :

~~~sh
python -m unittest tests_standalone.test_r60_contract_freeze -v
python -m drawtemp.sdk.migration --verify-baseline docs/drawtemp5/reference-baseline.json
python -m drawtemp.quality.r60_freeze --root . --revision "$(git rev-parse HEAD)" --output r60a-report.json --enforce-regressions
# Audit opt-in des paires historiques :
python -m drawtemp.quality.r60_freeze --root . --revision "$(git rev-parse HEAD)" --fixture-manifest fixtures/r60a-manifest.json --output r60a-corpus.json --enforce-regressions
~~~

Le workflow r60a-contract-freeze.yml exécute le test à deux versions Python et produit un artefact pour le SHA évalué. Le rapport n'est ni une signature, ni la preuve d'une exécution GPU, ni un certificat de publication.

## Gate R60 / suivi restant

| Lot | Avancement vérifiable | Bloqueurs |
|---|---|---|
| R60.A (ce lot) | Snapshot des contrats, parité historique R0, préflight hash-pinné, refus des versions inconnues | Corpus multi-versions étendu, validation des migrations 5.x→10.x sur projets réels, vérification des gates R40–R59 |
| R60.B | Non livré ici | Jeu original hybride ville + groupe + temps réel↔CT + boutique + quêtes + HUD + 2 régions, éditable par Studio |
| R60.C | Non livré ici | CI de master finale, 3 OS, GPU matériel, UX tiers, droits, sauvegardes et export sur PC propre, dossier signé et décision humaine |

**Politique de merge :** PR dédiée ciblant master. Ne pas présenter un merge de code ou des tests headless comme une certification R60.C. Les mutations du format sauvegarde restent interdites hors ADR/migration explicitement approuvée.
