"""Visual prefab catalogue metadata and deterministic, headless thumbnail layout.

The renderer uses ordinary Tk Canvas primitives at runtime. This module has
no Tk dependency; the category/filter/layout contract is unit-testable.
Existing version-1 JSON files are read unchanged.
"""
from dataclasses import dataclass
from pathlib import Path

CATEGORIES = ('Tous', 'Quartiers', 'Bâtiments', 'Fortifications',
              'Décors', 'Interactifs', 'Personnages')
MAX_THUMBNAIL_CELLS = 4096


@dataclass(frozen=True)
class PrefabCard:
    filename: str
    name: str
    category: str
    width: int
    height: int
    groups: int
    structures: int
    actors: int
    objects: int
    thumbnail: tuple
    error: str = ''


def prefab_category(prefab):
    """One predictable category per prefab, with no new manifest field."""
    structures = prefab['structures']
    actors = prefab['units']
    objects = prefab['objects']
    tiles = prefab['tiles']
    groups = prefab['groups']
    names = {str(s.get('name', '')).casefold() for s in structures}
    if len(structures) > 1 or len(groups) > 2 and structures:
        return 'Quartiers'
    if names & {'rempart', 'mur', 'porte', 'pont', 'tour',
                'herse', 'fortification', 'bastion', 'château'}:
        return 'Fortifications'
    if structures:
        return 'Bâtiments'
    if objects:
        return 'Interactifs'
    if actors:
        return 'Personnages'
    if tiles:
        return 'Décors'
    return 'Quartiers'


def _cell_color(tile):
    if tile is None:
        return '#e8ebe9'
    surface = tile.get('surface', 'grass')
    feature = tile.get('feature', '')
    if feature in ('tree', 'bush', 'hedge'):
        return '#357856'
    if feature in ('wall', 'rock', 'boulder'):
        return '#747f8b'
    if feature in ('lantern', 'crate', 'chest'):
        return '#a77d50'
    return {
        'water': '#4f91c0', 'river': '#4f91c0',
        'stone': '#a4a9ac', 'cobble': '#b3a89d',
        'dirt': '#bfa27c', 'sand': '#dccb90',
        'grass': '#85b98a',
    }.get(surface, '#8eae91')


def thumbnail_model(prefab):
    """Z-ordered local grid symbols, capped for very large authoring groups."""
    from .iso_structures import structure_template, structure_footprint

    cells = {}
    for row in prefab['tiles'][:MAX_THUMBNAIL_CELLS]:
        cells[tuple(row['pos'])] = _cell_color(row['tile'])
    for structure in prefab['structures']:
        clip = structure_template(
            structure['name'], structure['turns'],
            door_slot=structure['door_slot'])
        for x, y in structure_footprint(clip, structure['anchor']):
            cells[(x, y)] = '#7c689a'
    for obj in prefab['objects']:
        cells[tuple(obj['pos'])] = '#e0a74b'
    for actor in prefab['units']:
        cells[tuple(actor['pos'])] = '#357db5'
    return tuple((x, y, color) for (x, y), color in sorted(
        cells.items(), key=lambda a: (a[0][1], a[0][0]))[:MAX_THUMBNAIL_CELLS])


def prefab_card(path, prefab):
    """Display metadata; content was validated by load_group_prefab."""
    width, height = prefab['size']
    return PrefabCard(
        Path(path).name, prefab['name'], prefab_category(prefab),
        width, height, len(prefab['groups']),
        len(prefab['structures']), len(prefab['units']),
        len(prefab['objects']), thumbnail_model(prefab))


def broken_prefab_card(path, message):
    return PrefabCard(
        Path(path).name, Path(path).stem, 'Invalide', 0, 0,
        0, 0, 0, 0, (), str(message))


def filter_prefab_cards(cards, search='', category='Tous'):
    term = search.strip().casefold()
    if category not in CATEGORIES:
        return ()
    return tuple(c for c in cards if
                 (category == 'Tous' or c.category == category)
                 and (not term or term in
                      (c.name+' '+c.filename+' '+c.category).casefold()))


def thumbnail_rectangles(card, width=160, height=85, pad=7):
    """Pixels within an image card; stay deterministic across Tk/DPR."""
    if not card.width or not card.height:
        return ()
    size = min((width - 2*pad) / card.width,
               (height - 2*pad) / card.height)
    size = max(size, 0.1)
    ox = (width - card.width * size) / 2
    oy = (height - card.height * size) / 2
    return tuple((ox+x*size, oy+y*size,
                  ox+(x+1)*size, oy+(y+1)*size, color)
                 for x, y, color in card.thumbnail)
