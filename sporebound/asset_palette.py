"""Presentation adapter over the existing iso tools, not a second asset registry.

No Tk/Pillow import: catalog queries also work in headless validation tools.
"""
from dataclasses import dataclass
import unicodedata

from .iso_map import ATLAS_MATERIALS
from .iso_props import PROP_NAMES
from .iso_structures import STRUCTURE_NAMES, structure_template


@dataclass(frozen=True)
class PaletteEntry:
    id: str
    name: str
    category: str
    kind: str
    value: str

    def footprint(self, turns=0):
        if self.kind == 'structure':
            clip = structure_template(self.value, turns)
            return clip.width, clip.height
        return 1, 1

    @property
    def effect(self):
        if self.kind == 'structure':
            return 'Tampon de terrain : remplace sols, décors, blocages et hauteurs.'
        if self.kind == 'surface':
            return ('Pinceau existant : l’eau bloque ; pont ou remplacement d’eau '
                    'libère la case, sauf mur de pierre conservé.')
        return ('Pinceau existant : le mur de pierre bloque ; le remplacer '
                'libère la case sauf sur l’eau.')


_LABELS = dict(zip(ATLAS_MATERIALS,
                   ('Herbe', 'Terre / chemin', 'Pierre', 'Pavés', 'Sable',
                    'Roche', 'Eau / rivière', 'Plancher de pont')))
_PROP_LABELS = dict(zip(PROP_NAMES,
                        ('Arbre', 'Buisson', 'Rocher', 'Ruine', 'Caisse',
                         'Lanterne', 'Marches décoratives', 'Mur de pierre',
                         'Arche', 'Clôture', 'Roseaux', 'Pilier')))
ENTRIES = tuple(
    [PaletteEntry('surface:'+s, _LABELS[s], 'Sols', 'surface', s)
     for s in ATLAS_MATERIALS]
    + [PaletteEntry('feature:'+s, _PROP_LABELS[s],
                    'Végétation' if s in ('tree', 'bush', 'reeds') else 'Décors',
                    'feature', s) for s in PROP_NAMES]
    + [PaletteEntry('structure:'+s, s, 'Structures', 'structure', s)
       for s in STRUCTURE_NAMES])
CATEGORIES = ('Tous', 'Sols', 'Végétation', 'Décors', 'Structures')


def _normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if unicodedata.category(c) != 'Mn')


def search_entries(query='', category='Tous'):
    terms = _normalized(query).split()
    return tuple(e for e in ENTRIES
                 if (category == 'Tous' or e.category == category)
                 and all(term in _normalized(' '.join((e.id, e.name, e.category)))
                         for term in terms))
