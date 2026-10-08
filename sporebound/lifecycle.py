"""Explicit actor lifecycle operations, invoked inside Battle transactions."""
from .actors import ActorFactory, validate_actor
from .model import require


def spawn(battle, definition):
    """Create a validated actor without touching the initiative clock or RNG."""
    require(isinstance(definition, dict), 'Spawn must be an object')
    actor = ActorFactory(battle.content.archetypes).create(definition)
    require(not any(u.id == actor.id for u in battle.units), f'Duplicate actor: {actor.id}')
    require(battle.board.contains(actor.pos), f'Outside board: {actor.pos}')
    require(not battle.board.tile(actor.pos).blocked, f'Blocked spawn: {actor.pos}')
    require(not any(u.alive and u.pos == actor.pos for u in battle.units), f'Occupied spawn: {actor.pos}')
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
