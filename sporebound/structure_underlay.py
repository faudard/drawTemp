"""Restore exact sparse terrain beneath authored structures (Content v1).

New instances optionally store an underlay snapshot; old documents without it
retain the historical erase-on-remove behavior. The snapshot lives with the
visual identity and is NOT a second tactical terrain layer.
"""
from copy import deepcopy
from dataclasses import asdict

from .model import Tile, require


def capture_underlay(mission, cells):
    """Snapshot the terrain under a future structure, including absent tiles."""
    tiles = {tuple(row['pos']): row for row in mission['board']['tiles']}
    result = []
    for cell in sorted(cells, key=lambda c: (c[1], c[0])):
        raw = tiles.get(cell)
        # Canonicalize partial tile input (including defaults) to the same
        # contract emitted by Content.to_dict and validated on reload.
        payload = None if raw is None else asdict(Tile(**{
            key: deepcopy(value) for key, value in raw.items() if key != 'pos'}))
        result.append({'pos': list(cell), 'tile': payload})
    return result


def restore_footprint(mission, instance):
    """Detach one identity and restore its prior ground in a mission copy.

    The current structure/painted tiles disappear. On legacy records, no
    historical ground exists and the original erase behavior is retained.
    """
    record = next((row for row in mission.get('structures', ())
                   if row['id'] == instance.id), None) if instance.id else None
    mission['structures'] = [row for row in mission.get('structures', ())
                             if row['id'] != instance.id] if instance.id else list(
                                 mission.get('structures', ()))
    occupied = set(instance.cells)
    retained = [row for row in mission['board']['tiles']
                if tuple(row['pos']) not in occupied]
    if record is not None and 'underlay' in record:
        snapshot = record['underlay']
        require({tuple(entry['pos']) for entry in snapshot} == occupied,
                'Structure underlay footprint mismatch')
        for entry in snapshot:
            if entry['tile'] is not None:
                retained.append({'pos': list(entry['pos']), **deepcopy(entry['tile'])})
    mission['board']['tiles'] = retained
