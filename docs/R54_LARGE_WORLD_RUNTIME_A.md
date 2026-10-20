# R54.A — Large World Runtime : fondation headless

R54.A fournit un **contrat optionnel** et non la certification globale R54.
R54.B (Inspector Qt, LOD et preview) et R54.C (intégration Player,
parité export, benchmarks p95/p99) restent à implémenter.

## Contrat canonique

L'extension `GameProject.extensions["org.drawtemp.streaming"]` emploie
l'enveloppe R24.3 : `{"schema_version":1,"data":{...},"references":[]}`.

La section `data` contient `version: 1`, `start`, `max_cache_bytes`
(1 KiB–32 MiB) et `cells` (1–256). Chaque cellule déclare :

- `id` stable, `region` stable et `scene` correspondant à une scène R25 ;
- `neighbors` (liens bidirectionnels vers au plus huit voisins) ;
- `entities` (jusqu'à 64 paires `{id, initial}`, IDs globaux uniques).

Les portails doivent exister dans `GameProject.scene_routes`; chaque cellule
doit être accessible depuis `start`. Aucun chemin de fichier, script projet
ou nouvel état d'inventaire parallèle n'est accepté.

## État du jeu et reprise

`GameSession.route_transition()` met à jour le curseur R54 seulement après
validation du routeur canonique. Le rollback restaure également R54.
`world_stream_event(id, entity, before, after)` applique un CAS persistent
et idempotent, sans réattribuer de récompense.

Le checkpoint `world_stream` porte `version/history/events`, validés
avant mutation. Son historique de cellules est recoupé avec le journal
`scene_route` R25. Un projet sans extension ne change pas de format
de sauvegarde.

## Cache temporaire et annulation

`WorldCellCache` accepte uniquement un chargeur fiable fourni par le
Player/Studio ; aucune fonction n'est importée ou exécutée depuis le
manifeste utilisateur. `request` fournit un ticket, `resolve` applique
une copie JSON validée au LRU, `cancel` invalide le ticket. Même si un
worker termine après annulation, aucun chargement tardif ne modifie le cache
ou `GameSession`.

Budget résident borné, 8 requêtes simultanées maximum, 1–4 workers,
charge utile maximale de 2 MiB. Les méthodes de contrôle sont prévues
pour être appelées depuis un seul thread propriétaire.

## Vérification

```sh
python -m unittest tests_standalone.test_r54_world_streaming -v
```

Cas prévus : trajet sur trois cellules et retour, sérialisation, corruption,
rejeu idempotent, validation des arêtes, LRU, détachement des copies, annulation
et retour tardif, échec de chargeur et dépassement mémoire.

**Statut de gate :** R54.A seulement. Aucun viewport Qt, export Player,
endurance ou certification GPU n'est revendiqué.
