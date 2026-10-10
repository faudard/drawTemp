"""Mission progression graph shared by the editor and future player UI.

Edges are the existing Mission.next_missions contract.  No parallel routing
format or implicit scenario progression is introduced.
"""
from collections import deque
from copy import deepcopy

from .model import Content, require


def _ids(content):
    return list(content.missions)


def inspect_graph(content, starts):
    """Deterministic reachability, cycles and layout for any valid content."""
    content.validate()
    ids = _ids(content)
    require(isinstance(starts, (list, tuple)) and bool(starts), 'Choose a starting mission')
    require(all(s in content.missions for s in starts), 'Unknown campaign starting mission')
    edges = {mid: list(dict.fromkeys(content.missions[mid].next_missions)) for mid in ids}
    depths = {}
    queue = deque()
    for start in starts:
        if start not in depths:
            depths[start] = 0
            queue.append(start)
    while queue:
        mid = queue.popleft()
        for successor in edges[mid]:
            if successor not in depths:
                depths[successor] = depths[mid] + 1
                queue.append(successor)
    unreachable = [mid for mid in ids if mid not in depths]

    # Depth-first search with an explicit stack, including genuine back-edges.
    color = {}
    active = []
    cycles = []
    for root in ids:
        if color.get(root):
            continue
        color[root] = 1
        active.append(root)
        frames = [(root, iter(edges[root]))]
        while frames:
            node, outgoing = frames[-1]
            successor = next(outgoing, None)
            if successor is None:
                frames.pop()
                active.pop()
                color[node] = 2
            elif color.get(successor) == 1:
                start = active.index(successor)
                path = active[start:] + [successor]
                if path not in cycles:
                    cycles.append(path)
            elif not color.get(successor):
                color[successor] = 1
                active.append(successor)
                frames.append((successor, iter(edges[successor])))

    # Put disconnected components to the right of the main campaign.
    disconnected_depth = (max(depths.values()) + 2) if depths else 0
    levels = {}
    for mid in ids:
        level = depths.get(mid, disconnected_depth)
        levels.setdefault(level, []).append(mid)
    positions = {}
    for depth, items in levels.items():
        for index, mid in enumerate(items):
            positions[mid] = (80 + 190 * depth, 70 + 105 * index)
    return {
        'starts': list(dict.fromkeys(starts)),
        'edges': [(mid, target) for mid in ids for target in edges[mid]],
        'reachable': [mid for mid in ids if mid in depths],
        'unreachable': unreachable,
        'terminal': [mid for mid in ids if not edges[mid]],
        'cycles': cycles,
        'positions': positions,
    }


def set_link(data, origin, target, enabled=True):
    """Change one link, preserving other branches and original mission order."""
    require(type(enabled) is bool, 'Enabled must be a boolean')
    new = deepcopy(data)
    by_id = {mission['id']: mission for mission in new['missions']}
    require(origin in by_id and target in by_id, 'Unknown mission in link')
    require(origin != target, 'A mission cannot unlock itself')
    outgoing = by_id[origin].setdefault('next_missions', [])
    if enabled and target not in outgoing:
        outgoing.append(target)
    elif not enabled:
        by_id[origin]['next_missions'] = [mid for mid in outgoing if mid != target]
    return Content.from_dict(new).to_dict()
