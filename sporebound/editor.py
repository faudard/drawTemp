"""Own mission editor and tactical playtest UI. Tk is imported only by launch()."""
from copy import deepcopy
import json
from pathlib import Path

from .ai import play_activation
from .engine import Battle
from .model import Content, RuleError
from .map_authoring import (cells_in_rectangle, copy_terrain, move_object,
                            move_unit, paint_deployment, paste_terrain,
                            selected_cells as validate_selection)
from .map_transform import (group_entities, load_stamp, move_group, save_stamp,
                            transform_terrain)
from .siege import available_operations
from .storage import load_battle, save_battle, write_json


class Document:
    """Validated edits with bounded undo history; playtests always use a copy."""
    def __init__(self, content: Content):
        self.data = content.to_dict()
        self.undo_stack = []
        self.redo_stack = []
        self.saved = json.dumps(self.data, sort_keys=True)

    @property
    def dirty(self):
        return json.dumps(self.data, sort_keys=True) != self.saved

    def replace(self, data):
        validated = Content.from_dict(data).to_dict()
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
        tiles = mission['board']['tiles']
        seen = set()
        for cell in cells:
            cell = tuple(cell)
            if cell in seen:
                continue
            seen.add(cell)
            if not (0 <= cell[0] < width and 0 <= cell[1] < height):
                raise RuleError(f'Case hors carte : {cell}')
            old = next((t for t in tiles if tuple(t['pos']) == cell), {'pos': list(cell)})
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
            elif brush == 'goal':
                goal = [list(c) for c in mission.get('goal', [])]
                if list(cell) not in goal:
                    goal.append(list(cell))
                mission['goal'] = goal
            else:
                raise RuleError('Unknown brush')
            tiles[:] = [t for t in tiles if tuple(t['pos']) != cell]
            tiles.append(new)
        if seen:
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

    def place_unit(self, mid, uid, cell):
        data = deepcopy(self.data)
        mission = next(m for m in data['missions'] if m['id'] == mid)
        next(u for u in mission['units'] if u['id'] == uid)['pos'] = list(cell)
        self.replace(data)

    def save(self, path):
        Content.from_dict(self.data)
        write_json(path, self.data)
        self.saved = json.dumps(self.data, sort_keys=True)

    def playtest(self, mid, seed=1):
        return Battle(Content.from_dict(self.data), mid, seed)


def launch(path):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog

    root = tk.Tk()
    root.title('Sporebound — Atelier gameplay autonome')
    root.geometry('1280x850')
    doc = Document(Content.load(path))
    current_path = Path(path)
    battle = None
    studio = None
    campaign_session = None
    campaign_battle = False
    selected_cell = (0, 0)
    stroke_cells = []
    rectangle_anchor = None
    selected_tiles = set()
    selection_mission = ''
    selection_additive = False
    terrain_clipboard = None
    tile_size = 54
    mission_var = tk.StringVar(value=doc.data['missions'][0]['id'])
    brush_var = tk.StringVar(value='wall')
    tool_var = tk.StringVar(value='Pinceau')
    unit_var = tk.StringVar()
    action_var = tk.StringVar(value='move')
    facing_var = tk.StringVar(value='south')
    object_var = tk.StringVar()
    zone_var = tk.StringVar(value='attackers')
    layer_vars = {name: tk.BooleanVar(value=True) for name in
                  ('Terrain', 'Relief', 'Déploiement', 'Objectifs', 'Objets', 'Unités')}
    status_var = tk.StringVar(value='Édition : choisir un pinceau puis cliquer sur une case.')

    def guarded(fn):
        def run(*args):
            try:
                fn(*args)
            except (RuleError, OSError, ValueError, KeyError, StopIteration) as exc:
                messagebox.showerror('Opération refusée', str(exc))
        return run

    def source_pending():
        return source.get('1.0', 'end-1c').strip() != json.dumps(doc.data, indent=2, ensure_ascii=False)

    def discard_ok():
        return not (doc.dirty or source_pending() or (studio is not None and studio.dirty())) or messagebox.askyesno('Modifications', 'Abandonner les modifications non enregistrées ?')

    def refresh_source():
        source.delete('1.0', 'end')
        source.insert('1.0', json.dumps(doc.data, indent=2, ensure_ascii=False))

    def design_change(fn):
        nonlocal battle
        if source_pending() and not messagebox.askyesno('JSON non appliqué', 'Abandonner les modifications JSON non appliquées ?'):
            return
        fn()
        battle = None
        refresh_source()
        refresh()

    @guarded
    def open_doc():
        nonlocal doc, current_path, battle
        if not discard_ok():
            return
        name = filedialog.askopenfilename(filetypes=[('Projet Sporebound', '*.json')])
        if name:
            candidate = Document(Content.load(name))
            doc, current_path, battle = candidate, Path(name), None
            mission_var.set(doc.data['missions'][0]['id'])
            if studio is not None:
                studio.reload_project()
            refresh_source()
            refresh()

    @guarded
    def save_doc():
        nonlocal current_path
        if source_pending():
            doc.replace(json.loads(source.get('1.0', 'end')))
        name = filedialog.asksaveasfilename(initialfile=current_path.name, defaultextension='.json', filetypes=[('JSON', '*.json')])
        if name:
            doc.save(name)
            current_path = Path(name)
            refresh_source()
            status_var.set(f'Projet enregistré : {name}')

    @guarded
    def apply_json():
        nonlocal battle
        doc.replace(json.loads(source.get('1.0', 'end')))
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
        battle = progress.prepare(Content.from_dict(doc.data), mid)
        campaign_battle = True
        mission_var.set(mid)
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

    def set_zoom(delta):
        nonlocal tile_size
        next_size = max(24, min(96, tile_size + delta))
        if next_size != tile_size:
            tile_size = next_size
            refresh()
            status_var.set(f'Zoom carte : {tile_size}px/case')

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
            design_change(lambda: doc.paint_many(mission_var.get(), cells, brush))

    def paste_preview(event):
        canvas.delete('paste_preview')
        if battle or tool_var.get() != 'Collage' or terrain_clipboard is None:
            return
        cell = (int(canvas.canvasx(event.x) // tile_size),
                int(canvas.canvasy(event.y) // tile_size))
        mission = next(m for m in doc.data['missions'] if m['id'] == mission_var.get())
        offsets = terrain_clipboard.offsets
        if len(offsets) > 512:
            # Mouse-motion rendering stays bounded for huge selections.
            width, height = terrain_clipboard.width, terrain_clipboard.height
            valid = 0 <= cell[0] and 0 <= cell[1] and (
                cell[0] + width <= mission['board']['width']) and (
                cell[1] + height <= mission['board']['height'])
            canvas.create_rectangle(cell[0]*tile_size+4, cell[1]*tile_size+4,
                                    (cell[0]+width)*tile_size-4,
                                    (cell[1]+height)*tile_size-4,
                                    outline='#36a16c' if valid else '#e05252',
                                    width=3, dash=(4, 3), tags='paste_preview')
            return
        for dx, dy in offsets:
            x, y = cell[0] + dx, cell[1] + dy
            inside = 0 <= x < mission['board']['width'] and 0 <= y < mission['board']['height']
            canvas.create_rectangle(x*tile_size+4, y*tile_size+4,
                                    (x+1)*tile_size-4, (y+1)*tile_size-4,
                                    outline='#36a16c' if inside else '#e05252',
                                    width=3, dash=(4, 3), tags='paste_preview')

    @guarded
    def click(event):
        nonlocal selected_cell, stroke_cells, rectangle_anchor, selection_additive
        canvas.focus_set()
        stroke_cells = []
        selected_cell = (int(canvas.canvasx(event.x) // tile_size),
                         int(canvas.canvasy(event.y) // tile_size))
        validate_selection(doc.data, mission_var.get(), [selected_cell])
        tool, brush = tool_var.get(), brush_var.get()
        canvas.delete('stroke_preview')
        if battle:
            refresh()
        elif tool == 'Collage':
            paste_at(selected_cell)
        elif tool in ('Sélection', 'Rectangle') and (tool == 'Sélection' or brush not in ('unit', 'object')):
            rectangle_anchor = selected_cell
            selection_additive = bool(event.state & 0x0001)
            stroke_cells = [selected_cell]
            x, y = selected_cell[0] * tile_size, selected_cell[1] * tile_size
            canvas.create_rectangle(x+3, y+3, x+tile_size-3, y+tile_size-3,
                                    outline='#2a61ff', width=3, tags='stroke_preview')
        else:
            rectangle_anchor = None
            stroke_cells = [selected_cell]
            paint_cells([selected_cell], brush)

    def drag(event):
        if battle or not stroke_cells or tool_var.get() == 'Collage':
            return
        if tool_var.get() not in ('Sélection', 'Rectangle') and brush_var.get() in ('unit', 'object'):
            return
        cell = (int(canvas.canvasx(event.x) // tile_size),
                int(canvas.canvasy(event.y) // tile_size))
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
            canvas.create_rectangle(x1*tile_size+3, y1*tile_size+3,
                                    (x2+1)*tile_size-3, (y2+1)*tile_size-3,
                                    outline='#2a61ff', width=3, tags='stroke_preview')
        elif cell not in stroke_cells:
            stroke_cells.append(cell)
            x, y = cell[0] * tile_size, cell[1] * tile_size
            canvas.create_rectangle(x+3, y+3, x+tile_size-3, y+tile_size-3,
                                    outline='#2a61ff', width=3, tags='stroke_preview')

    @guarded
    def end_stroke(_event):
        nonlocal selected_cell, stroke_cells, rectangle_anchor, selected_tiles
        tool, brush = tool_var.get(), brush_var.get()
        if not battle and tool == 'Sélection' and rectangle_anchor is not None and stroke_cells:
            cells = cells_in_rectangle(doc.data, mission_var.get(), rectangle_anchor,
                                       stroke_cells[-1])
            selected_tiles = selected_tiles | set(cells) if selection_additive else set(cells)
            selected_cell = stroke_cells[-1]
            refresh()
        elif not battle and tool == 'Rectangle' and rectangle_anchor is not None and stroke_cells and brush not in ('unit', 'object'):
            end = stroke_cells[-1]
            selected_cell = end
            if brush in ('zone+', 'zone-'):
                paint_cells(cells_in_rectangle(doc.data, mission_var.get(),
                                               rectangle_anchor, end), brush)
            else:
                design_change(lambda: doc.paint_rectangle(mission_var.get(),
                                                          rectangle_anchor, end, brush))
        elif not battle and tool == 'Pinceau' and brush not in ('unit', 'object') and len(stroke_cells) > 1:
            selected_cell = stroke_cells[-1]
            paint_cells(stroke_cells[1:], brush)
        stroke_cells = []
        rectangle_anchor = None
        canvas.delete('stroke_preview')


    def refresh(*args):
        nonlocal selected_cell, campaign_battle, selection_mission, selected_tiles
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
            selected_tiles.clear()
            selection_mission = mission_var.get()
        content = Content.from_dict(doc.data)
        mission = battle.mission if battle else content.missions[mission_var.get()]
        board = battle.board if battle else mission.board
        units = battle.units if battle else mission.units
        unit_box['values'] = [u.id for u in units if not battle or not battle.deploying
                              or u.team == 'player' and u.alive]
        if unit_var.get() not in unit_box['values']:
            unit_var.set(unit_box['values'][0] if unit_box['values'] else '')
        object_box['values'] = [o['id'] for o in mission.objects]
        if object_var.get() not in object_box['values']:
            object_var.set(object_box['values'][0] if object_box['values'] else '')
        selected_tiles.intersection_update(set(board.cells()))
        canvas.delete('all')
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
                if t.cost > 1: color = '#b29f78'
                if t.cover: color = '#b0c9a8'
                if t.hazard: color = '#eead93'
                if t.blocked: color = '#555555'
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
        text = f'{mission.name}\nObjectif : {mission.objective}\nCase : {selected_cell}\n'
        for obj in mission.objects:
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
                action_box['values'] = actions
                if action_var.get() not in actions: action_var.set('move')
                if action_var.get() not in {'move'} and not action_var.get().startswith(('item:','object:','siege-attack:','repair-siege:')):
                    try:
                        forecast = battle.forecast(action_var.get(), selected_cell)
                        text += '\nPrévision immédiate (avant réactions) :\n'
                        text += '\n'.join(f'{r["unit"]}: {r["kind"]} {r["amount"]} {r["status"]} ({r["chance"]:.0%})' for r in forecast)
                    except RuleError as exc:
                        text += '\nCible : '+str(exc)
            text += '\n\nUnités :\n'+'\n'.join(f'{u.name}: {u.hp} PV, {u.mp} MP, CT {u.ct}\n  {u.statuses}' for u in units)
            journal.delete('1.0','end')
            journal.insert('1.0','\n'.join(json.dumps(e,ensure_ascii=False) for e in battle.events[-100:]))
            journal.see('end')
        else:
            text += ('\nCarte : sélectionner une zone, Ctrl+C, choisir le point '
                     'd’ancrage, Ctrl+V ou l’outil Collage.'
                     f'\nCases sélectionnées : {len(selected_tiles)}'
                     f' | Presse-papiers : {len(terrain_clipboard.offsets) if terrain_clipboard else 0}'
                     '\nCouches : visibilité d’édition seulement ; règles inchangées.'
                     '\nDonnées tactiques avancées : onglet JSON.')
        inspector.delete('1.0','end')
        inspector.insert('1.0', text)
        if studio is not None:
            studio.refresh()

    bar = ttk.Frame(root)
    bar.pack(fill='x')
    for label,cmd in [('Ouvrir',open_doc),('Enregistrer sous',save_doc),('Nouvelle mission',new_mission),('Carte vierge',blank_mission),('Annuler',guarded(lambda: design_change(doc.undo))),('Rétablir',guarded(lambda: design_change(doc.redo))),('Playtest',start),('Éditer',stop),('Sauver combat',save_game),('Charger combat',load_game)]:
        ttk.Button(bar,text=label,command=cmd).pack(side='left',padx=2,pady=4)
    controls = ttk.Frame(root)
    controls.pack(fill='x')
    ttk.Label(controls,text='Mission').pack(side='left')
    mission_box = ttk.Combobox(controls,textvariable=mission_var,state='readonly',width=14)
    mission_box.pack(side='left')
    mission_box.bind('<<ComboboxSelected>>', lambda e: stop())
    ttk.Label(controls,text='Outil').pack(side='left')
    ttk.Combobox(controls,textvariable=tool_var,state='readonly',width=11,
                 values=['Pinceau','Rectangle','Sélection','Collage']).pack(side='left')
    ttk.Label(controls,text='Terrain').pack(side='left')
    ttk.Combobox(controls,textvariable=brush_var,state='readonly',width=10,
                 values=['wall','erase','height+','height-','mud','hazard',
                         'cover','goal','unit','object','zone+','zone-']).pack(side='left')
    unit_box = ttk.Combobox(controls,textvariable=unit_var,state='readonly',width=12)
    unit_box.pack(side='left')
    ttk.Label(controls,text='Objet').pack(side='left')
    object_box = ttk.Combobox(controls,textvariable=object_var,state='readonly',width=12)
    object_box.pack(side='left')
    ttk.Label(controls,text='Commande').pack(side='left')
    action_box = ttk.Combobox(controls,textvariable=action_var,state='readonly',width=18)
    action_box.pack(side='left')
    action_box.bind('<<ComboboxSelected>>', refresh)
    ttk.Button(controls,text='Exécuter',command=execute).pack(side='left')
    ttk.Combobox(controls,textvariable=facing_var,state='readonly',width=6,values=['north','south','east','west']).pack(side='left')
    ttk.Button(controls,text='Fin',command=end_turn).pack(side='left')
    ttk.Button(controls,text='IA : 1 tour',command=ai_turn).pack(side='left')
    authoring_controls = ttk.Frame(root)
    authoring_controls.pack(fill='x', padx=5)
    ttk.Button(authoring_controls, text='Copier cases', command=copy_selection).pack(side='left',padx=2)
    ttk.Button(authoring_controls, text='Coller terrain', command=paste_selection).pack(side='left',padx=2)
    ttk.Label(authoring_controls, text='Zone').pack(side='left',padx=(9,2))
    ttk.Entry(authoring_controls, textvariable=zone_var, width=14).pack(side='left')
    ttk.Label(authoring_controls, text='Couche visible :').pack(side='left',padx=(8,2))
    for name, var in layer_vars.items():
        ttk.Checkbutton(authoring_controls, text=name, variable=var,
                        command=refresh).pack(side='left',padx=2)
    notebook = ttk.Notebook(root)
    notebook.pack(fill='both',expand=True)
    work = ttk.Frame(notebook)
    notebook.add(work,text='Carte et combat')
    canvas_frame = ttk.Frame(work)
    canvas_frame.pack(side='left',fill='both',expand=True)
    canvas = tk.Canvas(canvas_frame,background='#eeeeee',takefocus=1)
    xs,ys = ttk.Scrollbar(canvas_frame,orient='horizontal',command=canvas.xview),ttk.Scrollbar(canvas_frame,orient='vertical',command=canvas.yview)
    canvas.configure(xscrollcommand=xs.set,yscrollcommand=ys.set)
    xs.pack(side='bottom',fill='x'); ys.pack(side='right',fill='y'); canvas.pack(fill='both',expand=True)
    canvas.bind('<Button-1>',click)
    canvas.bind('<B1-Motion>',drag)
    canvas.bind('<ButtonRelease-1>',end_stroke)
    canvas.bind('<Motion>',paste_preview)
    canvas.bind('<Control-c>',lambda _e: copy_selection())
    canvas.bind('<Control-v>',lambda _e: paste_selection())
    inspector = tk.Text(work,width=43,wrap='word')
    inspector.pack(side='right',fill='y')
    source_frame = ttk.Frame(notebook)
    notebook.add(source_frame,text='Données JSON')
    ttk.Button(source_frame,text='Valider et appliquer',command=apply_json).pack(anchor='w')
    source = tk.Text(source_frame,wrap='none',undo=True)
    source.pack(fill='both',expand=True)
    journal = tk.Text(notebook,wrap='word')
    notebook.add(journal,text='Journal de combat')
    from types import SimpleNamespace
    from .studio_panels import StudioPanels

    def select_workspace_mission(mid):
        if mid not in {m['id'] for m in doc.data['missions']}:
            raise RuleError(f'Unknown mission: {mid}')
        mission_var.set(mid)
        stop()

    studio = StudioPanels(
        notebook, tk, ttk,
        SimpleNamespace(showerror=messagebox.showerror,
                        askstring=simpledialog.askstring,
                        asksaveasfilename=filedialog.asksaveasfilename),
        doc=lambda: doc, content_path=lambda: current_path,
        mission=mission_var.get, selection=lambda: selected_cell,
        design_change=design_change, play_campaign=start_campaign,
        status=status_var, mission_change=stop,
        select_mission=select_workspace_mission)
    ttk.Label(root,textvariable=status_var).pack(fill='x')
    root.protocol('WM_DELETE_WINDOW',lambda: root.destroy() if discard_ok() else None)
    refresh_source()
    refresh()
    root.mainloop()

