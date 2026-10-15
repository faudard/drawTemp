# R1.E — Certification headless / renforcement du Game SDK

**Cible :** stabiliser R1 sur le `master` intégrant #252 (R1.9) et #259
(R1.6–R1.8, R1.10) ; ne pas réimplémenter les gates Qt, GPU et packaging R14.

## Contrat de certification

`drawtemp.sdk.certification.certify_trace` exécute toute une trace autorisée
sur deux **GameSession canoniques distinctes** issues de la même origine
vérifiée : l'une continue en mémoire, l'autre est restaurée entre chaque
commande. Pour chaque commande acceptée, le gate compare :

1. le `GameSession.recording()` exact, **pas uniquement le digest final** ;
2. le `GameSession.load()` sur un vrai fichier écrit atomiquement, sans
   mutation des octets par l'opération de lecture ;
3. l'empreinte complète de l'état tactique, y compris positions, PV, CT et
   actifs ; les empreintes dédiées des états RNG, CT/tick/activation et events ;
4. l'état global `MultiFrontSession.state()` (timeline, fronts, batailles
   ouvertes, ravitaillement si présent) dans les cas de siège.

La preuve est liée au checkpoint initial, notamment aux identités des
batailles. Deux sessions créées indépendamment avec la même seed peuvent
avoir des UUID différents : le gate compare deux **relectures du même
checkpoint**, pas des SHA bruts issus de nouveaux UUID.

Les erreurs (`CertificationError`) sont fail-closed avec codes
`invalid_budget`, `wrong_start`, `invalid_start`, `invalid_command`,
`step_failed`, `runtime_divergence`, `disk_divergence`,
`disk_mutation`, `state_divergence`.

## Exécuter

```shell
python -m pip install .
python -m unittest tests_standalone.test_drawtemp5_r1e -v
python -m drawtemp.sdk.certification_gate \
  --seeds 1 17 221 --combat-steps 12 \
  --report r1e-certification.json
```

Le gate CLI fait jouer le dialogue d'entrée, la mission Jeanne, le levier
ouvrant la porte, puis un échantillon borné de commandes tactiques générées
par l'IA canonique. Il émet `schema: 1`, `result: pass` et les preuves
par étape. **Un certificat ne peut être considéré obtenu que si le programme
se termine avec code 0 et si l'artefact est conservé par la CI du même SHA.**

Le workflow `drawtemp5-r0.yml` exécute les tests et le gate sur Python
3.10 / 3.12 / 3.14 et conserve `r1e-certification.json` parmi les
artefacts. Le gate n'est pas exécuté par anticipation sur le conteneur
de développement s'il ne possède pas de checkout exécutable du dépôt.

## Regressions testées

- Plusieurs seeds (1, 17, 221), commande, sauvegarde/reprise après chaque
  étape et empreintes séparées RNG, CT, events.
- Scénario multi-fronts canonique : doctrine, avance de timeline, focus,
  commande de bataille, sauvegarde et reprise exactes.
- Tampering d'un replay Battle interne **même après recalcul du hash du
  GameSession extérieur**.
- Écriture du backup en échec : les deux générations préexistantes restent
  intactes et lisibles.
- Lock de writer résiduel : aucun écrasement et aucune suppression automatique
  du lock.
- Sauvegarde d'une autre campagne, primaire illisible, liens symboliques,
  restauration explicite et préservation des octets `.damaged`.
- Résultats `SdkWorkQueue` : le worker n'applique jamais directement
  l'édition et seule l'API `AuthoringSession.apply` sur le thread propriétaire
  accepte les modifications ; imports publics sans Qt ou Tk.

## API proposée

Les types `CertificationError`, `CertificationStep`,
`CertificationReport`, `certify_trace`, `SdkWorkQueue`, `WorkTicket`,
`WorkResult` et `WorkQueueError` sont exportés via `drawtemp.sdk`.
Les capacités `certification.v1` et `workers.v1` sont annoncées ; le
statut du SDK **reste `provisional`** tant que ses gates n'ont pas été
observés en réussite.

## Conditions pour clore R1

- [ ] CI du commit final verte sur les 3 versions de Python.
- [ ] Certificats `r1e-certification.json` de chaque matrice collectés et
      inspectés (les SHA des replays varient avec les UUID d'instance).
- [ ] Tests de corruption/backup/concurrence sans échec et sans fuite de `.tmp`.
- [ ] Revue de compatibilité Content v1, GameProject v1, GameSession v1.
- [ ] R14 reste responsable des validations Qt, GPU réel, goldens, packaging
      et compatibilité multi-OS étendue (voir PR #254) : ces conditions ne
      sont **pas** déclarées satisfaites par les tests headless R1.E.

Le maintien de la compatibilité Tk reste obligatoire jusqu'à l'achèvement
et à la certification R16 ; ce lot n'enlève aucune API legacy.
