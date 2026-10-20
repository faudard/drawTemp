# R71.A — Connected Games Architecture (isolated laboratory)

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

## Explicit gates before any public network capability

1. **R67.C:** link an auditable GO decision and review threat model, transport
   authentication, ticket distribution, TLS, connection rate limits and abuse
   response. This in-process harness does **not** implement those layers.
2. **R70.C:** verify certified release SHA, migrations, export and real-player
   quality evidence. Neither a merged PR nor local unit tests are equivalent.
3. **R71.B:** add an isolated service adapter, failure-injection laboratory for
   latency/loss/reorder, metrics without secrets, version handshake and
   explicit client incompatibility handling. Keep solo mode offline.
4. **R71.C:** two-device private cooperative slice, CPU/network overload,
   reconnect and concurrency fuzz, authoritative replay, security audit,
   QA and **GO/NO-GO** on an exact commit SHA.

**Non-goals:** real transport, NAT, P2P, WAN matchmaking, production security,
rollback of published games, live migration, networked rewards, MMO or a
certified multiplayer runtime. The reducer is supplied by the trusted game
domain, rather than copied into a second engine.
