# ADR R67 — Faisabilité multijoueur, serveur autoritaire et gate

**Statut :** étude R67.A–C / prototype de laboratoire, décision **REDUCE** (pas de GO produit).
**Portée :** coopération privée, exactement deux participants sur une scène bornée.
**Roadmap :** [R67, R51–R80](DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md).

## 1. Décision d'architecture (R67.A)

- **Autorité :** le serveur est seul propriétaire des positions et de la progression du tick. Les clients transmettent des intentions validées (déplacement cardinal seulement). Ni coordonnées arbitraires, ni état du monde, ni commandes d'inventaire ne peuvent être écrits par un client.
- **Horloge :** 60 ticks/s logiques. Simulation entière (grille), exécution ordonnée `p1`, puis `p2`; un input absent équivaut à ne pas bouger. Aucun FPS d'affichage n'est utilisé comme source de vérité.
- **Commandes :** `{version,player,tick,seq,dx,dy}`, schéma exact v1, plages bornées, identification de l'expéditeur hors paquet, rejet des séquences répétées, des ticks tardifs et trop futurs (`MAX_AHEAD=16`). Ce n'est **pas** un protocole de sécurité opérationnel : dans le laboratoire, l'identité est fournie directement par l'orchestrateur.
- **Synchronisation :** snapshots autoritaires complets `{version,tick,positions,digest}`, horodatés par tick; le client conserve uniquement le snapshot validé le plus récent. La validation SHA-256 permet de détecter une corruption accidentelle dans ce prototype, **pas** de prouver l'authenticité d'une source.
- **Rejeu :** le serveur journalise, pour chaque tick, les inputs acceptés et un digest canonique. `verify_journal` reconstruit la scène depuis son état initial et contrôle chaque digest; aucun autre moteur métier n'est créé.
- **Transport à l'étude :** datagrammes non fiables simulés, seed, latence, jitter et pertes reproductibles. Aucun socket, aucun port ouvert, aucune découverte de pairs. Comparer ultérieurement un service TLS/WebSocket simple avec un transport UDP/QUIC authentifié; choix **reporté** tant que les mesures réelles et la surface d'attaque ne sont pas connues.
- **Compatibilité :** ce spike est volontairement isolé dans `drawtemp/sdk/r67_network_feasibility.py`. Il n'ajoute aucune capability publique, ne modifie ni `GameSession`, ni `ActionRuntime`, ni les sauvegardes solo, ni le Player/Studio.

### Menaces / limitations explicites

| Menace ou limite | État du spike | Exigence avant tout GO |
|---|---|---|
| Usurpation `player`, champs cachés, téléportation | Commandes strictes, identité attachée à l'envoi simulé | Authentification réelle, liaison identité/session, isolation des clients |
| Replay / réordonnancement / déconnexion | Numéros de séquence, ticks, rejet fail-closed; aucune reconnexion | Fenêtre anti-replay documentée, accusés de réception, rejoin et restauration |
| Corruption / injection des snapshots | SHA-256 sans secret (non authentifiant) | TLS ou chiffrement authentifié, parsing sécurisé, limite de taille des messages |
| DoS / saturation / mémoire | Nombre de ticks borné pour l'essai | Rate limiting par client, quotas mémoire, fuzz et tests de charge |
| Divergence / triche temporelle | Inputs bornés, digest et replay serveur | Tests d'horloge dérivée et latence réelle, corrections sans client authoritative |
| Vie privée / données de session | Pas de télémétrie réseau ni de stockage | Politique de rétention, opt-in et suppression, audit RGPD |
| Plateformes / maintenance | Python stdlib en mémoire, aucun device réel | Windows/Linux/macOS, CI, 2 machines physiques, coût d'hébergement |

## 2. Prototype et reproductibilité (R67.B)

```bash
python -m unittest discover -s tests_standalone -p "test_r67_network_feasibility.py" -v
python scripts/r67_network_spike.py --seed 67 --ticks 240 --loss-percent 8 --latency-ticks 2 --jitter-ticks 2 --input-lead 5 --snapshot-interval 4
```

Tous les paramètres sont des entiers bornés. La latence et le jitter sont des **ticks virtuels** (16,67 ms par tick), non une mesure de RTT réel. L'échantillon ci-dessous est généré localement pour ces options : 2 acteurs, 240 ticks, 8 % de perte probabiliste indépendante sur uplink/downlink.

| Mesure simulée | Valeur |
|---|---:|
| Commandes émises / perdues uplink | 470 / 54 |
| Snapshots émis / perdus downlink | 120 / 8 |
| Rejets de séquence réordonnée | 34 |
| Dérive p95 / maximale des snapshots clients | 7 / 14 ticks |
| Retard final client p1 / p2 | 0 / 4 ticks |
| Journal déterministe | `replay_verified=true` |

Le rejet de commandes réordonnées est un **coût visible** de la politique anti-replay simplifiée; pas une fonctionnalité de rollback ni de livraison fiable. Les mesures changent selon le seed et les paramètres; elles ne démontrent aucun comportement réseau physique.

## 3. Gate R67.C — REDUCE

**Décision courante : REDUCE** : poursuivre uniquement l'étude d'un mode coop à deux joueurs sur réseau local contrôlé. **Aucun GO** pour R71–R73, qui restent hors chemin critique de release, et aucune promesse MMO, lobby public, connexion Internet, synchronisation de sauvegardes ou multijoueur commercial.

La décision **GO** ne pourrait être discutée qu'après **toutes** les preuves suivantes :

1. Contrats R25/R29/R56/R59/R60 vérifiés sur `master`, non inférés des roadmaps; chemins de sauvegarde/replay solo inchangés.
2. Démonstration sur **deux appareils réels** Windows/Linux/macOS concernés, avec latence/jitter/perte mesurés; scénarios de déconnexion, réordonnancement, tick drift, reconnexion, tick rollover et saturation.
3. Transport authentifié, versionnement, limites et quotas, fuzz de trames, anti-replay et modèle de menace revus; aucune autorité donnée au client sur progression, récompenses ou inventaire.
4. Budget explicite CPU/mémoire/bande passante, p95/p99, rétention/consentement, coûts d'exploitation et plan de maintenance.
5. Tests de non-régression CT/action/solo, audits de sauvegardes, revue de sécurité, CI multi-OS et arbitrage humain signés.

**NO-GO** si un de ces invariants ne peut pas être garanti à coût acceptable; **REDUCE** si l'intérêt de la coopération subsiste mais sans justification de maintenance ou sans données physiques. Le spike ne saurait décider automatiquement du GO à partir d'un bon digest.

## 4. Dépendances et suites proposées

- **R67.A :** ADR et restrictions ci-dessus documentés; choix réel de transport encore ouvert.
- **R67.B :** scène artificielle deux joueurs, canal bidirectionnel dégradé, snapshots autoritaires, replay et tests automatisés; **pas** de réseau LAN réel.
- **R67.C :** décision REDUCE motivée, report explicite R71–R73; pas de release multijoueur.
- **Suite si étude reconduite :** adapter, avec protocole versionné et authentifié, une scène bornée déjà pilotée par le Core (plutôt que reproduire sa logique) et monter un banc à deux machines. Ne modifier les formats de sauvegarde qu'après une décision d'architecture distincte.
