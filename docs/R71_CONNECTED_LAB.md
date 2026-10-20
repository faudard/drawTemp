# R71.A–C — Connected Games Architecture (isolated laboratory)

**Status:** experimental, not player-facing; **R71 GO not certified**.
The canonical R51–R80 roadmap makes R71 conditional on **R67=GO** and the
R70 certification. No GO documentation was established as part of this lot.
This PR deliberately does **not** activate multiplayer, introduce a network
listener, change GameSession, or alter existing CT, save, replay, project/asset
schemas, Player or Studio entry points.

## Contract (v1)

- The sporebound.connected_lab_r71 module implements a strict UTF-8 JSON message
  envelope with version, type=command, session, player, sequence, tick, entity
  and command={kind,args}. Extra fields, duplicate JSON keys, nonfinite numbers,
  invalid identifiers/types, excessive frames and arbitrary nested payloads
  are rejected.
- A **trusted host** supplies a static ownership table, a command-kind
  allowlist, secret tickets issued **out of band**, and a deterministic pure
  reducer. An unauthenticated, unauthorized or stale command never reaches the
  reducer. Reconnect rotates bearer tickets; the journal excludes credentials.
- Two participants maximum, 32 entities, 4 KiB/frame, eight ticks of
  lookahead, 32 inputs/tick, 64 KiB state. The host-side lab uses the existing
  FixedTickJournal for ordering, state digests and replay.
- Failed tick reducers leave the local state snapshot and tick unchanged.
  Replay rechecks recorded ownership/sequence and compares per-tick checksums.
  Checksums prove reproducibility, **not authenticity of a hostile server**.

## Verification

    python -m unittest tests_standalone.test_r71_connected_lab -v
    python -m unittest tests_standalone.test_r25_foundation -v

Adversarial cases: unknown protocol versions, unexpected/duplicate fields,
UTF-8 corruption, oversized frames, NaN, invalid authority, replayed or missing
sequences, wrong tickets, disconnected participants, distant or backward ticks,
reducer failure without partial commit, and tampered recordings.

## R71.B — in-process service, fault injection and diagnostics

R71.B adds `sporebound.connected_service_r71` without modifying any offline
Player/GameSession entry point:

- **`ConnectedLabService`**: per-client version/capability handshake,
  admission with R71.A ticket rotation, disconnect/rejoin, safe command
  acknowledgments, deterministic tick forwarding and read-only snapshots.
  Malformed/unnegotiated/stale commands never reach game logic.
- **`FaultProfile` + `SimulatedSessionLink`**: seeded virtual-time packet
  latency, jitter, percentage-based loss and duplication, scheduled packet
  reorder and bounded queues (256 packets). It is not a real transport:
  packets are fed into the service in memory. Game ticks advance separately.
  A packet that arrives after its authoritative deadline is **rejected**;
  reliable retransmission/compensation is not implemented or claimed.
- **Diagnostics**: service counters and bounded status codes, virtual-link
  delivery/drop/duplicate/reorder counts, latency min/max/p95 in virtual
  steps, pending capacity and current tick. No message bodies, player names,
  tokens, or credentials are stored in diagnostic events. Latency is **not**
  measured WAN latency or a real-time millisecond benchmark.
- **Version handling**: v1 and capability `commands_v1` are mandatory;
  unsupported clients fail closed. `plan_v0_hello_migration` prepares only
  an **explicit upgrade proposal** for a v0 hello; it does not permit legacy
  command frames to connect or silently migrate a session/gameplay save.

### Run tests and laboratory evidence

```sh
python -m unittest tests_standalone.test_r71_connected_lab -v
python -m unittest tests_standalone.test_r71_connected_service -v
python -m unittest tests_standalone.test_r25_foundation -v
python scripts/r71_lab_report.py --seed 71 --latency 2 --jitter 1 --loss 25 --duplicate 10
python scripts/r71_lab_report.py --seed 71 --latency 1 --reorder-every 2 --reorder-delay 3
```

The CLI runs a private, two-identity increment-only reducer and prints
`r71b-lab-report-v1` JSON containing link/service counters, an
authoritative state digest and a replay journal digest, **not secrets**.
Varying loss/reorder may result in deliberately rejected packets; such a
report is not proof of seamless cooperative gameplay. The sample uses an
independent laboratory reducer, not a copied tactical engine.

Local R71.A/R71.B isolated smoke tests (against an R25 journal shim) pass,
but **full repository CI has not been verified**. Treat any GitHub workflow
failure before job startup as a verification blocker, not a passed test.

## R71.C — private cooperative certification probe (NO-GO)

The opt-in `sporebound.connected_certification_r71` module adds a bounded,
fully offline, two-player pressure-plate scene driven through R71.A's canonical
FixedTickJournal and R71.B's simulated fault link. **Both participants must
submit an authorized `hold` on the same authoritative tick**. The gate opens
at most once; it does not create loot, inventory, achievements, game saves or
a separate Player runtime.

Evidence includes:

- A clean 2-player run with authoritative replay and per-tick checksums.
- Seeded packet loss, duplication, jitter, reordering and late-command
  rejection. These failures are visible, not masked by client prediction.
- Disconnect/rejoin with ticket rotation, refused commands while offline and
  restored authoritative snapshots.
- A 256-packet simulated queue saturation attempt, atomic overflow refusal,
  anti-replay rejection, and deterministic replay after the flood.
- Replay tamper checks (including forged outer and journal digests) and
  explicit version-incompatibility refusal.
- A reproducible JSON decision report whose **current decision is NO-GO**.

Run:

```sh
python -m unittest tests_standalone.test_r71_connected_certification -v
python scripts/r71c_certification.py --seed 71
# Explicit automated release gate: nonzero (2) while not certified
python scripts/r71c_certification.py --seed 71 --require-go
```

The ordinary evidence command returns 0 after producing an accurate NO-GO
report; `--require-go` returns 2 to prevent interpreting a research artifact
as a certified release. The report contains no credentials or gameplay/user
identities. It deliberately marks R67=GO, R70 certification, real authenticated
transport, sender-bound identities, two physical devices, CPU/memory/bandwidth
measurements, security audit, and cross-platform CI as **unproven/false**.

**Operational gap:** the R71.B in-memory service does not bind a command's
claimed `player` to a verified network transport identity. Sequence numbers
and rotated lab tickets do not replace transport authentication. No public
connection, production anti-cheat or reliable resend is provided. A true LAN
two-device demonstration, security/DoS review, real measured load, CI and a
human signed GO decision remain prerequisites; R67.C currently says REDUCE.

### R71.C certification result

**NO-GO for a product release.** A successful in-memory replay is evidence
of a narrow deterministic contract, **not** evidence for operational security,
real multiplayer reliability, platform compatibility, transport availability,
or completed R70 gates. Keep R71 optional and the solo Player entirely offline.

## Explicit gates before any public network capability

1. **R67.C:** link an auditable GO decision and review threat model, transport
   authentication, ticket distribution, TLS, connection rate limits and abuse
   response. This in-process harness does **not** implement those layers.
2. **R70.C:** verify certified release SHA, migrations, export and real-player
   quality evidence. Neither a merged PR nor local unit tests are equivalent.
3. **R71.B:** the isolated in-process service/seeded fault lab and client
   version negotiation exist on this experimental branch; integrated CI,
   operational metrics and security certification remain unverified.
4. **R71.C:** the *offline* two-client fixture, queue saturation/reconnect,
   replay and fail-closed NO-GO report are available. A real **two-device**
   transport test, CPU/memory and network instrumentation, fuzz/concurrency,
   security audit, QA and human GO are **not** complete.

**Non-goals:** real transport, NAT, P2P, WAN matchmaking, production security,
rollback of published games, live migration, networked rewards, MMO or a
certified multiplayer runtime. The reducer is supplied by the trusted game
domain, rather than copied into a second engine.
