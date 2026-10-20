# R73.A — Network Session Policy (laboratory contract, NO-GO)

Status: **implemented headless policy checks only**. This is not network gameplay,
a supported protocol, an authenticated transport, a GUI Session Designer, or an
exportable cooperative Player. In particular **R71 and R72 have not been
certified GO** by this work. R73.B and R73.C remain blocked.

Reference: [R51–R80 detailed roadmap](../DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md),
R71/R72/R73 and their evidence gates.

## Scope of this PR

- `drawtemp.sdk.network_session_policy.SessionPolicy` is immutable,
  declarative and explicitly **opt-in**. Without opt-in all checks return
  `opt_in_required`.
- Exact JSON-compatible version 1 policy document; unknown/duplicate command
  definitions rejected, protocol pinned to **`r73-lab/1` (research-only)**,
  local-only privacy, content/project SHA-256 identity and bounded commands.
- Permissions: immutable host identity, max two member IDs, explicit allowlist
  and a host-only command subset. A trusted host/transport must provide the
  authenticated actor binding; a client string is **not authentication**.
- Commands: fail-closed JSON envelope with duplicate-key rejection, bounded
  payload/depth, strict monotone per-actor sequence, idle timeout and
  unknown-command denial. This function does **not execute commands**.
- Crash/rejoin: only compares candidate metadata against a **host-provided**
  canonical GameSession checkpoint revision/digest and committed sequence.
  It never writes/restores a save, runs rewards or owns replay authority.
- All join/command/rejoin checks require *both* trusted, verified R71 and R72
  gates. Default is **NO-GO**; test-supplied gates are simulation only.
  Caller must never read `approved_gates` from any client packet.

## Host-side integration contract (future R71/R72)

1. Authenticate a remote actor using a separately reviewed transport and
   associate its identity with the session. Neither IDs nor hashes are secrets.
2. Validate actual R71/R72 evidence; create a **host-owned** immutable
   `frozenset({"R71", "R72"})` only after gate approval. Do not authorize
   a game to set these values itself.
3. Derive the policy digests from validated canonical project/content.
   Invoke `evaluate_join` before adding the actor to the trusted membership.
4. Invoke `evaluate_command` with trusted identity, membership, authoritative
   previously committed per-actor sequence, and a monotonic last-seen duration
   before forwarding any command through the *existing* GameSession.
   Only advance committed sequence after GameSession confirms commitment;
   reject duplicates after reconnection.
5. Persist/recover with canonical GameSession only; pass its trusted
   checkpoint revision/digest and committed sequence to
   `evaluate_rejoin`. A stale client cannot overwrite state. Replay missing
   commands from the host journal, never re-award loot or rewards.
6. A future Session Designer must only **stage** policy changes through
   canonical authoring/validation/Undo; it must not open sockets while editing.

## Unsupported / threat model

This module deliberately has **no socket, TLS, invitation token, transport
authentication, packet sequencing across channels, host migration, authority
handoff, state replication, bandwidth telemetry, crash recovery, Qt UI or
export integration**. It is a building block, not a defense against a
malicious host or compromised server. No external networking should be exposed
on this basis. The solo Player, SDK capabilities and existing saves are
unchanged.

## Verification

```sh
python -m unittest -v tests_standalone.test_r73a_network_session_policy
python -m unittest -v tests_standalone.test_game_session
```

R73.A policy proof: unknown versions, invalid JSON/IDs/digests, absent gates,
spoofed peers, capacity, host-only operations, command replay/reorder, timeouts,
oversized commands and stale rejoin are rejected. CI runs this headless in
Python 3.10 and 3.12. **This does not meet R73's full gate**; R71.C and
R72.C, security/transport reviews, real two-machine testing, Qt UX,
clean-machine export and explicit GO/NO-GO evidence remain mandatory.
