"""Own mission editor and tactical playtest UI. Tk is imported only by launch()."""
from itertools import islice
from copy import deepcopy
import json
from pathlib import Path

from .editor_render_cache import EditorRenderCache
from .editor_refresh_scale import EditorContentProjection, MinimapBackgroundCache
from .editor_architecture import (EditingContext, EditorChange, StructureCommand,
                                  StructureGroupCommand, EditorGroupMoveCommand,
                                  EditorGroupTreeDropCommand, EditorGroupBatchCommand,
                                  GroupPrefabPlaceCommand,
                                  EntityCommand,
                                  RENDERER, MINIMAP, INSPECTOR, WORKSPACE)
from .ai import play_activation
from .engine import Battle
from .model import Content, RuleError
from .map_authoring import (cells_in_rectangle, copy_terrain, move_object,
                            move_unit, paint_deployment, paste_terrain,
                            selected_cells as validate_selection)
from .map_transform import (group_entities, load_stamp, move_group, save_stamp,
                            transform_terrain)
from .map_builder4 import smart_brush_cells, surface_region
from .presentation import battle_frame
from .iso_map import (FEATURES, SURFACES, IsoGeometry, _flatten,
                      _line_cells, SURFACE_COLORS, IsoTerrainAtlas)
from .iso_props import IsoPropAtlas
from .iso_object_atlas import IsoObjectAtlas
from .interior_levels import (FLOOR_SURFACES, FLOOR_FEATURES, MAX_INTERIOR_LEVEL,
                              add_interior_floor, delete_interior_floor,
                              edit_interior_tile, floor_hit_test,
                              projected_floor_polygon)
from .level_navigation import add_level_link, place_unit_on_level
from .iso_building_atlas import IsoBuildingAtlas
from .iso_fortification_atlas import IsoFortificationAtlas
from .iso_actor_atlas import IsoActorAtlas
from .entity_placement import (palette_entities, place_palette_entity,
                               preview_entity_cells)
from .entity_editing import (edit_entity, relocate_entity, duplicate_entity,
                             remove_entity, entities_at)
from .iso_structures import (STRUCTURE_NAMES, door_slots, structure_template,
                             structure_footprint, validate_structure_placement,
                             place_structure, remove_structure, structure_at,
                             edit_structure, validate_structure_edit)
from .iso_architecture import (PIVOTS, ARCHITECTURE_NAMES, placement_origin,
                               preview_structure_sprite_position)
from .structure_groups import selected_structures, transform_structure_group
from .building_visuals import (FACADES, ROOFS, DEFAULT_APPEARANCE,
                               building_appearance, exterior_wall_cells,
                               edit_building_appearance, set_building_window)
from .map_layer_workspace import (LAYERS as EDITOR_LAYERS, empty_views,
                                  load_views, save_views, view_for, update_view,
                                  ensure_unlocked)
from .editor_groups import (create_editor_group, add_selection_to_group,
                            remove_selection_from_group, transfer_selection_to_group,
                            rename_editor_group, reparent_editor_group,
                            delete_editor_group, descendant_groups,
                            group_display_cells, selected_group_roots,
                            check_tree_drop)
from .group_prefabs import (capture_group_prefab, load_group_prefab,
                            save_group_prefab, list_group_prefabs,
                            prefab_file_slug, prefab_display_cells)
from .group_prefab_transform import rotate_group_prefab
from .quarter_generator import (STYLES as QUARTER_STYLES, SIZES as QUARTER_SIZES,
                                suggest_quarters, preview_quarter)
from .prefab_catalog import prefab_card, broken_prefab_card
from .prefab_palette import VisualPrefabPalette
from .siege import available_operations
from .storage import load_battle, save_battle, write_json
from .tactical_rpg3 import authored_rules_for_document
from .studio_transaction import StudioTransactionStore
from .editor_reliability import EditRecoveryJournal
from .performance_trace import begin_ui, finish_ui
from .workspace_shell import inspect_map, LayoutStore, palette_source_for_tree
from .workspace_editing import WorkspacePropertyCommand, editable_form


class Document:
    """Validated edits with bounded undo history; playtests always use a copy."""
    def __init__(self, content: Content):
        self.data = content.to_dict()
        self.undo_stack = []
        self.redo_stack = []
        self.edit_policy = None  # Optional editor-only validation before commit.
        self.saved = json.dumps(self.data, sort_keys=True)

    @property
    def dirty(self):
        return json.dumps(self.data, sort_keys=True) != self.saved

    def replace(self, data):
        validated = Content.from_dict(
            data, rules=authored_rules_for_document(data)).to_dict()
        if self.edit_policy is not None:
            self.edit_policy(self.data, validated)
        self.undo_stack.append(deepcopy(self.data))
        self.undo_stack = self.undo_stack[-50:]
        self.redo_stack.clear()
        self.data = validated

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.data)
            self.data = self.undo_stack.pop()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.data)
            self.data = self.redo_stack.pop()

    def tile(self, mid, cell, brush):
        self.paint_many(mid, [cell], brush)

    def paint_many(self, mid, cells, brush):
        """A brush stroke is one validated, undoable change."""
        data = deepcopy(self.data)
        mission = next(m for m in data['missions'] if m['id'] == mid)
        width, height = mission['board']['width'], mission['board']['height']
        tiles = {tuple(t['pos']): t for t in mission['board']['tiles']}
        seen = set()
        for cell in cells:
            cell = tuple(cell)
            if cell in seen:
                continue
            seen.add(cell)
            if not (0 <= cell[0] < width and 0 <= cell[1] < height):
                raise RuleError(f'Case hors carte : {cell}')
            old = tiles.get(cell, {'pos': list(cell)})
            new = {**old}
            if brush == 'erase':
                new = {'pos': list(cell)}
                mission['goal'] = [goal for goal in mission.get('goal', [])
                                   if tuple(goal) != cell]
            elif brush == 'wall':
                new['blocked'] = True
            elif brush == 'height+':
                new['height'] = min(99, old.get('height', 0) + 1)
            elif brush == 'height-':
                new['height'] = max(0, old.get('height', 0) - 1)
            elif brush == 'mud':
                new['cost'] = 2
            elif brush == 'hazard':
                new['hazard'] = 4
            elif brush == 'cover':
                new['cover'] = 20
            elif brush.startswith('surface:'):
                surface = brush.partition(':')[2]
                if surface not in SURFACES:
                    raise RuleError('Surface inconnue')
                new['surface'] = surface
                if surface == 'water' or old.get('feature') == 'stone_wall':
                    new['blocked'] = True
                elif surface == 'bridge' or old.get('surface') == 'water':
                    new['blocked'] = False
            elif brush.startswith('feature:'):
                feature = brush.partition(':')[2]
                if feature not in FEATURES:
                    raise RuleError('Décor inconnu')
                new['feature'] = feature
                if feature == 'stone_wall':
                    new['blocked'] = True
                elif old.get('feature') == 'stone_wall':
                    new['blocked'] = old.get('surface') == 'water'
            elif brush == 'feature-erase':
                new['feature'] = ''
                if old.get('feature') == 'stone_wall':
                    new['blocked'] = old.get('surface') == 'water'
            elif brush.startswith('height:'):
                value = brush.partition(':')[2]
                if not value.isdigit() or not 0 <= int(value) <= 99:
                    raise RuleError('Hauteur attendue entre 0 et 99')
                new['height'] = int(value)
            elif brush == 'goal':
                goal = [list(c) for c in mission.get('goal', [])]
                if list(cell) not in goal:
                    goal.append(list(cell))
                mission['goal'] = goal
            else:
                raise RuleError('Unknown brush')
            tiles[cell] = new
        if seen:
            mission['board']['tiles'] = list(tiles.values())
            self.replace(data)

    def paint_rectangle(self, mid, start, end, brush):
        """Fill the inclusive rectangle between two map cells in one edit."""
        mission = next((m for m in self.data['missions'] if m['id'] == mid), None)
        if mission is None:
            raise RuleError(f'Unknown mission: {mid}')
        width, height = mission['board']['width'], mission['board']['height']
        if not isinstance(start, (list, tuple)) or not isinstance(end, (list, tuple)):
            raise RuleError('Rectangle corners must be inside the map')
        if (len(start) != 2 or len(end) != 2 or
                any(type(v) is not int for v in (*start, *end)) or
                not (0 <= start[0] < width and 0 <= start[1] < height and
                     0 <= end[0] < width and 0 <= end[1] < height)):
            raise RuleError('Rectangle corners must be inside the map')
        start, end = tuple(start), tuple(end)
        x1, x2 = sorted((start[0], end[0]))
        y1, y2 = sorted((start[1], end[1]))
        cells = [(x, y) for y in range(y1, y2 + 1) for x in range(x1, x2 + 1)]
        self.paint_many(mid, cells, brush)

    def smart_paint(self, mid, anchors, brush, *, radius=0, shape='diamond'):
        """Paint a continuous footprint as one validated, undoable operation."""
        if brush in ('unit', 'object', 'zone+', 'zone-'):
            raise RuleError('Smart terrain brushes cannot place linked entities or zones')
        cells = smart_brush_cells(self.data, mid, anchors, radius=radius, shape=shape)
        self.paint_many(mid, cells, brush)
        return len(cells)

    def flood_surface(self, mid, start, surface, *, allowed_cells=None):
        """Existing four-neighbour fill, optionally restricted to a selection."""
        if surface not in SURFACES:
            raise RuleError('Surface inconnue')
        region = surface_region(self.data, mid, start, allowed_cells=allowed_cells)
        mission = next(m for m in self.data['missions'] if m['id'] == mid)
        tiles = {tuple(tile['pos']): tile for tile in mission['board']['tiles']}
        if tiles.get(tuple(start), {}).get('surface', 'grass') == surface:
            return 0
        self.paint_many(mid, region, 'surface:' + surface)
        return len(region)

    def place_unit(self, mid, uid, cell):
        data = deepcopy(self.data)
        mission = next(m for m in data['missions'] if m['id'] == mid)
        next(u for u in mission['units'] if u['id'] == uid)['pos'] = list(cell)
        self.replace(data)

    def save(self, path):
        Content.from_dict(self.data, rules=authored_rules_for_document(self.data))
        write_json(path, self.data)
        self.saved = json.dumps(self.data, sort_keys=True)

    def playtest(self, mid, seed=1):
        # A designer opting into starting tactical roles/formations should see
        # their actual effects in playtest. Untagged legacy documents keep
        # their exact default-rules manifest and replay semantics.
        rules = authored_rules_for_document(self.data)
        return Battle(Content.from_dict(self.data, rules=rules),
                      mid, seed, rules=rules)


def launch(path):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog

    root = tk.Tk()
    root.title('Sporebound — Atelier gameplay autonome')
    root.geometry('1280x850')
    def recover_if_pending(store):
        if not store.pending:
            return True
        decision = messagebox.askyesnocancel(
            'Sauvegarde Studio interrompue',
            f'Une écriture Content + GameProject a été interrompue pour\n'
            f'{store.content_path.name}.\n'
            'Oui : terminer la sauvegarde.\n'
            'Non : revenir aux fichiers précédents.\n'
            'Annuler : garder les fichiers intacts.')
        if decision is None:
            return False
        store.recover('complete' if decision else 'rollback')
        return True

    recovery = StudioTransactionStore(path)
    try:
        if not recover_if_pending(recovery):
            root.destroy()
            return
    except (RuleError, OSError, ValueError) as exc:
        messagebox.showerror('Récupération refusée', str(exc))
        root.destroy()
        return
    edit_recovery = EditRecoveryJournal(path)
    recovered_work = None
    if edit_recovery.pending:
        choice = messagebox.askyesnocancel(
            'Travail Studio interrompu',
            'Des modifications non enregistrées sont disponibles.\n'
            'Oui : récupérer en mémoire (sans écraser les fichiers).\n'
            'Non : abandonner ce brouillon.\n'
            'Annuler : conserver le brouillon et quitter.')
        if choice is None:
            root.destroy()
            return
        if choice:
            try:
                recovered_work = edit_recovery.restore()
            except (RuleError, OSError, ValueError) as exc:
                messagebox.showerror('Restauration refusée', str(exc))
                root.destroy()
                return
        else:
            edit_recovery.discard()
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    # Initialize dependent Studio panels against the on-disk pair first.
    # A draft may add/remove missions and invalidate the disk GameProject;
    # adopting the draft before StudioPanels.reload_project would fail.
    doc = Document(Content.from_dict(
        raw, rules=authored_rules_for_document(raw)))
    current_path = Path(path)
    disk_revisions = StudioTransactionStore(current_path).revisions()
    battle = None
    studio = None
    campaign_session = None
    campaign_battle = False
    selected_cell = (0, 0)
    stroke_cells = []
    stroke_before = None
    stroke_redo = None
    rectangle_anchor = None
    selected_tiles = set()
    selection_mission = ''
    selection_additive = False
    terrain_clipboard = None
    tile_size = 54
    iso_geometry = None
    iso_var = tk.BooleanVar(value=False)
    interior_var = tk.BooleanVar(value=False)  # Editor visibility only.
    floor_var = tk.IntVar(value=1)  # Selected visual deck (ground always 0).
    travel_level_var = tk.IntVar(value=0)  # Combat target includes ground floor.
    floor_surface_var = tk.StringVar(value='stone')
    floor_feature_var = tk.StringVar(value='crate')
    floor_action_var = tk.StringVar(value='Sol')
    surface_var = tk.StringVar(value='grass')
    feature_var = tk.StringVar(value='tree')
    level_var = tk.IntVar(value=2)
    structure_var = tk.StringVar(value='Maison')
    structure_pivot_var = tk.StringVar(value='Coin')
    structure_door_var = tk.StringVar(value='Entrée A')
    facade_var = tk.StringVar(value='pierre')
    roof_var = tk.StringVar(value='tuiles')
    window_present_var = tk.BooleanVar(value=True)
    structure_turns = 0
    structure_group_dx = tk.IntVar(value=1)
    structure_group_dy = tk.IntVar(value=0)
    editor_group_dx = tk.IntVar(value=1)
    editor_group_dy = tk.IntVar(value=0)
    group_prefab_var = tk.StringVar(value='')
    group_prefab_rotation_var = tk.StringVar(value='0°')
    quarter_style_var = tk.StringVar(value='Village')
    quarter_size_var = tk.StringVar(value='16 × 14')
    quarter_seed_var = tk.IntVar(value=1)
    quarter_variant_var = tk.StringVar(value='Variante 1')
    quarter_status_var = tk.StringVar(value='Choisir un style puis proposer trois variantes.')
    quarter_choices = ()
    quarter_pending = None
    group_prefab_preview_key = None
    group_prefab_cache_key = None
    group_prefab_cache_value = None
    prefab_gallery = None
    prefab_floating = None
    prefab_window = None
    prefab_drag_hover = None
    selected_group_id = None
    group_tree_signature = None
    group_tree_items = {}
    group_tree_cell_counts = {}
    group_tree_drag = None
    group_tree_updating = False
    structure_selection_cell = None
    structure_selection_id = None
    structure_drag_from = None
    structure_drag_anchor = None
    structure_drag_duplicate = False
    structure_drag_hover = None
    structure_preview_key = None
    asset_palette = None
    entity_palette = None
    entity_choice = None
    entity_hover_key = None
    entity_passage_entry = None
    entity_entry = None
    entity_settings = {}
    entity_inspector = None
    entity_target = None
    mission_var = tk.StringVar(value=doc.data['missions'][0]['id'])
    brush_var = tk.StringVar(value='wall')
    tool_var = tk.StringVar(value='Pinceau')
    brush_radius_var = tk.IntVar(value=1)
    brush_shape_var = tk.StringVar(value='diamond')
    unit_var = tk.StringVar()
    action_var = tk.StringVar(value='move')
    facing_var = tk.StringVar(value='south')
    object_var = tk.StringVar()
    zone_var = tk.StringVar(value='attackers')
    layer_vars = {name: tk.BooleanVar(value=True) for name in EDITOR_LAYERS}
    layer_lock_vars = {name: tk.BooleanVar(value=False) for name in EDITOR_LAYERS}
    active_layer_level = tk.IntVar(value=0)
    status_var = tk.StringVar(value='Édition : choisir un pinceau puis cliquer sur une case.')
    mode_var = tk.StringVar(value='MODE : ÉDITION')
    try:
        map_view_data = load_views(current_path)
    except RuleError as exc:
        # A damaged editor sidecar must never make a valid game unopenable.
        map_view_data = empty_views()
        status_var.set('Préférences de carte ignorées : ' + str(exc))
    doc.edit_policy = lambda before, after: ensure_unlocked(before, after, map_view_data)
    editing_context = EditingContext(doc, mission_var.get)
    editor_content_cache = EditorContentProjection()
    minimap_background = MinimapBackgroundCache()

    def guarded(fn):
        def run(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except (RuleError, OSError, ValueError, KeyError, StopIteration) as exc:
                messagebox.showerror('Opération refusée', str(exc))
        return run

    def apply_saved_map_view():
        current = view_for(map_view_data, mission_var.get())
        for name in EDITOR_LAYERS:
            layer_vars[name].set(current['visible'][name])
            layer_lock_vars[name].set(current['locked'][name])
        active_layer_level.set(current['active_level'])
        interior_var.set(current['interiors'])

    def persist_map_view():
        nonlocal map_view_data
        mid = mission_var.get()
        updated = update_view(
            map_view_data, mid,
            visible={name: var.get() for name, var in layer_vars.items()},
            locked={name: var.get() for name, var in layer_lock_vars.items()},
            active_level=active_layer_level.get(), interiors=interior_var.get())
        save_views(current_path, updated)
        map_view_data = updated
        status_var.set('Vue de carte enregistrée (préférences du Studio).')

    @guarded
    def view_options_changed():
        persist_map_view()
        refresh()

    @guarded
    def active_level_changed(_event=None):
        level = active_layer_level.get()
        scene = next(m for m in doc.data['missions'] if m['id'] == mission_var.get())
        if level and not any(row['level'] == level
                             for row in scene.get('interior_floors', ())):
            active_layer_level.set(view_for(
                map_view_data, mission_var.get())['active_level'])
            raise RuleError('Créer un étage N' + str(level) + ' avant de le sélectionner.')
        if level:
            floor_var.set(level)
            interior_var.set(True)
            iso_var.set(True)
        persist_map_view()
        refresh()

    def source_pending():
        return source.get('1.0', 'end-1c').strip() != json.dumps(doc.data, indent=2, ensure_ascii=False)

    def discard_ok():
        return not (doc.dirty or source_pending() or (studio is not None and studio.dirty())) or messagebox.askyesno('Modifications', 'Abandonner les modifications non enregistrées ?')

    def refresh_source():
        source.delete('1.0', 'end')
        source.insert('1.0', json.dumps(doc.data, indent=2, ensure_ascii=False))

    work_checkpoint_job = None

    def checkpoint_work():
        nonlocal work_checkpoint_job
        work_checkpoint_job = None
        if studio is None:
            return
        project_dirty = (json.dumps(studio.project.to_dict(), sort_keys=True)
                         != studio.project_saved)
        try:
            edit_recovery.checkpoint(
                doc.data, studio.project, expected_disk=disk_revisions,
                dirty=(doc.dirty, project_dirty))
        except (RuleError, OSError, ValueError) as exc:
            # Sidecar failures must never corrupt or block editor commands.
            status_var.set('Récupération de travail non actualisée : ' + str(exc))

    def schedule_work_checkpoint():
        nonlocal work_checkpoint_job
        editing_context.diagnostics.cancel()
        if work_checkpoint_job is not None:
            root.after_cancel(work_checkpoint_job)
        work_checkpoint_job = root.after(350, checkpoint_work)

    def design_change(fn, *, board_only=False):
        nonlocal battle
        if source_pending() and not messagebox.askyesno('JSON non appliqué', 'Abandonner les modifications JSON non appliquées ?'):
            return
        notice = fn()
        if studio is not None and stroke_before is None:
            studio.capture_history()
        battle = None
        refresh_source()
        if isinstance(notice, EditorChange):
            # Commands publish only after JSON and Studio history are in sync.
            editing_context.notify(notice)
        else:
            refresh(board_only=board_only)

    @guarded
    def open_doc():
        nonlocal doc, current_path, battle, disk_revisions, map_view_data
        nonlocal selection_mission, edit_recovery
        if not discard_ok():
            return
        name = filedialog.askopenfilename(filetypes=[('Projet Sporebound', '*.json')])
        if name:
            if not recover_if_pending(StudioTransactionStore(name)):
                return
            raw = json.loads(Path(name).read_text(encoding='utf-8'))
            next_recovery = EditRecoveryJournal(name)
            next_work = None
            if next_recovery.pending:
                decision = messagebox.askyesnocancel(
                    'Travail Studio interrompu',
                    'Récupérer les modifications non enregistrées de ce projet ?\n'
                    'Non abandonne le brouillon, Annuler conserve le projet actuel.')
                if decision is None:
                    return
                if decision:
                    next_work = next_recovery.restore()
                else:
                    next_recovery.discard()
            candidate = Document(Content.from_dict(
                raw, rules=authored_rules_for_document(raw)))
            restored_views = load_views(name)
            if current_path.resolve() != Path(name).resolve():
                edit_recovery.discard()  # User accepted leaving old project.
            doc, current_path, battle = candidate, Path(name), None
            edit_recovery = next_recovery
            map_view_data = restored_views
            doc.edit_policy = lambda before, after: ensure_unlocked(before, after, map_view_data)
            selection_mission = ''  # A different file may reuse the mission ID.
            editing_context.document = doc
            disk_revisions = StudioTransactionStore(current_path).revisions()
            mission_var.set(doc.data['missions'][0]['id'])
            if studio is not None:
                studio.reload_project()
                if next_work:
                    recovered_content = next_work[0]
                    doc.data = Content.from_dict(
                        recovered_content,
                        rules=authored_rules_for_document(recovered_content)).to_dict()
                    if mission_var.get() not in {
                            m['id'] for m in doc.data['missions']}:
                        mission_var.set(doc.data['missions'][0]['id'])
                    studio.restore_unsaved_project(next_work[1])
                studio.history.on_change = schedule_work_checkpoint
            refresh_source()
            refresh()
            refresh_group_prefabs()

    @guarded
    def save_doc():
        nonlocal current_path, disk_revisions, edit_recovery
        if StudioTransactionStore(current_path).pending:
            raise RuleError('Récupérer la sauvegarde Studio interrompue avant toute écriture')
        if source_pending():
            doc.replace(json.loads(source.get('1.0', 'end')))
        name = filedialog.asksaveasfilename(initialfile=current_path.name, defaultextension='.json', filetypes=[('JSON', '*.json')])
        if name:
            destination = Path(name)
            if destination.resolve() == current_path.resolve():
                if StudioTransactionStore(current_path).revisions()[0] != disk_revisions[0]:
                    raise RuleError('Le contenu a changé sur disque : recharger avant écrasement.')
            doc.save(name)
            original_path = current_path
            current_path = destination
            saved_content = StudioTransactionStore(current_path).revisions()[0]
            disk_revisions = (saved_content,
                              disk_revisions[1] if current_path.resolve() ==
                              original_path.resolve() else None)
            if current_path.resolve() != original_path.resolve():
                # Save As is a new recovery identity and a new disk baseline.
                edit_recovery.discard()
                edit_recovery = EditRecoveryJournal(current_path)
                save_views(current_path, map_view_data)
            refresh_source()
            refresh_group_prefabs()
            status_var.set(f'Projet enregistré : {name}')
            schedule_work_checkpoint()

    @guarded
    def save_all():
        """Validate and publish both Studio documents with recovery support."""
        nonlocal current_path, disk_revisions
        if studio is None:
            raise RuleError('Studio non initialisé')
        store = StudioTransactionStore(current_path)
        edited = (json.loads(source.get('1.0', 'end')) if source_pending()
                  else doc.data)
        original = doc.data
        original_project = studio.project
        try:
            new_data = Content.from_dict(
                edited, rules=authored_rules_for_document(edited)).to_dict()
            ensure_unlocked(doc.data, new_data, map_view_data)
            doc.data = new_data
            studio.apply_project()
            store.save(doc.data, studio.project.to_dict(),
                       expected_previous=disk_revisions)
        except Exception:
            # A failed save must not silently apply unsaved fields or leave
            # half an in-memory transaction. Inputs remain in their widgets
            # so the designer can fix the issue and retry after recovery.
            doc.data = original
            studio.project = original_project
            raise
        doc.saved = json.dumps(doc.data, sort_keys=True)
        current_path = store.content_path
        disk_revisions = store.revisions()
        studio.project_path = store.project_path
        studio.project_saved = json.dumps(studio.project.to_dict(), sort_keys=True)
        studio.capture_history()
        refresh_source()
        refresh()
        status_var.set('Contenu et projet enregistrés ensemble (récupération activée).')
        schedule_work_checkpoint()

    @guarded
    def undo_global():
        nonlocal battle
        if source_pending():
            raise RuleError('Appliquer ou abandonner les modifications JSON avant annulation.')
        if studio._pending_fields() and not messagebox.askyesno(
                'Champs non appliqués', 'Abandonner les champs non appliqués ?'):
            return
        if stroke_before is not None:
            end_stroke(None)
        if not studio.history.can_undo:
            return
        studio.undo_global()
        battle = None
        refresh_source()
        refresh()

    @guarded
    def redo_global():
        nonlocal battle
        if source_pending():
            raise RuleError('Appliquer ou abandonner les modifications JSON avant rétablissement.')
        if studio._pending_fields() and not messagebox.askyesno(
                'Champs non appliqués', 'Abandonner les champs non appliqués ?'):
            return
        if stroke_before is not None:
            end_stroke(None)
        if not studio.history.can_redo:
            return
        studio.redo_global()
        battle = None
        refresh_source()
        refresh()

    @guarded
    def apply_json():
        nonlocal battle
        doc.replace(json.loads(source.get('1.0', 'end')))
        if studio is not None:
            studio.capture_history()
        battle = None
        refresh_source()
        refresh()
        status_var.set('Données validées et appliquées.')

    @guarded
    def new_mission():
        mid = simpledialog.askstring('Nouvelle mission', 'Identifiant unique :')
        if not mid:
            return
        def edit():
            data = deepcopy(doc.data)
            template = deepcopy(next(m for m in data['missions'] if m['id'] == mission_var.get()))
            template.update(id=mid, name=mid, next_missions=[])
            data['missions'].append(template)
            doc.replace(data)
            mission_var.set(mid)
        design_change(edit)

    @guarded
    def blank_mission():
        from .authoring import add_blank_mission
        mid = simpledialog.askstring('Carte vierge', 'Identifiant de mission :')
        if not mid:
            return
        name = simpledialog.askstring('Carte vierge', 'Titre :', initialvalue=mid)
        if name is None:
            return
        width = simpledialog.askinteger('Carte vierge', 'Largeur (4–128) :',
                                         initialvalue=8, minvalue=4, maxvalue=128)
        if width is None:
            return
        height = simpledialog.askinteger('Carte vierge', 'Hauteur (4–128) :',
                                          initialvalue=8, minvalue=4, maxvalue=128)
        if height is None:
            return
        def edit():
            doc.replace(add_blank_mission(doc.data, mid, name, width, height))
            mission_var.set(mid)
        design_change(edit)

    @guarded
    def start():
        nonlocal battle, campaign_battle
        campaign_battle = False
        if source_pending():
            doc.replace(json.loads(source.get('1.0', 'end')))
            refresh_source()
        battle = doc.playtest(mission_var.get())
        tool_tabs.select(tools_main)
        notebook.select(work)
        refresh()
        status_var.set('Playtest isolé. Choisir une commande, cliquer une cible, puis Exécuter.')

    def stop():
        nonlocal battle, campaign_battle
        campaign_battle = False
        battle = None
        refresh()
        status_var.set('Retour à l’édition. Progression de campagne inchangée.')

    @guarded
    def start_campaign(progress, mid):
        nonlocal battle, campaign_session, campaign_battle
        if source_pending():
            raise RuleError('Appliquer ou abandonner les modifications JSON avant de jouer.')
        campaign_session = progress
        rules = authored_rules_for_document(doc.data)
        battle = progress.prepare(Content.from_dict(doc.data, rules=rules),
                                  mid, ruleset=rules)
        campaign_battle = True
        mission_var.set(mid)
        tool_tabs.select(tools_main)
        notebook.select(work)
        refresh()
        status_var.set('Campagne : mission lancée. La progression sera validée à la fin du combat.')

    @guarded
    def ai_turn():
        if battle and not battle.result:
            play_activation(battle)
            refresh()

    @guarded
    def end_turn():
        if battle:
            directions = dict(north=[0,-1], south=[0,1], east=[1,0], west=[-1,0])
            battle.execute({'kind': 'end', 'facing': directions[facing_var.get()]})
            refresh()

    @guarded
    def execute():
        if not battle:
            return
        action = action_var.get()
        if action == 'start_battle':
            cmd = {'kind': 'start_battle'}
        elif action == 'deploy':
            directions = dict(north=[0,-1], south=[0,1], east=[1,0], west=[-1,0])
            cmd = {'kind': 'deploy', 'unit': unit_var.get(), 'cell': list(selected_cell),
                   'facing': directions[facing_var.get()]}
        elif action == 'move':
            cmd = {'kind': 'move', 'cell': list(selected_cell)}
        elif action == 'level_move':
            cmd = {'kind': 'level_move', 'level': travel_level_var.get(),
                   'cell': list(selected_cell)}
        elif action == 'level_attack':
            cmd = {'kind': 'level_attack', 'level': travel_level_var.get(),
                   'cell': list(selected_cell)}
        elif action.startswith('item:'):
            cmd = {'kind': 'item', 'item': action[5:], 'cell': list(selected_cell)}
        elif action.startswith('object:'):
            cmd = {'kind': 'interact', 'object': action[7:]}
        elif action.startswith('siege-attack:'):
            cmd = {'kind': 'siege_attack', 'object': action[13:]}
        elif action.startswith('repair-siege:'):
            cmd = {'kind': 'repair_siege', 'object': action[13:]}
        else:
            cmd = {'kind': 'act', 'skill': action, 'cell': list(selected_cell)}
        battle.execute(cmd)
        refresh()

    @guarded
    def save_game():
        if battle:
            name = filedialog.asksaveasfilename(defaultextension='.json', initialfile='battle.json')
            if name:
                save_battle(name, battle)
                status_var.set('Combat et replay enregistrés.')

    @guarded
    def load_game():
        nonlocal battle, campaign_battle
        campaign_battle = False
        name = filedialog.askopenfilename(filetypes=[('Combat/replay', '*.json')])
        if name:
            battle = load_battle(name)
            refresh()

    def _selection_for_current_map():
        if battle:
            raise RuleError('Quitter le combat pour modifier la carte.')
        if not selected_tiles:
            raise RuleError('Utiliser l’outil Sélection pour choisir des cases.')
        return validate_selection(doc.data, mission_var.get(), selected_tiles)

    @guarded
    def copy_selection():
        nonlocal terrain_clipboard
        if source_pending():
            raise RuleError('Appliquer ou abandonner les changements JSON avant la copie.')
        terrain_clipboard = copy_terrain(doc.data, mission_var.get(),
                                         _selection_for_current_map())
        status_var.set(f'Copié : {len(terrain_clipboard.offsets)} cases de terrain '
                       '(acteurs et objets non copiés).')
        refresh()

    def paste_at(anchor):
        nonlocal selected_tiles
        if battle:
            raise RuleError('Le collage est réservé à l’éditeur.')
        if terrain_clipboard is None:
            raise RuleError('Copier d’abord une sélection de terrain.')
        if source_pending():
            raise RuleError('Appliquer ou abandonner les modifications JSON avant le collage.')
        design_change(lambda: doc.replace(paste_terrain(doc.data, mission_var.get(),
                                                         terrain_clipboard, anchor)))
        selected_tiles = {(anchor[0]+dx, anchor[1]+dy)
                          for dx, dy in terrain_clipboard.offsets}
        status_var.set(f'Collage validé en {anchor} ({len(selected_tiles)} cases).')
        refresh()

    @guarded
    def paste_selection():
        paste_at(selected_cell)

    @guarded
    def rotate_or_flip(operation):
        nonlocal terrain_clipboard
        if battle:
            raise RuleError('Quitter le combat avant de transformer le terrain.')
        if terrain_clipboard is None:
            raise RuleError('Copier une sélection avant rotation ou symétrie.')
        terrain_clipboard = transform_terrain(terrain_clipboard, operation)
        status_var.set(f'Terrain transformé : {terrain_clipboard.width} × '
                       f'{terrain_clipboard.height} cases. Cliquer pour coller.')
        tool_var.set('Collage')
        refresh()

    @guarded
    def save_terrain_stamp():
        if battle or source_pending():
            raise RuleError('Terminer les modifications avant de sauvegarder un modèle.')
        if terrain_clipboard is None:
            raise RuleError('Copier une sélection avant de créer un modèle.')
        name = simpledialog.askstring('Modèle de terrain', 'Nom du modèle :')
        if name is None:
            return
        output = filedialog.asksaveasfilename(
            defaultextension='.stamp.json',
            filetypes=[('Modèle terrain JSON', '*.json')], initialfile='terrain.stamp.json')
        if output:
            save_stamp(output, terrain_clipboard, name)
            status_var.set(f'Modèle terrain enregistré : {output}')

    @guarded
    def open_terrain_stamp():
        nonlocal terrain_clipboard
        if battle:
            raise RuleError('Quitter le combat avant de charger un modèle.')
        filename = filedialog.askopenfilename(
            filetypes=[('Modèle terrain JSON', '*.json')])
        if filename:
            terrain_clipboard = load_stamp(filename)
            tool_var.set('Collage')
            status_var.set(f'Modèle prêt : {terrain_clipboard.width} × '
                           f'{terrain_clipboard.height} cases.')
            refresh()

    @guarded
    def shift_entity_group(dx, dy):
        nonlocal selected_tiles
        if battle or source_pending():
            raise RuleError('Terminer les modifications et quitter le combat.')
        cells = _selection_for_current_map()
        unit_ids, object_ids = group_entities(doc.data, mission_var.get(), cells)
        if not unit_ids and not object_ids:
            raise RuleError('Aucun acteur ni objet de la sélection à déplacer.')
        design_change(lambda: doc.replace(move_group(
            doc.data, mission_var.get(), unit_ids, object_ids, dx=dx, dy=dy)))
        # Keep the entity group selected at its new coordinates (within bounds).
        mission = next(m for m in doc.data['missions'] if m['id'] == mission_var.get())
        selected_tiles = {(x+dx, y+dy) for x, y in selected_tiles
                          if 0 <= x+dx < mission['board']['width'] and
                          0 <= y+dy < mission['board']['height']}
        status_var.set(f'Groupe déplacé : {len(unit_ids)} unités, '
                       f'{len(object_ids)} objets ; Δ({dx}, {dy}).')
        refresh()

    @guarded
    def apply_structure_group(duplicate=False):
        nonlocal selected_tiles, selected_cell
        if battle is not None or source_pending():
            raise RuleError('Quitter le playtest et appliquer le JSON avant édition.')
        cells = _selection_for_current_map()
        group = selected_structures(doc.data, mission_var.get(), cells)
        if not group:
            raise RuleError('Sélectionner la totalité des cases de chaque bâtiment (outil Sélection).')
        dx, dy = structure_group_dx.get(), structure_group_dy.get()
        if (dx, dy) == (0, 0) and not duplicate:
            status_var.set('Décalage nul : aucune modification à enregistrer.')
            return
        # A single Document.replace is the whole Undo transaction.
        design_change(lambda: editing_context.execute(
            StructureGroupCommand(tuple(cells), dx, dy, duplicate=duplicate),
            publish=False))
        moved_cells = {(x + dx, y + dy) for item in group for x, y in item.cells}
        selected_tiles = moved_cells
        selected_cell = (group[0].anchor[0] + dx, group[0].anchor[1] + dy)
        tool_var.set('Sélection')
        refresh()
        status_var.set(f'{len(group)} structure(s) ' +
                       ('dupliquée(s)' if duplicate else 'déplacée(s)') +
                       f' : Δ({dx}, {dy}) ; une seule annulation.')

    @guarded
    def preview_structure_group():
        if battle is not None or source_pending():
            raise RuleError('Quitter le playtest et appliquer le JSON avant édition.')
        group = selected_structures(doc.data, mission_var.get(),
                                     _selection_for_current_map())
        if not group:
            raise RuleError('Sélectionner au moins une empreinte de structure complète.')
        dx, dy = structure_group_dx.get(), structure_group_dy.get()
        mission = next(m for m in doc.data['missions']
                       if m['id'] == mission_var.get())
        width, height = mission['board']['width'], mission['board']['height']
        footprint = [(x + dx, y + dy) for item in group for x, y in item.cells]
        try:
            editing_context.preview(StructureGroupCommand(
                tuple(_selection_for_current_map()), dx, dy))
            color, note = '#36a16c', 'valide'
        except RuleError as exc:
            color, note = '#e05252', str(exc)
        canvas.delete('structure_group_ghost')
        if iso_var.get() and iso_geometry is not None:
            for item in group:
                moved_anchor = item.anchor[0] + dx, item.anchor[1] + dy
                instance, origin = preview_structure_sprite_position(
                    iso_geometry, item.name, moved_anchor, item.turns,
                    door_slot=item.door_slot)
                loader = (building_atlas if instance.name in ARCHITECTURE_NAMES
                          else fortification_atlas)
                photo = loader.sprite(instance.name, instance.turns, tile_size)
                if photo is not None:
                    canvas.create_image(*origin, image=photo, anchor='nw',
                                        tags='structure_group_ghost')
        preview_cells((c for c in footprint if 0 <= c[0] < width and
                       0 <= c[1] < height), tag='structure_group_preview',
                      color=color)
        status_var.set(f'Aperçu {len(group)} structure(s) : {note}.')

    def _active_group():
        if selected_group_id is None:
            raise RuleError('Choisir un groupe dans l’arborescence.')
        mission = next(m for m in doc.data['missions']
                       if m['id'] == mission_var.get())
        if not any(g['id'] == selected_group_id for g in
                   mission.get('editor_groups', ())):
            raise RuleError('Le groupe sélectionné n’existe plus.')
        return mission

    @guarded
    def create_map_group(*, child=False, empty=False):
        nonlocal selected_group_id
        if battle or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        parent = selected_group_id if child else None
        if child:
            _active_group()
        if not empty and not selected_tiles:
            raise RuleError('Sélectionner des cases ou créer un groupe vide.')
        name = simpledialog.askstring('Nouveau groupe',
                                      'Nom du groupe (ex. Village, Tour, Jardin) :')
        if name is None:
            return
        before = {g['id'] for g in next(m for m in doc.data['missions']
                                       if m['id'] == mission_var.get())
                  .get('editor_groups', ())}
        design_change(lambda: doc.replace(create_editor_group(
            doc.data, mission_var.get(), name, parent=parent,
            cells=tuple(selected_tiles) if not empty else ())))
        new_ids = {g['id'] for g in next(m for m in doc.data['missions']
                                        if m['id'] == mission_var.get())
                   .get('editor_groups', ())}
        created = new_ids - before
        if created:
            selected_group_id = created.pop()
        refresh()
        status_var.set('Groupe créé : ' + name)

    @guarded
    def assign_group_selection():
        if battle or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        _active_group()
        cells = _selection_for_current_map()
        design_change(lambda: doc.replace(add_selection_to_group(
            doc.data, mission_var.get(), selected_group_id, cells)))
        status_var.set('Cases et objets de la sélection liés au groupe.')

    @guarded
    def unlink_group_selection():
        if battle or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        _active_group()
        cells = _selection_for_current_map()
        design_change(lambda: doc.replace(remove_selection_from_group(
            doc.data, mission_var.get(), selected_group_id, cells)))
        status_var.set('Sélection retirée du groupe sans supprimer ses objets.')

    @guarded
    def transfer_group_selection():
        if battle or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        _active_group()
        cells = _selection_for_current_map()
        design_change(lambda: doc.replace(transfer_selection_to_group(
            doc.data, mission_var.get(), selected_group_id, cells)))
        status_var.set('Appartenance de la sélection transférée au groupe.')

    @guarded
    def change_group_parent():
        if battle or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        mission = _active_group()
        groups = mission.get('editor_groups', [])
        current = next(g for g in groups if g['id'] == selected_group_id)
        available = ', '.join(g['id']+': '+g['name'] for g in groups
                              if g['id'] != selected_group_id)
        choice = simpledialog.askstring(
            'Déplacer dans l’arbre',
            'ID du nouveau parent (vide = racine) :\n'+available,
            initialvalue=current['parent'] or '')
        if choice is None:
            return
        parent = choice.strip() or None
        design_change(lambda: doc.replace(reparent_editor_group(
            doc.data, mission_var.get(), selected_group_id, parent)))

    @guarded
    def rename_map_group():
        if battle or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        mission = _active_group()
        current = next(g for g in mission['editor_groups']
                       if g['id'] == selected_group_id)
        name = simpledialog.askstring('Renommer le groupe', 'Nom :',
                                      initialvalue=current['name'])
        if name is not None:
            design_change(lambda: doc.replace(rename_editor_group(
                doc.data, mission_var.get(), selected_group_id, name)))

    @guarded
    def ungroup_map_group():
        nonlocal selected_group_id
        if battle or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        _active_group()
        gid = selected_group_id
        selected_group_id = None
        design_change(lambda: doc.replace(delete_editor_group(
            doc.data, mission_var.get(), gid)))
        status_var.set('Groupe dissocié ; ses membres et sous-groupes sont conservés.')

    def _selected_groups_from_tree():
        """Only explicit group rows are batch targets; children are deduped."""
        chosen = tuple(iid[2:] for iid in group_tree.selection()
                       if iid.startswith('g:'))
        if not chosen and selected_group_id is not None:
            chosen = (selected_group_id,)
        return selected_group_roots(_group_tree_mission(), chosen)

    @guarded
    def shift_map_group(dx=None, dy=None, *, preview=False, duplicate=False):
        nonlocal selected_tiles, selected_cell, selected_group_id
        if battle or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        mission = _group_tree_mission()
        roots = _selected_groups_from_tree()
        dx = editor_group_dx.get() if dx is None else dx
        dy = editor_group_dy.get() if dy is None else dy
        cmd = EditorGroupBatchCommand(roots, dx, dy, duplicate=duplicate)
        footprint = set()
        for gid in roots:
            footprint.update(group_display_cells(mission, gid))
        if preview:
            try:
                editing_context.preview(cmd)
                color, note = '#36a16c', 'valide'
            except RuleError as exc:
                color, note = '#e05252', str(exc)
            board = mission['board']
            ghost = ((x+dx, y+dy) for x, y in sorted(footprint)
                     if 0 <= x+dx < board['width'] and
                        0 <= y+dy < board['height'])
            from itertools import islice
            preview_cells(islice(ghost, 512), tag='editor_group_preview',
                          color=color)
            status_var.set(('Copie' if duplicate else 'Déplacement') +
                           f' de {len(roots)} groupe(s) : {note}')
            return
        existing_ids = {g['id'] for g in mission.get('editor_groups', ())}
        design_change(lambda: editing_context.execute(cmd, publish=False))
        next_mission = _group_tree_mission()
        if duplicate:
            copied = {g['id'] for g in next_mission['editor_groups']} - existing_ids
            copied_roots = tuple(g['id'] for g in next_mission['editor_groups']
                                 if g['id'] in copied and g['parent'] not in copied)
            selected_group_id = copied_roots[0] if copied_roots else None
            selected_tiles = set().union(
                *(group_display_cells(next_mission, gid) for gid in copied_roots))
            chosen = copied_roots
        else:
            selected_tiles = set().union(
                *(group_display_cells(next_mission, gid) for gid in roots))
            chosen = roots
        if selected_tiles:
            selected_cell = min(selected_tiles, key=lambda p: (p[1], p[0]))
        refresh()
        chosen_items = tuple('g:'+gid for gid in chosen
                             if group_tree.exists('g:'+gid))
        if chosen_items:
            group_tree.selection_set(chosen_items)
            group_tree.focus(chosen_items[0])
        status_var.set(
            f'{len(chosen)} groupe(s) ' +
            ('dupliqués' if duplicate else 'déplacés') +
            f' Δ({dx}, {dy}) ; une seule annulation.')

    def _prefab_library():
        return current_path.parent / 'prefabs'

    def refresh_group_prefabs():
        paths = list_group_prefabs(_prefab_library())
        options = [item.name for item in paths]
        group_prefab_box.configure(values=options)
        if group_prefab_var.get() not in options:
            group_prefab_var.set(options[0] if options else '')
        if prefab_gallery is not None:
            rows = []
            for item in paths:
                try:
                    rows.append(prefab_card(item, load_group_prefab(item)))
                except (RuleError, ValueError, OSError, KeyError, TypeError) as exc:
                    rows.append(broken_prefab_card(item, str(exc)))
            prefab_gallery.update(rows)
            prefab_gallery.selected = group_prefab_var.get()
            prefab_gallery.render()
            if prefab_floating is not None:
                prefab_floating.update(rows)
                prefab_floating.selected = group_prefab_var.get()
                prefab_floating.render()
        return paths

    def _chosen_prefab():
        nonlocal group_prefab_cache_key, group_prefab_cache_value
        name = group_prefab_var.get()
        require_path = next((item for item in list_group_prefabs(
            _prefab_library()) if item.name == name), None)
        if require_path is None:
            raise RuleError('Sélectionner un préfab dans la bibliothèque.')
        turns = {'0°': 0, '90°': 1, '180°': 2, '270°': 3}.get(
            group_prefab_rotation_var.get())
        if turns is None:
            raise RuleError('Rotation de préfab inconnue.')
        stat = require_path.stat()
        key = (str(require_path), stat.st_mtime_ns, stat.st_size, turns)
        if key != group_prefab_cache_key:
            new = rotate_group_prefab(load_group_prefab(require_path), turns)
            group_prefab_cache_value = new
            group_prefab_cache_key = key
        return group_prefab_cache_value

    @guarded
    def export_group_prefab():
        if battle is not None or source_pending():
            raise RuleError('Terminer le playtest et appliquer le JSON.')
        roots = _selected_groups_from_tree()
        name = simpledialog.askstring(
            'Créer un préfab', 'Nom du modèle réutilisable :',
            initialvalue='Ensemble de groupes')
        if name is None:
            return
        prefab = capture_group_prefab(
            doc.data, mission_var.get(), roots, name)
        output = _prefab_library() / prefab_file_slug(name)
        overwrite = output.exists() and messagebox.askyesno(
            'Remplacer un préfab', 'Remplacer '+output.name+' ?')
        if output.exists() and not overwrite:
            return
        save_group_prefab(prefab, output, overwrite=overwrite)
        refresh_group_prefabs()
        group_prefab_var.set(output.name)
        status_var.set('Préfab sauvegardé : '+str(output))

    @guarded
    def import_group_prefab():
        name = filedialog.askopenfilename(
            title='Importer un préfab',
            filetypes=[('Préfab de groupes', '*.json')])
        if not name:
            return
        prefab = load_group_prefab(name)
        target = _prefab_library() / prefab_file_slug(prefab['name'])
        overwrite = target.exists() and messagebox.askyesno(
            'Remplacer un préfab', 'Remplacer '+target.name+' ?')
        if target.exists() and not overwrite:
            return
        save_group_prefab(prefab, target, overwrite=overwrite)
        refresh_group_prefabs()
        group_prefab_var.set(target.name)
        status_var.set('Préfab ajouté à la bibliothèque : '+target.name)

    def draw_prefab_thumbnail(_event=None, *, prefab=None):
        # The library and generated alternatives share the same visual
        # preview; no second model or renderer for generated buildings.
        prefab_thumbnail.delete('all')
        try:
            prefab = _chosen_prefab() if prefab is None else prefab
        except (RuleError, OSError, ValueError) as exc:
            prefab_thumbnail.create_text(
                8, 55, text=str(exc)[:40], anchor='w', fill='#a33c33')
            return
        width, height = prefab['size']
        pitch = min(14., 246. / width, 104. / height)
        ox = (254. - width * pitch) / 2
        oy = (114. - height * pitch) / 2
        tones = {'water': '#6196c0', 'cobble': '#a49c86',
                 'stone': '#999b98', 'dirt': '#af9474',
                 'bridge': '#ad9272', 'grass': '#83b48a'}
        for tile in prefab['tiles'][:2048]:
            x, y = tile['pos']
            raw = tile['tile'] or {}
            color = tones.get(raw.get('surface', 'grass'), '#83b48a')
            if raw.get('blocked'):
                color = '#665c55'
            prefab_thumbnail.create_rectangle(
                ox + x*pitch, oy + y*pitch,
                ox + (x+1)*pitch, oy + (y+1)*pitch,
                fill=color, outline='', tags='prefab_thumbnail_tile')
            if raw.get('feature') and pitch >= 7:
                prefab_thumbnail.create_oval(
                    ox + (x+.3)*pitch, oy + (y+.3)*pitch,
                    ox + (x+.7)*pitch, oy + (y+.7)*pitch,
                    fill='#416a47', outline='')
        for building in prefab['structures']:
            plan = structure_template(building['name'], building['turns'],
                                      door_slot=building['door_slot'])
            x, y = building['anchor']
            prefab_thumbnail.create_rectangle(
                ox+x*pitch, oy+y*pitch,
                ox+(x+plan.width)*pitch, oy+(y+plan.height)*pitch,
                outline='#583925', width=2)
        for item in prefab['objects']:
            x, y = item['pos']
            prefab_thumbnail.create_rectangle(
                ox+(x+.2)*pitch, oy+(y+.2)*pitch,
                ox+(x+.8)*pitch, oy+(y+.8)*pitch,
                fill='#8653a5', outline='')
        for item in prefab['units']:
            x, y = item['pos']
            prefab_thumbnail.create_oval(
                ox+(x+.15)*pitch, oy+(y+.15)*pitch,
                ox+(x+.85)*pitch, oy+(y+.85)*pitch,
                fill='#e4bb72', outline='#6f533a')
        prefab_thumbnail.create_text(5, 5, anchor='nw',
                                    text=f'{width} × {height} cases',
                                    fill='#374151')

    def preview_group_prefab_at(prefab, anchor):
        # Preview performs the same complete validation as the commit. An
        # invalid placement is red, but never changes map data or undo state.
        nonlocal group_prefab_preview_key
        key = (id(doc.data), mission_var.get(), group_prefab_cache_key,
               anchor)
        if key == group_prefab_preview_key:
            return
        group_prefab_preview_key = key
        canvas.delete('editor_group_preview')
        try:
            editing_context.preview(GroupPrefabPlaceCommand(prefab, anchor))
            color, note = '#36a16c', 'valide'
        except RuleError as exc:
            color, note = '#e05252', str(exc)
        mission = _group_tree_mission()
        width, height = mission['board']['width'], mission['board']['height']
        visible = (cell for cell in sorted(prefab_display_cells(prefab, anchor))
                   if 0 <= cell[0] < width and 0 <= cell[1] < height)
        preview_cells(tuple(islice(visible, 512)),
                      tag='editor_group_preview', color=color)
        status_var.set(f'Préfab {prefab["name"]} ({group_prefab_rotation_var.get()})'
                       f' : {note} ; cliquer pour insérer.')

    def _prefab_world_at(screen_pixel):
        """Window-relative pointer to board coordinates in both map modes."""
        x, y = screen_pixel
        x, y = canvas.canvasx(x), canvas.canvasy(y)
        if iso_var.get() and iso_geometry is not None:
            cell = iso_geometry.hit_test(x, y)
        else:
            cell = (int(x // tile_size), int(y // tile_size))
        if cell is None:
            return None
        board = _group_tree_mission()['board']
        return cell if 0 <= cell[0] < board['width'] and 0 <= cell[1] < board['height'] else None

    def clear_prefab_drag():
        nonlocal prefab_drag_hover
        prefab_drag_hover = None
        canvas.delete('prefab_drag_preview')

    def preview_prefab_at(prefab, anchor, *, drag=False):
        """Pure preview; rejected placements turn red, never enter history."""
        nonlocal prefab_drag_hover
        target_tag = 'prefab_drag_preview' if drag else 'editor_group_preview'
        hover_key = (prefab['name'], tuple(anchor), mission_var.get(),
                     id(doc.data), group_prefab_rotation_var.get())
        if drag and prefab_drag_hover == hover_key:
            return
        prefab_drag_hover = hover_key
        try:
            if battle is not None or source_pending():
                raise RuleError('Terminer le playtest et appliquer le JSON.')
            editing_context.preview(GroupPrefabPlaceCommand(prefab, tuple(anchor)))
            color, message = '#36a16c', 'destination valide'
        except (RuleError, ValueError, KeyError) as exc:
            color, message = '#e05252', str(exc)
        board = _group_tree_mission()['board']
        cells = sorted(prefab_display_cells(prefab, anchor))
        visible = (cell for cell in cells if 0 <= cell[0] < board['width']
                   and 0 <= cell[1] < board['height'])
        from itertools import islice
        preview_cells(islice(visible, 512), tag=target_tag, color=color)
        status_var.set(f'Préfab {prefab["name"]} : {message}')

    def commit_prefab_at(prefab, anchor):
        nonlocal selected_group_id, selected_tiles, selected_cell
        if battle is not None or source_pending():
            raise RuleError('Terminer le playtest et appliquer le JSON.')
        before = {g['id'] for g in _group_tree_mission().get('editor_groups', ())}
        command = GroupPrefabPlaceCommand(prefab, tuple(anchor))
        # This uses exactly the existing typed authoring and undo transaction.
        # A drag never dispatches a terrain-brush click.
        design_change(lambda: editing_context.execute(command, publish=False))
        mission = _group_tree_mission()
        created = {g['id'] for g in mission.get('editor_groups', ())} - before
        roots = [g['id'] for g in mission['editor_groups']
                 if g['id'] in created and g['parent'] not in created]
        selected_group_id = roots[0] if roots else None
        selected_tiles = set().union(
            *(group_display_cells(mission, gid) for gid in roots))
        selected_cell = tuple(anchor)
        clear_prefab_drag()
        refresh()
        if selected_group_id and group_tree.exists('g:'+selected_group_id):
            group_tree.selection_set('g:'+selected_group_id)
        status_var.set(f'Préfab {prefab["name"]} placé en {tuple(anchor)} '
                       '— Annuler/Rétablir disponibles.')

    @guarded
    def place_chosen_prefab(*, preview=False, anchor=None):
        prefab = _chosen_prefab()
        anchor = tuple(selected_cell if anchor is None else anchor)
        if preview:
            preview_group_prefab_at(prefab, anchor)
        else:
            commit_prefab_at(prefab, anchor)

    def palette_prefab_hover(filename, screen_pixel):
        anchor = _prefab_world_at(screen_pixel)
        if anchor is None:
            clear_prefab_drag()
            return
        try:
            prefab = rotate_group_prefab(
                load_group_prefab(_prefab_library() / filename),
                {'0°': 0, '90°': 1, '180°': 2, '270°': 3}[
                    group_prefab_rotation_var.get()])
        except (RuleError, ValueError, OSError):
            clear_prefab_drag()
            return
        preview_prefab_at(prefab, anchor, drag=True)

    @guarded
    def palette_prefab_drop(filename, screen_pixel):
        anchor = _prefab_world_at(screen_pixel)
        if anchor is None:
            raise RuleError('Déposer le préfab à l’intérieur de la carte.')
        prefab = rotate_group_prefab(
                load_group_prefab(_prefab_library() / filename),
                {'0°': 0, '90°': 1, '180°': 2, '270°': 3}[
                    group_prefab_rotation_var.get()])
        commit_prefab_at(prefab, anchor)

    def open_visual_prefab_palette():
        """Roomy nonmodal palette; the author can still drop onto the map."""
        nonlocal prefab_window, prefab_floating
        if prefab_window is not None and prefab_window.winfo_exists():
            prefab_window.lift()
            prefab_window.focus_set()
            return
        window = tk.Toplevel(root)
        window.title('Palette visuelle — Préfabs')
        window.geometry('390x540')
        window.transient(root)
        ttk.Label(window,
                  text='Choisir un modèle puis glisser sa miniature sur la carte.',
                  wraplength=355).pack(anchor='w', padx=8, pady=6)
        floating = VisualPrefabPalette(
            window, tk, ttk,
            on_select=group_prefab_var.set,
            on_preview=palette_prefab_hover,
            on_drop=palette_prefab_drop,
            on_cancel=clear_prefab_drag,
            map_canvas=canvas,
            status=status_var.set)
        floating.frame.pack(fill='both', expand=True, padx=6, pady=4)
        prefab_window, prefab_floating = window, floating

        def close():
            nonlocal prefab_window, prefab_floating
            floating.cancel()
            window.destroy()
            prefab_window = None
            prefab_floating = None

        window.protocol('WM_DELETE_WINDOW', close)
        window.bind('<Escape>', lambda _e: close())
        ttk.Button(window, text='Actualiser les modèles',
                   command=refresh_group_prefabs).pack(fill='x',
                                                       padx=8, pady=(0, 6))
        refresh_group_prefabs()

    def enable_prefab_stamping():
        if battle is not None or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON.')
        _chosen_prefab()  # Check the library item before switching tools.
        tool_var.set('Préfab')
        status_var.set('Préfab actif : survoler la carte, clic pour insérer ; '
                       'choisir la rotation 0/90/180/270°.')

    def _quarter_choice():
        if not quarter_choices:
            raise RuleError('Générer trois propositions avant sélection.')
        index = {'Variante 1': 0, 'Variante 2': 1,
                 'Variante 3': 2}.get(quarter_variant_var.get())
        if index is None:
            raise RuleError('Choisir une variante existante.')
        return quarter_choices[index]

    def refresh_quarter_thumbnail(_event=None):
        if quarter_choices:
            choice = _quarter_choice()
            draw_prefab_thumbnail(prefab=choice)
            quarter_status_var.set(
                f'{choice["name"]} : {len(choice["structures"])} bâtiments, '
                f'{len(choice["tiles"])} cases, 1 coffre interactif.')

    @guarded
    def propose_quarters():
        nonlocal quarter_choices, quarter_pending
        if battle is not None or source_pending():
            raise RuleError('Revenir dans le Studio et appliquer le JSON.')
        text = quarter_size_var.get()
        sizes = {f'{w} × {h}': (w, h) for w, h in QUARTER_SIZES}
        if text not in sizes:
            raise RuleError('Taille de quartier non prise en charge.')
        quarter_choices = suggest_quarters(
            style=quarter_style_var.get(), size=sizes[text],
            seed=quarter_seed_var.get())
        quarter_pending = None
        quarter_variant_var.set('Variante 1')
        canvas.delete('quarter_generation_preview')
        refresh_quarter_thumbnail()
        status_var.set('Trois plans reproductibles proposés, aucun changement appliqué.')

    @guarded
    def preview_quarter_proposal():
        nonlocal quarter_pending
        if battle is not None or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON.')
        prefab = _quarter_choice()
        anchor = tuple(selected_cell)
        quarter_pending = None
        canvas.delete('quarter_generation_preview')
        try:
            proposed, report = preview_quarter(doc.data, mission_var.get(),
                                               prefab, anchor)
            ensure_unlocked(doc.data, proposed, map_view_data)
            color = '#36a16c'
            quarter_pending = (mission_var.get(), anchor, id(doc.data),
                               quarter_variant_var.get())
            description = (
                f'+{report["structures"]} bâtiments · +{report["objects"]} objet · '
                f'+{report["groups"]} groupes · {report["cells"]} cases modifiées')
        except RuleError as exc:
            color = '#e05252'
            description = 'Placement refusé : ' + str(exc)
        mission = _group_tree_mission()
        width, height = mission['board']['width'], mission['board']['height']
        inside = (p for p in sorted(prefab_display_cells(prefab, anchor))
                  if 0 <= p[0] < width and 0 <= p[1] < height)
        preview_cells(tuple(islice(inside, 512)),
                      tag='quarter_generation_preview', color=color)
        quarter_status_var.set(description)
        status_var.set(description)

    @guarded
    def confirm_quarter_proposal():
        nonlocal quarter_pending
        prefab = _quarter_choice()
        key = (mission_var.get(), tuple(selected_cell), id(doc.data),
               quarter_variant_var.get())
        if quarter_pending != key:
            raise RuleError('Prévisualiser cette variante à cette position avant validation.')
        if battle is not None or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON.')
        # Document.replace and editor locks are still authoritative. Reject a
        # stale or now-invalid plan instead of installing a preview snapshot.
        command = GroupPrefabPlaceCommand(prefab, tuple(selected_cell))
        design_change(lambda: editing_context.execute(command, publish=False))
        quarter_pending = None
        canvas.delete('quarter_generation_preview')
        quarter_status_var.set('Quartier inséré avec une seule opération Undo.')
        status_var.set('Quartier inséré : ouvrir ses groupes pour modifier '
                       'routes, bâtiments, objets et décors.')

    @guarded
    def save_quarter_as_prefab():
        prefab = _quarter_choice()
        output = _prefab_library() / prefab_file_slug(prefab['name'])
        overwrite = output.exists() and messagebox.askyesno(
            'Remplacer le modèle', 'Remplacer '+output.name+' ?')
        if output.exists() and not overwrite:
            return
        save_group_prefab(prefab, output, overwrite=overwrite)
        refresh_group_prefabs()
        group_prefab_var.set(output.name)
        draw_prefab_thumbnail()
        quarter_status_var.set('Modèle conservé dans la bibliothèque : '+output.name)

    def _group_tree_mission():
        return next(m for m in doc.data['missions']
                    if m['id'] == mission_var.get())

    def _load_group_cells(gid):
        """Populate one page on expansion, including draggable individual tiles."""
        folder = 'cells:' + gid
        if not group_tree.exists(folder):
            return
        group = next((g for g in _group_tree_mission().get('editor_groups', ())
                      if g['id'] == gid), None)
        if group is None:
            return
        points = group['cells']
        offset = group_tree_cell_counts.get(gid, 0)
        more = 'more:' + gid
        if group_tree.exists(more):
            group_tree.delete(more)
        if offset >= len(points):
            return
        tiles = {tuple(t['pos']): t for t in _group_tree_mission()['board']['tiles']}
        limit = min(offset + 128, len(points))
        for x, y in points[offset:limit]:
            iid = f't:{gid}:{x}:{y}'
            tile = tiles.get((x, y), {})
            detail = tile.get('feature') or tile.get('surface', 'grass')
            group_tree.insert(folder, 'end', iid=iid,
                              text=f'Case ({x},{y}) · {detail}')
            group_tree_items[iid] = ('cell', gid, (x, y))
        group_tree_cell_counts[gid] = limit
        if limit < len(points):
            group_tree.insert(folder, 'end', iid=more,
                              text='Afficher 128 cases supplémentaires…')
            group_tree_items[more] = ('more', gid, None)

    def expand_group_cells(_event=None):
        info = group_tree_items.get(group_tree.focus())
        if info is not None and info[0] == 'cells':
            _load_group_cells(info[1])

    def select_group_in_tree(_event=None):
        nonlocal selected_group_id, selected_tiles, selected_cell
        if group_tree_updating:
            return
        selections = group_tree.selection()
        if not selections:
            return
        focus = selections[-1]
        info = group_tree_items.get(focus)
        if info and info[0] == 'more':
            _load_group_cells(info[1])
            return
        mission = _group_tree_mission()
        groups = [iid[2:] for iid in selections if iid.startswith('g:')]
        if not groups:
            iid = focus
            while iid and not iid.startswith('g:'):
                iid = group_tree.parent(iid)
            if not iid:
                return
            groups = [iid[2:]]
        selected_group_id = groups[-1]
        selected_tiles = set()
        for gid in selected_group_roots(mission, tuple(groups)):
            selected_tiles.update(group_display_cells(mission, gid))
        if selected_tiles:
            selected_cell = min(selected_tiles, key=lambda p: (p[1], p[0]))
        tool_var.set('Sélection')
        refresh()
        if studio is not None:
            studio.workspace.sync_map_selection(
                mission_var.get(), selected_cell, group_id=selected_group_id)
        status_var.set(f'{len(groups)} groupe(s) sélectionné(s) : '
                       f'{len(selected_tiles)} case(s) et emprises.')

    def refresh_group_tree(mission):
        nonlocal group_tree_signature, selected_group_id, group_tree_updating
        rows = mission.editor_groups
        signature = mission.id, json.dumps(rows, sort_keys=True)
        if signature == group_tree_signature:
            return
        expanded = {iid for iid in group_tree_items
                    if group_tree.exists(iid) and group_tree.item(iid, 'open')}
        old_groups = {iid for iid in group_tree_items if iid.startswith('g:')}
        group_tree_signature = signature
        group_tree_updating = True
        try:
            group_tree.delete(*group_tree.get_children())
            group_tree_items.clear()
            group_tree_cell_counts.clear()
            group_tree.insert('', 'end', iid='root:groups',
                              text='Racine / sans groupe — déposer ici', open=True)
            group_tree_items['root:groups'] = ('root', None, None)
            for group in rows:
                gid = group['id']
                iid = 'g:' + gid
                group_tree.insert('root:groups', 'end', iid=iid,
                                  text=group['name']+' ('+gid+')',
                                  open=iid not in old_groups or iid in expanded)
                group_tree_items[iid] = ('group', gid, None)
            for group in rows:
                gid, parent = group['id'], group['parent']
                key = 'g:' + gid
                if parent:
                    group_tree.move(key, 'g:'+parent, 'end')
                if group['cells']:
                    folder = 'cells:' + gid
                    group_tree.insert(key, 'end', iid=folder,
                                      text='Cases / décors : '+str(len(group['cells'])),
                                      open=folder in expanded)
                    group_tree_items[folder] = ('cells', gid, None)
                    if folder in expanded:
                        _load_group_cells(gid)
                    else:
                        group_tree.insert(folder, 'end', iid='more:'+gid,
                                          text='Développer pour voir les cases')
                        group_tree_items['more:'+gid] = ('more', gid, None)
                for field, title in (('unit_ids', 'Personnage'),
                                     ('object_ids', 'Objet'),
                                     ('structure_ids', 'Bâtiment')):
                    for identifier in group[field]:
                        iid = 'm:' + gid + ':' + field + ':' + identifier
                        group_tree.insert(key, 'end', iid=iid,
                                          text=title + ' : ' + identifier)
                        group_tree_items[iid] = (field, gid, identifier)
            if selected_group_id and group_tree.exists('g:'+selected_group_id):
                group_tree.selection_set('g:'+selected_group_id)
            elif selected_group_id:
                selected_group_id = None
        finally:
            group_tree_updating = False

    def _tree_drop_target(iid):
        if iid == 'root:groups':
            return iid, None
        while iid and iid != 'root:groups' and not iid.startswith('g:'):
            iid = group_tree.parent(iid)
        if iid.startswith('g:'):
            return iid, iid[2:]
        if iid == 'root:groups':
            return iid, None
        return None, None

    def tree_drag_cancel(_event=None):
        nonlocal group_tree_drag
        if group_tree_drag:
            previous = group_tree_drag.get('hover')
            if previous and group_tree.exists(previous):
                group_tree.item(previous, tags=())
        was_active = bool(group_tree_drag and group_tree_drag['active'])
        group_tree_drag = None
        group_tree.configure(cursor='')
        if _event is not None and was_active:
            status_var.set('Glisser-déposer annulé.')
            return 'break'

    def tree_drag_press(event):
        nonlocal group_tree_drag
        tree_drag_cancel()
        iid = group_tree.identify_row(event.y)
        info = group_tree_items.get(iid)
        if info and info[0] == 'more':
            _load_group_cells(info[1])
            return 'break'
        if (not info or info[0] == 'root' or
                group_tree.identify_element(event.x, event.y).endswith('indicator')):
            return
        group_tree_drag = {'source': info, 'x': event.x, 'y': event.y,
                           'active': False, 'hover': None, 'target': None,
                           'valid': False}

    def tree_drag_motion(event):
        drag = group_tree_drag
        if not drag:
            return
        if not drag['active']:
            if max(abs(event.x-drag['x']), abs(event.y-drag['y'])) < 6:
                return
            drag['active'] = True
        if event.y < 12:
            group_tree.yview_scroll(-1, 'units')
        elif event.y > group_tree.winfo_height()-12:
            group_tree.yview_scroll(1, 'units')
        hover, target = _tree_drop_target(group_tree.identify_row(event.y))
        if hover == drag['hover']:
            return
        if drag['hover'] and group_tree.exists(drag['hover']):
            group_tree.item(drag['hover'], tags=())
        drag.update(hover=hover, target=target, valid=False)
        if hover is None:
            group_tree.configure(cursor='arrow')
            status_var.set('Déposer sur un groupe ou sur Racine.')
            return
        kind, owner, member = drag['source']
        try:
            if battle or source_pending():
                raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
            check_tree_drop(_group_tree_mission(), owner, kind,
                            member=member, target_group_id=target)
        except RuleError as exc:
            group_tree.item(hover, tags=('group-drop-invalid',))
            group_tree.configure(cursor='arrow')
            status_var.set('Dépôt refusé : ' + str(exc))
        else:
            drag['valid'] = True
            group_tree.item(hover, tags=('group-drop-valid',))
            group_tree.configure(cursor='hand2')
            status_var.set('Déposer pour réorganiser les groupes (Annuler possible).')

    def tree_drag_release(event):
        nonlocal selected_group_id
        drag = group_tree_drag
        if not drag:
            return
        active, valid, source, target = (drag['active'], drag['valid'],
                                         drag['source'], drag['target'])
        # The release may occur on a different row than the last motion event.
        actual_hover, _ = _tree_drop_target(group_tree.identify_row(event.y))
        valid = valid and actual_hover == drag['hover']
        tree_drag_cancel()
        if not active or not valid:
            return
        kind, owner, member = source
        command = EditorGroupTreeDropCommand(
            owner, kind, member, target_group_id=target)
        try:
            if battle or source_pending():
                raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
            design_change(lambda: editing_context.execute(command, publish=False))
        except (RuleError, ValueError) as exc:
            status_var.set('Dépôt refusé : ' + str(exc))
            return
        selected_group_id = target if target is not None else owner
        row_id = 'g:' + selected_group_id
        if group_tree.exists(row_id):
            group_tree.selection_set(row_id)
        refresh()
        status_var.set('Arbre réorganisé vers '+(target or 'racine')+
                       ' ; Annuler / Rétablir disponibles.')

    def set_zoom(delta):
        nonlocal tile_size
        next_size = max(24, min(96, tile_size + delta))
        if next_size != tile_size:
            tile_size = next_size
            refresh()
            status_var.set(f'Zoom carte : {tile_size}px/case')

    @guarded
    def rotate_structure(direction):
        nonlocal structure_turns
        structure_turns = (structure_turns + direction) % 4
        if structure_selection_cell is None:
            tool_var.set('Structure')
        canvas.delete('structure_preview')
        status_var.set(f'Structure {structure_var.get()} : rotation '
                       f'{structure_turns * 90} degrés ; cliquer pour poser.')

    @guarded
    def remove_selected_structure():
        nonlocal structure_selection_cell, structure_selection_id
        if battle is not None:
            raise RuleError('Quitter le playtest avant de supprimer une structure.')
        if source_pending():
            raise RuleError('Appliquer ou abandonner le JSON avant la suppression.')
        target = structure_selection_cell if structure_selection_cell is not None else selected_cell
        design_change(lambda: doc.replace(remove_structure(
            doc.data, mission_var.get(), target)))
        structure_selection_cell = None
        structure_selection_id = None
        status_var.set('Structure supprimée ; annulation possible.')


    def selected_structure():
        if structure_selection_cell is None:
            raise RuleError('Sélectionner d’abord une structure sur la carte.')
        current = structure_at(doc.data, mission_var.get(), structure_selection_cell)
        if structure_selection_id and current.id != structure_selection_id:
            raise RuleError('La structure sélectionnée a changé. La sélectionner à nouveau.')
        return current

    def cancel_structure_drag(_event=None):
        nonlocal structure_drag_from, structure_drag_anchor, structure_drag_hover
        structure_drag_from = None
        structure_drag_anchor = None
        structure_drag_hover = None
        canvas.delete('structure_drag_preview')
        canvas.delete('structure_drag_sprite')

    @guarded
    def nudge_selected_structure(dx, dy):
        nonlocal structure_selection_cell, structure_selection_id
        if tool_var.get() != 'Sélection structure':
            return
        if battle is not None or source_pending():
            raise RuleError('Quitter le playtest et appliquer le JSON avant édition.')
        current = selected_structure()
        anchor = (current.anchor[0] + dx, current.anchor[1] + dy)
        design_change(lambda: editing_context.execute(
            StructureCommand(structure_selection_cell, anchor=anchor),
            publish=False))
        structure_selection_cell = anchor
        structure_selection_id = structure_at(doc.data, mission_var.get(), anchor).id
        status_var.set(f'{current.name} déplacée en {anchor} (Undo disponible).')
        refresh()

    @guarded
    def apply_structure_properties():
        """Update the authored structure, not the next placement template."""
        nonlocal structure_selection_cell
        if battle is not None or source_pending():
            raise RuleError('Quitter le playtest et appliquer le JSON avant édition.')
        current = selected_structure()
        chosen = (structure_var.get(), structure_turns, structure_door_slot())
        if chosen == (current.name, current.turns, current.door_slot):
            status_var.set('Structure inchangée.')
            return
        design_change(lambda: editing_context.execute(
            StructureCommand(structure_selection_cell,
                             name=chosen[0], quarter_turns=chosen[1],
                             door_slot=chosen[2]), publish=False))
        structure_selection_cell = current.anchor
        status_var.set('Propriétés de structure appliquées (Undo disponible).')

    @guarded
    def apply_building_style():
        if battle is not None or source_pending():
            raise RuleError('Quitter le playtest et appliquer le JSON avant édition.')
        building = selected_structure()
        if not building.id:
            raise RuleError('Utiliser une maison ou tour avec identité persistante.')
        design_change(lambda: doc.replace(edit_building_appearance(
            doc.data, mission_var.get(), building.id,
            facade=facade_var.get(), roof=roof_var.get())))
        status_var.set('Façade et toiture modifiées : Undo/Redo disponibles.')

    def choose_window_mode(present):
        window_present_var.set(present)
        tool_var.set('Fenêtre façade')
        status_var.set(('Poser' if present else 'Effacer') +
                       ' une fenêtre : cliquer une case de mur extérieur.')

    @guarded
    def begin_structure_edit(duplicate):
        if battle is not None or source_pending():
            raise RuleError('Quitter le playtest et appliquer le JSON avant édition.')
        current = selected_structure()
        tool_var.set('Dupliquer structure' if duplicate else 'Déplacer structure')
        status_var.set(('Dupliquer' if duplicate else 'Déplacer') +
                       f' {current.name} : choisir la destination sur la carte.')

    def structure_door_slot():
        return 0 if structure_door_var.get() == 'Entrée A' else 1

    def structure_clip():
        return structure_template(structure_var.get(), structure_turns,
                                  door_slot=structure_door_slot())

    def structure_anchor(cursor):
        return placement_origin(structure_clip(), cursor, structure_pivot_var.get())

    def _mission_visual_records():
        mission = next(m for m in doc.data['missions']
                       if m['id'] == mission_var.get())
        return mission.get('structures', ())

    def authored_building_at(cell):
        scene = Content.from_dict(doc.data).missions[mission_var.get()]
        from .iso_architecture import architecture_instances
        instance = next((b for b in architecture_instances(
            scene.board, scene.structures) if cell in b.cells), None)
        if instance is None or not instance.id:
            raise RuleError('Sélectionner une maison/tour/ruine placée avec identité.')
        if instance.name not in ARCHITECTURE_NAMES:
            raise RuleError('Les étages nécessitent un bâtiment habitable.')
        return instance.id

    @guarded
    def create_interior_level():
        if battle or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        sid = authored_building_at(selected_cell)
        level = floor_var.get()
        design_change(lambda: doc.replace(add_interior_floor(
            doc.data, mission_var.get(), sid, level)))
        interior_var.set(True)
        iso_var.set(True)
        active_layer_level.set(level)
        persist_map_view()
        refresh()
        status_var.set(f'Étage N{level} créé pour {sid} (Undo disponible).')

    @guarded
    def remove_interior_level():
        if battle or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        sid = authored_building_at(selected_cell)
        level = floor_var.get()
        design_change(lambda: doc.replace(delete_interior_floor(
            doc.data, mission_var.get(), sid, level)))
        scene = next(m for m in doc.data['missions'] if m['id'] == mission_var.get())
        if (active_layer_level.get() == level and not any(
                floor['level'] == level for floor in scene.get('interior_floors', ()))):
            active_layer_level.set(0)
            persist_map_view()
        status_var.set(f'Étage N{level} supprimé (Undo disponible).')

    @guarded
    def create_level_stair():
        if battle or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        destination = floor_var.get()
        start = [destination-1, *selected_cell]
        end = [destination, *selected_cell]
        design_change(lambda: doc.replace(add_level_link(
            doc.data, mission_var.get(), start, end)))
        status_var.set(f'Escalier bidirectionnel N{destination-1} ↔ N{destination}'
                       f' créé en {selected_cell}.')

    @guarded
    def set_unit_floor():
        if battle or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        level = floor_var.get()
        design_change(lambda: doc.replace(place_unit_on_level(
            doc.data, mission_var.get(), unit_var.get(), level,
            selected_cell)))
        status_var.set(f'{unit_var.get()} positionné à N{level} en {selected_cell}.')

    def select_interior_paint():
        interior_var.set(True)
        iso_var.set(True)
        active_layer_level.set(floor_var.get())
        tool_var.set('Étage intérieur')
        view_options_changed()
        status_var.set('Étage : cliquer sur un plateau surélevé pour éditer le plan visuel.')

    def active_brush():
        return f'height:{level_var.get()}' if brush_var.get() == 'height_set' else brush_var.get()

    def paint_cells(cells, brush):
        if brush == 'unit':
            design_change(lambda: doc.replace(move_unit(
                doc.data, mission_var.get(), unit_var.get(), cells[-1])))
        elif brush == 'object':
            design_change(lambda: doc.replace(move_object(
                doc.data, mission_var.get(), object_var.get(), cells[-1])))
        elif brush in ('zone+', 'zone-'):
            design_change(lambda: doc.replace(paint_deployment(
                doc.data, mission_var.get(), zone_var.get(), cells,
                erase=brush == 'zone-')))
        else:
            # Erase and goal brushes also edit mission objectives and must
            # refresh all Studio consumers synchronously.
            design_change(
                lambda: doc.paint_many(mission_var.get(), cells, brush),
                board_only=brush not in ('erase', 'goal'))

    def event_cell(event):
        px, py = canvas.canvasx(event.x), canvas.canvasy(event.y)
        if (battle and iso_var.get() and iso_geometry is not None
                and action_var.get() in {'level_move', 'level_attack'}
                and travel_level_var.get() > 0):
            scene = battle.mission
            for building in reversed(getattr(iso_geometry, 'architecture_instances', ())):
                floor = next((row for row in scene.interior_floors
                              if row['structure_id'] == building.id and
                              row['level'] == travel_level_var.get()), None)
                if floor is not None:
                    found = floor_hit_test(iso_geometry, building, floor, px, py)
                    if found is not None:
                        return found
            return None
        if (tool_var.get() == 'Étage intérieur' and iso_var.get()
                and iso_geometry is not None):
            scene = Content.from_dict(doc.data).missions[mission_var.get()]
            for building in reversed(getattr(iso_geometry, 'architecture_instances', ())):
                if any(f['structure_id'] == building.id and
                       f['level'] == floor_var.get()
                       for f in scene.interior_floors):
                    # Only the elevated plane is interactive in this tool.
                    floor = next(f for f in scene.interior_floors
                                 if f['structure_id'] == building.id and
                                 f['level'] == floor_var.get())
                    cell = floor_hit_test(iso_geometry, building, floor, px, py)
                    if cell is not None:
                        return cell
            return None
        if iso_var.get() and iso_geometry is not None:
            return iso_geometry.hit_test(px, py)
        return int(px // tile_size), int(py // tile_size)

    def preview_cells(cells, *, tag, color):
        canvas.delete(tag)
        if iso_var.get() and iso_geometry is not None:
            for cell in cells:
                if iso_geometry.board.contains(cell):
                    canvas.create_polygon(*_flatten(iso_geometry.polygon(cell)),
                                          fill='', outline=color, width=3, tags=tag)
        else:
            for x, y in cells:
                canvas.create_rectangle(x*tile_size+3, y*tile_size+3,
                                        (x+1)*tile_size-3, (y+1)*tile_size-3,
                                        outline=color, width=3, tags=tag)

    def clear_placement_preview(_event=None):
        nonlocal structure_preview_key, group_prefab_preview_key
        group_prefab_preview_key = None
        structure_preview_key = None
        nonlocal entity_hover_key
        entity_hover_key = None
        for tag in ('paste_preview', 'fill_preview', 'structure_preview',
                    'structure_group_preview', 'structure_group_ghost',
                    'brush_preview', 'asset_ghost', 'entity_preview',
                    'entity_ghost', 'entity_route', 'entity_source',
                    'entity_target_preview', 'floor_preview',
                    'editor_group_preview', 'prefab_drag_preview'):
            canvas.delete(tag)

    def paste_preview(event):
        nonlocal structure_preview_key, entity_hover_key
        if tool_var.get() == 'Préfab':
            if battle is not None or source_pending():
                clear_placement_preview()
                return
            cell = event_cell(event)
            if cell is None:
                clear_placement_preview()
                return
            try:
                prefab = _chosen_prefab()
            except RuleError as exc:
                clear_placement_preview()
                status_var.set(str(exc))
                return
            preview_group_prefab_at(prefab, cell)
            return
        if structure_drag_from is not None:
            if tool_var.get() != 'Sélection structure':
                cancel_structure_drag()  # Tool changed while dragging.
            else:
                return  # The drag owns its own validated footprint and sprite.
        tool = tool_var.get()
        key = None
        if tool in ('Structure', 'Déplacer structure', 'Dupliquer structure'):
            cursor = event_cell(event)
            key = (tool, cursor, mission_var.get(), structure_var.get(),
                   structure_turns, structure_door_var.get(),
                   structure_pivot_var.get(), structure_selection_cell,
                   id(doc.data))
            if key == structure_preview_key:
                return
        structure_preview_key = key
        if battle:
            clear_placement_preview()
            return
        if tool_var.get() in ('Déplacer entité', 'Dupliquer entité') and entity_target:
            cell = event_cell(event)
            if cell is not None:
                mission = next(m for m in doc.data['missions']
                               if m['id'] == mission_var.get())
                if 0 <= cell[0] < mission['board']['width'] and 0 <= cell[1] < mission['board']['height']:
                    preview_cells([cell], tag='entity_target_preview', color='#2361ff')
            return
        if tool_var.get() == 'Entité' and entity_entry is not None:
            cursor = event_cell(event)
            if cursor is None:
                return
            mission = next(m for m in doc.data['missions']
                           if m['id'] == mission_var.get())
            cells, valid = preview_entity_cells(
                doc.data, mission_var.get(), entity_entry, cursor,
                link=entity_settings.get('link', ''),
                destination=entity_settings.get('destination', ''))
            preview_cells([c for c in cells if 0 <= c[0] < mission['board']['width']
                           and 0 <= c[1] < mission['board']['height']],
                          tag='brush_preview', color='#36a16c' if valid else '#e05252')
            if valid and entity_entry.kind == 'actor':
                facing = entity_settings.get('facing', 'south')
                style = asset_palette.actor_visual_style(entity_entry)
                photo = actor_atlas.sprite(style, facing, 0, tile_size)
                if photo is not None:
                    if iso_var.get() and iso_geometry is not None:
                        cx, cy = iso_geometry.center(cursor)
                        x, y = cx, cy + tile_size*5/54
                    else:
                        x, y = (cursor[0]+.5)*tile_size, (cursor[1]+1)*tile_size
                    canvas.create_image(x, y, image=photo, anchor='s', tags='asset_ghost')
            elif valid and entity_entry.kind == 'object':
                if iso_var.get() and iso_geometry is not None:
                    x, y = iso_geometry.center(cursor)
                else:
                    x, y = (cursor[0]+.5)*tile_size, (cursor[1]+.5)*tile_size
                canvas.create_rectangle(x-11, y-19, x+11, y+1, fill='#9264ab',
                                        outline='#3d2554', tags='asset_ghost')
                canvas.create_text(x, y-23, text=entity_entry.name[:9],
                                   tags='asset_ghost')
            return
        if tool_var.get() == 'Entité' and entity_choice is not None:
            cell = event_cell(event)
            if cell is None:
                clear_placement_preview()
                return
            entry, facing, link, destination, team = entity_choice
            key = (id(doc.data), mission_var.get(), cell, entry.id, facing,
                   link, destination, team, entity_passage_entry,
                   tile_size, iso_var.get())
            if key == entity_hover_key:
                return
            clear_placement_preview()
            mission = next(m for m in doc.data['missions']
                           if m['id'] == mission_var.get())
            from .entity_palette import (
                preview_entity_placement, preview_passage_source)
            is_passage = entry.id == 'object:passage' and destination is None
            if is_passage and entity_passage_entry is None:
                feedback = preview_passage_source(doc.data, mission_var.get(), cell)
            elif is_passage:
                feedback = preview_entity_placement(
                    doc.data, mission_var.get(), entry.id, entity_passage_entry,
                    facing=facing, link=link, destination=cell, team=team)
            else:
                feedback = preview_entity_placement(
                    doc.data, mission_var.get(), entry.id, cell, facing=facing,
                    link=link, destination=destination, team=team)
            entity_hover_key = key
            color = '#36a16c' if feedback.allowed else '#e05252'
            indicated_cells = (cell,) if is_passage and entity_passage_entry is not None else feedback.cells
            inside = [c for c in indicated_cells
                      if 0 <= c[0] < mission['board']['width']
                      and 0 <= c[1] < mission['board']['height']]
            if is_passage and entity_passage_entry is not None:
                if iso_var.get() and iso_geometry is not None:
                    x1, y1 = iso_geometry.center(entity_passage_entry)
                    x2, y2 = iso_geometry.center(cell)
                else:
                    x1, y1 = ((p + .5)*tile_size for p in entity_passage_entry)
                    x2, y2 = ((p + .5)*tile_size for p in cell)
                canvas.create_line(x1, y1, x2, y2, fill=color, width=3,
                                   arrow='last', dash=(5, 3), tags='entity_route')
                preview_cells((entity_passage_entry,), tag='entity_source',
                              color='#2361ff')
            if iso_var.get() and iso_geometry is not None and inside:
                cx, cy = iso_geometry.center(cell)
                if entry.kind in ('actor', 'archetype'):
                    photo = actor_atlas.sprite(entry.style, facing, 0, tile_size)
                else:
                    photo = object_atlas.sprite(entry.id.partition(':')[2], tile_size)
                if photo is not None:
                    canvas.create_image(cx, cy + tile_size * 18 / 54,
                                        image=photo, anchor='s',
                                        tags='entity_ghost')
                else:
                    canvas.create_oval(cx-9, cy-9, cx+9, cy+9,
                                       fill='#9070b1', outline='#4b5261',
                                       tags='entity_ghost')
            preview_cells(inside, tag='entity_preview', color=color)
            if not feedback.allowed:
                status_var.set('Placement refusé : ' + feedback.reason)
            elif is_passage:
                status_var.set('Passage : cliquer la ' +
                               ('sortie' if entity_passage_entry is not None
                                else 'case d’entrée') + '.')
            else:
                status_var.set(entry.label + ' : emplacement valide, cliquer pour poser.')
            return
        clear_placement_preview()
        if tool_var.get() == 'Fenêtre façade':
            cell = event_cell(event)
            if cell is not None:
                try:
                    building = structure_at(doc.data, mission_var.get(), cell)
                    row = next((r for r in _mission_visual_records()
                                if r['id'] == building.id), None)
                    allowed = (row is not None
                               and (cell[0]-building.anchor[0],
                                    cell[1]-building.anchor[1])
                               in exterior_wall_cells(row))
                except RuleError:
                    allowed = False
                preview_cells([cell], tag='brush_preview',
                              color='#36a16c' if allowed else '#e05252')
            return
        if tool_var.get() == 'Étage intérieur':
            cursor = event_cell(event)
            if cursor is not None and iso_geometry is not None:
                canvas.create_polygon(*_flatten(projected_floor_polygon(
                    iso_geometry, cursor, floor_var.get())),
                    fill='', outline='#2361ff', width=3, tags='floor_preview')
            return
        if tool_var.get() in ('Structure', 'Déplacer structure', 'Dupliquer structure'):
            cursor = event_cell(event)
            if cursor is None:
                return
            try:
                clip = structure_clip()
                anchor = placement_origin(clip, cursor, structure_pivot_var.get())
            except RuleError:
                preview_cells([cursor], tag='structure_preview', color='#e05252')
                return
            cells = structure_footprint(clip, anchor)
            mission = next(m for m in doc.data['missions']
                           if m['id'] == mission_var.get())
            width, height = mission['board']['width'], mission['board']['height']
            inside = [c for c in cells
                      if 0 <= c[0] < width and 0 <= c[1] < height]
            try:
                if tool_var.get() == 'Structure':
                    validate_structure_placement(doc.data, mission_var.get(),
                                                 clip, anchor)
                else:
                    validate_structure_edit(
                        doc.data, mission_var.get(), structure_selection_cell,
                        anchor=anchor, name=structure_var.get(),
                        quarter_turns=structure_turns,
                        door_slot=structure_door_slot(),
                        duplicate=tool_var.get() == 'Dupliquer structure')
                color = '#36a16c'
            except RuleError:
                color = '#e05252'
            if iso_var.get() and iso_geometry is not None:
                instance, origin = preview_structure_sprite_position(
                    iso_geometry, structure_var.get(), anchor, structure_turns,
                    door_slot=structure_door_slot())
                loader = (building_atlas if instance.name in ARCHITECTURE_NAMES
                          else fortification_atlas)
                photo = loader.sprite(instance.name, instance.turns, tile_size)
                if photo is not None:
                    # The PNG's top-left is derived from the exact same roof
                    # geometry used to draw the structure after placement.
                    canvas.create_image(*origin, image=photo, anchor='nw',
                                        tags='asset_ghost')
            preview_cells(inside, tag='structure_preview', color=color)
            return
        if tool == 'Pinceau intelligent':
            anchor = event_cell(event)
            if anchor is None:
                return
            try:
                footprint = smart_brush_cells(
                    doc.data, mission_var.get(), [anchor],
                    radius=brush_radius_var.get(), shape=brush_shape_var.get())
            except RuleError:
                return
            preview_cells(footprint, tag='brush_preview', color='#2361ff')
            return
        if tool_var.get() == 'Pinceau' and iso_var.get() and iso_geometry is not None:
            cell = event_cell(event)
            if cell is None or not iso_geometry.board.contains(cell):
                return
            brush = active_brush()
            cx, cy = iso_geometry.center(cell)
            if brush.startswith('surface:'):
                surface = brush.partition(':')[2]
                variant = (cell[0]*37 + cell[1]*19) % 2
                photo = iso_atlas.tile(surface, tile_size, variant=variant)
                if photo is not None:
                    canvas.create_image(cx-tile_size, cy-tile_size/2,
                                        image=photo, anchor='nw', tags='asset_ghost')
            elif brush.startswith('feature:'):
                feature = brush.partition(':')[2]
                photo = iso_props.sprite(feature, tile_size)
                if photo is not None:
                    canvas.create_image(cx, cy+tile_size*18/54,
                                        image=photo, anchor='s', tags='asset_ghost')
            else:
                return
            # Keep the tile selection visible over opaque sprite previews.
            preview_cells([cell], tag='brush_preview', color='#2361ff')
            return
        if tool_var.get() == 'Remplissage':
            anchor = event_cell(event)
            if anchor is not None:
                preview_cells([anchor], tag='fill_preview', color='#36a16c')
            return
        if tool_var.get() != 'Collage' or terrain_clipboard is None:
            return
        anchor = event_cell(event)
        if anchor is None:
            return
        mission = next(m for m in doc.data['missions'] if m['id'] == mission_var.get())
        cells = [(anchor[0]+dx,anchor[1]+dy) for dx,dy in terrain_clipboard.offsets]
        inside = lambda c: (0 <= c[0] < mission['board']['width'] and
                            0 <= c[1] < mission['board']['height'])
        if len(cells) > 512:
            # Bound pointer-motion work on large stamps.
            preview_cells([anchor],tag='paste_preview',
                          color='#36a16c' if all(map(inside, (anchor,
                            (anchor[0]+terrain_clipboard.width-1,
                             anchor[1]+terrain_clipboard.height-1)))) else '#e05252')
            return
        preview_cells([c for c in cells if inside(c)], tag='paste_preview',
                      color='#36a16c' if all(map(inside,cells)) else '#e05252')

    @guarded
    def fill_selection():
        if battle or source_pending():
            raise RuleError('Terminer le combat et appliquer le JSON avant édition.')
        if not selected_tiles:
            raise RuleError('Sélectionner une zone de la carte à remplir.')
        brush = active_brush()
        if not brush.startswith('surface:'):
            raise RuleError('Choisir un sol avant de remplir la sélection.')
        seed = (selected_cell if selected_cell in selected_tiles
                else min(selected_tiles, key=lambda p: (p[1], p[0])))
        count = 0
        def apply():
            nonlocal count
            count = doc.flood_surface(
                mission_var.get(), seed, brush.partition(':')[2],
                allowed_cells=selected_tiles)
        design_change(apply)
        status_var.set(f'Remplissage sélection : {count} case(s) modifiée(s).')

    def sample_appearance(cell, *, decor=False):
        if source_pending():
            raise RuleError('Appliquer ou abandonner le JSON avant la pipette.')
        mission = next(m for m in doc.data['missions'] if m['id'] == mission_var.get())
        tile = next((t for t in mission['board']['tiles']
                     if tuple(t['pos']) == cell), {})
        if decor:
            feature = tile.get('feature', '')
            feature_var.set(feature if feature else 'tree')
            brush_var.set('feature:' + feature if feature else 'feature-erase')
            status_var.set('Pipette décor : ' + (feature or 'aucun'))
        else:
            surface = tile.get('surface', 'grass')
            surface_var.set(surface)
            brush_var.set('surface:' + surface)
            status_var.set('Pipette sol : ' + surface)
        tool_var.set('Pinceau')
        refresh()

    @guarded
    def click(event):
        nonlocal selected_cell, stroke_cells, stroke_before, stroke_redo, rectangle_anchor, selection_additive, entity_target
        nonlocal structure_turns, structure_selection_cell, structure_selection_id
        nonlocal structure_drag_from, structure_drag_anchor, structure_drag_duplicate
        nonlocal entity_passage_entry
        cancel_structure_drag()
        canvas.focus_set()
        stroke_cells = []
        selected_cell = event_cell(event)
        if selected_cell is None:
            return
        validate_selection(doc.data, mission_var.get(), [selected_cell])
        editing_context.selection.set(mission_var.get(), selected_cell,
                                      selected_tiles, publish=False)
        tool, brush = tool_var.get(), active_brush()
        canvas.delete('stroke_preview')
        if battle:
            refresh()
        elif tool == 'Collage':
            paste_at(selected_cell)
        elif tool == 'Préfab':
            place_chosen_prefab(anchor=selected_cell)
        elif tool == 'Sélection structure':
            if source_pending():
                raise RuleError('Appliquer ou abandonner le JSON avant édition.')
            current = structure_at(doc.data, mission_var.get(), selected_cell)
            structure_selection_cell = current.anchor
            structure_selection_id = current.id or None
            structure_var.set(current.name)
            structure_turns = current.turns
            structure_door_var.set('Entrée B' if current.door_slot else 'Entrée A')
            row = next((r for r in _mission_visual_records()
                        if r['id'] == current.id), None)
            settings = building_appearance(row) if row is not None else DEFAULT_APPEARANCE
            facade_var.set(settings['facade'])
            roof_var.set(settings['roof'])
            structure_drag_from = selected_cell
            structure_drag_anchor = None
            structure_drag_duplicate = bool(event.state & 0x0001)
            status_var.set(f'{current.name} sélectionnée : {current.id or "ancienne structure"}'
                           f' en {current.anchor}. Glisser pour déplacer, '
                           'Maj+glisser pour dupliquer, flèches pour ajuster.')
            refresh()
        elif tool in ('Déplacer structure', 'Dupliquer structure'):
            if source_pending():
                raise RuleError('Appliquer ou abandonner le JSON avant édition.')
            current = selected_structure()
            anchor = structure_anchor(selected_cell)
            duplicate = tool == 'Dupliquer structure'
            design_change(lambda: editing_context.execute(
                StructureCommand(
                    structure_selection_cell, anchor=anchor,
                    name=structure_var.get(), quarter_turns=structure_turns,
                    door_slot=structure_door_slot(), duplicate=duplicate),
                publish=False))
            structure_selection_cell = anchor
            structure_selection_id = structure_at(doc.data, mission_var.get(), anchor).id
            tool_var.set('Sélection structure')
            status_var.set(('Structure dupliquée' if duplicate else 'Structure déplacée')
                           + f' en {anchor}. Annuler/Rétablir disponibles.')
            refresh()
        elif tool == 'Fenêtre façade':
            if source_pending():
                raise RuleError('Appliquer ou abandonner le JSON avant édition.')
            sid = authored_building_at(selected_cell)
            design_change(lambda: doc.replace(set_building_window(
                doc.data, mission_var.get(), sid, selected_cell,
                present=window_present_var.get())))
            status_var.set('Ouverture de façade enregistrée (visuelle uniquement).')
        elif tool == 'Inspecter entité':
            open_entity_inspector(selected_cell)
            return
        elif tool in ('Déplacer entité', 'Dupliquer entité'):
            nonlocal_entity_target = entity_target
            if nonlocal_entity_target is None:
                raise RuleError('Sélectionner une entité à déplacer ou dupliquer.')
            operation, kind, identifier, mid = nonlocal_entity_target
            if mid != mission_var.get() or (operation == 'move') != (tool == 'Déplacer entité'):
                raise RuleError('La sélection de départ ne correspond pas à cette mission.')
            if battle or source_pending():
                raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
            design_change(lambda: editing_context.execute(
                EntityCommand(operation, kind, identifier,
                              cell=selected_cell), publish=False))
            entity_target = None
            tool_var.set('Inspecter entité')
            status_var.set(f'{kind} {identifier} : {operation} vers {selected_cell}; annulation possible.')
        elif tool == 'Entité' and entity_entry is not None:
            if source_pending():
                raise RuleError('Appliquer ou abandonner le JSON avant la pose.')
            if entity_entry is None:
                raise RuleError('Choisir un acteur ou objet dans la bibliothèque.')
            design_change(lambda: doc.replace(place_palette_entity(
                doc.data, mission_var.get(), entity_entry, selected_cell,
                **entity_settings)))
            status_var.set(f'{entity_entry.name} placé en {selected_cell} '
                           '(annulation et sauvegarde disponibles).')
        elif tool == 'Entité':
            if battle or source_pending():
                raise RuleError('Terminer le playtest et appliquer le JSON avant la pose.')
            if entity_choice is None:
                raise RuleError('Choisir un acteur ou objet dans la palette.')
            from .entity_palette import place_entity, preview_passage_source
            entry, facing, link, destination, team = entity_choice
            if entry.id == 'object:passage' and destination is None:
                if entity_passage_entry is None:
                    checked = preview_passage_source(
                        doc.data, mission_var.get(), selected_cell)
                    if not checked.allowed:
                        raise RuleError(checked.reason)
                    entity_passage_entry = selected_cell
                    refresh()
                    status_var.set('Entrée ' + str(selected_cell) +
                                   ' sélectionnée. Cliquer la sortie ou Échap.')
                    return
                entrance = entity_passage_entry
                design_change(lambda: doc.replace(place_entity(
                    doc.data, mission_var.get(), entry.id, entrance,
                    facing=facing, link=link, destination=selected_cell,
                    team=team)))
                entity_passage_entry = None
                status_var.set('Passage ' + str(entrance) + ' → ' +
                               str(selected_cell) + ' créé ; Undo/Redo disponible.')
            else:
                design_change(lambda: doc.replace(place_entity(
                    doc.data, mission_var.get(), entry.id, selected_cell,
                    facing=facing, link=link, destination=destination,
                    team=team)))
                status_var.set(f'{entry.label} placé en {selected_cell} ; '
                               'Undo/Redo et sauvegarde disponibles.')
        elif tool == 'Étage intérieur':
            if source_pending():
                raise RuleError('Appliquer le JSON avant de modifier l’étage.')
            sid = authored_building_at(selected_cell)
            action = floor_action_var.get()
            options = ({'surface': floor_surface_var.get()} if action == 'Sol' else
                       {'feature': floor_feature_var.get()} if action == 'Mobilier' else
                       {'present': False} if action == 'Trou' else
                       {'present': True} if action == 'Restaurer' else None)
            if options is None:
                raise RuleError('Outil étage invalide')
            design_change(lambda: doc.replace(edit_interior_tile(
                doc.data, mission_var.get(), sid, floor_var.get(),
                selected_cell, **options)))
            status_var.set(f'Étage {floor_var.get()} : {action} en {selected_cell}.')
        elif tool == 'Structure':
            if source_pending():
                raise RuleError('Appliquer ou abandonner le JSON avant la pose.')
            name = structure_var.get()
            rotation = structure_turns
            door = structure_door_slot()
            anchor = structure_anchor(selected_cell)
            design_change(lambda: doc.replace(place_structure(
                doc.data, mission_var.get(), name, anchor, rotation,
                door_slot=door)))
            status_var.set(f'Structure {name} posée en {anchor} '
                           f'(rotation {rotation * 90} degrés, pivot '
                           f'{structure_pivot_var.get()}).')
        elif tool == 'Remplissage':
            if not brush.startswith('surface:'):
                raise RuleError('Choisir un sol dans la palette avant le remplissage.')
            if source_pending():
                raise RuleError('Appliquer ou abandonner le JSON avant de remplir.')
            count = 0
            def fill():
                nonlocal count
                count = doc.flood_surface(mission_var.get(), selected_cell,
                                         brush.partition(':')[2])
            design_change(fill)
            status_var.set(f'Remplissage : {count} case(s) modifiée(s).')
        elif tool == 'Pipette sol':
            sample_appearance(selected_cell)
        elif tool == 'Pipette décor':
            sample_appearance(selected_cell, decor=True)
        elif tool in ('Sélection', 'Rectangle') and (tool == 'Sélection' or brush not in ('unit', 'object')):
            rectangle_anchor = selected_cell
            selection_additive = bool(event.state & 0x0001)
            stroke_cells = [selected_cell]
            preview_cells([selected_cell],tag='stroke_preview',color='#2a61ff')
        else:
            rectangle_anchor = None
            stroke_cells = [selected_cell]
            stroke_before = deepcopy(doc.data)
            stroke_redo = list(doc.redo_stack)
            # Click immediately applies the first cell (legacy Tk interaction).
            if tool == 'Pinceau intelligent':
                design_change(lambda: doc.smart_paint(
                    mission_var.get(), [selected_cell], brush,
                    radius=brush_radius_var.get(), shape=brush_shape_var.get()))
            else:
                paint_cells([selected_cell], brush)

    def drag(event):
        nonlocal structure_drag_anchor, structure_drag_hover
        if not battle and tool_var.get() == 'Sélection structure' and structure_drag_from is not None:
            cell = event_cell(event)
            if cell is None:
                structure_drag_anchor = None
                structure_drag_hover = None
                canvas.delete('structure_drag_preview')
                canvas.delete('structure_drag_sprite')
                return
            if cell == structure_drag_hover:
                return
            structure_drag_hover = cell
            current = selected_structure()
            anchor = (current.anchor[0] + cell[0] - structure_drag_from[0],
                      current.anchor[1] + cell[1] - structure_drag_from[1])
            structure_drag_anchor = anchor if cell != structure_drag_from else None
            canvas.delete('structure_drag_preview')
            canvas.delete('structure_drag_sprite')
            if structure_drag_anchor is None:
                return
            clip = structure_template(current.name, current.turns,
                                      door_slot=current.door_slot)
            mission = next(m for m in doc.data['missions'] if m['id'] == mission_var.get())
            width, height = mission['board']['width'], mission['board']['height']
            footprint = structure_footprint(clip, anchor)
            inside = [c for c in footprint
                      if 0 <= c[0] < width and 0 <= c[1] < height]
            try:
                validate_structure_edit(
                    doc.data, mission_var.get(), structure_selection_cell,
                    anchor=anchor, duplicate=structure_drag_duplicate)
                color = '#36a16c'
            except RuleError:
                color = '#e05252'
            if iso_var.get() and iso_geometry is not None:
                instance, origin = preview_structure_sprite_position(
                    iso_geometry, current.name, anchor, current.turns,
                    door_slot=current.door_slot)
                loader = (building_atlas if instance.name in ARCHITECTURE_NAMES
                          else fortification_atlas)
                photo = loader.sprite(instance.name, instance.turns, tile_size)
                if photo is not None:
                    canvas.create_image(*origin, image=photo, anchor='nw',
                                        tags='structure_drag_sprite')
            preview_cells(inside, tag='structure_drag_preview', color=color)
            return
        if battle or not stroke_cells or tool_var.get() == 'Collage':
            return
        if tool_var.get() not in ('Sélection', 'Rectangle') and brush_var.get() in ('unit', 'object'):
            return
        cell = event_cell(event)
        if cell is None:
            return
        mission = next(m for m in doc.data['missions'] if m['id'] == mission_var.get())
        if not (0 <= cell[0] < mission['board']['width'] and
                0 <= cell[1] < mission['board']['height']):
            return
        if tool_var.get() in ('Sélection', 'Rectangle') and rectangle_anchor is not None:
            stroke_cells[:] = [cell]
            canvas.delete('stroke_preview')
            ax, ay = rectangle_anchor
            x1, x2 = sorted((ax, cell[0]))
            y1, y2 = sorted((ay, cell[1]))
            preview_cells(((x,y) for y in range(y1,y2+1) for x in range(x1,x2+1)),
                          tag='stroke_preview',color='#2a61ff')
        elif cell != stroke_cells[-1]:
            for point in list(_line_cells(stroke_cells[-1],cell))[1:]:
                if point not in stroke_cells:
                    stroke_cells.append(point)
            if tool_var.get() == 'Pinceau intelligent':
                footprint = smart_brush_cells(
                    doc.data, mission_var.get(), stroke_cells,
                    radius=brush_radius_var.get(), shape=brush_shape_var.get())
                if len(footprint) <= 512:
                    preview_cells(footprint, tag='stroke_preview', color='#2a61ff')
                else:
                    preview_cells([cell], tag='stroke_preview', color='#2a61ff')
            else:
                preview_cells(stroke_cells,tag='stroke_preview',color='#2a61ff')

    @guarded
    def end_stroke(_event):
        nonlocal selected_cell, stroke_cells, stroke_before, stroke_redo, rectangle_anchor, selected_tiles
        nonlocal structure_selection_cell, structure_selection_id
        tool, brush = tool_var.get(), active_brush()
        if tool != 'Sélection structure' and structure_drag_from is not None:
            cancel_structure_drag()
        if not battle and tool == 'Sélection structure' and structure_drag_from is not None:
            anchor = structure_drag_anchor
            duplicate = structure_drag_duplicate
            cancel_structure_drag()
            if anchor is None:
                return  # A click selects; only a real drag commits a change.
            current = selected_structure()
            design_change(lambda: editing_context.execute(
                StructureCommand(structure_selection_cell, anchor=anchor,
                                 duplicate=duplicate), publish=False))
            structure_selection_cell = anchor
            structure_selection_id = structure_at(doc.data, mission_var.get(), anchor).id
            selected_cell = anchor
            status_var.set(('Copie' if duplicate else 'Déplacement') +
                           f' de {current.name} en {anchor} (Undo disponible).')
            refresh()
            return
        if not battle and tool == 'Sélection' and rectangle_anchor is not None and stroke_cells:
            cells = cells_in_rectangle(doc.data, mission_var.get(), rectangle_anchor,
                                       stroke_cells[-1])
            selected_tiles = selected_tiles | set(cells) if selection_additive else set(cells)
            selected_cell = stroke_cells[-1]
            refresh(selection_only=True)
            if studio is not None:
                studio.workspace.sync_map_selection(
                    mission_var.get(), selected_cell, cells=selected_tiles)
        elif not battle and tool == 'Rectangle' and rectangle_anchor is not None and stroke_cells and brush not in ('unit', 'object'):
            end = stroke_cells[-1]
            selected_cell = end
            if brush in ('zone+', 'zone-'):
                paint_cells(cells_in_rectangle(doc.data, mission_var.get(),
                                               rectangle_anchor, end), brush)
            else:
                design_change(lambda: doc.paint_rectangle(mission_var.get(),
                                                          rectangle_anchor, end, brush))
        elif not battle and tool in ('Pinceau', 'Pinceau intelligent') and brush not in ('unit', 'object') and len(stroke_cells) > 1:
            selected_cell = stroke_cells[-1]
            # Validate the complete stroke from the unmodified snapshot. An
            # invalid destination rolls back the first-click preview too.
            try:
                temporary = Document(Content.from_dict(
                    stroke_before, rules=authored_rules_for_document(stroke_before)))
                if tool == 'Pinceau intelligent':
                    temporary.smart_paint(
                        mission_var.get(), stroke_cells, brush,
                        radius=brush_radius_var.get(), shape=brush_shape_var.get())
                else:
                    temporary.paint_many(mission_var.get(), stroke_cells, brush)
            except (RuleError, ValueError, KeyError):
                doc.data = stroke_before
                if doc.undo_stack:
                    doc.undo_stack.pop()
                doc.redo_stack = stroke_redo
                refresh_source()
                refresh()
                raise
            else:
                ensure_unlocked(stroke_before, temporary.data, map_view_data)
                doc.data = temporary.data
                refresh_source()
                refresh(board_only=brush not in ('erase', 'goal'))
        if stroke_before is not None and studio is not None:
            studio.capture_history()
        stroke_cells = []
        stroke_before = None
        stroke_redo = None
        rectangle_anchor = None
        canvas.delete('stroke_preview')


    def refresh_minimap_viewport():
        # Pan/scroll and selection-only refreshes never repaint static tiles.
        mini_canvas.delete('viewport')
        size = 184
        left, right = canvas.xview()
        top, bottom = canvas.yview()
        mini_canvas.create_rectangle(
            left*size, top*size, right*size, bottom*size,
            outline='#2369ac', width=2, tags='viewport')

    def draw_minimap(board, mission, units):
        """Static minimap only changes with authored scene, layers or combat."""
        # A combat frame is dynamic and must never be reused by authoring revision.
        key = (editor_content_cache.generation, mission.id,
               board.width, board.height,
               tuple((name, layer_vars[name].get())
                     for name in ('Terrain', 'Relief', 'Déploiement',
                                  'Objectifs', 'Objets', 'Unités')),
               object() if battle is not None else None)
        redraw = minimap_background.needs_background(key, mini_canvas)
        if redraw:
            mini_canvas.delete('all')
            size = 184
            sx, sy = size / board.width, size / board.height
            mini_canvas.create_rectangle(0, 0, size, size, fill='#e4e4e4',
                                         outline='#999999')
            if layer_vars['Terrain'].get() or layer_vars['Relief'].get():
                for (x, y), tile in board.tiles.items():
                    color = None
                    if layer_vars['Terrain'].get():
                        if tile.surface != 'grass': color = SURFACE_COLORS[tile.surface]
                        if tile.blocked and tile.surface != 'water': color = '#515151'
                        elif tile.hazard: color = '#e3a187'
                        elif tile.cover: color = '#a4c599'
                        elif tile.cost > 1: color = '#b8a37c'
                    if color is None and layer_vars['Relief'].get() and tile.height:
                        color = '#b7b9d2'
                    if color:
                        mini_canvas.create_rectangle(x*sx,y*sy,(x+1)*sx,(y+1)*sy,
                                                     fill=color,outline=color)
            if layer_vars['Déploiement'].get():
                for zone in mission.deployment:
                    for x, y in zone['cells']:
                        mini_canvas.create_rectangle(x*sx,y*sy,(x+1)*sx,(y+1)*sy,
                                                     fill='#a5dbe6',outline='')
            if layer_vars['Objectifs'].get():
                for x, y in mission.goal:
                    mini_canvas.create_rectangle(x*sx,y*sy,(x+1)*sx,(y+1)*sy,
                                                 fill='#d8c86e',outline='')
            if layer_vars['Objets'].get():
                for obj in mission.objects:
                    x,y = obj['pos']
                    mini_canvas.create_oval(x*sx,y*sy,(x+1)*sx,(y+1)*sy,
                                            fill='#7047ad',outline='')
            if layer_vars['Unités'].get():
                for actor in units:
                    x,y = actor.pos
                    color = '#27649c' if actor.team == 'player' else '#bb503b'
                    mini_canvas.create_oval(x*sx,y*sy,(x+1)*sx,(y+1)*sy,
                                            fill=color,outline='')
        refresh_minimap_viewport()
        minimap_background.complete(key, mini_canvas, background_redrawn=redraw)

    def minimap_navigate(event):
        # Navigating changes only the main canvas view and its viewport overlay.
        canvas.xview_moveto(max(0.0, min(1.0, event.x / 184 - 0.2)))
        canvas.yview_moveto(max(0.0, min(1.0, event.y / 184 - 0.2)))
        refresh_minimap_viewport()

    @guarded
    def open_selected_entity(kind):
        if battle is not None:
            raise RuleError('Revenir en mode Éditer pour ouvrir la fiche.')
        mission = next(m for m in doc.data['missions']
                       if m['id'] == mission_var.get())
        entries = (mission['units'] if kind == 'unit'
                   else mission.get('objects', []))
        chosen = next((item for item in entries
                       if tuple(item['pos']) == selected_cell), None)
        if chosen is None:
            raise RuleError('Aucun élément de ce type sur la case.')
        studio.focus_map_entity(kind, chosen['id'])

    @guarded
    def open_selected_gate_event():
        if battle is not None:
            raise RuleError('Revenir en mode Éditer pour lier un événement.')
        mission = next(m for m in doc.data['missions']
                       if m['id'] == mission_var.get())
        selected = next((item for item in mission.get('objects', ())
                         if tuple(item['pos']) == selected_cell
                         and item['kind'] in ('door', 'switch')), None)
        if selected is None:
            raise RuleError('Sélectionner une porte ou un levier sur la carte.')
        studio.focus_gate_event(
            selected['id'] if selected['kind'] == 'door' else selected['link'])

    def refresh(*args, views=None, selection_only=False, board_only=False):
        nonlocal selected_cell, campaign_battle, selection_mission, selected_tiles, iso_geometry
        nonlocal selected_group_id, group_tree_signature
        nonlocal structure_selection_cell, structure_selection_id, structure_preview_key
        nonlocal entity_hover_key, entity_passage_entry
        ui_started = begin_ui()
        structure_preview_key = None
        entity_hover_key = None
        if campaign_battle and battle is not None and battle.result in ('victory', 'defeat'):
            from .narrative import StoryBook
            story = StoryBook(studio.project.story, Content.from_dict(doc.data),
                              studio.project.campaigns)
            route = battle.result == 'victory' and battle.mission.id in story.after
            earned = campaign_session.finish(battle, unlock_next=not route)
            if earned and route:
                story.after_victory(campaign_session, battle.mission.id)
            campaign_battle = False
            status_var.set('Résultat de campagne enregistré : ' + battle.result)
        mids = [m['id'] for m in doc.data['missions']]
        mission_box['values'] = mids
        if mission_var.get() not in mids:
            mission_var.set(mids[0])
        if selection_mission != mission_var.get():
            apply_saved_map_view()
            selected_tiles.clear()
            tree_drag_cancel()
            selected_group_id = None
            group_tree_signature = None
            structure_selection_cell = None
            structure_selection_id = None
            cancel_structure_drag()
            entity_passage_entry = None
            selection_mission = mission_var.get()
        if structure_selection_id is not None:
            mission_row = next(m for m in doc.data['missions']
                               if m['id'] == mission_var.get())
            record = next((row for row in mission_row.get('structures', ())
                           if row['id'] == structure_selection_id), None)
            if record is None:
                structure_selection_cell = None
                structure_selection_id = None
            else:
                structure_selection_cell = tuple(record['anchor'])
        content = editor_content_cache.get(doc.data)
        mission = battle.mission if battle else content.missions[mission_var.get()]
        refresh_group_tree(content.missions[mission_var.get()])
        board = battle.board if battle else mission.board
        units = battle.units if battle else mission.units
        unit_box['values'] = [u.id for u in units if not battle or not battle.deploying
                              or u.team == 'player' and u.alive]
        if unit_var.get() not in unit_box['values']:
            unit_var.set(unit_box['values'][0] if unit_box['values'] else '')
        object_box['values'] = [o['id'] for o in mission.objects]
        if object_var.get() not in object_box['values']:
            object_var.set(object_box['values'][0] if object_box['values'] else '')
        # Bound the work to the selection, not all 16,384 board cells.
        selected_tiles.intersection_update(
            {c for c in selected_tiles if board.contains(c)})
        editing_context.selection.set(mission_var.get(), selected_cell,
                                      selected_tiles, publish=False)
        if views is None or RENDERER in views:
            if iso_var.get():
                # Editor and its actual Battle use the identical terrain/asset
                # scene. Intents come from battle_frame: no game-rule duplication.
                clear_placement_preview()
                canvas.delete('stroke_preview')
                live = battle_frame(battle, selected_cell) if battle else None
                iso_geometry = editor_renderer.draw(
                    board, mission, units, cell_size=tile_size,
                    layers={**{name: var.get() for name, var in layer_vars.items()},
                            'Intérieurs': interior_var.get(),
                            'Étage actif': (battle.unit_levels.get(battle.active_id, 0)
                                            if battle and battle.active_id else
                                            active_layer_level.get()
                                            if interior_var.get()
                                            and layer_vars['Étages'].get() else 0)},
                    selected_cell=selected_cell, selected_tiles=selected_tiles,
                    reachable=live.reachable if live else (),
                    danger=live.danger if live else (),
                    active_id=live.active_id if live else None,
                    atlas=iso_atlas, prop_atlas=iso_props,
                    building_atlas=building_atlas,
                    fortification_atlas=fortification_atlas,
                    actor_atlas=actor_atlas, object_atlas=object_atlas,
                    unit_levels=battle.unit_levels if battle else None,
                    scene_revision=None if battle else
                    (editor_content_cache.generation, mission.id))
            else:
                iso_geometry = None
                editor_renderer.invalidate()
                canvas.configure(scrollregion=(0, 0, board.width * tile_size, board.height * tile_size))
                reachable = battle.reachable() if battle else {}
                deployment_cells = ({tuple(c) for z in mission.deployment for c in z['cells']}
                                    if layer_vars['Déploiement'].get() else set())
                danger_cells = ({tuple(c) for o in mission.objects if o['kind'] == 'defense'
                                 and not o.get('disabled') and o.get('charges', 2) > 0
                                 for c in o['cells']} if layer_vars['Objets'].get() else set())
                for c in board.cells():
                    t = board.tile(c)
                    color = '#dddddd'
                    if layer_vars['Terrain'].get():
                        color = SURFACE_COLORS[t.surface]
                        if t.cost > 1: color = '#b29f78'
                        if t.cover: color = '#b0c9a8'
                        if t.hazard: color = '#eead93'
                        if t.blocked and t.surface != 'water': color = '#555555'
                    if layer_vars['Relief'].get() and t.height: color = '#c3c3df'
                    if c in deployment_cells and (not battle or battle.deploying): color = '#a8dce8'
                    if c in mission.goal and layer_vars['Objectifs'].get(): color = '#d7c469'
                    if c in danger_cells: color = '#f0a181'
                    x, y = c[0] * tile_size, c[1] * tile_size
                    canvas.create_rectangle(x, y, x+tile_size, y+tile_size, fill=color,
                                            outline='#288949' if c in reachable else '#999999', width=3 if c in reachable else 1)
                    if t.height and layer_vars['Relief'].get():
                        canvas.create_text(x+8, y+8, text=str(t.height), anchor='nw')
                    if t.hazard and layer_vars['Terrain'].get():
                        canvas.create_text(x+tile_size-3, y+tile_size-3, text=f'!{t.hazard}', anchor='se')
                    if t.feature and layer_vars['Décors'].get():
                        canvas.create_text(x+tile_size//2, y+tile_size//2,
                                           text=t.feature[:5], fill='#293e30',
                                           font=('TkDefaultFont', 8, 'bold'))
                for obj in mission.objects if layer_vars['Objets'].get() else ():
                    x,y = obj['pos']
                    if obj['kind'] == 'passage':
                        dx,dy = obj['destination']
                        canvas.create_line((x+.5)*tile_size,(y+.5)*tile_size,
                                           (dx+.5)*tile_size,(dy+.5)*tile_size,
                                           fill='#6e42a1', width=2, arrow='last',
                                           dash=() if obj.get('enabled', True) else (4, 3))
                    canvas.create_text(x*tile_size+tile_size//2,y*tile_size+8,text=obj['kind'][:2], fill='#5b3294')
                relic = battle.relic_pos if battle else mission.relic
                if relic is not None and layer_vars['Objectifs'].get():
                    canvas.create_text(relic[0]*tile_size+tile_size//2,relic[1]*tile_size+tile_size//2,text='R',fill='#a06c00',font=('TkDefaultFont',16))
                for u in units if layer_vars['Unités'].get() else ():
                    x,y = (v*tile_size for v in u.pos)
                    color = '#cce2ff' if u.team == 'player' else '#ffc8bc'
                    if not u.alive: color = '#aaaaaa'
                    canvas.create_oval(x+6,y+10,x+tile_size-6,y+tile_size-4,fill=color,outline='#111111',width=3 if battle and u.id==battle.active_id else 1)
                    canvas.create_text(x+tile_size//2,y+tile_size//2,text=u.name[:3])
                    canvas.create_text(x+tile_size//2,y+tile_size-10,text=str(u.hp),font=('TkDefaultFont',8))
                for sx, sy in sorted(selected_tiles):
                    canvas.create_rectangle(sx*tile_size+4, sy*tile_size+4,
                                            (sx+1)*tile_size-4, (sy+1)*tile_size-4,
                                            outline='#1f6e9a', width=3, tags='selection')
                x,y = (v*tile_size for v in selected_cell)
                canvas.create_rectangle(x+2,y+2,x+tile_size-2,y+tile_size-2,outline='#002fcc',width=2)
        if views is None or INSPECTOR in views:
            inspected_tile = board.tile(selected_cell) if board.contains(selected_cell) else None
            mode_var.set('MODE : PLAYTEST (édition verrouillée)' if battle else 'MODE : ÉDITION')
            selected_units = [u for u in units if tuple(u.pos) == selected_cell]
            selected_objects = [o for o in mission.objects if tuple(o['pos']) == selected_cell]
            if selected_units:
                heading = 'PERSONNAGE — ' + ', '.join(u.name for u in selected_units)
            elif selected_objects:
                heading = 'OBJET — ' + ', '.join(o['id'] for o in selected_objects)
            else:
                heading = 'TERRAIN — case ' + str(selected_cell)
            # Switching to a smaller mission may invalidate the previous
            # cursor position; keep the shared inspector on a valid tile.
            if not board.contains(selected_cell):
                selected_cell = (0, 0)
            context = inspect_map(doc.data, mission_var.get(),
                                  selected_cell, selected_tiles)
            text = (context.title + '\n' + context.detail +
                    f'\nObjectif : {mission.objective}\n')
            for actor in selected_units:
                text += (f'Acteur {actor.id} • {actor.team} • '
                         f'PV {actor.hp}/{actor.max_hp} • CT {actor.ct}\n')
            for obj in selected_objects:
                text += f'Objet {obj["id"]} : {obj["kind"]}\n'
            actor_focus.configure(state='normal' if selected_units and not battle else 'disabled')
            object_focus.configure(state='normal' if selected_objects and not battle else 'disabled')
            event_focus.configure(state='normal' if not battle and
                                  any(o['kind'] in ('door', 'switch')
                                      for o in selected_objects) else 'disabled')
            if inspected_tile is not None:
                text += (f'Surface : {inspected_tile.surface} | Décor : '
                         f'{inspected_tile.feature or "aucun"} | Niveau : {inspected_tile.height}\n')
            if iso_var.get() and board.contains(selected_cell):
                from .iso_interiors import interior_plan
                building = next((instance for instance in getattr(
                    iso_geometry, 'architecture_instances', ())
                    if selected_cell in instance.cells), None)
                if building is not None and building.name in ARCHITECTURE_NAMES:
                    room = interior_plan(board, building)
                    text += (f'Intérieur : {building.name} ({building.id or "hérité"})'
                             f' | {len(room.floors)} cases accessibles'
                             f' | {len(room.walls)} murs'
                             f' | {len(room.furnishings)} décors'
                             f' | entrée {"visible" if room.doors else "obstruée"}\n')
                    floors = [f for f in mission.interior_floors
                              if f['structure_id'] == building.id]
                    if floors:
                        text += ('Plateaux visuels (non jouables) : '
                                 + ', '.join(f'N{f["level"]} ({len(f["tiles"])} cases)'
                                             for f in sorted(floors, key=lambda f: f['level']))
                                 + '\n')
            for obj in selected_objects:
                if obj['kind'] == 'defense':
                    text += f"Défense {obj['id']} ({obj['team']}) : {obj.get('charges',2)} charges, dégâts {obj.get('power',15)}, {'sabotée' if obj.get('disabled') else 'active'}\n"
                if obj['kind'] == 'passage':
                    text += f"Passage {obj['id']} : {obj['pos']} → {obj['destination']} ({'installé' if obj.get('enabled',True) else 'à installer'})\n"
            if battle:
                text += f'Tick : {battle.tick} | Résultat : {battle.result or "en cours"}\nTenue : {battle.hold_ticks}/{mission.target_ticks}\n'
                if mission.objective == 'crown':
                    text += f'Couronne : {battle.carrier or battle.relic_pos}\n'
                if battle.deploying:
                    text += 'DÉPLOIEMENT — horloge arrêtée.\nChoisir une unité, une case bleue et son orientation, puis deploy / Exécuter.\nChoisir start_battle / Exécuter pour lancer l’assaut.\n'
                    action_box['values'] = ['deploy', 'start_battle']
                    if action_var.get() not in action_box['values']: action_var.set('deploy')
                if battle.active:
                    u = battle.active
                    text += f'Actif : {u.name} ({u.team})\nPV {u.hp}/{u.max_hp} | MP {u.mp}/{u.max_mp} | CT {u.ct}\nDéplacement : {"utilisé" if u.moved else "libre"}\nAction : {"utilisée" if u.acted else "libre"}\n'
                    actions = ['move','attack',*u.skills,'item:potion','item:ether','item:phoenix',*['object:'+o['id'] for o in mission.objects],*available_operations(battle,u)]
                    if mission.level_links:
                        actions = (['level_move', 'level_attack', 'attack']
                                   if battle.unit_levels.get(u.id, 0) else
                                   ['level_move', 'level_attack', *actions])
                    action_box['values'] = actions
                    if action_var.get() not in actions: action_var.set('move')
                    if action_var.get() not in {'move'} and not action_var.get().startswith(('item:','object:','siege-attack:','repair-siege:')):
                        try:
                            forecast = battle.forecast(action_var.get(), selected_cell)
                            text += '\nPrévision immédiate (avant réactions) :\n'
                            text += '\n'.join(f'{r["unit"]}: {r["kind"]} {r["amount"]} {r["status"]} ({r["chance"]:.0%})' for r in forecast)
                        except RuleError as exc:
                            text += '\nCible : '+str(exc)
                if selected_units:
                    text += '\nÉtats sélectionnés :\n' + '\n'.join(
                        f'{u.name}: {u.statuses}' for u in selected_units)
                journal.configure(state='normal')
                journal.delete('1.0','end')
                journal.insert('1.0','\n'.join(json.dumps(e,ensure_ascii=False) for e in battle.events[-100:]))
                journal.see('end')
                journal.configure(state='disabled')
            else:
                journal.configure(state='normal')
                journal.delete('1.0', 'end')
                journal.configure(state='disabled')
                text += (f'\nSélection : {len(selected_tiles)} case(s)\n'
                         f'Presse-papiers : '
                         f'{len(terrain_clipboard.offsets) if terrain_clipboard else 0} case(s)\n'
                         'Aide détaillée : panneau Raccourcis et aide.'
                         '\nActeurs/objets : palette pour placer, inspecteur pour modifier.'
                         '\nInspecter entité : cliquer un acteur/objet; déplacer, dupliquer ou supprimer.')
            inspector.configure(state='normal')
            if not battle and structure_selection_cell is not None:
                try:
                    structure = structure_at(doc.data, mission_var.get(),
                                             structure_selection_cell)
                    record = next((row for row in mission.structures
                                   if row['id'] == structure.id), None)
                    ground_status = ('Sauvegardé (' + str(len(record['underlay'])) +
                                     ' cases)' if record is not None and
                                     'underlay' in record else
                                     'Ancienne structure : sol non récupérable')
                    text += ('\n\nSTRUCTURE SÉLECTIONNÉE\n'
                             f'{structure.name} — {structure.id or "héritée (sans ID)"}\n'
                             f'Ancrage : {structure.anchor}\n'
                             f'Emprise : {structure.width}×{structure.height}\n'
                             f'Rotation : {structure.turns * 90}°\n'
                             f'Entrée : {structure.door_slot + 1}\n'
                             f'Terrain sous le bâtiment : {ground_status}\n'
                             'Éditer les propriétés dans la barre Structure, '
                             'puis Appliquer ; déplacer ou dupliquer par clic.')
                    preview_cells(structure.cells, tag='structure_selection',
                                  color='#2369ac')
                except RuleError:
                    structure_selection_cell = None
                    structure_selection_id = None
            inspector.delete('1.0','end')
            inspector.insert('1.0', text)
            inspector.configure(state='disabled')
        if views is None or MINIMAP in views:
            draw_minimap(board, mission, units)
        if studio is not None and (views is None or WORKSPACE in views):
            if board_only and battle is None and views is None:
                studio.defer_map_refresh()
            elif selection_only and battle is None and views is None:
                studio.refresh_selection()
            else:
                studio.refresh()
            if studio.history is not None:
                history_status.set(
                    f'Historique Studio : {studio.history._cursor} modification(s) '
                    f'· Annuler : {"oui" if studio.history.can_undo else "non"} '
                    f'· Rétablir : {"oui" if studio.history.can_redo else "non"}')
        finish_ui("map.refresh", ui_started, canvas, counts={
            "map_cells": board.width * board.height,
            "cell_size": tile_size, "isometric": iso_var.get(),
            "canvas_items": len(canvas.find_all()) if ui_started is not None else 0,
            "selected_tiles": len(selected_tiles),
            "renderer_enabled": views is None or RENDERER in views,
        })

    bar = ttk.Frame(root)
    bar.pack(fill='x')
    for label,cmd in [('Ouvrir',open_doc),('Enregistrer sous',save_doc),('Enregistrer tout',save_all),('Nouvelle mission',new_mission),('Carte vierge',blank_mission),('Annuler',undo_global),('Rétablir',redo_global),('Playtest',start),('Éditer',stop),('Sauver combat',save_game),('Charger combat',load_game)]:
        ttk.Button(bar,text=label,command=cmd).pack(side='left',padx=2,pady=4)
    # A compact tool notebook replaces the seven permanent toolbar rows.
    # Keep the existing action callbacks/variables; only presentation changes.
    tool_tabs = ttk.Notebook(root)
    tool_tabs.pack(fill='x', padx=6, pady=(0, 4))
    tools_main = ttk.Frame(tool_tabs)
    tools_terrain = ttk.Frame(tool_tabs)
    tools_structure = ttk.Frame(tool_tabs)
    tools_selection = ttk.Frame(tool_tabs)
    for page, title in ((tools_main, 'Carte & combat'),
                        (tools_terrain, 'Terrain & couches'),
                        (tools_structure, 'Architecture'),
                        (tools_selection, 'Sélection & modèles')):
        tool_tabs.add(page, text=title)
    controls = ttk.Frame(tools_main)
    controls.pack(fill='x', padx=5, pady=2)
    battle_controls = ttk.Frame(tools_main)
    battle_controls.pack(fill='x', padx=5, pady=2)
    ttk.Label(controls,text='Mission').pack(side='left')
    mission_box = ttk.Combobox(controls,textvariable=mission_var,state='readonly',width=14)
    mission_box.pack(side='left')
    mission_box.bind('<<ComboboxSelected>>', lambda e: stop())
    ttk.Label(controls,text='Outil').pack(side='left')
    ttk.Combobox(controls,textvariable=tool_var,state='readonly',width=15,
                 values=['Pinceau','Pinceau intelligent','Rectangle','Sélection','Sélection structure','Collage',
                         'Remplissage','Pipette sol','Pipette décor',
                         'Structure','Sélection structure',
                         'Déplacer structure','Dupliquer structure',
                         'Entité','Inspecter entité','Déplacer entité',
                         'Dupliquer entité','Étage intérieur','Préfab',
                         'Fenêtre façade']).pack(side='left')
    ttk.Label(controls,text='Terrain').pack(side='left')
    ttk.Combobox(controls,textvariable=brush_var,state='readonly',width=10,
                 values=['wall','erase','height+','height-','height_set','mud','hazard',
                         'cover','goal','unit','object','zone+','zone-']).pack(side='left')
    ttk.Label(battle_controls, text='Unité').pack(side='left')
    unit_box = ttk.Combobox(battle_controls,textvariable=unit_var,state='readonly',width=12)
    unit_box.pack(side='left')
    ttk.Label(battle_controls,text='Objet').pack(side='left')
    object_box = ttk.Combobox(battle_controls,textvariable=object_var,state='readonly',width=12)
    object_box.pack(side='left')
    ttk.Label(battle_controls,text='Commande').pack(side='left')
    action_box = ttk.Combobox(battle_controls,textvariable=action_var,state='readonly',width=18)
    action_box.pack(side='left')
    action_box.bind('<<ComboboxSelected>>', refresh)
    ttk.Button(battle_controls,text='Exécuter',command=execute).pack(side='left')
    ttk.Combobox(battle_controls,textvariable=facing_var,state='readonly',width=6,values=['north','south','east','west']).pack(side='left')
    ttk.Button(battle_controls,text='Fin',command=end_turn).pack(side='left')
    ttk.Button(battle_controls,text='IA : 1 tour',command=ai_turn).pack(side='left')
    authoring_controls = ttk.Frame(tools_terrain)
    authoring_controls.pack(fill='x', padx=5, pady=2)
    ttk.Button(authoring_controls, text='Copier cases', command=copy_selection).pack(side='left',padx=2)
    ttk.Button(authoring_controls, text='Coller terrain', command=paste_selection).pack(side='left',padx=2)
    ttk.Label(authoring_controls, text='Zone').pack(side='left',padx=(9,2))
    ttk.Entry(authoring_controls, textvariable=zone_var, width=14).pack(side='left')
    # Roof cutaway is used constantly when authoring interiors, so keep
    # this high-frequency layer one click away even with the compact menu.
    ttk.Checkbutton(authoring_controls, text='Toitures',
                    variable=layer_vars['Toitures'],
                    command=view_options_changed).pack(side='left', padx=(12, 2))
    layers_button = ttk.Menubutton(authoring_controls, text='Autres couches ▾')
    layers_button.pack(side='left', padx=(6, 2))
    layers_menu = tk.Menu(layers_button, tearoff=False)
    for name, var in layer_vars.items():
        if name == 'Toitures':
            continue
        layers_menu.add_checkbutton(label=name, variable=var,
                                    command=view_options_changed)
    layers_button.configure(menu=layers_menu)
    lock_button = ttk.Menubutton(authoring_controls, text='Verrouiller couches ▾')
    lock_button.pack(side='left', padx=(6, 2))
    lock_menu = tk.Menu(lock_button, tearoff=False)
    for name, var in layer_lock_vars.items():
        lock_menu.add_checkbutton(label=name, variable=var,
                                  command=view_options_changed)
    lock_button.configure(menu=lock_menu)
    ttk.Label(authoring_controls, text='Niveau actif :').pack(side='left', padx=(8, 2))
    active_combo = ttk.Combobox(authoring_controls, state='readonly',
                                textvariable=active_layer_level, width=3,
                                values=(0, 1, 2, 3))
    active_combo.pack(side='left', padx=2)
    active_combo.bind('<<ComboboxSelected>>', active_level_changed)
    scenery_controls = ttk.Frame(tools_terrain)
    scenery_controls.pack(fill='x', padx=5, pady=2)
    ttk.Checkbutton(scenery_controls, text='Vue isométrique 2.5D',
                    variable=iso_var, command=refresh).pack(side='left', padx=4)
    ttk.Label(scenery_controls, text='Sol :').pack(side='left', padx=(10,2))
    surface_box = ttk.Combobox(scenery_controls, textvariable=surface_var,
                               state='readonly', width=12, values=sorted(SURFACES))
    surface_box.pack(side='left')
    surface_box.bind('<<ComboboxSelected>>',
                     lambda e: (brush_var.set('surface:'+surface_var.get()),
                                tool_var.set('Pinceau')))
    ttk.Label(scenery_controls, text='Décor :').pack(side='left', padx=(10,2))
    feature_box = ttk.Combobox(scenery_controls, textvariable=feature_var,
                               state='readonly', width=13,
                               values=sorted(FEATURES - {''}))
    feature_box.pack(side='left')
    feature_box.bind('<<ComboboxSelected>>',
                     lambda e: (brush_var.set('feature:'+feature_var.get()),
                                tool_var.set('Pinceau')))
    ttk.Button(scenery_controls, text='Effacer décor',
               command=lambda: brush_var.set('feature-erase')).pack(side='left',padx=4)
    smart_controls = ttk.Frame(tools_terrain)
    smart_controls.pack(fill='x', padx=5, pady=2)
    ttk.Button(smart_controls, text='Pinceau intelligent',
               command=lambda: tool_var.set('Pinceau intelligent')).pack(side='left', padx=2)
    ttk.Label(smart_controls, text='Rayon :').pack(side='left', padx=(6, 2))
    ttk.Combobox(smart_controls, state='readonly', width=3,
                 textvariable=brush_radius_var, values=(0, 1, 2, 3)).pack(side='left')
    ttk.Combobox(smart_controls, textvariable=brush_shape_var,
                 state='readonly', width=8, values=('diamond', 'square')).pack(side='left')
    ttk.Button(smart_controls, text='Remplir sélection',
               command=fill_selection).pack(side='left', padx=2)
    for label, tool in [('Remplir sol', 'Remplissage'),
                        ('Pipette sol', 'Pipette sol'),
                        ('Pipette décor', 'Pipette décor')]:
        ttk.Button(scenery_controls, text=label,
                   command=lambda name=tool: tool_var.set(name)).pack(side='left',padx=2)
    ttk.Label(scenery_controls, text='Niveau :').pack(side='left',padx=(10,2))
    ttk.Spinbox(scenery_controls, from_=0, to=99, textvariable=level_var,
                width=4).pack(side='left')
    ttk.Button(scenery_controls, text='Fixer niveau',
               command=lambda: (brush_var.set('height_set'),
                                tool_var.set('Pinceau'))).pack(side='left',padx=4)
    def choose_palette_asset(entry, turns):
        nonlocal structure_turns, entity_entry, entity_settings, entity_choice
        if battle is not None:
            status_var.set('Revenir en mode Éditer avant de choisir un asset à placer.')
            return False
        if entry.kind in ('actor', 'object'):
            entity_entry = entry
            entity_choice = None
            entity_settings = asset_palette.placement_settings()
            tool_var.set('Entité')
        elif entry.kind == 'structure':
            tool_tabs.select(tools_structure)
            structure_var.set(entry.value)
            structure_turns = turns
            structure_door_var.set('Entrée A')
            tool_var.set('Structure')
        else:
            tool_tabs.select(tools_terrain)
            (surface_var if entry.kind == 'surface' else feature_var).set(entry.value)
            brush_var.set(entry.id)
            tool_var.set('Pinceau')
        iso_var.set(True)
        notebook.select(work)
        refresh()
        status_var.set(entry.name + ' : cliquer sur la carte. ' + entry.effect)
        canvas.focus_set()
        return True

    def choose_entity(entry, facing, link, destination, team):
        nonlocal entity_choice, entity_passage_entry, entity_entry
        if battle is not None or source_pending():
            status_var.set('Terminer le playtest et appliquer le JSON avant édition.')
            return False
        entity_choice = (entry, facing, link, destination, team)
        entity_entry = None
        entity_passage_entry = None
        tool_var.set('Entité')
        iso_var.set(True)
        notebook.select(work)
        refresh()
        status_var.set(entry.label + ' : cliquer sur la carte pour placer une copie.')
        canvas.focus_set()
        return True

    def cancel_passage_placement():
        nonlocal entity_passage_entry
        if entity_passage_entry is not None:
            entity_passage_entry = None
            clear_placement_preview()
            status_var.set('Placement du passage annulé. Aucun objet créé.')
            refresh()

    def open_entity_palette():
        nonlocal entity_palette
        if entity_palette is None:
            from .studio_entity_palette import EntityPalette
            entity_palette = EntityPalette(
                root, snapshot=lambda: (doc.data, mission_var.get()),
                actors=actor_atlas, choose=choose_entity,
                cell_size=lambda: tile_size, props=iso_props,
                objects=object_atlas)
            wire_drop(entity_palette.tree, 'entity')
        else:
            entity_palette.show()

    def open_asset_palette():
        nonlocal asset_palette
        if asset_palette is None:
            from .studio_asset_palette import AssetPalette
            asset_palette = AssetPalette(
                root, terrain=iso_atlas, props=iso_props,
                buildings=building_atlas, fortifications=fortification_atlas,
                choose=choose_palette_asset, cell_size=lambda: tile_size,
                actors=actor_atlas, content=lambda: doc.data,
                mission=mission_var.get,
                entities=lambda: palette_entities(doc.data, mission_var.get()))
            wire_drop(asset_palette.tree, 'asset')
        else:
            asset_palette.show()

    @guarded
    def commit_entity_edit(operation, kind, identifier, values):
        if battle is not None or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        mid = mission_var.get()
        if operation not in ('edit', 'remove'):
            raise RuleError('Unknown entity edit action')
        cmd = EntityCommand(operation, kind, identifier,
                            fields=tuple(values.items()))
        design_change(lambda: editing_context.execute(cmd, publish=False))
        status_var.set(f'{kind} {identifier} : {operation} confirmé (Undo/Redo disponible).')
        return True

    def begin_entity_target(operation, kind, identifier):
        nonlocal entity_target
        if battle is not None or source_pending():
            messagebox.showerror('Édition indisponible',
                                 'Quitter le combat et appliquer le JSON.')
            return False
        entity_target = (operation, kind, identifier, mission_var.get())
        tool_var.set('Déplacer entité' if operation == 'move' else 'Dupliquer entité')
        notebook.select(work)
        status_var.set(f'{operation} {kind} {identifier} : cliquer la case cible.')
        canvas.focus_set()
        return True

    def open_entity_inspector(cell):
        nonlocal entity_inspector
        if battle is not None or source_pending():
            raise RuleError('Quitter le combat et appliquer le JSON avant édition.')
        if not entities_at(doc.data, mission_var.get(), cell):
            raise RuleError('Aucun acteur ou objet sur cette case.')
        if entity_inspector is None:
            from .studio_entity_inspector import EntityInspector
            entity_inspector = EntityInspector(
                root, snapshot=lambda: (doc.data, mission_var.get()),
                actors=actor_atlas, commit=commit_entity_edit,
                begin_target=begin_entity_target,
                cell_size=lambda: tile_size,
                open_event=lambda door_id: studio.focus_gate_event(door_id))
        entity_inspector.show_at(cell)

    @guarded
    def inspect_selected_entity():
        tool_var.set('Inspecter entité')
        open_entity_inspector(selected_cell)

    structure_controls = ttk.Frame(tools_structure)
    structure_controls.pack(fill='x', padx=5, pady=2)
    ttk.Button(structure_controls, text='Bibliothèque d’assets',
               command=open_asset_palette).pack(side='left', padx=4)
    ttk.Button(structure_controls, text='Acteurs et objets',
               command=open_entity_palette).pack(side='left', padx=4)
    ttk.Button(structure_controls, text='Inspecter acteur / objet',
               command=inspect_selected_entity).pack(side='left', padx=4)
    ttk.Label(structure_controls, text='Structures multi-cases :').pack(side='left', padx=(2, 5))
    structure_box = ttk.Combobox(structure_controls, textvariable=structure_var,
                                 state='readonly', width=16, values=STRUCTURE_NAMES)
    structure_box.pack(side='left', padx=2)
    def change_structure(_event):
        structure_door_var.set('Entrée A')
        if structure_selection_cell is None:
            tool_var.set('Structure')
    structure_box.bind('<<ComboboxSelected>>', change_structure)
    ttk.Button(structure_controls, text='Poser structure',
               command=lambda: tool_var.set('Structure')).pack(side='left',padx=3)
    ttk.Button(structure_controls, text='Supprimer structure',
               command=remove_selected_structure).pack(side='left',padx=3)
    ttk.Button(structure_controls, text='↺ Bâtiment',
               command=lambda: rotate_structure(-1)).pack(side='left',padx=2)
    ttk.Button(structure_controls, text='↻ Bâtiment',
               command=lambda: rotate_structure(1)).pack(side='left',padx=2)
    structure_options = ttk.Frame(tools_structure)
    structure_options.pack(fill='x', padx=5, pady=2)
    ttk.Checkbutton(structure_options, text='Intérieurs / coupe des toits',
                    variable=interior_var, command=view_options_changed).pack(side='left', padx=4)
    ttk.Label(structure_options, text='Pivot :').pack(side='left',padx=(2, 4))
    ttk.Combobox(structure_options, textvariable=structure_pivot_var,
                 state='readonly', width=8, values=PIVOTS).pack(side='left',padx=2)
    ttk.Label(structure_options, text='Position de porte :').pack(side='left',padx=(12, 4))
    ttk.Combobox(structure_options, textvariable=structure_door_var,
                 state='readonly', width=10,
                 values=('Entrée A','Entrée B')).pack(side='left',padx=2)
    ttk.Label(structure_options,
              text='Entrée B : Maison/Ruines seulement ; masquage automatique des toits en édition.').pack(side='left',padx=8)
    structure_edit_controls = ttk.Frame(tools_structure)
    structure_edit_controls.pack(fill='x', padx=5)
    ttk.Button(structure_edit_controls, text='Sélectionner structure',
               command=lambda: tool_var.set('Sélection structure')).pack(side='left',padx=3)
    ttk.Button(structure_edit_controls, text='Déplacer sélection',
               command=lambda: begin_structure_edit(False)).pack(side='left',padx=3)
    ttk.Button(structure_edit_controls, text='Dupliquer sélection',
               command=lambda: begin_structure_edit(True)).pack(side='left',padx=3)
    ttk.Button(structure_edit_controls, text='Appliquer propriétés',
               command=apply_structure_properties).pack(side='left',padx=3)
    ttk.Label(structure_edit_controls, text='Glisser = déplacer · Maj+glisser = dupliquer · flèches = ajuster').pack(side='left',padx=8)
    structure_group_controls = ttk.Frame(tools_structure)
    structure_group_controls.pack(fill='x', padx=5)
    ttk.Label(structure_group_controls,
              text='Structures groupées (Sélection : inclure toutes les cases) :').pack(side='left',padx=(2,5))
    ttk.Label(structure_group_controls,text='ΔX').pack(side='left')
    ttk.Spinbox(structure_group_controls, from_=-128, to=128,
                textvariable=structure_group_dx, width=4).pack(side='left',padx=2)
    ttk.Label(structure_group_controls,text='ΔY').pack(side='left')
    ttk.Spinbox(structure_group_controls, from_=-128, to=128,
                textvariable=structure_group_dy, width=4).pack(side='left',padx=2)
    ttk.Button(structure_group_controls, text='Aperçu groupe',
               command=preview_structure_group).pack(side='left',padx=3)
    ttk.Button(structure_group_controls, text='Déplacer groupe',
               command=lambda: apply_structure_group(False)).pack(side='left',padx=3)
    ttk.Button(structure_group_controls, text='Dupliquer groupe',
               command=lambda: apply_structure_group(True)).pack(side='left',padx=3)
    facade_controls = ttk.Frame(tools_structure)
    facade_controls.pack(fill='x', padx=5, pady=3)
    ttk.Label(facade_controls, text='Façade :').pack(side='left', padx=(2, 3))
    ttk.Combobox(facade_controls, textvariable=facade_var, state='readonly',
                 width=9, values=FACADES).pack(side='left')
    ttk.Label(facade_controls, text='Toiture :').pack(side='left', padx=(10, 3))
    ttk.Combobox(facade_controls, textvariable=roof_var, state='readonly',
                 width=9, values=ROOFS).pack(side='left')
    ttk.Button(facade_controls, text='Appliquer façade/toiture',
               command=apply_building_style).pack(side='left', padx=5)
    ttk.Button(facade_controls, text='Poser fenêtre',
               command=lambda: choose_window_mode(True)).pack(side='left', padx=3)
    ttk.Button(facade_controls, text='Effacer fenêtre',
               command=lambda: choose_window_mode(False)).pack(side='left', padx=3)
    ttk.Label(facade_controls,
              text='Maison/Tour · Fenêtres décoratives sur murs extérieurs').pack(
                  side='left', padx=5)
    floor_controls = ttk.Frame(root)
    floor_controls.pack(fill='x', padx=5)
    ttk.Label(floor_controls, text='Étage supérieur (visuel) :').pack(side='left',padx=3)
    floor_combo = ttk.Combobox(floor_controls, textvariable=floor_var,
                               state='readonly', width=3,
                               values=tuple(range(1, MAX_INTERIOR_LEVEL+1)))
    floor_combo.pack(side='left')
    floor_combo.bind('<<ComboboxSelected>>', lambda _e: refresh())
    ttk.Button(floor_controls, text='Créer',
               command=create_interior_level).pack(side='left',padx=2)
    ttk.Button(floor_controls, text='Supprimer',
               command=remove_interior_level).pack(side='left',padx=2)
    ttk.Label(floor_controls, text='Opération').pack(side='left',padx=3)
    ttk.Combobox(floor_controls, textvariable=floor_action_var, state='readonly',
                 width=10, values=('Sol','Mobilier','Trou','Restaurer')).pack(side='left')
    ttk.Label(floor_controls, text='Sol').pack(side='left',padx=3)
    ttk.Combobox(floor_controls, textvariable=floor_surface_var, state='readonly',
                 width=8, values=sorted(FLOOR_SURFACES)).pack(side='left')
    ttk.Label(floor_controls, text='Objet').pack(side='left',padx=3)
    ttk.Combobox(floor_controls, textvariable=floor_feature_var, state='readonly',
                 width=9, values=sorted(FLOOR_FEATURES)).pack(side='left')
    ttk.Button(floor_controls, text='Peindre étage',
               command=select_interior_paint).pack(side='left',padx=4)
    tactical_floors = ttk.Frame(tools_selection)
    tactical_floors.pack(fill='x', padx=5, pady=2)
    ttk.Label(tactical_floors, text='Gameplay vertical :').pack(side='left',padx=3)
    ttk.Label(tactical_floors, text='Destination N').pack(side='left',padx=3)
    ttk.Combobox(tactical_floors, textvariable=travel_level_var,
                 state='readonly', width=3,
                 values=tuple(range(MAX_INTERIOR_LEVEL+1))).pack(side='left')
    ttk.Button(tactical_floors, text='Escalier N-1 ↔ N',
               command=create_level_stair).pack(side='left',padx=3)
    ttk.Button(tactical_floors, text='Placer unité à N',
               command=set_unit_floor).pack(side='left',padx=3)
    advanced_controls = ttk.Frame(tools_selection)
    advanced_controls.pack(fill='x', padx=5, pady=3)
    for label,operation in [('↻ 90°','rotate_cw'), ('↺ 90°','rotate_ccw'),
                            ('⇄ Sym. H','mirror_x'), ('⇅ Sym. V','mirror_y')]:
        ttk.Button(advanced_controls,text=label,
                   command=lambda op=operation: rotate_or_flip(op)).pack(side='left',padx=2)
    ttk.Button(advanced_controls,text='Sauver modèle',
               command=save_terrain_stamp).pack(side='left',padx=2)
    ttk.Button(advanced_controls,text='Charger modèle',
               command=open_terrain_stamp).pack(side='left',padx=2)
    ttk.Label(advanced_controls, text='Groupe :').pack(side='left',padx=(10,2))
    for label,dx,dy in [('←',-1,0), ('↑',0,-1), ('↓',0,1), ('→',1,0)]:
        ttk.Button(advanced_controls,text=label,width=3,
                   command=lambda x=dx,y=dy: shift_entity_group(x,y)).pack(side='left',padx=1)
    ttk.Label(advanced_controls,text='Zoom :').pack(side='left',padx=(10,2))
    ttk.Button(advanced_controls,text='−',width=3,
               command=lambda: set_zoom(-6)).pack(side='left')
    ttk.Button(advanced_controls,text='+',width=3,
               command=lambda: set_zoom(6)).pack(side='left')
    notebook = ttk.Notebook(root)
    notebook.pack(fill='both',expand=True)
    work = ttk.Panedwindow(notebook, orient='horizontal')
    notebook.add(work,text='Carte et combat')
    sidebar = ttk.Frame(work, width=230)
    canvas_region = ttk.Panedwindow(work, orient='vertical')
    side_panel = ttk.Frame(work, width=315)
    work.add(sidebar, weight=1)
    work.add(canvas_region, weight=4)
    work.add(side_panel, weight=2)
    canvas_frame = ttk.Frame(canvas_region)
    canvas_region.add(canvas_frame, weight=4)
    canvas = tk.Canvas(canvas_frame,background='#eeeeee',takefocus=1)
    editor_renderer = EditorRenderCache(canvas)
    iso_atlas = IsoTerrainAtlas(canvas)
    iso_props = IsoPropAtlas(canvas)
    building_atlas = IsoBuildingAtlas(canvas)
    fortification_atlas = IsoFortificationAtlas(canvas)
    actor_atlas = IsoActorAtlas(canvas)
    object_atlas = IsoObjectAtlas(canvas)
    xs,ys = ttk.Scrollbar(canvas_frame,orient='horizontal',command=canvas.xview),ttk.Scrollbar(canvas_frame,orient='vertical',command=canvas.yview)
    canvas.configure(xscrollcommand=xs.set,yscrollcommand=ys.set)
    xs.pack(side='bottom',fill='x'); ys.pack(side='right',fill='y'); canvas.pack(fill='both',expand=True)
    canvas.bind('<Button-1>',click)
    canvas.bind('<B1-Motion>',drag)
    canvas.bind('<ButtonRelease-1>',end_stroke)
    canvas.bind('<Motion>',paste_preview)
    canvas.bind('<Leave>', lambda e: (clear_placement_preview(e),
                                            cancel_structure_drag(e)))
    canvas.bind('<Escape>', lambda event: (
        cancel_structure_drag(event), cancel_passage_placement()))
    canvas.bind('<Left>', lambda _e: nudge_selected_structure(-1, 0))
    canvas.bind('<Right>', lambda _e: nudge_selected_structure(1, 0))
    canvas.bind('<Up>', lambda _e: nudge_selected_structure(0, -1))
    canvas.bind('<Down>', lambda _e: nudge_selected_structure(0, 1))
    # Escape handles both drag cancellation and passage placement above.
    canvas.bind('<Control-c>',lambda _e: copy_selection())
    canvas.bind('<Control-g>',lambda _e: create_map_group())
    canvas.bind('<Control-v>',lambda _e: paste_selection())
    canvas.bind('<Control-r>',lambda _e: rotate_or_flip('rotate_cw'))
    def toggle_interiors(_event=None):
        interior_var.set(not interior_var.get())
        view_options_changed()
    canvas.bind('<Control-i>', toggle_interiors)
    canvas.bind('<Control-Shift-R>',lambda _e: rotate_or_flip('rotate_ccw'))
    canvas.bind('<Control-plus>',lambda _e: set_zoom(6))
    canvas.bind('<Control-minus>',lambda _e: set_zoom(-6))
    ttk.Button(side_panel, text='Ouvrir la palette visuelle de préfabs',
               command=open_visual_prefab_palette).pack(
                   fill='x', padx=6, pady=(4, 0))
    ttk.Label(side_panel, text='INSPECTEUR', font=('TkDefaultFont', 11, 'bold')).pack(
        anchor='w', padx=6, pady=(8, 3))
    ttk.Label(side_panel, textvariable=mode_var).pack(anchor='w', padx=6)
    ttk.Label(side_panel,text='Vue tactique').pack(anchor='w',padx=6,pady=(7,0))
    mini_canvas = tk.Canvas(side_panel,width=184,height=184,
                            background='#f5f5f5',highlightthickness=1)
    mini_canvas.pack(anchor='w',padx=3,pady=3)
    mini_canvas.bind('<Button-1>', minimap_navigate)
    ttk.Label(side_panel, text='GROUPES ET APPARTENANCES',
              font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=6)
    tree_box = ttk.Frame(side_panel)
    tree_box.pack(fill='x', padx=6, pady=3)
    group_tree = ttk.Treeview(tree_box, show='tree', height=8, selectmode='extended')
    group_scroll = ttk.Scrollbar(tree_box, orient='vertical',
                                 command=group_tree.yview)
    group_tree.configure(yscrollcommand=group_scroll.set)
    group_tree.pack(side='left', fill='both', expand=True)
    group_scroll.pack(side='right', fill='y')
    group_tree.tag_configure('group-drop-valid', background='#d3f2d7')
    group_tree.tag_configure('group-drop-invalid', background='#ffd8d5')
    group_tree.bind('<<TreeviewSelect>>', select_group_in_tree)
    group_tree.bind('<<TreeviewOpen>>', expand_group_cells)
    group_tree.bind('<ButtonPress-1>', tree_drag_press)
    group_tree.bind('<B1-Motion>', tree_drag_motion)
    group_tree.bind('<ButtonRelease-1>', tree_drag_release)
    group_tree.bind('<Escape>', tree_drag_cancel)
    group_tree.bind('<FocusOut>', tree_drag_cancel)
    group_controls = ttk.Frame(side_panel)
    group_controls.pack(fill='x', padx=5)
    for actions in (
        (('Créer vide', lambda: create_map_group(empty=True)),
         ('Grouper cases', create_map_group),
         ('Sous-groupe', lambda: create_map_group(child=True, empty=True))),
        (('Ajouter', assign_group_selection), ('Renommer', rename_map_group),
         ('Dissocier', ungroup_map_group)),
        (('Retirer', unlink_group_selection),
         ('Transférer', transfer_group_selection),
         ('Parent…', change_group_parent))):
        group_row = ttk.Frame(group_controls)
        group_row.pack(fill='x')
        for text, action in actions:
            ttk.Button(group_row, text=text, command=action).pack(
                side='left', padx=1, pady=1)
    group_move_controls = ttk.Frame(side_panel)
    group_move_controls.pack(fill='x', padx=5, pady=(0, 5))
    ttk.Label(group_move_controls, text='ΔX').pack(side='left')
    ttk.Spinbox(group_move_controls, from_=-128, to=128,
                textvariable=editor_group_dx, width=4).pack(side='left', padx=2)
    ttk.Label(group_move_controls, text='ΔY').pack(side='left')
    ttk.Spinbox(group_move_controls, from_=-128, to=128,
                textvariable=editor_group_dy, width=4).pack(side='left', padx=2)
    ttk.Button(group_move_controls, text='Aperçu',
               command=lambda: shift_map_group(preview=True)).pack(side='left',padx=2)
    ttk.Button(group_move_controls, text='Déplacer',
               command=shift_map_group).pack(side='left',padx=2)
    group_clone_controls = ttk.Frame(side_panel)
    group_clone_controls.pack(fill='x', padx=5, pady=(0, 5))
    ttk.Button(group_clone_controls, text='Aperçu copie',
               command=lambda: shift_map_group(
                   preview=True, duplicate=True)).pack(side='left',padx=2)
    ttk.Button(group_clone_controls, text='Dupliquer groupes',
               command=lambda: shift_map_group(
                   duplicate=True)).pack(side='left',padx=2)
    ttk.Label(group_clone_controls, text='Ctrl/Maj : sélection multiple'
              ).pack(side='left',padx=3)
    ttk.Label(side_panel, text='BIBLIOTHÈQUE DE PRÉFABS',
              font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=6)
    group_prefab_box = ttk.Combobox(side_panel,
                                   textvariable=group_prefab_var,
                                   state='readonly')
    group_prefab_box.pack(fill='x', padx=6, pady=2)
    prefab_thumbnail = tk.Canvas(side_panel, width=254, height=114,
                                 background='#eef0ea', highlightthickness=1,
                                 highlightbackground='#adb2ad')
    prefab_thumbnail.pack(anchor='w', padx=6, pady=(1, 5))
    group_prefab_box.bind('<<ComboboxSelected>>', draw_prefab_thumbnail)
    group_prefab_row = ttk.Frame(side_panel)
    group_prefab_row.pack(fill='x', padx=5)
    for text, action in (
        ('Enregistrer préfab', export_group_prefab),
        ('Importer préfab', import_group_prefab),
        ('Actualiser', refresh_group_prefabs),
    ):
        ttk.Button(group_prefab_row, text=text, command=action).pack(
            side='left', padx=1, pady=1)
    group_prefab_row_2 = ttk.Frame(side_panel)
    group_prefab_row_2.pack(fill='x', padx=5, pady=(0, 5))
    ttk.Label(group_prefab_row_2, text='Rotation').pack(side='left', padx=2)
    group_prefab_rotation_box = ttk.Combobox(
        group_prefab_row_2, textvariable=group_prefab_rotation_var,
        values=('0°', '90°', '180°', '270°'), state='readonly', width=5)
    group_prefab_rotation_box.pack(side='left', padx=2)
    group_prefab_rotation_box.bind('<<ComboboxSelected>>', draw_prefab_thumbnail)
    ttk.Button(group_prefab_row_2, text='Aperçu préfab',
               command=lambda: place_chosen_prefab(preview=True)
               ).pack(side='left', padx=2)
    ttk.Button(group_prefab_row_2, text='Placer préfab',
               command=place_chosen_prefab).pack(side='left', padx=2)
    group_prefab_stamp_row = ttk.Frame(side_panel)
    group_prefab_stamp_row.pack(fill='x', padx=5, pady=(0, 5))
    ttk.Button(group_prefab_stamp_row, text='Poser à la souris',
               command=enable_prefab_stamping).pack(side='left', padx=2)
    ttk.Label(group_prefab_stamp_row,
              text='Survol validé vert/rouge · 1 clic = 1 Undo'
              ).pack(side='left', padx=3)
    refresh_group_prefabs()
    draw_prefab_thumbnail()
    quarter_frame = ttk.LabelFrame(side_panel, text='GÉNÉRATION ASSISTÉE · QUARTIER')
    quarter_frame.pack(fill='x', padx=5, pady=4)
    quarter_row = ttk.Frame(quarter_frame)
    quarter_row.pack(fill='x')
    ttk.Label(quarter_row, text='Style').pack(side='left', padx=2)
    ttk.Combobox(quarter_row, textvariable=quarter_style_var, state='readonly',
                 width=11, values=QUARTER_STYLES).pack(side='left', padx=2)
    ttk.Label(quarter_row, text='Emprise').pack(side='left', padx=2)
    ttk.Combobox(quarter_row, textvariable=quarter_size_var, state='readonly',
                 width=9, values=tuple(f'{w} × {h}' for w, h in QUARTER_SIZES)
                 ).pack(side='left', padx=2)
    quarter_row2 = ttk.Frame(quarter_frame)
    quarter_row2.pack(fill='x', pady=2)
    ttk.Label(quarter_row2, text='Seed').pack(side='left', padx=2)
    ttk.Spinbox(quarter_row2, from_=0, to=999998,
                textvariable=quarter_seed_var, width=7).pack(side='left', padx=2)
    ttk.Button(quarter_row2, text='Générer 3 variantes',
               command=propose_quarters).pack(side='left', padx=2)
    quarter_row3 = ttk.Frame(quarter_frame)
    quarter_row3.pack(fill='x')
    quarter_box = ttk.Combobox(
        quarter_row3, textvariable=quarter_variant_var,
        values=('Variante 1', 'Variante 2', 'Variante 3'),
        state='readonly', width=13)
    quarter_box.pack(side='left', padx=2)
    quarter_box.bind('<<ComboboxSelected>>', refresh_quarter_thumbnail)
    ttk.Button(quarter_row3, text='Aperçu des différences',
               command=preview_quarter_proposal).pack(side='left', padx=2)
    quarter_row4 = ttk.Frame(quarter_frame)
    quarter_row4.pack(fill='x')
    ttk.Button(quarter_row4, text='Confirmer placement',
               command=confirm_quarter_proposal).pack(side='left', padx=2)
    ttk.Button(quarter_row4, text='Enregistrer comme préfab',
               command=save_quarter_as_prefab).pack(side='left', padx=2)
    ttk.Label(quarter_frame, textvariable=quarter_status_var,
              wraplength=278).pack(anchor='w', padx=3, pady=3)
    ttk.Label(side_panel, text='PALETTE VISUELLE · GLISSER SUR LA CARTE',
              font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', padx=6,
                                                     pady=(3, 2))
    prefab_gallery = VisualPrefabPalette(
        side_panel, tk, ttk,
        on_select=group_prefab_var.set,
        on_preview=palette_prefab_hover,
        on_drop=palette_prefab_drop,
        on_cancel=clear_prefab_drag,
        map_canvas=canvas,
        status=status_var.set)
    prefab_gallery.frame.pack(fill='x', padx=5, pady=(0, 5))
    group_prefab_box.bind(
        '<<ComboboxSelected>>',
        lambda _event: prefab_gallery.choose(group_prefab_var.get()))
    refresh_group_prefabs()
    inspector = tk.Text(side_panel,width=37,wrap='word',takefocus=1)
    inspector.pack(side='top',fill='both',expand=True, padx=6, pady=4)
    actor_focus = ttk.Button(side_panel, text='Modifier le personnage sélectionné',
                             command=lambda: open_selected_entity('unit'))
    actor_focus.pack(fill='x', padx=6, pady=2)
    object_focus = ttk.Button(side_panel, text='Modifier l’objet sélectionné',
                              command=lambda: open_selected_entity('object'))
    object_focus.pack(fill='x', padx=6, pady=2)
    event_focus = ttk.Button(
        side_panel, text='Créer événement lié à la porte',
        command=open_selected_gate_event)
    event_focus.pack(fill='x', padx=6, pady=2)
    ttk.Button(side_panel, text='Personnages et événements',
               command=lambda: studio.workspace._show_tab(
                   'Personnages et événements')).pack(fill='x', padx=6, pady=3)
    ttk.Button(side_panel, text='Explorer dans le Workspace',
               command=lambda: notebook.select(studio.workspace.tab)).pack(
                   fill='x', padx=6, pady=(1, 7))

    bottom_panel = ttk.Notebook(canvas_region, height=140)
    canvas_region.add(bottom_panel, weight=1)
    journal = tk.Text(bottom_panel, wrap='word', height=7)
    bottom_panel.add(journal, text='Journal de combat')
    history_panel = ttk.Frame(bottom_panel)
    bottom_panel.add(history_panel, text='Historique')
    history_status = tk.StringVar(value='Annuler / Rétablir : édition du contenu et du projet')
    ttk.Label(history_panel, textvariable=history_status).pack(
        anchor='w', padx=8, pady=5)
    ttk.Button(history_panel, text='Annuler', command=undo_global).pack(
        side='left', padx=8)
    ttk.Button(history_panel, text='Rétablir', command=redo_global).pack(
        side='left', padx=8)
    console_panel = ttk.Frame(bottom_panel)
    bottom_panel.add(console_panel, text='Console')
    console_view = tk.Text(console_panel, height=6, wrap='word', state='disabled')
    console_view.pack(fill='both', expand=True)
    def append_console(*_args):
        value = status_var.get().strip()
        if not value:
            return
        console_view.configure(state='normal')
        console_view.insert('end', value + '\n')
        if int(console_view.index('end-1c').split('.')[0]) > 250:
            console_view.delete('1.0', '40.0')
        console_view.see('end')
        console_view.configure(state='disabled')
    status_var.trace_add('write', append_console)
    simulation_panel = ttk.Frame(bottom_panel)
    bottom_panel.add(simulation_panel, text='Simulation')
    ttk.Label(simulation_panel,
              text='Lancer le Player/Playtest existant ; aucune simulation parallèle.').pack(
                  anchor='w', padx=8, pady=5)
    ttk.Button(simulation_panel, text='Playtest', command=start).pack(
        side='left', padx=8)
    ttk.Button(simulation_panel, text='Retour à l’édition', command=stop).pack(
        side='left', padx=8)
    help_panel = ttk.Frame(bottom_panel)
    bottom_panel.add(help_panel, text='Raccourcis et aide')
    ttk.Label(help_panel, text=(
        'Alt+1 : carte  •  Alt+2 : espace projet  •  Ctrl+F : chercher\n'
        'Ctrl+C/V : copier/coller la sélection sur la carte  •  '
        'Échap : vider la recherche\n'
        'Glisser les séparateurs pour adapter le navigateur, la carte, '
        'le journal et l’inspecteur.'),
        justify='left', wraplength=620).pack(anchor='nw', padx=12, pady=12)
    source_frame = ttk.Frame(notebook)
    notebook.add(source_frame,text='Données JSON')
    ttk.Button(source_frame,text='Valider et appliquer',command=apply_json).pack(anchor='w')
    source = tk.Text(source_frame,wrap='none',undo=True)
    source.pack(fill='both',expand=True)
    from types import SimpleNamespace
    from .studio_panels import StudioPanels

    def select_workspace_mission(mid):
        if mid not in {m['id'] for m in doc.data['missions']}:
            raise RuleError(f'Unknown mission: {mid}')
        mission_var.set(mid)
        stop()

    def focus_workspace_map(mid, cell, *, show_map=True, group_id=None):
        nonlocal selected_cell, selected_group_id
        if not show_map and battle is not None:
            return  # Inspecting a project reference never cancels playtest.
        if mid != mission_var.get() or show_map and battle is not None:
            select_workspace_mission(mid)
        validate_selection(doc.data, mid, [tuple(cell)])
        # Map and project tree share the exact same persistent group identity.
        # Do not treat a group as merely its first tile.
        selected_tiles.clear()
        selected_group_id = None
        if group_id is not None:
            group_mission = next(m for m in doc.data['missions']
                                 if m['id'] == mid)
            descendants = descendant_groups(group_mission, group_id)
            if not descendants:
                raise RuleError('Groupe introuvable : ' + group_id)
            selected_group_id = group_id
            selected_tiles.update(group_display_cells(group_mission, group_id))
        selected_cell = tuple(cell)
        editing_context.selection.set(mid, selected_cell, selected_tiles,
                                      publish=False)
        if show_map:
            notebook.select(work)
        refresh(selection_only=True)
        if group_id is not None and group_tree.exists('g:' + group_id):
            group_tree.selection_set('g:' + group_id)
        # A diagnostic must reveal the object, not just update its ID.
        # Use the same coordinate projection as the active map renderer.
        if iso_var.get() and iso_geometry is not None:
            cx, cy = iso_geometry.center(selected_cell)
        else:
            cx = (selected_cell[0] + 0.5) * tile_size
            cy = (selected_cell[1] + 0.5) * tile_size
        bounds = canvas.cget('scrollregion').split()
        if len(bounds) == 4:
            left, top, right, bottom = map(float, bounds)
            width = max(canvas.winfo_width(), 1)
            height = max(canvas.winfo_height(), 1)
            if right - left > width:
                canvas.xview_moveto(max(0.0, min(
                    (cx - left - width/2) / (right-left),
                    1 - width/(right-left))))
            if bottom - top > height:
                canvas.yview_moveto(max(0.0, min(
                    (cy - top - height/2) / (bottom-top),
                    1 - height/(bottom-top))))
        if show_map:
            canvas.focus_set()

    def on_project_saved(path):
        nonlocal disk_revisions
        canonical = current_path.with_suffix('.game.json').resolve()
        if Path(path).resolve() == canonical:
            disk_revisions = (disk_revisions[0],
                              StudioTransactionStore(current_path).revisions()[1])
            schedule_work_checkpoint()

    def commit_workspace_properties(key, baseline, values):
        """One typed, validated edit with Editor undo and Studio history."""
        if battle is not None or source_pending():
            raise RuleError('Quitter le playtest et appliquer le JSON avant édition.')
        form = editable_form(doc.data, key)
        if form.mission_id != mission_var.get():
            select_workspace_mission(form.mission_id)
        command = WorkspacePropertyCommand(
            key, baseline, tuple(values.items()))
        design_change(lambda: editing_context.execute(command, publish=False))
        status_var.set('Propriétés Workspace enregistrées (Annuler/Rétablir).')
        return True

    studio = StudioPanels(
        notebook, tk, ttk,
        SimpleNamespace(showerror=messagebox.showerror,
                        askstring=simpledialog.askstring,
                        asksaveasfilename=filedialog.asksaveasfilename),
        doc=lambda: doc, content_path=lambda: current_path,
        mission=mission_var.get, selection=lambda: selected_cell,
        design_change=design_change, play_campaign=start_campaign,
        status=status_var, mission_change=stop,
        select_mission=select_workspace_mission,
        on_project_saved=on_project_saved, set_active_mission=mission_var.set,
        focus_map_cell=focus_workspace_map,
        workspace_edit=commit_workspace_properties)
    if recovered_work:
        recovered_content = recovered_work[0]
        doc.data = Content.from_dict(
            recovered_content,
            rules=authored_rules_for_document(recovered_content)).to_dict()
        if mission_var.get() not in {m['id'] for m in doc.data['missions']}:
            mission_var.set(doc.data['missions'][0]['id'])
        studio.restore_unsaved_project(recovered_work[1])
        status_var.set('Travail interrompu restauré en mémoire ; enregistrer pour le conserver.')
    studio.history.on_change = schedule_work_checkpoint
    studio.workspace.incremental_validator = editing_context.diagnostics
    studio.workspace.attach_navigator(sidebar)
    studio.workspace.attach_problems(bottom_panel)
    ttk.Button(sidebar, text='Espace projet complet',
               command=lambda: notebook.select(studio.workspace.tab)).pack(
                   fill='x', padx=7, pady=(3, 8))
    def wire_drop(tree, kind):
        """Native Tk pointer gesture across Studio's existing Treeviews.

        A drop invokes the same palette selection and canvas click as manual
        placement, so validations, authoring history and undo are unchanged.
        """
        gesture = {}

        def start(event):
            gesture.clear()
            row = tree.identify_row(event.y)
            if row and not row.startswith('group:'):
                gesture.update(row=row, x=event.x_root, y=event.y_root)

        def finish(event):
            row = gesture.get('row')
            start_x, start_y = gesture.get('x'), gesture.get('y')
            gesture.clear()
            if not row or start_x is None:
                return
            if abs(event.x_root - start_x) + abs(event.y_root - start_y) < 12:
                return
            # Never interpret a release outside the visible tactical canvas.
            x = event.x_root - canvas.winfo_rootx()
            y = event.y_root - canvas.winfo_rooty()
            if not (0 <= x < canvas.winfo_width() and
                    0 <= y < canvas.winfo_height()):
                return
            if battle or source_pending():
                messagebox.showerror('Placement indisponible',
                                     'Quitter le playtest et valider le JSON.')
                return
            try:
                if kind == 'asset':
                    entry = asset_palette.entries.get(row)
                    if entry is None or not choose_palette_asset(
                            entry, asset_palette.turns):
                        return
                elif kind == 'entity':
                    entry = entity_palette.entries.get(row)
                    if entry is None or not choose_entity(
                            entry, entity_palette.facing.get(),
                            entity_palette.link.get(),
                            entity_palette.destination.get(),
                            entity_palette.team.get()):
                        return
                else:
                    entry = palette_source_for_tree(
                        row, doc.data, mission_var.get())
                    link, destination = '', ''
                    if row.startswith('map_object:'):
                        mid, entity_id = row.partition(':')[2].split('/', 1)
                        source_mission = next(
                            m for m in doc.data['missions'] if m['id'] == mid)
                        original = next(
                            o for o in source_mission['objects']
                            if o['id'] == entity_id)
                        link = original.get('link', '')
                        destination = original.get('destination', '')
                    if not choose_entity(entry, 'south', link, destination,
                                         entry.team or 'enemy'):
                        return
                from types import SimpleNamespace
                gesture_event = SimpleNamespace(x=int(x), y=int(y), state=0)
                click(gesture_event)
                end_stroke(gesture_event)
            except (RuleError, ValueError, KeyError, TypeError, StopIteration) as exc:
                messagebox.showerror('Dépôt refusé', str(exc))

        tree.bind('<ButtonPress-1>', start, add='+')
        tree.bind('<ButtonRelease-1>', finish, add='+')

    wire_drop(studio.workspace.tree, 'workspace')
    wire_drop(studio.workspace.sidebar_tree, 'workspace')

    def focus_project_search(_event=None):
        notebook.select(work)
        entry = studio.workspace.sidebar_search
        entry.focus_set()
        entry.selection_range(0, 'end')

    # Subscription order is intentionally renderer -> inspector -> minimap ->
    # workspace. A typed edit publishes once; each view consumes only its
    # topic and render caching remains owned by EditorRenderCache.
    for topic in (RENDERER, INSPECTOR, MINIMAP, WORKSPACE):
        editing_context.notifications.subscribe(
            topic, lambda notice, view=topic: refresh(views=(view,)))
    tool_var.trace_add(
        'write', lambda *_: editing_context.tools.set(
            tool_var.get(), mission_var.get()))

    root.bind('<Control-f>', focus_project_search)
    root.bind('<Control-Shift-p>',
              lambda _e: studio.workspace.focus_problems())
    root.bind('<Alt-KeyPress-3>',
              lambda _e: studio.workspace.focus_problems())
    root.bind('<Alt-KeyPress-1>', lambda _event: notebook.select(work))
    root.bind('<Alt-KeyPress-2>',
              lambda _event: notebook.select(studio.workspace.tab))
    ttk.Label(root,textvariable=status_var).pack(fill='x')

    def layout_store():
        return LayoutStore(current_path.with_suffix('.workspace.layout.json'))

    def save_layout(_event=None):
        try:
            layout_store().save({
                'outer_left': work.sashpos(0),
                'outer_right': work.sashpos(1),
                'vertical': canvas_region.sashpos(0),
                'tab': notebook.tab(notebook.select(), 'text'),
            })
        except (OSError, ValueError, tk.TclError):
            # UI preferences must never prevent authoring or saving gameplay.
            pass

    def restore_layout():
        values = layout_store().load()
        try:
            if 'outer_left' in values and values['outer_left'] < work.winfo_width():
                work.sashpos(0, values['outer_left'])
            if 'outer_right' in values and values['outer_right'] < work.winfo_width():
                work.sashpos(1, values['outer_right'])
            if 'vertical' in values and values['vertical'] < canvas_region.winfo_height():
                canvas_region.sashpos(0, values['vertical'])
            for tab in notebook.tabs():
                if notebook.tab(tab, 'text') == values.get('tab', 'Carte et combat'):
                    notebook.select(tab)
                    break
        except tk.TclError:
            pass

    work.bind('<ButtonRelease-1>', save_layout, add='+')
    canvas_region.bind('<ButtonRelease-1>', save_layout, add='+')
    root.after_idle(restore_layout)
    def close_editor():
        if discard_ok():
            if work_checkpoint_job is not None:
                root.after_cancel(work_checkpoint_job)
            edit_recovery.discard()
            save_layout()
            root.destroy()
    root.protocol('WM_DELETE_WINDOW', close_editor)
    refresh_source()
    refresh()
    root.mainloop()

