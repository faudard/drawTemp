# R62.A — Farming & Life Simulation : fondation déterministe

Statut : **implémentation headless/SDK en PR, gate R62 ouvert**. Cette tranche
suit [R62 dans la roadmap R51–R80](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md).
Les éditeurs visuels R62.B, le Player Qt et le vertical slice R62.C ne sont pas
implémentés dans ce lot.

## Source de vérité

- Configuration opt-in : `GameProject.extensions["org.drawtemp.farming"]`
  au format standard `{"schema_version":1,"data":{...},"references":[]}`.
- Dépendance obligatoire : `org.drawtemp.livingworld` (R35). Le **jour**
  est `LivingWorld.day`, jamais une deuxième horloge. Une avance explicite
  de R35 ou un tick de déplacement temps réel/platform déclenche une
  synchronisation des fermes, même quand leur scène n'est pas au focus.
- Inventaire et récompenses : `GameSession.progress.inventory` (Campaign).
  Les IDs d'objets doivent venir des équipements canoniques ou des ressources
  R55 validées, pas d'un inventaire R62 parallèle.
- Le moteur tactique CT, les projets sans extension et les anciens checkpoints
  ne changent pas de format : le bloc `"farming"` est absent par défaut.

## Contrat auteur R62.A (version 1)

```json
{
  "version": 1,
  "seed": 62,
  "season_days": 14,
  "weather": true,
  "plots": [
    {"id": "field", "scene": "arrival", "soil": "loam"}
  ],
  "crops": [
    {
      "id": "medicinal_herbs",
      "seed_item": "herb",
      "yield_item": "elixir",
      "yield_quantity": 2,
      "grow_days": 2,
      "soils": ["loam"],
      "seasons": ["spring", "summer"]
    }
  ],
  "animals": [
    {
      "id": "hen",
      "scene": "arrival",
      "feed_item": "herb",
      "yield_item": "elixir",
      "yield_quantity": 1,
      "interval_days": 1
    }
  ]
}
```

Cet exemple est **un extrait de `data`** et nécessite que `arrival`, `herb`
et `elixir` soient des identités présentes dans le projet/Content.
Les cultures poussent après `grow_days` jours écoulés ; les animaux doivent
être nourris (jour courant ou précédent) avant une collecte, une seule fois
par période `interval_days`. Les quatre saisons suivent une rotation fixe.
La météo optionnelle (`rain/cloud/sun`) est une projection déterministe
`(seed, day)` : elle **n'affecte pas encore** la vitesse de pousse ni les
besoins hydriques, réservés aux lots ultérieurs.

Bornes : 128 parcelles, 64 cultures, 64 animaux, 1024 reçus de commande,
entiers de stock 0..1 000 000, calendrier fondé sur les jours entiers.
Identifiants, scènes, sols, saisons et items sont validés strictement, sans
hooks Python ni expression arbitraire.

## API et garanties

- `GameSession.farming_state(scene=None)` : projection détachée de la saison,
  de la météo, des parcelles et de l'état des animaux. `scene=None`
  inclut les fermes hors focus.
- `farming_plant(plot_id, crop_id, receipt_id)` : consomme une graine via
  l'inventaire canonique ; sol, saison et occupation validés.
- `farming_harvest(plot_id, receipt_id)` : crédite le rendement une seule
  fois après maturité, en libérant la parcelle.
- `farming_feed(animal_id, receipt_id)` et
  `farming_collect(animal_id, receipt_id)` : consomment la nourriture,
  contrôlent le rythme et attribuent la production.
- Les appels passent par la scène routée active, sans dialogue ni bataille,
  avec prévalidation sur copie isolée : aucune modification partielle en cas
  de refus (inventaire insuffisant, calendrier, seuils, id, capacité).
- `drawtemp.sdk.simulation.Simulation` expose les mêmes opérations avec
  `expected_revision` et une projection gelée pour UI/Player.
- Les reçus contiennent `kind`, `target`, `day`, `id` et la culture
  lors d'un semis ; ils sont rejoués à la restauration pour vérifier
  l'état complet des parcelles, animaux et calendrier. L'identifiant est
  idempotent : une même commande n'est pas payée ou récompensée deux fois.
  Ce contrôle n'est **pas** une signature cryptographique.

## Vérification prévue

```sh
python -m unittest tests_standalone.test_r62_farming_life -v
python -m unittest tests_standalone.test_r35_commerce -v
python -m unittest tests_standalone.test_r55_system_design -v
python -m unittest tests_standalone.test_r25_scene_router -v
```

Le fichier `.github/workflows/r62-farming-life.yml` cible ces contrôles en CI.
Le gate R62 exige encore R62.B Farm/Relationship Studio (formulaires typés,
conditions, Undo/Redo), R62.C VS-62 jouable dans le Player Qt, endurance
multi-jours et multi-seeds, validation UX/accessibilité et CI sur le SHA final.
**Aucun de ces gates n'est déclaré certifié ici.**
