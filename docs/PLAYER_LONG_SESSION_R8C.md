# R8.C — Player long-session integration (R8.14–R8.16)

> Experimental, explicitly selected, **never a silent migration**.

The existing Player (and every legacy v2 session) continues to use
`SessionStore` unless the player selects **Sessions longues** on the title
screen. No saved-content schema changes and no additional tactical engine
or UI storage model are introduced.

## Player flow (R8.14)

Selecting *Sessions longues (expérimental, slots séparés)* changes the
destination for New Game and Continue to:

```
<profile_stem>_session_saves/<campaign_id>/slot_<number>.long.json
<profile_stem>_session_saves/<campaign_id>/slot_<number>.long.json.journal
<profile_stem>_session_saves/<campaign_id>/slot_<number>.long.json.bak
```

The ordinary `slot_<number>.json` file remains intact and independently
playable. New long sessions **refuse to overwrite** any previous slot,
backup or journal. Accepted actions are written to the bounded, atomic
`LongSessionStore` journal; pressing Save/Quit compacts that journal
into an independently replay-verified checkpoint. The bounded, opt-in
format introduced by PR #163 is unchanged.

At the headless API:

```python
from sporebound.player_controller import PlayerController

player = PlayerController(content, project, profile)
player.new_long_game("main", 1)
player.start_mission("garden")
player.execute({"kind": "end"})

resume = PlayerController(content, project, profile)
resume.load_long_game("main", 1)
assert resume.session.recording() == player.session.recording()
```

The public PlayerController commands still own gameplay state transitions.
The controller issues a new opaque request ID per accepted user intent.
`LongSessionStore` validates each action before durable publication and
deduplicates recent IDs across compaction. Its ID history is bounded (128);
it is **not** unlimited exactly-once delivery for network retries.

## Explicit migration (R8.14)

```python
player.migrate_to_long_game("main", 1)
```

The source is verified against current content/project/rules and campaign
identity **before** any destination is created. The copy goes into a new
`.long.json` slot, not into the source `.json` path. The GUI asks for
consent and then checks the copied slot; selecting Cancel changes nothing.

Changes to authoring rules, content versions, or battle replay protocols
are **not** silently migrated. Incompatible saves remain untouched.

## Player-visible recovery (R8.15)

```python
status = player.inspect_long_game("main", 1)  # never mutates disk or active player
if status.source == "backup" or status.degraded:
    # UI must show data-loss warning and ask permission.
    player.restore_long_game(
        "main", 1, expected_digest=status.session.recording()["digest"])
player.load_long_game("main", 1)
```

The GUI never automatically restores the backup. It explains that
actions since the fallback checkpoint may be lost and asks for confirmation.
The damaged primary is written byte-for-byte to `<slot>.damaged` before
the verified fallback is made primary. A previous `.damaged` is never
silently overwritten. A bad journal that cannot be independently verified
still fails closed.

## Single-writer lock (R8.16)

Mutations `initialize`, `perform`, `compact`, and `restore` on
`LongSessionStore` use a portable `O_CREAT|O_EXCL` advisory
`<slot>.lock` file. This protects the full read/verify/apply/publish
transaction, not just the final JSON replace.

- Simultaneous writers for the same long-session slot are rejected.
- A stale lock after a killed process is **not** automatically stolen:
  the operator must inspect the process and manually remove the lock
  after verifying it is no longer in use.
- Different campaign slots do not share a lock.
- Read-only inspection does not acquire a writer lock.
- No cross-device or network filesystem lock guarantees are claimed.

## Release gate

```sh
python -m unittest discover -s tests_standalone -p test_long_session_player_r8.py -v
python -m unittest discover -s tests_standalone -p test_long_session_r8.py -v
python -m unittest discover -s tests_standalone -p test_player_controller.py -v
python -m unittest discover -s tests_standalone -p test_save_contract.py -v
```

`tests_standalone/test_long_session_player_r8.py` additionally exercises
UI cancel, recovery acknowledgement, partial-write rollback, separate
legacy and long slots, explicit migration and lock refusal.

This PR does not auto-recover a stale lock; a future improvement may add a
read-only diagnostic (PID, creation time, inode, checkpoint digest) to
make *manual* recovery more comfortable. Promoting experimental long-session
mode to the Player default requires an independent release gate.
