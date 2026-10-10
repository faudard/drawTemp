"""Visual, transaction-safe combinator editing for narrative choice predicates.

This module manipulates the existing GameProject.story condition schema:
all/any/not, flag comparisons, completed_mission and gold_gte. UI paths
address a position within a single choice, not persistent scene identities.
"""
from copy import deepcopy

from .model import RuleError, require
from .narrative import _condition, matches
from .story_graph import condition_label


def typed_value(text):
    """Authoring conversion for booleans, decimal integers and literal strings."""
    require(isinstance(text, str), 'Condition value must be text')
    stripped = text.strip()
    if stripped.lower() == 'true':
        return True
    if stripped.lower() == 'false':
        return False
    if stripped and (stripped.isdecimal() or
                     stripped[0] == '-' and stripped[1:].isdecimal()):
        return int(stripped)
    return text


def predicate(kind, name='', value='', *, content=None):
    """Construct a leaf predicate without requiring hand-written JSON."""
    if kind == 'flag_eq':
        result = {'flag': name.strip(), 'eq': typed_value(value)}
    elif kind in ('flag_gte', 'flag_lte'):
        converted = typed_value(value)
        require(type(converted) is int, 'Flag comparison requires an integer')
        result = {'flag': name.strip(),
                  'gte' if kind == 'flag_gte' else 'lte': converted}
    elif kind == 'completed_mission':
        result = {'completed_mission': name.strip()}
    elif kind == 'gold_gte':
        converted = typed_value(value)
        require(type(converted) is int, 'Gold comparison requires an integer')
        result = {'gold_gte': converted}
    else:
        raise RuleError('Unknown condition preset')
    if content is not None:
        _condition(result, content)
    return result


def _path(path):
    require(isinstance(path, (tuple, list)), 'Invalid condition path')
    require(len(path) <= 16, 'Condition path too long')
    for token in path:
        require(token == 'not' or
                (isinstance(token, (tuple, list)) and len(token) == 2
                 and token[0] in ('all', 'any')
                 and type(token[1]) is int and token[1] >= 0),
                'Invalid condition path')
    return tuple(path)


def _find(root, path):
    current = root
    for token in _path(path):
        require(isinstance(current, dict), 'Condition path points outside the tree')
        if token == 'not':
            require('not' in current, 'Missing NOT predicate')
            current = current['not']
        else:
            kind, index = token
            require(kind in current and isinstance(current[kind], list) and
                    index < len(current[kind]), 'Unknown condition path')
            current = current[kind][index]
    return current


def _parent(root, path):
    path = _path(path)
    require(path, 'Cannot delete or replace the root through its parent')
    return _find(root, path[:-1]), path[-1]


def _write(parent, token, value):
    if token == 'not':
        parent['not'] = value
    else:
        parent[token[0]][token[1]] = value


def rows(expression):
    """Stable depth-first rows for a Treeview; no mutation of the predicate."""
    if expression is None:
        return []
    result = []

    def walk(node, path, depth):
        require(isinstance(node, dict), 'Malformed condition tree')
        result.append({'path': path, 'depth': depth, 'label': condition_label(node),
                       'kind': next(iter(node), ''), 'expression': deepcopy(node)})
        if 'all' in node or 'any' in node:
            kind = 'all' if 'all' in node else 'any'
            for i, child in enumerate(node[kind]):
                walk(child, path+((kind, i),), depth+1)
        elif 'not' in node:
            walk(node['not'], path+('not',), depth+1)
    walk(expression, (), 0)
    return result


def update_expression(expression, action, *, path=(), leaf=None, operator='all'):
    """Return a new root. UI calls GameProject validation before committing.

    replace: swap a chosen node (or create a new unconditional root)
    append:  add a leaf inside the selected AND/OR group
    wrap:    surround a node with AND, OR, or NOT
    delete:  remove a child; delete on root means unconditional
    """
    require(action in ('replace', 'append', 'wrap', 'delete'),
            'Unknown condition operation')
    path = _path(path)
    require(operator in ('all', 'any', 'not'), 'Unknown boolean operator')
    updated = deepcopy(expression)
    if action == 'replace':
        require(isinstance(leaf, dict), 'Select a predicate to insert')
        if not path:
            return deepcopy(leaf)
        parent, token = _parent(updated, path)
        _write(parent, token, deepcopy(leaf))
    elif action == 'append':
        require(isinstance(leaf, dict), 'Select a predicate to insert')
        target = _find(updated, path) if updated is not None else None
        require(isinstance(target, dict) and
                ('all' in target or 'any' in target),
                'Choose an AND/OR group to add a predicate')
        kind = 'all' if 'all' in target else 'any'
        require(len(target[kind]) < 20, 'A group may contain at most 20 conditions')
        target[kind].append(deepcopy(leaf))
    elif action == 'wrap':
        target = _find(updated, path) if updated is not None else None
        require(isinstance(target, dict), 'Choose a predicate to wrap')
        wrapper = ({'not': deepcopy(target)} if operator == 'not'
                   else {operator: [deepcopy(target)]})
        if not path:
            return wrapper
        parent, token = _parent(updated, path)
        _write(parent, token, wrapper)
    else:
        require(updated is not None, 'No condition to delete')
        if not path:
            return None
        parent, token = _parent(updated, path)
        require(token != 'not', 'Remove the whole NOT group or replace its child')
        items = parent[token[0]]
        require(len(items) > 1, 'Cannot leave an AND/OR group empty')
        items.pop(token[1])
    return updated


def change_choice(project, content, scene_id, choice_id, expression):
    """One fully validated GameProject mutation; reject loss of fallback."""
    from .story_authoring import update_choice
    if expression is not None:
        _condition(expression, content)
    return update_choice(project, content, scene_id, choice_id,
                         when=expression, clear_condition=expression is None)


def evaluate(expression, *, flags=None, gold=0, completed=()):
    """Simulate visibility without touching an active save slot."""
    from types import SimpleNamespace
    require(isinstance(flags, dict) and
            all(isinstance(k, str) and type(v) in (bool, int, str)
                for k, v in flags.items()) if flags is not None else True,
            'Invalid preview flags')
    require(type(gold) is int and 0 <= gold <= 1000000,
            'Invalid preview gold')
    require(isinstance(completed, (list, tuple, set)) and
            all(isinstance(k, str) for k in completed), 'Invalid preview missions')
    return True if expression is None else matches(
        expression, SimpleNamespace(story_flags=flags or {}, gold=gold,
                                    completed=list(completed)))
