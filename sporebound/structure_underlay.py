"""Restore exact sparse terrain beneath authored structures (Content v1).

New instances optionally store an underlay snapshot; old documents without it
retain the historical erase-on-remove behavior. The snapshot lives with the
visual identity and is NOT a second tactical terrain layer.
"""
from copy import deepcopy

from .model import require


def capture_underlay(mission, cells):
    """Snapshot the terrain under a future structure, including absent tiles."""
    tiles = {tuple(row['pos']): row for row in mission['board']['tiles']}
    return [
        {'pos': list(cell),
         'tile': deepcopy({key: value for key, value in tiles[cell].items()
                           if key != 'pos'}) if cell in tiles else None}
        for cell in sorted(cells, key=lambda c: (c[1], c[0]))
    ]


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
