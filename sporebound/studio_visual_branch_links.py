"""Canvas link ports for the existing StoryGraphEditor (3.6).

Adds no Canvas schema, game objects, or second navigator. Scene occurrences
remain UI-only; targets resolve to canonical scene/event IDs.
"""
from .visual_branch_graph import connect_visual_branch, visual_target_palette
from .model import require


class VisualBranchInteractions:
    """Mixin: ports, drag previews, typed target resolution and atomic edits."""

    def _visual_setup(self):
        self._visual_targets = []
        self._visual_ports = []
        self._visual_drag = None
        self._visual_drag_line = None
        self.selected_event = ''
        self.event_join_var = self.tk.StringVar(value='ET')
        self.visual_mission = self.tk.StringVar(value=self.owner.mission())
        self.canvas.bind('<B1-Motion>', self._visual_motion, add='+')
        self.canvas.bind('<ButtonRelease-1>', self._visual_release, add='+')

    def _visual_mission_id(self):
        missions = [row['id'] for row in self.owner.doc().data['missions']]
        chosen = self.visual_mission.get()
        return chosen if chosen in missions else self.owner.mission()

    def _visual_palette(self, layout):
        present = {row['scene_id'] for row in layout['nodes']
                   if row['scene_id']}
        return visual_target_palette(
            self.owner.doc().data, self.owner.project,
            self._visual_mission_id(), present, max_scenes=25, max_events=60)

    def _visual_target(self, kind, identifier, x, y, width, height):
        self._visual_targets.append({
            'kind': kind, 'id': identifier,
            'rect': (x, y-height//2, x+width, y+height//2),
        })

    def _visual_port(self, kind, identifier, choice_id, x, y):
        radius = 9
        tag = 'visual_port_' + str(len(self._visual_ports))
        self._visual_ports.append({
            'kind': kind, 'id': identifier, 'choice': choice_id, 'x': x, 'y': y,
        })
        self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                                fill='#0891b2', outline='#155e75', width=2,
                                tags=(tag, 'visual_link_port'))
        self.canvas.tag_bind(
            tag, '<ButtonPress-1>',
            lambda event, n=len(self._visual_ports)-1:
            self._visual_begin(event, n))

    def _visual_scene_port(self, scene_id, path, x, y, width, height):
        scenes = self.owner.project.story['scenes']
        row = next((s for s in scenes if s['id'] == scene_id), None)
        if row is None:
            return
        is_selected = path == self.selected_path
        choice = (self.choice_var.get()
                  if is_selected and
                  self.choice_var.get() in {c['id'] for c in row['choices']}
                  else row['choices'][0]['id'])
        self._visual_port('scene', scene_id, choice,
                          x+width+13, y)
        self.canvas.create_text(x+width+13, y+17,
                                text=choice[:12], anchor='n',
                                font=('TkDefaultFont', 8), fill='#155e75')

    def _visual_draw(self, layout, scale, width, height):
        """Render target palettes next to (not in place of) existing tree."""
        self._visual_targets = []
        self._visual_ports = []
        self._visual_drag = None
        self._visual_drag_line = None
        for node in layout['nodes']:
            if not node['scene_id']:
                continue
            x, y = self._pos(node['path'])
            self._visual_target('scene', node['scene_id'], x, y, width, height)
            self._visual_scene_port(
                node['scene_id'], node['path'], x, y, width, height)

        palette = self._visual_palette(layout)
        # The two columns are the same canvas, so dragging can cross scene
        # occurrences, detached scenes, and authored event cards.
        scene_x = int(layout['width']*scale)+65
        event_x = scene_x+315
        card_w = int(208*scale)
        card_h = int(70*scale)
        title_y = 31
        self.canvas.create_text(
            scene_x, title_y, text='AUTRES SCÈNES',
            anchor='nw', fill='#334155',
            font=('TkDefaultFont', 10, 'bold'))
        self.canvas.create_text(
            event_x, title_y, text='ÉVÉNEMENTS · '+self._visual_mission_id(),
            anchor='nw', fill='#334155',
            font=('TkDefaultFont', 10, 'bold'))
        for kind, rows, x in (
                ('scene', palette['scenes'], scene_x),
                ('event', palette['events'], event_x)):
            for index, item in enumerate(rows):
                y = int((98 + index*106)*scale)
                tag = 'visual_' + kind + '_' + str(index)
                selected = kind == 'event' and item['id'] == self.selected_event
                color = '#dbeafe' if kind == 'scene' else '#fef3c7'
                self.canvas.create_rectangle(
                    x, y-card_h//2, x+card_w, y+card_h//2,
                    fill=color, outline='#2563eb' if selected else '#94a3b8',
                    width=3 if selected else 1, tags=(tag,))
                self.canvas.create_text(
                    x+card_w//2, y-12*scale,
                    text=item['id'], width=card_w-12, justify='center',
                    fill='#0f172a', font=('TkDefaultFont', 9, 'bold'),
                    tags=(tag,))
                self.canvas.create_text(
                    x+card_w//2, y+14*scale, text=item['title'][:38],
                    width=card_w-15, justify='center',
                    fill='#334155', tags=(tag,))
                self._visual_target(kind, item['id'], x, y, card_w, card_h)
                if kind == 'scene':
                    self._visual_scene_port(
                        item['id'], None, x, y, card_w, card_h)
                else:
                    self._visual_port('event', item['id'], '', x+card_w+12, y)
                    self.canvas.tag_bind(
                        tag, '<Button-1>',
                        lambda event, eid=item['id']:
                        self._visual_select_event(eid))
                    self.canvas.tag_bind(
                        tag, '<Double-Button-1>',
                        lambda event, eid=item['id']:
                        self._visual_open_event(eid))
        extent_x = event_x+card_w+120
        extent_y = max(
            layout['height']*scale,
            (140+max(len(palette['scenes']),
                     len(palette['events']))*106)*scale)
        self.canvas.configure(scrollregion=(
            0, 0, int(extent_x), int(extent_y)))
        if palette['events_truncated'] or palette['scenes_truncated']:
            self.status.set('Palette limitée : sélectionner une autre mission '
                            'ou réduire les scènes/événements affichés.')

    def _visual_select_event(self, event_id):
        self.selected_event = event_id
        self.draw()
        self._visual_details_event()

    def _visual_details_event(self):
        mission = next(m for m in self.owner.doc().data['missions']
                       if m['id'] == self._visual_mission_id())
        row = next((e for e in mission.get('triggers', [])
                    if e['id'] == self.selected_event), None)
        if row is None:
            return
        from .event_graph import condition_summary, action_title
        lines = [
            'ÉVÉNEMENT TACTIQUE · '+row['id'],
            'Mission : '+mission['id'],
            'Condition : '+condition_summary(row),
            'Actions :',
            *('· '+action_title(a) for a in row['actions']),
            '',
            'Tirer son port turquoise vers un autre événement (ET/OU),',
            'ou vers une scène (dialogue déclenché par cet événement).',
        ]
        self.info.configure(state='normal')
        self.info.delete('1.0', 'end')
        self.info.insert('1.0', '\n'.join(lines))
        self.info.configure(state='disabled')

    def _visual_open_event(self, event_id=None):
        event_id = event_id or self.selected_event
        require(bool(event_id), 'Select a tactical event first')
        mid = self._visual_mission_id()
        if mid != self.owner.mission():
            self.owner.set_active_mission(mid)
        graph = self.owner.advanced.event_graph
        graph.event_id.set(event_id)
        graph.refresh()
        self.editor.notebook.select(graph.tab)

    def _visual_begin(self, event, port_number):
        source = self._visual_ports[port_number]
        self._visual_drag = dict(source)
        start_x, start_y = source['x'], source['y']
        px, py = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self._visual_drag_line = self.canvas.create_line(
            start_x, start_y, px, py, fill='#0891b2',
            dash=(5, 4), width=3,
            arrow='last', tags=('visual_drag_preview',))
        self.status.set(
            'Déposer sur une scène ou un événement · Échap / vide = annuler')

    def _visual_motion(self, event):
        if self._visual_drag is None or self._visual_drag_line is None:
            return
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.coords(
            self._visual_drag_line,
            self._visual_drag['x'], self._visual_drag['y'], x, y)

    def _visual_pick(self, x, y):
        # Scene occurrences are canonically the same scene. The target ID,
        # never a tuple of occurrence paths, is used to edit StoryBook.
        for item in reversed(self._visual_targets):
            x1, y1, x2, y2 = item['rect']
            if x1 <= x <= x2 and y1 <= y <= y2:
                return item
        return None

    def _visual_release(self, event):
        source = self._visual_drag
        if source is None:
            return
        self._visual_drag = None
        if self._visual_drag_line is not None:
            self.canvas.delete(self._visual_drag_line)
            self._visual_drag_line = None
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        target = self._visual_pick(x, y)
        if target is None:
            self.status.set('Liaison annulée : aucune cible sous le curseur.')
            return
        self.owner._run(
            lambda: self._visual_commit(source, target))

    def _visual_commit(self, source, target):
        mid = self._visual_mission_id()
        data, project = connect_visual_branch(
            self.owner.doc().data, self.owner.project, mid,
            source_kind=source['kind'], source_id=source['id'],
            target_kind=target['kind'], target_id=target['id'],
            choice_id=source['choice'],
            event_join='any' if self.event_join_var.get() == 'OU' else 'all')
        if data != self.owner.doc().data:
            self.owner.design_change(lambda: self.owner.doc().replace(data))
            require(self.owner.doc().data == data,
                    'Enregistrement Content annulé : projet inchangé')
        if project.to_dict() != self.owner.project.to_dict():
            self.owner.project = project
            self.editor.reset_project()
        self.owner.refresh()
        self.status.set('Liaison validée : ' + source['id'] +
                        ('/' + source['choice'] if source['choice'] else '') +
                        ' → ' + target['id'] +
                        ' (Content + GameProject, historique global)')

    def _visual_recenter(self):
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
