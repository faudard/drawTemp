"""Explicit actor lifecycle operations, invoked inside Battle transactions."""
from .actors import ActorFactory, validate_actor
from .model import require


def _fallback_cells(battle, origin):
    """Stable nearest-cell order: distance, y, x."""
    return sorted(
        (cell for cell in battle.board.cells()
         if not battle.board.tile(cell).blocked
         and not any(u.alive and u.pos == cell for u in battle.units)),
        key=lambda cell: (abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]), cell[1], cell[0]),
    )


def spawn(battle, definition):
    """Create a validated actor without touching the initiative clock or RNG."""
    require(isinstance(definition, dict), 'Spawn must be an object')
    spawn_spec = dict(definition)
    fallback_nearest = bool(spawn_spec.pop('fallback_nearest', False))
    actor = ActorFactory(battle.content.archetypes).create(spawn_spec)
    require(not any(u.id == actor.id for u in battle.units), f'Duplicate actor: {actor.id}')
    require(battle.board.contains(actor.pos), f'Outside board: {actor.pos}')
    occupied = any(u.alive and u.pos == actor.pos for u in battle.units)
    blocked = battle.board.tile(actor.pos).blocked
    if (occupied or blocked) and fallback_nearest:
        cells = _fallback_cells(battle, actor.pos)
        require(bool(cells), 'No free spawn cell')
        actor.pos = cells[0]
    else:
        require(not blocked, f'Blocked spawn: {actor.pos}')
        require(not occupied, f'Occupied spawn: {actor.pos}')
    validate_actor(actor, battle.content.skills, battle.content.archetypes, battle.rules)
    battle.units.append(actor)
    battle.emit('actor_spawned', unit=actor.id, actor_kind=actor.kind, team=actor.team)
    battle._collect(actor)
    return actor


def despawn(battle, actor_id):
    """Remove an actor and its transient reaction state."""
    actor = next((u for u in battle.units if u.id == actor_id), None)
    require(actor is not None, f'Unknown actor: {actor_id}')
    require(actor_id != battle.mission.protected_id, 'Cannot despawn protected actor')
    battle.prepared_reactions.pop(actor_id, None)
    if battle.carrier == actor_id:
        battle.carrier = None
        battle.relic_pos = actor.pos
        battle.emit('relic_dropped', unit=actor_id, pos=actor.pos)
    battle.units.remove(actor)
    if battle.active_id == actor_id:
        battle.active_id = None
    battle.emit('actor_despawned', unit=actor_id)
    return actor
