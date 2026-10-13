"""3.7.21C: read-only, real-engine before/after isometric event scene.

Uses precisely the shared Map Editor/Player iso_map renderer and the two
disposable Battle instances from event_context. The preview does not create
an alternate renderer, game interpreter, or persistent project data.
"""
from .event_context import format_preview_report, preview_event
from .iso_map import IsoTerrainAtlas, render_isometric
from .iso_props import IsoPropAtlas
from .iso_building_atlas import IsoBuildingAtlas
from .iso_fortification_atlas import IsoFortificationAtlas
from .iso_actor_atlas import IsoActorAtlas

LAYERS = {name: True for name in
          ('Terrain', 'Relief', 'Décors', 'Bâtiments', 'Toitures',
           'Déploiement', 'Objectifs', 'Objets', 'Unités')}


def draw_preview(canvas, battle, *, highlighted=(), cell_size=44):
    """Paint a Battle snapshot with the exact shared isometric renderer."""
    atlases = (
        IsoTerrainAtlas(canvas), IsoPropAtlas(canvas),
        IsoBuildingAtlas(canvas), IsoFortificationAtlas(canvas),
        IsoActorAtlas(canvas),
    )
    # Keep PhotoImage refs alive while this Tk Canvas exists.
    canvas._event_preview_atlases = atlases
    geo = render_isometric(
        canvas, battle.board, battle.mission, battle.units,
        cell_size=cell_size, layers=LAYERS,
        selected_cell=None, selected_tiles=set(),
        atlas=atlases[0], prop_atlas=atlases[1],
        building_atlas=atlases[2], fortification_atlas=atlases[3],
        actor_atlas=atlases[4])
    for obj in battle.mission.objects:
        pos = tuple(obj['pos'])
        cx, cy = geo.center(pos)
        label = obj['id']
        if obj['kind'] == 'door':
            label += ' · ouverte' if obj.get('open', False) else ' · fermée'
        elif obj['kind'] == 'switch':
            label += ' · utilisé' if obj.get('used', False) else ' · disponible'
        color = '#22a889' if obj.get('open', False) else '#aa65d2'
        if obj['id'] in highlighted:
            canvas.create_polygon(*tuple(value for pair in geo.polygon(pos)
                                         for value in pair),
                                  outline='#fbbf24', fill='', width=4,
                                  tags='preview_changed_object')
        canvas.create_text(cx, cy+cell_size/2+11, text=label, fill=color,
                           font=('TkDefaultFont', 9, 'bold'),
                           tags='preview_object_label')
    return geo


def show_event_scene(editor, *, scenario='initial', tick=0):
    """Open a paired visual comparison; never replace Studio or Player state."""
    owner, tk, ttk = editor.owner, editor.tk, editor.ttk
    report = preview_event(owner.doc().data, owner.mission(),
                           editor.context['event_id'], scenario=scenario,
                           tick=tick, include_scene=True)
    before, after = report['scene_before'], report['scene_after']
    changed_objects = {
        obj['id'] for obj in after.mission.objects
        if obj != next((old for old in before.mission.objects
                       if old['id'] == obj['id']), obj)
    }
    window = tk.Toplevel(editor.tab)
    window.title('Aperçu isométrique — ' + editor.context['event_id'])
    window.geometry('1160x720')
    window.transient(editor.tab.winfo_toplevel())
    ttk.Label(window,
              text='Avant / après : bataille isolée, commandes et triggers du moteur réel',
              font=('TkDefaultFont', 12, 'bold')).pack(anchor='w', padx=10, pady=5)
    compare = ttk.Panedwindow(window, orient='horizontal')
    compare.pack(fill='both', expand=True, padx=8)
    for title, battle in (('AVANT — état préparé', before),
                          ('APRÈS — résolution moteur', after)):
        pane = ttk.LabelFrame(compare, text=title)
        compare.add(pane, weight=1)
        canvas = tk.Canvas(pane, bg='#202a36', highlightthickness=0)
        sx = ttk.Scrollbar(pane, orient='horizontal', command=canvas.xview)
        sy = ttk.Scrollbar(pane, orient='vertical', command=canvas.yview)
        canvas.configure(xscrollcommand=sx.set, yscrollcommand=sy.set)
        sx.pack(side='bottom', fill='x')
        sy.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)
        draw_preview(canvas, battle, highlighted=changed_objects)
        canvas.bind('<MouseWheel>', lambda event, c=canvas: c.yview_scroll(
            -1 if event.delta > 0 else 1, 'units'))
    footer = ttk.Frame(window)
    footer.pack(fill='x', padx=10, pady=5)
    synopsis = 'Aucun lien narratif avec la mission'
    if editor.context['scene_id']:
        synopsis = ('Après une victoire DE CAMPAGNE, scène liée : ' +
                    editor.context['scene_id'] +
                    '. L’aperçu isolé ne lance pas cette transition.')
        ttk.Button(footer, text='Ouvrir la scène narrative',
                   command=lambda: editor.open_linked_story()).pack(
                       side='right', padx=4)
    ttk.Label(footer, text=synopsis, wraplength=920).pack(side='left', fill='x')
    trace = tk.Text(window, height=8, wrap='word')
    trace.pack(fill='x', padx=10, pady=(0, 8))
    trace.insert('1.0', '\n'.join(format_preview_report(report)))
    trace.configure(state='disabled')
    return window
