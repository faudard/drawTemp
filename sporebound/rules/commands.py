"""Command adapters; Battle owns the transaction and turn lifecycle."""
from ..model import require
from .registry import CommandRule, Registry


def cell(command):
    raw = command['cell']
    require(isinstance(raw, (list, tuple)) and len(raw) == 2
            and all(type(v) is int for v in raw), 'Invalid cell')
    return tuple(raw)


def default_commands():
    handlers = {
        'move': lambda b, u, c: b._move(u, cell(c)),
        'act': lambda b, u, c: b._act(u, c['skill'], cell(c)),
        'item': lambda b, u, c: b._item(u, c['item'], cell(c)),
        'charge': lambda b, u, c: b._charge(u, cell(c)),
        'relay': lambda b, u, c: b._relay(u, c['partner'], cell(c)),
        'disengage': lambda b, u, c: b._disengage(u),
        'interact': lambda b, u, c: b._interact(u, c['object']),
        'siege_attack': lambda b, u, c: b._siege_attack(u, c['object']),
        'repair_siege': lambda b, u, c: b._repair_siege(u, c['object']),
        'prepare': lambda b, u, c: b._prepare(u, c['mode'], c.get('target')),
        'end': lambda b, u, c: b._end(u, tuple(c.get('facing', u.facing))),
    }
    return Registry(tuple((key, CommandRule(handler)) for key, handler in handlers.items()))

