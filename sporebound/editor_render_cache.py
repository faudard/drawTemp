"""Retained Canvas commands for the Studio's shared isometric renderer.

The normal renderer remains the source of drawing/occlusion rules. Replaying its
commands through this adapter avoids Tcl calls for unchanged items; no document
revision assumptions are required (Studio panels can edit dictionaries in place).
"""
from hashlib import blake2b
from time import perf_counter

from .iso_map import IsoGeometry, render_isometric


class EditorRenderCache:
    def __init__(self, canvas, *, max_retained_cells=4096):
        self.canvas = canvas
        self.max_retained_cells = max_retained_cells
        self.geometry = None
        self._geometry_key = None
        self._items = {}
        self._order = ()
        self._raises = ()
        self._region = None
        self.stats = {}
        self._owns_canvas = False
        self._large_signature = None
        self._large_selection = None
        self._large_selected_tiles = frozenset()
        self._large_item_count = None

    def invalidate(self):
        """Call when another renderer takes ownership of the Canvas."""
        self.canvas.delete('all')
        self._owns_canvas = False
        self._items.clear()
        self._order = ()
        self._raises = ()
        self._region = None
        self.geometry = None
        self._geometry_key = None
        self._large_signature = None
        self._large_selection = None
        self._large_selected_tiles = frozenset()
        self._large_item_count = None

    def begin_group(self, group):
        self._group = group
        self._counts = {}

    def _create(self, kind, coords, options):
        tags = options.get('tags', ())
        tags = (tags,) if isinstance(tags, str) else tuple(tags)
        category = kind, tags
        ordinal = self._counts.get(category, 0)
        self._counts[category] = ordinal + 1
        key = self._group, category, ordinal
        self._commands[key] = (kind, coords, options)

    def create_polygon(self, *coords, **options):
        self._create('polygon', coords, options)

    def create_line(self, *coords, **options):
        self._create('line', coords, options)

    def create_image(self, *coords, **options):
        self._create('image', coords, options)

    def create_rectangle(self, *coords, **options):
        self._create('rectangle', coords, options)

    def create_oval(self, *coords, **options):
        self._create('oval', coords, options)

    def create_text(self, *coords, **options):
        self._create('text', coords, options)

    def tag_raise(self, *args):
        self._pending_raises.append(args)

    def configure(self, *, scrollregion):
        self._pending_region = scrollregion

    def _commit(self):
        created = updated = deleted = 0
        for key in self._items.keys() - self._commands.keys():
            self.canvas.delete(self._items.pop(key)[0])
            deleted += 1
        for key, command in self._commands.items():
            old = self._items.get(key)
            kind, coords, options = command
            if old is None:
                item = getattr(self.canvas, 'create_' + kind)(*coords, **options)
                created += 1
            else:
                item, previous = old
                if previous != command:
                    # Reset options removed by a drawing branch by recreating
                    # that item. Tk defaults differ between item types.
                    if previous[2].keys() != options.keys():
                        self.canvas.delete(item)
                        item = getattr(self.canvas, 'create_' + kind)(*coords, **options)
                        created += 1
                        deleted += 1
                    else:
                        if previous[1] != coords:
                            self.canvas.coords(item, *coords)
                        changes = {k: v for k, v in options.items()
                                   if previous[2][k] != v}
                        if changes:
                            self.canvas.itemconfigure(item, **changes)
                        updated += 1
            self._items[key] = item, command
        order = tuple(self._commands)
        raises = tuple(self._pending_raises)
        if order != self._order or created or raises != self._raises:
            for key in order:
                self.canvas.tag_raise(self._items[key][0])
        if order != self._order or created or raises != self._raises:
            for args in raises:
                self.canvas.tag_raise(*args)
        if self._region != self._pending_region:
            self.canvas.configure(scrollregion=self._pending_region)
        self._region = self._pending_region
        self._order, self._raises = order, raises
        self.stats.update(created=created, updated=updated, deleted=deleted,
                          items=len(self._items))

    @staticmethod
    def _large_scene_signature(board, mission, units, options):
        """Snapshot *values*, never model identities (Studio rebuilds Content).

        Both the authored board and live units can be edited in-place. The
        display signature includes all non-selection inputs to the renderer,
        including layer flags, threats, sprite poses and atlas identities.
        Only the two selection overlays may be updated independently.
        """
        visual_options = tuple((name, repr(value))
                               for name, value in sorted(options.items())
                               if name not in ('selected_cell', 'selected_tiles'))
        state = repr((board, mission, units, visual_options))
        return blake2b(state.encode('utf-8'), digest_size=16).digest()

    def _large_selection_safe(self, before, after):
        """Changing roof cutaway requires a complete depth/occlusion pass."""
        return not any((before in building.cells) != (after in building.cells)
                       for building in getattr(self.geometry,
                                               'architecture_instances', ()))

    def _draw_large_selection(self, selected_cell, selected_tiles):
        """Replace only the two selection contours, respecting painter order.

        The normal renderer always raises the 'selection' tag above roofs and
        actors. Recreating these final overlays is equivalent whenever the
        authored scene and architectural cutaway state have not changed.
        """
        self.canvas.delete('selection')
        count = 0
        for cell in self.geometry.draw_order:
            if cell not in selected_tiles and cell != selected_cell:
                continue
            corners = tuple(value for point in self.geometry.polygon(cell)
                            for value in point)
            if cell in selected_tiles:
                self.canvas.create_polygon(*corners, outline='#23689e',
                                           fill='', width=3, tags='selection')
                count += 1
            if cell == selected_cell:
                self.canvas.create_polygon(*corners, outline='#2361ff',
                                           fill='', width=3, tags='selection')
                count += 1
        self.canvas.tag_raise('selection')
        return count

    def draw(self, board, mission, units, **options):
        start = perf_counter()
        if not self._owns_canvas:
            self.canvas.delete('all')
            self._owns_canvas = True
        key = (board.width, board.height, options['cell_size'],
               tuple(sorted((pos, tile.height) for pos, tile in board.tiles.items()
                            if tile.height)))
        rebuilt = key != self._geometry_key
        if rebuilt:
            self.geometry = IsoGeometry(board, options['cell_size'])
            self._geometry_key = key
        else:
            # Content.from_dict produces fresh models on every Studio refresh.
            self.geometry.board = board
        if board.width * board.height > self.max_retained_cells:
            # Full retained command diffing is too expensive at 128². Skip
            # genuinely unchanged scenes and redraw just selection contours
            # when roof cutaway is unaffected. Everything else is a full pass.
            self._items.clear()
            self._order = self._raises = ()
            self._region = None
            signature = self._large_scene_signature(board, mission, units, options)
            selected_cell = options['selected_cell']
            selected_tiles = frozenset(options['selected_tiles'])
            reusable = (not rebuilt and self.stats.get('mode') == 'geometry'
                        and signature == self._large_signature
                        and hasattr(self.canvas, 'find_all')
                        and self._large_item_count == len(self.canvas.find_all()))
            if reusable:
                if (selected_cell == self._large_selection
                        and selected_tiles == self._large_selected_tiles):
                    self.stats = dict(mode='geometry', fast_path='noop',
                                      geometry_rebuilt=False, created=0,
                                      updated=0, deleted=0,
                                      items=self._large_item_count,
                                      render_ms=(perf_counter() - start) * 1000)
                    return self.geometry
                if self._large_selection_safe(self._large_selection, selected_cell):
                    try:
                        count = self._draw_large_selection(selected_cell,
                                                           selected_tiles)
                        self._large_selection = selected_cell
                        self._large_selected_tiles = selected_tiles
                        self._large_item_count = len(self.canvas.find_all())
                    except Exception:
                        self.invalidate()
                        raise
                    self.stats = dict(mode='geometry', fast_path='selection',
                                      geometry_rebuilt=False, created=count,
                                      updated=0, deleted=None,
                                      items=self._large_item_count,
                                      render_ms=(perf_counter() - start) * 1000)
                    return self.geometry
            try:
                render_isometric(self.canvas, board, mission, units,
                                 geometry=self.geometry, **options)
            except Exception:
                self.invalidate()
                raise
            self._large_signature = signature
            self._large_selection = selected_cell
            self._large_selected_tiles = selected_tiles
            self._large_item_count = (len(self.canvas.find_all())
                                      if hasattr(self.canvas, 'find_all') else None)
            self.stats = dict(mode='geometry', fast_path='full',
                              geometry_rebuilt=rebuilt, created=None,
                              updated=0, deleted=None, items=self._large_item_count,
                              render_ms=(perf_counter() - start) * 1000)
            return self.geometry
        if self.stats.get('mode') == 'geometry':
            self.canvas.delete('all')
        self._large_signature = None
        self._large_item_count = None
        self._commands = {}
        self._pending_raises = []
        self.begin_group('scene')
        try:
            render_isometric(self, board, mission, units,
                             geometry=self.geometry, retained=True, **options)
            self._commit()
        except Exception:
            self.invalidate()
            raise
        finally:
            # Keep only the committed display list, never accumulate frames.
            self._commands = {}
        self.stats.update(mode='retained', geometry_rebuilt=rebuilt,
                          render_ms=(perf_counter() - start) * 1000)
        return self.geometry
