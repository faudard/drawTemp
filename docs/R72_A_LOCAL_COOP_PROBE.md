# R72.A — Sonde headless de coopération locale (expérimentale)

**État : prototype de contrat hors Player, non certifié, décision de release NO-GO.**

Référence : [roadmap R51–R80](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md), lots R72.A (P0), R72.B (P1), R72.C (P0). R72 reste conditionné au GO documenté de R71 ainsi qu'aux gates R53/R65/R70.

## Contrats implémentés

- Module local drawtemp.quality.r72_coop_probe : deux sièges fixes, déconnexion/reconnexion, spawn déterministe, puzzle à deux plaques, deux attaques distinctes sur un boss, une seule récompense globale.
- Commande : joueur, séquence, révision observée, action, direction. Validation stricte; rejet atomique des actions invalides. Révision optimiste et séquences contiguës par joueur.
- Retry après ACK perdu : idempotence des commandes reconnues; refus explicite d'une charge différente sous une séquence déjà consommée.
- Snapshot avec format/version, état, journal accepté et digest SHA-256 canonique. Au restore, replay des commandes depuis l'état initial, comparaison de l'état final; tous les joueurs repartent hors connexion, puis doivent se reconnecter explicitement.
- audit_local_probe vérifie déconnexion, replay et récompense unique. Le rapport ne peut jamais afficher release_ready=true.

## Exécution

    python -m unittest discover -s tests_standalone -p 'test_r72_coop_probe.py' -v
    python -m drawtemp.quality.r72_coop_probe

Le test unitaire couvre stale revision, trous de séquence, ACK dupliqué, conflit de payload, restore, malformation, corruption, incompatibilité de schéma et décision de sortie fail-closed.

## Limites P0 / gates toujours bloquants

- Ce module est une **fixture locale de validation**, pas un deuxième moteur, pas un transport réseau et pas une intégration GameSession. Aucun Player solo ou save historique n'est modifié.
- Aucune authentification, autorisation, synchronisation réseau, prédiction, rollback transport, invitation, UX Qt, client réel ou dispositif distant. player_id n'est pas une preuve d'identité. L'appelant est local/de confiance.
- SHA-256 n'est ni une signature ni un MAC : la preuve d'intégrité ne protège pas contre un adversaire qui remplace un journal valide.
- Journal borné à 10 000 événements; pas de preuve de charge/DoS, GPU, tri-OS, clean-machine, Qt onscreen ou latence physique.
- R67/R71 : décision GO signée, protocole/autorité/transport/auth sécurité et adversarial QA; R53, R65, R70 certifiés.
- R72.B : UX deux joueurs, invitations locales, comportement déconnexion/reprise et tests sur deux appareils isolés.
- R72.C : adaptation sur GameSession canonique, puzzle/boss jouable, replays serveurs, latence/perte/désordre, divergence mesurée, verdict GO/REDUCE/NO-GO.

**Une sonde locale verte n'autorise pas le support multijoueur en production.**
