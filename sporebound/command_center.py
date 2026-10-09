"""Text command centre for simultaneous tactical fronts.

Pure dashboard rendering is UI-framework agnostic. The small REPL can be run
without Tk and uses only session methods, keeping replay/save deterministic.
"""
import json
import os
from pathlib import Path
import shlex
import tempfile

from .fronts import MultiFrontSession
from .model import RuleError, require

HELP = """Commands:
  status                         Show all fronts, convoys and last orders
  focus FRONT                    Switch controlled battle
  doctrine FRONT hold|assault|delay|retreat
  turn [N]                       Advance 1..20 strategic turns
  reserve FRONT ID X Y           Send one player from finite reserves
  transfer FRONT ID X Y          Transfer an idle player from focused front
  escort CONVOY_ID               Spend one escort to avoid one ambush
  rescue CONVOY_ID               Supply a stranded convoy, resume journey
  skirmish CONVOY_ID             Start playable convoy rescue battle
  rescue-act CONVOY_ID JSON      Execute one tactical rescue command
  abandon CONVOY_ID              Lose stranded convoy / withdraw from rescue
  evacuate CONVOY_ID             Save people, forfeit cargo
  salvage CONVOY_ID              Partial recovery after defeating a raider
  negotiate CONVOY_ID            Pay ransom mid-skirmish, keep cargo
  pursue CONVOY_ID               Chase fleeing raiders for lost cargo
  pursuit-act CONVOY_ID JSON     Play pursuit using normal Battle commands
  giveup-pursuit CONVOY_ID       Stop pursuing, lose remaining loot
  tactical JSON                  Execute one normal Battle command
  save PATH                      Atomic JSON checkpoint with verified replay
  load PATH                      Verify and resume a multi-front recording
  help / quit
"""


def dashboard(session, *, event_count=8):
    require(type(event_count) is int and event_count >= 0,
            "Invalid event display count")
    clock = session.timeline
    lines = [f"STRATEGIC COMMAND  | turn {clock.turn} | focus: {clock.focused}",
             "FRONTS  [name | doctrine | players : defenders | outcome]"]
    for name, front in sorted(clock.fronts.items()):
        marker = ">" if name == clock.focused else " "
        lines.append(
            f"{marker} {name:12} {front['doctrine']:8} "
            f"{front['strength']:4} : {front['opposition']:<4} {front['status']}"
        )
    if session.logistics is not None:
        logistics = session.logistics
        resources = "  ".join(f"{k}={v}" for k, v in sorted(logistics.reserves.items()))
        lines.append(f"RESERVES  {resources} | escorts={logistics.escorts}"
                     f" | free transport={logistics.capacity - sum(len(x['actors']) for x in logistics.in_transit)}")
        if logistics.supplies is not None:
            lines.append("SUPPLIES  " + "  ".join(
                f"{team}={amount}" for team, amount in sorted(logistics.supplies.items())))
        lines.append("CONVOYS  [id | origin -> destination | troops | ETA | status]")
        for convoy in logistics.in_transit:
            remaining = max(0, convoy["arrival"] - clock.turn)
            status = "RESCUE NEEDED" if convoy.get("stranded") else (
                "ESCORTED" if convoy.get("escorted") else "EN ROUTE")
            lines.append(
                f"  {convoy['id']}  {convoy['from']} -> {convoy['to']} "
                f"| {len(convoy['actors'])} | {remaining} turn(s) | {status}"
            )
        if not logistics.in_transit:
            lines.append("  none")
    if session.rescue_battles:
        lines.append("RESCUE BATTLES  [convoy | active unit | cart HP]")
        for cid, battle in sorted(session.rescue_battles.items()):
            cart = battle.unit(battle.mission.protected_id)
            lines.append(f"  {cid} | {battle.active_id or 'none'} "
                         f"| {cart.hp}/{cart.max_hp}")
    if session.rescue_outcomes:
        lines.append("RESCUE RESULTS  " + ", ".join(
            f"{cid}={outcome}" for cid, outcome in sorted(session.rescue_outcomes.items())))
    if session.pursuit_targets:
        lines.append("RECOVERABLE LOOT  " + ", ".join(
            f"{cid}={row['loot']} supplies ({row['front']})"
            for cid, row in sorted(session.pursuit_targets.items())))
    if session.pursuit_battles:
        lines.append("PURSUIT BATTLES  " + ", ".join(
            f"{cid} active={battle.active_id or 'none'}"
            for cid, battle in sorted(session.pursuit_battles.items())))
    if session.pursuit_outcomes:
        lines.append("PURSUIT RESULTS  " + ", ".join(
            f"{cid}={result}" for cid, result in sorted(session.pursuit_outcomes.items())))
    if session.blocked_reinforcements:
        lines.append("INTERDICTED: " + ", ".join(sorted(session.blocked_reinforcements)))
    if event_count:
        lines.append("LAST STRATEGIC EVENTS")
        for event in clock.events[-event_count:]:
            details = ", ".join(f"{key}={value}" for key, value in event.items()
                                if key not in {"kind", "turn"})
            lines.append(f"  T{event['turn']}: {event['kind']} {details}".rstrip())
    return "\n".join(lines)


def _save(path, recording):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=destination.parent,
                prefix=".command-", suffix=".json", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(recording, stream, sort_keys=True, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def handle(session, line):
    """Parse one command and return (session, response, exit_requested).

    Invalid commands are rejected by the domain API, without partial writes.
    Caller should catch RuleError/ValueError/OSError for user-facing errors.
    """
    line = line.strip()
    if not line:
        return session, "", False
    if line.startswith("tactical "):
        command = json.loads(line.partition(" ")[2])
        session.execute(command)
        return session, "Tactical command accepted.", False
    if line.startswith(("rescue-act ", "pursuit-act ")):
        parts = line.split(" ", 2)
        require(len(parts) == 3, "Expected side-battle CONVOY_ID JSON")
        if parts[0] == "rescue-act":
            session.execute_rescue(parts[1], json.loads(parts[2]))
        else:
            session.execute_pursuit(parts[1], json.loads(parts[2]))
        return session, dashboard(session), False
    # Filesystem paths are not shell arguments. In particular shlex's POSIX
    # mode would strip Windows backslashes (e.g. C:\\Users\\...).
    if line.startswith(("save ", "load ")):
        action, raw_path = line.split(" ", 1)
        raw_path = raw_path.strip()
        require(bool(raw_path), "Missing checkpoint filename")
        if raw_path.startswith('"'):
            try:
                filename = json.loads(raw_path)
            except json.JSONDecodeError:
                filename = raw_path.strip('"')
        else:
            filename = raw_path.strip("'")
        require(isinstance(filename, str) and bool(filename),
                "Invalid checkpoint filename")
        if action == "save":
            recording = session.recording()
            require(MultiFrontSession.replay(recording, rules=session.rules).digest()
                    == session.digest(), "Replay verification failed")
            _save(filename, recording)
            return session, "Verified checkpoint saved.", False
        recording = json.loads(Path(filename).read_text(encoding="utf-8"))
        restored = MultiFrontSession.replay(recording, rules=session.rules)
        return restored, dashboard(restored), False
    args = shlex.split(line)
    action, fields = args[0], args[1:]
    if action == "quit" and not fields:
        return session, "", True
    if action == "help" and not fields:
        return session, HELP, False
    if action == "status" and not fields:
        return session, dashboard(session), False
    if action == "focus" and len(fields) == 1:
        session.switch(fields[0])
        return session, dashboard(session), False
    if action == "doctrine" and len(fields) == 2:
        session.set_doctrine(*fields)
        return session, dashboard(session), False
    if action == "turn" and len(fields) <= 1:
        count = int(fields[0]) if fields else 1
        require(1 <= count <= 20, "Advance between 1 and 20 turns")
        for _ in range(count):
            session.advance()
        return session, dashboard(session), False
    if action in {"reserve", "transfer"} and len(fields) == 4:
        front, uid, x, y = fields
        position = [int(x), int(y)]
        if action == "reserve":
            convoy = session.send_reserves(front, [
                {"id": uid, "name": uid, "team": "player", "pos": position}])
        else:
            convoy = session.transfer_units(front, {uid: position})
        return session, f"Ordered {convoy} to {front}.", False
    if action in {"escort", "rescue", "skirmish", "abandon",
                  "evacuate", "salvage", "negotiate", "pursue",
                  "giveup-pursuit"} and len(fields) == 1:
        if action == "escort":
            session.escort_convoy(fields[0])
        elif action == "rescue":
            session.rescue_convoy(fields[0])
        elif action == "skirmish":
            session.start_rescue(fields[0])
        elif action == "abandon":
            session.abandon_convoy(fields[0])
        elif action == "evacuate":
            session.evacuate_convoy(fields[0])
        elif action == "salvage":
            session.salvage_convoy(fields[0])
        elif action == "negotiate":
            session.negotiate_convoy(fields[0])
        elif action == "pursue":
            session.start_pursuit(fields[0])
        else:
            session.abandon_pursuit(fields[0])
        return session, dashboard(session), False
    raise RuleError("Unknown command or arguments. Type 'help'.")


def run(session, *, input_fn=input, output_fn=print):
    output_fn(dashboard(session))
    while True:
        try:
            session, response, done = handle(session, input_fn("command> "))
            if response:
                output_fn(response)
            if done:
                return session
        except EOFError:
            return session
        except (RuleError, ValueError, OSError, TypeError) as error:
            output_fn(f"Rejected: {error}")
