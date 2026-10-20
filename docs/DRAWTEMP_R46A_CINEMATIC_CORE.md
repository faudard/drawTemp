# R46.A — Cinematic Studio Pro : contrats et reprise

**État : code proposé en PR, pas release certifiée.**
Référence : roadmap R41–R50, section R46.1–R46.3.

## ADR — conserver la timeline unique R11

Le tableau canonique GameProject.cinematics conserve **strictement** son format
R11 : clips, pistes, événements, IDs, positions, sons, caméra, animation et FX.
Aucune deuxième timeline et aucune seconde vérité gameplay.

L'extension déclarative opt-in GameProject.extensions sous la clé
**drawtemp.cinematicpro** référence exclusivement les couples (clip, event)
existants. Chaque effet est déclenché au start_ms de cet événement R11, sans
timestamp parallèle. Le validateur rejette version inconnue, référence absente,
liaison en double et effet non autorisé.

La seule opération logique R46.A est **set_flag**, avec un nom de flag valide
et une valeur booléenne. Elle modifie les flags de la campagne dans le
GameSession canonique. Aucun eval, callback non contrôlé, inventaire parallèle
ou second moteur narratif n'est ajouté.

## Exemple de données versionnées

~~~json
{
  "extensions": {
    "drawtemp.cinematicpro": {
      "schema_version": 1,
      "data": {
        "version": 1,
        "cues": [
          {
            "clip": "war_council",
            "event": "decision",
            "effect": {
              "kind": "set_flag",
              "flag": "war_council_seen",
              "value": true
            }
          }
        ]
      }
    }
  }
}
~~~

Cet exemple présuppose que le clip R11 war_council contient déjà l'événement
decision. Les modifications doivent passer par une transaction AuthoringSession.

## Contrat d'exécution headless

- **cinematic_pro_start(clip_id)** : commence le clip, déclenche les effets à t=0.
- **cinematic_pro_advance(elapsed_ms)** : avance en millisecondes logiques
  entières et applique les effets franchis, triés par (start_ms, event_id).
- **cinematic_pro_pause() / resume()** : interrompt/reprend le curseur logique.
- **cinematic_pro_seek(position_ms)** : déplacement de prévisualisation
  *sans effet gameplay*, ne défait pas les effets déjà appliqués.
- **cinematic_pro_skip()** : applique une seule fois tous les effets restants,
  y compris ceux sautés par un seek, puis termine le clip.
- **cinematic_pro_state()** : état détaché du curseur et journal des effets.

Les effets appliqués sont enregistrés sous l'identité clip/event dans un
ledger persistant, une fois par campagne. La lecture R11 des images et
la présentation audio restent des projections sans effet de bord.

Les projets R46 sauvegardent **cinematic_pro** dans le même enregistrement
GameSession version 1 et dans le même checksum que la campagne. La reprise
valide curseur, statut, références et journal; les entrées absentes ou
malformées sont rejetées. Les anciens projets et enregistrements n'ont
aucune nouvelle clé.

## Tests

Commande : python -m unittest tests_standalone.test_drawtemp_r46a_cinematic_pro -v

Cas couverts : format historique, validation stricte, temps zéro, progression
en différentes tailles de pas, pause/reprise, seek sans effet, skip idempotent,
rechargement de checkpoint et refus d'enregistrements falsifiés.

## Dépendances et gates non validés

**R46.B** : éditeur Qt multipiste professionnel, trim/zoom/scrub, localisation,
voix/sous-titres, assets sous licence, Undo/Redo, validations Qt onscreen.

**R46.C** : connexion narrative complète R42, transitions action/CT,
épisode 90 s à deux parcours, sauvegarde et injections de crash, parité
Studio/Player, QA multi-OS, GPU/audio physiques, Player autonome.

R46.A ne propose encore que des effets booléens et un journal
once-per-campaign; les répétitions intentionnelles de séquences et les
choix narratifs restent à préciser dans R46.B/C. Aucune certification
8.6 n'est revendiquée.
