# Balance Matrix 3.8.2 — comparaison multi-missions et compositions

Le **Balance Matrix** complète le [Battle Lab 3.8](BATTLE_LAB_38.md) sans
introduire de nouvelles formules de dégâts, heuristiques IA, ou schémas de
mission. Il réutilise `run_lab()` et sa validation de replay sur des copies
indépendantes du contenu.

## Workflow dans le Studio

1. Ouvrir **Espace projet → Balance Matrix**.
2. Choisir une mission et une variante guidée : **témoin**, PV alliés/ennemis,
   défense/attaque ennemie, retirer une unité, ou augmenter l'attaque d'une
   unité. Ajouter plusieurs scénarios, éventuellement sur plusieurs missions.
3. Fixer une **liste commune de seeds** et un plafond de commandes identique
   pour tous les scénarios, puis **Comparer les scénarios**.
4. Consulter le taux de victoire, les deltas de victoire, p95 CT/commandes,
   limites non résolues, et les échantillons par seed.
5. Enregistrer un rapport JSON et éventuellement une référence de version
   précédente. Le gate inter-versions compare **les mêmes ID de scénarios**
   sur les mêmes missions et seeds. On peut rejoindre le **Battle Lab** depuis
   une ligne de la matrice pour inspecter la mission authorée.

Le Studio ne modifie **jamais** les unités de la mission réelle : les
changements sont appliqués à une copie profonde du modèle `Content`, puis
soumis à `Content.validate()` et exécutés dans le moteur original.
Chaque mission comparée reçoit automatiquement un cas
`<mission>::baseline`. Une variante n'est **jamais comparée au témoin d'une
autre mission**.

Les presets Studio ne constituent pas un nouvel éditeur de classes, et le
retour vers le Battle Lab ouvre la **mission authorée**, pas une fausse scène
de variante. Pour comparer des classes entièrement équipées, l'API permet
de fournir des combinaisons explicites de champs tactiques déjà supportés
(armes, réactions, compétences, etc.), ou plusieurs `Content` pré-authorés.
La comparaison par les mêmes seeds est équitable mais reste **descriptive**,
sans conclure à une signification statistique.

## CLI — reproductible en CI

Le modèle JSON d'exemple est fourni dans
`examples/balance_matrix_382_cases.json`.

```sh
python -m sporebound balance-matrix \
    --matrix-cases examples/balance_matrix_382_cases.json \
    --seed 1 --runs 8 --limit 500 --report matrix_before.json

# Comparer après modification des règles/contenus :
python -m sporebound balance-matrix \
    --matrix-cases examples/balance_matrix_382_cases.json \
    --seed 1 --runs 8 --limit 500 --baseline matrix_before.json \
    --report matrix_after.json
```

La commande sort avec code **2** si un des scénarios dépasse un budget
autorisé (`--max-victory-drop`, `--max-p95-growth`,
`--max-new-limits`). Les ID, missions, seeds et plafond doivent correspondre,
ou la comparaison est refusée. Les comparaisons inter-versions sont des
**gates de régression**, différents des deltas exploratoires
variante/témoin d'une même exécution.

## API

```python
from sporebound.balance_matrix import run_matrix, compare_matrices

report = run_matrix(content, [
    {"id": "garden/no_archer", "mission": "garden",
     "remove_units": ["comptable"]},
    {"id": "garden/armor", "mission": "garden",
     "team_deltas": {"enemy": {"defense": 1}}},
], seeds=[1, 7, 42], max_commands=500,
   rulesets={"authored": my_authored_rules})

# Variantes de règles : fournir un autre RuleSet valide dans le mapping
# rulesets et référencer sa clé via {"ruleset": "variant_name"}.
```

Une variante peut utiliser `team_deltas`, `unit_deltas`,
`remove_units` ou `unit_overrides`. Les modifications d'unités ciblées
restent soumises au validateur canonique ; les effets tactiques réels
viennent exclusivement de `Battle`. Une variante de règles est un véritable
`RuleSet` fourni par l'appelant, jamais un dictionnaire de coefficients
ad hoc interprété par un deuxième moteur.

Limites : maximum **24 scénarios explicites**, **64 seeds** par scénario,
**10 000 commandes** par seed. Les témoins automatiques s'ajoutent aux
scénarios explicites ; pour les gros plans, réduire les seeds en itération
rapide puis lancer la batterie complète en CI.

## Critères de validation

- Deux runs identiques produisent les mêmes rapports, résultats et digests.
- Les seeds sont appariées par mission, y compris quand plusieurs missions
  sont analysées simultanément.
- Un ajustement d'unités n'altère jamais le contenu d'origine.
- Les entrées incohérentes, ou la suppression de tous les ennemis/joueurs,
  sont refusées par la validation des données.
- Les replays canoniques restent vérifiés et le rapport a un format JSON
  déterministe.
- L'ancienne référence `docs/evidence/battle_lab_garden_38.json`
  reste testée : ce chantier n'en modifie aucun seuil.
