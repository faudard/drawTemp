# R29.C — Dual-runtime disk replay and conditional hybrid certification

**Statut : code proposé, R29 release NO-GO.** Dépendances R29.A #299 et R29.B #313 ; les PR R26 #300, R25.A #298 et R25.B #314 restent séparées.

## Portée réelle

R29.C audite deux moteurs déjà prévus dans la roadmap, sans en introduire un troisième :

- **Action R26** : audit_action_disk compare à chaque tick les événements et digests de deux instances du vrai ActionRuntime. Tous les N ticks, la seconde sauvegarde sur disque puis recharge son état ; le replay est vérifié, les entrées ne sont pas mutées et une sauvegarde volontairement altérée doit être rejetée.
- **Transitions CT R25.B** : audit_route_disk applique uniquement route_move, route_transition, execute, abandon_encounter et return_to_campaign à deux GameSession authentiques. La seconde est restaurée depuis disque et doit être identique à la première après chaque commande. Les préconditions de scène et de mission restent appliquées ; campagne → bataille CT → campagne est mesuré.
- **Consolidation** : assemble_evidence distingue les deux probes. Quel que soit leur résultat individuel, la transition *temps réel → CT → temps réel* et la sauvegarde commune restent bloquées. Le rapport contient toujours hybrid=blocked, release_ready=false, decision=no-go.

## CLI reproductible

Tests de contrat :

    python -m unittest tests_standalone.test_r29c_integrated -v

Résumé des dépendances :

    python scripts/certify_r29c_journeys.py --report out/r29c.json

Sur une branche ayant **réellement intégré R26** :

    python scripts/certify_r29c_journeys.py --scene authored_action.json --action-commands tick_inputs.json --checkpoint-every 5 --require-action --report out/r29c-action.json

Les commandes action portent des ticks entiers contigus 1..N, compatibles avec ActionRuntime.step.

Sur une branche ayant **réellement intégré R25.B** :

    python scripts/certify_r29c_journeys.py --route-content game.json --route-project game.game.json --route-initial initial-session.json --route-commands route-commands.json --checkpoint-every 2 --require-route --report out/r29c-route.json

L'enregistrement initial est celui de la vraie GameSession ; aucune option ne force les flags ou déverrouille des missions. Les commandes de route sont une liste JSON avec op et args, limitée à la liste autorisée.

Codes retour : 0 = collecte sans échec, **pas certification** ; 1 = erreur vraie/entrée invalide ; 2 = dépendance explicitement requise absente ou --require-release.

## Tests, CI et limites

Le workflow drawtemp-r29c-integrated.yml lance les tests de contrat Python 3.12 sur Ubuntu/Windows/macOS. Les deux tests d'intégration requièrent les vrais modules issus des PR #300/#314 : sans ces dépendances, ils sont **skipped et signalés**, pas simulés.

Validation locale initiale : **six tests exécutés et réussis ; deux tests d'intégration skipped**. La validation effective de R26 et R25.B sur le SHA intégré, ainsi que la CI du présent commit, ne sont pas acquises par ce résultat.

**R29 reste NO-GO.** Cette tranche ne certifie ni sauvegarde transactionnelle hybride commune, ni reprise entre genres, ni RPG menu, ni UI Qt, GPU matériel, goldens, licences, export sur PC propre, ni tests humains.

Étape suivante : réunir R25.B et R26 dans une session propriétaire unique, écrire le parcours action→CT→action avec état commun et crash injection aux frontières, puis exécuter les vrais probes sur le SHA consolidé. Références : roadmap R29 multi-genres et documentation R29.A/B.
